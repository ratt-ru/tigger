# -*- coding: utf-8 -*-
import math
import os.path
import numpy

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
  # dict of optional item attributes (key is name, value id default value)
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

  def copy (self):
    """Returns copy of object. Copies all attributes.""";
    attrs = self.optional_attrs.copy();
    attrs.update(self._extra_attrs);
    return self.__class__( *[ (attr,getattr(self,attr)) for attr in self.mandatory_attrs],**attrs);

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

  def renderAttrMarkup (self,attr,value,tags=None,verbose=None,mandatory=False):
    # render ModelItems recursively via renderMarkup() above
    if isinstance(value,ModelItem):
      return value.renderMarkup(tags,attrname=(not mandatory and attr) or None);
    # figure out enclosing tags
    tag,endtag,tags = self._resolveTags(tags,attr);
    # convert numpy types to float or complexes
    if isinstance(value,(numpy.int8,numpy.int16,numpy.int32,numpy.int64)):
      value = int(value);
    elif isinstance(value,(numpy.float32,numpy.float64,numpy.float128)):
      value = float(value);
    elif isinstance(value,(numpy.complex64,numpy.complex128,numpy.complex256)):
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
      markup += "mdlval=\"%s\">"%repr(value);
      if verbose is attr:
        markup += comment%':'.join((attr,str(value)));
      else:
        markup += comment%''.join((verbose,str(value)));
    markup += endtag;
    return markup;

def _deg_to_dms (x):
  """Converts x (in degrees) into d,m,s tuple, where d and m are ints."""
  degs,mins = divmod(x,1.);
  mins *= 60;
  mins,secs = divmod(mins,1);
  secs *= 60;
  return int(degs),int(mins),secs;

class Position (ModelItem):
  mandatory_attrs  = [ "ra","dec" ];

  @staticmethod
  def ra_hms_static (rad):
    """Returns RA as tuple of (h,m,s)""";
    # convert negative values
    while rad < 0:
        rad += 2*math.pi;
    # convert to hours
    rad *= 12.0/math.pi;
    return  _deg_to_dms(rad);

  def ra_hms (self):
    return self.ra_hms_static(self.ra);

  @staticmethod
  def dec_dms_static (rad):
    """Returns Dec as tuple of (d,m,s)""";
    if rad < 0:
        mult = -1;
        rad = abs(rad);
    else:
        mult = 1
    d,m,s = _deg_to_dms(rad*DEG);
    return (mult*(d%180),m,s);

  def dec_dms (self):
    return self.dec_dms_static(self.dec);

class Flux (ModelItem):
  mandatory_attrs  = [ "I" ];
  def rescale (self,scale):
    self.I *= scale;

class Polarization (Flux):
  mandatory_attrs  = Flux.mandatory_attrs + [ "Q","U","V" ];
  def rescale (self,scale):
    for stokes in "IQUV":
      setattr(self,stokes,getattr(self,stokes)*scale);

class PolarizationWithRM (Polarization):
  mandatory_attrs = Polarization.mandatory_attrs + [ "rm","freq0" ];

class Spectrum (ModelItem):
  """The Spectrum class is an abstract representation of spectral information. The base implementation corresponds
  to a flat spectrum.
  """;
  def normalized_intensity (self,freq):
    """Returns the normalized intensity for a given frequency, normalized to unity at the reference frequency (if any)"""
    return 1;

class SpectralIndex (Spectrum):
  mandatory_attrs  = [ "spi","freq0" ];
  def normalized_intensity (self,freq):
    """Returns the normalized intensity for a given frequency, normalized to unity at the reference frequency (if any)"""
    return (freq/self.freq0)**self.spi;

class Shape (ModelItem):
  """Abstract base class for a source's brightness distribution.
  The ex/ey/pa attributes give the overall shape of the source."""
  mandatory_attrs  = [ "ex","ey","pa" ];
  pass;

class Gaussian (Shape):
  typecode = "Gau";
  def strDesc (self,**kw):
    return """%d"x%d"@%ddeg"""%(round(self.ex*DEG*3600),round(self.ey*DEG*3600),round(self.pa*DEG));


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
