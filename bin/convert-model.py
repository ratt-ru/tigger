#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import pyfits
import re
import os.path
import pyfits


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
  parser.add_option("--rename",action="store_true",
                    help="Rename sources according to the OAR (ordering, azimuth, radius) scheme""");

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
    sys.path.append(os.path.dirname(os.path.dirname(__file__)));
    try:
      import Tigger
    except:
      parser.error("Unable to import the Tigger package. Please check your installation and PYTHONPATH.");
  from Tigger.Models import Import,ModelHTML

  # figure out input and output
  skymodel_name,ext = os.path.splitext(skymodel);
  if ext.upper() == 'MDL':
    loadfunc,format = Import.importNEWSTAR,"NEWSTAR";
  else:
    loadfunc,format = ModelHTML.loadModel,"native";

  # nothing to do?
  if format is "native" and not options.rename and not options.app_to_int:
    parser.error("Native input format is same as output, and no conversion flags specified.");

  # figure out output name, if not specified
  if output is None:
    if format is "native":
      output = skymodel;
    else:
      output = skymodel_name + ModelHTML.DefaultExtension;
  # check if we need to overwrite
  if os.path.exists(output) and not options.force:
    parser.error("Output file %s already exists. Use the -f switch to overwrite."%output);

  # load the model
  model = loadfunc(skymodel);

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
    print "Converted apparent to instrinsic flux for %d model sources"%nsrc;
    if len(model.sources) != nsrc:
      print "  (%d sources were skipped for whatever reason.)"%(len(model.sources)-nsrc);

  if options.rename:
    pass;

  # save output
  model.save(output);
