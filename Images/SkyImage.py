import sys
import traceback
import math
import os.path
import time

from PyQt4.Qt import *
from PyQt4.Qwt5 import *
import  numpy
import numpy.ma
import pyfits
from scipy.ndimage import interpolation,measurements

import Kittens.utils

from Tigger.Coordinates import Projection
import Colormaps

DEG = math.pi/180;

_verbosity = Kittens.utils.verbosity(name="skyimage");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

class SkyImagePlotItem (QwtPlotItem,QObject):
  """SkyImagePlotItem is a 2D image in l,m coordimnates""";
  def __init__ (self,nx=0,ny=0,l0=0,m0=0,dl=1,dm=1,image=None):
    QwtPlotItem.__init__(self);
    # name, if any
    self.name = self.filename = None;
    # internal init
    self._qo = QObject();
    self._image = self._imgminmax = None;
    self._nvaluecalls = 0;
    self._value_time = self._value_time0 = None;
    self._lminmax = (0,0);
    self._mminmax = (0,0);
    self._cache_qimage = {};
    self._cache_mapping = self._cache_imap = self._cache_interp = None;
    # set image, if specified
    if image is not None:
      nx,ny = image.shape;
      self.setImage(image);
    # set coordinates, if specified
    if nx and ny:
      self.setImageCoordinates(nx,ny,l0,m0,dl,dm);
    # set default colormap and intensity map
    self.colormap = Colormaps.Greyscale;
    self.imap = Colormaps.LinearIntensityMap();

  def emit (self,*args):
    self._qo.emit(*args);

  def connect (self,*args):
    QObject.connect(self._qo,*args);

  def clearDisplayCache (self):
    """Clears all display caches.""";
    self._cache_qimage = {};
    self._cache_interp = self._cache_imap = None;

  def setColorMap(self,cmap=None,emit=True):
    """Changes the colormap. If called with no arguments, clears colormap-dependent caches""";
    self._cache_qimage = {};
    if cmap:
      self.colormap = cmap;
    if emit:
      self.emit(SIGNAL("repaint"));

  def setIntensityMap(self,imap=None,emit=True):
    """Changes the intensity map. If called with no arguments, clears intensity map-dependent caches""";
    self._cache_qimage = {};
    self._cache_imap = None;
    if imap:
      self.imap = imap;
    if emit:
      self.emit(SIGNAL("repaint"));

  def colorMap (self):
    return self.colormap;

  def intensityMap (self):
    return self.imap;

  def setImageCoordinates (self,nx,ny,x0,y0,l0,m0,dl,dm):
    """Sets up image coordinates. Pixel x0,y0 is centered at location l0,m0 in the plot, pixel size is dl,dm, image size is (nx,ny)"""
    dprint(2,"image coordinates are",nx,ny,x0,y0,l0,m0,dl,dm);
    self._nx,self._ny = nx,ny;
    self._l0,self._m0 = l0,m0;
    self._dl,self._dm = dl,dm;
    self._x0,self._y0 = x0,y0;
    self._lminmax = (l0-dl*(x0+0.5),l0+(nx-x0-0.5)*dl);
    if dl < 0:
      self._lminmax = (self._lminmax[1],self._lminmax[0]);
    self._mminmax = (m0-dm*(y0+0.5),m0+(ny-y0-0.5)*dm);
    self._bounding_rect = QRectF(self._lminmax[0],self._mminmax[0],nx*abs(dl),ny*abs(dm));
    self._bounding_rect_pix = QRect(0,0,nx,ny);
    dprint(2,"image extents are",self._lminmax,self._mminmax);

  def imageDims (self):
    """Returns image dimensions as mx,ny""";
    return self._nx,self._ny;

  def referencePixel (self):
    return self._x0,self._y0;

  def lmToPix (self,l,m):
    """Converts l,m coordimnates to float (so possibly fractional) pixel coordinates."""
    return self._x0+(l-self._l0)/self._dl,self._y0+(m-self._m0)/self._dm;

  def pixToLm (self,x,y):
    """Converts pixel coordinates to lm coordinates."""
    return self._l0 + (x-self._x0)*self._dl,self._m0 + (y-self._y0)*self._dm;

  def getExtents (self):
    """Returns image extent, as (l0,m0),(l1,m1)""";
    return self._lminmax,self._mminmax;

  def boundingRect (self):
    """Returns bouding rectangle of image, in lm coordinates.""";
    return self._bounding_rect;

  def currentRect (self):
    """Returns currently visible rectange, in lm coordinates. Coordinates may be outside of image range.""";
    return self._current_rect;

  def currentRectPix (self):
    """Returns currently visible rectange, in pixel coordinates. Pixel coordinates are bounded to 0,0 and nx-1,ny-1.""";
    return self._current_rect_pix;

  def setImage (self,image,key=None,minmax=None):
    """Sets image array.
    If key is not None, sets this as the image key (for use with the pixmap cache.)
    If minmax is not None, then stores this as the (presumably cached or precomputed) min/max values.
    """;
    self._image = image;
    self._imgminmax = minmax;
    self._image_key = key;
    # clear intermediate caches
    self._prefilter =  self._cache_interp = self._cache_imap = None;
    # if key is None, also clear QImage cache -- it only works when we have images identified by keys
    if key is None:
      self._cache_qimage = {};

  def image (self):
    """Returns image array.""";
    return self._image;

  def imageMinMax (self):
    if not self._imgminmax:
      self._imgminmax = measurements.extrema(self._image)[:2];
    return self._imgminmax;

  def draw (self,painter,xmap,ymap,rect):
    """Implements QwtPlotItem.draw(), to render the image on the given painter.""";
    xp1,xp2,xdp,xs1,xs2,xds = xinfo = xmap.p1(),xmap.p2(),xmap.pDist(),xmap.s1(),xmap.s2(),xmap.sDist();
    yp1,yp2,ydp,ys1,ys2,yds = yinfo = ymap.p1(),ymap.p2(),ymap.pDist(),ymap.s1(),ymap.s2(),ymap.sDist();
    dprint(5,"draw:",rect,xinfo,yinfo);
    self._current_rect = QRectF(QPointF(xs2,ys1),QSizeF(xds,yds));
    self._current_rect_pix = QRect(QPoint(*self.lmToPix(xs1,ys1)),QPoint(*self.lmToPix(xs2,ys2))).intersected(self._bounding_rect_pix);
    dprint(5,"draw:",self._current_rect_pix);
    # put together tuple describing current mapping
    mapping = xinfo,yinfo;
    # if mapping has changed w.r.t. cache (i.e. zoom has changed), discard all cached QImages
    if mapping != self._cache_mapping:
      dprint(2,"does not match cached mapping, cache is:",self._cache_mapping);
      dprint(2,"and we have:",mapping);
      self.clearDisplayCache();
      self._cache_mapping = mapping;
    t0 = time.time();
    # check cached QImage for current image key.
    qimg = self._cache_qimage.get(self._image_key);
    if qimg:
      dprint(5,"QImage found in cache, reusing");
    # else regenerate image
    else:
      # check for cached intensity-mapped data
      if self._cache_imap is not None:
        dprint(5,"intensity-mapped data found in cache, reusing");
      else:
        if self._cache_interp is not None:
          dprint(5,"interpolated data found in cache, reusing");
        else:
          self._cache_imap = None;
          if self._prefilter is None:
            self._prefilter = interpolation.spline_filter(self._image,order=2);
            dprint(2,"spline prefiltering took",time.time()-t0,"secs"); t0 = time.time();
          # make arrays of plot coordinates
          # xp[0],yp[0] corresponds to pixel 0,0, where 0,0 is the upper-left corner of the plot
          # the maps are in a funny order (w.r.t. meaning of p1/p2/s1/s2), so the indices here are determined empirically
          # We also adjust by half-pixel, to get the world coordinate of the pixel _center_
          xp = xmap.s1() - (xmap.sDist()/xmap.pDist())*(0.5+numpy.arange(int(xmap.pDist())));
          yp = ymap.s2() - (ymap.sDist()/ymap.pDist())*(0.5+numpy.arange(int(ymap.pDist())));
          # now convert plot coordinates into fractional image pixel coordinates
          xi = self._x0 + (xp - self._l0)/self._dl;
          yi = self._y0 + (yp - self._m0)/self._dm;
          # interpolate image data
          ###        # old code for nearest-neighbour interpolation
          ###        # superceded by interpolation below (we simply round pixel coordinates to go to NN when oversampling)
          ###        xi = xi.round().astype(int);
          ###        oob_x = (xi<0)|(xi>=self._nx);
          ###        xi[oob_x] = 0;
          ###        yi = yi.round().astype(int);
          ###        oob_y = (yi<0)|(yi>=self._ny);
          ###        yi[oob_y] = 0;
          ###        idx = (xi[:,numpy.newaxis]*self._ny + yi[numpy.newaxis,:]).ravel();
          ###        interp_image = self._image.ravel()[idx].reshape((len(xi),len(yi)));
          ###        interp_image[oob_x,:] = 0;
          ###        interp_image[:,oob_y] = 0;
          ###        self._qimage_cache = self.colormap.colorize(interp_image,self._img_range);
          ###        self._qimage_cache_attrs = (rect,xinfo,yinfo);
          # if either axis is oversampled by a factor of 3 or more, switch to nearest-neighbour interpolation by rounding pixel values
          if abs(xmap.sDist()/xmap.pDist()) < abs(self._dl/3):
            xi = xi.round();
          if abs(ymap.sDist()/ymap.pDist()) < abs(self._dm/3):
            yi = yi.round();
          # make [2,nx,ny] array of interpolation coordinates
          xy = numpy.zeros((2,len(xi),len(yi)));
          xy[0,:,:] = xi[:,numpy.newaxis];
          xy[1,:,:] = yi[numpy.newaxis,:];
          # interpolate. Use NAN for out of range pixels...
          interp_image = interpolation.map_coordinates(self._prefilter,xy,order=2 ,cval=numpy.nan,prefilter=False);
          # ...and put a mask on them (Colormap.colorize() will make these transparent).
          mask = numpy.isnan(interp_image);
          self._cache_interp = numpy.ma.masked_array(interp_image,mask);
          dprint(2,"interpolation took",time.time()-t0,"secs"); t0 = time.time();
        # ok, we have interpolated data in _cache_interp
        self._cache_imap = self.imap.remap(self._cache_interp);
        dprint(2,"intensity mapping took",time.time()-t0,"secs"); t0 = time.time();
      # ok, we have intensity-mapped data in _cache_imap
      qimg = self.colormap.colorize(self._cache_imap);
      dprint(2,"colorizing took",time.time()-t0,"secs"); t0 = time.time();
      # cache the qimage
      self._cache_qimage[self._image_key] = qimg.copy();
    # now draw the image
    t0 = time.time();
    painter.drawImage(xp1,yp2,qimg);
    dprint(2,"drawing took",time.time()-t0,"secs");

ScalePrefixes = [ "p","n",u"\u03bc","m","","K","M","G","T" ];

def getScalePrefix (*values):
  """Helper method to get the optimal scale and SI prefix for a given range of values""";
  # take log10. If all values are zero, use prefix of 1.
  log10 = numpy.ma.log10(numpy.ma.abs(values));
  if log10.mask.all():
    return 1,"";
  # find appropriate prefix
  # Add 1 to log10(min) (so that >=.1 unit is reported as unit), divide by 3, take floor, look up unit prefix
  m = int(math.floor((log10.min()+1)/3)) + 4;
  m = max(m,0);
  m = min(m,len(ScalePrefixes)-1);
  return 10**((m-4)*3),ScalePrefixes[m];

class SkyCubePlotItem (SkyImagePlotItem):
  """Extends SkyImagePlotItem with a hypercube containing extra slices.""";
  def __init__ (self,data=None,ndim=None):
    SkyImagePlotItem.__init__(self);
    # datacube (array of any rank)
    self._data = self._dataminmax = None;
    # current image slice (a list of indices) applied to data to make an image
    self.imgslice = None;
    # info about sky axes
    self._skyaxes = [None,None];
    # info about other axes
    self._extra_axes = [];
    # set other info
    if data is not None:
      self.setData(data);
    elif ndim:
      self.setNumAxes(ndim);

  def setData (self,data):
    """Sets the datacube.""";
    self._data = data;
    self._dataminmax = None;
    self.setNumAxes(data.ndim);

  def data (self):
    return self._data;

  def dataMinMax (self):
    if not self._dataminmax:
      self._dataminmax = measurements.extrema(self.data());
    return self._dataminmax;

  def setNumAxes (self,ndim):
    self.imgslice = [0]*ndim;

  def setSkyAxis (self,n,iaxis,nx,x0,dx,xpix0):
    """Sets the sky axis, n=0 for RA and n=1 for Dec"""
    if not self.imgslice:
      raise RuntimeError,"setNumAxes() must be called first";
    # reverse axis if step is negative
#    if dx<0:
#      dx = -dx;
#      xpix0 = nx-1-xpix0;
#      self.imgslice[iaxis] = slice(-1,None,-1);
#    else:
    self.imgslice[iaxis] = slice(None);
    self._skyaxes[n] = iaxis,nx,x0,dx,xpix0;
    if iaxis == 0:
      self.ra0 = x0;
    else:
      self.dec0 = x0;

  def getSkyAxis (self,n):
    return self._skyaxes[n][:2];

  def setExtraAxis (self,iaxis,name,labels,values,units):
    """Sets additional hypercube axis. labels is an array of strings, one per each axis element, for labelled axes, or None if axis should be labelled with values/units.
    values is an array of axis values, and units are the units in which values are expressed.
    """;
    units = units or "";
    scale,prefix = getScalePrefix(values);
    units = prefix+units;
    if labels is None:
      labels = [ "%d: %g %s"%(i,val/scale,units) for i,val in enumerate(values) ];
    self._extra_axes.append((iaxis,name,labels,values,units,scale));

  def numExtraAxes (self):
    return len(self._extra_axes);

  def extraAxisNumberNameLabels (self,i):
    return self._extra_axes[i][:3];

  def extraAxisValues (self,i):
    return self._extra_axes[i][3];

  def extraAxisUnitScale (self,i):
    return self._extra_axes[i][4:6];

  def setPlotProjection (self,proj=None):
    """Sets the projection of the plot. Must be called before image is drawn. If None is given, the default
    projection is used.
    """;
    if not (self._skyaxes[0] and self._skyaxes[1]):
      raise RuntimeError,"setSkyAxis() must be called for both sky axes";
    (iaxis_ra,nx,ra0,dra,i0),(iaxis_dec,ny,dec0,ddec,j0) = self._skyaxes;
    proj = proj or self.projection;
    # setup projection properties and get center of field
    l0,m0 = proj.lm(ra0,dec0);
    # find cell sizes
    if proj is self.projection:
      dl,dm = -self.projection.xscale,self.projection.yscale;
    else:
      dl = proj.offset(dra,0)[0];
      dm = proj.offset(0,ddec)[1];
    # setup image coordinates
    self.setImageCoordinates(nx,ny,i0,j0,l0,m0,dl,dm);

  def setDefaultProjection (self,projection=None):
    """Sets default image projection. If None is given, sets up default SinWCS projection.""";
    self.projection = projection or Projection.SinWCS(ra0,dec0);
    self.setPlotProjection();

  def _setupSlice (self):
    index = tuple(self.imgslice);
    key = tuple([ index[iaxis] for iaxis,name,labels,values,units,scale in self._extra_axes ]);
    self.setImage(self._data[index],key=key);

  def selectSlice (self,*indices):
    if len(indices) != len(self._extra_axes):
      raise ValueError,"number of indices does not match number of extra axes""";
    for i,(iaxis,name,labels,values,units,scale) in enumerate(self._extra_axes):
      self.imgslice[iaxis] = indices[i];
    self._setupSlice();
    self.emit(SIGNAL("slice"),indices);

  def currentSlice (self):
    return list(self.imgslice);

class FITSImagePlotItem (SkyCubePlotItem):
  def __init__ (self,filename=None,name=None):
    SkyCubePlotItem.__init__(self);
    self.name = name;
    if filename:
      self.read(filename);

  # Table of Stokes parameters corresponding to Stokes axis indices
  # Taken from Table 7, Greisen, E. W., and Calabretta, M. R., Astronomy & Astrophysics, 395, 1061-1075, 2002
  # (http://www.aanda.org/index.php?option=article&access=bibcode&bibcode=2002A%2526A...395.1061GFUL)
  # So StokesNames[1] == "I", StokesNames[-1] == "RR", StokesNames[-8] == "YX", etc.
  StokesNames = [ "","I","Q","U","V","YX","XY","YY","XX","LR","RL","LL","RR"  ];
  # complex axis convention
  ComplexNames = [ "","real","imag","weight" ];

  def read (self,filename):
    self.filename = filename;
    self.name = self.name or os.path.basename(filename);
    # read FITS file
    ff = pyfits.open(filename);
    ff[0].verify('silentfix');
    hdr = ff[0].header;
    # copying transposed data (thus into C order) somehow speeds up all subsequent operations
    self.setData(numpy.transpose(ff[0].data).copy());
    ndim = hdr['NAXIS'];
    # setup projection
    proj = Projection.FITSWCS(hdr);
    nx = ny = None;
    # find axes
    for iaxis in range(ndim):
      axs = str(iaxis+1);
      # get axis description
      npix = hdr['NAXIS'+axs];
      crval = hdr.get('CRVAL'+axs,0 );
      cdelt = hdr.get('CDELT'+axs,1) ;
      crpix = hdr.get('CRPIX'+axs,1) -1;
      name = hdr.get('CTYPE'+axs,axs).upper();
      unit = hdr.get('CUNIT'+axs);
      # have we found the coordinate axes?
      if name.startswith('RA'):
        nx = npix;
        iaxis_ra = iaxis;
      elif name.startswith('DEC'):
        ny = npix;
        iaxis_dec = iaxis;
      # else add axis to slicers
      else:
        # values becomes a list of axis values
        values = list(crval + numpy.arange(crpix,crpix+npix)*cdelt);
        unit = unit and unit.lower().capitalize();
        # FITS knows of two enumerable axes: STOKES and COMPLEX. For these two, replace values with proper names
        if name == "STOKES":
          labels = [ (self.StokesNames[int(i)] if i>0 and i<len(self.StokesNames) else "%d"%i) for i in values ];
        elif name == "COMPLEX":
          labels = [ (self.ComplexNames[int(i)] if i>0 and i<len(self.ComplexNames) else "%d"%i) for i in values ];
        else:
          name = name.split("-")[0];
          # if values are a simple sequence startying at 0 or 1, make simple labels
          if cdelt == 1 and values[0] in (0.,1.):
            labels = [ "%d%s"%(val,unit) for val in values ];
          # else set labels to None: setExtraAxis() will figure it out
          else:
            labels = None;
        self.setExtraAxis(iaxis,name,labels,values,unit);
    if nx is None or ny is None:
      raise ValueError,"FITS file does not appear to contain a RA and/or DEC axis";
    self.setSkyAxis(0,iaxis_ra,nx,proj.ra0,-proj.xscale,proj.xpix0);
    self.setSkyAxis(1,iaxis_dec,ny,proj.dec0,proj.yscale,proj.ypix0);
    self.setDefaultProjection(proj);
    self._setupSlice();

