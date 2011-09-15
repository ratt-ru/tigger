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

from PyQt4.Qt import *
from PyQt4.Qwt5 import *

import math
import  numpy
import numpy.ma
from scipy.ndimage import measurements

import Kittens.utils
import copy

_verbosity = Kittens.utils.verbosity(name="colormap");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

class IntensityMap (object):
  """An IntensityMap maps a float array into a 0...1 range."""
  def __init__ (self,dmin=None,dmax=None):
    """Constructor. An optional data range may be supplied.""";
    self.range = None;
    if dmin is not None:
      if dmax is None:
        raise TypeError,"both dmin and dmax must be specified, or neither.""";
      self.setDataRange(dmin,dmax);

  def copy (self):
    return copy.copy(self);

  def setDataRange (self,dmin,dmax):
    """Sets the data range.""";
    self.range = dmin,dmax;

  def setDataSubset (self,subset,minmax=None):
    """Sets the data subset.""";
    self.subset = subset;
    self.subset_minmax = minmax;

  def getDataSubset (self):
    return self.subset,self.subset_minmax;

  def getDataRange (self,data):
    """Returns the set data range, or uses data min/max if it is not set""";
    # use data min/max if no explicit ranges are set
    return self.range or measurements.extrema(data)[:2];

  def remap (self,data):
    """Remaps data into 0...1 range""";
    raise RuntimeError,"remap() not implemented in "+str(type(self));

class LinearIntensityMap (IntensityMap):
  """This scales data linearly between preset min and max values."""
  def remap (self,data):
    d0,d1 = self.getDataRange(data);
    dd = d1 - d0;
    if dd:
      return ((data-d0)/dd).clip(0,1);
    else:
      return numpy.zeros(data.shape,float);

class LogIntensityMap (IntensityMap):
  """This scales data linearly between preset min and max values."""
  def __init__ (self,log_cycles=6):
    self.log_cycles = log_cycles;

  def remap (self,data):
    # d0,d1 is current data range
    d0,d1 = self.getDataRange(data);
    if d0 == d1:
      return numpy.zeros(data.shape,float);
    dmax  = d1 - d0;
    data = data - d0;
    dmin = dmax*(10**(-self.log_cycles));
    # clip data to between dmin and dmax, and take log
    data = numpy.ma.log10(data.clip(dmin,dmax));
    # now rescale
    return (data - math.log10(dmin))/(math.log10(dmax) - math.log10(dmin));


class HistEqIntensityMap (IntensityMap):
  def __init__ (self,nbins=256):
    """Creates intensity mapper which uses histogram equalization.""";
    IntensityMap.__init__(self);
    self._nbins = nbins;
    self._cdf = self._bins = self.subset = None;

  def setDataSubset (self,subset,minmax=None):
    IntensityMap.setDataSubset(self,subset,minmax);
    self._bins = None;  # to recompute the CDF

  def setDataRange (self,*range):
    IntensityMap.setDataRange(self,*range);
    self._bins = None;  # to recompute the CDF

  def _computeCDF (self,data):
    """Recomputes the CDF using the current data subset and range""";
    dmin,dmax = self.getDataRange(self.subset if self.subset is not None else data);
    if dmin == dmax:
      self._cdf = None;
    else:
      dprint(1,"computing CDF for range",dmin,dmax);
      # make cumulative histogram, normalize to 0...1
      hist = measurements.histogram(self.subset if self.subset is not None else data,dmin,dmax,self._nbins);
      cdf = numpy.cumsum(hist);
      cdf = cdf/float(cdf[-1]);
      # append 0 at beginning, as left side of bin
      self._cdf = numpy.zeros(len(cdf)+1,float);
      self._cdf[1:] = cdf[...];
      # make array of bin edges
      self._bins = dmin + (dmax-dmin)*numpy.arange(self._nbins+1)/float(self._nbins);

  def remap (self,data):
    if self._bins is None:
      self._computeCDF(data);
    if self._cdf is None:
      return numpy.zeros(data.shape,float);
    values = numpy.interp(data.ravel(),self._bins,self._cdf).reshape(data.shape);
    if hasattr(data,'mask'):
      values = numpy.ma.masked_array(values,data.mask);
    return values;

class Colormap (QObject):
  """A Colormap provides operations for turning normalized float arrays into QImages. The default implementation is a linear colormap between two colors.
  """;
  def __init__ (self,name,color0=QColor("black"),color1=QColor("white"),alpha=(1,1)):
    QObject.__init__(self);
    self.name = name;
    # color is either specified as one argument (which should then be a [3,n] or [4,n] array),
    # or as two QColors orstring names.
    if isinstance(color0,(list,tuple)):
      self._rgb = numpy.array(color0);
      if self._rgb.shape[1] != 3 or self._rgb.shape[0] < 2:
        raise TypeError,"expected [N,3] (N>=2) array as first argument";
    else:
      if isinstance(color0,str):
        color0 = QColor(color0);
      if isinstance(color1,str):
        color1 = QColor(color1);
      self._rgb = numpy.array([[color0.red(),color0.green(),color0.blue()],
                                             [color1.red(),color1.green(),color1.blue()]])/255.;
    self._rgb_arg = numpy.arange(self._rgb.shape[0])/(self._rgb.shape[0]-1.0)
    # alpha array
    self._alpha = numpy.array(alpha).astype(float);
    self._alpha_arg = numpy.arange(len(alpha))/(len(alpha)-1.0);
    # background brush
    self._brush = None;

  def makeQImage (self,width,height):
    data = numpy.zeros((width,height),float);
    data[...] = (numpy.arange(width)/(width-1.))[:,numpy.newaxis];
    # make brush image -- diag background, with colormap on top
    img = QImage(width,height,QImage.Format_RGB32);
    painter = QPainter(img);
    painter.fillRect(0,0,width,height,QBrush(QColor("white")));
    painter.fillRect(0,0,width,height,QBrush(Qt.BDiagPattern));
    painter.drawImage(0,0,self.colorize(data));
    painter.end();
    return img;

  def makeQPixmap (self,width,height):
    data = numpy.zeros((width,height),float);
    data[...] = (numpy.arange(width)/(width-1.))[:,numpy.newaxis];
    # make brush image -- diag background, with colormap on top
    img = QPixmap(width,height);
    painter = QPainter(img);
    painter.fillRect(0,0,width,height,QBrush(QColor("white")));
    painter.fillRect(0,0,width,height,QBrush(Qt.BDiagPattern));
    painter.drawImage(0,0,self.colorize(data));
    painter.end();
    return img;

  def makeBrush (self,width,height):
    return QBrush(self.makeQImage(width,height));

  def colorize (self,data,alpha=None):
    """Converts normalized data (0...1) array into a QImage of the same dimensions.
    'alpha', if set, is a 0...1 array of the same size, which is mapped to the alpha channel
    (i.e. 0 for fully transparent and 1 for fully opaque).
    If data is a masked array, masked pixels will be fully transparent.""";
    # setup alpha channel
    if alpha is None:
      alpha = numpy.interp(data.ravel(),self._alpha_arg,self._alpha).reshape(data.shape);
    alpha = numpy.round(255*alpha).astype(numpy.int32).clip(0,255);
    # make RGB arrays
    rgbs = [ (numpy.interp(data.ravel(),self._rgb_arg,self._rgb[:,i]).
                reshape(data.shape)*255).round().astype(numpy.int32).clip(0,255)
             for i in range(3) ];
    # add data mask
    mask = getattr(data,'mask',None);
    if mask is not None and mask is not False:
      alpha[mask] = 0;
      for x in rgbs:
        x[mask] = 0;
    # do the deed
    return self.QARGBImage(alpha,*rgbs);
    
  def makeControlWidgets (self,parent):
    """Creates control widgets for the colormap's internal parameters.
    "parent" is a parent widget.
    Returns None if no controls are required""";
    return None;

  class QARGBImage (QImage):
    """This is a QImage which is constructed from an A,R,G,B arrays.""";
    def __init__ (self,a,r,g,b):
      nx,ny = r.shape;
      argb = (a<<24) | (r<<16) | (g<<8) | b;
      # transpose array, as it is in column-major (C order), while QImages are in row-major order
      dprint(5,"making qimage of size",nx,ny);
      self._buffer = argb.transpose().tostring();
      QImage.__init__(self,self._buffer,nx,ny,QImage.Format_ARGB32);

class ColormapWithControls (Colormap):
  """This is a base class for a colormap with controls knobs""";
  class SliderControl (QObject):
    """This class implements a slider control for a colormap""";
    def __init__ (self,name,value,minval,maxval,step,format="%s: %.1f"):
      QObject.__init__(self);
      self.name,self.value,self.minval,self.maxval,self.step,self.format = \
        name,value,minval,maxval,step,format;
      self._default = value;
      self._wlabel = None;

    def makeControlWidgets (self,parent,gridlayout,row,column):
      toprow = QWidget(parent);
      gridlayout.addWidget(toprow,row*2,column);
      top_lo = QHBoxLayout(toprow);
      top_lo.setContentsMargins(0,0,0,0);
      self._wlabel = QLabel(self.format%(self.name,self.value),toprow);
      top_lo.addWidget(self._wlabel);
      self._wreset = QToolButton(toprow);
      self._wreset.setText("reset");
      self._wreset.setToolButtonStyle(Qt.ToolButtonTextOnly);
      self._wreset.setAutoRaise(True);
      self._wreset.setEnabled(self.value != self._default);
      QObject.connect(self._wreset,SIGNAL("clicked()"),self._resetValue);
      top_lo.addWidget(self._wreset);
      self._wslider = QwtSlider(parent);
      # This works around a stupid bug in QwtSliders -- see comments on histogram zoom wheel above
      self._wslider_timer = QTimer(parent);
      self._wslider_timer.setSingleShot(True);
      self._wslider_timer.setInterval(500);
      QObject.connect(self._wslider_timer,SIGNAL("timeout()"),self.setValue);
      gridlayout.addWidget(self._wslider,row*2+1,column);
      self._wslider.setRange(self.minval,self.maxval);
      self._wslider.setStep(self.step);
      self._wslider.setValue(self.value);
      self._wslider.setTracking(False);
      QObject.connect(self._wslider,SIGNAL("valueChanged(double)"),self.setValue);
      QObject.connect(self._wslider,SIGNAL("sliderMoved(double)"),self._previewValue);

    def _resetValue (self):
      self._wslider.setValue(self._default);
      self.setValue(self._default);

    def setValue (self,value=None,notify=True):
      # only update widgets if already created
      self.value = value;
      if self._wlabel is not None:
        if value is None:
          self.value = value = self._wslider.value();
        self._wreset.setEnabled(value != self._default);
        self._wlabel.setText(self.format%(self.name,self.value));
        # stop timer if being called to finalize the change in value
        if notify:
          self._wslider_timer.stop();
          self.emit(SIGNAL("valueChanged"),self.value);
      
    def _previewValue (self,value):
      self.setValue(notify=False);
      self._wslider_timer.start(500);
      self.emit(SIGNAL("valueMoved"),self.value);
      
  def emitChange (self,*dum):
    self.emit(SIGNAL("colormapChanged"));

  def emitPreview (self,*dum):
    self.emit(SIGNAL("colormapPreviewed"));
    
  def loadConfig (self,config):
    pass;
    
  def saveConfig (self,config,save=True):
    pass;

class CubeHelixColormap (ColormapWithControls):
  """This implements the "cubehelix" colour scheme proposed by Dave Green:
  D. Green 2011, Bull. Astr. Soc. India (2011) 39, 289–295
  http://arxiv.org/pdf/1108.5083v1
  """
  def __init__(self,gamma=1,rgb=0.5,rots=-1.5,hue=1.2,name="CubeHelix"):
    ColormapWithControls.__init__(self,name);
    self.gamma  = self.SliderControl("Gamma",gamma,0,6,.1);
    self.color  = self.SliderControl("Colour",rgb,0,3,.1);
    self.cycles = self.SliderControl("Cycles",rots,-10,10,.1);
    self.hue    = self.SliderControl("Hue",hue,0,2,.1);
    
  def colorize (self,data,alpha=None):
    """Converts normalized data (0...1) array into a QImage of the same dimensions.
    'alpha', if set, is a 0...1 array of the same size, which is mapped to the alpha channel
    (i.e. 0 for fully transparent and 1 for fully opaque).
    If data is a masked array, masked pixels will be fully transparent.""";
    # setup alpha channel
    if alpha is None:
      alpha = numpy.zeros(data.shape,dtype=numpy.int32);
      alpha[...] = 255;
    else:
      alpha = numpy.round(255*alpha).astype(numpy.int32).clip(0,255);
    # make RGB arrays
    dg = data**self.gamma.value;
    a = self.hue.value*dg*(1-dg)/2;
    phi = 2*math.pi*(self.color.value/3 + self.cycles.value*data);
    cosphi = a*numpy.cos(phi);
    sinphi = a*numpy.sin(phi);
    r = dg - 0.14861*cosphi + 1.78277*sinphi;
    g = dg - 0.29227*cosphi - 0.90649*sinphi;
    b = dg + 1.97249*cosphi;
    rgbs = [ (x*255).round().astype(numpy.int32).clip(0,255) for x in r,g,b ];
    # add data mask
    mask = getattr(data,'mask',None);
    if mask is not None and mask is not False:
      alpha[mask] = 0;
      for x in rgbs:
        x[mask] = 0;
    # do the deed
    return self.QARGBImage(alpha,*rgbs);

  def makeControlWidgets (self,parent):
    """Creates control widgets for the colormap's internal parameters.
    "parent" is a parent widget.
    Returns None if no controls are required""";
    top = QWidget(parent);
    layout = QGridLayout(top);
    layout.setContentsMargins(0,0,0,0);
    for irow,icol,control in ((0,0,self.gamma),(0,1,self.color),(1,0,self.cycles),(1,1,self.hue)):
      control.makeControlWidgets(top,layout,irow,icol);
      QObject.connect(control,SIGNAL("valueChanged"),self.emitChange);
      QObject.connect(control,SIGNAL("valueMoved"),self.emitPreview);
    return top;

  def loadConfig (self,config):
    for name in "gamma","color","cycles","hue":
      control = getattr(self,name);
      value = config.getfloat("cubehelix-colourmap-%s"%name,control.value);
      control.setValue(value,notify=False);
    
  def saveConfig (self,config,save=True):
    for name in "gamma","color","cycles","hue":
      control = getattr(self,name);
      config.set("cubehelix-colourmap-%s"%name,control.value,save=save);


# instantiate "static" colormaps (i.e. those that have no internal parameters, and thus can be
# shared among images without instantiating a new Colormap object for each)
GreyscaleColormap = Colormap("Greyscale");
TransparentFuchsiaColormap = Colormap("Transparent Fuchsia",color0="fuchsia",color1="fuchsia",alpha=(0,1));

from ColormapTables import Karma
_karma_colormaps = [
    Colormap(cmap,getattr(Karma,cmap))
      for cmap in [
        "Background",
        "Heat",
        "Isophot",
        "Mousse",
        "Rainbow",
        "RGB",
        "RGB2",
        "Smooth",
        "Staircase",
        "Mirp",
        "Random" ]
  ];
  
def getColormapList ():
  """Returns list of Colormap instances."""
  
  # Some colormaps need a unique instantiation (because they have parameters)
  # For the rest, use the static objects
  return [ GreyscaleColormap,
           CubeHelixColormap(),
           TransparentFuchsiaColormap ] + _karma_colormaps;
