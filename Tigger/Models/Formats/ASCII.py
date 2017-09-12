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

import sys,traceback,math,numpy,re

import Kittens.utils

from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
import Tigger.Models.Formats
from Tigger.Models.Formats import dprint,dprintf


DefaultDMSFormat = dict(name=0,
    ra_h=1,ra_m=2,ra_s=3,dec_d=4,dec_m=5,dec_s=6,
    i=7,q=8,u=9,v=10,spi=11,rm=12,emaj_s=13,emin_s=14,pa_d=15,
    freq0=16,tags=slice(17,None));

DefaultDMSFormatString = "name ra_h ra_m ra_s dec_d dec_m dec_s i q u v spi rm emaj_s emin_s pa_d freq0 tags...";

FormatHelp = """
ASCII files are treated as columns of whitespace-separated values. The order
of the columns is determined by a format string, which can be specified in
the first line of the file (prefixed by "#format:"), or supplied by the
user.  Note that in subsequent lines the "#" character is treated as a
comment delimiter, everything following a "#" is ignored.

The format string contains a simple list of field names, such as "name ra_d
dec_d i".  Fields with unrecognized names are simply ignored -- a good way
to skip over unwanted columns is to use a name like 'dummy' or '-'.

The following field names are recognized. Note that only a subset of these
needs to be present (as a minimum, coordinates and I flux needs to be
supplied, but the rest is optional):

name:             source name
ra_{rad,d,h,m,s}: RA or RA component,
                  (in radians, degrees, hours, minutes or seconds)
ra_err_{rad,d,h,m,s}: error on RA (in appropriate units)
dec_{rad,d,m,s}:  declination or declination component
dec_sign:         declination sign (+ or -)
dec_err_{rad,d,m,s}: error on dec (in appropriate units)
i,q,u,v:          IQUV fluxes
{i,q,u,v}_err:    errors on fluxes
pol_frac:         linear polarization fraction
                  (will interpret both "0.1" and "10%" correctly)
pol_pa_{rad,d}:   linear polarization angle
rm:               rotation measure (freq0 must be supplied as well)
rm_err:           error on rotation measures
spi:              spectral index (freq0 must be supplied as well)
spi2,3,4...:      spectral curvature
spi_err,spi2_err,...: error on spectral index and curvature
freq0:            reference frequency, for rm and/or spi
emaj_{rad,d,m,s}: source extent, major axis (for Gaussian sources)
emin_{rad,d,m,s}: source extent, minor axis (for Gaussian sources)
{emin,emaj}_err_{rad,d,m,s}:  error on source extent
pa_{rad,d}:       position angle (for Gaussian sources)
pa_err_{ra,d}:    error on position angle
tags:             comma-separated source tags
tags...:          absorb all remaining fields as source tags
:TYPE:ATTR        custom attribute. Contents of field will be converted to Python TYPE
                  (bool, int, float, complex, str) and associated with custom source atribute "ATTR"
""";

DEG = math.pi/180;

# dict of angulr units with their scale in radians
ANGULAR_UNITS = dict(rad=1,d=DEG,m=DEG/60,s=DEG/3600,h=DEG*15)
# subsets of angular units for leading RA or Dec column
ANGULAR_UNITS_RA = dict(rad=1,d=DEG,h=DEG*15)
ANGULAR_UNITS_DEC = dict(rad=1,d=DEG)

def load (filename,format=None,freq0=None,center_on_brightest=False,min_extent=0,verbose=0,**kw):
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

  # Get column number associated with field from format dict, as well as the error
  # column number. Returns tuple of indices, with None index indicating no such column
  def get_field (name):
    return format.get(name,None),format.get(name+"_err",None);
  # Get column number associated with field from format dict, as well as the error
  # column number. Field is an angle thus will be suffixed with _{rad,d,h,m,s}.
  # Returns tuple of
  #     column,scale,err_column,err_scale
  # with None index indicating no such column. Scale is scaling factor to convert
  # quantity in column to radians
  def get_ang_field (name,units=ANGULAR_UNITS):
    column = err_column = colunit = errunit = None
    units = units or ANGULAR_UNITS;
    for unit,scale in units.iteritems():
      if column is None:
        column = format.get("%s_%s"%(name,unit));
        if column is not None:
          colunit = scale;
      if err_column is None:
        err_column = format.get("%s_err_%s"%(name,unit))
        if err_column is not None:
          errunit = scale;
    return column,colunit,err_column,errunit;

  # helper function: returns element #num from the fields list, multiplied by scale, or None if no such field
  def getval (num,scale=1):
    return None if ( num is None or len(fields) <= num ) else float(fields[num])*scale;

  # now process file line-by-line
  linenum = 0;
  format_str = ''
  for line in file(filename):
    # for the first line, figure out the file format
    if not linenum:
      if not format and line.startswith("#format:"):
        format = line[len("#format:"):].strip();
        dprint(1,"file contains format header:",format);
      # set default format
      if format is None:
        format = DefaultDMSFormatString;
      # is the format a string rather than a dict? Turn it into a dict then
      if isinstance(format,str):
        format_str = format;
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
        # nf = max(format.itervalues())+1;
        # fields = ['---']*nf;
        # for field,number in format.iteritems():
        #   fields[number] = field;
        # format_str = " ".join(fields);
      # get list of custom attributes from format
      custom_attrs = [];
      for name,col in format.iteritems():
        if name.startswith(":"):
          m = re.match("^:(bool|int|float|complex|str):([\w]+)$",name);
          if not m:
            raise TypeError,"invalid field specification '%s' in format string"%name;
          custom_attrs.append((eval(m.group(1)),m.group(2),col));
      # get minimum necessary fields from format
      name_field = format.get('name',None);
      # flux
      i_field,i_err_field = get_field("i");
      if i_field is None:
        raise ValueError,"ASCII format specification lacks mandatory flux field ('i')";
      # main RA field
      ra_field,ra_scale,ra_err_field,ra_err_scale = get_ang_field('ra',ANGULAR_UNITS_RA);
      if ra_field is None:
        raise ValueError,"ASCII format specification lacks mandatory Right Ascension field ('ra_h', 'ra_d' or 'ra_rad')";
      # main Dec field
      dec_field,dec_scale,dec_err_field,dec_err_scale = get_ang_field('dec',ANGULAR_UNITS_DEC);
      if dec_field is None:
        raise ValueError,"ASCII format specification lacks mandatory Declination field ('dec_d' or 'dec_rad')";
      # polarization as QUV
      quv_fields = [ get_field(x) for x in ['q','u','v'] ];
      # linear polarization as fraction and angle
      polfrac_field = format.get('pol_frac',None);
      if polfrac_field is not None:
        polpa_field,polpa_scale = format.get('pol_pa_d',None),(math.pi/180);
        if not polpa_field is not None:
          polpa_field,polpa_scale = format.get('pol_pa_rad',None),1;
      # fields for extent parameters
      extent_fields = [ get_ang_field(x,ANGULAR_UNITS) for x in 'emaj','emin','pa' ];
      # all three must be present, else ignore
      if any( [ x[0] is None for x in extent_fields ] ):
        extent_fields = None;
      # fields for reference freq and RM and SpI
      freq0_field = format.get('freq0',None);
      rm_field,rm_err_field = get_field('rm');
      spi_fields = [ get_field('spi') ] + [ get_field('spi%d'%i) for i in range(2,10) ];
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
      i = getval(i_field);
      i_err = getval(i_err_field);
      # get position: RA
      ra = getval(ra_field);
      ra_err = getval(ra_err_field,ra_scale);
      if 'ra_m' in format:
        ra += float(fields[format['ra_m']])/60.;
      if 'ra_s' in format:
        ra += float(fields[format['ra_s']])/3600.;
      ra *= ra_scale;
      # position: Dec. Separate treatment of sign
      dec = abs(getval(dec_field));
      dec_err = getval(dec_err_field,dec_scale);
      if 'dec_m' in format:
        dec += float(fields[format['dec_m']])/60.;
      if 'dec_s' in format:
        dec += float(fields[format['dec_s']])/3600.;
      if fields[format.get('dec_sign',dec_field)][0] == '-':
        dec = -dec;
      dec *= dec_scale;
      # for up position object
      pos = ModelClasses.Position(ra,dec,ra_err=ra_err,dec_err=dec_err);
      # see if we have freq0

      # Use explicitly provided reference frequency for this source if available
      f0 = None
      if freq0_field is not None:
        try:
          f0 = float(fields[freq0_field])
          # If no default reference frequency for the model was supplied,
          # initialise from first source with a reference frequency
          if freq0 is None:
            freq0 = f0
            dprint(0,"Set default freq0 to %s "
                     "from source on line %s." % (f0, linenum));

        except IndexError:
          f0 = None

      # Otherwise use default reference frequency (derived from args
      # or first reference frequency found in source)
      if f0 is None and freq0 is not None:
        f0 = freq0

      # see if we have Q/U/V
      (q,q_err),(u,u_err),(v,v_err) = [ (getval(x),getval(x_err)) for x,x_err in quv_fields ];
      if polfrac_field is not None:
        pf = fields[polfrac_field];
        pf = float(pf[:-1])/100 if pf.endswith("%") else float(pf);
        ppa = float(fields[polpa_field])*polpa_scale if polpa_field is not None else 0;
        q = i*pf*math.cos(2*ppa);
        u = i*pf*math.sin(2*ppa);
        v = 0;
      # see if we have RM as well. Create flux object (unpolarized, polarized, polarized w/RM)
      rm,rm_err = getval(rm_field),getval(rm_err_field);
      if q is None:
        flux = ModelClasses.Polarization(i,0,0,0,I_err=i_err);
      elif f0 is None or rm is None:
        flux = ModelClasses.Polarization(i,q,u,v,I_err=i_err,Q_err=q_err,U_err=u_err,V_err=v_err);
      else:
        flux = ModelClasses.PolarizationWithRM(i,q,u,v,rm,f0,I_err=i_err,Q_err=q_err,U_err=u_err,V_err=v_err,rm_err=rm_err);
      # see if we have a spectral index
      if f0 is None:
        spectrum = None;
      else:
        spi = [ getval(x) for x,xerr in spi_fields ];
        spi_err = [ getval(xerr) for x,xerr in spi_fields ];
        dprint(4,name,"spi is",spi,"err is",spi_err)
        # if any higher-order spectral terms are specified, include them here but trim off all trailing zeroes
        while spi and not spi[-1]:
          del spi[-1];
          del spi_err[-1]
        if not spi:
          spectrum = None;
        elif len(spi) == 1:
          spectrum = ModelClasses.SpectralIndex(spi[0],f0);
          if spi_err[0] is not None:
            spectrum.spi_err = spi_err[0];
        else:
          spectrum = ModelClasses.SpectralIndex(spi,f0);
          if any([ x is not None for x in spi_err ]):
            spectrum.spi_err = spi_err;
      # see if we have extent parameters
      ex = ey = pa = 0;
      if extent_fields:
        ex,ey,pa = [ ( getval(x[0],x[1]) or 0 ) for x in extent_fields ];
        extent_errors = [ getval(x[2],x[3]) for x in extent_fields ];
      # form up shape object
      if (ex or ey) and max(ex,ey) >= min_extent:
        shape = ModelClasses.Gaussian(ex,ey,pa);
        for ifield,field in enumerate(['ex','ey','pa']):
          if extent_errors[ifield] is not None:
            shape.setAttribute(field+"_err",extent_errors[ifield]);
      else:
        shape = None;
      # get tags
      tagdict = {};
      if tags_slice:
        try:
          tags = fields[tags_slice];
        except IndexError:
          pass;
        for tagstr1 in tags:
          for tagstr in tagstr1.split(","):
            if tagstr[0] == "+":
              tagname,value = tagstr[1:],True;
            elif tagstr[0] == "-":
              tagname,value = tagstr[1:],False;
            elif "=" in tagstr:
              tagname,value = tagstr.split("=",1);
              if value[0] in "'\"" and value[-1] in "'\"":
                value = value[1:-1];
              else:
                try:
                  value = float(value);
                except:
                  continue;
            else:
              tagname,value = tagstr,True;
            tagdict[tagname] = value;
      # OK, now form up the source object
      # now create a source object
      dprint(3,name,ra,dec,i,q,u,v);
      src = SkyModel.Source(name,pos,flux,shape=shape,spectrum=spectrum,**tagdict);
      # get custom attributes
      for type_,attr,column in custom_attrs:
        if column is not None and len(fields) > column:
          src.setAttribute(attr,type_(fields[column]));
      # add to source list
      srclist.append(src);
      # check if it's the brightest
      brightness = src.brightness();
      if brightness > maxbright:
        maxbright = brightness;
        brightest_name = src.name;
        radec0 = ra,dec;
    except:
      if verbose:
        traceback.print_exc();
      dprintf(0,"%s:%d: %s, skipping\n",filename,linenum,str(sys.exc_info()[1]));
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  # create model
  model = ModelClasses.SkyModel(*srclist);
  if freq0 is not None:
    model.setRefFreq(freq0);
  # set model format
  model.setAttribute("ASCII_Format",format_str);
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


def save (model,filename,sources=None,format=None,**kw):
  """
  Exports model to a text file
  """;
  if sources is None:
    sources = model.sources;
  dprintf(2,"writing %d model sources to text file %s\n",len(sources),filename);
  # create catalog parser based on either specified format, or the model format, or the default format
  format_str = format or getattr(model,'ASCII_Format',DefaultDMSFormatString);
  dprint(2,"format string is",format_str);
  # convert this into format dict
  fields = [ [field,i] for i,field in enumerate(format_str.split()) ];
  if not fields:
    raise ValueError,"illegal format string '%s'"%format;
  # last fieldname can end with ... ("tags..."), so strip it
  if fields[-1][0].endswith('...'):
    fields[-1][0] = fields[-1][0][:-3];
  # make format dict
  format = dict(fields);
  nfields = len(fields);
  # get minimum necessary fields from format
  name_field = format.get('name',None);
  # main RA field
  ra_rad_field,ra_d_field,ra_h_field,ra_m_field,ra_s_field = \
    [ format.get(x,None) for x in 'ra_rad','ra_d','ra_h','ra_m','ra_s' ];
  dec_rad_field,dec_d_field,dec_m_field,dec_s_field = \
    [ format.get(x,None) for x in 'dec_rad','dec_d','dec_m','dec_s' ];
  if ra_h_field is not None:
    ra_scale = 15;
    ra_d_field = ra_h_field;
  else:
    ra_scale = 1;
  # fields for reference freq and RM and SpI
  freq0_field = format.get('freq0',None);
  rm_field = format.get('rm',None);
  spi_field = format.get('spi',None);
  tags_field = format.get('tags',None);
  # open file
  ff = open(filename,mode="wt");
  ff.write("#format: %s\n"%format_str);
  # write sources
  nsrc = 0;
  for src in sources:
    # only write points and gaussians
    if src.shape is not None and not isinstance(src.shape,ModelClasses.Gaussian):
      dprint(3,"skipping source '%s': non-supported type '%s'"%(src.name,src.shape.typecode));
      continue;
    # prepare field values
    fval = ['0']*nfields;
    # name
    if name_field is not None:
      fval[name_field] = src.name;
    # position: RA
    ra,dec = src.pos.ra,src.pos.dec;
    # RA in radians
    if ra_rad_field is not None:
      fval[ra_rad_field] = str(ra);
    ra /= ra_scale;
    # RA in h/m/s or d/m/s
    if ra_m_field is not None:
      ra,ram,ras = src.pos.ra_hms_static(ra,scale=180,prec=1e-4);
      fval[ra_m_field] = str(ram);
      if ra_s_field is not None:
        fval[ra_s_field] = str(ras);
      if ra_d_field is not None:
        fval[ra_d_field] = str(ra);
    elif ra_d_field is not None:
        fval[ra_d_field] = str(ra*180/math.pi);
    # position: Dec
    if dec_rad_field is not None:
      fval[dec_rad_field] = str(dec);
    if dec_m_field is not None:
      dsign,decd,decm,decs = src.pos.dec_sdms();
      fval[dec_m_field] = str(decm);
      if dec_s_field is not None:
        fval[dec_s_field] = str(decs);
      if dec_d_field is not None:
        fval[dec_d_field] = dsign+str(decd);
    elif dec_d_field is not None:
        fval[dec_d_field] = str(dec*180/math.pi);
    # fluxes
    for stokes in "IQUV":
      field = format.get(stokes.lower());
      if field is not None:
        fval[field] = str(getattr(src.flux,stokes,0));
    # fractional polarization
    if 'pol_frac' in format:
      i,q,u = [ getattr(src.flux,stokes,0) for stokes in "IQU" ];
      fval[format['pol_frac']] = str(math.sqrt(q*q+u*u)/i);
      pa = math.atan2(u,q)/2;
      for field,scale in ('pol_pa_rad',1.),('pol_pa_d',DEG):
        ifield = format.get(field);
        if ifield is not None:
          fval[ifield] = str(pa/scale);
    # shape
    if src.shape:
      for parm,sparm in ("emaj","ex"),("emin","ey"),("pa","pa"):
        for field,scale in (parm,1.),(parm+'_rad',DEG),(parm+'_d',DEG),(parm+'_m',DEG/60),(parm+'_s',DEG/3600):
          ifield = format.get(field.lower());
          if ifield is not None:
            fval[ifield] = str(getattr(src.shape,sparm,0)/scale);
    # RM, spi, freq0
    if freq0_field is not None:
      freq0 = (src.spectrum and getattr(src.spectrum,'freq0',None)) or getattr(src.flux,'freq0',0);
      fval[freq0_field] = str(freq0);
    if rm_field is not None:
      fval[rm_field] = str(getattr(src.flux,'rm',0));
    if spi_field is not None and hasattr(src,'spectrum'):
      fval[spi_field] = str(getattr(src.spectrum,'spi',0));
    # tags
    if tags_field is not None:
      outtags = [];
      for tag,value in src.getTags():
        if isinstance(value,str):
          outtags.append("%s=\"%s\""%(tag,value));
        elif isinstance(value,bool):
          if value:
            outtags.append("+"+tag);
          else:
            outtags.append("-"+tag);
        elif isinstance(value,(int,float)):
          outtags.append("%s=%f"%(tag,value));
      fval[tags_field] = ",".join(outtags);
    # write the line
    ff.write(" ".join(fval)+"\n");
    nsrc += 1;

  ff.close();
  dprintf(1,"wrote %d sources to file %s\n",nsrc,filename);


Tigger.Models.Formats.registerFormat("ASCII",load,"ASCII table",(".txt",".lsm"),export_func=save);
