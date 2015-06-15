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

import Kittens.utils
import os.path
import sys
import traceback

_verbosity = Kittens.utils.verbosity(name="lsmformats");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

Formats = {};
_FormatList = [];
_FormatsInitialized = False;

def _initFormats ():
  """Initializes all known formats by importing their modules""";
  global _FormatsInitialized;
  if not _FormatsInitialized:
    for format in [ "ModelHTML","ASCII","BBS","NEWSTAR","AIPSCC","AIPSCCFITS","PyBDSMGaul" ]:
      try:
        __import__(format,globals(),locals());
      except:
        traceback.print_exc();
        print "Error loading support for format '%s', see above. Format will not be available."%format;
    _FormatsInitialized = True;

def registerFormat (name,import_func,doc,extensions,export_func=None):
  """Registers an external format, with an import function""";
  global Formats;
  Formats[name] = (import_func,export_func,doc,extensions);
  _FormatList.append(name);

def getFormat (name):
  """Gets file format by name. Returns name,import_func,export_func,docstring if found, None,None,None,None otherwise.""";
  _initFormats();
  if name not in Formats:
    return None,None,None,None;
  import_func,export_func,doc,extensions = Formats[name];
  return name,import_func,export_func,doc;

def getFormatExtensions (name):
  """Gets file format by name. Returns name,import_func,export_func,docstring if found, None,None,None,None otherwise.""";
  _initFormats();
  if name not in Formats:
    return None;
  import_func,export_func,doc,extensions = Formats[name];
  return extensions;
  
def determineFormat (filename):
  """Tries to determine file format by filename. Returns name,import_func,export_func,docstring if found, None,None,None,None otherwise.""";
  _initFormats();
  for name,(import_func,export_func,doc,extensions) in Formats.iteritems():
    for ext in extensions:
      if filename.endswith(ext):
        return name,import_func,export_func,doc;
  return None,None,None,None;
  
def listFormats ():
  _initFormats();
  return _FormatList;

def listFormatsFull ():
  _initFormats();
  return [ (name,Formats[name]) for name in _FormatList ];

def resolveFormat (filename,format):
  """Helper function, resolves format/filename arguments to a format tuple""";
  _initFormats();
  if format:
    name,import_func,export_func,doc = getFormat(format);
    if not import_func:
      raise TypeError("Unknown model format '%s'"%format);
  else:
    name,import_func,export_func,doc = determineFormat(filename);
    if not import_func:
      raise TypeError("Cannot determine model format from filename '%s'"%filename);
  return name,import_func,export_func,doc;
  
# provide some convenience methods

def load (filename,format=None,verbose=True):
  """Loads a sky model."""
  name,import_func,export_func,doc = resolveFormat(filename,format);
  if not import_func:
    raise TypeError("Unknown model format '%s'"%format);
  if verbose:
    print "Loading %s: %s"%(filename,doc);
  return import_func(filename);

def save (model,filename,format=None,verbose=True):
  """Saves a sky model."""
  name,import_func,export_func,doc = resolveFormat(filename,format);
  if verbose:
    print "Saving %s: %s"%(filename,doc);
  return export_func(model,filename);
