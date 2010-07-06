# -*- coding: utf-8 -*-
from PyQt4.Qt import *
from PyQt4.Qwt5 import *
import math
import os.path
import time
import numpy

import Kittens.utils

from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

_verbosity = Kittens.utils.verbosity(name="plot");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Models import ModelClasses,PlotStyles
from Coordinates import Projection
from  Models.SkyModel import SkyModel
from Tigger import pixmaps,Config
import MainWindow

# plot Z depths for various classes of objects
Z_Image = 1000;
Z_Grid = 9000;
Z_Source = 10000;
Z_SelectedSource = 10001;
Z_CurrentSource = 10002;

# default stepping of grid circles
DefaultGridStep_ArcMin = 30;

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
    self.plotmarker = QwtPlotMarker();
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
    self.imagecon = imgman.loadImage(src.shape.filename,duplicate=False,model=src.name);
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
  def __init__ (self,parent,configname):
    QDialog.__init__(self,parent);
    self.setModal(False);
    self.setFocusPolicy(Qt.NoFocus);
    self.hide();
    self._configname = configname;
    self._geometry = None;

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
    ToolDialog.__init__(self,parent,configname="livezoom");
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
    self._reticules = QwtPlotCurve(),QwtPlotCurve();
    for curve in self._reticules:
      curve.setPen(QPen(QColor("green")));
      curve.setStyle(QwtPlotCurve.Lines);
      curve.attach(self._zoomplot);
      curve.setZ(1);
    # setup cross-section curves
    pen = makeDualColorPen("navy","yellow");
    self._xcs = QwtPlotCurve();
    self._ycs = QwtPlotCurve();
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
    ToolDialog.__init__(self,parent,configname="liveprofile");
    self.setWindowTitle("Profiles");
    # add plots
    lo0 = QVBoxLayout(self);
    lo0.setSpacing(0);
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1);
    lab = QLabel("Profile axis: ",self);
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
    self._profcurve = QwtPlotCurve();
    self._ycs = QwtPlotCurve();
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
  MouseSubset = 1;
  MouseSelect = 2;
  MouseDeselect = 3;

  class Plot (QwtPlot):
    """Auguments QwtPlot with additional functions, including a cache of QPoints thatr's cleared whenever a plot layout is
    updated of the plot is zoomed""";
    def __init__ (self,mainwin,*args):
      QwtPlot.__init__(self,*args);
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
      dprint(5,"updateLayout");
      self.clearCaches();
      res = QwtPlot.updateLayout(self);
      self.emit(SIGNAL("updateLayout"));
      return res;

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
      self._track_callback = track_callback;
      if label:
        self._label = QwtText(label);
      else:
        self._label = QwtText("");
      self._fixed_aspect = False;
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

    def _checkAspects (self):
      """If fixed-aspect mode is in effect, goes through zoom rects and adjusts them to the plot aspect""";
      if self._fixed_aspect:
        dprint(2,"plot canvas size is",self.plot().size());
        dprint(2,"zoom rects are",self._zoomrects);
        stack = map(self.adjustRect,self._zoomrects);
        self.setZoomStack(stack,self.zoomRectIndex());
        dprint(2,"new zoom stack is",stack);

    def setZoomBase (self,zbase):
      QwtPlotZoomer.setZoomBase(self);
      # init list of desired zoom rects
      self._zoomrects = [ QRectF(zbase) ];
      dprint(2,"zoom base is",self._zoomrects);

    def adjustRect (self,rect):
      """Adjusts rectangle w.r.t. aspect ratio settings. That is, if a fixed aspect ratio is in effect, adjusts the rectangle to match
      the aspect ratio of the plot canvas. Returns adjusted version."""
      if self._fixed_aspect:
        aspect0 = self.canvas().width()/float(self.canvas().height());
        aspect = rect.width()/float(rect.height());
        # increase rectangle, if needed to match the aspect
        if aspect < aspect0:
          dx = rect.width()*(aspect0/aspect-1)/2;
          return rect.adjusted(-dx,0,dx,0);
        elif aspect > aspect0:
          dy = rect.height()*(aspect/aspect0-1)/2;
          return rect.adjusted(0,-dy,0,dy);
      return rect;

    def rescale (self):
      self.plot().clearCaches();
      return QwtPlotZoomer.rescale(self);

    def zoom (self,rect):
      if isinstance(rect,int) or rect.intersected(self.zoomBase()) == rect:
        dprint(2,"zoom",rect);
        if not isinstance(rect,int):
          self._zoomrects[self.zoomRectIndex()+1:] = [ QRectF(rect) ];
          rect = self.adjustRect(rect);
          dprint(2,"zooming to",rect);
        QwtPlotZoomer.zoom(self,rect);
        dprint(2,"zoom stack is now",self.zoomStack());
      else:
        dprint(2,"invalid zoom selected, ignoring");

    def trackerText (self,pos):
      return (self._track_callback and self._track_callback(pos)) or (self._label if self.isActive() else QwtText(""));

  class PlotPicker (QwtPlotPicker):
    """Auguments QwtPlotPicker with functions for selecting objects""";
    def __init__ (self,canvas,label,color="red",select_callback=None,track_callback=None,
                        mode=QwtPicker.RectSelection,rubber_band=QwtPicker.RectRubberBand,text_bg=None):
      QwtPlotPicker.__init__(self,QwtPlot.xBottom,QwtPlot.yLeft,mode,rubber_band,QwtPicker.ActiveOnly,canvas);
      # setup appearance
      self._text = QwtText(label);
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
        else:
          QObject.connect(self,SIGNAL("selected(const QwtDoublePoint &)"),select_callback);

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
        return text;

  def __init__ (self,parent,mainwin,*args):
    QWidget.__init__(self,parent,*args);
    self._currier = PersistentCurrier();
    lo = QHBoxLayout(self);
    lo.setSpacing(0);
    lo.setContentsMargins(0,0,0,0);
    self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);
    self.plot  = self.Plot(self,mainwin);
    self.plot.setAutoDelete(False);
    self.plot.setEnabled(False);
    self.plot.enableAxis(QwtPlot.yLeft,False);
    self.plot.enableAxis(QwtPlot.xBottom,False);
    lo.addWidget(self.plot);
    # setup plot groupings
    self._zoomer = None;
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
    # attach zoomer if None
    self._zoomer = self.PlotZoomer(self.plot.canvas(),track_callback=self._trackCoordinates,label="zoom");
    zpen = makeDualColorPen("navy","yellow");
    self._zoomer.setRubberBandPen(zpen);
    self._zoomer.setTrackerPen(QColor("navy"));
    self._zoomer.setTrackerMode(QwtPicker.AlwaysOn);
    QObject.connect(self._zoomer,SIGNAL("zoomed(const QwtDoubleRect &)"),self._plotZoomed);
    # attach object pickers
    # selection pickers
    self._picker1 = self.PlotPicker(self.plot.canvas(),"select","green",self._selectRect,track_callback=self._trackCoordinates);
    self._picker1.setTrackerMode(QwtPicker.AlwaysOn);
    self._picker1.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton);
    self._picker2 = self.PlotPicker(self.plot.canvas(),"+select","green",curry(self._selectRect,mode=self.SelectionAdd));
    self._picker2.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton,Qt.SHIFT);
    self._picker3 = self.PlotPicker(self.plot.canvas(),"select","green",self._selectNearestSource,mode=QwtPicker.PointSelection);
    self._picker3.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton,Qt.CTRL);
    # live zoomer
    self._livezoom = LiveImageZoom(self);
    self._liveprofile = LiveProfile(self);
    # other internal init
    self._markers = {};
    self.model = None;
    self.projection = None;
    self._text_no_source = QwtText("");
    self._text_no_source.setColor(QColor("red"));
    # image controller
    self._updates_enabled = False;
    self._imgman = self._image = None;
    self._markers = {};
    self._source_lm = {};
    self._export_png_dialog = None;
    # menu and toolbar
    self._menu = QMenu("&Plot",self);
    self._wtoolbar = QToolBar(self);
    self._wtoolbar.setOrientation(Qt.Vertical);
    lo.insertWidget(0,self._wtoolbar);
    self._qag_mousemode = QActionGroup(self);
    self._qa_unzoom = self._wtoolbar.addAction(pixmaps.zoom_out.icon(),"Unzoom plot",self._currier.curry(self._zoomer.zoom,0));
    self._qa_unzoom.setShortcut(Qt.ALT+Qt.Key_Minus);
    self._wtoolbar.addSeparator();
    self._menu.addAction(self._qa_unzoom);
    # mouse mode controls
    mouse_menu = self._menu.addMenu("Mouse mode");
    self._qa_mm = [
      mouse_menu.addAction(pixmaps.zoom_in.icon(),"Zoom",self._currier.curry(self.setMouseMode,self.MouseZoom),Qt.Key_F4),
      mouse_menu.addAction(pixmaps.zoom_colours.icon(),"Select image subset",self._currier.curry(self.setMouseMode,self.MouseSubset)),
      mouse_menu.addAction(pixmaps.big_plus.icon(),"Select objects",self._currier.curry(self.setMouseMode,self.MouseSelect)),
      mouse_menu.addAction(pixmaps.big_minus.icon(),"Deselect objects",self._currier.curry(self.setMouseMode,self.MouseDeselect)) ];
    for qa in self._qa_mm:
      self._qag_mousemode.addAction(qa);
      qa.setCheckable(True);
      self._wtoolbar.addAction(qa);
    self.setMouseMode(self.MouseZoom);
    # hide/show zoomer
    self._qa_showlivezoom = qa = QAction("Show quick zoom && cross-sections",self);
    qa.setShortcut(Qt.Key_F2);
    qa.setCheckable(True);
    qa.setChecked(True);
    qa.setVisible(False);
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._livezoom.setVisible);
    QObject.connect(self._livezoom,SIGNAL("isVisible"),qa.setChecked);
    self._menu.addAction(qa);
    # hide/show profile
    self._qa_showliveprof = qa = QAction("Show profiles",self);
    qa.setShortcut(Qt.Key_F3);
    qa.setCheckable(True);
    qa.setChecked(False);
    qa.setVisible(False);
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._liveprofile.setVisible);
    QObject.connect(self._liveprofile,SIGNAL("isVisible"),qa.setChecked);
    self._menu.addAction(qa);
    # fixed aspect
    qa = self._menu.addAction("Fix aspect ratio");
    qa.setCheckable(True);
    qa.setChecked(True);
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._zoomer.setFixedAspect);
    self._zoomer.setFixedAspect(True);
    # save as PNG file
    self._menu.addAction("Export plot to PNG file...",self._exportPlotToPNG);

  def close (self):
    self._livezoom.close();
    self._liveprofile.close();

  def getMenu (self):
    return self._menu;

  def enableUpdates (self,enable=True):
    self._updates_enabled = enable;
    if enable:
      self._updateContents();

  # extra flag for updateContents() -- used when image content or projection has changed
  UpdateImages = 1<<16;

  def setImageManager (self, im):
    """Attaches an image manager."""
    self._imgman = im;
    im.setZ0(Z_Image);
    im.enableImageBorders(self._image_pen,self._grid_color,self._bg_brush);
    QObject.connect(im,SIGNAL("imagesChanged"),self._currier.curry(self._updateContents,self.UpdateImages));

  def enableMouseMode (self,mode,enable=True):
    """Enables or disables the given mode.""";
    qa = self._qa_mm[mode];
    qa.setVisible(enable);
    # if disabled the currently checked mode, reset mode to default (zoom)
    if not enable and qa.isChecked():
      self._mouse_mode = self.MouseZoom;
    # call setMouseMode() function to readjust GUI (change shortcuts, etc.)
    self.setMouseMode(self._mouse_mode);

  def setMouseMode (self,mode):
    """Sets the current mouse mode, updates action shortcuts""";
    dprint(1,"setting mouse mode",mode);
    self._mouse_mode = mode;
    self._qa_mm[mode].setChecked(True);
    # remove shortcuts from all actions
    for qa in self._qa_mm:
      qa.setShortcut(QKeySequence());
    # set shortcut on the next visible action after the checked one
    self._qa_mm[mode].setChecked(True);
    next = (mode+1)%len(self._qa_mm);
    while not self._qa_mm[next].isVisible():
      next = (next+1)%len(self._qa_mm);
    self._qa_mm[next].setShortcut(Qt.Key_F4);
    # disable/enable pickers accordingly
    # picker1 is for selecting rectangles: active for intensity zoom mode, and for selection modes
    # picker2 is for selecting rectangles with SHIFT. Active for selection modes only.
    # picker3 is for selecting sources with CTRL. Always active.
    self._zoomer.setEnabled(mode == self.MouseZoom);
    self._picker1.setEnabled(mode != self.MouseZoom);
    self._picker2.setEnabled(mode in (self.MouseSelect,self.MouseDeselect));
    self._picker3.setLabel("+select",color="green");
    if mode == self.MouseSubset:
      self._picker1.setLabel("subset ",color="blue");
    elif mode == self.MouseSelect:
      self._picker1.setLabel("select ",color="green");
      self._picker2.setLabel("+",color="green");
    elif mode == self.MouseDeselect:
      self._picker1.setLabel("-select",color="red");
      for p in self._picker2,self._picker3:
        p.setLabel("",color="red");

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

  def _trackCoordinates (self,pos):
    if not self.projection:
      return None;
    # if Ctrl is pushed, get nearest source and make it "current"
    if QApplication.keyboardModifiers()&(Qt.ControlModifier|Qt.ShiftModifier):
      src = self.findNearestSource(pos,world=False,range=range);
      if src:
        self.model.setCurrentSource(src);
    # get ra/dec coordinates of point
    pos = self.plot.screenPosToLm(pos);
    l,m = pos.x(),pos.y();
    ra,dec = self.projection.radec(l,m);
    rh,rm,rs = ModelClasses.Position.ra_hms_static(ra);
    dd,dm,ds = ModelClasses.Position.dec_dms_static(dec);
#    text = "<P align=\"right\">%2dh%02dm%05.2fs %+2d&deg;%02d'%05.2f\""%(rh,rm,rs,dd,dm,ds);
    # emit message as well
    msgtext = u"%2dh%02dm%05.2fs %+2d\u00B0%02d'%05.2f\""%(rh,rm,rs,dd,dm,ds);
    # if we have an image, add pixel coordinates
    image = self._imgman and self._imgman.getTopImage();
    if image:
      x,y = map(int,map(round,image.lmToPix(l,m)));
      nx,ny = image.imageDims();
      if x>=0 and x<nx and y>=0 and y<ny:
#        text += "<BR>x=%d y=%d"%(round(x),round(y));
        msgtext += "   x=%d y=%d value=%g"%(x,y,image.image()[x,y]);
      self._livezoom.trackImage(image,x,y);
      self._liveprofile.trackImage(image,x,y);
#    text += "</P>"
#    text = QwtText(text,QwtText.RichText);
#    if self._coord_bg_brush:
#      text.setBackgroundBrush(self._coord_bg_brush);
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

  def _selectRect (self,rect,world=True,mode=SelectionClear|SelectionAdd):
    """Selects sources within the specified rectangle. For meaning of 'mode', see flags above.
        Note that _mouse_mode == MouseDeselect will force mode=SelectionRemove.
        'rect' is a QRectF/QwtDoubleRect object in lm coordinates if world=True, else a QRect object in screen coordinates."""
    dprint(1,"selectRect",rect);
    if not world:
      rect = self.plot.screenRectToLm(rect);
    # in mouse-zoom mode, do nothing (not supposed to be called anyway)
    if self._mouse_mode == self.MouseZoom:
      return;
    elif self._mouse_mode == self.MouseSubset:
      dprint(1,"intensity zoom into",rect,"image:",self._image.boundingRect());
      if not self._image or not rect.intersects(self._image.boundingRect()):
        return;
      zoomrect = self._image.boundingRect().intersected(rect);
      dprint(1,"intensity zoom into",zoomrect);
      self._imgman.setLMRectSubset(zoomrect);
      self.setMouseMode(self.MouseZoom);
    elif self._mouse_mode in (self.MouseSelect,self.MouseDeselect):
      # deselect mouse mode implies removing from selection
      if self._mouse_mode == self.MouseDeselect:
        mode = self.SelectionRemove;
      # convert rectangle to lm coordinates
      if not world:
        rect = self.plot.screenRectToLm(rect);
      # find sources
      sources = [ marker.source() for marker in self._markers.itervalues() if marker.isVisible() and rect.contains(marker.lmQPointF()) ];
      if sources:
        self._selectSources(sources,mode);

  def _plotZoomed (self,rect):
    dprint(2,"zoomed to",rect);
    self._qa_unzoom.setEnabled(rect != self._zoomer.zoomBase());

  def _updateContents (self,what=SkyModel.UpdateAll,origin=None):
    # do nothing if updates are disabled (this is possible on startup, or when multiple
    # things are being loaded), or if update is of no concern to us
    if not self._updates_enabled or not what&(SkyModel.UpdateSourceList|SkyModel.UpdateSourceContent|self.UpdateImages):
      return;
    # clear plot, but do not delete items
    self.projection = None;
    self.plot.clear();
    # get current image (None if no images)
    self._image = self._imgman and self._imgman.getCenterImage();
    # show/hide live zoomer with image
    if self._image:
      self._qa_showlivezoom.setVisible(True);
      self._qa_showliveprof.setVisible(True);
      self._livezoom.setVisible(self._qa_showlivezoom.isChecked());
      self._liveprofile.setVisible(self._qa_showliveprof.isChecked());
    else:
      self._livezoom.setVisible(False,emit=False);
      self._qa_showlivezoom.setVisible(False);
      self._liveprofile.setVisible(False,emit=False);
      self._qa_showliveprof.setVisible(False);
    # enable or disable mouse modes as appropriate
    self.enableMouseMode(self.MouseSubset,bool(self._image));
    self.enableMouseMode(self.MouseSelect,bool(self.model));
    self.enableMouseMode(self.MouseDeselect,bool(self.model));
    # do nothing if no image and no model
    if not self._image and not self.model:
      self.plot.setEnabled(False);
      return;
    self.plot.setEnabled(True);
    # Use projection of first image, or 'Sin' by default
    if self._image:
      self.projection = self._image.projection;
      dprint(1,"using projection from image",self._image.name);
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
    dprint(2,"plot extents for model & images",extent);
    (lmin,lmax),(mmin,mmax) = extent;
    # adjust plot limits, if a fixed ratio is in effect. This also sets the zoom base.
    zbase = QRectF(QPointF(lmin,mmin),QPointF(lmax,mmax));
    rect = self._zoomer.adjustRect(zbase);
    lmin,lmax,mmin,mmax = rect.left(),rect.right(),rect.top(),rect.bottom();
    dprint(2,"adjusted for aspect ratio",lmin,lmax,mmin,mmax);
    # reset plot limits   -- X axis inverted (L increases to left)
    self.plot.setAxisScale(QwtPlot.yLeft,mmin,mmax);
    self.plot.setAxisScale(QwtPlot.xBottom,lmax,lmin);
    self.plot.axisScaleEngine(QwtPlot.xBottom).setAttribute(QwtScaleEngine.Inverted, True);
    self._zoomer.setZoomBase(zbase);
    dprint(5,"drawing grid");
    # add grid lines
    self._grid = [ QwtPlotCurve(),QwtPlotCurve() ];
    self._grid[0].setData([lmin,lmax],[0,0]);
    self._grid[1].setData([0,0],[mmin,mmax]);
    # add grid circles
    circstep = DefaultGridStep_ArcMin;
    # see how many units (of arcminute) fit in max diagonal direction
    maxr = int(round(math.sqrt(lmax**2+mmax**2)/(DEG/60)));
    # cache sines and cosines of curve argument
    angles = numpy.array(range(0,361,5))*DEG;
    sines = numpy.sin(angles);
    cosines = numpy.cos(angles);
    # make circles
    for r in range(circstep,maxr,circstep):
      # find radius in each direction, by projecting a point
      rl ,dum= self.projection.offset(r*DEG/60,0);
      dum,rm = self.projection.offset(0,r*DEG/60);
      # make curve
      curve = QwtPlotCurve();
      x ,y = rl*cosines,rm*sines;
      curve.setData(x,y);
      curve.setCurveAttribute(QwtPlotCurve.Fitted,True);
      self._grid.append(curve);
      # make a text label and marker
      marker = QwtPlotMarker();
      d,m = divmod(r,60);
      label = ("%d&deg;%02d'"%(d,m) if m else "%d&deg;"%d) if d else "%02d'"%m;
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
      b = [ abs(src.brightness()) for src in self.model.sources ];
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
    # update the plot
    self._qa_unzoom.setEnabled(False);
    self.plot.replot();

  def setModel (self,model):
    self._source_lm = {};
    self._markers = {};
    self.model = model;
    dprint(2,"setModel",model);
    if model :
      # connect signals
      self.model.connect("updated",self._updateContents);
      self.model.connect("selected",self.updateModelSelection);
      self.model.connect("changeCurrentSource",self.setCurrentSource);
      self.model.connect("changeGroupingStyle",self.changeGroupingStyle);
    # update plot
    self._updateContents(SkyModel.UpdateAll);

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
    return (math.log10(abs(src.brightness())) - math.log10(self._min_bright)+1)*3;
