#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import pyfits
import re
import os.path
import pyfits
import math
import numpy
import traceback

DEG = math.pi/180;

NATIVE = "Tigger";

if __name__ == '__main__':
  import Kittens.utils
  from Kittens.utils import curry
  _verbosity = Kittens.utils.verbosity(name="convert-model");
  dprint = _verbosity.dprint;
  dprintf = _verbosity.dprintf;

  # find Tigger
  try:
    import Tigger
  except ImportError:
    dirname = os.path.dirname(os.path.realpath(__file__));
    # go up the directory tree looking for directory "Tigger"
    while len(dirname) > 1:
      if os.path.basename(dirname) == "Tigger":
	break;
      dirname = os.path.dirname(dirname);
    else:
      print "Unable to locate the Tigger directory, it is not a parent of %s. Please check your installation and/or PYTHONPATH."%os.path.realpath(__file__);
      sys.exit(1);
    sys.path.append(os.path.dirname(dirname));
    try:
      import Tigger
    except:
      print "Unable to import the Tigger package from %s. Please check your installation and PYTHONPATH."%dirname;
      sys.exit(1);
      
  from Tigger.Models import Import,ModelHTML
  from Tigger import Coordinates

  # setup some standard command-line option parsing
  #
  from optparse import OptionParser
  parser = OptionParser(usage="""%prog: sky_model [output_model]""",
                        description="""Converts sky models into Tigger format and/or applies various processing options.
Input 'sky_model' may be any model format importable by Tigger, recognized by extension, or explicitly specified via an option switch.
'output_model' is always a native Tigger model. If an output model is not specfied, the conversion is done in-place if the input model
is a Tigger model (-f switch must be specified to allow overwriting), or else a new filename is generated.""");
  parser.add_option("-f","--force",action="store_true",
                    help="Forces overwrite of output model.");
  parser.add_option("--newstar",action="store_true",
                    help="Input is a NEWSTAR model.");
  parser.add_option("--text",action="store_true",
                    help="Input is an ASCII text table.");
  parser.add_option("--format",type="string",
                    help="""Format string, for text tables. Default is "%default".""");
  parser.add_option("--tigger",action="store_true",
                    help="Input is a Tigger model.");
  parser.add_option("--app-to-int",action="store_true",
                    help="Convert apparent fluxes in input model to intrinsic. Only works for NEWSTAR or NEWSTAR-derived input models.");
  parser.add_option("--recenter",type="string",metavar='COORDINATES',
                    help="Shift the sky model to a different field center. Use a pyrap.measures direction string of the form "+\
                    "REF,C1,C2, for example \"j2000,1h5m0.2s,+30d14m15s\", or \"b1950,115.2d,+30.5d\". See the pyrap.measures documentation for more details.");
  parser.add_option("--ref-freq",type="float",metavar="MHz",
                    help="Set or change the reference frequency of the model.");
  parser.add_option("--primary-beam",type="string",metavar="EXPR",
                    help="""Apply a primary beam expression to estimate apparent fluxes. Any valid Python expression using the variables 'r' and 'fq' is accepted.
                    Example (for the WSRT-like 25m dish PB): "cos(min(65*fq*1e-9*r,1.0881))**6".""");
  parser.add_option("--min-extent",type="float",metavar="ARCSEC",
                    help="Minimal source extent, when importing NEWSTAR or ASCII DMS files. Sources with a smaller extent will be treated as point sources. Default is %default.");
  parser.add_option("--cluster-dist",type="float",metavar="ARCSEC",
                    help="Distance parameter for source clustering. Default is %default.");
  parser.add_option("--rename",action="store_true",
                    help="Rename sources according to the COPART (cluster ordering, P.A., radial distance, type) scheme");
  parser.add_option("--radial-step",type="float",metavar="ARCMIN",
                    help="Size of one step in radial distance for the COPART scheme. Default is %default'.");
  parser.add_option("-d", "--debug",dest="verbose",type="string",action="append",metavar="Context=Level",
                    help="(for debugging Python code) sets verbosity level of the named Python context. May be used multiple times.");

  parser.set_defaults(cluster_dist=60,min_extent=0,format=Import.DefaultDMSFormatString,radial_step=10,ref_freq=-1);

  (options,rem_args) = parser.parse_args();
  min_extent = (options.min_extent/3600)*DEG;

  # get filenames
  if len(rem_args) == 1:
    skymodel = rem_args[0];
    output = None;
  elif len(rem_args) == 2:
    skymodel,output = rem_args;
  else:
    parser.error("Incorrect number of arguments. Use -h for help.");

  # figure out recenter option
  if options.recenter:
    try:
      import pyrap.measures
    except:
      traceback.print_exc();
      print "Failed to import pyrap.measures, which is required by the --recenter option."
      print "You probably need to install the 'pyrap' package for this to work."
      sys.exit(1);
    dm = pyrap.measures.measures();
    try:
      center_dir = dm.direction(*(options.recenter.split(',')));
      center_dir = dm.measure(center_dir,'j2000');
      qq = dm.get_value(center_dir);
      print "Will recenter model to %s"%str(qq);
      recenter_radec = [ q.get_value('rad') for q in qq ];
    except:
      print "Error parsing or converting --recenter coordinates, see traceback:";
      traceback.print_exc();
      sys.exit(1);

  # figure out input and output
  skymodel_name,ext = os.path.splitext(skymodel);
  # input format is either explicit, or determined by extension
  if options.newstar:
    loadfunc,kws,format = Import.importNEWSTAR,dict(min_extent=min_extent),"NEWSTAR";
  elif options.text:
    loadfunc,kws,format = Import.importASCII,dict(min_extent=min_extent,format=options.format),"ASCII";
  elif options.tigger:
    loadfunc,kws,format = ModelHTML.loadModel,{},NATIVE;
  elif ext.upper() == '.MDL':
    loadfunc,kws,format = Import.importNEWSTAR,dict(min_extent=min_extent),"NEWSTAR";
  elif ext.upper() in (".TXT",".LSM"):
    loadfunc,kws,format = Import.importASCII,dict(min_extent=min_extent,format=options.format),"ASCII";
  else:
    loadfunc,kws,format = ModelHTML.loadModel,{},NATIVE;

  print "Reading %s as a model of type '%s'"%(skymodel,format);
  # nothing to do?
  if format is NATIVE:
    if not options.rename and not options.app_to_int and not options.recenter:
      print "Input format is same as output, and no conversion flags specified.";
      sys.exit(1);

  # figure out output name, if not specified
  if output is None:
    if format is NATIVE:
      output = skymodel;
    else:
      output = skymodel_name + "." + ModelHTML.DefaultExtension;
  # if no extension on output, add default
  else:
    if not os.path.splitext(output)[1]:
      output = output + "." + ModelHTML.DefaultExtension;

  # check if we need to overwrite
  if os.path.exists(output) and not options.force:
    print "Output file %s already exists. Use the -f switch to overwrite."%output;
    sys.exit(1);

  # load the model
  model = loadfunc(skymodel,**kws);
  if not model.sources:
    print "Input model %s contains no sources"%skymodel;
    sys.exit(1);
  print "Model contains %d sources"%len(model.sources);

  # convert apparent flux to intrinsic
  if options.app_to_int:
    nsrc = 0;
    for src in model.sources:
      bg = getattr(src,'newstar_beamgain',None);
      if getattr(src,'flux_apparent',None) and bg is not None:
        src.setAttribute('Iapp',src.flux.I);
        for pol in 'IQUV':
          if hasattr(src.flux,pol):
            setattr(src.flux,pol,getattr(src.flux,pol)/bg);
        src.removeAttribute('flux_apparent');
        src.setAttribute('flux_intrinsic',True);
        nsrc += 1;
    print "Converted apparent to intrinsic flux for %d model sources"%nsrc;
    if len(model.sources) != nsrc:
      print "  (%d sources were skipped for whatever reason.)"%(len(model.sources)-nsrc);

  # set refrence frequency
  if options.ref_freq >= 0:
    model.setRefFreq(options.ref_freq*1e+6);
    print "Set reference frequency to %f MHz"%options.ref_freq;
    
  # recenter
  if options.recenter:
    proj_src = Coordinates.Projection.SinWCS(*model.fieldCenter());
    proj_target = Coordinates.Projection.SinWCS(*recenter_radec);
    for src in model.sources:
      src.pos.ra,src.pos.dec = proj_target.radec(*proj_src.lm(src.pos.ra,src.pos.dec));
    model.setFieldCenter(*recenter_radec);

  # set PB expression and estimate apparent fluxes
  if options.primary_beam:
    try:
      from math import *
      pbexp = eval('lambda r,fq:'+options.primary_beam);
      dum = pbexp(0,1e+9); # evaluate at r=0 and 1 GHz as a test
      if not isinstance(dum,float):
        raise TypeError,"does not evaluate to a float";
    except Exception,exc:
      print "Bad primary beam expression '%s': %s"%(options.primary_beam,str(exc));
      sys.exit(1);
    # get frequency
    fq = model.refFreq() or 1.4e+9;
    nsrc = 0;
    print "Using beam expression '%s' with reference frequency %f MHz"%(options.primary_beam,fq*1e-6);
    # evaluate sources
    for src in model.sources:
      r = getattr(src,'r',None);
      if r is not None:
        bg = pbexp(r,fq);
        src.setAttribute('beamgain',bg);
        src.setAttribute('Iapp',src.flux.I*bg);
        nsrc += 1;
    print "Applied primary beam expression to %d model sources"%nsrc;
    if len(model.sources) != nsrc:
      print "  (%d sources were skipped for whatever reason, probably they didn't have an 'r' attribute)"%(len(model.sources)-nsrc);

  if options.rename:
    print "Renaming sources using the COPART convention"
    typecodes = dict(Gau="G",FITS="F");
    # sort sources by decreasing flux
    sources = sorted(model.sources,lambda a,b:cmp(b.brightness(),a.brightness()));
    projection = Coordinates.Projection.SinWCS(*model.fieldCenter());
    # work out source clusters
    l = numpy.zeros(len(sources),float);
    m = numpy.zeros(len(sources),float);
    for i,src in enumerate(sources):
      l[i],m[i] = projection.lm(src.pos.ra,src.pos.dec);
    # now, convert to dist[i,j]: distance between sources i and j
    dist = numpy.sqrt((l[:,numpy.newaxis]-l[numpy.newaxis,:])**2 + (m[:,numpy.newaxis]-m[numpy.newaxis,:])**2);
    # cluster[i] is (N,R), where N is cluster number for source #i, and R is rank of that source in the cluster
    # place source 0 into cluster 0,#0
    cluster = [ (0,0) ];
    clustersize = [1];
    clusterflux = [ sources[0].brightness() ];
    dist0 = options.cluster_dist*DEG/3600;
    for i in range(1,len(sources)):
      src = sources[i];
      # find closest brighter source, and assign to its cluster if close enough
      imin = dist[i,:i].argmin();
      if dist[i,imin] <= dist0:
        iclust,rank = cluster[imin];
        cluster.append((iclust,clustersize[iclust]));
        clustersize[iclust] += 1;
        clusterflux[iclust] += src.brightness();
      # else start new cluster from source
      else:
        cluster.append((len(clustersize),0));
        clustersize.append(1);
        clusterflux.append(src.brightness());
    # now go over and rename the sources
    # make array of source names
    chars = [ chr(x) for x in range(ord('a'),ord('z')+1) ];
    names = list(chars);
    while len(names) < len(sources):
      names += [ ch+name for ch in chars for name in names ];
    # make a second version where the single-char names are capitalized
    Names = list(names);
    Names[:26] = [ n.upper() for n in chars ];
    # now go over and rename the sources
    clustername = {};
    for i,src in enumerate(sources):
      iclust,rank = cluster[i];
      # for up name of cluster based on rank-0 source
      if not rank:
        # lookup radius, in units of arcmin
        rad_min = math.sqrt(l[i]**2+m[i]**2)*(60/DEG);
        # divide by radial step
        rad = min(int(rad_min/options.radial_step),10);
        radchr = '0123456789x'[rad];
        if rad_min > options.radial_step*0.01:
          # convert p.a. to tens of degrees
          pa = math.atan2(l[i],m[i]);
          if pa < 0:
            pa += math.pi*2;
          pa = round(pa/(DEG*10))%36;
          # make clustername
          clusname = clustername[iclust] = "%s%02d%s"%(Names[iclust],pa,radchr);
        else:
          clusname = clustername[iclust] = "%s0"%(Names[iclust]);
        src.name = "%s%s"%(clusname,typecodes.get(src.typecode,''));
        src.setAttribute('cluster_lead',True);
      else:
        clusname = clustername[iclust];
        src.name = "%s%s%s"%(clusname,names[rank-1],typecodes.get(src.typecode,''));
      src.setAttribute('cluster',clusname);
      src.setAttribute('cluster_size',clustersize[iclust]);
      src.setAttribute('cluster_flux',clusterflux[iclust]);
  # save output
  print "Saving model to",output;
  model.save(output);
