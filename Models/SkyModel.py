# -*- coding: utf-8 -*-
from ModelClasses import *
import PlotStyles

class ModelTag (ModelItem):
  mandatory_attrs = [ "name" ];
  optional_attrs = dict([ (attr,None) for attr in PlotStyles.StyleAttributes ]);

ModelTag.registerClass();

class ModelTagSet (ModelItem):
  def __init__ (self,*tags,**kws):
    ModelItem.__init__(self,**kws);
    self.tags = dict([ (tag.name,tag) for tag in tags ]);

  def add (self,tag):
    """Adds a ModelTag object to the tag set""";
    self.tags[tag.name] = tag;

  def get (self,tagname):
    """Returns ModelTag object associated with tag name, inserting a new one if not found""";
    return self.tags.setdefault(name,ModelTag(name));

  def getAll (self):
    all = self.tags.values();
    all.sort(lambda a,b:cmp(a.name,b.name));
    return all;

  def addNames (self,names):
    """Ensures that ModelTag objects are initialized for all tagnames in names""";
    for name in names:
      self.tags.setdefault(name,ModelTag(name));

  def renderMarkup (self,tag="A",attrname=None):
      """Makes a markup string corresponding to the model item.
      'tags' is the HTML tag to use.
      """;
      # opening tag
      markup = "<%s mdltype=ModelTagList "%tag;
      if attrname is not None:
        markup += "mdlattr=%s "%attrname;
      markup +=">";
      # write mandatory attributes
      for name,tt in self.tags.iteritems():
        markup += self.renderAttrMarkup(name,tt,tag="TR",mandatory=True);
      # closing tag
      markup += "</%s>"%tag;
      return markup;
ModelTagSet.registerClass();

class Source (ModelItem):
  """Source represents a model source.
  Each source has mandatory name (class str), pos (class Position) and flux (class Flux) model attributes.
  There are optional spectrum (class Spectrum) and shape (class Shape) model attributes.

  Standard Python attributes of a Source object are:
    selected: if the source is selected (e.g. in a selection widget)
    typecode: a type code. This is "pnt" if no shape is set (i.e.for a delta-function), otherwise it's the shape's typecode.
  """;
  mandatory_attrs  = [ "name","pos","flux" ];
  optional_attrs     = dict(spectrum=None,shape=None);
  allow_extra_attrs = True;

  def __init__ (self,*args,**kw):
    ModelItem.__init__(self,*args,**kw);
    self.typecode = (self.shape and self.shape.typecode) or "pnt";
    self.selected = False;

  def select (self,sel=True):
    self.selected = sel;

  def brightness (self):
    iapp = getattr(self,'Iapp',None);
    if iapp is not None:
      return iapp;
    else:
      return getattr(self.flux,'I',0.);

  def getTagNames (self):
    return [ attr for attr,val in self.getExtraAttributes() if attr[0] != "_" ];

  def getTags (self):
    return [ (attr,val) for attr,val in self.getExtraAttributes() if attr[0] != "_" ];

  class Grouping (object):
    # show_plot settings
    NoPlot = 0;
    Default = 1;
    Plot = 2;
    def __init__ (self,name,func,style=PlotStyles.DefaultPlotStyle,sources=None):
      self.name = name;
      self.style = style;
      self.func = func;
      self.total = 0;
      if sources:
        self.computeTotal(sources);
    def computeTotal (self,sources):
      self.total = len(filter(self.func,sources));
      return self.total;

Source.registerClass();

class SkyModel (ModelItem):
  optional_attrs   = dict(name=None,plotstyles={},pbexp=None,ra0=None,dec0=None);

  def __init__ (self,*sources,**kws):
    ModelItem.__init__(self,**kws);
    # "current" source (grouping "current" below is defined as that one source)
    self._current_source = None;
    self._filename = None;
    # list of loaded images associated with this model
    self._images = [];
    # setup source list
    self.setSources(sources);

  def copy (self):
    return SkyModel(*self.sources,**dict(self.getAttributes()));

  def images (self):
    """Returns list of images associated with this model""";
    return self._images;

  def setFilename (self,filename):
    self._filename = filename;

  def filename (self):
    return self._filename;

  def setCurrentSource (self,src,origin=None):
    """Changes the current source. If it has indeed changed, emits a currentSourceChanged signal. Arguments passed with the signal:
    src: the new current source.
    src0: the previously current source.
    origin: originator of changes.
    """;
    if self._current_source is not src:
      src0 = self._current_source;
      self._current_source = src;
      if self.signalsEnabled():
        self.emit("changeCurrentSource",src,src0,origin);

  def currentSource (self):
    return self._current_source;

  # Bitflags for the 'what' argument of the updated() signal below.
  # These indicate what exactly has been updated:
  UpdateSourceList  =  1;           # source list changed
  UpdateSourceContent = 2;      # source attributes have changed
  UpdateTags = 4;                     # tags have been changed
  UpdateGroupVis = 8;               # visibility of a grouping (group.style.show_list attribute) has changed
  UpdateGroupStyle = 16;          # plot style of a grouping has changed
  UpdateSelectionOnly = 32;       # (in combination with UpdateSourceContent): update only affects currently selected sources
  UpdateAll =  UpdateSourceList +UpdateSourceContent+UpdateTags+UpdateGroupVis+UpdateGroupStyle ;

  def emitUpdate (self,what=UpdateSourceContent,origin=None):
    """emits an updated() signal, indicating that the model has changed. Arguments passed through with the signal:
    what: what is updated. A combination of flags above.
    origin: originator of changes.
    """
    if self.signalsEnabled():
      self.emit("updated",what,origin);

  def emitSelection (self,origin=None):
    """emits an selected() signal, indicating that the selection has changed. Arguments passed through with the signal:
    num: number of selected sources.
    origin: originator of changes.
    """;
    self.selgroup.computeTotal(self.sources);
    if self.signalsEnabled():
      self.emit("selected",self.selgroup.total,origin);

  def emitChangeGroupingVisibility (self,group,origin=None):
    if self.signalsEnabled():
      self.emit("changeGroupingVisibility",group,origin);
      self.emitUpdate(SkyModel.UpdateGroupVis,origin);

  def emitChangeGroupingStyle (self,group,origin=None):
    if self.signalsEnabled():
      self.emit("changeGroupingStyle",group,origin);
      self.emitUpdate(SkyModel.UpdateGroupStyle,origin);


  def setSources (self,sources,origin=None):
    self.sources = list(sources);
    self.scanTags();
    self.initGroupings();

  def addSources (self,*src):
    self.sources += list(src);
    self.scanTags(src);
    self.computeGroupings();

  def scanTags (self,sources=None):
    """Populates self.tagnames with a list of tags present in sources""";
    sources = sources or self.sources;
    tagnames = set();
    for src in sources:
      tagnames.update(src.getTagNames());
    self.tagnames = list(tagnames);
    self.tagnames.sort();

  def initGroupings (self):
    # init default and "selected" groupings
    # For the default style, make sure all style fields are initialied to proper values, so that some style setting is always guaranteed.
    # Do this by sarting with the Baseline style, and applying the specified default style to it as an update.
    if 'default' in self.plotstyles:
      defstyle = PlotStyles.BaselinePlotStyle.copy();
      defstyle.update(self.plotstyles['default']);
      defstyle.apply = True;
    else:
      defstyle = self.plotstyles['default'] = PlotStyles.BaselinePlotStyle;
    self.defgroup = Source.Grouping("all sources",func=lambda src:True,sources=self.sources,style=defstyle);
    self.curgroup = Source.Grouping("current source",func=lambda src:self.currentSource() is src,sources=self.sources,
                                                        style=self.plotstyles.setdefault('current',PlotStyles.HighlightPlotStyle));
    self.selgroup = Source.Grouping("selected sources",func=lambda src:getattr(src,'selected',False),sources=self.sources,
                                                        style=self.plotstyles.setdefault('selected',PlotStyles.SelectionPlotStyle));
    # and make ordered list of groupings
    self.groupings = [ self.defgroup,self.curgroup,self.selgroup ];
    # make groupings from available source types
    self._typegroups = {};
    typecodes = list(set([src.typecode for src in self.sources]));
    typecodes.sort();
    if len(typecodes) > 1:
      for code in typecodes:
          self._typegroups[code] = group = Source.Grouping("type: %s"%code,lambda src,code=code:src.typecode==code,sources=self.sources,
                                                                            style=self.plotstyles.setdefault('type:%s'%code,PlotStyles.DefaultPlotStyle));
          self.groupings.append(group);
    # make groupings from source tags
    self._taggroups = {};
    for tag in self.tagnames:
      self._taggroups[tag] = group = Source.Grouping("tag: %s"%tag,
                                                                    lambda src,tag=tag:getattr(src,tag,None) not in [None,False],
                                                                    sources=self.sources,
                                                                    style=self.plotstyles.setdefault('tag:%s'%tag,PlotStyles.DefaultPlotStyle));
      self.groupings.append(group);

  def _remakeGroupList (self):
    self.groupings = [ self.defgroup,self.curgroup,self.selgroup ];
    typenames = self._typegroups.keys();
    typenames.sort();
    self.groupings += [ self._typegroups[name] for name in typenames ];
    self.groupings += [ self._taggroups[name] for name in self.tagnames ];

  def getTagGrouping (self,tag):
    return self._taggroups[tag];

  def getTypeGrouping (self,typename):
    return self._typegroups[typename];

  def getSourcePlotStyle (self,src):
    """Returns PlotStyle object for given source, using the styles in the model grouping.
    Returns tuple of plotstyle,label, or None,None if no source is to be plotted.
    """;
    # first grouping is the default, so init style from that
    style0 = style = self.groupings[0].style;
    # get list of styles from other matching groupings (in reverse order, excluding #0 which is default)
    styles = [ group.style for group in self.groupings[-1:0:-1] if group.func(src) ];
    # "show_plot" attribute: if at least one group is showing explicitly, show
    # else if at least one group is hiding explicitly, hide
    # else use default setting
    show = [ st.show_plot for st in styles ];
    if max(show) == PlotStyles.ShowAlways:
      show = True;
    elif min(show) == PlotStyles.ShowNot:
      show = False;
    else:
      show = bool(style0.show_plot);
    if not show:
      return None,None;
    # Override attributes in style object with non-default attributes found in each matching grouping
    # Go in reverse, so 'current' overrides 'selected' overrides types overrides tags
    for st in styles:
      if st.apply:
        # make copy-on-write, so we don't overwrite the original style object
        if style is style0:
          style = style0.copy();
        style.update(st);
    return style,PlotStyles.makeSourceLabel(style.label,src);

  def addTag (self,tag):
    if tag in self.tagnames:
      return False;
    # tags beginning with "_" are internal, not added to tagname list
    if tag[0] == "_":
      return False;
    # add to list
    self.tagnames.append(tag);
    self.tagnames.sort();
    # add to groupings
    self._taggroups[tag] = Source.Grouping("tag: %s"%tag,
                                                                  lambda src,tag=tag:getattr(src,tag,None) not in [None,False],
                                                                  sources=self.sources,
                                                                  style=self.plotstyles.setdefault('tag:%s'%tag,PlotStyles.DefaultPlotStyle));
    # reform grouping list
    self._remakeGroupList();
    return True;

  def setFieldCenter (self,ra0,dec0):
    self.ra0 = ra0;
    self.dec0 = dec0;

  def setPrimaryBeam (self,pbexp):
    self.pbexp = pbexp;
    # eval("lambda r,fq:"+self.beam_expr);

  def fieldCenter (self):
    """Returns center of field. If this is not explicitly specified in the model, uses the average position of all sources.""";
    if self.ra0 is None:
      self.ra0 = reduce(lambda x,y:x+y,[ src.pos.ra for src in self.sources ])/len(self.sources);
    if self.dec0 is None:
      self.dec0 = reduce(lambda x,y:x+y,[ src.pos.dec for src in self.sources ])/len(self.sources);
    return self.ra0,self.dec0;

SkyModel.registerClass();
