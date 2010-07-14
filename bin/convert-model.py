#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import pyfits
import re
import os.path
import pyfits
import math
import numpy

DEG = math.pi/180;


if __name__ == '__main__':
  # setup some standard command-line option parsing
  #
  from optparse import OptionParser
  parser = OptionParser(usage="""%prog: sky_model [output_model]""",
                        description="""Converts sky models between formats and/or applies varipous processing options.
Input 'sky_model' may be any model format importable by Tigger, recognized by its extension. 'output_model' is always a native
Tigger model. If an output model is not specfied, the conversion is done in-place if the input model is a Tigger model (-f switch
must be specified then), or else a new filename is generated.""");
  parser.add_option("-f","--force",action="store_true",
                    help="Forces overwrite of output model.");
  parser.add_option("--app-to-int",action="store_true",
                    help="Convert apparent fluxes to intrinsic. Only works for NEWSTAR or NEWSTAR-derived input models.");
  parser.add_option("--cluster-dist",type="float",metavar="ARCSEC",
                    help="Distance parameter for source clustering. Default is %default.");
  parser.add_option("--rename",action="store_true",
                    help="Rename sources according to the COPART (cluster ordering, P.A., radius, type) scheme""");

  parser.set_defaults(cluster_dist=60);

  (options,rem_args) = parser.parse_args();

  # get filenames
  if len(rem_args) == 1:
    skymodel = rem_args[0];
    output = None;
  elif len(rem_args) == 2:
    skymodel,output = rem_args;
  else:
    parser.error("Incorrect number of arguments. Use -h for help.");

  # find Tigger
  try:
    import Tigger
  except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))));
    try:
      import Tigger
    except:
      print "Unable to import the Tigger package. Please check your installation and PYTHONPATH.";
      sys.exit(1);
  from Tigger.Models import Import,ModelHTML
  from Tigger import Coordinates

  # figure out input and output
  skymodel_name,ext = os.path.splitext(skymodel);
  if ext.upper() == '.MDL':
    loadfunc,format = Import.importNEWSTAR,"NEWSTAR";
  else:
    loadfunc,format = ModelHTML.loadModel,"native";

  print "Reading %s as a %s format model"%(skymodel,format);
  # nothing to do?
  if format is "native":
    if options.rename and not options.app_to_int:
      print "Native input format is same as output, and no conversion flags specified.";
      sys.exit(1);

  # figure out output name, if not specified
  if output is None:
    if format is "native":
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
  model = loadfunc(skymodel);
  if not model.sources:
    print "Input model %s contains no sources."%skymodel;
    sys.exit(1);

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
        # lookup radius, in units of 10'. 'x' means >=100'
        rad = min(int(math.sqrt(l[i]**2+m[i]**2)*(60/DEG)/10),10);
        radchr = '0123456789x'[rad];
        # convert p.a. to tens of degrees
        pa = math.atan2(l[i],m[i]);
        if pa < 0:
          pa += math.pi*2;
        pa = round(pa/(DEG*10))%36;
        # make clustername
        clusname = clustername[iclust] = "%s%02d%s"%(Names[iclust],pa,radchr);
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
