# -*- coding: utf-8 -*-
#
#% $Id: BBS.py 8378 2011-08-30 15:18:30Z oms $ 
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
import struct
import time
import os.path
import re

import  numpy
import pyfits

import Kittens.utils

import Tigger.Models.Formats
from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
from Tigger.Models.Formats import dprint,dprintf
from math import cos,sin,acos,asin,atan2,sqrt,pi

DEG = math.pi/180
ARCMIN = DEG/60
ARCSEC = ARCMIN/60

"""
Loads an AIPS-format clean component list
"""

def lm_to_radec (l,m,ra0,dec0):
  """Returns ra,dec corresponding to l,m w.r.t. direction ra0,dec0""";
  # see formula at http://en.wikipedia.org/wiki/Orthographic_projection_(cartography)
  rho = sqrt(l**2+m**2);
  if rho == 0.0:
    ra = ra0
    dec = dec0
  else:
    cc = asin(rho);
    ra = ra0 + atan2( l*sin(cc),rho*cos(dec0)*cos(cc)-m*sin(dec0)*sin(cc) );
    dec = asin( cos(cc)*sin(dec0) + m*sin(cc)*cos(dec0)/rho );
  return ra,dec;

_units = dict(DEG=DEG, DEGREE=DEG, DEGREES=DEG,
              RAD=1, RADIAN=1, RADIANS=1,
              ARCMIN=ARCMIN, ARCMINS=ARCMIN,
              ARCSEC=ARCSEC, ARCSECS=ARCSEC
              )

def load (filename,center=None,**kw):
  """Imports an AIPS clean component list from FITS table
  """
  srclist = [];
  dprint(1,"importing AIPS clean component FITS table",filename);
  # read file
  ff = pyfits.open(filename);
  
  if center is None:
    hdr = ff[0].header
    ra  = hdr['CRVAL1'] * _units[hdr.get('CUNIT1','DEG').strip()]
    dec = hdr['CRVAL2'] * _units[hdr.get('CUNIT2','DEG').strip()]

    print "Using FITS image centre (%.4f, %.4f deg) as field centre" % (ra/DEG, dec/DEG)
    center = ra, dec

  # now process file line-by-line
  cclist = ff[1].data;
  hdr = ff[1].header
  ux = _units[hdr.get('TUNIT2','DEG').strip()]
  uy = _units[hdr.get('TUNIT3','DEG').strip()]
  for num,ccrec in enumerate(cclist):
    stokes_i,dx,dy = map(float,ccrec);
    # convert dx/dy to real positions
    l,m = sin(dx*ux), sin(dy*uy);
    ra,dec = lm_to_radec(l,m,*center);
    pos = ModelClasses.Position(ra,dec);
    flux = ModelClasses.Flux(stokes_i);
    # now create a source object
    src = SkyModel.Source('cc%d'%num,pos,flux);
    src.setAttribute('r',math.sqrt(l*l+m*m));
    srclist.append(src);
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  # create model
  model = ModelClasses.SkyModel(*srclist);
  # setup model center
  model.setFieldCenter(*center);
  # setup radial distances
  projection = Coordinates.Projection.SinWCS(*model.fieldCenter());
  return model;


Tigger.Models.Formats.registerFormat("AIPSCCFITS",load,"AIPS CC FITS model",(".fits",".FITS",".fts",".FTS"));
