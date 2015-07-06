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

import math
import os.path
import numpy
import copy

from Tigger import startup_dprint
startup_dprint(1,"starting ModelClasses");

DEG = 180/math.pi;

AtomicTypes = dict(bool=bool,int=int,float=float,complex=complex,str=str,list=list,tuple=tuple,dict=dict,NoneType=lambda x:None);

class ModelItem (object):
  """ModelItem is a base class for all model items. ModelItem provides functions
  for saving, loading, and initializing items, using class attributes that describe the
  item's structure.
  A ModelItem has a number of named attributes (both mandatory and optional), which are
    sufficient to fully describe the item.
  A ModelItem is constructed by specifying its attribute values. Mandatory attributes are
    passed as positional arguments to the constructor, while optional attributes are passed
    as keyword arguments.
  'mandatory_attrs' is a class data member that provides a list of mandatory attributes.
  'optional_attrs' is a class data member that provides a dict of optional attributes and their
      default values (i.e. their value when missing). Subclasses are expected to redefine these
      attributes.
  """;

  # list of mandatory item attributes
  mandatory_attrs  = [];
  # dict of optional item attributes (key is name, value is default value)
  optional_attrs   = {};
  # True is arbitrary extra attributes are allowed
  allow_extra_attrs = False;
  # dict of rendertags for attributes. Default is to render ModelItems with the "A" tag,
  # and atomic attributes with the "TD" tag
  attr_rendertag   = {};
  # dict of verbosities for attributes. If an entry is present for a given attribute, then
  # the attribute's text representation will be rendered within its tags
  attr_verbose     = {};

  def __init__ (self,*args,**kws):
    """The default ModelItem constructor treats its positional arguments as a list of
    mandatory attributes, and its keyword arguments as optional attributes""";
    # check for argument errors
    if len(args) < len(self.mandatory_attrs):
      raise TypeError,"too few arguments in constructor of "+self.__class__.__name__;
    if len(args) > len(self.mandatory_attrs):
      raise TypeError,"too many arguments in constructor of "+self.__class__.__name__;
    # set mandatory attributes from argument list
    for attr,value in zip(self.mandatory_attrs,args):
      if not isinstance(value,AllowedTypesTuple):
        raise TypeError,"invalid type %s for attribute %s (class %s)"%(type(value).__name__,attr,self.__class__.__name__);
      setattr(self,attr,value);
    # set optional attributes from keywords
    for kw,default in self.optional_attrs.iteritems():
      value = kws.pop(kw,default);
      if not isinstance(value,AllowedTypesTuple):
        raise TypeError,"invalid type %s for attribute %s (class %s)"%(type(value).__name__,kw,self.__class__.__name__);
      setattr(self,kw,value);
    # set extra attributes, if any are left
    self._extra_attrs = set();
    if self.allow_extra_attrs:
      for kw,value in kws.iteritems():
        if not isinstance(value,AllowedTypesTuple):
          raise TypeError,"invalid type %s for attribute %s (class %s)"%(type(value).__name__,kw,self.__class__.__name__);
        self.setAttribute(kw,value);
    elif kws:
        raise TypeError,"unknown parameters %s in constructor of %s"%(','.join(kws.keys()),self.__class__.__name__);
    # other init
    self._signaller = None;
    self._connections = set();

  def enableSignals (self):
    """Enables Qt signals for this object.""";
    import PyQt4.Qt;
    self._signaller = PyQt4.Qt.QObject();

  def signalsEnabled (self):
    return bool(self._signaller);

  def connect (self,signal_name,receiver,reconnect=False):
    """Connects SIGNAL from object to specified receiver slot. If reconnect is True, allows duplicate connections.""";
    if not self._signaller:
      raise RuntimeError,"ModelItem.connect() called before enableSignals()";
    import PyQt4.Qt;
    if reconnect or (signal_name,receiver) not in self._connections:
      self._connections.add((signal_name,receiver));
      PyQt4.Qt.QObject.connect(self._signaller,PyQt4.Qt.SIGNAL(signal_name),receiver);

  def emit (self,signal_name,*args):
    """Emits named SIGNAL from this object .""";
    if not self._signaller:
      raise RuntimeError,"ModelItem.emit() called before enableSignals()";
    import PyQt4.Qt;
    self._signaller.emit(PyQt4.Qt.SIGNAL(signal_name),*args);

  def registerClass (classobj):
    if not isinstance(classobj,type):
      raise TypeError,"registering invalid class object: %s"%classobj;
    globals()[classobj.__name__] = classobj;
    AllowedTypes[classobj.__name__] = classobj;
    AllowedTypesTuple = tuple(AllowedTypes.itervalues());
  registerClass = classmethod(registerClass);

  def setAttribute (self,attr,value):
    if attr not in self.mandatory_attrs and attr not in self.optional_attrs:
      self._extra_attrs.add(attr);
    setattr(self,attr,value);

  def removeAttribute (self,attr):
    if hasattr(self,attr):
      delattr(self,attr);
    self._extra_attrs.discard(attr);

  def getExtraAttributes (self):
    """Returns list of extra attributes, as (attr,value) tuples""";
    return  [ (attr,getattr(self,attr)) for attr in self._extra_attrs ];

  def getAttributes (self):
    """Returns list of all attributes (mandatory+optional+extra), as (attr,value) tuples""";
    attrs = [ (attr,getattr(self,attr)) for attr in self.mandatory_attrs ];
    for attr,default in self.optional_attrs.iteritems():
      val = getattr(self,attr,default);
      if val != default:
        attrs.append((attr,val));
    attrs += [ (attr,getattr(self,attr)) for attr in self._extra_attrs ];
    return attrs;

  def __copy__ (self):
    """Returns copy of object. Copies all attributes.""";
    attrs = self.optional_attrs.copy();
    attrs.update(self.getExtraAttributes());
    return self.__class__( *[ getattr(self,attr) for attr in self.mandatory_attrs],**attrs);
  
  def __deepcopy__ (self,memodict):
    """Returns copy of object. Copies all attributes.""";
    attrs = self.optional_attrs.copy();
    attrs.update(self.getExtraAttributes());
    attrs = copy.deepcopy(attrs,memodict);
    return self.__class__( *[ copy.deepcopy(getattr(self,attr),memodict) for attr in self.mandatory_attrs],**attrs);

  def copy (self,deep=True):
    if deep:
      return copy.deepcopy(self);
    else:
      return __copy__(self);

  def strAttributes (self,sep=",",label=True,
                                float_format="%.2g",complex_format="%.2g%+.2gj"):
    """Renders attributes as string. Child classes may redefine this to make a better string representation.
    If label=True, uses "attrname=value", else uses "value".
    'sep' specifies a separator.
    """;
    fields = [];
    for attr,val in self.getAttributes():
      ss = (label and "%s="%attr) or "";
      if isinstance(val,(float,int)):
        ss += float_format%val;
      elif isinstance(val,complex):
        ss += complex_format%val;
      else:
        ss += str(val);
      fields.append(ss);
    return sep.join(fields);

  def strDesc (self,**kw):
    """Returns string describing the object, used in GUIs and such. Default implementation calls strAttributes()."""
    return strAttributes(**kw);

  def _resolveTags (self,tags,attr=None):
    """helper function called from renderMarkup() and renderAttrMarkup() below to
    figure out which HTML tags to enclose a value in. Return value is tuple of (tag,endtag,rem_tags), where
    tag is the HTML tag to use (or None for default, usually "A"), endtag is the closing tag (including <> and whitespace, if any),
    and rem_tags is to be passed to child items' resolveMarkup() """;
    # figure out enclosing tag
    if not tags:
      tag,tags = None,None;  # use default
    elif isinstance(tags,str):
      tag,tags = tags,None;           # one tag supplied, use that here and use defaults for sub-items
    elif isinstance(tags,(list,tuple)):
      tag,tags = tags[0],tags[1:];   # stack of tags supplied: use first here, pass rest to sub-items
    else:
      raise ValueError,"invalid 'tags' parameter of type "+str(type(tags));
    # if tag is None, use default
    tag = tag or self.attr_rendertag.get(attr,None) or "A";
    if tag.endswith('\n'):
      tag = tag[:-1];
      endtag = "</%s>\n"%tag;
    else:
      endtag = "</%s> "%tag;
    return tag,endtag,tags;

  def renderMarkup (self,tags=None,attrname=None):
    """Makes a markup string corresponding to the model item.
    'tags' is the HTML tag to use.
    If 'verbose' is not None, a text representation of the item (using str()) will be included
    as HTML text between the opening and closing tags.
    """;
    tag,endtag,tags = self._resolveTags(tags,attrname);
    # opening tag
    markup = "<%s mdltype=%s "%(tag,type(self).__name__);
    if attrname is not None:
      markup += "mdlattr=\"%s\" "%attrname;
    markup +=">";
    # render attrname as comment
    if attrname:
      if tag == "TR":
        markup += "<TD bgcolor=yellow>%s</TD>"%attrname;
      else:
        markup += "<A>%s:</A> "%attrname;
    # write mandatory attributes
    for attr in self.mandatory_attrs:
      markup += self.renderAttrMarkup(attr,getattr(self,attr),tags=tags,mandatory=True);
    # write optional attributes only wheh non-default
    for attr,default in sorted(self.optional_attrs.iteritems()):
      val = getattr(self,attr,default);
      if val != default:
        markup += self.renderAttrMarkup(attr,val,tags=tags);
    # write extra attributes
    for attr in self._extra_attrs:
      markup += self.renderAttrMarkup(attr,getattr(self,attr),tags=tags);
    # closing tag
    markup += endtag;
    return markup;
    
  numpy_int_types = tuple([
      getattr(numpy,"%s%d"%(t,d)) for t in "int","uint" for d in 8,16,32,64 
      if hasattr(numpy,"%s%d"%(t,d))
    ]);
  numpy_float_types = tuple([
      getattr(numpy,"float%d"%d) for d in 32,64,96,128 
      if hasattr(numpy,"float%d"%d)
    ]);

  def renderAttrMarkup (self,attr,value,tags=None,verbose=None,mandatory=False):
    # render ModelItems recursively via renderMarkup() above
    if isinstance(value,ModelItem):
      return value.renderMarkup(tags,attrname=(not mandatory and attr) or None);
    # figure out enclosing tags
    tag,endtag,tags = self._resolveTags(tags,attr);
    # convert numpy types to float or complexes
    if isinstance(value,self.numpy_int_types):
      value = int(value);
    elif isinstance(value,self.numpy_float_types):
      value = float(value);
    elif numpy.iscomplexobj(value):
      value = complex(value);
    # render opening tags
    markup = "<%s mdltype=%s "%(tag,type(value).__name__);
    if not mandatory:
      markup += "mdlattr=\"%s\" "%attr;
    # if rendering table row, use TD to render comments
    if verbose is None:
      verbose = attr; # and self.attr_verbose.get(attr);
    if tag == "TR":
      comment = "<TD bgcolor=yellow>%s</TD>";
    else:
      comment = "<A>%s</A> ";
    # render lists or tuples iteratively
    if isinstance(value,(list,tuple)):
      markup += ">";
      if verbose:
        markup += comment%(verbose+":");
      for i,item in enumerate(value):
        markup += self.renderAttrMarkup(str(i),item,mandatory=True,tags=tags);
    # render dicts iteratively
    elif isinstance(value,dict):
      markup += ">";
      if verbose:
        markup += comment%(verbose+":");
      for key,item in sorted(value.iteritems()):
        markup += self.renderAttrMarkup(key,item,tags=tags);
    # render everything else inline
    else:
      if isinstance(value,str):
        markup += "mdlval=\"'%s'\">"%value.replace("\"","\\\"").replace("'","\\'");
      else:
        markup += "mdlval=\"%s\">"%repr(value);
      if verbose is attr:
        markup += comment%':'.join((attr,str(value)));
      else:
        markup += comment%''.join((verbose,str(value)));
    markup += endtag;
    return markup;

def _deg_to_dms (x,prec=0.01):
  """Converts x (in degrees) into d,m,s tuple, where d and m are ints.
  prec gives the precision, in arcseconds."""
  mins,secs = divmod(round(x*3600/prec)*prec,60);
  mins = int(mins);
  degs,mins = divmod(mins,60);
  return degs,mins,secs;

class Position (ModelItem):
  mandatory_attrs  = [ "ra","dec" ];
  optional_attrs = dict(ra_err=None,dec_err=None);

  @staticmethod
  def ra_hms_static (rad,scale=12,prec=0.01):
    """Returns RA as tuple of (h,m,s)""";
    # convert negative values
    while rad < 0:
        rad += 2*math.pi;
    # convert to hours
    rad *= scale/math.pi;
    return  _deg_to_dms(rad,prec);

  def ra_hms (self,prec=0.01):
    return self.ra_hms_static(self.ra,scale=12,prec=prec);

  def ra_dms (self,prec=0.01):
    return self.ra_hms_static(self.ra,scale=180,prec=prec);

  @staticmethod
  def dec_dms_static (rad,prec=0.01):
    return Position.dec_sdms_static(rad,prec)[1:];
  
  @staticmethod
  def dec_sdms_static (rad,prec=0.01):
    """Returns Dec as tuple of (sign,d,m,s). Sign is "+" or "-".""";
    sign = "-" if rad<0 else "+";
    d,m,s = _deg_to_dms(abs(rad)*DEG,prec);
    return (sign,d,m,s);

  def dec_sdms (self,prec=0.01):
    return self.dec_sdms_static(self.dec,prec);

class Flux (ModelItem):
  mandatory_attrs  = [ "I" ];
  optional_attrs = dict(I_err=None);
  def rescale (self,scale):
    self.I *= scale;

class Polarization (Flux):
  mandatory_attrs  = Flux.mandatory_attrs + [ "Q","U","V" ];
  optional_attrs = dict(I_err=None,Q_err=None,U_err=None,V_err=None);
  def rescale (self,scale):
    for stokes in "IQUV":
      setattr(self,stokes,getattr(self,stokes)*scale);

class PolarizationWithRM (Polarization):
  mandatory_attrs = Polarization.mandatory_attrs + [ "rm","freq0" ];
  optional_attrs = dict(Polarization.optional_attrs,rm_err=None)

class Spectrum (ModelItem):
  """The Spectrum class is an abstract representation of spectral information. The base implementation corresponds
  to a flat spectrum.
  """;
  def normalized_intensity (self,freq):
    """Returns the normalized intensity for a given frequency,normalized to unity at the reference frequency (if any)"""
    return 1;

class SpectralIndex (Spectrum):
  mandatory_attrs  = [ "spi","freq0" ];
  optional_attrs = dict(spi_err=None);
  def normalized_intensity (self,freq):
    """Returns the normalized intensity for a given frequency, normalized to unity at the reference frequency (if any)"""
    if isinstance(self.spi,(list,tuple)):
      spi = self.spi[0];
      logfreq = numpy.log(freq/self.freq0);
      for i,x in enumerate(self.spi[1:]):
        spi = spi + x*(logfreq**(i+1));
    else:
      spi = self.spi;
    return (freq/self.freq0)**spi;

class Shape (ModelItem):
  """Abstract base class for a source's brightness distribution.
  The ex/ey/pa attributes give the overall shape of the source."""
  mandatory_attrs  = [ "ex","ey","pa" ];
  optional_attrs = dict(ex_err=None,ey_err=None,pa_err=None);
  def getShape (self):
    return self.ex,self.ey,self.pa
  def getShapeErr (self):
    err = [ getattr(self,a+'_err',None) for a in self.mandatory_attrs ] 
    if all([ a is None for a in err ]):
      return None
    return tuple(err)

class Gaussian (Shape):
  typecode = "Gau";
  def strDesc (self,delimiters=('"',"x","@","deg"),**kw):
    return """%.2g%s%s%.2g%s%s%d%s"""%(self.ex*DEG*3600,delimiters[0],delimiters[1],self.ey*DEG*3600,delimiters[0],
                                       delimiters[2],round(self.pa*DEG),delimiters[3]);
  def strDescErr (self,delimiters=('"',"x","@","deg"),**kw):
    err = self.getShapeErr();
    return err and """%.2g%s%s%.2g%s%s%d%s"""%(err[0]*DEG*3600,delimiters[0],delimiters[1],err[1]*DEG*3600,delimiters[0],
                                       delimiters[2],round(err[2]*DEG),delimiters[3]);


class FITSImage (Shape):
  typecode = "FITS";
  mandatory_attrs  = Shape.mandatory_attrs + [ "filename","nx","ny" ];
  optional_attrs = dict(pad=2);
  def strDesc (self,**kw):
    return """%s %dx%d"""%(os.path.basename(self.filename),self.nx,self.ny);

startup_dprint(1,"end of class defs");

# populate dict of AllowedTypes with all classes defined so far
globs = list(globals().iteritems());

AllowedTypes = dict(AtomicTypes.iteritems());
AllowedTypes['NoneType'] = type(None);  # this must be a type, otherwise isinstance() doesn't work
for name,val in globs:
  if isinstance(val,type):
    AllowedTypes[name] = val;
AllowedTypesTuple = tuple(AllowedTypes.itervalues());

startup_dprint(1,"end of ModelClasses");
