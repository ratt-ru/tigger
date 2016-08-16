# -*- coding: utf-8 -*-
#
#% $Id$
#
#
# Copyright (C) 2002-2011
# The MeqTree Foundation &
# ASTRON (Netherlands Foundation for Research in Astronomy)
# P.O.Box 2, 7990 AA Dwingeloo, The Netherlands
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>,
# or write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import sys
import traceback
import math
import os.path
import time

from PyQt4.Qt import *
from PyQt4.Qwt5 import *
import  numpy
import numpy.ma
from scipy.ndimage import interpolation,measurements

import Kittens.utils
pyfits = Kittens.utils.import_pyfits();

from Tigger.Coordinates import Projection
from Tigger.Images import Colormaps
from Tigger.Images import FITSHeaders

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
    self._psfsize = 0,0,0;
    # set image, if specified
    if image is not None:
      nx,ny = image.shape;
      self.setImage(image);
    # set coordinates, if specified
    if nx and ny:
      self.setImageCoordinates(nx,ny,l0,m0,dl,dm);
    # set default colormap and intensity map
    self.colormap = Colormaps.GreyscaleColormap;
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

  def updateCurrentColorMap (self):
    self._cache_qimage = {};
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
    """Returns image extent, as (l0,l1),(m0,m1)""";
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

  def imagePixel (self,x,y):
    if numpy.ma.isMA(self._image):
      return self._image.data[x,y],self._image.mask[x,y];
    else:
      return self._image[x,y],False;

  def imageMinMax (self):
    if not self._imgminmax:
      dprint(3,"computing image min/max");
      rdata,rmask = self.optimalRavel(self._image);
      try:
        self._imgminmax = measurements.extrema(rdata,labels=rmask,index=None if rmask is None else False)[:2];
      except:
        # when all data is masked, some versions of extrema() throw an exception
        self._imgminmax = numpy.nan,numpy.nan;
      dprint(3,self._imgminmax);
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
          image = self._image.transpose() if self._data_fortran_order else self._image;
          spline_order = 2;
          xsamp = abs(xmap.sDist()/xmap.pDist())/abs(self._dl);
          ysamp = abs(ymap.sDist()/ymap.pDist())/abs(self._dm);
          if max(xsamp,ysamp) < .33 or min(xsamp,ysamp) > 2:
            spline_order = 1;
          dprint(2,"regenerating drawing cache, sampling factors are",xsamp,ysamp,"spline order is",spline_order);
          self._cache_imap = None;
          if self._prefilter is None and spline_order>1:
            self._prefilter = interpolation.spline_filter(image,order=spline_order);
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
          if xsamp < .33:
            xi = xi.round();
          if ysamp < .33:
            yi = yi.round();
          # make [2,nx,ny] array of interpolation coordinates
          xy = numpy.zeros((2,len(xi),len(yi)));
          xy[0,:,:] = xi[:,numpy.newaxis];
          xy[1,:,:] = yi[numpy.newaxis,:];
          # interpolate. Use NAN for out of range pixels...
          # for fortran order, tranpose axes for extra speed (flip XY around then)
          if self._data_fortran_order:
            xy = xy[-1::-1,...];
          if spline_order > 1:
            interp_image = interpolation.map_coordinates(self._prefilter,xy,order=spline_order,cval=numpy.nan,prefilter=False);
          else:
            interp_image = interpolation.map_coordinates(image,xy,order=spline_order,cval=numpy.nan);
          # ...and put a mask on them (Colormap.colorize() will make these transparent).
          mask = ~numpy.isfinite(interp_image);
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

  def setPsfSize (self,maj,min,pa):
    self._psfsize = maj,min,pa;

  def getPsfSize (self):
    return self._psfsize;

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

  def setData (self,data,fortran_order=False):
    """Sets the datacube. fortran_order is a hint, which makes iteration over
    fortran-order arrays faster when computing min/max and such.""";
    # Note that iteration order is absolutely critical for large cubes -- if data is in fortran
    # order in memory, then that's the way we should iterate over it, period. Transposing is too
    # slow. We therefore create 1D "views" of the data using numpy.ravel(x,order='F'), and use
    # thse to iterate over the data for things like min/max, masking, etc.
    if fortran_order:
      dprint(3,"setData: computing mask (fortran order)");
      rav = numpy.ravel(data,order='F');
      rfin = numpy.isfinite(rav);
      if rfin.all():
        dprint(3,"setData: phew, all finite, nothing to be masked");
        self._data = data;
      else:
        dprint(3,"setData: setting masked elements to 0");
        rmask = ~rfin;
        rav[rmask] = 0;
        dprint(3,"setData: creating masked array");
        mask = rmask.reshape(data.shape[-1::-1]).transpose();
        self._data = numpy.ma.masked_array(data,mask);
    else:
      dprint(3,"setData: computing mask (C order)");
      fin = numpy.isfinite(data);
      if fin.all():
        dprint(3,"setData: phew, all finite, nothing to be masked");
        self._data = data;
      else:
        dprint(3,"setData: setting masked elements to 0");
        mask = ~fin;
        data[mask] = 0;
        dprint(3,"setData: creating masked array");
        self._data = numpy.ma.masked_array(data,mask);
    dprint(3,"setData: wrapping up");
    self._data_fortran_order = fortran_order;
    self._dataminmax = None;
    self.setNumAxes(data.ndim);
    ### old slow code
    #dprint(3,"setData: computing mask");
    #fin = numpy.isfinite(data);
    #mask = ~fin;
    #dprint(3,"setData: setting masked elements to 0");
    #data[mask] = 0;
    #dprint(3,"setData: creating masked array");
    #self._data = numpy.ma.masked_array(data,mask);
    #dprint(3,"setData: wrapping up");
    #self._data_fortran_order = fortran_order;
    #self._dataminmax = None;
    #self.setNumAxes(data.ndim);

  def data (self):
    """Returns datacube""";
    return self._data;

  def isDataInFortranOrder (self):
    return self._data_fortran_order;

  def optimalRavel (self,array):
    """Returns the "optimal ravel" corresponding to the given array, which is either FORTRAN
    or C order. The optimal ravel is that over which iteration is fastest.
    Returns tuple of ravarray,ravmask. If input array is not masked, then ravmask=None."""
    order = 'F' if self._data_fortran_order else 'C';
    rarr = numpy.ravel(array,order=order);
    rmask = numpy.ravel(array.mask,order=order) if numpy.ma.isMA(array) else None;
    return rarr,rmask;

  def dataMinMax (self):
    if not self._dataminmax:
      rdata,rmask = self.optimalRavel(self._data);
      dprint(3,"computing data min/max");
      try:
        self._dataminmax = measurements.extrema(rdata,labels=rmask,index=None if rmask is None else False);
      except:
        # when all data is masked, some versions of extrema() throw an exception
        self._dataminmax = numpy.nan,numpy.nan;
      dprint(3,self._dataminmax);
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
    # estimate number of significant digits
    valarr = numpy.array(values)/scale;
    try:
      ndigits = int(math.ceil(math.log10(max(abs(valarr))/abs((valarr[1:]-valarr[0:-1])).min())));
      nexp = int(abs(numpy.log10(abs(valarr))).max());
 #     print ndigits,nexp;
      if nexp > 4:
        format = ".%de"%ndigits;
      else:
        format = ".%df"%ndigits;
    except:
      format = ".2g";
    if labels is None:
      labels = [ ("%d: %"+format+" %s")%(i,val/scale,units) for i,val in enumerate(values) ];
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
    image = self._data[index];
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

  @staticmethod
  def hasComplexAxis (hdr):
    """Returns True if given FITS header has a complex axis (must be last axis)""";
    nax = hdr['NAXIS'];
    return nax if hdr['CTYPE%d'%nax].strip() == "COMPLEX" else 0;

  @staticmethod
  def addComplexAxis (header):
    """Adds a complex axis to the given FITS header, returns new copy of header""";
    hdr = header.copy();
    nax = hdr['NAXIS']+1;
    hdr['NAXIS'] = nax;
    hdr.set('NAXIS%d'%nax,2,"complex image");
    hdr.set('CTYPE%d'%nax,"COMPLEX","complex image");
    hdr.set('CRPIX%d'%nax,1);
    hdr.set('CRVAL%d'%nax,1);
    hdr.set('CDELT%d'%nax,1);
    return hdr;

  @staticmethod
  def removeComplexAxis (header):
    """Removes a complex axis from the given FITS header, returns new copy of header""";
    axis = FITSImagePlotItem.hasComplexAxis(header);
    if axis:
      header = header.copy();
      header['NAXIS'] = axis-1;
      for name in 'NAXIS','CTYPE','CRPIX','CRVAL','CDELT':
        key = "%s%d"%(name,axis);
        if header.has_key(key):
          del header[key];
    return header;

  def __init__ (self,filename=None,name=None,hdu=None):
    SkyCubePlotItem.__init__(self);
    self.name = name;
    if filename or hdu:
      self.read(filename,hdu);

  StokesNames = FITSHeaders.StokesNames;
  ComplexNames = FITSHeaders.ComplexNames;

  def read (self,filename,hdu=None):
    self.filename = filename;
    self.name = self.name or os.path.basename(filename);
    # read FITS file
    if not hdu:
      dprint(3,"opening",filename);
      hdu = pyfits.open(filename)[0];
      hdu.verify('silentfix');
    hdr = self.fits_header = hdu.header;
    dprint(3,"reading data");
    data = hdu.data;
    # NB: all-data operations (such as getting global min/max or computing of histograms) are much faster
    # (almost x2) when data is iterated
    # over in the proper order. After a transpose(), data is in fortran order. Tell this to setData().
    data = numpy.transpose(data);  # .copy()
    dprint(3,"setting data");
    self.setData(data,fortran_order=True);
    dprint(3,"reading header");
    ndim = hdr['NAXIS'];
    if ndim < 2:
      raise ValueError,"Cannot load a one-dimensional FITS file";
    # setup projection
    # (strip out history from header, as big histories really slow down FITSWCS)
    hdr1 = pyfits.Header(filter(lambda x:not str(x).startswith('HISTORY'),hdr.cards));
    proj = Projection.FITSWCS(hdr1);
    nx = ny = None;
    # find X and Y axes
    for iaxis in range(ndim):
      axs = str(iaxis+1);
      npix = hdr['NAXIS'+axs];
      name = hdr.get('CTYPE'+axs,axs).strip().upper();
      # have we found the coordinate axes?
      if FITSHeaders.isAxisTypeX(name):
        nx = npix;
        iaxis_ra = iaxis;
      elif FITSHeaders.isAxisTypeY(name):
        ny = npix;
        iaxis_dec = iaxis;
    # check that we have them
    if nx is None or ny is None:
      iaxis_ra,iaxis_dec = 0,1;
      nx,ny = hdr.get('NAXIS1'),hdr.get('NAXIS2');
    for iaxis in range(ndim):
      axs = str(iaxis+1);
      # get axis description
      npix = hdr['NAXIS'+axs];
      crval = hdr.get('CRVAL'+axs,0 );
      cdelt = hdr.get('CDELT'+axs,1) ;
      crpix = hdr.get('CRPIX'+axs,1) -1;
      name = hdr.get('CTYPE'+axs,axs).strip().upper();
      unit = hdr.get('CUNIT'+axs);
      # if this is not an X/Y axis, add it to the slicers
      if iaxis not in (iaxis_ra,iaxis_dec):
        # values becomes a list of axis values
        values = list(crval + (numpy.arange(npix) - crpix)*cdelt);
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
        self.setExtraAxis(iaxis,name or ("axis "+axs),labels,values,unit);
    # check for beam parameters
    psf = [ hdr.get(x,None) for x in 'BMAJ','BMIN','BPA' ];
    if all([x is not None for x in psf]):
      self.setPsfSize(*[ p/180*math.pi for p in psf ]);
    self.setSkyAxis(0,iaxis_ra,nx,proj.ra0,-proj.xscale,proj.xpix0);
    self.setSkyAxis(1,iaxis_dec,ny,proj.dec0,proj.yscale,proj.ypix0);
    self.setDefaultProjection(proj);
    dprint(3,"setting initial slice");
    self._setupSlice();

  def save (self,filename):
    data = data1 = self.data().transpose();
    if numpy.ma.isMA(data):
      data1 = data.data.copy();
      data1[data.mask] = numpy.NAN;
    hdu = pyfits.PrimaryHDU(data1,self.fits_header);
    hdu.verify('silentfix');
    if os.path.exists(filename):
      os.remove(filename);
    hdu.writeto(filename,clobber=True);
    self.filename = filename;
    self.name = os.path.basename(filename);
