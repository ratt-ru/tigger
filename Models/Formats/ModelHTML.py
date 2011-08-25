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

import time
import os.path
import sys
import traceback
from HTMLParser import HTMLParser

import Kittens.utils
_verbosity = Kittens.utils.verbosity(name="lsmhtml");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel

DefaultExtension = "lsm.html";

def save (model,filename,sources=None,**kw):
  if sources is None:
    sources = model.sources;
  fobj = file(filename,'w');
  fobj.write("""<HTML><BODY mdltype=SkyModel>\n""");
  if model.name is not None:
    fobj.write(model.renderAttrMarkup('name',model.name,tags='TITLE',verbose="Sky model: "));
    fobj.write("\n");
  # write list of sources
  fobj.write("""<H1>Source list</H1>\n<TABLE BORDER=1 FRAME=box RULES=all CELLPADDING=5>\n""");
  for src in sources:
    fobj.write(src.renderMarkup(tags=["TR\n","TD"]));
    fobj.write("\n");
  fobj.write("""</TABLE>\n""");
  # plot styles
  if model.plotstyles is not None:
    fobj.write("""<H1>Plot styles</H1>\n<TABLE BORDER=1 FRAME=box RULES=all CELLPADDING=5>\n""");
    fobj.write(model.renderAttrMarkup('plotstyles',model.plotstyles,tags=['A','TR\n','TD'],verbose=""));
    fobj.write("""</TABLE>\n""");
  # other attributes
  fobj.write("\n");
  fobj.write("""<H1>Other properties</H1>\n""");
  if model.pbexp is not None:
    fobj.write("<P>");
    fobj.write(model.renderAttrMarkup('pbexp',model.pbexp,tags='A',verbose="Primary beam expression: "));
    fobj.write("</P>\n");
  if model.freq0 is not None:
    fobj.write("<P>");
    fobj.write(model.renderAttrMarkup('freq0',model.freq0,tags='A',verbose="Reference frequency, Hz: "));
    fobj.write("</P>\n");
  if model.ra0 is not None or model.dec0 is not None:
    fobj.write("<P>");
    fobj.write(model.renderAttrMarkup('ra0',model.ra0,tags='A',verbose="Field centre ra: "));
    fobj.write(model.renderAttrMarkup('dec0',model.dec0,tags='A',verbose="dec: "));
    fobj.write("</P>\n");
  for attr,value in model.getExtraAttributes():
    if attr not in ("pbexp","freq0","ra0","dec0"):
      fobj.write("<P>");
      fobj.write(model.renderAttrMarkup(attr,value,tags='A'));
      fobj.write("</P>\n");
  fobj.write("""</BODY></HTML>\n""");

def load (filename,**kw):
  parser = ModelIndexParser();
  parser.reset();
  for line in file(filename):
      parser.feed(line);
  parser.close();
  if not parser.toplevel_objects:
    raise RuntimeError,"failed to load sky model from file %s"%filename;
  return parser.toplevel_objects[0];

class ModelIndexParser (HTMLParser):
  def reset (self):
    HTMLParser.reset(self);
    self.objstack = [];
    self.tagstack = [];
    self.toplevel_objects = [];

  def end (self):
    dprintf(4,"end");

  def handle_starttag (self,tag,attrs):
    dprint(4,"start tag",tag,attrs);
    attrs = dict(attrs);
    # append tag to tag stack. Second element in tuple indicates whether
    # tag is associated with the start of an object definition
    self.tagstack.append([tag,None]);
    # see if attributes describe an LSM object
    # 'type' is an object class
    mdltype = attrs.get('mdltype');
    if not mdltype:
      return;
    # 'attr' is an attribute name. If this is set, then the object is an attribute
    # of the parent-level class
    mdlattr = attrs.get('mdlattr');
    # 'value' is a value. If this is set, then the object can be created from a string
    mdlval  = attrs.get('mdlval');
    dprintf(3,"model item type %s, attribute %s, inline value %s\n",mdltype,mdlattr,mdlval);
    if mdlattr and not self.objstack:
      dprintf(0,"WARNING: attribute %s at top level, ignoring\n",mdlattr);
      return;
    # Now look up the class in our globals, or in ModelClasses
    typeobj = ModelClasses.AtomicTypes.get(mdltype) or ModelClasses.__dict__.get(mdltype);
    if not callable(typeobj):
      dprintf(0,"WARNING: unknown object type %s, ignoring\n",mdltype);
      return;
    # see if object value is inlined
    if mdlval is not None:
      try:
        obj = typeobj(eval(mdlval));
      except:
        traceback.print_exc();
        dprintf(0,"WARNING: failed to create object of type %s from string value '%s', ignoring\n",mdltype,mdlval);
        return;
      self.add_object(mdlattr,obj);
    # else add object to stack and start accumulating attributes
    else:
      # change entry on tagstack to indicate that this tag started an object
      self.tagstack[-1][1] = len(self.objstack);
      # append object entry to stack -- we'll create the object when a corresponding end-tag
      # is encountered.
      self.objstack.append([mdlattr,typeobj,[],{}]);

  def handle_endtag (self,endtag):
    dprint(4,"end tag",endtag);
    # close all tags from top of stack, until we hit this one's start tag
    while self.tagstack:
      tag,nobj = self.tagstack.pop(-1);
      dprint(4,"closing tag",tag);
      # if tag corresponds to an object, create object
      if nobj is not None:
        self.close_stack_object();
      if tag == endtag:
        break;

  def add_object (self,attr,obj):
    """Adds object to model."""
    # if no object stack, then object is a top-level container
    if not self.objstack:
      if attr:
        dprintf(0,"WARNING: attribute %s at top level, ignoring\n",attr);
        return;
      self.toplevel_objects.append(obj);
    # else  add object as attribute or argument of top container in the stack
    else:
      if attr:
        self.objstack[-1][3][attr] = obj;
      else:
        self.objstack[-1][2].append(obj);

  def close_stack_object (self):
    """This function is called when an object from the top of the stack needs to be created.
    Stops accumulating attributes and calls the object constructor."""
    mdlattr,typeobj,args,kws = self.objstack.pop(-1);
    # create object
    try:
      if typeobj in (list,tuple):
        obj = typeobj(args);
      else:
        obj = typeobj(*args,**kws);
    except:
      traceback.print_exc();
      dprintf(0,"WARNING: failed to create object of type %s for attribute %s, ignoring\n",typeobj,mdlattr);
      return;
    # add the object to model
    self.add_object(mdlattr,obj);

import Tigger.Models.Formats
Tigger.Models.Formats.registerFormat("Tigger",load,"Tigger sky model",(".lsm.html",),export_func=save);
