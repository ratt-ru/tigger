## -*- coding: utf-8 -*-
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
import numpy
import os.path
import time
import traceback
import sys
from scipy.ndimage import measurements

import Kittens.utils
from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

_verbosity = Kittens.utils.verbosity(name="imagectl");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Tigger.Images import SkyImage,Colormaps
from Tigger.Models import ModelClasses,PlotStyles
from Tigger.Coordinates import Projection,radec_string;
from Tigger.Models.SkyModel import SkyModel
from Tigger import pixmaps
from Tigger.Widgets import FloatValidator

from Tigger.Images.RenderControl import RenderControl
from Tigger.Images.ControlDialog import ImageControlDialog

class ImageController (QFrame):
  """An ImageController is a widget for controlling the display of one image.
  It can emit the following signals from the image:
  raise                     raise button was clicked
  center                  center-on-image option was selected
  unload                  unload option was selected
  slice                     image slice has changed, need to redraw (emitted by SkyImage automatically)
  repaint                 image display range or colormap has changed, need to redraw (emitted by SkyImage automatically)
  """;
  def __init__ (self,image,parent,imgman,name=None,save=False):
    QFrame.__init__(self,parent);
    self.setFrameStyle(QFrame.StyledPanel|QFrame.Raised);
    # init state
    self.image = image;
    self._imgman = imgman;
    self._currier = PersistentCurrier();
    self._control_dialog = None;
    # create widgets
    self._lo = lo = QHBoxLayout(self);
    lo.setContentsMargins(0,0,0,0);
    lo.setSpacing(2);
    # raise button
    self._wraise = QToolButton(self);
    lo.addWidget(self._wraise);
    self._wraise.setIcon(pixmaps.raise_up.icon());
    self._wraise.setAutoRaise(True);
    self._can_raise = False;
    QObject.connect(self._wraise,SIGNAL("clicked()"),self._raiseButtonPressed);
    self._wraise.setToolTip("""<P>Click here to raise this image above other images. Hold the button down briefly to
      show a menu of image operations.</P>""");
    # center label
    self._wcenter = QLabel(self);
    self._wcenter.setPixmap(pixmaps.center_image.pm());
    self._wcenter.setToolTip("<P>The plot is currently centered on (the reference pixel %d,%d) of this image.</P>"%self.image.referencePixel());
    lo.addWidget(self._wcenter);
    # name/filename label
    self.name = image.name;
    self._wlabel = QLabel(self.name,self);
    self._number = 0;
    self.setName(self.name);
    self._wlabel.setToolTip("%s %s"%(image.filename,u"\u00D7".join(map(str,image.data().shape))));
    lo.addWidget(self._wlabel,1);
    # if 'save' is specified, create a "save" button
    if save:
      self._wsave = QToolButton(self);
      lo.addWidget(self._wsave);
      self._wsave.setText("save");
      self._wsave.setAutoRaise(True);
      self._save_dir = save if isinstance(save,str) else ".";
      QObject.connect(self._wsave,SIGNAL("clicked()"),self._saveImage);
      self._wsave.setToolTip("""<P>Click here to write this image to a FITS file.</P>""");
    # render control
    dprint(2,"creating RenderControl");
    self._rc = RenderControl(image,self);
    dprint(2,"done");
    # selectors for extra axes
    self._wslicers = [];
    curslice = self._rc.currentSlice(); # this may be loaded from config, so not necessarily 0
    for iextra,axisname,labels in self._rc.slicedAxes():
      if axisname.upper() not in ["STOKES","COMPLEX"]:
        lbl = QLabel("%s:"%axisname,self);
        lo.addWidget(lbl);
      else:
        lbl = None;
      slicer = QComboBox(self);
      self._wslicers.append(slicer);
      lo.addWidget(slicer);
      slicer.addItems(labels);
      slicer.setToolTip("""<P>Selects current slice along the %s axis.</P>"""%axisname);
      slicer.setCurrentIndex(curslice[iextra]);
      QObject.connect(slicer,SIGNAL("activated(int)"),self._currier.curry(self._rc.changeSlice,iextra));
    # min/max display ranges
    lo.addSpacing(5);
    self._wrangelbl = QLabel(self);
    lo.addWidget(self._wrangelbl);
    self._minmaxvalidator = FloatValidator(self);
    self._wmin = QLineEdit(self);
    self._wmax = QLineEdit(self);
    width = self._wmin.fontMetrics().width("1.234567e-05");
    for w in self._wmin,self._wmax:
      lo.addWidget(w,0);
      w.setValidator(self._minmaxvalidator);
      w.setMaximumWidth(width);
      w.setMinimumWidth(width);
      QObject.connect(w,SIGNAL("editingFinished()"),self._changeDisplayRange);
    # full-range button
    self._wfullrange = QToolButton(self);
    lo.addWidget(self._wfullrange,0);
    self._wfullrange.setIcon(pixmaps.zoom_range.icon());
    self._wfullrange.setAutoRaise(True);
    QObject.connect(self._wfullrange,SIGNAL("clicked()"),self.renderControl().resetSubsetDisplayRange);
    rangemenu = QMenu(self);
    rangemenu.addAction(pixmaps.full_range.icon(),"Full subset",self.renderControl().resetSubsetDisplayRange);
    for percent in (99.99,99.9,99.5,99,98,95):
      rangemenu.addAction("%g%%"%percent,self._currier.curry(self._changeDisplayRangeToPercent,percent));
    self._wfullrange.setPopupMode(QToolButton.DelayedPopup);
    self._wfullrange.setMenu(rangemenu);
    # update widgets from current display range
    self._updateDisplayRange(*self._rc.displayRange());
    # lock button
    self._wlock = QToolButton(self);
    self._wlock.setIcon(pixmaps.unlocked.icon());
    self._wlock.setAutoRaise(True);
    self._wlock.setToolTip("""<P>Click to lock or unlock the intensity range. When the intensity range is locked across multiple images, any changes in the intensity
          range of one are propagated to the others. Hold the button down briefly for additional options.</P>""");
    lo.addWidget(self._wlock);
    QObject.connect(self._wlock,SIGNAL("clicked()"),self._toggleDisplayRangeLock);
    QObject.connect(self.renderControl(),SIGNAL("displayRangeLocked"),self._setDisplayRangeLock);
    QObject.connect(self.renderControl(),SIGNAL("dataSubsetChanged"),self._dataSubsetChanged);
    lockmenu = QMenu(self);
    lockmenu.addAction(pixmaps.locked.icon(),"Lock all to this",self._currier.curry(imgman.lockAllDisplayRanges,self.renderControl()));
    lockmenu.addAction(pixmaps.unlocked.icon(),"Unlock all",imgman.unlockAllDisplayRanges);
    self._wlock.setPopupMode(QToolButton.DelayedPopup);
    self._wlock.setMenu(lockmenu);
    self._setDisplayRangeLock(self.renderControl().isDisplayRangeLocked());
    # dialog button
    self._wshowdialog = QToolButton(self);
    lo.addWidget(self._wshowdialog);
    self._wshowdialog.setIcon(pixmaps.colours.icon());
    self._wshowdialog.setAutoRaise(True);
    self._wshowdialog.setToolTip("""<P>Click for colourmap and intensity policy options.</P>""");
    QObject.connect(self._wshowdialog,SIGNAL("clicked()"),self.showRenderControls);
    tooltip = """<P>You can change the currently displayed intensity range by entering low and high limits here.</P>
    <TABLE>
      <TR><TD><NOBR>Image min:</NOBR></TD><TD>%g</TD><TD>max:</TD><TD>%g</TD></TR>
      </TABLE>"""%self.image.imageMinMax();
    for w in self._wmin,self._wmax,self._wrangelbl:
      w.setToolTip(tooltip);

    # create image operations menu
    self._menu = QMenu(self.name,self);
    self._qa_raise = self._menu.addAction(pixmaps.raise_up.icon(),"Raise image",self._currier.curry(self.image.emit,SIGNAL("raise")));
    self._qa_center = self._menu.addAction(pixmaps.center_image.icon(),"Center plot on image",self._currier.curry(self.image.emit,SIGNAL("center")));
    self._qa_show_rc = self._menu.addAction(pixmaps.colours.icon(),"Colours && Intensities...",self.showRenderControls);
    if save:
      self._qa_save = self._menu.addAction("Save image...",self._saveImage);
    self._menu.addAction("Export image to PNG file...",self._exportImageToPNG);
    self._export_png_dialog = None;
    self._menu.addAction("Unload image",self._currier.curry(self.image.emit,SIGNAL("unload")));
    self._wraise.setMenu(self._menu);
    self._wraise.setPopupMode(QToolButton.DelayedPopup);

    # connect updates from renderControl and image
    self.image.connect(SIGNAL("slice"),self._updateImageSlice);
    QObject.connect(self._rc,SIGNAL("displayRangeChanged"),self._updateDisplayRange);

    # default plot depth of image markers
    self._z_markers = None;
    # and the markers themselves
    self._image_border = QwtPlotCurve();
    self._image_label = QwtPlotMarker();

    # subset markers
    self._subset_pen = QPen(QColor("Light Blue"));
    self._subset_border = QwtPlotCurve();
    self._subset_border.setPen(self._subset_pen);
    self._subset_border.setVisible(False);
    self._subset_label = QwtPlotMarker();
    text = QwtText("subset");
    text.setColor(self._subset_pen.color());
    self._subset_label.setLabel(text);
    self._subset_label.setLabelAlignment(Qt.AlignRight|Qt.AlignBottom);
    self._subset_label.setVisible(False);
    self._setting_lmrect = False;

    self._all_markers = [ self._image_border,self._image_label,self._subset_border,self._subset_label ];

  def close (self):
    if self._control_dialog:
      self._control_dialog.close();
      self._control_dialog = None;

  def __del__ (self):
    self.close();

  def __eq__ (self,other):
    return self is other;

  def renderControl (self):
    return self._rc;

  def getMenu (self):
    return self._menu;

  def getFilename (self):
    return self.image.filename;

  def setName (self,name):
    self.name = name;
    self._wlabel.setText("%s: %s"%(chr(ord('a')+self._number),self.name));

  def setNumber (self,num):
    self._number = num;
    self._menu.menuAction().setText("%s: %s"%(chr(ord('a')+self._number),self.name));
    self._qa_raise.setShortcut(QKeySequence("Alt+"+chr(ord('A')+num)));
    self.setName(self.name);

  def getNumber (self):
    return self._number;

  def setPlotProjection (self,proj):
    self.image.setPlotProjection(proj);
    sameproj = proj == self.image.projection;
    self._wcenter.setVisible(sameproj);
    self._qa_center.setVisible(not sameproj);
    if self._image_border:
      (l0,l1),(m0,m1) = self.image.getExtents();
      path = numpy.array([l0,l0,l1,l1,l0]),numpy.array([m0,m1,m1,m0,m0]);
      self._image_border.setData(*path);
      if self._image_label:
        self._image_label.setValue(path[0][2],path[1][2]);

  def addPlotBorder (self,border_pen,label,label_color=None,bg_brush=None):
    # make plot items for image frame
    # make curve for image borders
    (l0,l1),(m0,m1) = self.image.getExtents();
    self._border_pen = QPen(border_pen);
    self._image_border.show();
    self._image_border.setData([l0,l0,l1,l1,l0],[m0,m1,m1,m0,m0]);
    self._image_border.setPen(self._border_pen);
    self._image_border.setZ(self.image.z()+1 if self._z_markers is None else self._z_markers);
    if label:
      self._image_label.show();
      self._image_label_text = text = QwtText(" %s "%label);
      text.setColor(label_color);
      text.setBackgroundBrush(bg_brush);
      self._image_label.setValue(l1,m1);
      self._image_label.setLabel(text);
      self._image_label.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter);
      self._image_label.setZ(self.image.z()+2 if self._z_markers is None else self._z_markers);

  def setPlotBorderStyle (self,border_color=None,label_color=None):
    if border_color:
      self._border_pen.setColor(border_color);
      self._image_border.setPen(self._border_pen);
    if label_color:
      self._image_label_text.setColor(label_color);
      self._image_label.setLabel(self._image_label_text);

  def showPlotBorder (self,show=True):
    self._image_border.setVisible(show);
    self._image_label.setVisible(show);

  def attachToPlot (self,plot,z_markers=None):
    for item in [ self.image ] + self._all_markers:
      if item.plot() != plot:
        item.attach(plot);

  def setImageVisible (self,visible):
    self.image.setVisible(visible);

  def showRenderControls (self):
    if not self._control_dialog:
      dprint(1,"creating control dialog");
      self._control_dialog = ImageControlDialog(self,self._rc,self._imgman);
      dprint(1,"done");
    if not self._control_dialog.isVisible():
      dprint(1,"showing control dialog");
      self._control_dialog.show();
    else:
      self._control_dialog.hide();

  def _changeDisplayRangeToPercent (self,percent):
    if not self._control_dialog:
      self._control_dialog = ImageControlDialog(self,self._rc,self._imgman);
    self._control_dialog._changeDisplayRangeToPercent(percent);

  def _updateDisplayRange (self,dmin,dmax):
    """Updates display range widgets.""";
    self._wmin.setText("%.4g"%dmin);
    self._wmax.setText("%.4g"%dmax);
    self._updateFullRangeIcon();

  def _changeDisplayRange (self):
    """Gets display range from widgets and updates the image with it.""";
    try:
      newrange = float(str(self._wmin.text())),float(str(self._wmax.text()));
    except ValueError:
      return;
    self._rc.setDisplayRange(*newrange);

  def _dataSubsetChanged (self,subset,minmax,desc,subset_type):
    """Called when the data subset changes (or is reset)""";
    # hide the subset indicator -- unless we're invoked while we're actually setting the subset itself
    if not self._setting_lmrect:
      self._subset = None;
      self._subset_border.setVisible(False);
      self._subset_label.setVisible(False);

  def setLMRectSubset (self,rect):
    self._subset = rect;
    l0,m0,l1,m1 = rect.getCoords();
    self._subset_border.setData([l0,l0,l1,l1,l0],[m0,m1,m1,m0,m0]);
    self._subset_border.setVisible(True);
    self._subset_label.setValue(max(l0,l1),max(m0,m1));
    self._subset_label.setVisible(True);
    self._setting_lmrect = True;
    self.renderControl().setLMRectSubset(rect);
    self._setting_lmrect = False;

  def currentSlice (self):
    return self._rc.currentSlice();

  def _updateImageSlice (self,slice):
    dprint(2,slice);
    for i,(iextra,name,labels) in enumerate(self._rc.slicedAxes()):
      slicer = self._wslicers[i];
      if slicer.currentIndex() != slice[iextra]:
        dprint(3,"setting widget",i,"to",slice[iextra]);
        slicer.setCurrentIndex(slice[iextra]);

  def setMarkersZ (self,z):
    self._z_markers = z;
    for i,elem in enumerate(self._all_markers):
      elem.setZ(z+i);

  def setZ (self,z,top=False,depthlabel=None,can_raise=True):
    self.image.setZ(z);
    if self._z_markers is None:
      for i,elem in enumerate(self._all_markers):
        elem.setZ(z+i+i);
    # set the depth label, if any
    label = "%s: %s"%(chr(ord('a')+self._number),self.name);
    # label = "%s %s"%(depthlabel,self.name) if depthlabel else self.name;
    if top:
      label = "%s: <B>%s</B>"%(chr(ord('a')+self._number),self.name);
    self._wlabel.setText(label);
    # set hotkey
    self._qa_show_rc.setShortcut(Qt.Key_F9 if top else QKeySequence());
    # set raise control
    self._can_raise = can_raise;
    self._qa_raise.setVisible(can_raise);
    self._wlock.setVisible(can_raise);
    if can_raise:
      self._wraise.setToolTip("<P>Click here to raise this image to the top. Click on the down-arrow to access the image menu.</P>");
    else:
      self._wraise.setToolTip("<P>Click to access the image menu.</P>");

  def _raiseButtonPressed (self):
    if self._can_raise:
      self.image.emit(SIGNAL("raise"));
    else:
      self._wraise.showMenu();

  def _saveImage (self):
    filename = QFileDialog.getSaveFileName(self,"Save FITS file",self._save_dir,"FITS files(*.fits *.FITS *fts *FTS)");
    filename = str(filename);
    if not filename:
      return;
    busy = BusyIndicator();
    self._imgman.showMessage("""Writing FITS image %s"""%filename,3000);
    QApplication.flush();
    try:
      self.image.save(filename);
    except Exception,exc:
      busy = None;
      traceback.print_exc();
      self._imgman.showErrorMessage("""Error writing FITS image %s: %s"""%(filename,str(sys.exc_info()[1])));
      return None;
    self.renderControl().startSavingConfig(filename);
    self.setName(self.image.name);
    self._qa_save.setVisible(False);
    self._wsave.hide();
    busy = None;

  def _exportImageToPNG (self,filename=None):
    if not filename:
      if not self._export_png_dialog:
          dialog = self._export_png_dialog = QFileDialog(self,"Export image to PNG",".","*.png");
          dialog.setDefaultSuffix("png");
          dialog.setFileMode(QFileDialog.AnyFile);
          dialog.setAcceptMode(QFileDialog.AcceptSave);
          dialog.setModal(True);
          QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self._exportImageToPNG);
      return self._export_png_dialog.exec_() == QDialog.Accepted;
    busy = BusyIndicator();
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = str(filename);
    # make QPixmap
    nx,ny = self.image.imageDims();
    (l0,l1),(m0,m1) = self.image.getExtents();
    pixmap = QPixmap(nx,ny);
    painter = QPainter(pixmap);
    # use QwtPlot implementation of draw canvas, since we want to avoid caching
    xmap = QwtScaleMap();
    xmap.setPaintInterval(0,nx);
    xmap.setScaleInterval(l1,l0);
    ymap = QwtScaleMap();
    ymap.setPaintInterval(ny,0);
    ymap.setScaleInterval(m0,m1);
    self.image.draw(painter,xmap,ymap,pixmap.rect());
    painter.end();
    # save to file
    try:
      pixmap.save(filename,"PNG");
    except Exception,exc:
      self.emit(SIGNAL("showErrorMessage"),"Error writing %s: %s"%(filename,str(exc)));
      return;
    self.emit(SIGNAL("showMessage"),"Exported image to file %s"%filename);

  def _toggleDisplayRangeLock (self):
    self.renderControl().lockDisplayRange(not self.renderControl().isDisplayRangeLocked());

  def _setDisplayRangeLock (self,locked):
    self._wlock.setIcon(pixmaps.locked.icon() if locked else pixmaps.unlocked.icon());

  def _updateFullRangeIcon (self):
    if self._rc.isSubsetDisplayRange():
      self._wfullrange.setIcon(pixmaps.zoom_range.icon());
      self._wfullrange.setToolTip("""<P>The current intensity range is the full range. Hold this button down briefly for additional options.</P>""");
    else:
      self._wfullrange.setIcon(pixmaps.full_range.icon());
      self._wfullrange.setToolTip("""<P>Click to reset to a full intensity range. Hold the button down briefly for additional options.</P>""");
