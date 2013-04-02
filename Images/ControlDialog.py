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
# This program is free software; you can redistribute f and/or modify
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
import numpy
import sys
import time
from scipy.ndimage import measurements

import Kittens.utils
from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

from Tigger.Images import SkyImage,Colormaps
from Tigger import pixmaps
from Tigger.Widgets import FloatValidator,TiggerPlotCurve,TiggerPlotMarker

from RenderControl import RenderControl,dprint,dprintf

DataValueFormat = "%.4g";

class Separator (QWidget):
  def __init__ (self,parent,label,extra_widgets=[],style=QFrame.HLine+QFrame.Raised,offset=16):
    QWidget.__init__(self,parent);
    lo = QHBoxLayout(self);
    lo.setContentsMargins(0,0,0,0);
    lo.setSpacing(4);
    if offset:
      frame = QFrame(self);
      frame.setFrameStyle(style);
      frame.setMinimumWidth(offset);
      lo.addWidget(frame,0);
    lo.addWidget(QLabel(label,self),0);
    frame = QFrame(self);
    frame.setFrameStyle(style);
    lo.addWidget(frame,1);
    for w in extra_widgets:
      lo.addWidget(w,0);


class ImageControlDialog (QDialog):
  def __init__ (self,parent,rc,imgman):
    """An ImageControlDialog is initialized with a parent widget, a RenderControl object,
    and an ImageManager object""";
    QDialog.__init__(self,parent);
    image = rc.image;
    self.setWindowTitle("%s: Colour Controls"%image.name);
    self.setWindowIcon(pixmaps.colours.icon());
    self.setModal(False);
    self.image = image;
    self._rc = rc;
    self._imgman = imgman;
    self._currier = PersistentCurrier();

    # init internal state
    self._prev_range = self._display_range = None,None;
    self._hist = None;
    self._geometry = None;

    # create layouts
    lo0 = QVBoxLayout(self);
#    lo0.setContentsMargins(0,0,0,0);

    # histogram plot
    whide = self.makeButton("Hide",self.hide,width=128);
    whide.setShortcut(Qt.Key_F9);
    lo0.addWidget(Separator(self,"Histogram and ITF",extra_widgets=[whide]));
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    self._histplot = QwtPlot(self);
    self._histplot.setAutoDelete(False);
    lo1.addWidget(self._histplot,1);
    lo2 = QHBoxLayout();
    lo2.setContentsMargins(0,0,0,0);
    lo2.setSpacing(2);
    lo0.addLayout(lo2);
    lo0.addLayout(lo1);
    self._wautozoom = QCheckBox("autozoom",self);
    self._wautozoom.setChecked(True);
    self._wautozoom.setToolTip("""<P>If checked, then the histrogram plot will zoom in automatically when
      you narrow the current intensity range.</P>""");
    self._wlogy = QCheckBox("log Y",self);
    self._wlogy.setChecked(True);
    self._ylogscale = True;
    self._wlogy.setToolTip("""<P>If checked, a log-scale Y axis is used for the histogram plot instead of a linear one.""");
    QObject.connect(self._wlogy,SIGNAL("toggled(bool)"),self._setHistLogScale);
    self._whistunzoom  = self.makeButton("",self._unzoomHistogram,icon=pixmaps.full_range.icon());
    self._whistzoomout = self.makeButton("-",self._currier.curry(self._zoomHistogramByFactor,math.sqrt(.1)));
    self._whistzoomin  = self.makeButton("+",self._currier.curry(self._zoomHistogramByFactor,math.sqrt(10)));
    self._whistzoomin.setToolTip("""<P>Click to zoom into the histogram plot by one step. This does not
      change the current intensity range.</P>""");
    self._whistzoomout.setToolTip("""<P>Click to zoom out of the histogram plot by one step. This does not
      change the current intensity range.</P>""");
    self._whistunzoom.setToolTip("""<P>Click to reset the histogram plot back to its full extent.
      This does not change the current intensity range.</P>""");
    self._whistzoom = QwtWheel(self);
    self._whistzoom.setOrientation(Qt.Horizontal);
    self._whistzoom.setMaximumWidth(80);
    self._whistzoom.setRange(10,0);
    self._whistzoom.setStep(0.1);
    self._whistzoom.setTickCnt(30);
    self._whistzoom.setTracking(False);
    QObject.connect(self._whistzoom,SIGNAL("valueChanged(double)"),self._zoomHistogramFinalize);
    QObject.connect(self._whistzoom,SIGNAL("sliderMoved(double)"),self._zoomHistogramPreview);
    self._whistzoom.setToolTip("""<P>Use this wheel control to zoom in/out of the histogram plot.
      This does not change the current intensity range.
      Note that the zoom wheel should also respond to your mouse wheel, if you have one.</P>""");
    # This works around a stupid bug in QwtSliders -- when using the mousewheel, only sliderMoved() signals are emitted,
    # with no final  valueChanged(). If we want to do a fast preview of something on sliderMoved(), and a "slow" final
    # step on valueChanged(), we're in trouble. So we start a timer on sliderMoved(), and if the timer expires without
    # anything else happening, do a valueChanged().
    # Here we use a timer to call zoomHistogramFinalize() w/o an argument.
    self._whistzoom_timer = QTimer(self);
    self._whistzoom_timer.setSingleShot(True);
    self._whistzoom_timer.setInterval(500);
    QObject.connect(self._whistzoom_timer,SIGNAL("timeout()"),self._zoomHistogramFinalize);
    # set same size for all buttons and controls
    width = 24;
    for w in self._whistunzoom,self._whistzoomin,self._whistzoomout:
      w.setMinimumSize(width,width);
      w.setMaximumSize(width,width);
    self._whistzoom.setMinimumSize(80,width);
    self._wlab_histpos_text = "(hover here for help)";
    self._wlab_histpos = QLabel(self._wlab_histpos_text,self);
    self._wlab_histpos.setToolTip("""
      <P>The plot shows a histogram of either the full image or its selected subset
      (as per the "Data subset" section below).</P>
      <P>The current intensity range is indicated by the grey box
      in the plot.</P>
      <P>Use the left mouse button to change the low intensity limit, and the right
      button (on Macs, use Ctrl-click) to change the high limit.</P>
      <P>Use Shift with the left mouse button to zoom into an area of the histogram,
      or else use the "zoom wheel" control or the plus/minus toolbuttons above the histogram to zoom in or out.
      To zoom back out to the full extent of the histogram, click on the rightmost button above the histogram.</P>
      """);
    lo2.addWidget(self._wlab_histpos,1);
    lo2.addWidget(self._wautozoom);
    lo2.addWidget(self._wlogy,0);
    lo2.addWidget(self._whistzoomin,0);
    lo2.addWidget(self._whistzoom,0);
    lo2.addWidget(self._whistzoomout,0);
    lo2.addWidget(self._whistunzoom,0);
    self._zooming_histogram = False;

    sliced_axes = rc.slicedAxes();
    dprint(1,"sliced axes are",sliced_axes);
    self._stokes_axis = None;

    # subset indication
    lo0.addWidget(Separator(self,"Data subset"));
    # sliced axis selectors
    self._wslicers = [];
    if sliced_axes:
      lo1 = QHBoxLayout();
      lo1.setContentsMargins(0,0,0,0);
      lo1.setSpacing(2);
      lo0.addLayout(lo1);
      lo1.addWidget(QLabel("Current slice:  ",self));
      for i,(iextra,name,labels) in enumerate(sliced_axes):
        lo1.addWidget(QLabel("%s:"%name,self));
        if name == "STOKES":
          self._stokes_axis = iextra;
        # add controls
        wslicer = QComboBox(self);
        self._wslicers.append(wslicer);
        wslicer.addItems(labels);
        wslicer.setToolTip("""<P>Selects current slice along the %s axis.</P>"""%name);
        wslicer.setCurrentIndex(self._rc.currentSlice()[iextra]);
        QObject.connect(wslicer,SIGNAL("activated(int)"),self._currier.curry(self._rc.changeSlice,iextra));
        lo2 = QVBoxLayout();
        lo1.addLayout(lo2);
        lo2.setContentsMargins(0,0,0,0);
        lo2.setSpacing(0);
        wminus = QToolButton(self);
        wminus.setArrowType(Qt.UpArrow);
        QObject.connect(wminus,SIGNAL("clicked()"),self._currier.curry(self._rc.incrementSlice,iextra,1));
        if i == 0:
          wminus.setShortcut(Qt.SHIFT+Qt.Key_F7);
        elif i == 1:
          wminus.setShortcut(Qt.SHIFT+Qt.Key_F8);
        wplus = QToolButton(self);
        wplus.setArrowType(Qt.DownArrow);
        QObject.connect(wplus,SIGNAL("clicked()"),self._currier.curry(self._rc.incrementSlice,iextra,-1));
        if i == 0:
          wplus.setShortcut(Qt.Key_F7);
        elif i == 1:
          wplus.setShortcut(Qt.Key_F8);
        wminus.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);
        wplus.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);
        sz = QSize(12,8);
        wminus.setMinimumSize(sz);
        wplus.setMinimumSize(sz);
        wminus.resize(sz);
        wplus.resize(sz);
        lo2.addWidget(wminus);
        lo2.addWidget(wplus);
        lo1.addWidget(wslicer);
        lo1.addSpacing(5);
      lo1.addStretch(1);
    # subset indicator
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo1.setSpacing(2);
    lo0.addLayout(lo1);
    self._wlab_subset = QLabel("Subset: xxx",self);
    self._wlab_subset.setToolTip("""<P>This indicates the current data subset to which the histogram
      and the stats given here apply. Use the "Reset to" control on the right to change the
      current subset and recompute the histogram and stats.</P>""");
    lo1.addWidget(self._wlab_subset,1);

    self._wreset_full = self.makeButton(u"\u2192 full",self._rc.setFullSubset);
    lo1.addWidget(self._wreset_full);
    if sliced_axes:
#      if self._stokes_axis is not None and len(sliced_axes)>1:
#        self._wreset_stokes = self.makeButton(u"\u21920Stokes",self._rc.setFullSubset);
      self._wreset_slice = self.makeButton(u"\u2192 slice",self._rc.setSliceSubset);
      lo1.addWidget(self._wreset_slice);
    else:
      self._wreset_slice = None;

    # min/max controls
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1,0);
    self._wlab_stats = QLabel(self);
    lo1.addWidget(self._wlab_stats,0);
    self._wmore_stats = self.makeButton("more...",self._showMeanStd);
    self._wlab_stats.setMinimumHeight(self._wmore_stats.height());
    lo1.addWidget(self._wmore_stats,0);
    lo1.addStretch(1);

    # intensity controls
    lo0.addWidget(Separator(self,"Intensity mapping"));
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo1.setSpacing(2);
    lo0.addLayout(lo1,0);
    self._range_validator = FloatValidator(self);
    self._wrange = QLineEdit(self),QLineEdit(self);
    self._wrange[0].setToolTip("""<P>This is the low end of the intensity range.</P>""");
    self._wrange[1].setToolTip("""<P>This is the high end of the intensity range.</P>""");
    for w in self._wrange:
      w.setValidator(self._range_validator);
      QObject.connect(w,SIGNAL("editingFinished()"),self._changeDisplayRange);
    lo1.addWidget(QLabel("low:",self),0);
    lo1.addWidget(self._wrange[0],1);
    self._wrangeleft0 = self.makeButton(u"\u21920",self._setZeroLeftLimit,width=32);
    self._wrangeleft0.setToolTip("""<P>Click this to set the low end of the intensity range to 0.</P>""");
    lo1.addWidget(self._wrangeleft0,0);
    lo1.addSpacing(8);
    lo1.addWidget(QLabel("high:",self),0);
    lo1.addWidget(self._wrange[1],1);
    lo1.addSpacing(8);
    self._wrange_full = self.makeButton(None,self._setHistDisplayRange,icon=pixmaps.intensity_graph.icon());
    lo1.addWidget(self._wrange_full);
    self._wrange_full.setToolTip("""<P>Click this to reset the intensity range to the current extent of the histogram plot.</P>""");
    # add menu for display range
    range_menu = QMenu(self);
    wrange_menu = QToolButton(self);
    wrange_menu.setText("Reset to");
    wrange_menu.setToolTip("""<P>Use this to reset the intensity range to various pre-defined settings.</P>""");
    lo1.addWidget(wrange_menu);
    self._qa_range_full = range_menu.addAction(pixmaps.full_range.icon(),"Full subset",self._rc.resetSubsetDisplayRange);
    self._qa_range_hist = range_menu.addAction(pixmaps.intensity_graph.icon(),"Current histogram limits",self._setHistDisplayRange);
    for percent in (99.99,99.9,99.5,99,98,95):
      range_menu.addAction("%g%%"%percent,self._currier.curry(self._changeDisplayRangeToPercent,percent));
    wrange_menu.setMenu(range_menu);
    wrange_menu.setPopupMode(QToolButton.InstantPopup);

    lo1 = QGridLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1,0);
    self._wimap = QComboBox(self);
    lo1.addWidget(QLabel("Intensity policy:",self),0,0);
    lo1.addWidget(self._wimap,1,0);
    self._wimap.addItems(rc.getIntensityMapNames());
    QObject.connect(self._wimap,SIGNAL("currentIndexChanged(int)"),self._rc.setIntensityMapNumber);
    self._wimap.setToolTip("""<P>Use this to change the type of the intensity transfer function (ITF).</P>""");

    # log cycles control
    lo1.setColumnStretch(1,1);
    self._wlogcycles_label = QLabel("Log cycles: ",self);
    lo1.addWidget(self._wlogcycles_label,0,1);
#    self._wlogcycles = QwtWheel(self);
#    self._wlogcycles.setTotalAngle(360);
    self._wlogcycles = QwtSlider(self);
    self._wlogcycles.setToolTip("""<P>Use this to change the log-base for the logarithmic intensity transfer function (ITF).</P>""");
    # This works around a stupid bug in QwtSliders -- see comments on histogram zoom wheel above
    self._wlogcycles_timer = QTimer(self);
    self._wlogcycles_timer.setSingleShot(True);
    self._wlogcycles_timer.setInterval(500);
    QObject.connect(self._wlogcycles_timer,SIGNAL("timeout()"),self._setIntensityLogCycles);
    lo1.addWidget(self._wlogcycles,1,1);
    self._wlogcycles.setRange(1.,10);
    self._wlogcycles.setStep(0.1);
    self._wlogcycles.setTracking(False);
    QObject.connect(self._wlogcycles,SIGNAL("valueChanged(double)"),self._setIntensityLogCycles);
    QObject.connect(self._wlogcycles,SIGNAL("sliderMoved(double)"),self._previewIntensityLogCycles);
    self._updating_imap = False;

    # lock intensity map
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1,0);
#    lo1.addWidget(QLabel("Lock range accross",self));
    wlock = QCheckBox("Lock display range",self);
    wlock.setToolTip("""<P>If checked, then the intensity range will be locked. The ranges of all locked images
      change simultaneously.</P>""");
    lo1.addWidget(wlock);
    wlockall = QToolButton(self);
    wlockall.setIcon(pixmaps.locked.icon());
    wlockall.setText("Lock all to this");
    wlockall.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);
    wlockall.setAutoRaise(True);
    wlockall.setToolTip("""<P>Click this to lock together the intensity ranges of all images.</P>""");
    lo1.addWidget(wlockall);
    wunlockall = QToolButton(self);
    wunlockall.setIcon(pixmaps.unlocked.icon());
    wunlockall.setText("Unlock all");
    wunlockall.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);
    wunlockall.setAutoRaise(True);
    wunlockall.setToolTip("""<P>Click this to unlock the intensity ranges of all images.</P>""");
    lo1.addWidget(wunlockall);
    wlock.setChecked(self._rc.isDisplayRangeLocked());
    QObject.connect(wlock,SIGNAL("clicked(bool)"),self._rc.lockDisplayRange);
    QObject.connect(wlockall,SIGNAL("clicked()"),self._currier.curry(self._imgman.lockAllDisplayRanges,self._rc));
    QObject.connect(wunlockall,SIGNAL("clicked()"),self._imgman.unlockAllDisplayRanges);
    QObject.connect(self._rc,SIGNAL("displayRangeLocked"),wlock.setChecked);

#    self._wlock_imap_axis = [ QCheckBox(name,self) for iaxis,name,labels in sliced_axes ];
#    for iw,w in enumerate(self._wlock_imap_axis):
#      QObject.connect(w,SIGNAL("toggled(bool)"),self._currier.curry(self._rc.lockDisplayRangeForAxis,iw));
#      lo1.addWidget(w,0);
    lo1.addStretch(1);

    # lo0.addWidget(Separator(self,"Colourmap"));
    # color bar
    self._colorbar = QwtPlot(self);
    lo0.addWidget(self._colorbar);
    self._colorbar.setAutoDelete(False);
    self._colorbar.setMinimumHeight(32);
    self._colorbar.enableAxis(QwtPlot.yLeft,False);
    self._colorbar.enableAxis(QwtPlot.xBottom,False);
    # color plot
    self._colorplot = QwtPlot(self);
    lo0.addWidget(self._colorplot);
    self._colorplot.setAutoDelete(False);
    self._colorplot.setMinimumHeight(64);
    self._colorplot.enableAxis(QwtPlot.yLeft,False);
    self._colorplot.enableAxis(QwtPlot.xBottom,False);
    # self._colorplot.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);
    self._colorbar.hide();
    self._colorplot.hide();
    # color controls
    lo1 = QHBoxLayout();
    lo1.setContentsMargins(0,0,0,0);
    lo0.addLayout(lo1,1);
    lo1.addWidget(QLabel("Colourmap:",self));
    # colormap list
    ### NB: use setIconSize() and icons in QComboBox!!!
    self._wcolmaps = QComboBox(self);
    self._wcolmaps.setIconSize(QSize(128,16));
    self._wcolmaps.setToolTip("""<P>Use this to select a different colourmap.</P>""");
    for cmap in self._rc.getColormapList():
      self._wcolmaps.addItem(QIcon(cmap.makeQPixmap(128,16)),cmap.name);
    lo1.addWidget(self._wcolmaps);
    QObject.connect(self._wcolmaps,SIGNAL("activated(int)"),self._rc.setColorMapNumber);
    # add widgetstack for colormap controls
    self._wcolmap_control_stack = QStackedWidget(self);
    self._wcolmap_control_blank = QWidget(self._wcolmap_control_stack);
    self._wcolmap_control_stack.addWidget(self._wcolmap_control_blank);
    lo0.addWidget(self._wcolmap_control_stack);
    self._colmap_controls = [];
    # add controls to stack
    for index,cmap in enumerate(self._rc.getColormapList()):
      if isinstance(cmap,Colormaps.ColormapWithControls):
        controls = cmap.makeControlWidgets(self._wcolmap_control_stack);
        self._wcolmap_control_stack.addWidget(controls);
        QObject.connect(cmap,SIGNAL("colormapChanged"),
            self._currier.curry(self._previewColormapParameters,index,cmap));
        QObject.connect(cmap,SIGNAL("colormapPreviewed"),
            self._currier.curry(self._previewColormapParameters,index,cmap));
        self._colmap_controls.append(controls);
      else:
        self._colmap_controls.append(self._wcolmap_control_blank);

    # connect updates from renderControl and image
    self.image.connect(SIGNAL("slice"),self._updateImageSlice);
    QObject.connect(self._rc,SIGNAL("intensityMapChanged"),self._updateIntensityMap);
    QObject.connect(self._rc,SIGNAL("colorMapChanged"),self._updateColorMap);
    QObject.connect(self._rc,SIGNAL("dataSubsetChanged"),self._updateDataSubset);
    QObject.connect(self._rc,SIGNAL("displayRangeChanged"),self._updateDisplayRange);

    # update widgets
    self._setupHistogramPlot();
    self._updateDataSubset(*self._rc.currentSubset());
    self._updateColorMap(image.colorMap());
    self._updateIntensityMap(rc.currentIntensityMap(),rc.currentIntensityMapNumber());
    self._updateDisplayRange(*self._rc.displayRange());

  def makeButton (self,label,callback=None,width=None,icon=None):
    btn = QToolButton(self);
#    btn.setAutoRaise(True);
    label and btn.setText(label);
    icon and btn.setIcon(icon);
#    btn = QPushButton(label,self);
 #   btn.setFlat(True);
    if width:
      btn.setMinimumWidth(width);
      btn.setMaximumWidth(width);
    if icon:
      btn.setIcon(icon);
    if callback:
      QObject.connect(btn,SIGNAL("clicked()"),callback);
    return btn;

#  def closeEvent (self,ev):
#    ev.ignore();
#    self.hide();

  def hide(self):
    self._geometry = self.geometry();
    QDialog.hide(self);

  def show (self):
    dprint(4,"show entrypoint");
    if self._geometry:
      dprint(4,"setting geometry");
      self.setGeometry(self._geometry);
    if self._hist is None:
      busy = BusyIndicator();
      dprint(4,"updating histogram");
      self._updateHistogram();
      dprint(4,"updating stats");
      self._updateStats(self._subset,self._subset_range);
      busy = None;
    dprint(4,"calling QDialog.show");
    QDialog.show(self);

  # number of bins used to compute intensity transfer function
  NumItfBins = 1000;
  # number of bins used for displaying histograms
  NumHistBins = 500;
  # number of bins used for high-res histograms
  NumHistBinsHi = 10000;
  # colorbar height, as fraction of plot area
  ColorBarHeight = 0.1;

  class HistLimitPicker (QwtPlotPicker):
    """Auguments QwtPlotPicker with functions for selecting hist min/max values""";
    def __init__ (self,plot,label,color="green",mode=QwtPicker.PointSelection,rubber_band=QwtPicker.VLineRubberBand,tracker_mode=QwtPicker.ActiveOnly,track=None):
      QwtPlotPicker.__init__(self,QwtPlot.xBottom,QwtPlot.yRight,mode,rubber_band,tracker_mode,plot.canvas());
      self.plot = plot;
      self.label = label;
      self.track = track;
      self.color = QColor(color);
      self.setRubberBandPen(QPen(self.color));

    def trackerText (self,pos):
      x,y = self.plot.invTransform(QwtPlot.xBottom,pos.x()),self.plot.invTransform(QwtPlot.yLeft,pos.y());
      if self.track:
        text = self.track(x,y);
        if text is not None:
          return text;
      if self.label:
        text = QwtText(self.label%dict(x=x,y=y));
        text.setColor(self.color);
        return text;
      return QwtText();

    def widgetLeaveEvent (self,ev):
      if self.track:
        self.track(None,None);
      QwtPlotPicker.widgetLeaveEvent(self,ev);

  class ColorBarPlotItem (QwtPlotItem):
    def __init__ (self,y0,y1,*args):
      QwtPlotItem.__init__(self,*args);
      self._y0 = y1;
      self._dy = y1-y0;

    def setIntensityMap (self,imap):
      self.imap = imap;

    def setColorMap (self,cmap):
      self.cmap = cmap;

    def draw (self,painter,xmap,ymap,rect):
      """Implements QwtPlotItem.draw(), to render the colorbar on the given painter.""";
      xp1,xp2,xdp,xs1,xs2,xds = xinfo = xmap.p1(),xmap.p2(),xmap.pDist(),xmap.s1(),xmap.s2(),xmap.sDist();
      yp1,yp2,ydp,ys1,ys2,yds = yinfo = ymap.p1(),ymap.p2(),ymap.pDist(),ymap.s1(),ymap.s2(),ymap.sDist();
      # xp: coordinates of pixels xp1...xp2 in data units
      xp = xs1 + (xds/xdp)*(0.5+numpy.arange(int(xdp)));
      # convert y0 and y1 into pixel coordinates
      y0 = yp1 - (self._y0-ys1)*(ydp/yds);
      dy = self._dy*(ydp/yds);
      # remap into an Nx1 image
      qimg = self.cmap.colorize(self.imap.remap(xp.reshape((len(xp),1))));
      # plot image
      painter.drawImage(QRect(xp1,y0,xdp,dy),qimg);

  class HistogramLineMarker (object):
    """Helper class implementing a line marker for a histogram plot""";
    def __init__ (self,plot,color="black",linestyle=Qt.DotLine,align=Qt.AlignBottom|Qt.AlignRight,z=90,label="",zlabel=None,linewidth=1,spacing=2,
                  yaxis=QwtPlot.yRight):
      self.line = TiggerPlotCurve();
      self.color = color = color if isinstance(color,QColor) else QColor(color);
      self.line.setPen(QPen(color,linewidth,linestyle));
      self.marker = TiggerPlotMarker();
      self.marker.setLabelAlignment(align);
      try:
        self.marker.setSpacing(spacing);
      except AttributeError:
        pass;
      self.setText(label);
      self.line.setZ(z);
      self.marker.setZ(zlabel if zlabel is not None else z);
      # set axes -- using yRight, since that is the "markup" z-axis
      self.line.setAxis(QwtPlot.xBottom,yaxis);
      self.marker.setAxis(QwtPlot.xBottom,yaxis);
      # attach to plot
      self.line.attach(plot);
      self.marker.attach(plot);

    def show (self):
      self.line.show();
      self.marker.show();

    def hide (self):
      self.line.hide();
      self.marker.hide();

    def setText (self,text):
      label = QwtText(text);
      label.setColor(self.color);
      self.marker.setLabel(label);


  def _setupHistogramPlot (self):
    self._histplot.setCanvasBackground(QColor("lightgray"));
    self._histplot.setAxisFont(QwtPlot.yLeft,QApplication.font());
    self._histplot.setAxisFont(QwtPlot.xBottom,QApplication.font());
    # add histogram curves
    self._histcurve1 = TiggerPlotCurve();
    self._histcurve2 = TiggerPlotCurve();
    self._histcurve1.setStyle(QwtPlotCurve.Steps);
    self._histcurve2.setStyle(QwtPlotCurve.Steps);
    self._histcurve1.setPen(QPen(Qt.NoPen));
    self._histcurve1.setBrush(QBrush(QColor("slategrey")));
    pen = QPen(QColor("red"));
    pen.setWidth(1);
    self._histcurve2.setPen(pen);
    self._histcurve1.setZ(0);
    self._histcurve2.setZ(100);
#    self._histcurve1.attach(self._histplot);
    self._histcurve2.attach(self._histplot);
    # add maxbin and half-max curves
    self._line_0       = self.HistogramLineMarker(self._histplot,color="grey50",linestyle=Qt.SolidLine,align=Qt.AlignTop|Qt.AlignLeft,z=90);
    self._line_mean    = self.HistogramLineMarker(self._histplot,color="black",linestyle=Qt.SolidLine,align=Qt.AlignBottom|Qt.AlignRight,z=91,
          label="mean",zlabel=151);
    self._line_std     = self.HistogramLineMarker(self._histplot,color="black",linestyle=Qt.SolidLine,align=Qt.AlignTop|Qt.AlignRight,z=91,
          label="std",zlabel=151);
    sym = QwtSymbol();
    sym.setStyle(QwtSymbol.VLine);
    sym.setSize(8);
    self._line_std.line.setSymbol(sym);
    self._line_maxbin  = self.HistogramLineMarker(self._histplot,color="green",linestyle=Qt.DotLine,align=Qt.AlignTop|Qt.AlignRight,z=92,
          label="max bin",zlabel=150);
    self._line_halfmax = self.HistogramLineMarker(self._histplot,color="green",linestyle=Qt.DotLine,align=Qt.AlignBottom|Qt.AlignRight,z=90,
          label="half-max",yaxis=QwtPlot.yLeft);
    # add current range
    self._rangebox = TiggerPlotCurve();
    self._rangebox.setStyle(QwtPlotCurve.Steps);
    self._rangebox.setYAxis(QwtPlot.yRight);
    self._rangebox.setPen(QPen(Qt.NoPen));
    self._rangebox.setBrush(QBrush(QColor("darkgray")));
    self._rangebox.setZ(50);
    self._rangebox.attach(self._histplot);
    self._rangebox2 = TiggerPlotCurve();
    self._rangebox2.setStyle(QwtPlotCurve.Sticks);
    self._rangebox2.setYAxis(QwtPlot.yRight);
    self._rangebox2.setZ(60);
#  self._rangebox2.attach(self._histplot);
    # add intensity transfer function
    self._itfcurve = TiggerPlotCurve();
    self._itfcurve.setStyle(QwtPlotCurve.Lines);
    self._itfcurve.setPen(QPen(QColor("blue")));
    self._itfcurve.setYAxis(QwtPlot.yRight);
    self._itfcurve.setZ(120);
    self._itfcurve.attach(self._histplot);
    self._itfmarker = TiggerPlotMarker();
    label = QwtText("ITF");
    label.setColor(QColor("blue"));
    self._itfmarker.setLabel(label);
    try:
      self._itfmarker.setSpacing(0);
    except AttributeError:
      pass;
    self._itfmarker.setLabelAlignment(Qt.AlignTop|Qt.AlignRight);
    self._itfmarker.setZ(120);
    self._itfmarker.attach(self._histplot);
    # add colorbar
    self._cb_item = self.ColorBarPlotItem(1,1+self.ColorBarHeight);
    self._cb_item.setYAxis(QwtPlot.yRight);
    self._cb_item.attach(self._histplot);
    # add pickers
    self._hist_minpicker = self.HistLimitPicker(self._histplot,"low: %(x).4g");
    self._hist_minpicker.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton);
    QObject.connect(self._hist_minpicker,SIGNAL("selected(const QwtDoublePoint &)"),self._selectLowLimit);
    self._hist_maxpicker = self.HistLimitPicker(self._histplot,"high: %(x).4g");
    self._hist_maxpicker.setMousePattern(QwtEventPattern.MouseSelect1,Qt.RightButton);
    QObject.connect(self._hist_maxpicker,SIGNAL("selected(const QwtDoublePoint &)"),self._selectHighLimit);
    self._hist_maxpicker1 = self.HistLimitPicker(self._histplot,"high: %(x).4g");
    self._hist_maxpicker1.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton,Qt.CTRL);
    QObject.connect(self._hist_maxpicker1,SIGNAL("selected(const QwtDoublePoint &)"),self._selectHighLimit);
    self._hist_zoompicker = self.HistLimitPicker(self._histplot,label="zoom",
                                                 tracker_mode=QwtPicker.AlwaysOn,track=self._trackHistCoordinates,color="black",
                                                 mode=QwtPicker.RectSelection,rubber_band=QwtPicker.RectRubberBand);
    self._hist_zoompicker.setMousePattern(QwtEventPattern.MouseSelect1,Qt.LeftButton,Qt.SHIFT);
    QObject.connect(self._hist_zoompicker,SIGNAL("selected(const QwtDoubleRect &)"),self._zoomHistogramIntoRect);

  def _trackHistCoordinates (self,x,y):
    self._wlab_histpos.setText((DataValueFormat+" %d")%(x,y) if x is not None else self._wlab_histpos_text);
    return QwtText();

  def _updateITF (self):
    """Updates current ITF array.""";
    # do nothing if no histogram -- means we're not visible
    if self._hist is not None:
      xdata = self._itf_bins;
      ydata = self.image.intensityMap().remap(xdata);
      self._rangebox.setData(self._rc.displayRange(),[1,1]);
      self._rangebox2.setData(self._rc.displayRange(),[1,1]);
      self._itfcurve.setData(xdata,ydata);
      self._itfmarker.setValue(xdata[0],1);

  def _updateHistogram (self,hmin=None,hmax=None):
    """Recomputes histogram. If no arguments, computes full histogram for
    data subset. If hmin/hmax is specified, computes zoomed-in histogram.""";
    busy = BusyIndicator();
    self._prev_range = self._display_range;
    dmin,dmax = self._subset_range;
    hmin0,hmax0 = dmin,dmax;
    if hmin0 >= hmax0:
      hmax0 = hmin0+1;
    subset,mask = self.image.optimalRavel(self._subset);
    # compute full-subset hi-res histogram, if we don't have one (for percentile stats)
    if self._hist_hires is None:
      dprint(1,"computing histogram for full subset range",hmin0,hmax0);
      self._hist_hires = measurements.histogram(subset,hmin0,hmax0,self.NumHistBinsHi,labels=mask,index=None if mask is None else False);
      self._hist_bins_hires = hmin0 + (hmax0-hmin0)*(numpy.arange(self.NumHistBinsHi)+0.5)/float(self.NumHistBinsHi);
      self._hist_binsize_hires =  (hmax0-hmin0)/self.NumHistBins;
    # if hist limits not specified, then compute lo-res histogram based on the hi-res one
    if hmin is None:
      hmin,hmax = hmin0,hmax0;
      # downsample to low-res histogram
      self._hist = self._hist_hires.reshape((self.NumHistBins,self.NumHistBinsHi/self.NumHistBins)).sum(1);
    else:
      # zoomed-in low-res histogram
      # bracket limits at subset range
      hmin,hmax = max(hmin,dmin),min(hmax,dmax);
      if hmin >= hmax:
        hmax = hmin+1;
      dprint(1,"computing histogram for",self._subset.shape,self._subset.dtype,hmin,hmax);
      self._hist = measurements.histogram(subset,hmin,hmax,self.NumHistBins,labels=mask,index=None if mask is None else False);
    dprint(1,"histogram computed");
    # compute bins
    self._itf_bins = hmin + (hmax-hmin)*(numpy.arange(self.NumItfBins))/(float(self.NumItfBins)-1);
    self._hist_bins = hmin + (hmax-hmin)*(numpy.arange(self.NumHistBins)+0.5)/float(self.NumHistBins);
    # histogram range and position of peak
    self._hist_range = hmin,hmax;
    self._hist_min,self._hist_max,self._hist_imin,self._hist_imax = measurements.extrema(self._hist);
    self._hist_peak = self._hist_bins[self._hist_imax];
    # set controls accordingly
    if dmin >= dmax:
      dmax = dmin+1;
    zoom = math.log10((dmax-dmin)/(hmax-hmin));
    self._whistzoom.setValue(zoom);
    self._whistunzoom.setEnabled(zoom>0);
    self._whistzoomout.setEnabled(zoom>0);
    # reset scales
    self._histplot.setAxisScale(QwtPlot.xBottom,hmin,hmax);
    self._histplot.setAxisScale(QwtPlot.yRight,0,1+self.ColorBarHeight);
    # update curves
    # call _setHistLogScale() (with current setting) to update axis scales and set data
    self._setHistLogScale(self._ylogscale,replot=False);
    # set plot lines
    self._line_0.line.setData([0,0],[0,1]);
    self._line_0.marker.setValue(0,0);
    self._line_maxbin.line.setData([self._hist_peak,self._hist_peak],[0,1]);
    self._line_maxbin.marker.setValue(self._hist_peak,0);
    self._line_maxbin.setText(("max bin:"+DataValueFormat)%self._hist_peak);
    # set half-max line
    self._line_halfmax.line.setData(self._hist_range,[self._hist_max/2,self._hist_max/2]);
    self._line_halfmax.marker.setValue(hmin,self._hist_max/2);
    # update ITF
    self._updateITF();

  def _updateStats (self,subset,minmax):
    """Recomputes subset statistics.""";
    if subset.size <= (2048*2048):
      self._showMeanStd(busy=False);
    else:
      self._wlab_stats.setText(("min: %s  max: %s  np: %d"%(DataValueFormat,DataValueFormat,self._subset.size))%minmax);
      self._wmore_stats.show();

  def _updateDataSubset (self,subset,minmax,desc,subset_type):
    """Called when the displayed data subset is changed. Updates the histogram.""";
    self._subset = subset;
    self._subset_range = minmax;
    self._wlab_subset.setText("Subset: %s"%desc);
    self._hist = self._hist_hires = None;
    self._wreset_full.setVisible(subset_type is not RenderControl.SUBSET_FULL);
    self._wreset_slice and self._wreset_slice.setVisible(subset_type is not RenderControl.SUBSET_SLICE);
    # hide the mean/std markers, they will only be shown when _showMeanStd() is called
    self._line_mean.hide();
    self._line_std.hide();
    # if we're visibile, recompute histograms and stats
    if self.isVisible():
      # if subset is sufficiently small, compute extended stats on-the-fly. Else show the "more" button to compute them later
      self._updateHistogram();
      self._updateStats(subset,minmax);
      self._histplot.replot();

  def _showMeanStd (self,busy=True):
    if busy:
      busy = BusyIndicator();
    dmin,dmax = self._subset_range;
    subset,mask = self.image.optimalRavel(self._subset);
    dprint(5,"computing mean");
    mean = measurements.mean(subset,labels=mask,index=None if mask is None else False);
    dprint(5,"computing std");
    std = measurements.standard_deviation(subset,labels=mask,index=None if mask is None else False);
    dprint(5,"done");
    text = "  ".join([ ("%s: "+DataValueFormat)%(name,value) for name,value in ("min",dmin),("max",dmax),("mean",mean),("std",std) ]+["np: %d"%self._subset.size]);
    self._wlab_stats.setText(text);
    self._wmore_stats.hide();
    # update markers
    ypos = 0.3;
    self._line_mean.line.setData([mean,mean],[0,1]);
    self._line_mean.marker.setValue(mean,ypos);
    self._line_mean.setText((u"\u03BC="+DataValueFormat)%mean);
    self._line_mean.show();
    self._line_std.line.setData([mean-std,mean+std],[ypos,ypos]);
    self._line_std.marker.setValue(mean,ypos);
    self._line_std.setText((u"\u03C3="+DataValueFormat)%std);
    self._line_std.show();
    self._histplot.replot();

  def _setIntensityLogCyclesLabel (self,value):
      self._wlogcycles_label.setText("Log cycles: %4.1f"%value);

  def _previewIntensityLogCycles (self,value):
    self._setIntensityLogCycles(value,notify_image=False,write_config=False);
    self._wlogcycles_timer.start(500);

  def _setIntensityLogCycles (self,value=None,notify_image=True,write_config=True):
    if value is None:
      value = self._wlogcycles.value();
    # stop timer if being called to finalize the change in value
    if notify_image:
      self._wlogcycles_timer.stop();
    if not self._updating_imap:
      self._setIntensityLogCyclesLabel(value);
      self._rc.setIntensityMapLogCycles(value,notify_image=notify_image,write_config=write_config);
      self._updateITF();
      self._histplot.replot();

  def _updateDisplayRange (self,dmin,dmax):
    self._rangebox.setData([dmin,dmax],[.9,.9]);
    self._wrange[0].setText(DataValueFormat%dmin);
    self._wrange[1].setText(DataValueFormat%dmax);
    self._wrangeleft0.setEnabled(dmin!=0);
    self._display_range = dmin,dmax;
    # if auto-zoom is on, zoom the histogram
    # try to be a little clever about this. Zoom only if (a) both limits have changed (so that adjusting one end of the range
    # does not cause endless rezooms), or (b) display range is < 1/10 of the histogram range
    if self._wautozoom.isChecked() and self._hist  is not None:
      if (dmax - dmin)/(self._hist_range[1] - self._hist_range[0]) < .1 or (dmin != self._prev_range[0] and dmax != self._prev_range[1]):
        margin = (dmax-dmin)/8;
        self._updateHistogram(dmin-margin,dmax+margin);
    self._updateITF();
    self._histplot.replot();

  def _updateIntensityMap (self,imap,index):
    self._updating_imap = True;
    try:
      self._cb_item.setIntensityMap(imap);
      self._updateITF();
      self._histplot.replot();
      self._wimap.setCurrentIndex(index);
      if isinstance(imap,Colormaps.LogIntensityMap):
        self._wlogcycles.setValue(imap.log_cycles);
        self._setIntensityLogCyclesLabel(imap.log_cycles);
        self._wlogcycles.show();
        self._wlogcycles_label.show();
      else:
        self._wlogcycles.hide();
        self._wlogcycles_label.hide();
    finally:
      self._updating_imap = False;

  def _updateColorMap (self,cmap):
    self._cb_item.setColorMap(cmap);
    self._histplot.replot();
    try:
      index = self._rc.getColormapList().index(cmap);
    except:
      return;
    self._setCurrentColormapNumber(index,cmap);

  def _previewColormapParameters (self,index,cmap):
    """Called to preview a new colormap parameter value""";
    self._histplot.replot();
    self._wcolmaps.setItemIcon(index,QIcon(cmap.makeQPixmap(128,16)));

  def _setCurrentColormapNumber (self,index,cmap):
    self._wcolmaps.setCurrentIndex(index);
    # show controls for colormap
    self._wcolmap_control_stack.setCurrentWidget(self._colmap_controls[index]);

  def _changeDisplayRange (self):
    """Gets display range from widgets and updates the image with it.""";
    try:
      newrange = [ float(str(w.text())) for w in self._wrange ];
    except ValueError:
      return;
    self._rc.setDisplayRange(*newrange);

  def _setHistDisplayRange (self):
    self._rc.setDisplayRange(*self._hist_range);

  def _updateImageSlice (self,slice):
    for i,(iextra,name,labels) in enumerate(self._rc.slicedAxes()):
      self._wslicers[i].setCurrentIndex(slice[iextra]);

  def _changeDisplayRangeToPercent (self,percent):
    busy = BusyIndicator();
    if self._hist is None:
      self._updateHistogram();
      self._updateStats(self._subset,self._subset_range);
    # delta: we need the [delta,100-delta] interval of the total distribution
    delta = self._subset.size*((100.-percent)/200.);
    # get F(x): cumulative sum
    cumsum = numpy.zeros(len(self._hist_hires)+1,dtype=int);
    cumsum[1:] = numpy.cumsum(self._hist_hires);
    bins = numpy.zeros(len(self._hist_hires)+1,dtype=float);
    bins[0] = self._subset_range[0];
    bins[1:] = self._hist_bins_hires + self._hist_binsize_hires/2;
    # use interpolation to find value interval corresponding to [delta,100-delta] of the distribution
    dprint(2,self._subset.size,delta,self._subset.size-delta);
    dprint(2,cumsum,self._hist_bins_hires);
    # if first bin is already > delta, then set colour range to first bin
    x0,x1 = numpy.interp([delta,self._subset.size-delta],cumsum,bins);
    # and change the display range (this will also cause a histplot.replot() via _updateDisplayRange above)
    self._rc.setDisplayRange(x0,x1);

  def _setZeroLeftLimit (self):
    self._rc.setDisplayRange(0.,self._rc.displayRange()[1]);

  def _selectLowLimit (self,pos):
    self._rc.setDisplayRange(pos.x(),self._rc.displayRange()[1]);

  def _selectHighLimit (self,pos):
    self._rc.setDisplayRange(self._rc.displayRange()[0],pos.x());

  def _unzoomHistogram (self):
    self._updateHistogram();
    self._histplot.replot();

  def _zoomHistogramByFactor (self,factor):
    """Changes histogram limits by specified factor""";
    # get max distance of plot limit from peak
    dprint(1,"zooming histogram by",factor);
    halfdist = (self._hist_range[1] - self._hist_range[0])/(factor*2);
    self._updateHistogram(self._hist_peak-halfdist,self._hist_peak+halfdist);
    self._histplot.replot();

  def _zoomHistogramIntoRect (self,rect):
    hmin,hmax = rect.bottomLeft().x(),rect.bottomRight().x();
    if hmax > hmin:
      self._updateHistogram(rect.bottomLeft().x(),rect.bottomRight().x());
      self._histplot.replot();

  def _zoomHistogramPreview (self,value):
    dprint(2,"wheel moved to",value);
    self._zoomHistogramFinalize(value,preview=True);
    self._whistzoom_timer.start();

  def _zoomHistogramFinalize (self,value=None,preview=False):
    if self._zooming_histogram:
      return;
    self._zooming_histogram = True;
    try:
      if value is not None:
        dmin,dmax = self._subset_range;
        dist = max(dmax-self._hist_peak,self._hist_peak-dmin)/10**value;
        self._preview_hist_range = max(self._hist_peak-dist,dmin),min(self._hist_peak+dist,dmax);
      if preview:
        self._histplot.setAxisScale(QwtPlot.xBottom,*self._preview_hist_range);
      else:
        dprint(2,"wheel finalized at",value);
        self._whistzoom_timer.stop();
        self._updateHistogram(*self._preview_hist_range);
      self._histplot.replot();
    finally:
      self._zooming_histogram = False;

  def _setHistLogScale (self,logscale,replot=True):
    self._ylogscale = logscale;
    if logscale:
      self._histplot.setAxisScaleEngine(QwtPlot.yLeft,QwtLog10ScaleEngine());
      ymax = max(1,self._hist_max);
      self._histplot.setAxisScale(QwtPlot.yLeft,1,10**(math.log10(ymax)*(1+self.ColorBarHeight)));
      y = self._hist.copy();
      y[y==0] = 1;
      self._histcurve1.setData(self._hist_bins,y);
      self._histcurve2.setData(self._hist_bins,y);
    else:
      self._histplot.setAxisScaleEngine(QwtPlot.yLeft,QwtLinearScaleEngine());
      self._histplot.setAxisScale(QwtPlot.yLeft,0,self._hist_max*(1+self.ColorBarHeight));
      self._histcurve1.setData(self._hist_bins,self._hist);
      self._histcurve2.setData(self._hist_bins,self._hist);
    if replot:
      self._histplot.replot();
