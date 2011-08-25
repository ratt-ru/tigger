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
import  numpy

import Kittens.utils

from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
import Tigger.Models.Formats
from Tigger.Models.Formats import dprint,dprintf


DefaultDMSFormat = dict(name=0,
    ra_h=1,ra_m=2,ra_s=3,dec_d=4,dec_m=5,dec_s=6,
    i=7,q=8,u=9,v=10,spi=11,rm=12,ex=13,ey=14,pa=15,
    freq0=16,tags=slice(17,None));

DefaultDMSFormatString = "name ra_h ra_m ra_s dec_d dec_m dec_s i q u v spi rm ex ey pa freq0 tags...";

def load (filename,format=None,freq0=None,center_on_brightest=True,min_extent=0):
  """Imports an ASCII table
  The 'format' argument can be either a dict (such as the DefaultDMSFormat dict above), or a string such as DefaultDMSFormatString.
  (Other possible field names are "ra_d", "ra_rad", "dec_rad", "dec_sign".)
  If None is specified, DefaultDMSFormat is used.
  The 'freq0' argument supplies a default reference frequency (if one is not contained in the file.)
  If 'center_on_brightest' is True, the mpodel field center will be set to the brightest source.
  'min_extent' is minimal source extent (in radians), above which a source will be treated as a Gaussian rather than a point component.
  """
  srclist = [];
  dprint(1,"importing ASCII DMS file",filename);
  # brightest source and its coordinates
  maxbright = 0;
  brightest_name = radec0 = None;

  # now process file line-by-line
  linenum = 0;
  for line in file(filename):
    # for the first line, firgure out the file format
    if not linenum:
      if not format and line.startswith("#format:"):
        format = line[len("#format:"):];
        dprint(1,"file contains format header:",format);
      # set default format
      if format is None:
        format = DefaultDMSFormatString;
      # is the format a string rather than a dict? Turn it into a dict then
      if isinstance(format,str):
        # make list of fieldname,fieldnumber tuples
        fields = [ (field,i) for i,field in enumerate(format.split()) ];
        if not fields:
          raise ValueError,"illegal format string in file: '%s'"%format;
        # last fieldname can end with ... to indicate that it absorbs the rest of the line
        if fields[-1][0].endswith('...'):
          fields[-1] = (fields[-1][0][:-3],slice(fields[-1][1],None));
        # make format dict
        format = dict(fields);
      elif not isinstance(format,dict):
        raise TypeError,"invalid 'format' argument of type %s"%(type(format))
      # get minimum necessary fields from format
      name_field = format.get('name',None);
      # flux
      try:
        i_field = format['i'];
      except KeyError:
        raise ValueError,"ASCII format specification lacks mandatory flux field ('i')";
      # main RA field
      if 'ra_h' in format:
        ra_field,ra_scale = format['ra_h'],(math.pi/12);
      elif 'ra_d' in format:
        ra_field,ra_scale = format['ra_d'],(math.pi/180);
      elif 'ra_rad' in format:
        ra_field,ra_scale = format['ra_rad'],1.;
      else:
        raise ValueError,"ASCII format specification lacks mandatory Right Ascension field ('ra_h', 'ra_d' or 'ra_rad')";
      # main Dec field
      if 'dec_d' in format:
        dec_field,dec_scale = format['dec_d'],(math.pi/180);
      elif 'dec_rad' in format:
        dec_field,dec_scale = format['dec_rad'],1.;
      else:
        raise ValueError,"ASCII format specification lacks mandatory Declination field ('dec_d' or 'dec_rad')";
      try:
        quv_fields = [ format[x] for x in ['q','u','v'] ];
      except KeyError:
        quv_fields = None;
      # fields for extent parameters
      try:
        ext_fields = [ format[x] for x in ['ex','ey','pa'] ];
      except KeyError:
        ext_fields = None;
      # fields for reference freq and RM and SpI
      freq0_field = format.get('freq0',None);
      rm_field = format.get('rm',None);
      spi_field = format.get('spi',None);
      tags_slice = format.get('tags',None);
    # now go on to process the line
    linenum += 1;
    try:
      # strip whitespace
      line = line.strip();
      dprintf(4,"%s:%d: read line '%s'\n",filename,linenum,line);
      # skip empty or commented lines
      if not line or line[0] == '#':
        continue;
      # split (at whitespace) into fields
      fields = line.split();
      # get  name
      name = fields[name_field] if name_field is not None else str(len(srclist)+1);
      i = float(fields[i_field]);
      # get position: RA
      ra = float(fields[ra_field]);
      if 'ra_m' in format:
        ra += float(fields[format['ra_m']])/60.;
      if 'ra_s' in format:
        ra += float(fields[format['ra_s']])/3600.;
      ra *= ra_scale;
      # position: Dec. Separate treatment of sign
      dec = abs(float(fields[dec_field]));
      if 'dec_m' in format:
        dec += float(fields[format['dec_m']])/60.;
      if 'dec_s' in format:
        dec += float(fields[format['dec_s']])/3600.;
      if fields[format.get('dec_sign',dec_field)][0] == '-':
        dec = -dec;
      dec *= dec_scale;
      # see if we have freq0
      try:
        f0 = freq0 or (freq0_field and float(fields[freq0_field]));
      except IndexError:
        f0 = None;
      # set model refrence frequency
      if f0 is not None and freq0 is None:
        freq0 = f0;
      # see if we have Q/U/V
      q=u=v=None;
      if quv_fields:
        try:
          q,u,v = map(float,[fields[x] for x in quv_fields]);
        except IndexError:
          pass;
      # see if we have RM as well. Create flux object (unpolarized, polarized, polarized w/RM)
      if q is None:
        flux = ModelClasses.Polarization(i,0,0,0);
      elif f0 is None or rm_field is None or rm_field >= len(fields):
        flux = ModelClasses.Polarization(i,q,u,v);
      else:
        flux = ModelClasses.PolarizationWithRM(i,q,u,v,float(fields[rm_field]),f0);
      # see if we have a spectral index
      if f0 is None or spi_field is None or spi_field >= len(fields):
        spectrum = None;
      else:
        spectrum = ModelClasses.SpectralIndex(float(fields[spi_field]),f0);
      # see if we have extent parameters
      ex=ey=pa=0;
      if ext_fields:
        try:
          ex,ey,pa = map(float,[fields[x] for x in ext_fields]);
        except IndexError:
          pass;
      # form up shape object
      if (ex or ey) and max(ex,ey) >= min_extent:
        shape = ModelClasses.Gaussian(ex,ey,pa);
      else:
        shape = None;
      # get tags
      tags = [];
      if tags_slice:
        try:
          tags = fields[tags_slice];
        except IndexError:
          pass;
      # OK, now form up the source object
      # position
      pos = ModelClasses.Position(ra,dec);
      # now create a source object
      dprint(3,name,ra,dec,i,q,u,v);
      src = SkyModel.Source(name,pos,flux,shape=shape,spectrum=spectrum,**dict([(tag,True) for tag in tags]));
      srclist.append(src);
      # check if it's the brightest
      brightness = src.brightness();
      if brightness > maxbright:
        maxbright = brightness;
        brightest_name = src.name;
        radec0 = ra,dec;
    except:
      dprintf(0,"%s:%d: %s, skipping\n",filename,linenum,str(sys.exc_info()[1]));
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  # create model
  model = ModelClasses.SkyModel(*srclist);
  if freq0 is not None:
    model.setRefFreq(freq0);
  # setup model center
  if center_on_brightest and radec0:
    dprintf(2,"brightest source is %s (%g Jy) at %f,%f\n",brightest_name,maxbright,*radec0);
    model.setFieldCenter(*radec0);
  # setup radial distances
  projection = Coordinates.Projection.SinWCS(*model.fieldCenter());
  for src in model.sources:
    l,m = projection.lm(src.pos.ra,src.pos.dec);
    src.setAttribute('r',math.sqrt(l*l+m*m));
  return model;


Tigger.Models.Formats.registerFormat("ASCII",load,"ASCII file (hms/dms)",(".txt",".lsm"));
