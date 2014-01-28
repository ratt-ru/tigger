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
import os.path
import re
import time
import numpy

import Kittens.utils

from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

_verbosity = Kittens.utils.verbosity(name="plot");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Tigger import pixmaps,Config,ConfigFile
from Tigger.Models import ModelClasses,PlotStyles
from Tigger import Coordinates
from Tigger.Coordinates import Projection
from Tigger.Models.SkyModel import SkyModel
from Tigger.Widgets import TiggerPlotCurve,TiggerPlotMarker
from Tigger.Plot import MouseModes

# plot Z depths for various classes of objects
Z_Image = 1000;
Z_Grid = 9000;
Z_Source = 10000;
Z_SelectedSource = 10001;
Z_CurrentSource = 10002;
Z_Markup = 10010;

# default stepping of grid circles
DefaultGridStep_ArcSec = 30*60;

DEG = math.pi/180;

class SourceMarker (object):
  """SourceMarker implements a source marker corresponding to a SkyModel source.
  The base class implements a marker at the centre.
  """;
  QwtSymbolStyles = dict( none=QwtSymbol.NoSymbol,
                                        cross=QwtSymbol.XCross,
                                        plus=QwtSymbol.Cross,
                                        dot=QwtSymbol.Ellipse,
                                        circle=QwtSymbol.Ellipse,
                                        square=QwtSymbol.Rect,
                                        diamond=QwtSymbol.Diamond,
                                        triangle=QwtSymbol.Triangle,
                                        dtriangle=QwtSymbol.DTriangle,
                                        utriangle=QwtSymbol.UTriangle,
                                        ltriangle=QwtSymbol.LTriangle,
                                        rtriangle=QwtSymbol.RTriangle,
                                        hline=QwtSymbol.HLine,
                                        vline=QwtSymbol.VLine,
                                        star1=QwtSymbol.Star1,
                                        star2=QwtSymbol.Star2,
                                        hexagon=QwtSymbol.Hexagon );

  def __init__ (self,src,l,m,size,model):
    self.src = src;
    self._lm,self._size = (l,m),size;
    self.plotmarker = TiggerPlotMarker();
    self.plotmarker.setValue(l,m);
    self._symbol = QwtSymbol();
    self._font = QApplication.font();
    self._model = model;
    self.resetStyle();

  def lm (self):
    """Returns plot coordinates of marker, as an l,m tuple""";
    return self._lm;

  def lmQPointF (self):
    """Returns plot coordinates of marker, as a QPointF""";
    return self.plotmarker.value();

  def source (self):
    """Returns model source associated with marker""";
    return self.src;

  def attach (self,plot):
    """Attaches to plot""";
    self.plotmarker.attach(plot);

  def isVisible (self):
    return self.plotmarker.isVisible();

  def setZ (self,z):
    self.plotmarker.setZ(z);

  def resetStyle (self):
    """Sets the source style based on current model settings"""
    self.style,self.label = self._model.getSourcePlotStyle(self.src);
    self._selected = getattr(self.src,'selected',False);
    # setup marker components
    self._setupMarker(self.style,self.label);
    # setup depth
    if self._model.currentSource() is self.src:
      self.setZ(Z_CurrentSource);
    elif self._selected:
      self.setZ(Z_SelectedSource);
    else:
      self.setZ(Z_Source);

  def _setupMarker (self,style,label):
    """Sets up the plot marker (self.plotmarker) based on style object and label string.
    If style=None, makes marker invisible.""";
    if not style:
      self.plotmarker.setVisible(False);
      return;
    self.plotmarker.setVisible(True);
    self._symbol.setStyle(self.QwtSymbolStyles.get(style.symbol,QwtSymbol.Cross));
    self._font.setPointSize(style.label_size);
    symbol_color = QColor(style.symbol_color);
    label_color = QColor(style.label_color);
    # dots have a fixed size
    if style.symbol == "dot":
      self._symbol.setSize(2);
    else:
      self._symbol.setSize(self._size);
    self._symbol.setPen(QPen(symbol_color,style.symbol_linewidth));
    self._symbol.setBrush(QBrush(Qt.NoBrush));
    lab_pen = QPen(Qt.NoPen);
    lab_brush = QBrush(Qt.NoBrush);
    self._label = label or "";
    self.plotmarker.setSymbol(self._symbol);
    txt = QwtText(self._label);
    txt.setColor(label_color);
    txt.setFont(self._font);
    txt.setBackgroundPen(lab_pen);
    txt.setBackgroundBrush(lab_brush);
    self.plotmarker.setLabel(txt);
    self.plotmarker.setLabelAlignment(Qt.AlignBottom|Qt.AlignRight);

  def checkSelected (self):
    """Checks the src.selected attribute, resets marker if it has changed.
    Returns True is something has changed.""";
    sel = getattr(self.src,'selected',False);
    if self._selected == sel:
      return False;
    self._selected = sel;
    self.resetStyle();
    return True;

  def changeStyle (self,group):
    if group.func(self.src):
      self.resetStyle();
      return True;
    return False;

class ImageSourceMarker (SourceMarker):
  """This auguments SourceMarker with a FITS image."""
  def __init__ (self,src,l,m,size,model,imgman):
    # load image if needed
    self.imgman = imgman;
    dprint(2,"loading Image source",src.shape.filename);
    self.imagecon = imgman.loadImage(src.shape.filename,duplicate=False,to_top=False,model=src.name);
    # this will return None if the image fails to load, in which case we still produce a marker,
    # but nothing else
    if self.imagecon:
      self.imagecon.setMarkersZ(Z_Source);
    # init base class
    SourceMarker.__init__(self,src,l,m,size,model);

  def attach (self,plot):
    SourceMarker.attach(self,plot);
    if self.imagecon:
      self.imagecon.attachToPlot(plot);

  def _setupMarker (self,style,label):
    SourceMarker._setupMarker(self,style,label);
    if not style:
      return;
    symbol_color = QColor(style.symbol_color);
    label_color = QColor(style.label_color);
    if self.imagecon:
      self.imagecon.setPlotBorderStyle(border_color=symbol_color,label_color=label_color);

def makeSourceMarker (src,l,m,size,model,imgman):
  """Creates source marker based on source type""";
  shape = getattr(src,'shape',None);
#  print type(shape),isinstance(shape,ModelClasses.FITSImage),shape.__class__,ModelClasses.FITSImage;
  if isinstance(shape,ModelClasses.FITSImage):
    return ImageSourceMarker(src,l,m,size,model,imgman);
  else:
    return SourceMarker(src,l,m,size,model);

def makeDualColorPen (color1,color2,width=3):
  c1,c2 = QColor(color1).rgb(),QColor(color2).rgb();
  texture = QImage(2,2,QImage.Format_RGB32);
  texture.setPixel(0,0,c1);
  texture.setPixel(1,1,c1);
  texture.setPixel(0,1,c2);
  texture.setPixel(1,0,c2);
  return QPen(QBrush(texture),width);

class ToolDialog (QDialog):
  def __init__ (self,parent,configname,menuname,show_shortcut=None):
    QDialog.__init__(self,parent);
    self.setModal(False);
    self.setFocusPolicy(Qt.NoFocus);
    self.hide();
    self._configname = configname;
    self._geometry = None;
    # make hide/show qaction
    self._qa_show = qa = QAction("Show %s"%menuname.replace("&","&&"),self);
    if show_shortcut:
      qa.setShortcut(show_shortcut);
    qa.setCheckable(True);
    qa.setChecked(Config.getbool("%s-show"%configname,False));
    qa.setVisible(False);
    qa.setToolTip("""<P>The quick zoom & cross-sections window shows a zoom of the current image area
      under the mose pointer, and X/Y cross-sections through that area.</P>""");
    QObject.connect(qa,SIGNAL("triggered(bool)"),self.setVisible);
    self._closing = False;
    self._write_config = curry(Config.set,"%s-show"%configname);
    QObject.connect(qa,SIGNAL("triggered(bool)"),self._write_config);
    QObject.connect(self,SIGNAL("isVisible"),qa.setChecked);

  def getShowQAction (self):
    return self._qa_show;

  def makeAvailable (self,available=True):
    """Makes the tool available (or unavailable)-- shows/hides the "show" control, and shows/hides the dialog according to this control.""";
    self._qa_show.setVisible(available);
    self.setVisible(self._qa_show.isChecked() if available else False);

  def initGeometry (self):
    x0 = Config.getint('%s-x0'%self._configname,0);
    y0 = Config.getint('%s-y0'%self._configname,0);
    w = Config.getint('%s-width'%self._configname,0);
    h = Config.getint('%s-height'%self._configname,0);
    if w and h:
      self.resize(w,h);
      self.move(x0,y0);
      return True;
    return False;

  def _saveGeometry (self):
    Config.set('%s-x0'%self._configname,self.pos().x());
    Config.set('%s-y0'%self._configname,self.pos().y());
    Config.set('%s-width'%self._configname,self.width());
    Config.set('%s-height'%self._configname,self.height());

  def close (self):
    self._closing = True;
    QDialog.close(self);

  def closeEvent (self,event):
    QDialog.closeEvent(self,event);
    if not self._closing:
      self._write_config(False);

  def moveEvent (self,event):
    self._saveGeometry();
    QDialog.moveEvent(self,event);

  def resizeEvent (self,event):
    self._saveGeometry();
    QDialog.resizeEvent(self,event);

  def setVisible (self,visible,emit=True):
    if not visible:
      self._geometry = self.geometry();
    else:
      if self._geometry:
        self.setGeometry(self._geometry);
    if emit:
      self.emit(SIGNAL("isVisible"),visible);
    QDialog.setVisible(self,visible);

class LiveImageZoom (ToolDialog):
  def __init__ (self,parent,radius=10,factor=12):
    ToolDialog.__init__(self,parent,configname="livezoom",menuname="live zoom & cross-sections",show_shortcut=Qt.Key_F2);
    self.setWindowTitle("Zoom & Cross-sections");
    radius = Config.getint("livezoom-radius",radius);
    # add plots
    self._lo0 = lo0 = QVBoxLayout(self);
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo1.setSpacing(0);
    lo0.addLayout(lo1);
    # control checkboxes
    self._showzoom = QCheckBox("show zoom",self);
    self._showcs = QCheckBox("show cross-sections",self);
    self._showzoom.setChecked(True);
    self._showcs.setChecked(True);
    QObject.connect(self._showzoom,SIGNAL("toggled(bool)"),self._showZoom);
    QObject.connect(self._showcs,SIGNAL("toggled(bool)"),self._showCrossSections);
    lo1.addWidget(self._showzoom,0);
    lo1.addSpacing(5);
    lo1.addWidget(self._showcs,0);
    lo1.addStretch(1);
    self._smaller = QToolButton(self);
    self._smaller.setIcon(pixmaps.window_smaller.icon());
    QObject.connect(self._smaller,SIGNAL("clicked()"),self._shrink);
    self._larger = QToolButton(self);
    self._larger.setIcon(pixmaps.window_larger.icon());
    QObject.connect(self._larger,SIGNAL("clicked()"),self._enlarge);
    lo1.addWidget(self._smaller);
    lo1.addWidget(self._larger);
    self._has_zoom = self._has_xcs = self._has_ycs = False;
    # setup zoom plot
    font = QApplication.font();
    self._zoomplot = QwtPlot(self);
#    self._zoomplot.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed);
    self._zoomplot.setMargin(0);
    self._zoomplot.setTitle("");
    axes = {    QwtPlot.xBottom: "X pixel coordinate",
                        QwtPlot.yLeft:"Y pixel coordinate",
                        QwtPlot.xTop:"X cross-section value",
                        QwtPlot.yRight:"Y cross-section value" };
    for axis,title in axes.iteritems():
      self._zoomplot.enableAxis(True);
      self._zoomplot.setAxisScale(axis,0,1);
      self._zoomplot.setAxisFont(axis,font);
      self._zoomplot.setAxisMaxMajor(axis,3);
      self._zoomplot.axisWidget(axis).setMinBorderDist(16,16);
      self._zoomplot.axisWidget(axis).show();
      text = QwtText(title);
      text.setFont(font);
      self._zoomplot.axisWidget(axis).setTitle(text);
    self._zoomplot.setAxisLabelRotation(QwtPlot.yLeft,-90);
    self._zoomplot.setAxisLabelAlignment(QwtPlot.yLeft,Qt.AlignVCenter);
    self._zoomplot.setAxisLabelRotation(QwtPlot.yRight,90);
    self._zoomplot.setAxisLabelAlignment(QwtPlot.yRight,Qt.AlignVCenter);
    self._zoomplot.plotLayout().setAlignCanvasToScales(True);
    lo0.addWidget(self._zoomplot,0);
    # setup ZoomItem for zoom plot
    self._zi = self.ImageItem();
    self._zi.attach(self._zoomplot);
    self._zi.setZ(0);
    # setup targeting reticule for zoom plot
    self._reticules = TiggerPlotCurve(),TiggerPlotCurve();
    for curve in self._reticules:
      curve.setPen(QPen(QColor("green")));
      curve.setStyle(QwtPlotCurve.Lines);
      curve.attach(self._zoomplot);
      curve.setZ(1);
    # setup cross-section curves
    pen = makeDualColorPen("navy","yellow");
    self._xcs = TiggerPlotCurve();
    self._ycs = TiggerPlotCurve();
    self._xcs.setPen(makeDualColorPen("navy","yellow"));
    self._ycs.setPen(makeDualColorPen("black","cyan"));
    for curve in self._xcs,self._ycs:
      curve.setStyle(QwtPlotCurve.Steps);
      curve.attach(self._zoomplot);
      curve.setZ(2);
    self._xcs.setXAxis(QwtPlot.xBottom);
    self._xcs.setYAxis(QwtPlot.yRight);
    self._ycs.setXAxis(QwtPlot.xTop);
    self._ycs.setYAxis(QwtPlot.yLeft);
    self._ycs.setCurveType(QwtPlotCurve.Xfy);
    # make QTransform for flipping images upside-down
    self._xform = QTransform();
    self._xform.scale(1,-1);
    # init geometry
    self.setPlotSize(radius,factor);
    self.initGeometry();


  def _showZoom (self,show):
    if not show:
      self._zi.setVisible(False);

  def _showCrossSections (self,show):
    self._zoomplot.enableAxis(QwtPlot.xTop,show);
    self._zoomplot.enableAxis(QwtPlot.yRight,show);
    if not show:
      self._xcs.setVisible(False);
      self._ycs.setVisible(False);

  def _enlarge (self):
    self.setPlotSize(self._radius*2,self._magfac);

  def _shrink (self):
    self.setPlotSize(self._radius/2,self._magfac);

  def setPlotSize (self,radius,factor):
    Config.set('livezoom-radius',radius);
    self._radius = radius;
    # enable smaller/larger buttons based on radius
    self._smaller.setEnabled(radius>5);
    self._larger.setEnabled(radius<40);
    # compute other sizes
    self._npix = radius*2+1;
    self._magfac = factor;
    width = height = self._npix*self._magfac;
    self._zoomplot.setMinimumHeight(height+80);
    self._zoomplot.setMinimumWidth(width+80);
    # set data array
    self._data = numpy.ma.masked_array(numpy.zeros((self._npix,self._npix),float),numpy.zeros((self._npix,self._npix),bool));
    # reset window size
    self._lo0.update();
    self.resize(self._lo0.minimumSize());

  def _getZoomSlice (self,ix,nx):
    ix0,ix1 = ix - self._radius,ix + self._radius + 1;
    zx0 = -min(ix0,0);
    ix0 = max(ix0,0);
    zx1 = self._npix - max(ix1,nx-1) + (nx-1)
    ix1 = min(ix1,nx-1);
    return ix0,ix1,zx0,zx1;

  class ImageItem (QwtPlotItem):
    """ImageItem subclass used by LiveZoomer to display zoomed-in images""";
    def __init__ (self):
      QwtPlotItem.__init__(self);
      self._qimg = None;

    def setImage (self,qimg):
      self._qimg = qimg;

    def draw (self,painter,xmap,ymap,rect):
      """Implements QwtPlotItem.draw(), to render the image on the given painter.""";
      self._qimg and painter.drawImage(QRect(xmap.p1(),ymap.p2(),xmap.pDist(),ymap.pDist()),self._qimg);


  def trackImage (self,image,ix,iy):
    if not self.isVisible():
      return;
    # update zoomed image
    # find overlap of zoom window with image, mask invisible pixels
    nx,ny = image.imageDims();
    ix0,ix1,zx0,zx1 = self._getZoomSlice(ix,nx);
    iy0,iy1,zy0,zy1 = self._getZoomSlice(iy,ny);
    if ix0 < nx and ix1 >=0 and iy0 < ny and iy1 >= 0:
      if self._showzoom.isChecked():
        self._data.mask[...] = False;
        self._data.mask[:zx0,...] = True;
        self._data.mask[zx1:,...] = True;
        self._data.mask[...,:zy0] = True;
        self._data.mask[...,zy1:] = True;
        # copy & colorize region
        self._data[zx0:zx1,zy0:zy1] = image.image()[ix0:ix1,iy0:iy1];
        intensity = image.intensityMap().remap(self._data);
        self._zi.setImage(image.colorMap().colorize(image.intensityMap().remap(self._data)).transformed(self._xform));
        self._zi.setVisible(True);
      # set cross-sections
      if self._showcs.isChecked():
        if iy >=0 and iy < ny and ix1>ix0:
          xcs = [ float(x) for x in image.image()[ix0:ix1,iy] ];
          self._xcs.setData(numpy.arange(ix0-1,ix1)+.5,[xcs[0]]+xcs);
          self._xcs.setVisible(True);
          self._zoomplot.setAxisAutoScale(QwtPlot.yRight);
          self._has_xcs = True;
        else:
          self._xcs.setVisible(False);
          self._zoomplot.setAxisScale(QwtPlot.yRight,0,1);
        if ix >=0 and ix < nx and iy1>iy0:
          ycs = [ float(y) for y in image.image()[ix,iy0:iy1] ];
          self._ycs.setData([ycs[0]]+ycs,numpy.arange(iy0-1,iy1)+.5);
          self._ycs.setVisible(True);
          self._zoomplot.setAxisAutoScale(QwtPlot.xTop);
          self._has_ycs = True;
        else:
          self._ycs.setVisible(False);
          self._zoomplot.setAxisScale(QwtPlot.xTop,0,1);
    else:
      for plotitem in self._zi,self._xcs,self._ycs:
        plotitem.setVisible(False);
    # set zoom plot scales
    x0,x1 = ix-self._radius-.5,ix+self._radius+.5;
    y0,y1 = iy-self._radius-.5,iy+self._radius+.5
    self._reticules[0].setData([ix,ix],[y0,y1]);
    self._reticules[1].setData([x0,x1],[iy,iy]);
    self._zoomplot.setAxisScale(QwtPlot.xBottom,x0,x1);
    self._zoomplot.setAxisScale(QwtPlot.yLeft,y0,y1);
    self._zoomplot.enableAxis(QwtPlot.xTop,self._showcs.isChecked());
    # update plots
    self._zoomplot.replot();

class LiveProfile (ToolDialog):
  def __init__ (self,parent):
    ToolDialog.__init__(self,parent,configname="liveprofile",menuname="profiles",show_shortcut=Qt.Key_F3);
    self.setWindowTitle("Profiles");
    # add plots
    lo0 = QVBoxLayout(self);
    lo0.setSpacing(0);
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1);
    lab = QLabel("Axis: ",self);
    self._wprofile_axis = QComboBox(self);
    QObject.connect(self._wprofile_axis,SIGNAL("activated(int)"),self.selectAxis);
    lo1.addWidget(lab,0);
    lo1.addWidget(self._wprofile_axis,0);
    lo1.addStretch(1);
    # add profile plot
    self._font = font = QApplication.font();
    self._profplot = QwtPlot(self);
    self._profplot.setMargin(0);
    self._profplot.enableAxis(QwtPlot.xBottom);
    self._profplot.enableAxis(QwtPlot.yLeft);
    self._profplot.setAxisFont(QwtPlot.xBottom,font);
    self._profplot.setAxisFont(QwtPlot.yLeft,font);
#    self._profplot.setAxisMaxMajor(QwtPlot.xBottom,3);
    self._profplot.setAxisAutoScale(QwtPlot.yLeft);
    self._profplot.setAxisMaxMajor(QwtPlot.yLeft,3);
    self._profplot.axisWidget(QwtPlot.yLeft).setMinBorderDist(16,16);
    self._profplot.setAxisLabelRotation(QwtPlot.yLeft,-90);
    self._profplot.setAxisLabelAlignment(QwtPlot.yLeft,Qt.AlignVCenter);
    self._profplot.plotLayout().setAlignCanvasToScales(True);
    lo0.addWidget(self._profplot,0);
    self._profplot.setMinimumHeight(192);
    self._profplot.setMinimumWidth(256);
    self._profplot.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Minimum);
    # and profile curve
    self._profcurve = TiggerPlotCurve();
    self._ycs = TiggerPlotCurve();
    self._profcurve.setPen(QPen(QColor("black")));
    self._profcurve.setStyle(QwtPlotCurve.Lines);
    self._profcurve.attach(self._profplot);
    # config geometry
    if not self.initGeometry():
      self.resize(300,192);
    self._axes = [];
    self._lastsel = None;
    self._image_id = None;

  def setImage (self,image):
    if id(image) == self._image_id:
      return;
    self._image_id = id(image);
    # build list of axes -- first X and Y
    self._axes = [];
    for n,label in enumerate(("X","Y")):
      iaxis,np = image.getSkyAxis(n);
      self._axes.append((label,iaxis,range(np),"pixels"));
    self._xaxis = self._axes[0][1];
    self._yaxis = self._axes[1][1];
    # then, extra axes
    for i in range(image.numExtraAxes()):
      iaxis,name,labels = image.extraAxisNumberNameLabels(i);
      if len(labels) > 1 and name.upper() not in ("STOKES","COMPLEX"):
        values = image.extraAxisValues(i);
        unit,scale = image.extraAxisUnitScale(i);
        self._axes.append((name,iaxis,[x/scale for x in values],unit));
    # put them into the selector
    names = [ name for name,iaxis,vals,unit in self._axes ];
    self._wprofile_axis.addItems(names);
    if self._lastsel in names:
      axis = names.index(self._lastsel);
    elif len(self._axes) > 2:
      axis = 2;
    else:
      axis = 0;
    self._wprofile_axis.setCurrentIndex(axis);
    self.selectAxis(axis,remember=False);

  def selectAxis (self,i,remember=True):
    if i < len(self._axes):
      name,iaxis,values,unit = self._axes[i];
      self._selaxis = iaxis,values;
      self._profplot.setAxisScale(QwtPlot.xBottom,min(values),max(values));
      title = QwtText("%s, %s"%(name,unit) if unit else name);
      title.setFont(self._font);
      self._profplot.setAxisTitle(QwtPlot.xBottom,title);
      # save selection
      if remember:
        self._lastsel = name;

  def trackImage (self,image,ix,iy):
    if not self.isVisible():
      return;
    nx,ny = image.imageDims();
    inrange = ix < nx and ix >=0 and iy < ny and iy >= 0;
    if inrange:
      # check if image has changed
      self.setImage(image);
      # make profile slice
      iaxis,xval = self._selaxis;
      slicer = image.currentSlice();
      slicer[self._xaxis] = ix;
      slicer[self._yaxis] = iy;
      slicer[iaxis] = slice(None);
      yval = image.data()[tuple(slicer)];
      i0,i1 = 0,len(xval);
      # if X or Y profile, set axis scale to match that of window
      if iaxis == 0:
        rect = image.currentRectPix();
        i0 = rect.topLeft().x();
        i1 = i0 + rect.width();
        self._profplot.setAxisScale(QwtPlot.xBottom,xval[i0],xval[i1-1]);
      elif iaxis == 1:
        rect = image.currentRectPix();
        i0 = rect.topLeft().y();
        i1 = i0 + rect.height();
        self._profplot.setAxisScale(QwtPlot.xBottom,xval[i0],xval[i1-1]);
      self._profcurve.setData(xval[i0:i1],yval[i0:i1]);
    self._profcurve.setVisible(inrange);
    # update plots
    self._profplot.replot();

class SkyModelPlotter (QWidget):
  # Selection modes for the various selector functions below.
  # Default is usually Clear+Add
  SelectionClear     = 1;  # clear previous selection
  SelectionAdd       = 2;  # add to selection
  SelectionRemove = 4;  # remove from selection
  # Mouse pointer modes
  MouseZoom = 0;
  MouseMeasure = 1;
  MouseSubset = 2;
  MouseSelect = 3;
  MouseDeselect = 4;

  class Plot (QwtPlot):
    """Auguments QwtPlot with additional functions, including a cache of QPoints thatr's cleared whenever a plot layout is
    updated of the plot is zoomed""";
    def __init__ (self,mainwin,skymodelplotter,parent):
      QwtPlot.__init__(self,parent);
      self._skymodelplotter = skymodelplotter;
      self.setAcceptDrops(True);
      self.clearCaches();
      self._mainwin = mainwin;
      self._drawing_key = None;

    def dragEnterEvent (self,event):
      return self._mainwin.dragEnterEvent(event);

    def dropEvent (self,event):
      return self._mainwin.dropEvent(event);

    def lmPosToScreen (self,fpos):
      return QPoint(self.transform(QwtPlot.xBottom,fpos.x()),self.transform(QwtPlot.yLeft,fpos.y()));

    def lmRectToScreen (self,frect):
      return QRect(self.lmPosToScreen(frect.topLeft()),self.lmPosToScreen(frect.bottomRight()));

    def screenPosToLm (self,pos):
      return QPointF(self.invTransform(QwtPlot.xBottom,pos.x()),self.invTransform(QwtPlot.yLeft,pos.y()));

    def screenRectToLm(self,rect):
      return QRectF(self.screenPosToLm(rect.topLeft()),self.screenPosToLm(rect.bottomRight()));

    def getMarkerPosition (self,marker):
      """Returns QPoint associated with the given marker. Caches coordinate conversion by marker ID.""";
      mid = id(marker);
      pos = self._coord_cache.get(mid);
      if pos is None:
        self._coord_cache[mid] = pos = self.lmPosToScreen(marker.lmQPointF());
      return pos;

    def drawCanvas (self,painter):
      dprint(5,"drawCanvas",time.time()%60);
      if self._drawing_key is None:
        dprint(5,"drawCanvas: key not set, redrawing");
        return QwtPlot.drawCanvas(self,painter);
      else:
        dprint(5,"drawCanvas: current key is",self._drawing_key);
        pm = self._draw_cache.get(self._drawing_key);
        if pm:
          dprint(5,"drawCanvas: found pixmap in cache, drawing");
        else:
          width,height = painter.device().width(),painter.device().height()
          dprint(5,"drawCanvas: not in cache, redrawing %dx%d pixmap"%(width,height));
          self._draw_cache[self._drawing_key] = pm = QPixmap(width,height);
          pm.fill(self.canvasBackground());
          QwtPlot.drawCanvas(self,QPainter(pm));
        painter.drawPixmap(0,0,pm);
        dprint(5,"drawCanvas done",time.time()%60);
        return;

    def clear (self):
      """Override clear() to provide a saner interface.""";
      self.clearCaches();
      self.detachItems(QwtPlotItem.Rtti_PlotItem,False);

    def updateLayout (self):
      # if an update event is pending, skip our internal stuff
      if self._skymodelplotter.isUpdatePending():
        dprint(5,"updateLayout: ignoring, since a plot update is pending");
        QwtPlot.updateLayout(self);
      else:
        dprint(5,"updateLayout");
        self.clearCaches();
        QwtPlot.updateLayout(self);
        self.emit(SIGNAL("updateLayout"));

    def setDrawingKey (self,key=None):
      """Sets the current drawing key. If key is set to not None, then drawCanvas() will look in the draw cache
      for a pixmap matching the key, instead of redrawing the canvas. It will also cache the results of the draw.
      """;
      dprint(2,"setting drawing key",key);
      self._drawing_key = key;

    def clearCaches (self):
      dprint(2,"clearing plot caches");
      self._coord_cache = {};
      self._draw_cache = {};

    def clearDrawCache (self):
      self._draw_cache = {};

  class PlotZoomer (QwtPlotZoomer):
    def __init__(self,canvas,track_callback=None,label=None):
      QwtPlotZoomer.__init__(self, canvas);
      self.setMaxStackDepth(1000);
      self._use_wheel = True;
      self._track_callback = track_callback;
      if label:
        self._label = QwtText(label);
      else:
        self._label = QwtText("");
      self._fixed_aspect = False;
      self._dczoom_button = self._dczoom_modifiers = None;
      # maintain a separate stack of  "desired" (as opposed to actual) zoom rects. When a resize of the plot happens,
      # we recompute the actual zoom rect based on the aspect ratio and the desired rect.
      self._zoomrects = [];
      # watch plot for changes: if resized, aspect ratios need to be checked
      QObject.connect(self.plot(),SIGNAL("updateLayout"),self._checkAspects);

    def isFixedAspect (self):
      return self._fixed_aspect;

    def setFixedAspect (self,fixed):
      self._fixed_aspect = fixed;
      self._checkAspects();

    def setDoubleClickZoom (self,button,modifiers):
      self._dczoom_button,self._dczoom_modifiers = button,modifiers;

    def _checkAspects (self):
      """If fixed-aspect mode is in effect, goes through zoom rects and adjusts them to the plot aspect""";
      if self._fixed_aspect:
        dprint(2,"plot canvas size is",self.plot().size());
        dprint(2,"zoom rects are",self._zoomrects);
        self._resetZoomStack(self.zoomRectIndex());

    def setZoomStack (self,stack,index=0):
      self._zoomrects = stack;
      self._resetZoomStack(index);

    def _resetZoomStack (self,index):
      stack = map(self.adjustRect,self._zoomrects);
      if stack:
        zs = stack[index];
        dprint(2,"resetting plot limits to",zs);
        self.plot().setAxisScale(QwtPlot.yLeft,zs.top(),zs.bottom());
        self.plot().setAxisScale(QwtPlot.xBottom,zs.right(),zs.left());
        self.plot().axisScaleEngine(QwtPlot.xBottom).setAttribute(QwtScaleEngine.Inverted, True);
        QwtPlotZoomer.setZoomBase(self);
        dprint(2,"reset limits, zoom stack is now",self.zoomStack());
      dprint(2,"setting zoom stack",stack,index);
      QwtPlotZoomer.setZoomStack(self,stack,index);
      dprint(2,"zoom stack is now",self.zoomStack(),self.maxStackDepth());

    def adjustRect (self,rect):
      """Adjusts rectangle w.r.t. aspect ratio settings. That is, if a fixed aspect ratio is in effect, adjusts the rectangle to match
      the aspect ratio of the plot canvas. Returns adjusted version."""
      if self._fixed_aspect:
        dprint(2,"adjusting rect to canvas size:",self.canvas().size(),rect);
        aspect0 = self.canvas().width()/float(self.canvas().height()) if self.canvas().height() else 1;
        aspect = rect.width()/float(rect.height());
        # increase rectangle, if needed to match the aspect
        if aspect < aspect0:
          dx = rect.width()*(aspect0/aspect-1)/2;
          return rect.adjusted(-dx,0,dx,0);
        elif aspect0 and aspect > aspect0:
          dy = rect.height()*(aspect/aspect0-1)/2;
          return rect.adjusted(0,-dy,0,dy);
      return rect;

    def rescale (self):
      self.plot().clearCaches();
      return QwtPlotZoomer.rescale(self);

    def zoom (self,rect):
      if not isinstance(rect,int):
        rect = rect.intersected(self.zoomBase());
        # check that it's not too small, ignore if it is
        x1,y1,x2,y2 = rect.getCoords();
        x1 = self.plot().transform(self.xAxis(),x1);
        y1 = self.plot().transform(self.yAxis(),y1);
        x2 = self.plot().transform(self.xAxis(),x2);
        y2 = self.plot().transform(self.yAxis(),y2);
        dprint(2,"zoom by",abs(x1-x2),abs(y1-y2));
        if abs(x1-x2)<=20 and abs(y1-y2)<=20:
          return;
      if isinstance(rect,int) or rect.isValid():
        dprint(2,"zoom",rect);
        if not isinstance(rect,int):
          self._zoomrects[self.zoomRectIndex()+1:] = [ QRectF(rect) ];
          rect = self.adjustRect(rect);
          dprint(2,"zooming to",rect);
        QwtPlotZoomer.zoom(self,rect);
        dprint(2,"zoom stack is now",self.zoomStack());
      else:
        dprint(2,"invalid zoom selected, ignoring",rect);

    def trackerText (self,pos):
      return (self._track_callback and self._track_callback(pos)) or (self._label if self.isActive() else QwtText(""));

    def enableWheel (self,enable):
      self._use_wheel = enable;

    def widgetMouseDoubleClickEvent (self,ev):
      x = self.plot().invTransform(self.xAxis(),ev.x());
      y = self.plot().invTransform(self.yAxis(),ev.y());
      if int(ev.button()) == self._dczoom_button and int(ev.modifiers()) == self._dczoom_modifiers:
        self.emit(SIGNAL("provisionalZoom"),x,y,1,10);

    def widgetWheelEvent (self,ev):
      x = self.plot().invTransform(self.xAxis(),ev.x());
      y = self.plot().invTransform(self.yAxis(),ev.y());
      dprint(3,"zoomer wheel",ev.x(),ev.y(),ev.delta(),x,y,self._use_wheel);
      if self._use_wheel:
        self.emit(SIGNAL("provisionalZoom"),x,y,(1 if ev.delta() > 0 else -1),200);
#        if ev.delta() < 0:
#          if self.zoomRectIndex() > 0:
#            self.zoom(-1);
#          else:
#            dprint(0,"zoomed all the way out, wheel event ignored");
#        else:
#          x1,y1,x2,y2 = self.zoomRect().getCoords();
#          w = (x2-x1)/2;
#          h = (y2-y1)/2;
#          # self.zoom(QRectF(x-w/2,y-h/2,w,h));
#          self.emit(SIGNAL("provisionalZoom"),x,y,1);
      QwtPlotPicker.widgetWheelEvent(self,ev);

  class PlotPicker (QwtPlotPicker):
    """Auguments QwtPlotPicker with functions for selecting objects""";
    def __init__ (self,canvas,label,color="red",select_callback=None,track_callback=None,
                        mode=QwtPicker.RectSelection,rubber_band=QwtPicker.RectRubberBand,text_bg=None):
      QwtPlotPicker.__init__(self,QwtPlot.xBottom,QwtPlot.yLeft,mode,rubber_band,QwtPicker.ActiveOnly,canvas);
      # setup appearance
      self._text = QwtText(label);
      self._color = None;
#      self._text_inactive = QwtText();
      self.setLabel(label,color);
      if isinstance(text_bg,QColor):
        text_bg = QBrush(text_bg);
      self._text_bg = text_bg;
      if text_bg:
        self._text.setBackgroundBrush(text_bg);
        self._text_inactive.setBackgroundBrush(text_bg);
      # setup callbacks
      self._track_callback = track_callback;
      self._select_callback = select_callback;
      if select_callback:
        if mode == QwtPicker.RectSelection:
          QObject.connect(self,SIGNAL("selected(const QwtDoubleRect &)"),select_callback);
        elif mode == QwtPicker.PointSelection:
          QObject.connect(self,SIGNAL("selected(const QwtDoublePoint &)"),select_callback);
        elif mode == QwtPicker.PolygonSelection:
          QObject.connect(self,SIGNAL("selected(const QwtPolygon &)"),select_callback);

    def setLabel (self,label,color=None):
      if color:
        self.setRubberBandPen(makeDualColorPen(color,"white"));
        self._color = QColor(color);
        self._text.setColor(self._color);
      self._label = label;
      self._text.setText(label);

    def trackerText (self,pos):
      text = self._track_callback and self._track_callback(pos);
      if text is None:
        self._text.setText(self._label);
        return self._text; # if self.isActive() else self._text_inactive;
      else:
        if not isinstance(text,QwtText):
          if self._label:
            text = "%s %s"%(self._label,text);
          text = QwtText(text);
          self._text.setText(self._label);
          text = self._text;
        if self._text_bg:
          text.setBackgroundBrush(self._text_bg);
        if self._color is not None:
          text.setColor(self._color);
        return text;

  class PlotRuler (PlotPicker):
    """This is an ugly kludge to get a QwtPicker in PolygonSelection mode (with a PolygonRubberBand)
    to act as a DragSelection. By default, it is impossible to display a "ruler" that acts like
    a RecSelection-style DragSelection: rulers are only available with a PolygonSelection,
    which does not support drag, but rather requires two clicks. By intercepting the mouse release
    event here and faking a second mouse press, we achieve DragSelection-like behaviour."""
    def widgetLeaveEvent (self,event):
      self.reset();
    def transition (self,event):
      SkyModelPlotter.PlotPicker.transition(self,event);
      if event.type() == QEvent.MouseButtonRelease:
        ev1 = QMouseEvent(QEvent.MouseButtonPress,event.pos(),event.button(),event.buttons(),event.modifiers());
        SkyModelPlotter.PlotPicker.transition(self,ev1);
        ev2 = QMouseEvent(QEvent.MouseButtonRelease,event.pos(),event.button(),event.buttons(),event.modifiers());
        SkyModelPlotter.PlotPicker.transition(self,ev2);
        self.reset();

  def __init__ (self,parent,mainwin,*args):
    QWidget.__init__(self,parent,*args);
    # plot update logic -- handle updates via the event looop
    self._updates_enabled = False;  # updates ignored until this is True
    self._update_pending = 0;         # serial number of most recently posted update event
    self._update_done = 0;             # serial number of most recently processed update event
    self._update_what = 0;             # mask of updates ('what' arguments to _updateLayout) accumulated since last update was done
    # create currier
    self._currier = PersistentCurrier();
    # init widgetry
    lo = QHBoxLayout(self);
    lo.setSpacing(0);
    lo.setContentsMargins(0,0,0,0);
    self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);
    self.plot  = self.Plot(mainwin,self,self);
    self.plot.setAutoDelete(False);
    self.plot.setEnabled(False);
    self.plot.enableAxis(QwtPlot.yLeft,False);
    self.plot.enableAxis(QwtPlot.xBottom,False);
    lo.addWidget(self.plot);
    # setup plot groupings
    self._bg_color = QColor("#808080");
    self.plot.setCanvasBackground(self._bg_color);
    self._bg_brush = QBrush(self._bg_color);
    color = QColor("white");
    color.setAlpha(128);
    self._coord_bg_brush = QBrush(color);
    self._grid_color= QColor("navy");
    self._grid_pen = QPen(self._grid_color);
    self._grid_pen.setStyle(Qt.DotLine);
    self._image_pen = QPen(self._grid_color);
    self._image_pen.setStyle(Qt.DashLine);
    # init plot pickers
    self._initPickers();
    # init markup symbols and colors and pens
    self._plot_markup = [];
    self._stats_color = QColor("red");
    self._stats_pen = QPen(self._stats_color,1);
#    self._stats_pen.setStyle(Qt.DotLine);
    self._subset_color = QColor("lightblue");
    self._subset_pen = QPen(self._subset_color,1);
    self._markup_color = QColor("cyan");
    self._markup_pen = QPen(self._markup_color,1);
    self._markup_brush = QBrush(Qt.NoBrush);
    self._markup_xsymbol = QwtSymbol(QwtSymbol.XCross,self._markup_brush,self._markup_pen,QSize(16,16));
    self._markup_absymbol = QwtSymbol(QwtSymbol.Ellipse,self._markup_brush,self._markup_pen,QSize(4,4));
    self._markup_a_label = QwtText("A");
    self._markup_a_label.setColor(self._markup_color);
    self._markup_b_label = QwtText("B");
    self._markup_b_label.setColor(self._markup_color);
    # init live zoomers
    self._livezoom = LiveImageZoom(self);
    self._liveprofile = LiveProfile(self);
    # other internal init
    self.model = None;
    self.projection = None;
    self._zoomrect  = None;
    self._text_no_source = QwtText("");
    self._text_no_source.setColor(QColor("red"));
    # image controller
    self._imgman = self._image = None;
    self._markers = {};
    self._source_lm = {};
    self._export_png_dialog = None;
    # menu and toolbar
    self._menu = QMenu("&Plot",self);
    self._wtoolbar = QToolBar(self);
    self._wtoolbar.setIconSize(QSize(16,16));
    self._wtoolbar.setOrientation(Qt.Vertical);
    lo.insertWidget(0,self._wtoolbar);
    self._qag_mousemode = QActionGroup(self);
    self._qa_unzoom = self._wtoolbar.addAction(pixmaps.zoom_out.icon(),"Unzoom plot",self._currier.curry(self._zoomer.zoom,0));
    self._qa_unzoom.setToolTip("""<P>Click to unzoom the plot all the way out to its full size.</P>""");
    self._qa_unzoom.setShortcut(Qt.ALT+Qt.Key_Minus);
    self._wtoolbar.addSeparator();
    self._menu.addAction(self._qa_unzoom);
    # mouse mode controls
    mouse_menu = self._menu.addMenu("Mouse mode");
    # init top of menu
    mouse_menu.addAction("Show quick mouse reference",self._showMouseModeTooltip,Qt.Key_F1);
    self._qa_mwzoom = qa = mouse_menu.addAction("Use mouse wheel zoom");
    qa.setCheckable(True);
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._zoomer.enableWheel);
    QObject.connect(qa,SIGNAL("triggered(bool)"),self._currier.curry(Config.set,"mouse-wheel-zoom"));
    qa.setChecked(Config.getbool("mouse-wheel-zoom",True));
    self._zoomer.enableWheel(qa.isChecked());
    mouse_menu.addSeparator();
    self._mousemodes = MouseModes.MouseModeManager(self,mouse_menu,self._wtoolbar);
    QObject.connect(self._mousemodes,SIGNAL("setMouseMode"),self._setMouseMode);
    self._setMouseMode(self._mousemodes.currentMode());
    self._qa_colorzoom = self._wtoolbar.addAction(pixmaps.zoom_colours.icon(),"Zoom colourmap into subset",
        self._colourZoomIntoSubset);
    self._qa_colorzoom.setShortcut(Qt.SHIFT+Qt.Key_F4);
    self._qa_colorzoom.setVisible(False);
    self._menu.addAction(self._qa_colorzoom);
    # hide/show tools
    self._menu.addAction(self._liveprofile.getShowQAction());
    self._menu.addAction(self._livezoom.getShowQAction());
    # fixed aspect
    qa = self._menu.addAction("Fix aspect ratio");
    qa.setCheckable(True);
    qa.setChecked(Config.getbool("fix-aspect-ratio",True));
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._zoomer.setFixedAspect);
    QObject.connect(qa,SIGNAL("triggered(bool)"),self._currier.curry(Config.set,"fix-aspect-ratio"));
    self._zoomer.setFixedAspect(qa.isChecked());
    qa.setToolTip("""<P>Enable this to maintain a fixed aspect ratio in the plot.</P>""");
    # beam
    self._qa_show_psf = self._menu.addAction("Show PSF (aka beam)");
    self._qa_show_psf.setCheckable(True);
    self._qa_show_psf.setChecked(True);
    self._psf_marker = TiggerPlotCurve();
    self._psf_marker.setPen(QPen(QColor("lightgreen")));
    self._psf_marker.setZ(Z_Grid);
    QObject.connect(self._qa_show_psf,SIGNAL("toggled(bool)"),self._showPsfMarker);
    # grid stepping
    self._grid_step_arcsec = DefaultGridStep_ArcSec;
    gridmenu = self._menu.addMenu("Show grid circles");
    qag = QActionGroup(gridmenu);
    gridsteps = [ None,1,2,5,10,30,60,120,300,600 ];
    for step in gridsteps:
      if step is None:
        text = "None";
      elif step < 60:
        text = "%d'"%step;
      else:
        text = u"%d\u00B0"%(step/60);
      qa = gridmenu.addAction(text,self._currier.curry(self._setGridCircleStepping,step and step*60));
      qa.setCheckable(True);
      qa.setChecked(step==self._grid_step_arcsec);
      qag.addAction(qa);
    qa = self._qa_custom_grid = gridmenu.addAction("Custom...",self._setCustomGridCircleStepping);
    qa.setCheckable(True);
    qag.addAction(qa);
    self._grid_step_arcsec_str = "";
    if self._grid_step_arcsec/60 not in gridsteps:
      self._setCustomGridCircleSteppingLabel();
      qa.setChecked(True);
    # save as PNG file
    self._menu.addAction("Export plot to PNG file...",self._exportPlotToPNG,Qt.CTRL+Qt.Key_F12);

  def close (self):
    self._menu.clear();
    self._wtoolbar.clear();
    self._livezoom.close();
    self._liveprofile.close();

  def getMenu (self):
    return self._menu;

  def enableUpdates (self,enable=True):
    self._updates_enabled = enable;
    if enable:
      self.postUpdateEvent();

  # extra flag for updateContents() -- used when image content or projection has changed
  UpdateImages = 1<<16;

  def setImageManager (self, im):
    """Attaches an image manager."""
    self._imgman = im;
    im.setZ0(Z_Image);
    im.enableImageBorders(self._image_pen,self._grid_color,self._bg_brush);
    QObject.connect(im,SIGNAL("imagesChanged"),self._currier.curry(self.postUpdateEvent,self.UpdateImages));
    QObject.connect(im,SIGNAL("imageRaised"),self._imageRaised);

  class UpdateEvent (QEvent):
    def __init__ (self,serial):
      QEvent.__init__(self,QEvent.User);
      self.serial = serial;

  def isUpdatePending (self):
    return self._update_pending > self._update_done;

  def postUpdateEvent (self,what=SkyModel.UpdateAll,origin=None):
    """Posts an update event. Since plot updates are somewhat expensive, and certain operations can cause multiple updates,
    we handle them through the event loop."""
    dprintf(3,"postUpdateEvent(what=%x,origin=%s)\n",what,origin);
    self._update_what |= what;
    self._update_pending += 1;
    dprintf(3,"posting update event, serial %d, new mask %x\n",self._update_pending,self._update_what);
    QCoreApplication.postEvent(self,self.UpdateEvent(self._update_pending));

  def event (self,ev):
    if isinstance(ev,self.UpdateEvent):
      if ev.serial < self._update_pending:
        dprintf(3,"ignoring update event %d since a more recent one is already posted\n",ev.serial);
      else:
        dprintf(3,"received update event %d, updating contents with mask %x\n",ev.serial,self._update_what);
        self._updateContents(self._update_what);
        self._update_what = 0;
        self._update_done = ev.serial;
    return QWidget.event(self,ev);

  def _initPickers (self):
    """Called from __init__ to create the various plot pickers for support of mouse modes.""";
    # this picker is invisible -- it is just there to make sure _trackCoordinates is always called
    self._tracker = self.PlotPicker(self.plot.canvas(),"",mode=QwtPicker.PointSelection,track_callback=self._trackCoordinates);
    self._tracker.setTrackerMode(QwtPicker.AlwaysOn);
    # zoom picker
    self._zoomer = self.PlotZoomer(self.plot.canvas(),label="zoom");
    self._zoomer_pen = makeDualColorPen("navy","yellow");
    self._zoomer.setRubberBandPen(self._zoomer_pen);
    self._zoomer.setTrackerPen(QColor("yellow"));
    QObject.connect(self._zoomer,SIGNAL("zoomed(const QwtDoubleRect &)"),self._plotZoomed);
    QObject.connect(self._zoomer,SIGNAL("provisionalZoom"),self._plotProvisionalZoom);
    self._zoomer_box = TiggerPlotCurve();
    self._zoomer_box.setPen(self._zoomer_pen);
    self._zoomer_label = TiggerPlotMarker();
    self._zoomer_label_text = QwtText("");
    self._zoomer_label_text.setColor(QColor("yellow"));
    self._zoomer_label.setLabel(self._zoomer_label_text);
    self._zoomer_label.setLabelAlignment(Qt.AlignBottom|Qt.AlignRight);
    for item in self._zoomer_label,self._zoomer_box:
      item.setZ(Z_Markup);
    self._provisional_zoom_timer = QTimer(self);
    self._provisional_zoom_timer.setSingleShot(True);
    QObject.connect(self._provisional_zoom_timer,SIGNAL("timeout()"),self._finalizeProvisionalZoom);
    self._provisional_zoom = None;

#    self._zoomer.setStateMachine(QwtPickerDragRectMachine());
    self._zoomer.setSelectionFlags(QwtPicker.RectSelection|QwtPicker.DragSelection);
    # ruler picker for measurement mode
    self._ruler = self.PlotRuler(self.plot.canvas(),"measure","cyan",self._measureRuler,
      mode=QwtPicker.PolygonSelection,
      rubber_band=QwtPicker.PolygonRubberBand,
      track_callback=self._trackRuler);
    # this is the initial position of the ruler -- None if ruler is not tracking
    self._ruler_pos0 = None;
    # stats picker
    self._picker_stats = self.PlotPicker(self.plot.canvas(),"stats","red",self._selectRectStats);
    # model selection pickers
    self._picker1 = self.PlotPicker(self.plot.canvas(),"select","green",self._selectRect);
    self._picker2 = self.PlotPicker(self.plot.canvas(),"+select","green",curry(self._selectRect,mode=self.SelectionAdd));
    self._picker3 = self.PlotPicker(self.plot.canvas(),"-select","red",curry(self._selectRect,mode=self.SelectionRemove));
    self._picker4 = self.PlotPicker(self.plot.canvas(),"","green",self._selectNearestSource,mode=QwtPicker.PointSelection);
    for picker in self._zoomer,self._ruler,self._picker1,self._picker2,self._picker3,self._picker4:
      for sel in QwtEventPattern.MouseSelect1,QwtEventPattern.MouseSelect2,QwtEventPattern.MouseSelect3,QwtEventPattern.MouseSelect4:
        picker.setMousePattern(sel,0,0);
      picker.setTrackerMode(QwtPicker.ActiveOnly);
#    for picker in self._ruler,self._picker1,self._picker2,self._picker3:
#      QObject.connect(picker,SIGNAL("wheelEvent"),self._zoomer.widgetWheelEvent);

  def _showMouseModeTooltip (self):
    tooltip = self._mousemodes.currentMode().tooltip;
    if self._qa_mwzoom.isChecked():
      tooltip += """<P>You also have mouse-wheel zoom enabled. Rolling the wheel up will zoom in at the current zoom point.
      Rolling the wheel down will zoom back out.</P>""";
    QMessageBox.information(self,"Quick mouse reference",tooltip);
#    self._showCoordinateToolTip(self._mousemodes.currentMode().tooltip,rect=False);

  @staticmethod
  def _setPickerPattern (picker,patt,func,mousemode,auto_disable=True):
    """Helper function, sets mouse/key pattern for picker from the mode patterns dict""";
    mpat,kpat = mousemode.patterns.get(func,((0,0),(0,0)));
    if auto_disable:
      picker.setEnabled(mpat[0] or kpat[0]);
    elif mpat[0] or kpat[0]:
      picker.setEnabled(True);
    picker.setMousePattern(patt,*mpat);
    picker.setKeyPattern(patt,*kpat);

  def _setMouseMode (self,mode):
    """Sets the current mouse mode from patterns (see MouseModes), updates action shortcuts.
    'mode' is MouseModes.MouseModeManager.MouseMode object. This has a patterns dict.
    For each MM_xx function defined in MouseModes, patterns[MM_xx] = (mouse_patt,key_patt)
    Each pattern is either None, or a (button,state) pair. If MM_xx is not in the dict, then thatfunction is
    disabled.""";
    dprint(1,"setting mouse mode",mode.id);
    self._mouse_mode = mode.id;
    # remove markup
    self._removePlotMarkup();
    # disable/enable pickers accordingly
    self._zoomer.setEnabled(True);
    self._setPickerPattern(self._zoomer,QwtEventPattern.MouseSelect1,MouseModes.MM_ZWIN,mode,auto_disable=False);
    if MouseModes.MM_ZWIN in mode.patterns:
      self._zoomer.setDoubleClickZoom(*mode.patterns[MouseModes.MM_ZWIN][0]);
    else:
      self._zoomer.setDoubleClickZoom(0,0);
    self._setPickerPattern(self._zoomer,QwtEventPattern.MouseSelect2,MouseModes.MM_UNZOOM,mode,auto_disable=False);
    self._setPickerPattern(self._zoomer,QwtEventPattern.MouseSelect3,MouseModes.MM_ZUNDO,mode,auto_disable=False);
    self._setPickerPattern(self._zoomer,QwtEventPattern.MouseSelect6,MouseModes.MM_ZREDO,mode,auto_disable=False);
    self._setPickerPattern(self._ruler,QwtEventPattern.MouseSelect1,MouseModes.MM_MEAS,mode);
    self._setPickerPattern(self._picker_stats,QwtEventPattern.MouseSelect1,MouseModes.MM_STATS,mode);
    self._setPickerPattern(self._picker1,QwtEventPattern.MouseSelect1,MouseModes.MM_SELWIN,mode);
    self._setPickerPattern(self._picker2,QwtEventPattern.MouseSelect1,MouseModes.MM_SELWINPLUS,mode);
    self._setPickerPattern(self._picker3,QwtEventPattern.MouseSelect1,MouseModes.MM_DESEL,mode);
    self._setPickerPattern(self._picker4,QwtEventPattern.MouseSelect1,MouseModes.MM_SELSRC,mode);
    dprint(2,"picker4 pattern:",mode.patterns.get(MouseModes.MM_SELSRC,None));

  def findNearestSource (self,pos,world=True,range=10):
    """Returns source object nearest to the specified point (within range, in pixels), or None if nothing is in range.
        'pos' is a QPointF/QwtDoublePoint object in lm coordinates if world=True, else a QPoint object."""
    if world:
      pos = self.plot.lmPosToScreen(pos);
    dists = [ ((pos-self.plot.getMarkerPosition(marker)).manhattanLength(),marker) for marker in self._markers.itervalues() if marker.isVisible() ];
    if dists:
      mindist = min(dists,key=lambda x:x[0]);
      if mindist[0] < 10:
        return mindist[1].src;
    return  None;

  def _convertCoordinates (self,pos):
    # get ra/dec coordinates of point
    pos = self.plot.screenPosToLm(pos);
    l,m = pos.x(),pos.y();
    ra,dec = self.projection.radec(l,m);
    rh,rm,rs = ModelClasses.Position.ra_hms_static(ra);
    dsign,dd,dm,ds = ModelClasses.Position.dec_sdms_static(dec);
    dist,pa = Coordinates.angular_dist_pos_angle(self.projection.ra0,self.projection.dec0,ra,dec);
    Rd,Rm,Rs = ModelClasses.Position.dec_dms_static(dist);
    PAd = pa*180/math.pi;
    if PAd < 0:
      PAd += 360;
    # if we have an image, add pixel coordinates
    x = y = val = flag = None;
    image = self._imgman and self._imgman.getTopImage();
    if image:
      x,y = map(int,map(round,image.lmToPix(l,m)));
      nx,ny = image.imageDims();
      if x>=0 and x<nx and y>=0 and y<ny:
#        text += "<BR>x=%d y=%d"%(round(x),round(y));
        val,flag = image.imagePixel(x,y);
      else:
        x = y = None;
    return l,m,ra,dec,dist,pa,rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd,x,y,val,flag;

  def _trackRuler (self,pos):
    # beginning to track?
    if not self.projection:
      return None;
    if self._ruler_pos0 is None:
      self._ruler_pos0 = QPoint(pos.x(),pos.y());
      lmpos = self.plot.screenPosToLm(pos);
      ra,dec = self.projection.radec(lmpos.x(),lmpos.y());
      self._ruler_radec0 = [ ra,dec ];
      return None;
    if (pos - self._ruler_pos0).manhattanLength() > 1:
      lmpos = self.plot.screenPosToLm(pos);
      ra,dec = self.projection.radec(lmpos.x(),lmpos.y());
      dist,pa = Coordinates.angular_dist_pos_angle(*(self._ruler_radec0 + [ra,dec]));
      Rd,Rm,Rs = ModelClasses.Position.dec_dms_static(dist);
      pa *= 180/math.pi;
      pa += 360*(pa<0);
      msgtext = u"%d\u00B0%02d'%05.2f\"  PA=%.2f\u00B0"%(Rd,Rm,Rs,pa);
      # self._ruler1.setLabel("");
      return QwtText(msgtext);

  def _measureRuler (self,polygon):
    self._ruler_pos0 = None;
    if not self.projection or polygon.size() < 2:
      return;
    # get distance between points, if <=1, report coordinates rather than a measurement
    markup_items = [];
    pos0,pos1 = polygon.point(0),polygon.point(1);
    l,m,ra,dec,dist,pa,rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd,x,y,val,flag = self._convertCoordinates(pos0);
    if (pos0-pos1).manhattanLength() <= 1:
      # make tooltip text with HTML, make console (and cliboard) text w/o HTML
      tiptext = "<NOBR>";
      msgtext = "";
      if self.projection.has_projection():
        tiptext += "X: %02dh%02dm%05.2fs %s%02d&deg;%02d'%05.2f\"  &nbsp;  r<sub>0</sub>=%d&deg;%02d'%05.2f\"   &nbsp;  PA<sub>0</sub>=%06.2f&deg;"%(rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd);
        msgtext += u"X: %2dh%02dm%05.2fs %s%02d\u00B0%02d'%05.2f\" (%.6f\u00B0 %.6f\u00B0)  r=%d\u00B0%02d'%05.2f\" (%.6f\u00B0) PA=%6.2f\u00B0"%(
            rh,rm,rs,dsign,dd,dm,ds,ra*180/math.pi,dec*180/math.pi,Rd,Rm,Rs,dist*180/math.pi,PAd);
      if x is not None:
        tiptext += " &nbsp;  x=%d y=%d value=blank"%(x,y) if flag else " &nbsp;  x=%d y=%d value=%g"%(x,y,val);
        msgtext += "   x=%d y=%d value=blank"%(x,y) if flag else "   x=%d y=%d value=%g"%(x,y,val);
      tiptext += "</NOBR>";
      # make marker
      marker = TiggerPlotMarker();
      marker.setValue(l,m);
      marker.setSymbol(self._markup_xsymbol);
      markup_items.append(marker);
    else:
      l1,m1,ra1,dec1,dist1,pa1,rh1,rm1,rs1,dsign1,dd1,dm1,ds1,Rd1,Rm1,Rs1,PAd1,x1,y1,val1,flag1 = self._convertCoordinates(pos1);
      # make tooltip text with HTML, and console/clipboard text without HTML
      tiptext = "<NOBR>";
      msgtext = "";
      if self.projection.has_projection():
        tiptext += "A: %02dh%02dm%05.2fs %s%02d&deg;%02d'%05.2f\"  &nbsp; r<sub>0</sub>=%d&deg;%02d'%05.2f\"   &nbsp;  PA<sub>0</sub>=%06.2f&deg;"%(rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd);
        msgtext += u"A: %2dh%02dm%05.2fs %s%02d\u00B0%02d'%05.2f\" (%.6f\u00B0 %.6f\u00B0)  r=%d\u00B0%02d'%05.2f\" (%.6f\u00B0) PA=%06.2f\u00B0"%(
            rh,rm,rs,dsign,dd,dm,ds,ra*180/math.pi,dec*180/math.pi,Rd,Rm,Rs,dist*180/math.pi,PAd);
      if x is not None:
        tiptext += " &nbsp; x=%d y=%d value=blank"%(x,y) if flag else " &nbsp; x=%d y=%d value=%g"%(x,y,val);
        msgtext += u"   x=%d y=%d value=blank"%(x,y) if flag else "   x=%d y=%d value=%g"%(x,y,val);
      tiptext += "</NOBR><BR><NOBR>";
      if self.projection.has_projection():
        tiptext += "B: %02dh%02dm%05.2fs %s%02d&deg;%02d'%05.2f\" &nbsp;  r<sub>0</sub>=%d&deg;%02d'%05.2f\"  &nbsp;  PA<sub>0</sub>=%06.2f&deg;"%(rh1,rm1,rs1,dsign1,dd1,dm1,ds1,Rd1,Rm1,Rs1,PAd1) ;
        msgtext += u"\nB: %2dh%02dm%05.2fs %s%02d\u00B0%02d'%05.2f\" (%.6f\u00B0 %.6f\u00B0)  r=%d\u00B0%02d'%05.2f\" (%.6f\u00B0) PA=%6.2f\u00B0"%(
            rh1,rm1,rs1,dsign1,dd1,dm1,ds1,ra1*180/math.pi,dec1*180/math.pi,Rd1,Rm1,Rs1,dist1*180/math.pi,PAd1);
      if x1 is not None:
        tiptext += " &nbsp; x=%d y=%d value=blank"%(x1,y1) if flag1 else " &nbsp; x=%d y=%d value=%g"%(x1,y1,val1);
        msgtext += u"   x=%d y=%d value=blank"%(x1,y1) if flag1 else "   x=%d y=%d value=%g"%(x1,y1,val1);
      tiptext += "</NOBR><BR>";
      # distance measurement
      dist2,pa2 = Coordinates.angular_dist_pos_angle(ra,dec,ra1,dec1);
      Rd2,Rm2,Rs2 = ModelClasses.Position.dec_dms_static(dist2);
      pa2 *= 180/math.pi;
      pa2 += 360*(pa2<0);
      tiptext += "<NOBR>|AB|=%d&deg;%02d'%05.2f\" &nbsp; PA<sub>AB</sub>=%06.2f&deg;</NOBR>"%(Rd2,Rm2,Rs2,pa2);
      msgtext += u"\n|AB|=%d\u00B0%02d'%05.2f\" (%.6f\u00B0) PA=%6.2f\u00B0"%(Rd2,Rm2,Rs2,dist2*180/math.pi,pa2);
      # make markers
      marka,markb = TiggerPlotMarker(),TiggerPlotMarker();
      marka.setValue(l,m);
      markb.setValue(l1,m1);
      marka.setLabel(self._markup_a_label);
      markb.setLabel(self._markup_b_label);
      marka.setSymbol(self._markup_absymbol);
      markb.setSymbol(self._markup_absymbol);
      # work out optimal label alignment
      aligna = Qt.AlignRight if pos0.x() > pos1.x() else Qt.AlignLeft;
      alignb = Qt.AlignLeft if pos0.x() > pos1.x() else Qt.AlignRight;
      aligna |= Qt.AlignBottom if pos0.y() > pos1.y() else Qt.AlignTop;
      alignb |= Qt.AlignTop if pos0.y() > pos1.y() else Qt.AlignBottom;
      marka.setLabelAlignment(aligna);
      markb.setLabelAlignment(alignb);
      marka.setSpacing(0);
      markb.setSpacing(0);
      line = TiggerPlotCurve();
      line.setData([l,l1],[m,m1]);
      line.setBrush(self._markup_brush);
      line.setPen(self._markup_pen);
      markup_items = [ marka,markb,line ];
    # since this is going to hide the stats box, hide the colour zoom button too
    self._qa_colorzoom.setVisible(False);
    # calling QToolTip.showText() directly from here doesn't work, so set a timer on it
    QTimer.singleShot(10,self._currier.curry(self._showCoordinateToolTip,tiptext));
    # same deal for markup items
    for item in markup_items:
      item.setZ(Z_Markup);
    QTimer.singleShot(10,self._currier.curry(self._addPlotMarkup,markup_items));
    print msgtext;
    QApplication.clipboard().setText(msgtext+"\n");
    QApplication.clipboard().setText(msgtext+"\n",QClipboard.Selection);

  def _showCoordinateToolTip (self,text,rect=True):
    dprint(2,text);
    if rect:
      QToolTip.showText(self.plot.mapToGlobal(QPoint(0,0)),text,self.plot,self.plot.rect());
    else:
      QToolTip.showText(self.plot.mapToGlobal(QPoint(0,0)),text);

  def _imageRaised (self):
    """This is called when an image is raised to the top""";
    self._updatePsfMarker(None,replot=True);
    self._removePlotMarkup();
    self._image_subset = None;

  def _showPsfMarker (self,show):
    self._psf_marker.setVisible(show);
    self.plot.clearDrawCache();
    self.plot.replot();

  def _updatePsfMarker (self,rect=None,replot=False):
      # show PSF if asked to
      topimage = self._imgman and self._imgman.getTopImage();
      pmaj,pmin,ppa = topimage.getPsfSize() if topimage else (0,0,0);
      self._qa_show_psf.setVisible(bool(topimage and pmaj!=0));
      self._psf_marker.setVisible(bool(topimage and pmaj!=0 and self._qa_show_psf.isChecked()));
      if self._qa_show_psf.isVisible():
        rect = rect or self._zoomer.zoomBase();
        rect &= topimage.boundingRect();
        dprint(1,"updating PSF for zoom rect",rect);
        lm = rect.bottomLeft();
        l00 =  lm.x() + pmaj/1.2;
        m00 = lm.y() - pmaj/1.2;
        dprint(1,"drawing PSF at",l00,m00,"z",self._psf_marker.z());
        arg = numpy.arange(0,1.02,.02)*math.pi*2;
        mp0,lp0 = pmaj*numpy.cos(arg)/2,pmin*numpy.sin(arg)/2;  # angle 0 is m direction
        c,s = numpy.cos(ppa),numpy.sin(ppa);
        lp = lp0*c + mp0*s;
        mp = - lp0*s + mp0*c;
        self._psf_marker.setData(lp+l00,mp+m00);
        if replot and self._psf_marker.isVisible():
          self._replot();

  def _replot (self):
      dprint(1,"replot");
      self.plot.clearDrawCache();
      self.plot.replot();

  def _addPlotMarkup (self,items):
    """Adds a list of QwtPlotItems to the markup""";
    self._removePlotMarkup(replot=False);
    for item in items:
      item.attach(self.plot);
    self._plot_markup = items;
    self._replot();

  def _removePlotMarkup (self,replot=True):
    """Removes all markup items, and refreshes the plot if replot=True""";
    for item in self._plot_markup:
      item.detach();
    if self._plot_markup and replot:
      QToolTip.showText(QPoint(0,0),"");
      self._replot();
    self._plot_markup = [];

  def _trackCoordinates (self,pos):
    if not self.projection:
      return None;
    # if Ctrl is pushed, get nearest source and make it "current"
    if QApplication.keyboardModifiers()&(Qt.ControlModifier|Qt.ShiftModifier):
      src = self.findNearestSource(pos,world=False,range=range);
      if src:
        self.model.setCurrentSource(src);
    # get ra/dec coordinates of point
    l,m,ra,dec,dist,pa,rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd,x,y,val,flag = self._convertCoordinates(pos);
#    text = "<P align=\"right\">%2dh%02dm%05.2fs %+2d&deg;%02d'%05.2f\""%(rh,rm,rs,dd,dm,ds);
    # emit message as well
    msgtext = "";
    if self.projection.has_projection():
      msgtext = u"%02dh%02dm%05.2fs %s%02d\u00B0%02d'%05.2f\"  r=%d\u00B0%02d'%05.2f\"  PA=%.2f\u00B0"%(rh,rm,rs,dsign,dd,dm,ds,Rd,Rm,Rs,PAd);
    # if we have an image, add pixel coordinates
    image = self._imgman and self._imgman.getTopImage();
    if image and x is not None:
      msgtext += "   x=%d y=%d value=blank"%(x,y) if flag else "   x=%d y=%d value=%g"%(x,y,val);
      self._livezoom.trackImage(image,x,y);
      self._liveprofile.trackImage(image,x,y);
    self.emit(SIGNAL("showMessage"),msgtext,3000);
    return None;

  def _selectSources (self,sources,mode):
    """Helper function to select sources in list""";
    # turn list into set of ids
    subset = set(map(id,sources));
    updated = False;
    for src in self.model.sources:
      newsel = src.selected;
      if id(src) in subset:
        dprint(3,"selecting",src.name);
        if mode&self.SelectionAdd:
          newsel = True;
        elif mode&self.SelectionRemove:
          newsel = False;
      elif mode&self.SelectionClear:
        newsel = False;
      updated |= (newsel != src.selected);
      src.selected = newsel;
    # emit signal if changed
    if updated:
      self.model.emitSelection(origin=self);

  def _selectNearestSource (self,pos,world=True,range=10,mode=SelectionAdd):
    """Selects or deselects source object nearest to the specified point (within range, in pixels).
        Note that _mouse_mode == MouseDeselect will force mode=SelectionRemove.
        'pos' is a QPointF/QwtDoublePoint object in lm coordinates if world=True, else a QPoint object."""
    dprint(1,"selectNearestSource",pos);
    # deselect mouse mode implies removing from selection, in all other modes we add
    if self._mouse_mode == self.MouseDeselect:
      mode = self.SelectionRemove;
    src = self.findNearestSource(pos,world=world,range=range);
    if src:
      self._selectSources([src],mode);

  def _makeRectMarker (self,rect,pen):
    x1,y1,x2,y2 = rect.getCoords();
    line = TiggerPlotCurve();
    line.setData([x1,x1,x2,x2,x1],[y1,y2,y2,y1,y1]);
#      line.setBrush(self._stats_brush);
    line.setPen(pen);
    label = TiggerPlotMarker();
    label.setValue(max(x1,x2),max(y1,y2));
    text = QwtText("stats");
    text.setColor(pen.color());
    label.setLabel(text);
    label.setLabelAlignment(Qt.AlignBottom|Qt.AlignRight);
    return [ line,label ];

  def _selectImageSubset (self,rect,image=None):
    # make zoom button visible if subset is selected
    self._qa_colorzoom.setVisible(bool(rect));
    self._image_subset = rect;
    if rect is None:
      self._removePlotMarkup();
    else:
      # get image stats
      busy = BusyIndicator();
      stats = self._imgman.getLMRectStats(self._image_subset);
      busy = None;
      if stats is None:
        self._removePlotMarkup();
        self._image_subset = None;
        return;
      # make tooltip
      DataValueFormat = "%.4g";
      stats = list(stats);
      stats1 = tuple(stats[:4] + [ DataValueFormat%s for s in stats[4:9] ] + stats[9:]);
      msgtext = "[%d:%d,%d:%d] min %s, max %s, mean %s, std %s, sum %s, np %d"%stats1;
      tiptext = """<P><NOBR>Region: [%d:%d,%d:%d]</NOBR><BR>
        <NOBR>Stats: min %s, max %s, mean %s, std %s, sum %s, np %d</NOBR></BR>
        Use the "Colour zoom" button on the left (or press Shift+F4) to set the current data subset and
        intensity range to this image region.</P>"""%stats1;
      # make markup on plot to indicate current subset
      markup_items = self._makeRectMarker(rect,self._stats_pen);
      # calling QToolTip.showText() directly from here doesn't work, so set a timer on it
      QTimer.singleShot(10,self._currier.curry(self._showCoordinateToolTip,tiptext));
      # same deal for markup items
      for item in markup_items:
        item.setZ(Z_Markup);
      QTimer.singleShot(10,self._currier.curry(self._addPlotMarkup,markup_items));
      print msgtext;
      QApplication.clipboard().setText(msgtext+"\n");
      QApplication.clipboard().setText(msgtext+"\n",QClipboard.Selection);

  def _colourZoomIntoSubset (self):
    # zoom into current image subset (if any), and hide the zoom button
    dprint(1,self._image_subset);
    if self._image_subset is not None:
      self._imgman.setLMRectSubset(self._image_subset);
      self._removePlotMarkup();
      self._image_subset = None;
    self._qa_colorzoom.setVisible(False);

  def _selectRectStats (self,rect):
      image = self._imgman and self._imgman.getTopImage();
      dprint(1,"subset selection",rect,"image:",image and image.boundingRect());
      if not image or not rect.intersects(image.boundingRect()):
        self._selectImageSubset(None);
        return;
      zoomrect = image.boundingRect().intersected(rect);
      dprint(1,"selecting image subset",zoomrect);
      self._selectImageSubset(zoomrect,image);

  def _selectRect (self,rect,world=True,mode=SelectionClear|SelectionAdd):
    """Selects sources within the specified rectangle. For meaning of 'mode', see flags above.
        'rect' is a QRectF/QwtDoubleRect object in lm coordinates if world=True, else a QRect object in screen coordinates."""
    dprint(1,"selectRect",rect);
    if not world:
      rect = self.plot.screenRectToLm(rect);
    sources = [ marker.source() for marker in self._markers.itervalues() if marker.isVisible() and rect.contains(marker.lmQPointF()) ];
    if sources:
      self._selectSources(sources,mode);

  def _finalizeProvisionalZoom(self):
    if self._provisional_zoom is not None:
      self._zoomer.zoom(self._provisional_zoom);

  def _plotProvisionalZoom (self,x,y,level,timeout=200):
    """Called when mouse wheel is used to zoom in our out""";
    self._provisional_zoom_level += level;
    self._zoomer_box.setVisible(False);
    self._zoomer_label.setVisible(False);
    if self._provisional_zoom_level > 0:
      # make zoom box of size 2^level smaller than current screen
      x1,y1,x2,y2 = self._zoomer.zoomRect().getCoords();
      w = (x2-x1)/2**self._provisional_zoom_level;
      h = (y2-y1)/2**self._provisional_zoom_level;
      self._provisional_zoom = QRectF(x-w/2,y-h/2,w,h);
      x1,y1,x2,y2 = self._provisional_zoom.getCoords();
      self._zoomer_box.setData([x1,x2,x2,x1,x1],[y1,y1,y2,y2,y1]);
      self._zoomer_label.setValue(max(x1,x2),max(y1,y2));
      self._zoomer_label_text.setText("zoom");
      self._zoomer_label.setLabel(self._zoomer_label_text);
      self._zoomer_box.setVisible(True);
      self._zoomer_label.setVisible(True);
    else:
      maxout = -self._zoomer.zoomRectIndex();
      self._provisional_zoom_level = level = max(self._provisional_zoom_level,maxout);
      if self._provisional_zoom_level < 0:
        self._zoomer_label.setValue(x,y);
        self._zoomer_label_text.setText("zoom out %d"%abs(level) if level != maxout else "zoom out full");
        self._zoomer_label.setLabel(self._zoomer_label_text);
        self._zoomer_label.setVisible(True);
        self._provisional_zoom = int(self._provisional_zoom_level);
      else:
        self._provisional_zoom = None;
    QTimer.singleShot(5,self._replot);
    self._provisional_zoom_timer.start(timeout);

  def _plotZoomed (self,rect):
    dprint(2,"zoomed to",rect);
    self._zoomer_box.setVisible(False);
    self._zoomer_label.setVisible(False);
    self._provisional_zoom = None;
    self._provisional_zoom_level = 0;
    self._zoomrect = QRectF(rect); # make copy
    self._qa_unzoom.setEnabled(rect != self._zoomer.zoomBase());
    self._updatePsfMarker(rect,replot=True);

  def _setGridCircleStepping (self,arcsec=DefaultGridStep_ArcSec):
    """Changes the visible grid circles. None to disable.""";
    self._grid_step_arcsec = arcsec;
    self._updateContents();

  def _setCustomGridCircleStepping (self):
    """Opens dialog to get a custom grid step.""";
    text,ok = QInputDialog.getText(self,"Set custom grid step","""<P>
      Specify a custom grid stepping as a value and a unit string.<BR>Recognized unit strings are
      d or deg, ' (single quote) or arcmin, and " (double quote) or arcsec.<BR>Default is arcmin.</P>""",
      text=self._grid_step_arcsec_str);
    if text:
      match = re.match("([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)(d|deg|['\"]|arcmin)?$",text,re.I);
      try:
        value = float(match.group(1));
      except:
        QMessageBox.warning(self,"Invalid input","Invalid input: \"%s\""%text);
        return;
      if round(value) == value:
        value = int(value);
      unit = match.group(5);
      if unit in ("d","deg"):
        value *= 3600;
      elif not unit or unit in ("'","arcmin"):
        value *= 60;
    self._setGridCircleStepping(value or None);
    self._setCustomGridCircleSteppingLabel();

  def _setCustomGridCircleSteppingLabel (self):
    """Changes the label of the custom grid step action.""";
    step = self._grid_step_arcsec;
    if not step:
      self._grid_step_arcsec_str = "";
    elif step < 60:
      self._grid_step_arcsec_str = ("%f\"" if isinstance(step,float) else "%d\"")%step;
    elif step < 3600:
      self._grid_step_arcsec_str = ("%f'" if step%60 else "%d'")%(step/60.);
    else:
      self._grid_step_arcsec_str = ("%fdeg" if step%3600 else "%ddeg")%(step/3600.);
    if self._grid_step_arcsec_str:
      self._qa_custom_grid.setText("Custom (%s)..."%self._grid_step_arcsec_str);
    else:
      self._qa_custom_grid.setText("Custom...");

  def _updateContents (self,what=SkyModel.UpdateAll,origin=None):
    # do nothing if updates are disabled (this is possible on startup, or when multiple
    # things are being loaded), or if update is of no concern to us
    if not self._updates_enabled or not what&(SkyModel.UpdateSourceList|SkyModel.UpdateSourceContent|self.UpdateImages):
      return;
    # clear any plot markup
    dprint(2,"clearing plot markup");
    for item in self._plot_markup:
      item.detach();
    self._plot_markup = [];
    self._image_subset = None;
    # clear plot, but do not delete items
    self.projection = None;
    self.plot.clear();
    self._psf_marker.attach(self.plot);
    self._zoomer_box.attach(self.plot);
    self._zoomer_label.attach(self.plot);
    self._zoomer_box.setVisible(False);
    self._zoomer_label.setVisible(False);
    # get current image (None if no images)
    self._image = self._imgman and self._imgman.getCenterImage();
    # show/hide live zoomer with image
    if self._image:
      for tool in self._livezoom,self._liveprofile:
        tool.makeAvailable(bool(self._image));
    # enable or disable mouse modes as appropriate
    self._mousemodes.setContext(has_image=bool(self._image),has_model=bool(self.model));
    # do nothing if no image and no model
    if not self._image and not self.model:
      self.plot.setEnabled(False);
      return;
    self.plot.setEnabled(True);
    # Use projection of first image, or 'Sin' by default
    if self._image:
      self.projection = self._image.projection;
      dprint(1,"using projection from image",self._image.name);
      ra,dec = self.projection.radec(0,0);
    else:
      self.projection = Projection.SinWCS(*self.model.fieldCenter());
      dprint(1,"using default Sin projection");
    # compute lm: dict from source ID to l,m tuple
    if self.model:
      self._source_lm = dict([(id(src),self.projection.lm(src.pos.ra,src.pos.dec)) for src in self.model.sources]);
    # now find plot extents
    extent= [[0,0],[0,0]];
    for iext in 0,1:
      if self._source_lm:
        xmin = extent[iext][0] = min([lm[iext] for lm in self._source_lm.itervalues()]);
        xmax = extent[iext][1] = max([lm[iext] for lm in self._source_lm.itervalues()]);
        # add 5% on either side
        margin = .05*(xmax - xmin);
        extent[iext][0] -= margin;
        extent[iext][1] += margin;
        dprint(2,"plot extents for model",extent);
    # account for bounding rects of images
    # TODO: check that images are visible
    for img in ((self._imgman and self._imgman.getImages()) or []):
      ext = img.getExtents();
      dprint(2,"image extents",ext);
      for i in 0,1:
        extent[i][0] = min(extent[i][0],ext[i][0]);
        extent[i][1] = max(extent[i][1],ext[i][1]);
    # if margins still not set, force them to 1x1 degree
    for i in 0,1:
      if extent[i][0] == extent[i][1]:
        extent[i] = [-DEG*0.5,DEG*0.5 ];
    dprint(2,"plot extents for model & images",extent);
    (lmin,lmax),(mmin,mmax) = extent;
    # adjust plot limits, if a fixed ratio is in effect, and set the zoom base
    zbase = QRectF(QPointF(lmin,mmin),QPointF(lmax,mmax));
#    zbase = self._zoomer.adjustRect(zbase);
    zooms = [ zbase ];
    dprint(2,"zoom base, adjusted for aspect:",zbase);
    # zooms = [ self._zoomer.adjustRect(zbase) ];
    # if previously set zoom rect intersects the zoom base at all (and is not a superset), try to restore it
    dprint(2,"previous zoom area:",self._zoomrect);
    if self._zoomrect and self._zoomrect.intersects(zbase):
      rect = self._zoomrect.intersected(zbase);
#      rect = self._zoomer.adjustRect(self._zoomrect.intersected(zbase));
      if rect != zbase:
        dprint(2,"will restore zoomed area",rect);
        zooms.append(rect);
    self._qa_unzoom.setEnabled(len(zooms)>1);
    self._provisional_zoom_level = 0;
#    dprint(2,"adjusted for aspect ratio",lmin,lmax,mmin,mmax);
    # reset plot limits   -- X axis inverted (L increases to left)
#    lmin,lmax,mmin,mmax = zbase.left(),zbase.right(),zbase.top(),zbase.bottom();
#    self.plot.setAxisScale(QwtPlot.yLeft,mmin,mmax);
#    self.plot.setAxisScale(QwtPlot.xBottom,lmax,lmin);
#    self.plot.axisScaleEngine(QwtPlot.xBottom).setAttribute(QwtScaleEngine.Inverted, True);
#    dprint(2,"setting zoom base",zbase);
#    self._zoomer.setZoomBase(zbase);
    dprint(5,"drawing grid");
    # add grid lines & circles
    circstep = self._grid_step_arcsec;
    if circstep:
      self._grid = [ TiggerPlotCurve(),TiggerPlotCurve() ];
      self._grid[0].setData([lmin,lmax],[0,0]);
      self._grid[1].setData([0,0],[mmin,mmax]);
      # see how many units (of arcminute) fit in max diagonal direction
      maxr = int(round(math.sqrt(lmax**2+mmax**2)/(DEG/3600)));
      # cache sines and cosines of curve argument
      angles = numpy.array(range(0,361,5))*DEG;
      sines = numpy.sin(angles);
      cosines = numpy.cos(angles);
      # make circles
      for r in numpy.arange(circstep,maxr,circstep):
        # find radius in each direction, by projecting a point
        rl ,dum= self.projection.offset(r*DEG/3600,0);
        dum,rm = self.projection.offset(0,r*DEG/3600);
        # make curve
        curve = TiggerPlotCurve();
        x ,y = rl*cosines,rm*sines;
        curve.setData(x,y);
        curve.setCurveAttribute(QwtPlotCurve.Fitted,True);
        self._grid.append(curve);
        # make a text label and marker
        marker = TiggerPlotMarker();
        m,s = divmod(r,60);
        d,m = divmod(m,60);
        if d:
          label = "%d&deg;%02d'%02d\""%(d,m,s) if s else ("%d&deg;%02d'"%(d,m) if m else "%d&deg;"%d);
        elif m:
          label = "%d'%02d\""%(m,s) if s else "%d'"%m;
        else:
          label = "%d\""%s;
        text = QwtText(label,QwtText.RichText);
        text.setColor(self._grid_color);
        marker.setValue(x[0],y[0]);
        marker.setLabel(text);
        marker.setLabelAlignment(Qt.AlignRight|Qt.AlignBottom);
        marker.setZ(Z_Grid);
        marker.attach(self.plot);
      for gr in self._grid:
        gr.setPen(self._grid_pen);
        gr.setZ(Z_Grid);
        gr.attach(self.plot);
    # make a new set of source markers, since either the image or the model may have been updated
    if self.model:
      dprint(5,"making skymodel markers");
      # compute min/max brightness
      # brightnesses <=1e-20 are specifically excluded (as they're probably "dummy" sources, etc.)
      b = [ abs(src.brightness()) for src in self.model.sources if abs(src.brightness()) > 1e-20 ];
      self._min_bright = min(b) if b else 0;
      self._max_bright = max(b) if b else 0;
      # make items for every object in the model
      self._markers = {};
      for isrc,src in enumerate(self.model.sources):
        l,m = self._source_lm[id(src)];
        self._markers[src.name] = marker = makeSourceMarker(src,l,m,self.getSymbolSize(src),self.model,self._imgman);
    # now (re)attach the source markers, since the plot has been cleared
    for marker in self._markers.itervalues():
      marker.attach(self.plot);
    # attach images to plot
    if self._imgman:
      dprint(5,"attaching images");
      self._imgman.attachImagesToPlot(self.plot);
    # update the PlotZoomer with our set of zooms. This implictly causes a plot update
    dprint(5,"updating zoomer");
    self._zoomer.setZoomStack(zooms,len(zooms)-1);
    self._updatePsfMarker(None,replot=True);
    # self.plot.replot();

  def setModel (self,model):
    self._source_lm = {};
    self._markers = {};
    self.model = model;
    dprint(2,"setModel",model);
    if model :
      # connect signals
      self.model.connect("updated",self.postUpdateEvent);
      self.model.connect("selected",self.updateModelSelection);
      self.model.connect("changeCurrentSource",self.setCurrentSource);
      self.model.connect("changeGroupingStyle",self.changeGroupingStyle);
    # update plot
    self.postUpdateEvent(SkyModel.UpdateAll);

  def _exportPlotToPNG (self,filename=None):
    if not filename:
      if not self._export_png_dialog:
          dialog = self._export_png_dialog = QFileDialog(self,"Export plot to PNG",".","*.png");
          dialog.setDefaultSuffix("png");
          dialog.setFileMode(QFileDialog.AnyFile);
          dialog.setAcceptMode(QFileDialog.AcceptSave);
          dialog.setModal(True);
          QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self._exportPlotToPNG);
      return self._export_png_dialog.exec_() == QDialog.Accepted;
    busy = BusyIndicator();
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = str(filename);
    # make QPixmap
    pixmap = QPixmap(self.plot.width(),self.plot.height());
    pixmap.fill(self._bg_color);
    painter = QPainter(pixmap);
    # use QwtPlot implementation of draw canvas, since we want to avoid caching
    QwtPlot.drawCanvas(self.plot,painter);
    painter.end();
    # save to file
    try:
      pixmap.save(filename,"PNG");
    except Exception,exc:
      self.emit(SIGNAL("showErrorMessage"),"Error writing %s: %s"%(filename,str(exc)));
      return;
    self.emit(SIGNAL("showMessage"),"Exported plot to file %s"%filename);

  def setCurrentSource (self,src,src0=None,origin=None):
    dprint(2,"setCurrentSource",src and src.name,src0 and src0.name,origin);
    if self.model and self.model.curgroup.style.apply:
      for s in src,src0:
        marker = s and self._markers.get(s.name);
        marker and marker.resetStyle();
      self.plot.clearDrawCache();
      self.plot.replot();

  def updateModelSelection (self,nsel=0,origin=None):
    """This is callled when something changes the set of selected model sources""";
    # call checkSelected() on all plot markers, replot if any return True
    if filter(lambda marker:marker.checkSelected(),self._markers.itervalues()):
      self.plot.clearDrawCache();
      self.plot.replot();

  def changeGroupingStyle (self,group,origin=None):
    # call changeStyle() on all plot markers, replot if any return True
    if filter(lambda marker:marker.changeStyle(group),self._markers.itervalues()):
      self.plot.clearDrawCache();
      self.plot.replot();

  def getSymbolSize (self,src):
    return (max(math.log10(abs(src.brightness())) - math.log10(self._min_bright)+1,1))*3;
