#!/usr/bin/python
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
import pyfits
import re
import os.path
import pyfits
import math
import numpy
import traceback

DEG = math.pi/180;

def make_output_filename(output_file,input_file,extension):
  """Makes an output filename from the input by appending extension""";
  if output_file:
    return output_file;
  name,ext = os.path.splitext(input_file);
  name1,ext1 = os.path.splitext(name);
  if ext == ".html" and ext1 == ".lsm":
    return name1 + extension;
  else:
    return name + extension;


if __name__ == '__main__':
  import Kittens.utils
  from Kittens.utils import curry
  _verbosity = Kittens.utils.verbosity(name="export-model");
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
      
  from Tigger.Models import ModelHTML
  from Tigger import Coordinates
  from Tigger.Models.Formats import NEWSTAR
  from Tigger.Models.Formats import ASCII

  # setup some standard command-line option parsing
  #
  from optparse import OptionParser
  parser = OptionParser(usage="""%prog: sky_model [output_file]""",
                        description="""Exports a Tigger sky model into an external format. Format is determined by option switches, 
or automatically from the output filename extension.""");
  parser.add_option("-N","--newstar",action="store_true",
                    help="Export as a NEWSTAR model (.MDL) file.");
  parser.add_option("-f","--force",action="store_true",
                    help="Forces overwrite of output file.");
  parser.add_option("-t","--tags",type="string",action="append",metavar="TAG",
                    help="Only export sources with the specified tags.");
  parser.add_option("--ref-freq",type="float",metavar="MHz",
                    help="Specifies the reference frequency for the output model, overriding any frequency specified in the input.");
  parser.add_option("-d", "--debug",dest="verbose",type="string",action="append",metavar="Context=Level",
                    help="(for debugging Python code) sets verbosity level of the named Python context. May be used multiple times.");

  parser.set_defaults(ref_freq=0);

  (options,rem_args) = parser.parse_args();

  # get filenames
  if len(rem_args) == 1:
    input_file = rem_args[0];
    output_file = None;
  elif len(rem_args) == 2:
    input_file,output_file = rem_args;
  else:
    parser.error("Incorrect number of arguments. Use -h for help.");

  # figure out output_file format
  extension = None;
  if not options.newstar:
    if not output_file:
      print "Output format not specified.";
      sys.exit(1);
    name,ext = os.path.splitext(output_file);
    if ext.upper() == ".MDL":
      options.newstar = True;
    else:
      print "Output format cannot be determined from filename %s, please specify explicitly."%output_file;
      sys.exit(1);
    
  # read input model
  print "Reading Tigger model %s"%input_file;
  model = ModelHTML.loadModel(input_file);
  sources = model.sources;
  if not sources:
    print "No sources in model, output_file model will be empty.";
  else:
    # restrict sources
    for tag in (options.tags or []):
      sources = [ src for src in sources if getattr(src,tag,False) ];
    if not sources:
      print "No sources left after selection by tag has been applied, output_file model will be empty.";
  print "%d model sources will be exported."%len(sources);
  
  # now export
  if options.newstar:
    # determine reference frequency
    # first check the --ref-freq switch, then the model reference frequency attribute
    freq0 = (options.ref_freq*1e+6) or model.refFreq();
    # if neither is set, check sources' reference freq
    if not freq0:
      freq0_set = set();
      for src in sources:
        freq0 = ( src.spectrum and getattr(src.spectrum,'freq0',None) ) or getattr(src.flux,'freq0',None);
        if freq0:
          freq0_set.add(freq0);
      # must be the same for all sources
      if not freq0_set or len(freq0_set) > 1:
        print "Unable to determine reference frequency. Please specify explicitly via the --ref-freq option."
        sys.exit(1);
      freq0 = freq0_set.pop();
    print "Using a reference frequency of %.2f MHz"%(freq0*1e-6,);
    output_file = make_output_filename(output_file,input_file,".mdl");
    if os.path.exists(output_file) and not options.force:
      print "Output file %s already exists. Use the -f switch to overwrite."%output_file;
      sys.exit(1);
    print "Exporting to NEWSTAR model %s"%output_file;
    NEWSTAR.save(model,output_file,sources=sources,freq0=freq0);
