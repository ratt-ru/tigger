
import sys
import traceback
import math
import struct

import Kittens.utils
import  numpy

import ModelClasses
import SkyModel

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

def importASCII_DMS (filename,format=DefaultDMSFormat,freq0=None):
  srclist = [];
  dprint(2,"importing ASCII DMS file",filename);
  # get minimum necessary fields from format
  try:
    base_fields = [ format[x] for x in ['name','ra_h','ra_m','ra_s','dec_d','dec_m','dec_s','i'] ];
  except:
    raise ValueError,"DMS format specification lacks mandatory name and/or position and/or flux fields";
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

  # now process file line-by-line
  for linenum,line in enumerate(file(filename)):
    try:
      # strip whitespace
      line = line.strip();
      dprint(4,"read line:",line);
      # skip empty or commented lines
      if not line or line[0] == '#':
        continue;
      # split (at whitespace) into fields
      fields = line.split();
      # get minimal necessary attributes
      name = fields[base_fields[0]];
      try:
        h1,m1,s1,d2,m2,s2,i = map(float,[fields[x] for x in base_fields[1:]]);
      except IndexError:
        raise ValueError,"mandatory name/position/flux fields missing";
      # see if we have freq0
      try:
        f0 = freq0 or (freq0_field and float(fields[freq0_field]));
      except IndexError:
        f0 = None;
      # see if we have Q/U/V
      q=u=v=None;
      if quv_fields:
        try:
          q,u,v = map(float,[fields[x] for x in quv_fields]);
        except IndexError:
          pass;
      # see if we have RM as well. Create flux object (unpolarized, polarized, polarized w/RM)
      if q is None:
        flux = ModelClasses.Flux(i);
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
      ex=ey=pa=None;
      if ext_fields:
        try:
          ex,ey,pa = map(float,[fields[x] for x in ext_fields]);
        except IndexError:
          pass;
      # form up shape object
      if ex or ey:
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
      ra  = (h1+m1/60.+s1/3600.)*(math.pi/12);
      dec = (d2+m2/60.+s2/3600.)*(math.pi/180);
      pos = ModelClasses.Position(ra,dec);
      # now create a source object
      dprint(3,name,ra,dec,i,q,u,v);
      srclist.append(SkyModel.Source(name,pos,flux,shape=shape,spectrum=spectrum,**dict([(tag,True) for tag in tags])));
    except:
      dprintf(0,"%s:%d: %s, skipping\n",filename,linenum+1,str(sys.exc_info()[1]));
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  return ModelClasses.SkyModel(*srclist);

registerFormat("text file (hms/dms)",importASCII_DMS,extensions="*.txt");

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


def importNEWSTAR (filename,import_src=True,import_cc=True,**kw):
  """Imports a NEWSTAR MDL file.
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
    if fl_ext:
      shape = ModelClasses.Gaussian(eX,eY,eP);
    else:
      shape = None;
    # compute apparent flux
    src = SkyModel.Source(uniqname,pos,flux,shape=shape,spectrum=spectrum,**tags);
    srclist.append(src);
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  return ModelClasses.SkyModel(ra0=ra0,dec0=dec0,pbexp='max(cos(65*1e-9*fq*r)**6,.01)',*srclist);



