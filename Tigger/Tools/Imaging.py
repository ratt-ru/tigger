# -*- coding: utf-8 -*-
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

import Kittens.utils
pyfits = Kittens.utils.import_pyfits();
import math
import numpy

from Tigger.Coordinates import Projection,radec_string
from Tigger.Images import FITSHeaders
from scipy.ndimage.filters import convolve
from scipy.ndimage.interpolation import map_coordinates
import astLib.astWCS

# init debug printing
import Kittens.utils
_verbosity = Kittens.utils.verbosity(name="imaging");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

# conversion factors from radians
DEG = 180/math.pi;
ARCMIN = DEG*60;
ARCSEC = ARCMIN*60;
FWHM = math.sqrt(math.log(256));  # which is 2.3548;

def fitPsf (filename,cropsize=None):
  """Fits a Gaussian PSF to the FITS file given by 'filename'.
  If cropsize is specified, crops the central cropsize X cropsize pixels before fitting.
  Else determines cropsize by looking for the first negative sidelobe from the centre outwards.
  Returns maj_sigma,min_sigma,pa_NE (in radians)
  """;
  # read PSF from file
  psf = pyfits.open(filename)[0];
  hdr = psf.header;
  psf = psf.data;
  dprintf(2,"Read PSF of shape %s from file %s\n",psf.shape,filename);
  # remove stokes and freq axes
  if len(psf.shape) == 4:
    psf = psf[0,0,:,:];
  elif len(psf.shape) == 3:
    psf = psf[0,:,:];
  else:
    raise RuntimeError,"illegal PSF shape %s"+psf.shape;
  nx,ny = psf.shape;
  # crop the central region
  if cropsize:
    size = cropsize;
    psf = psf[(nx-size)//2:(nx+size)//2,(ny-size)//2:(ny+size)//2];
  # if size not specified, then auto-crop by looking for the first negative value starting from the center
  # this will break on very extended diagonal PSFs, but that's a pathological case
  else:
    ix = numpy.where(psf[:,ny//2]<0)[0];
    ix0 = max(ix[ix<nx//2]);
    ix1 = min(ix[ix>nx//2]);
    iy = numpy.where(psf[nx//2,:]<0)[0];
    iy0 = max(iy[iy<ny//2]);
    iy1 = min(iy[iy>ny//2]);
    print ix0,ix1,iy0,iy1;
    psf = psf[ix0:ix1,iy0:iy1];
  psf[psf<0] = 0;

  # estimate gaussian parameters, then fit
  import gaussfitter2
  parms0 = gaussfitter2.moments(psf,circle=0,rotate=1,vheight=0);
  print parms0;
  dprint(2,"Estimated parameters are",parms0);
  parms = gaussfitter2.gaussfit(psf,None,parms0,autoderiv=1,return_all=0,circle=0,rotate=1,vheight=0);
  dprint(0,"Fitted parameters are",parms);

  # now swap x and y around, since our axes are in reverse order
  ampl,y0,x0,sy,sx,rot = parms;

  # get pixel sizes in radians (by constructing a projection object)
  proj = Projection.FITSWCS(hdr);
  xscale,yscale = proj.xscale,proj.yscale;

  sx_rad = abs(sx * proj.xscale);
  sy_rad = abs(sy * proj.yscale);
  rot -= 90;  # convert West through North PA into the conventional North through East
  if sx_rad < sy_rad:
    sx_rad,sy_rad = sy_rad,sx_rad;
    rot -= 90;
  rot %= 180;

  dprintf(1,"Fitted gaussian PSF FWHM of %f x %f pixels (%f x %f arcsec), PA %f deg\n",sx*FWHM,sy*FWHM,sx_rad*FWHM*ARCSEC,sy_rad*FWHM*ARCSEC,rot);

  return sx_rad,sy_rad,rot/DEG;

def convolveGaussian (x1,y1,p1,x2,y2,p2):
    """convolves a Gaussian with extents x1,y1 and position angle p1
    with another Gaussian given by x2,y2,p2, and returns the extents 
    and angle of the resulting Gaussian."""
    # convert to Fourier plane extents, FT transforms a -> pi^2/a
    u1,v1,u2,v2 = [ (math.pi**2)*2*a**2 for a in x1,y1,x2,y2 ];
#    print "uv coeffs",u1,v1,u2,v2;
    c1,s1 = math.cos(p1),math.sin(p1);
    c2,s2 = math.cos(p2),math.sin(p2);
    # in the FT, this is a product of two Gaussians, each of the form:
    #   exp(-( u*(cx+sy)^2 + v*(cx-sy)^2))
    # note how we rotate BACK through the position angle
    # The product is necessarily a Gaussian itself, of the form
    #   exp(-(a.u^2+2b.u.v+c.v^2))
    # So we just need to collect the rotated Gaussian coefficients into a, b and c
    a = u1*c1**2+v1*s1**2+u2*c2**2+v2*s2**2
    c = u1*s1**2+v1*c1**2+u2*s2**2+v2*c2**2
    b = c1*s1*(u1-v1)+c2*s2*(u2-v2)
#    print "a,b,c",a,b,c;
    # ok, find semi-major axes a1, b1 using the formula from http://mathworld.wolfram.com/Ellipse.html eq. 21-22
    # to go from a general quadratic curve (with a,b,c given above, d=f=0, g=-1) to semi-axes a',b'
    D = math.sqrt((a-c)**2+4*b**2)
    E = a+c
    a1 = math.sqrt(2/(E-D))
    b1 = math.sqrt(2/(E+D))
#    print "a',b'",a1,b1,"coeffs",1/(a1**2),1/(b1**2)
    # and derive rotation angle
    if b:
        p1 = math.atan2(2*b,a-c)/2 + math.pi/2
#        if a > c:
#          p1 += math.pi/2
    else:
        p1 = 0 if a <= c else math.pi/2
#    print "rotation",p1/DEG
    # ok, convert a1,b1 from uv-plane to image plane 
    x1 = math.sqrt(1/(2*math.pi**2*a1**2))
    y1 = math.sqrt(1/(2*math.pi**2*b1**2))
    # note that because of reciprocality, y1 becomes the major axis and x1 the minor axis, so adjust for that
    return y1,x1,(p1-math.pi/2)%math.pi;  
  
def getImageCube (fitshdu,filename="",extra_axes=None):
  """Converts a FITS HDU (consisting of a header and data) into a 4+-dim numpy array where the
  first two axes are x and y, the third is Stokes (possibly of length 1, if missing in the
  original image), and the rest are either as found in the FITS header (if extra_axes=None),
  or in the order specified by CTYPE in extra_axes (if present, else a dummy axis of size 1 is inserted),
  with axes not present in extra_axes removed by taking the 0-th plane along each.
  Returns tuple of
    array,stokes_list,extra_axes_ctype_list,removed_axes_ctype_list
  e.g. array,("I","Q"),("FREQ--FOO","TIME--BAR")
  """
  hdr = fitshdu.header;
  data = fitshdu.data;
  # recognized axes
  ix = iy = istokes = None;
  naxis = len(data.shape);
  # other axes which will be returned
  other_axes = [];
  other_axes_ctype = [];
  remove_axes = [];
  remove_axes_ctype = [];
  # match axis ctype
  # this makes FREQ equivalent to FELO*
  def match_ctype (ctype,ctype_list):
    for i,ct in enumerate(ctype_list):
      if ct == ctype or ( ct == "FREQ" and ctype.startswith("FELO") ) or ( ctype == "FREQ" and ct.startswith("FELO") ):
        return i;
    return None;
  # identify X, Y and stokes axes
  for n in range(naxis):
    iax = naxis-1-n;
    axs = str(n+1);
    ctype = hdr.get('CTYPE'+axs).strip().upper();
    if ix is None and FITSHeaders.isAxisTypeX(ctype):
      ix = iax; # in numpy order, axes are reversed
    elif iy is None and FITSHeaders.isAxisTypeY(ctype):
      iy = iax;
    elif ctype == 'STOKES':
      if istokes is not None:
        raise ValueError,"duplicate STOKES axis in FITS file %s"%filename;
      istokes = iax;
      crval = hdr.get('CRVAL'+axs,0);
      cdelt = hdr.get('CDELT'+axs,1);
      crpix = hdr.get('CRPIX'+axs,1)-1;
      values = map(int,list(crval + (numpy.arange(data.shape[iax]) - crpix)*cdelt));
      stokes_names = [ (FITSHeaders.StokesNames[i]
                        if i>0 and i<len(FITSHeaders.StokesNames) else "%d"%i) for i in values ];
    else:
      other_axes.append(iax);
      other_axes_ctype.append(ctype);
  # not found?
  if ix is None or iy is None:
    raise ValueError,"FITS file %s does not appear to contain an X and/or Y axis"%filename;
  # form up shape of resulting image, and order of axes for transpose
  shape = [data.shape[ix],data.shape[iy]];
  axes = [ix,iy];
  # add stokes axis
  if istokes is None:
    shape.append(1);
    stokes_names = ("I",);
  else:
    shape.append(data.shape[istokes]);
    axes.append(istokes);
  if extra_axes:
    # if a fixed order for the extra axes is specified, add the ones we found
    for ctype in extra_axes:
      i = match_ctype(ctype,other_axes_ctype);
      if i is not None:
        iax = other_axes[i];
        axes.append(iax);
        shape.append(data.shape[iax]);
      else:
        shape.append(1);
    # add the ones that were not found into the remove list
    for iaxis,ctype in zip(other_axes,other_axes_ctype):
      if match_ctype(ctype,extra_axes) is None:
        axes.append(iaxis);
        remove_axes.append(iaxis);
        remove_axes_ctype.append(ctype);
  # return all extra axes found in header
  else:
    shape += [ data.shape[i] for i in other_axes ];
    axes += other_axes;
    extra_axes = other_axes_ctype;
  # tranpose
  data = data.transpose(axes);
  # trim off axes which are to be removed, if we have any
  if remove_axes:
    data = data[[Ellipsis]+[0]*len(remove_axes)];
  # reshape and return
  return data.reshape(shape),stokes_names,extra_axes,remove_axes_ctype;


class ImageResampler (object):
  """This class resamples images from one projection ("source") to another ("target").""";
  def __init__(self,sproj,tproj,sl,sm,tl,tm):
    """Creates resampler.
    sproj,tproj are the source and target Projection objects.
    sl,sm is a (sorted, ascending) list of l,m coordinates in the source image
    tl,tm is a (sorted, ascending) list of l,m coordinates in the target image
    """
    # convert tl,tm to to source coordinates
    # find the overlap region first, to keeps the number of coordinate conversions to a minimum
    overlap = astLib.astWCS.findWCSOverlap(sproj.wcs,tproj.wcs);
    tx2,tx1,ty1,ty2 = overlap['wcs2Pix'];
    # no overlap? stop then
    if tx1 > tl[-1] or tx2 < tl[0] or ty1 > tm[-1] or ty2 < tm[0]:
      self._target_slice = None,None;
      return;
    tx1 = max(0,int(math.floor(tx1)));
    tx2 = min(len(tl),int(math.floor(tx2+1)));
    ty1 = max(0,int(math.floor(ty1)));
    ty2 = min(len(tm),int(math.floor(ty2+1)));
    tl = tl[tx1:tx2];
    tm = tm[ty1:ty2];
    dprint(4,"overlap target pixels are %d:%d and %d:%d"%(tx1,tx2,ty1,ty2));

    #### The code below works but can be very slow  (~minutes) when doing large images, because of WCS
    ## make target lm matrix
    #tmat = numpy.zeros((2,len(tl),len(tm)));
    #tmat[0,...] = tl[:,numpy.newaxis];
    #tmat[1,...] = tm[numpy.newaxis,:];
    ## convert this to radec. Go through list since that's what Projection expects
    #dprint(4,"converting %d target l/m pixel coordinates to radec"%(len(tl)*len(tm)));
    #ra,dec = tproj.radec(tmat[0,...].ravel(),tmat[1,...].ravel())
    #dprint(4,"converting radec to source l/m");
    #tls,tms = sproj.lm(ra,dec);
    #tmat[0,...] = tls.reshape((len(tl),len(tm)));
    #tmat[1,...] = tms.reshape((len(tl),len(tm)));

    #### my alternative conversion code
    ## source to target is always an affine transform (one image projected into the plane of another, right?), so
    ## use WCS to map the corners, and figure out a linear transform from there

    # this maps three corners
    t00 = sproj.lm(*tproj.radec(tl[0],tm[0]));
    t1x = sproj.lm(*tproj.radec(tl[-1],tm[0]));
    t1y = sproj.lm(*tproj.radec(tl[0],tm[-1]));

    tmat = numpy.zeros((2,len(tl),len(tm)));
    tlnorm = (tl-tl[0])/(tl[-1]-tl[0]);
    tmnorm = (tm-tm[0])/(tm[-1]-tm[0]);
    tmat[0,...] = t00[0] + (tlnorm*(t1x[0]-t00[0]))[:,numpy.newaxis] + (tmnorm*(t1y[0]-t00[0]))[numpy.newaxis,:];
    tmat[1,...] = t00[1] + (tmnorm*(t1y[1]-t00[1]))[numpy.newaxis,:] + (tlnorm*(t1x[1]-t00[1]))[:,numpy.newaxis];

    dprint(4,"setting up slices");
    # ok, now find pixels in tmat that are within the source image extent
    tmask = (sl[0]<=tmat[0,...])&(tmat[0,...]<=sl[-1])&(sm[0]<=tmat[1,...])&(tmat[1,...]<=sm[-1]);
    # find extents along target's l and m axis
    # tmask_l/m is true for each target column/row that has pixels within the source image
    tmask_l = numpy.where(tmask.sum(1)>0)[0];
    tmask_m = numpy.where(tmask.sum(0)>0)[0];
    # check if there's no overlap at all -- return then
    if not len(tmask_l) or not len(tmask_m):
      self._target_slice = None,None;
      return;
    # ok, now we know over which pixels of the target image need to be interpolated
    ix0,ix1 = tmask_l[0],tmask_l[-1]+1;
    iy0,iy1 = tmask_m[0],tmask_m[-1]+1;
    self._target_slice = slice(ix0+tx1,ix1+tx1),slice(iy0+ty1,iy1+ty1);
    dprint(4,"slices are",ix0,ix1,iy0,iy1);
    # make [2,nx,ny] array of interpolation coordinates
    self._target_coords = tmat[:,ix0:ix1,iy0:iy1];

  def targetSlice (self):
    return self._target_slice;

  def __call__ (self,image):
    if self._target_slice[0] is None:
      return 0;
    else:
      return map_coordinates(image,self._target_coords);

def restoreSources (fits_hdu,sources,gmaj,gmin=None,grot=0,freq=None,primary_beam=None,apply_beamgain=False,ignore_nobeam=False):
  """Restores sources (into the given FITSHDU) using a Gaussian PSF given by gmaj/gmin/grot, in radians.
  gmaj/gmin is major/minor sigma parameter; grot is PA in the North thru East convention (PA=0 is N).

  If gmaj=0, uses delta functions instead.
  If freq is specified, converts flux to the specified frequency.
  If primary_beam is specified, uses it to apply a PB gain to each source. This must be a function of two arguments:
  r and freq, returning the power beam gain.
  If apply_beamgain is true, applies beamgain atribute instead, if this exists.
  Source tagged 'nobeam' will not have the PB gain applied, unless ignore_nobeam=True
  """;
  hdr = fits_hdu.header;
  data,stokes,extra_data_axes,dum = getImageCube(fits_hdu);
  # create projection object, using pixel coordinates
  proj = Projection.FITSWCSpix(hdr);
  naxis = len(data.shape);
  nx = data.shape[0];
  ny = data.shape[1];
  dprintf(1,"Read image of shape %s\n",data.shape);
  # Now we make "indexer" tuples. These use the numpy.newarray index to turn elementary vectors into
  # full arrays of the same number of dimensions as 'data' (data can be 2-, 3- or 4-dimensional, so we need
  # a general solution.)
  # For e.g. a nfreq x nstokes x ny x nx array, the following objects are created:
  #   x_indexer    turns n-vector vx into a _,_,_,n array
  #   y_indexer    turns m-vector vy into a _,_,m,_ array
  #   stokes_indexer turns the stokes vector into a _,nst,_,_ array
  # ...where "_" is numpy.newaxis.
  # The happy result of all this is that we can add a Gaussian into the data array at i1:i2,j1:j2 as follows:
  #  1. form up vectors of world coordinates (vx,vy) corresponding to pixel coordinates i1:i2 and j1:j2
  #  2. form up vector of Stokes parameters
  #  3. g = Gauss(vx[x_indexer],vy[y_indexer])*stokes[stokes_indexer]
  #  4. Just say data[j1:j2,i1:2,...] += g
  # This automatically expands all array dimensions as needed.

  # This is a helper function, returns an naxis-sized tuple, with slice(None) in the Nth
  # position, and elem_index elsewhere.
  def make_axis_indexer (n,elem_index=numpy.newaxis):
    indexer = [elem_index]*naxis;
    indexer[n] = slice(None);
    return tuple(indexer);
  x_indexer = make_axis_indexer(0);
  y_indexer = make_axis_indexer(1);
  # figure out stokes
  nstokes = len(stokes);
  stokes_vec = numpy.zeros((nstokes,));
  stokes_indexer = make_axis_indexer(2);
  dprint(2,"Stokes are",stokes);
  dprint(2,"Stokes indexing vector is",stokes_indexer);
  # get pixel sizes, in radians
  # gmaj != 0: use gaussian. Estimate PSF box size. We want a +/-5 sigma box
  if gmaj > 0:
    # convert grot from N-E to W-N (which is the more conventional mathematical definition of these things), so X is major axis
    grot += math.pi/2;  
    if gmin == 0:
      gmin = gmaj;
    cos_rot = math.cos(grot);
    sin_rot = math.sin(-grot);  # rotation is N->E, so swap the sign
  else:
    gmaj = gmin = grot = 0;
  conv_kernels = {};
  # loop over sources in model
  for src in sources:
    # get normalized intensity, if spectral info is available
    if freq is not None and getattr(src,'spectrum',None):
      ni = src.spectrum.normalized_intensity(freq);
      dprintf(3,"Source %s: normalized spectral intensity is %f\n",src.name,ni);
    else:
      ni = 1;
    #  multiply that by PB gain, if given
    if ignore_nobeam or not getattr(src,'nobeam',False):
      if apply_beamgain and hasattr(src,'beamgain'):
        ni *= getattr(src,'beamgain');
      elif primary_beam:
        r = getattr(src,'r',None);
        if r is not None:
          pb = primary_beam(r,freq);
          ni *= pb;
        dprintf(3,"Source %s: r=%g pb=%f, normalized intensity is %f\n",src.name,r,pb,ni);
    # process point sources
    if src.typecode in ('pnt','Gau'):
      # pixel coordinates of source
      xsrc,ysrc = proj.lm(src.pos.ra,src.pos.dec);
      # form up stokes vector
      for i,st in enumerate(stokes):
         stokes_vec[i] = getattr(src.flux,st,0)*ni;
      dprintf(3,"Source %s, %s Jy, at pixel %f,%f\n",src.name,stokes_vec,xsrc,ysrc);
      # for gaussian sources, convolve with beam
      if src.typecode == 'Gau':
        pa0 = src.shape.pa+math.pi/2;  # convert PA from N->E to conventional W->N
        ex0,ey0 = src.shape.ex/FWHM,src.shape.ey/FWHM;  # convert extents from FWHM to sigmas, since gmaj/gmin is in same scale
        if gmaj > 0:
          ex,ey,pa = convolveGaussian(ex0,ey0,pa0,gmaj,gmin,grot);
          # normalize flux by beam/extent ratio
          stokes_vec *= (gmaj*gmin)/(ex*ey);
          #print "%3dx%-3d@%3d * %3dx%-3d@%3d -> %3dx%-3d@%3d"%(
            #ex0 *FWHM*ARCSEC,ey0 *FWHM*ARCSEC,(pa0-math.pi/2)*DEG,
            #gmaj*FWHM*ARCSEC,gmin*FWHM*ARCSEC,(grot-math.pi/2)*DEG,
            #ex  *FWHM*ARCSEC,ey  *FWHM*ARCSEC,(pa-math.pi/2)*DEG);
        else:
          # normalize flux by pixel/extent ratio
          ex,ey,pa = ex0,ey0,pa0;
          stokes_vec *= (abs(proj.xscale*proj.yscale))/(ex*ey);
      else:
        ex,ey,pa = gmaj,gmin,grot;
      # gmaj != 0: use gaussian.
      if ex > 0 or ey > 0:
        # work out restoring box
        box_radius = 5*(max(ex,ey))/min(abs(proj.xscale),abs(proj.yscale));
        dprintf(2,"Will use a box of radius %f pixels for restoration\n",box_radius);
        cos_pa = math.cos(pa);
        sin_pa = math.sin(-pa);  # rotation is N->E, so swap the sign
        # pixel coordinates of box around source in which we evaluate the gaussian
        i1 = max(0,int(math.floor(xsrc-box_radius)));
        i2 = min(nx,int(math.ceil(xsrc+box_radius)));
        j1 = max(0,int(math.floor(ysrc-box_radius)));
        j2 = min(ny,int(math.ceil(ysrc+box_radius)));
        # skip sources if box doesn't overlap image
        if i1>=i2 or j1>=j2:
          continue;
        # now we convert pixel indices within the box into world coordinates, relative to source position
        xi = (numpy.arange(i1,i2) - xsrc)*proj.xscale;
        yj = (numpy.arange(j1,j2) - ysrc)*proj.yscale;
        # work out rotated coordinates
        xi1 = (xi*cos_pa)[x_indexer] - (yj*sin_pa)[y_indexer];
        yj1 = (xi*sin_pa)[x_indexer] + (yj*cos_pa)[y_indexer];
        # evaluate gaussian at these, scale up by stokes vector
        gg = stokes_vec[stokes_indexer]*numpy.exp(-((xi1/ex)**2+(yj1/ey)**2)/2.);
        # add into data
        data[i1:i2,j1:j2,...] += gg;
      # else gmaj=0: use delta functions
      else:
        xsrc = int(round(xsrc));
        ysrc = int(round(ysrc));
        # skip sources outside image
        if xsrc < 0 or xsrc >= nx or ysrc < 0 or ysrc >= ny:
          continue;
        xdum = numpy.array([1]);
        ydum = numpy.array([1]);
        data[xsrc:xsrc+1,ysrc:ysrc+1,...] += stokes_vec[stokes_indexer]*xdum[x_indexer]*ydum[y_indexer];
    # process model images -- convolve with PSF and add to data
    elif src.typecode == "FITS":
      modelff = pyfits.open(src.shape.filename);
      model,model_stokes,extra_model_axes,removed_model_axes = \
          getImageCube(modelff[0],src.shape.filename,extra_axes=extra_data_axes);
      modelproj = Projection.FITSWCSpix(modelff[0].header);
      # map Stokes planes: at least the first one ("I", presumably) must be present
      # The rest are represented by indices in model_stp. Thus e.g. for an IQUV data image and an IV model,
      # model_stp will be [0,-1,-1,1]
      model_stp = [ (model_stokes.index(st) if st in model_stokes else -1) for st in stokes ];
      if model_stp[0] < 0:
        print "Warning: model image %s lacks Stokes %s, skipping."%(src.shape.filename,model_stokes[0]);
        continue;
      # figure out whether the images overlap at all
      # in the trivial case, both images have the same WCS, so no resampling is needed
      if model.shape[:2] == data.shape[:2] and modelproj == proj:
        model_resampler = lambda x:x;
        data_x_slice = data_y_slice = slice(None);
        dprintf(3,"Source %s: same resolution as output, no interpolation needed\n",src.shape.filename);
      # else make a resampler engine
      else:
        model_resampler = ImageResampler(modelproj,proj,
          numpy.arange(model.shape[0],dtype=float),numpy.arange(model.shape[1],dtype=float),
          numpy.arange(data.shape[0],dtype=float),numpy.arange(data.shape[1],dtype=float));
        data_x_slice,data_y_slice = model_resampler.targetSlice();
        dprintf(3,"Source %s: resampling into image at %s, %s\n",src.shape.filename,data_x_slice,data_y_slice);
        # skip this source if no overlap
        if data_x_slice is None or data_y_slice is None:
          continue;
      # warn about ignored model axes (e.g. when model has frequency and our output doesn't)
      if removed_model_axes:
        print "Warning: model image %s has one or more axes that are not present in the output image:"%src.shape.filename;
        print "  taking the first plane along (%s)."%(",".join(removed_model_axes));
      # evaluate convolution kernel for this model scale, if not already cached
      conv_kernel = conv_kernels.get((modelproj.xscale,modelproj.yscale),None);
      if conv_kernel is None:
        box_radius = 5*(max(gmaj,gmin))/min(abs(modelproj.xscale),abs(modelproj.yscale));
        radius = int(round(box_radius));
        # convert pixel coordinates into world coordinates relative to 0
        xi = numpy.arange(-radius,radius+1)*modelproj.xscale
        yj = numpy.arange(-radius,radius+1)*modelproj.yscale
        # work out rotated coordinates
        xi1 = (xi*cos_rot)[:,numpy.newaxis] - (yj*sin_rot)[numpy.newaxis,:];
        yj1 = (xi*sin_rot)[:,numpy.newaxis] + (yj*cos_rot)[numpy.newaxis,:];
        # evaluate convolution kernel
        conv_kernel = numpy.exp(-((xi1/gmaj)**2+(yj1/gmin)**2)/2.);
        conv_kernels[modelproj.xscale,modelproj.yscale] = conv_kernel;
      # Work out data slices that we need to loop over.
      # For every 2D slice in the data image cube (assuming other axes besides x/y), we need to apply a
      # convolution to the corresponding model slice, and add it in to the data slice. The complication
      # is that any extra axis may be of length 1 in the model and of length N in the data (e.g. frequency axis),
      # in which case we need to add the same model slice to all N data slices. The loop below puts together a series
      # of index tuples representing each per-slice operation.
      # These two initial slices correspond to the x/y axes. Additional indices will be appended to these in a loop
      slices0 = [([data_x_slice,data_y_slice],[slice(None),slice(None)])];
      # work out Stokes axis
      sd0 = [data_x_slice,data_y_slice];
      sm0 = [slice(None),slice(None)];
      slices = [];
      slices = [ (sd0+[dst],sm0+[mst]) for dst,mst in enumerate(model_stp) if mst >= 0 ];
      #for dst,mst in enumerate(model_stp):
        #if mst >= 0:
          #slices = [ (sd0+[dst],sm0+[mst]) for sd0,sm0 in slices ];
      # now loop over extra axes
      for axis in range(3,len(extra_data_axes)+3):
        # list of data image indices to iterate over for this axis, 0...N-1
        indices = [[x] for x in range(data.shape[axis])];
        # list of model image indices to iterate over
        if model.shape[axis] == 1:
          model_indices = [[0]]*len(indices);
        # shape-n: must be same as data, in which case 0..N-1 is assigned to 0..N-1
        elif model.shape[axis] == data.shape[axis]:
          model_indices = indices;
        # else error
        else:
          raise RuntimeError,"axis %s of model image %s doesn't match that of output image"%\
                              (extra_data_axes[axis-3],src.shape.filename);
        # update list of slices
        slices =[ (sd0+sd,si0+si) for sd0,si0 in slices for sd,si in zip(indices,model_indices) ];
      # now loop over slices and assign
      for sd,si in slices:
        conv = convolve(model[tuple(si)],conv_kernel);
        data[tuple(sd)] += model_resampler(conv);
        ## for debugging these are handy:
        #data[0:conv.shape[0],0:conv.shape[1],0,0] = conv;
        #data[0:conv_kernel.shape[0],-conv_kernel.shape[1]:,0,0] = conv_kernel;
