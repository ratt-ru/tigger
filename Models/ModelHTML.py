import time
import os.path
import sys
import traceback
from HTMLParser import HTMLParser

import Kittens.utils
_verbosity = Kittens.utils.verbosity(name="lsmhtml");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

import ModelClasses
import SkyModel

def saveModel (filename,model):
  fobj = file(filename,'w');
  fobj.write("""<HTML><BODY mdltype=SkyModel>\n""");
  if model.name is not None:
    fobj.write(model.renderAttrMarkup('name',model.name,tags='TITLE',verbose="Sky model: "));
    fobj.write("\n");
  # write list of sources
  fobj.write("""<H1>Source list</H1>\n<TABLE BORDER=1 FRAME=box RULES=all CELLPADDING=5>\n""");
  for src in model.sources:
    fobj.write(src.renderMarkup(tags=["TR\n","TD"]));
    fobj.write("\n");
  fobj.write("""</TABLE>\n""");
  # plot styles
  if model.plotstyles is not None:
    fobj.write("""<H1>Plot styles</H1>\n<TABLE BORDER=1 FRAME=box RULES=all CELLPADDING=5>\n""");
    fobj.write(model.renderAttrMarkup('plotstyles',model.plotstyles,tags=['A','TR\n','TD'],verbose=""));
    fobj.write("""</TABLE>\n""");
  # other attributes
  fobj.write("""<H1>Other properties</H1>\n""");
  if model.pbexp is not None:
    fobj.write(model.renderAttrMarkup('pbexp',model.pbexp,tags='A',verbose="Primary beam expression: "));
    fobj.write("\n");
  fobj.write("""</BODY></HTML>\n""");

def loadModel (filename):
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

