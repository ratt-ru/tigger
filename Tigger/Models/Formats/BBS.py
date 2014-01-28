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
import struct
import time
import os.path
import re

import  numpy

import Kittens.utils

import Tigger.Models.Formats
from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
from Tigger.Models.Formats import dprint,dprintf


"""
The BBS sky model catalog file (*.cat, or *.catalog) is a human-readable text
file that contains a list of sources. The file should be in the `makesourcedb'
format. For details, please refer to
http://www.lofar.org/operations/doku.php?id=engineering:software:tools:makesourcedb#format_string
or
http://www.lofar.org/operations/doku.php?id=engineering:software:tools:bbs#creating_a_catalog_file
"""

class CatalogLine (object):
  """A CatalogLine turns one catalog file line into an object whose attributes correspond to the fields.
  """;
  def __init__ (self,parser,fields=None):
    """Creates a catalog line. If fields!=None, then this contains a list of fields already filled in""";
    self._parser = parser;
    self._fields = fields;
    if fields:
      # parse fields
      for field,number in parser.field_number.iteritems():
        fval = fields[number].strip() if number < len(fields) else '';
        if not fval:
          fval = parser.field_default.get(field,'');
        setattr(self,field,fval);
      # make directions
      self.ra_rad = parser.getAngle(self,'Ra','rah','rad','ram','ras');
      self.dec_rad = parser.getAngle(self,'Dec','dech','decd','decm','decs');
    else:
      # else make empty line
      for field in parser.field_number.iterkeys():
        setattr(self,field,'');
        
  def setPosition (self,ra,dec):
    """Sets the position ra/dec in radians: fills in fields according to the parser format""";
    self.ra_rad,self.dec_rad = ra,dec;
    self._parser.putAngle(self,ra,'Ra','rah','rad','ram','ras');
    self._parser.putAngle(self,dec,'Dec','dech','decd','decm','decs');
        
  def makeStr (self):
    """Converts into a string using the designated parser""";
    # build up dict of valid fields
    fields = {};
    for field,num in self._parser.field_number.iteritems():
      value = getattr(self,field,None);
      if value:
        fields[num] = value;
    # output
    output = "";
    nfields = max(fields.iterkeys())+1;
    for i in range(nfields):
      sep = self._parser.separators[i] if i<nfields-1 else '';
      output += "%s%s"%(fields.get(i,''),sep);
    return output;
  
class CatalogParser (object):
  def __init__ (self,format):
    # figure out fields and their separators
    fields = [];
    self.separators = [];
    while True:
      match = re.match("(\w[\w:]*(=(fixed)?'[^']*')?)(([^\w]+)(\w.*))?$",format);
      if not match:
        break;
      fields.append(match.group(1));
      # if no group 4, then we've reached the last field
      if not match.group(4):
        break;
      self.separators.append(match.group(5));
      format = match.group(6);
    # now parse the format specification
    # this is a dict of field name -> field index
    self.field_number = {};
    # this is a dict of field name -> default value
    self.field_default = dict(Category='2',I='1');
    # fill up the dicts
    for num_field,field in enumerate(fields):
      # is a default value given?
      match = re.match("(.+)='(.*)'$",field);
      if match:
        field = match.group(1);
        self.field_default[field] = match.group(2);
      self.field_number[field] = num_field;
    dprint(2,"fields are",self.field_number);
    dprint(2,"default values are",self.field_default);
    dprint(2,"separators are",self.separators);
    
  def defines (self,field):
    return field in self.field_number;
    
  def parse (self,line,linenum=0):
    """Parses one line. Returns None for empty or commented lines, else returns a CatalogLine object""";
    # strip whitespace
    line = line.strip();
    dprintf(3,"read line %d: %s\n",linenum,line);
    # skip empty or commented lines
    if not line or line[0] == '#':
      return None;
    # split using separators, quit when no more separators
    fields = [];
    for sep in self.separators:
      ff = line.split(sep,1);
      if len(ff) < 2:
        break;
      fields.append(ff[0]);
      line = ff[1];
    fields.append(line);
    dprint(4,"line %d: "%linenum,fields);
    return CatalogLine(self,fields);
    
  def newline (self):
    return CatalogLine(self);

  def getAngle (self,catline,field,fh,fd,fm,fs):
    """Helper function: given a CatalogLine, and a set of field indentifiers, turns this
    into an angle (in radians).""";
    scale = 1;
    if self.defines(field):
      fstr = getattr(catline,field,None);
      match = re.match('([+-]?\s*\d+)[h:](\d+)[m:]([\d.]*)s?$',fstr);
      if match:
        scale = 15;
      else:
        match = re.match('([+-]?\s*\d+).(\d+).(.*)$',fstr);
        if not match:
          raise ValueError,"invalid direction '%s'"%fstr;
      d,m,s = match.groups();
    else:
      if self.defines(fh):
        scale = 15;
        d = getattr(catline,fh);
      else:
        d = getattr(catline,fd,'0');
      m = getattr(catline,fm,'0');
      s = getattr(catline,fs,'0');
    # now, d,m,s are strings
    if d.startswith('-'):
      scale = -scale;
      d = d[1:];
    # convert to degrees
    return scale*(float(d) + float(m)/60 + float(s)/3600)*math.pi/180;

  def putAngle (self,catline,angle,field,fh,fd,fm,fs,prec=1e-6):
    """Helper function: inverse of getAngle.""";
    # decompose angle into sign,d,m,s
    if angle < 0:
      sign = "-";
      angle = -angle;
    else:
      sign = "+" if field == "Dec" else "";
    angle *= 12/math.pi if not self.defines(field) and self.defines(fh) else 180/math.pi;
    mins,secs = divmod(round(angle*3600/prec)*prec,60);
    mins = int(mins);
    degs,mins = divmod(mins,60);
    #generate output
    if self.defines(field):
      setattr(catline,field,"%s%d.%d.%.4f"%(sign,degs,mins,secs));
    else:
      setattr(catline,fh if self.defines(fh) else fd,"%s%d"%(sign,degs));
      setattr(catline,fm,"%d"%mins);
      setattr(catline,fs,"%.4f"%secs);


def load (filename,freq0=None,center_on_brightest=False,**kw):
  """Imports an BBS catalog file
  The 'format' argument can be either a dict (such as the DefaultDMSFormat dict above), or a string such as DefaultDMSFormatString.
  (Other possible field names are "ra_d", "ra_rad", "dec_rad", "dec_sign".)
  If None is specified, DefaultDMSFormat is used.
  The 'freq0' argument supplies a default reference frequency (if one is not contained in the file.)
  If 'center_on_brightest' is True, the mpodel field center will be set to the brightest source,
  else to the center of the first patch.
  """
  srclist = [];
  dprint(1,"importing BBS source table",filename);
  # read file
  ff = file(filename);
  # first line must be a format string: extract it
  line0 = ff.readline().strip();
  match = re.match("#\s*\((.+)\)\s*=\s*format",line0);
  if not match:
    raise ValueError,"line 1 is not a valid format specification";
  format_str = match.group(1);
  # create format parser from this string
  parser = CatalogParser(format_str);
    
  # check for mandatory fields
  for field in "Name","Type":
    if not parser.defines(field):
      raise ValueError,"Table lacks mandatory field '%s'"%field;

  maxbright = 0;
  patches = [];
  ref_freq = freq0;

  # now process file line-by-line
  linenum = 1;
  for line in ff:
    linenum += 1;
    try:
      # parse one line
      dprint(4,"read line:",line);
      catline = parser.parse(line,linenum);
      if not catline:
        continue;
      dprint(5,"line %d: "%linenum,catline.__dict__);
      # is it a patch record?
      patchname = getattr(catline,'Patch','');
      if not catline.Name:
        dprintf(2,"%s:%d: patch %s\n",filename,linenum,patchname);
        patches.append((patchname,catline.ra_rad,catline.dec_rad));
        continue;
      # form up name
      name = "%s:%s"%(patchname,catline.Name) if patchname else catline.Name;
      # check source type
      stype = catline.Type.upper();
      if stype not in ("POINT","GAUSSIAN"):
        raise ValueError,"unsupported source type %s"%stype;
      # see if we have freq0
      if freq0:
        f0 = freq0;
      elif hasattr(catline,'ReferenceFrequency'):
        f0 = float(catline.ReferenceFrequency or '0');
      else:
        f0 = None;
      # set model refrence frequency
      if f0 is not None and ref_freq is None:
        ref_freq = f0;
      # see if we have Q/U/V
      i,q,u,v = [ float(getattr(catline,stokes,'0') or '0') for stokes in "IQUV" ];
      # see if we have RM as well. Create flux object (unpolarized, polarized, polarized w/RM)
      if f0 is not None and hasattr(catline,'RotationMeasure'):
        flux = ModelClasses.PolarizationWithRM(i,q,u,v,float(catline.RotationMeasure or '0'),f0);
      else:
        flux = ModelClasses.Polarization(i,q,u,v);
      # see if we have a spectral index
      if f0 is not None and hasattr(catline,'SpectralIndex:0'):
        spectrum = ModelClasses.SpectralIndex(float(getattr(catline,'SpectralIndex:0') or '0'),f0);
      else:
        spectrum = None;
      # see if we have extent parameters
      if stype == "GAUSSIAN":
        ex = float(getattr(catline,"MajorAxis","0") or "0");
        ey = float(getattr(catline,"MinorAxis","0") or "0");
        pa = float(getattr(catline,"Orientation","0") or "0");
        shape = ModelClasses.Gaussian(ex,ey,pa);
      else:
        shape = None;
      # create tags
      tags = {};
      for field in "Patch","Category":
        if hasattr(catline,field):
          tags['BBS_%s'%field] = getattr(catline,field);
      # OK, now form up the source object
      # position
      pos = ModelClasses.Position(catline.ra_rad,catline.dec_rad);
      # now create a source object
      src = SkyModel.Source(name,pos,flux,shape=shape,spectrum=spectrum,**tags);
      srclist.append(src);
      # check if it's the brightest
      brightness = src.brightness();
      if brightness > maxbright:
        maxbright = brightness;
        brightest_name = src.name;
        radec0 = catline.ra_rad,catline.dec_rad;
    except:
      dprintf(0,"%s:%d: %s, skipping\n",filename,linenum,str(sys.exc_info()[1]));
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  # create model
  model = ModelClasses.SkyModel(*srclist);
  if ref_freq is not None:
    model.setRefFreq(ref_freq);
  # setup model center
  if center_on_brightest and radec0:
    dprintf(2,"setting model centre to brightest source %s (%g Jy) at %f,%f\n",brightest_name,maxbright,*radec0);
    model.setFieldCenter(*radec0);
  elif patches:
    name,ra,dec = patches[0];
    dprintf(2,"setting model centre to first patch %s at %f,%f\n",name,ra,dec);
    model.setFieldCenter(ra,dec);
  # map patches to model tags
  model.setAttribute("BBS_Patches",patches);
  model.setAttribute("BBS_Format",format_str);
  # setup radial distances
  projection = Coordinates.Projection.SinWCS(*model.fieldCenter());
  for src in model.sources:
    l,m = projection.lm(src.pos.ra,src.pos.dec);
    src.setAttribute('r',math.sqrt(l*l+m*m));
  return model;

def save (model,filename,sources=None,format=None,**kw):
  """Exports model to a BBS catalog file""";
  if sources is None:
    sources = model.sources;
  dprintf(2,"writing %d model sources to BBS file %s\n",len(sources),filename);
  # create catalog parser based on either specified format, or the model format, or the default format
  format = format or getattr(model,'BBS_Format',
        "Name, Type, Patch, Ra, Dec, I, Q, U, V, ReferenceFrequency, SpectralIndexDegree='0', SpectralIndex:0='0.0', MajorAxis, MinorAxis, Orientation");
  dprint(2,"format string is",format);
  parser = CatalogParser(format);
  # check for mandatory fields
  for field in "Name","Type":
    if not parser.defines(field):
      raise ValueError,"Output format lacks mandatory field '%s'"%field;
  # open file
  ff = open(filename,mode="wt");
  ff.write("# (%s) = format\n# The above line defines the field order and is required.\n\n"%format);
  # write patches
  for name,ra,dec in getattr(model,"BBS_Patches",[]):
    catline = parser.newline();
    catline.Patch = name;
    catline.setPosition(ra,dec);
    ff.write(catline.makeStr()+"\n");
  ff.write("\n");
  # write sources
  nsrc = 0;
  for src in sources:
    catline = parser.newline();
    # type
    if src.shape is None:
      catline.Type = "POINT";
    elif isinstance(src.shape,ModelClasses.Gaussian):
      catline.Type = "GAUSSIAN";
    else:
      dprint(3,"skipping source '%s': non-supported type '%s'"%(src.name,src.shape.typecode));
      continue;
    # name and patch
    name = src.name;
    patch = getattr(src,'BBS_Patch','');
    if patch and name.startswith(patch+':'):
      name = name[(len(patch)+1):]
    catline.Name = name;
    setattr(catline,'Patch',patch);
    # position
    catline.setPosition(src.pos.ra,src.pos.dec);
    # fluxes
    for stokes in "IQUV":
      setattr(catline,stokes,str(getattr(src.flux,stokes,0.)));
    # reference freq
    freq0 = (src.spectrum and getattr(src.spectrum,'freq0',None)) or getattr(src.flux,'freq0',None);
    if freq0 is not None:
      setattr(catline,'ReferenceFrequency',str(freq0));
    # RM, spi
    if isinstance(src.spectrum,ModelClasses.SpectralIndex):
      setattr(catline,'SpectralIndexDegree','0');
      setattr(catline,'SpectralIndex:0',str(src.spectrum.spi));
    if isinstance(src.flux,ModelClasses.PolarizationWithRM):
      setattr(catline,'RotationMeasure',str(src.flux.rm));
    # shape
    if isinstance(src.shape,ModelClasses.Gaussian):
      setattr(catline,'MajorAxis',src.shape.ex);
      setattr(catline,'MinorAxis',src.shape.ey);
      setattr(catline,'Orientation',src.shape.pa);
    # write line
    ff.write(catline.makeStr()+"\n");
    nsrc += 1;
    
  ff.close();
  dprintf(1,"wrote %d sources to file %s\n",nsrc,filename);


Tigger.Models.Formats.registerFormat("BBS",load,"BBS source catalog",(".cat",".catalog"),export_func=save);
