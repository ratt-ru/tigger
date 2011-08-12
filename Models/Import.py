
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

import Kittens.utils
import  numpy

import ModelClasses
import SkyModel

from Tigger import Coordinates

_verbosity = Kittens.utils.verbosity(name="lsmimport");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

Formats = {};

def registerFormat (name,import_func,doc=None,extensions=None):
    Formats[name] = (import_func,doc,extensions);

DefaultDMSFormat = dict(name=0,
    ra_h=1,ra_m=2,ra_s=3,dec_d=4,dec_m=5,dec_s=6,
    i=7,q=8,u=9,v=10,spi=11,rm=12,ex=13,ey=14,pa=15,
    freq0=16,tags=slice(17,None));

DefaultDMSFormatString = "name ra_h ra_m ra_s dec_d dec_m dec_s i q u v spi rm ex ey pa freq0 tags...";

def importASCII (filename,format=None,freq0=None,center_on_brightest=True,min_extent=0):
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
  # read file
  lines = list(enumerate(file(filename)));
  if not lines:
    return ModelClasses.SkyModel([]);
  # is there a format string in the file?
  line0 = lines[0][1].strip();
  if line0.startswith("#format:"):
    format = line0[len("#format:"):];
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

  # brightest source and its coordinates
  maxbright = 0;
  brightest_name = radec0 = None;

  # now process file line-by-line
  for linenum,line in lines:
    try:
      # strip whitespace
      line = line.strip();
      dprint(4,"read line:",line);
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
      dprintf(0,"%s:%d: %s, skipping\n",filename,linenum+1,str(sys.exc_info()[1]));
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

registerFormat("text file (hms/dms)",importASCII,extensions="*.txt");

def lm_ncp_to_radec(ra0,dec0,l,m):
  """Converts coordinates in l,m (NCP) relative to ra0,dec0 into ra,dec.""";
  sind0=math.sin(dec0)
  cosd0=math.cos(dec0)
  dl=l
  dm=m
  d0=dm*dm*sind0*sind0+dl*dl-2*dm*cosd0*sind0
  sind=math.sqrt(abs(sind0*sind0-d0))
  cosd=math.sqrt(abs(cosd0*cosd0+d0))
  if sind0>0:
    sind=abs(sind)
  else:
    sind=-abs(sind)
  dec=math.atan2(sind,cosd)
  if l != 0:
    ra=math.atan2(-dl,(cosd0-dm*sind0))+ra0
  else:
    ra=math.atan2((1e-10),(cosd0-dm*sind0))+ra0
  return (ra,dec)


def importNEWSTAR (filename,import_src=True,import_cc=True,min_extent=0,**kw):
  """Imports a NEWSTAR MDL file.
  'min_extent' is minimal source extent (in radians), above which a source will be treated as a Gaussian rather than a point component.
  """
  srclist = [];
  dprint(2,"importing NEWSTAR file",filename);
  # build the LSM from a NewStar .MDL model file
  # if only_cleancomp=True, only clean components are used to build the LSM
  # if no_cleancomp=True, no clean components are used to build the LSM
  ff=open(filename,mode="rb")
  #### read header -- 512 bytes
  gfh=numpy.fromfile(ff,dtype=numpy.uint8,count=512)
  ## type
  ftype=gfh[0:4].tostring()
  ## length
  fhlen=struct.unpack('i',gfh[4:8])
  fhlen=fhlen[0]
  ### version
  fver=struct.unpack('i',gfh[5:9])
  fver=fver[0]
  ### creation date
  crdate=gfh[12:23].tostring()
  ### creation time
  crtime=gfh[23:28].tostring()
  ### revision date
  rrdate=gfh[28:39].tostring()
  ### revision time
  rrtime=gfh[39:44].tostring()
  ### revision count
  rcount=struct.unpack('i',gfh[44:48])
  rcount=rcount[0]
  #### node name
  nname=gfh[48:128].tostring()
  ### the remaining info is not needed
  dprint(1,"%s: read header type=%s, length=%d, version=%d, created=%s@%s, updated=%s@%s x %d, node name=%s"%(filename,ftype,fhlen,fver,crdate,crtime,rrdate,rrtime,rcount,nname))
  ####### Model Header -- 64 bytes
  mdh=numpy.fromfile(ff,dtype=numpy.uint8,count=64)
  ### Max. # of lines in model or disk version
  maxlin=struct.unpack('i',mdh[12:16])
  maxlin=maxlin[0]
  ### pointer to model ???
  modptr=struct.unpack('i',mdh[16:20])
  modptr=modptr[0]
  #### no of sources in model
  nsources=struct.unpack('i',mdh[20:24])
  nsources=nsources[0]
  ### model type(0: no ra,dec, 1=app, 2=epoch)
  mtype=struct.unpack('i',mdh[24:28])
  mtype=mtype[0]
  ### Epoch (e.g. 1950) if TYP=2 (float) : 4 bytes
  mepoch=struct.unpack('f',mdh[28:32])
  mepoch=mepoch[0]
  ###  Model centre RA (circles) : double
  ra0=struct.unpack('d',mdh[32:40])
  ra0=ra0[0]*math.pi*2
  ### Model centre DEC (circles)
  dec0=struct.unpack('d',mdh[40:48])
  dec0=dec0[0]*math.pi*2
  ### Model centre FRQ (MHz)
  freq0=struct.unpack('d',mdh[48:56])
  freq0=freq0[0]*1e6
  beam_const = 65*1e-9*freq0;
  ###### the remaining is not needed
  dprint(1,"%s: read model header lines=%d, pointer=%d, sources=%d, type=%d, epoch=%f RA=%f, DEC=%f (rad) Freq=%f Hz"%(filename,maxlin,modptr,nsources,mtype,mepoch,ra0,dec0,freq0));
  ## temp dict to hold unique nodenames
  unamedict={}
  ########## Models -- 56 bytes
  for ii in range(0,nsources):
    mdl=numpy.fromfile(ff,dtype=numpy.uint8,count=56)
    ### Amplitude (Stokes I)
    sI=struct.unpack('f',mdl[0:4])
    sI=sI[0]*0.005 # convert from WU to Jy (1WU=5mJy)
    ### L offset (mult by 60*60*180/pi to get arcsecs)
    ll=struct.unpack('f',mdl[4:8])
    ll=ll[0]
    ### M offset
    mm=struct.unpack('f',mdl[8:12])
    mm=mm[0]
    ### Identification
    id=struct.unpack('i',mdl[12:16])
    id=id[0]
    ### Q fraction
    sQ=struct.unpack('f',mdl[16:20])
    sQ=sQ[0]*sI
    ### U fraction
    sU=struct.unpack('f',mdl[20:24])
    sU=sU[0]*sI
    ### V fraction
    sV=struct.unpack('f',mdl[24:28])
    sV=sV[0]*sI

    ### type bits
    ## Bits: bit 0= extended; bit 1= Q|U|V <>0 and no longer used according to Wim
    bit1=struct.unpack('B',mdl[52:53])[0];
    fl_ext = bit1&1;
    ### Type: bit 0= clean component; bit 3= beamed
    bit2 = struct.unpack('B',mdl[53:54])[0];
    fl_cc = bit2&1;
    fl_beamed = bit2&8;

    ### extended source params: in arcsec, so multiply by ???
    if fl_ext:
      eX=struct.unpack('f',mdl[28:32])
      eX=eX[0]
      eY=struct.unpack('f',mdl[32:36])
      eY=eY[0]
      eP=struct.unpack('f',mdl[36:40])
      eP=eP[0]
      ## the procedure is NMOEXT in nscan/nmoext.for
      if eP==0 and eX==eY:
        r0=0
      else:
        r0=0.5*(360/math.pi)*math.atan2(-eP,eY-eX)
      r1=math.sqrt(eP*eP+(eX-eY)*(eX-eY))
      r2=eX+eY
      # the real stuff
      # ex,eY (arcsec) (major,minor axes),  eP (deg) position angle
      #eX=math.sqrt(abs(0.5*(r2+r1)))*3600*360/math.pi
      #eY=math.sqrt(abs(0.5*(r2-r1)))*3600*360/math.pi
      #eP=r0/2
      # use radians directly
      eX=math.sqrt(abs(0.5*(r2+r1)))
      eY=math.sqrt(abs(0.5*(r2-r1)))
      eP=r0/(2*360)*math.pi
    ### spectral index
    SI=struct.unpack('f',mdl[40:44])
    SI=SI[0]
    ### rotation measure
    RM=struct.unpack('f',mdl[44:48])
    RM=RM[0]
    ###### the remaining is not needed
    # bit1 and bit2 together somehow specify the source type, which in Sarod's code is very confusing. So I just do:

    # NEWSTAR MDL lists might have same source twice if they are
    # clean components, so make a unique name for them
    bname='N'+str(id);
    if unamedict.has_key(bname):
      uniqname = bname+'_'+str(unamedict[bname])
      unamedict[bname] += 1
    else:
      uniqname = bname
      unamedict[bname] = 1
    # compose source information
    pos = ModelClasses.Position(*lm_ncp_to_radec(ra0,dec0,ll,mm));
    flux  = ModelClasses.PolarizationWithRM(sI,sQ,sU,sV,RM,freq0);
    spectrum = ModelClasses.SpectralIndex(SI,freq0);
    tags = {};
    # work out beam gain and apparent flux
    tags['_lm_ncp'] = (ll,mm);
    tags['_newstar_r']   = tags['r'] = r = math.sqrt(ll*ll+mm*mm);
    tags['newstar_beamgain'] = bg = max(math.cos(beam_const*r)**6,.01);
    if fl_beamed:
      tags['Iapp'] = sI*bg;
      tags['newstar_beamed'] = True;
      tags['flux_intrinsic'] = True;
    else:
      tags['flux_apparent'] = True;
    # make some tags based on model flags
    if fl_cc:
      tags['newstar_cc'] = True;
    # make shape if extended
    if fl_ext and max(eX,eY) >= min_extent:
      shape = ModelClasses.Gaussian(eX,eY,eP);
    else:
      shape = None;
    # compute apparent flux
    src = SkyModel.Source(uniqname,pos,flux,shape=shape,spectrum=spectrum,**tags);
    srclist.append(src);
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  return ModelClasses.SkyModel(ra0=ra0,dec0=dec0,pbexp='max(cos(65*1e-9*fq*r)**6,.01)',*srclist);



