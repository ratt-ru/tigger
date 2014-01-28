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

import ModelClasses
from PyQt4.Qt import *
import math

# string used to indicate default value of an attribute
DefaultValue = "default";
# string used to indicate "none" value of an attribute
NoneValue = "none";

# definitive list of style attributes
StyleAttributes = [ "symbol","symbol_color","symbol_size","symbol_linewidth","label","label_color","label_size" ];

# dict of attribute labels (i.e. for menus, column headings and such)
StyleAttributeLabels = dict(symbol="symbol",symbol_color="color",symbol_size="size",symbol_linewidth="line width",
                                           label="label",label_color="color",label_size="size");
# dict of attribute types. Any attribute not in this dict is of type str.
StyleAttributeTypes = dict(symbol_size=int,symbol_linewidth=int,label_size=int);

# list of known colors
ColorList = [ "black","blue","lightblue","green","lightgreen","cyan","red","orange red","purple","magenta","yellow","white" ];
DefaultColor = "black";
# Ignore this (non-existent) attribute on non-X11 platforms like the Mac
try:
    QColor.setAllowX11ColorNames(True);
except AttributeError:
    pass

# dict and method to pick a contrasting color (i.e. suitable as background for specified color)
ContrastColor = dict(white="#404040",yellow="#404040");
DefaultContrastColor = "#B0B0B0";

def getContrastColor (color):
  return ContrastColor.get(color,DefaultContrastColor);


# dict of possible user settings for each attribute
StyleAttributeOptions = dict(
  symbol = [ DefaultValue,NoneValue,"cross","plus","dot","circle","square","diamond" ],
  symbol_color =  [ DefaultValue ] + ColorList,
  label = [ DefaultValue,NoneValue,"%N","%N %BJy","%N %BJy r=%R'" ],
  label_color =  [ DefaultValue ] + ColorList,
  label_size = [ DefaultValue,6,8,10,12,14 ],
);

# constants for the show_list and show_plot attributes
ShowNot = 0;
ShowDefault = 1;
ShowAlways = 2;


DefaultPlotAttrs = dict(symbol=None,symbol_color=DefaultColor,symbol_size=5,symbol_linewidth=0,
                        label=None,label_color=DefaultColor,label_size=10,
                        show_list=ShowDefault,show_plot=ShowDefault,apply=0);

class PlotStyle (ModelClasses.ModelItem):
  optional_attrs = DefaultPlotAttrs;

  def copy (self):
    return PlotStyle(**dict([(attr,getattr(self,attr,default)) for attr,default in DefaultPlotAttrs.iteritems()]))

  def update (self,other):
    for attr in DefaultPlotAttrs.iterkeys():
      val = getattr(other,attr,None);
      if val is not None and val != DefaultValue:
        setattr(self,attr,val);

PlotStyle.registerClass();

# Default plot style. This must define everything! (I.e. no DefaultValue elements allowed.)
BaselinePlotStyle = PlotStyle(symbol="plus",symbol_color="yellow",symbol_size=2,symbol_linewidth=0,
                                            label=NoneValue,label_color="blue",label_size=6,
                                            show_list=ShowAlways,show_plot=ShowAlways,apply=1000);

SelectionPlotStyle = PlotStyle(symbol=DefaultValue,symbol_color="cyan",symbol_size=DefaultValue,symbol_linewidth=DefaultValue,
                                            label="%N",label_color="green",label_size=DefaultValue,
                                            show_list=ShowAlways,show_plot=ShowAlways,apply=-1);

HighlightPlotStyle = PlotStyle(symbol=DefaultValue,symbol_color="red",symbol_size=DefaultValue,symbol_linewidth=DefaultValue,
                                            label="%N %BJy",label_color="red",label_size=12,
                                            show_list=ShowAlways,show_plot=ShowAlways,apply=-2);

DefaultPlotStyle = PlotStyle(symbol=DefaultValue,symbol_color=DefaultValue,symbol_size=DefaultValue,symbol_linewidth=DefaultValue,
                                            label=DefaultValue,label_color=DefaultValue,label_size=DefaultValue,
                                            show_list=ShowDefault,show_plot=ShowDefault,apply=1000);

# cache of precompiled labels
_compiled_labels = {};

# label replacements
_label_keys = {   "%N": lambda src:src.name,
                            "%B": lambda src:"%.2g"%src.brightness(),
                            "%R": lambda src:(hasattr(src,'r') and "%.2g"%(src.r/math.pi*180*60)) or "",
                            "%T": lambda src:src.typecode,
                            "%I": lambda src:"%.2g"%getattr(src.flux,'I',0),
                            "%Q": lambda src:"%.2g"%getattr(src.flux,'Q',0),
                            "%U": lambda src:"%.2g"%getattr(src.flux,'U',0),
                            "%V": lambda src:"%.2g"%getattr(src.flux,'V',0),
};

def makeSourceLabel (label,src):
  if label == NoneValue or label is None:
    return "";
  global _label_keys;
  lbl = label;
  for key,func in _label_keys.iteritems():
    if lbl.find(key) >= 0:
      lbl = lbl.replace(key,func(src));
  return lbl;
