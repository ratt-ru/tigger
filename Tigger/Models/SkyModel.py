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

from ModelClasses import *
import PlotStyles

import re

from Tigger.Coordinates import angular_dist_pos_angle,DEG

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

  def get_attr (self,attr,default=None):
    return getattr(self,attr,default);

  def getTagNames (self):
    return [ attr for attr,val in self.getExtraAttributes() if attr[0] != "_" ];

  def getTags (self):
    return [ (attr,val) for attr,val in self.getExtraAttributes() if attr[0] != "_" ];

  getTag = get_attr;
  setTag = ModelItem.setAttribute;

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
  optional_attrs   = dict(name=None,plotstyles={},pbexp=None,ra0=None,dec0=None,freq0=None);
  allow_extra_attrs = True;

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

  def findSource (self,name):
    return self._src_by_name[name];

  def setSources (self,sources,origin=None,recompute_r=False):
    # if recompute_r is True, recomputes the 'r' attribute for all sources
    self.sources = list(sources);
    self._src_by_name = dict([(src.name,src) for src in self.sources]);
    if recompute_r:
      self.recomputeRadialDistance();
    self.scanTags();
    self.initGroupings();

  def addSources (self,sources,recompute_r=True):
    # if recompute_r is True, recomputes the 'r' attribute for new sources
    if recompute_r:
      self.recomputeRadialDistance(sources);
    self.setSources(list(self.sources)+list(sources));
    
  def __len__ (self):
    return len(self.sources);
    
  def __getitem__ (self,key):
    if isinstance(key,(int,slice)):
      return self.sources[key];
    elif isinstance(key,str):
      return self.findSource(key);
    else:
      raise TypeError("cannot index SkyModel with key of type %s"%str(type(key)));
    
  def __setitem__ (self,key,value):
    raise TypeError("cannot assign to items of SkyModel, use the setSources() method instead");
  
  def __iter__ (self):
    return iter(self.sources);

  def recomputeRadialDistance (self,sources=None):
    # refreshes the radial distance for a group of sources, or all sources in the model
    if (self.ra0 and self.dec0) is not None:
      for src in (sources or self.sources):
        r,pa = angular_dist_pos_angle(src.pos.ra,src.pos.dec,self.ra0,self.dec0);
        src.setAttribute('r',r);

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
      defstyle.apply = 1000;  # apply at lowest priority
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
    # get list of styles from  groupings to which this source belongs
    styles = [ group.style for group in self.groupings if group.func(src) ];
    # sort in order of priority (high apply to low apply)
    styles.sort(lambda a,b:cmp(b.apply,a.apply));
    # "show_plot" attribute: if at least one group is showing explicitly, show
    # else if at least one group is hiding explicitly, hide
    # else use default setting
    show = [ st.show_plot for st in styles ];
    if show and max(show) == PlotStyles.ShowAlways:
      show = True;
    elif show and min(show) == PlotStyles.ShowNot:
      show = False;
    else:
      show = bool(style0.show_plot);
    if not show:
      return None,None;
    # sort styles
    # Override attributes in style object with non-default attributes found in each matching grouping
    # Go in reverse, so 'current' overrides 'selected' overrides types overrides tags
    style = None;
    for st in styles:
      if st.apply:
        # make copy-on-write, so we don't overwrite the original style object
        if style is None:
          style = st.copy();
        else:
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
    self.ra0,self.dec0 = ra0,dec0;

  def setPrimaryBeam (self,pbexp):
    self.pbexp = pbexp;

  def primaryBeam (self):
    return getattr(self,'pbexp',None);

  def setRefFreq (self,freq0):
    self.freq0 = freq0;

  def refFreq (self):
    return self.freq0;

  def hasFieldCenter (self):
    return self.ra0 is not None and self.dec0 is not None;

  def fieldCenter (self):
    """Returns center of field. If this is not explicitly specified in the model, uses the average position of all sources.""";
    if self.ra0 is None:
      self.ra0 = reduce(lambda x,y:x+y,[ src.pos.ra for src in self.sources ])/len(self.sources) if self.sources else 0;
    if self.dec0 is None:
      self.dec0 = reduce(lambda x,y:x+y,[ src.pos.dec for src in self.sources ])/len(self.sources)  if self.sources else 0;
    return self.ra0,self.dec0;

  def save (self,filename,format=None, verbose=True):
    """Convenience function, saves model to file. Format may be specified explicitly, or determined from filename.""";
    import Formats
    Formats.save(self,filename,format=format, verbose=verbose);

  _re_bynumber = re.compile("^([!-])?(\\d+)?:(\\d+)?$");

  def getSourcesNear (self,ra,dec,tolerance=DEG/60):
    return [ src for src in self.sources if angular_dist_pos_angle(src.pos.ra,src.pos.dec,ra,dec)[0]<tolerance ];

  def getSourceSubset (self,selection=None):
    """Gets list of sources matching the given selection string (if None, then all sources are returned.)""";
    if not selection or selection.lower() == "all":
      return self.sources;
    # sort by brightness
    srclist0 = sorted(self.sources,lambda a,b:cmp(b.brightness(),a.brightness()));
    all = set([src.name for src in srclist0]);
    srcs = set();
    for ispec,spec in enumerate(re.split("\s+|,",selection)):
      spec = spec.strip();
      if spec:
        # if first spec is a negation, then implictly select all sources first
        if not ispec and spec[0] in "!-":
          srcs = all;
        if spec.lower() == "all":
          srcs = all;
        elif self._re_bynumber.match(spec):
          negate,start,end = self._re_bynumber.match(spec).groups();
          sl = slice(int(start) if start else None,int(end) if end else None);
          if negate:
            srcs.difference_update([ src.name for src in srclist0[sl]]);
          else:
            srcs.update([ src.name for src in srclist0[sl]]);
        elif spec.startswith("-=") or spec.startswith("!="):
          srcs.difference_update([ src.name for src in srclist0 if getattr(src,spec[2:],None) ]);
        elif spec.startswith("="):
          srcs.update([ src.name for src in srclist0 if getattr(src,spec[1:],None) ]);
        elif spec.startswith("-")  or spec.startswith("!"):
          srcs.discard(spec[1:]);
        else:
          srcs.add(spec);
    # make list
    return [ src for src in srclist0 if src.name in srcs ];


SkyModel.registerClass();
