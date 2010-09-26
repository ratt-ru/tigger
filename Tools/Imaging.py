# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

import pyfits
import gaussfitter2
import math
import numpy

from Tigger.Coordinates import Projection
from scipy.ndimage.filters import convolve

# init debug printing
import Kittens.utils
_verbosity = Kittens.utils.verbosity(name="imaging");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

# conversion factors from radians
DEG = 180/math.pi;
ARCMIN = DEG*60;
ARCSEC = ARCMIN*60;
FWHM = 2.3548;

def fitPsf (filename,cropsize=64):
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
  # crop the central region
  nx,ny = psf.shape;
  size = 64;
  psf = psf[(nx-size)/2:(nx+size)/2,(ny-size)/2:(ny+size)/2];

  # estimate gaussian parameters, then fit
  parms = gaussfitter2.moments(psf,circle=0,rotate=1,vheight=0);
  dprint(2,"Estimates parameters are",parms);
  parms = gaussfitter2.gaussfit(psf,None,parms,autoderiv=1,return_all=0,circle=0,rotate=1,vheight=0);
  dprint(2,"Fitted parameters are",parms);
  # now swap x and y around, since our axes are in reverse order
  ampl,y0,x0,sy,sx,rot = parms;

  # get pixel sizes in radians (by constructing a projection object)
  proj = Projection.FITSWCS(hdr);
  xscale,yscale = proj.xscale,proj.yscale;

  sx_rad = abs(sx * proj.xscale);
  sy_rad = abs(sy * proj.yscale);
  if sx_rad < sy_rad:
    sx_rad,sy_rad = sy_rad,sx_rad;
    rot -= 90;
  while rot > 180:
    rot -= 360;
  while rot < -180:
    rot += 360;

  dprintf(1,"Fitted gaussian PSF FWHM of %f x %f pixels (%f x %f arcsec), p.a. %f deg\n",sx*FWHM,sy*FWHM,sx_rad*FWHM*ARCSEC,sy_rad*FWHM*ARCSEC,rot);

  return sx_rad,sy_rad,rot/DEG;

def restoreSources (fits_hdu,sources,gmaj,gmin=None,grot=0,freq=None,primary_beam=None):
  """Restores sources (into the given FITSHDU) using a Gaussian PSF given by gmaj/gmin/grot.
  If gmaj=0, uses delta functions instead.
  If freq is specified, converts flux to the specified frequency.
  If primary_beam is specified, uses it to apply a PB gain to each source. This must be a function of two arguments:
  r and freq.
  """;
  hdr = fits_hdu.header;
  data = fits_hdu.data;
  # create projection object, using pixel coordinates
  proj = Projection.FITSWCSpix(hdr);
  # Note that "numpy" axis ordering is the reverse of "FITS" axis ordering.
  # The FITS header will have X as the first axis and Y as the second, the corresponding data
  # array has the x axis last and y second from last
  naxis = len(data.shape);
  nx = data.shape[-1];
  ny = data.shape[-2];
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
  #  4. Just say data[...,j1:j2,i1:2] += g
  # This automatically expands all array dimensions as needed.

  # This is a helper function, returns an naxis-sized tuple, with slice(None) in the N-from-last
  # position , and elem_index elsewhere.
  def make_axis_indexer (n,elem_index=numpy.newaxis):
    indexer = [elem_index]*naxis;
    indexer[naxis-1-n] = slice(None);
    return tuple(indexer);
  x_indexer = make_axis_indexer(0);
  y_indexer = make_axis_indexer(1);
  # figure out position of Stokes axis, and make indexing objects
  for n in range(2,naxis):
    if hdr.get('CTYPE%d'%(n+1)).strip().upper() == 'STOKES':
      nstokes = data.shape[naxis-1-n];
      if nstokes > 4:
        raise ValueError,"Too many stokes planes in image (%d)"%nstokes;
      stokes = "IQUV"[0:nstokes];
      stokes_vec = numpy.zeros((nstokes,));
      dprintf(2,"Stokes components are %s at image axis %d\n",stokes,n);
      stokes_indexer = make_axis_indexer(n);
      break;
  # else no stokes axis -- use I only, and an indexer object that'll make the stokes vector scalar
  else:
    stokes = "I";
    stokes_vec = numpy.zeros((1,));
    stokes_indexer = (0,);
  dprint(2,"Stokes are",stokes);
  dprint(2,"Stokes indexing vector is",stokes_indexer);
  # get pixel sizes, in radians
  # gmaj != 0: use gaussian. Estimate PSF box size. We want a +/-5 sigma box
  if gmaj > 0:
    if gmin == 0:
      gmin = gmaj;
    box_radius = 5*(max(gmaj,gmin))/min(abs(proj.xscale),abs(proj.yscale));
    dprintf(2,"Will use a box of radius %f pixels for restoration\n",box_radius);
    cos_rot = math.cos(grot);
    sin_rot = math.sin(grot);
  conv_kernel = None;
  # loop over sources in model
  for src in sources:
    # get normalized intensity, if spectral info is available
    if freq is not None and hasattr(src,'spectrum'):
      ni = src.spectrum.normalized_intensity(freq);
      dprintf(3,"Source %s: normalized spectral intensity is %f\n",src.name,ni);
    else:
      ni = 1;
    #  multiply that by PB gain, if given
    if primary_beam:
      r = getattr(src,'r',None);
      if r is not None:
        pb = primary_beam(r,freq);
        ni *= pb;
        dprintf(3,"Source %s: r=%g pb=%f, normalized intensity is %f\n",src.name,r,pb,ni);
    # process point sources
    if src.typecode == 'pnt':
      # pixel coordinates of source
      xsrc,ysrc = proj.lm(src.pos.ra,src.pos.dec);
      # form up stokes vector
      for i,st in enumerate(stokes):
         stokes_vec[i] = getattr(src.flux,st,-1)*ni;
      dprintf(3,"Source %s, %s Jy, at pixel %f,%f\n",src.name,stokes_vec,xsrc,ysrc);
      # gmaj != 0: use gaussian.
      if gmaj > 0:
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
        xi1 = (xi*cos_rot)[x_indexer] - (yj*sin_rot)[y_indexer];
        yj1 = (xi*sin_rot)[x_indexer] + (yj*cos_rot)[y_indexer];
        # evaluate gaussian at these, scale up by stokes vector
        gg = stokes_vec[stokes_indexer]*numpy.exp(-((xi1/gmaj)**2+(yj1/gmin)**2)/2.);
        # add into data
        data[...,j1:j2,i1:i2] += gg;
      # else gmaj=0: use delta functions
      else:
        xsrc = int(round(xsrc));
        ysrc = int(round(ysrc));
        # skip sources outside image
        if xsrc < 0 or xsrc >= nx or ysrc < 0 or ysrc >= ny:
          continue;
        xdum = numpy.array([1]);
        ydum = numpy.array([1]);
        data[...,ysrc:ysrc+1,xsrc:xsrc+1] += stokes_vec[stokes_indexer]*xdum[x_indexer]*ydum[y_indexer];
    # procvess model images -- convolve with PSF and add to data
    elif src.typecode == "FITS":
      imgff = pyfits.open(src.shape.filename);
      img = imgff[0].data
      # projection had better match
      imgproj = Projection.FITSWCSpix(imgff[0].header);
      if img.shape[-2:] != data.shape[-2:] or img.ndim > data.ndim or imgproj != proj:
        raise RuntimeError,"coordinates or shape of model image %s don't match those of output image"%src.shape.filename;
      # evaluate convolution kernel first time we need it
      if conv_kernel is None:
        radius = int(round(box_radius));
        # convert pixel coordinates into world coordinates relative to 0
        xi = numpy.arange(-radius,radius+1)*proj.xscale
        yj = numpy.arange(-radius,radius+1)*proj.yscale
        # work out rotated coordinates
        # (rememeber that X is last axis, Y is second-last)
        xi1 = (xi*cos_rot)[numpy.newaxis,:] - (yj*sin_rot)[:,numpy.newaxis];
        yj1 = (xi*sin_rot)[numpy.newaxis,:] + (yj*cos_rot)[:,numpy.newaxis];
        # evaluate convolution kernel
        conv_kernel = numpy.exp(-((xi1/gmaj)**2+(yj1/gmin)**2)/2.);
      # work out data slices that we need to loop over
      slices = [([Ellipsis],[Ellipsis])];
      for axis in range(2,data.ndim):
        # list of data indices to iterate over for this axis
        indices = [[x] for x in range(data.shape[-1-axis])];
        # list of image indices to iterate over
        if axis < img.ndim:
          # shape-1: use 0 throughout
          if img.shape[-1-axis] == 1:
            img_indices = [[0]]*len(indices);
          # shape-n: must be same as data
          elif img.shape[-1-axis] == data.shape[-1-axis]:
            img_indices = indices;
          # else error
          else:
            raise RuntimeError,"axis %d of model image %s doesn't match those of output image"%(axis,src.shape.filename);
        # no such axis in uimage -- no index
        else:
          img_indices = [[]]*range(indices);
        # update list of slices
        slices =[ (sd+sd0,si+si0) for sd0,si0 in slices for sd,si in zip(indices,img_indices) ];
      # now loop over slices and assign
      for sd,si in slices:
        data[tuple(sd)] += convolve(img[tuple(si)],conv_kernel);
