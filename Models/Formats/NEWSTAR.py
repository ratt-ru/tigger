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

import  numpy

import Kittens.utils

import Tigger.Models.Formats
from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
from Tigger.Models.Formats import dprint,dprintf

def lm_ncp_to_radec (ra0,dec0,l,m):
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
  return ra,dec

def radec_to_lm_ncp (ra0,dec0,ra,dec):
  """Converts coordinates in l,m (NCP) relative to ra0,dec0 into ra,dec.""";
  l=-math.sin(ra-ra0)*math.cos(dec)
  sind0=math.sin(dec0)
  if sind0 != 0:
    m=-(math.cos(ra-ra0)*math.cos(dec)-math.cos(dec0))/math.sin(dec0)
  else:
    m=0
  return (l,m)


def parseGFH (gfh):
  """Parses the GFH (general file header?) structure at the beginning of the file""";
  ## type
  ftype = gfh[0:4].tostring()
  ## length & version
  fhlen,fver = struct.unpack('ii',gfh[4:12])
  ### creation date
  crdate = gfh[12:23].tostring()
  ### creation time
  crtime = gfh[23:28].tostring()
  ### revision date
  rrdate = gfh[28:39].tostring()
  ### revision time
  rrtime = gfh[39:44].tostring()
  ### revision count
  rcount = struct.unpack('i',gfh[44:48])
  rcount = rcount[0]
  ### node name
  nname = gfh[48:128].tostring()
  ### types
  dattp = struct.unpack('B',gfh[128:129])[0];
  link1,link2 = struct.unpack('ii',gfh[152:160]);
  ### the remaining info is not needed
  dprint(1,"read header type=%s, length=%d, version=%d, created=%s@%s, updated=%s@%s x %d, node name=%s, dattp=%d, link=%d,%d"%
    (ftype,fhlen,fver,crdate,crtime,rrdate,rrtime,rcount,nname,dattp,link1,link2));
  return (ftype,fhlen,fver,crdate,crtime,rrdate,rrtime,rcount,nname);

def parseMDH (mdh):
  """Parses the MDH (model file header?) structure""";
  maxlin,modptr,nsources,mtype = struct.unpack('iiii',mdh[12:28]);
  mepoch = struct.unpack('f',mdh[28:32])[0];
  ra0,dec0,freq0 = struct.unpack('ddd',mdh[32:56]);
  ### Max. # of lines in model or disk version
  ### pointer to model ???
  ### no of sources in model
  ### model type(0: no ra,dec, 1=app, 2=epoch)
  ### Epoch (e.g. 1950) if TYP=2 (float) : 4 bytes
  ###  Model centre RA (circles) : double
  ra0 *= math.pi*2;
  dec0 *= math.pi*2;
  ### Model centre FRQ (MHz)
  freq0 *= 1e6
  ### the remaining is not needed
  dprint(1,"read model header maxlines=%d, pointer=%d, sources=%d, type=%d, epoch=%f RA=%f, DEC=%f (rad) Freq=%f Hz"%
    (maxlin,modptr,nsources,mtype,mepoch,ra0,dec0,freq0));
  return (maxlin,modptr,nsources,mtype,mepoch,ra0,dec0,freq0);
  
def load (filename,import_src=True,import_cc=True,min_extent=0,**kw):
  """Imports a NEWSTAR MDL file.
  min_extent is minimal source extent (in radians), above which a source will be treated as a Gaussian rather than a point component.
  import_src=False causes source components to be omitted
  import_cc=False causes clean components to be omitted
  """;
  srclist = [];
  dprint(1,"importing NEWSTAR file",filename);
  # build the LSM from a NewStar .MDL model file
  # if only_cleancomp=True, only clean components are used to build the LSM
  # if no_cleancomp=True, no clean components are used to build the LSM
  ff = open(filename,mode="rb");
  
  ### read GFH and MDH headers -- 512 bytes
  try:
    gfh = numpy.fromfile(ff,dtype=numpy.uint8,count=512);
    mdh = numpy.fromfile(ff,dtype=numpy.uint8,count=64);
    # parse headers
    ftype,fhlen,fver,crdate,crtime,rrdate,rrtime,rcount,nname = parseGFH(gfh);
    if ftype != ".MDL":
      raise TypeError;
    maxlin,modptr,nsources,mtype,mepoch,ra0,dec0,freq0 = parseMDH(mdh);
    
    beam_const = 65*1e-9*freq0;
    
    ## temp dict to hold unique nodenames
    unamedict={}
    ### Models -- 56 bytes
    for ii in xrange(0,nsources):
      mdl = numpy.fromfile(ff,dtype=numpy.uint8,count=56)
      
      ### source parameters
      sI,ll,mm,id,sQ,sU,sV,eX,eY,eP,SI,RM = struct.unpack('fffiffffffff',mdl[0:48])
      ### type bits
      bit1,bit2 = struct.unpack('BB',mdl[52:54]);

      # convert fluxes
      sI *= 0.005    # convert from WU to Jy (1WU=5mJy)
      sQ *= sI;
      sU *= sI;
      sV *= sI;

      # Interpret bitflags 1: bit 0= extended; bit 1= Q|U|V <>0 and no longer used according to Wim
      fl_ext = bit1&1;
      # Interpret bitflags 2: bit 0= clean component; bit 3= beamed
      fl_cc = bit2&1;
      fl_beamed = bit2&8;

      ### extended source params: in arcsec, so multiply by ???
      if fl_ext:
        ## the procedure is NMOEXT in nscan/nmoext.for
        if eP == 0 and eX == eY:
          r0 = 0
        else:
          r0 = .5*math.atan2(-eP,eY-eX)
        r1 = math.sqrt(eP*eP+(eX-eY)*(eX-eY))
        r2 = eX+eY
        eX = 2*math.sqrt(abs(0.5*(r2+r1)))
        eY = 2*math.sqrt(abs(0.5*(r2-r1)))
        eP = r0

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
      tags['newstar_id'] = id;
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
  except:
    traceback.print_exc();
    raise TypeError("%s does not appear to be a valid NEWSTAR MDL file"%filename);
  
  dprintf(2,"imported %d sources from file %s\n",len(srclist),filename);
  return ModelClasses.SkyModel(ra0=ra0,dec0=dec0,freq0=freq0,pbexp='max(cos(65*1e-9*fq*r)**6,.01)',*srclist);


def save (model,filename,freq0=None,sources=None,**kw):
  """Saves model to a NEWSTAR MDL file.
  The MDL file must exist, since the existing header is reused.
  'sources' is a list of sources to write, if None, then model.sources is used.
  """
  if sources is None:
    sources = model.sources;
  dprintf(2,"writing %s model sources to NEWSTAR file\n",len(sources),filename);
  
  ra0,dec0 = model.fieldCenter();
  freq0 = freq0 or model.refFreq();
  # if freq0 is not specified, scan sources
  if freq0 is None:
    for src in sources:
      freq0 = (src.spectrum and getattr(src.spectrum,'freq0',None)) or getattr(src.flux,'freq0',None);
      if freq0:
        break;
    else:
      raise ValueError("unable to determine NEWSTAR model reference frequency, please specify one explicitly.");
  
  ff = open(filename,mode="wb");
  
  ### create GFH header
  gfh = numpy.zeros(512,dtype=numpy.uint8);
  datestr = time.strftime("%d-%m-%Y");
  timestr = time.strftime("%H:%M");
  struct.pack_into("4sii11s5s11s5si80sB",gfh,0,".MDL",512,1,
    datestr,timestr,datestr,timestr,0,
    os.path.splitext(os.path.basename(filename))[0],6);  # 6=datatype
  # link1/link2 gives the header size actually
  struct.pack_into("ii",gfh,152,512,512);
  gfh.tofile(ff);  
  
  # create MDH header
  mdh = numpy.zeros(64,dtype=numpy.uint8);
  struct.pack_into('iiii',mdh,12,1,576,0,2); # maxlin,pointer,num_sources,mtype
  struct.pack_into('f',mdh,28,getattr(model,'epoch',2000));
  struct.pack_into('ddd',mdh,32,ra0/(2*math.pi),dec0/(2*math.pi),freq0*1e-6);
  mdh.tofile(ff);

  # get the max ID, if specified
  max_id = max([ getattr(src,'newstar_id',0) for src in sources ]);
  # now loop over model sources
  # count how many are written out -- only point sources and gaussians are actually written out, the rest are skipped
  nsrc = 0;
  for src in sources:
    # create empty newstar source structure
    mdl = numpy.zeros(56,dtype=numpy.uint8);
    
    if src.shape and not isinstance(src.shape,ModelClasses.Gaussian):
      dprint(3,"skipping source '%s': non-supported type '%s'"%(src.name,src.shape.typecode));
      continue;
    
    stI = src.flux.I;
    # get l,m NCP position -- either from tag, or compute
    lm = getattr(src,'_lm_ncp',None);
    if lm:
      if isinstance(lm,(tuple,list)) and len(lm) == 2:
        l,m = lm;
      else:
        dprint(0,"warning: skipping source '%s' because its _lm_ncp attribute is malformed (tuple of 2 values expected)"%src.name);
        continue;
    else:
      l,m = radec_to_lm_ncp(ra0,dec0,src.pos.ra,src.pos.dec);
      
    # update source count
    nsrc += 1;
    # generate source id
    src_id = getattr(src,'newstar_id',None);
    if src_id is None:
      src_id = max_id = max_id+1;

    # encode position, flux, identifier -- also, convert flux from Jy to WU to Jy (1WU=5mJy)
    struct.pack_into('fffi',mdl,0,stI/0.005,l,m,src_id);
     
    # encode fractional polarization
    struct.pack_into('fff',mdl,16,*[ getattr(src.flux,stokes,0.0)/stI for stokes in "QUV" ]);
    
    ## encode flag & type bits
    ## Flag: bit 0= extended; bit 1= Q|U|V <>0 and no longer used according to Wim
    ## Type: bit 0= clean component; bit 3= beamed
    beamed = getattr(src,'flux_intrinsic',False) or getattr(src,'newstar_beamed',False);
    struct.pack_into('BB',mdl,52,
      1 if src.shape else 0,
      (1 if getattr(src,'newstar_cc',False) else 0) | (8 if beamed else 0));

    ### extended source parameters
    if src.shape:
      ## the procedure is NMOEXF in nscan/nmoext.for
      R0 = math.cos(src.shape.pa);
      R1 = -math.sin(src.shape.pa);
      R2 = (.5*src.shape.ex)**2;
      R3 = (.5*src.shape.ey)**2;
      ex = R2*R1*R1+R3*R0*R0          
      ey = R2*R0*R0+R3*R1*R1
      pa = 2*(R2-R3)*R0*R1
      struct.pack_into('fff',mdl,28,ex,ey,pa);

    ### spectral index
    if isinstance(src.spectrum,ModelClasses.SpectralIndex):
      struct.pack_into('f',mdl,40,src.spectrum.spi);
    
    if isinstance(src.flux,ModelClasses.PolarizationWithRM):
      struct.pack_into('f',mdl,44,src.flux.rm);
      
    mdl.tofile(ff);
    
  # update MDH header with the new number of sources
  struct.pack_into('i',mdh,20,nsrc);
  ff.seek(512);
  mdh.tofile(ff);
  ff.close();
  dprintf(1,"wrote %d sources to file %s\n",nsrc,filename);


Tigger.Models.Formats.registerFormat("NEWSTAR",load,"NEWSTAR model file",(".mdl",".MDL"),export_func=save);
