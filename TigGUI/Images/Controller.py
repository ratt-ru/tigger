# Copyright (C) 2002-2022
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

import sys
import traceback

import numpy
from PyQt5.Qt import QHBoxLayout, QFileDialog, QComboBox, QLabel, QLineEdit, QDialog, QToolButton, \
    Qt, QApplication, QColor, QPixmap, QPainter, QFrame, QMenu, QPen, QKeySequence, QCheckBox
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDockWidget, QSizePolicy, QWidget, QPushButton, QStyle
from PyQt5.Qwt import QwtText, QwtPlotCurve, QwtPlotMarker, QwtScaleMap, QwtPlotItem
from PyQt5.QtCore import pyqtSignal, QPoint, QPointF, QSize

import TigGUI.kitties.utils
from TigGUI.Images.SkyImage import FITSImagePlotItem
from TigGUI.Plot.SkyModelPlot import LiveImageZoom
from TigGUI.kitties.utils import PersistentCurrier
from TigGUI.kitties.widgets import BusyIndicator


QStringList = list

_verbosity = TigGUI.kitties.utils.verbosity(name="imagectl")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf

from TigGUI.init import pixmaps
from TigGUI.Widgets import FloatValidator, TDockWidget
from TigGUI.Images.RenderControl import RenderControl
from TigGUI.Images.ControlDialog import ImageControlDialog


class ImageController(QFrame):
    """An ImageController is a widget for controlling the display of one image.
    It can emit the following signals from the image:
    raise                     raise button was clicked
    center                  center-on-image option was selected
    unload                  unload option was selected
    slice                     image slice has changed, need to redraw (emitted by SkyImage automatically)
    repaint                 image display range or colormap has changed, need to redraw (emitted by SkyImage automatically)
    """

    # image signals
    imageSignalRepaint = pyqtSignal()
    imageSignalSlice = pyqtSignal(tuple)
    imageSignalRaise = pyqtSignal([FITSImagePlotItem])
    imageSignalUnload = pyqtSignal(object)
    imageSignalCenter = pyqtSignal(object)

    def __init__(self, image, parent, imgman, name=None, save=False):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        # init state
        self._border_pen = None
        self._image_label_text = None
        self._subset = None
        self.image = image
        self._imgman = imgman
        self._currier = PersistentCurrier()
        self._control_dialog = None
        # create widgets
        self._lo = lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(2)
        # raise button
        self._wraise = QToolButton(self)
        lo.addWidget(self._wraise)
        self._wraise.setIcon(pixmaps.raise_up.icon())
        self._wraise.setAutoRaise(True)
        self._can_raise = False
        self._wraise.clicked.connect(self._raiseButtonPressed)
        self._wraise.setToolTip("""<P>Click here to raise this image above other images. Hold the button down briefly to
      show a menu of image operations.</P>""")
        # center label
        self._wcenter = QLabel(self)
        self._wcenter.setPixmap(pixmaps.center_image.pm())
        self._wcenter.setToolTip(
            "<P>The plot is currently centered on (the reference pixel %d,%d) of this image.</P>" % self.image.referencePixel())
        lo.addWidget(self._wcenter)
        # name/filename label
        self.name = image.name
        self._wlabel = QLabel(self.name, self)
        self._number = 0
        self.setName(self.name)
        self._wlabel.setToolTip("%s %s" % (image.filename, "\u00D7".join(map(str, image.data().shape))))
        lo.addWidget(self._wlabel, 1)
        # if 'save' is specified, create a "save" button
        if save:
            self._wsave = QToolButton(self)
            lo.addWidget(self._wsave)
            self._wsave.setText("save")
            self._wsave.setAutoRaise(True)
            self._save_dir = save if isinstance(save, str) else "."
            self._wsave.clicked.connect(self._saveImage)
            self._wsave.setToolTip("""<P>Click here to write this image to a FITS file.</P>""")
        # render control
        self.image.connectRepaint(self.imageSignalRepaint)
        self.image.connectSlice(self.imageSignalSlice)
        self.image.connectRaise(self.imageSignalRaise)
        self.image.connectUnload(self.imageSignalUnload)
        self.image.connectCenter(self.imageSignalCenter)
        dprint(2, "creating RenderControl")
        self._rc = RenderControl(image, self)
        dprint(2, "done")
        # selectors for extra axes
        self._wslicers = []
        curslice = self._rc.currentSlice()  # this may be loaded from config, so not necessarily 0
        for iextra, axisname, labels in self._rc.slicedAxes():
            if axisname.upper() not in ["STOKES", "COMPLEX"]:
                lbl = QLabel("%s:" % axisname, self)
                lo.addWidget(lbl)
            else:
                lbl = None
            slicer = QComboBox(self)
            self._wslicers.append(slicer)
            lo.addWidget(slicer)
            slicer.addItems(labels)
            slicer.setToolTip("""<P>Selects current slice along the %s axis.</P>""" % axisname)
            slicer.setCurrentIndex(curslice[iextra])
            slicer.activated[int].connect(self._currier.curry(self._rc.changeSlice, iextra))
        # min/max display ranges
        lo.addSpacing(5)
        self._wrangelbl = QLabel(self)
        lo.addWidget(self._wrangelbl)
        self._minmaxvalidator = FloatValidator(self)
        self._wmin = QLineEdit(self)
        self._wmax = QLineEdit(self)
        width = self._wmin.fontMetrics().width("1.234567e-05")
        for w in self._wmin, self._wmax:
            lo.addWidget(w, 0)
            w.setValidator(self._minmaxvalidator)
            w.setMaximumWidth(width)
            w.setMinimumWidth(width)
            w.editingFinished.connect(self._changeDisplayRange)
        # full-range button
        self._wfullrange = QToolButton(self)
        lo.addWidget(self._wfullrange, 0)
        self._wfullrange.setIcon(pixmaps.zoom_range.icon())
        self._wfullrange.setAutoRaise(True)
        self._wfullrange.clicked.connect(self.renderControl().resetSubsetDisplayRange)
        rangemenu = QMenu(self)
        rangemenu.addAction(pixmaps.full_range.icon(), "Full subset", self.renderControl().resetSubsetDisplayRange)
        for percent in (99.99, 99.9, 99.5, 99, 98, 95):
            rangemenu.addAction("%g%%" % percent, self._currier.curry(self._changeDisplayRangeToPercent, percent))
        self._wfullrange.setPopupMode(QToolButton.DelayedPopup)
        self._wfullrange.setMenu(rangemenu)
        # update widgets from current display range
        self._updateDisplayRange(*self._rc.displayRange())
        # lock button
        self._wlock = QToolButton(self)
        self._wlock.setIcon(pixmaps.unlocked.icon())
        self._wlock.setAutoRaise(True)
        self._wlock.setToolTip("""<P>Click to lock or unlock the intensity range. When the intensity range is locked across multiple images, any changes in the intensity
          range of one are propagated to the others. Hold the button down briefly for additional options.</P>""")
        lo.addWidget(self._wlock)
        self._wlock.clicked.connect(self._toggleDisplayRangeLock)
        self.renderControl().displayRangeLocked.connect(self._setDisplayRangeLock)
        self.renderControl().dataSubsetChanged.connect(self._dataSubsetChanged)
        lockmenu = QMenu(self)
        lockmenu.addAction(pixmaps.locked.icon(), "Lock all to this",
                           self._currier.curry(imgman.lockAllDisplayRanges, self.renderControl()))
        lockmenu.addAction(pixmaps.unlocked.icon(), "Unlock all", imgman.unlockAllDisplayRanges)
        self._wlock.setPopupMode(QToolButton.DelayedPopup)
        self._wlock.setMenu(lockmenu)
        self._setDisplayRangeLock(self.renderControl().isDisplayRangeLocked())
        # dialog button
        self._wshowdialog = QToolButton(self)
        lo.addWidget(self._wshowdialog)
        self._wshowdialog.setIcon(pixmaps.colours.icon())
        self._wshowdialog.setAutoRaise(True)
        self._wshowdialog.setToolTip("""<P>Click for colourmap and intensity policy options.</P>""")
        self._wshowdialog.clicked.connect(self.showRenderControls)
        tooltip = """<P>You can change the currently displayed intensity range by entering low and high limits here.</P>
            <TABLE>
            <TR><TD><NOBR>Image min:</NOBR></TD><TD>%g</TD><TD>max:</TD><TD>%g</TD></TR>
            </TABLE>""" % self.image.imageMinMax()
        for w in self._wmin, self._wmax, self._wrangelbl:
            w.setToolTip(tooltip)
        # create image operations menu
        self._menu = QMenu(self.name, self)
        self._qa_raise = self._menu.addAction(pixmaps.raise_up.icon(), "Raise image",
                                              self._currier.curry(self.image.signalRaise.emit, None))
        self._qa_center = self._menu.addAction(pixmaps.center_image.icon(), "Center plot on image",
                                               self._currier.curry(self.image.signalCenter.emit, True))
        self._qa_show_rc = self._menu.addAction(pixmaps.colours.icon(), "Colours && Intensities...",
                                                self.showRenderControls)
        if save:
            self._qa_save = self._menu.addAction("Save image...", self._saveImage)
        self._menu.addAction("Export image to PNG file...", self._exportImageToPNG)
        self._export_png_dialog = None
        self._menu.addAction("Unload image", self._currier.curry(self.image.signalUnload.emit, None))
        self._wraise.setMenu(self._menu)
        self._wraise.setPopupMode(QToolButton.DelayedPopup)
        # connect updates from renderControl and image
        self.image.signalSlice.connect(self._updateImageSlice)
        self._rc.displayRangeChanged.connect(self._updateDisplayRange)
        # default plot depth of image markers
        self._z_markers = None
        # and the markers themselves
        self._image_border = QwtPlotCurve()
        self._image_border.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._image_label = QwtPlotMarker()
        self._image_label.setRenderHint(QwtPlotItem.RenderAntialiased)
        # subset markers
        self._subset_pen = QPen(QColor("Light Blue"))
        self._subset_border = QwtPlotCurve()
        self._subset_border.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._subset_border.setPen(self._subset_pen)
        self._subset_border.setVisible(False)
        self._subset_label = QwtPlotMarker()
        self._subset_label.setRenderHint(QwtPlotItem.RenderAntialiased)
        text = QwtText("subset")
        text.setColor(self._subset_pen.color())
        self._subset_label.setLabel(text)
        self._subset_label.setLabelAlignment(Qt.AlignRight | Qt.AlignBottom)
        self._subset_label.setVisible(False)
        self._setting_lmrect = False
        self._all_markers = [self._image_border, self._image_label, self._subset_border, self._subset_label]
        self._exportMaxRes = False
        self._dockable_colour_ctrl = None

    def close(self):
        if self._control_dialog:
            self._control_dialog.close()
            self._control_dialog = None

    def __del__(self):
        self.close()

    def __eq__(self, other):
        return self is other

    def renderControl(self):
        return self._rc

    def getMenu(self):
        return self._menu

    def getFilename(self):
        return self.image.filename

    def setName(self, name):
        self.name = name
        self._wlabel.setText("%s: %s" % (chr(ord('a') + self._number), self.name))

    def setNumber(self, num):
        self._number = num
        self._menu.menuAction().setText("%s: %s" % (chr(ord('a') + self._number), self.name))
        self._qa_raise.setShortcut(QKeySequence("Alt+" + chr(ord('A') + num)))
        self.setName(self.name)

    def getNumber(self):
        return self._number

    def setPlotProjection(self, proj):
        self.image.setPlotProjection(proj)
        sameproj = proj == self.image.projection
        self._wcenter.setVisible(sameproj)
        self._qa_center.setVisible(not sameproj)
        if self._image_border:
            (l0, l1), (m0, m1) = self.image.getExtents()
            path = numpy.array([l0, l0, l1, l1, l0]), numpy.array([m0, m1, m1, m0, m0])
            self._image_border.setSamples(*path)
            if self._image_label:
                self._image_label.setValue(path[0][2], path[1][2])

    def addPlotBorder(self, border_pen, label, label_color=None, bg_brush=None):
        # make plot items for image frame
        # make curve for image borders
        (l0, l1), (m0, m1) = self.image.getExtents()
        self._border_pen = QPen(border_pen)
        self._image_border.show()
        self._image_border.setSamples([l0, l0, l1, l1, l0], [m0, m1, m1, m0, m0])
        self._image_border.setPen(self._border_pen)
        self._image_border.setZ(self.image.z() + 1 if self._z_markers is None else self._z_markers)
        if label:
            self._image_label.show()
            self._image_label_text = text = QwtText(" %s " % label)
            text.setColor(label_color)
            text.setBackgroundBrush(bg_brush)
            self._image_label.setValue(l1, m1)
            self._image_label.setLabel(text)
            self._image_label.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._image_label.setZ(self.image.z() + 2 if self._z_markers is None else self._z_markers)

    def setPlotBorderStyle(self, border_color=None, label_color=None):
        if border_color:
            self._border_pen.setColor(border_color)
            self._image_border.setPen(self._border_pen)
        if label_color:
            self._image_label_text.setColor(label_color)
            self._image_label.setLabel(self._image_label_text)

    def showPlotBorder(self, show=True):
        self._image_border.setVisible(show)
        self._image_label.setVisible(show)

    def attachToPlot(self, plot, z_markers=None):
        for item in [self.image] + self._all_markers:
            if item.plot() != plot:
                item.attach(plot)

    def setImageVisible(self, visible):
        self.image.setVisible(visible)

    def showRenderControls(self):
        if not self._control_dialog:
            dprint(1, "creating control dialog")
            self._control_dialog = ImageControlDialog(self, self._rc, self._imgman)
            # line below allows window to be resized by the user
            self._control_dialog.setSizeGripEnabled(True)
            # get and set sizing
            self._control_dialog.setMinimumWidth(396)
            # create size policy for control dialog
            colour_ctrl_policy = QSizePolicy()
            colour_ctrl_policy.setHorizontalPolicy(QSizePolicy.Minimum)
            self._control_dialog.setSizePolicy(colour_ctrl_policy)
            # setup dockable colour control dialog
            self._dockable_colour_ctrl = TDockWidget(title=f"{self._rc.image.name}", parent=self.parent().mainwin,
                                                     bind_widget=self._control_dialog,
                                                     close_slot=self.colourctrl_dockwidget_closed,
                                                     toggle_slot=self.colourctrl_dockwidget_toggled)
            self.addDockWidgetToTab()
            dprint(1, "done")
        # set dockable widget visibility in sync with control dialog
        if not self._control_dialog.isVisible():
            dprint(1, "showing control dialog")
            self._control_dialog.show()
            if self._dockable_colour_ctrl is not None:
                self._dockable_colour_ctrl.setVisible(True)
                self.addDockWidgetToTab()
                self._dockable_colour_ctrl.show()
                self._dockable_colour_ctrl.raise_()
                if not self.get_docked_widget_size(self._dockable_colour_ctrl):
                    geo = self.parent().mainwin.geometry()
                    geo.setWidth(self.parent().mainwin.width() + self._dockable_colour_ctrl.width())
                    self.parent().mainwin.setGeometry(geo)
        else:
            self._control_dialog.hide()
            self._dockable_colour_ctrl.setVisible(False)
            if not self.get_docked_widget_size(self._dockable_colour_ctrl):
                geo = self.parent().mainwin.geometry()
                geo.setWidth(self.parent().mainwin.width() - self._dockable_colour_ctrl.width())
                self.parent().mainwin.setGeometry(geo)

    def addDockWidgetToTab(self):
        # Add dockable widget to main window.
        # This needs to itterate through the widgets to find DockWidgets already in the right side area,
        # then tabifydockwidget when adding, or add to the right area if empty
        widget_list = self.parent().mainwin.findChildren(QDockWidget)
        for widget in widget_list:
            if self.parent().mainwin.dockWidgetArea(widget) == 2:  # if in right dock area
                if widget.isVisible() and not widget.isFloating():  # if widget active and not a window
                    if self._dockable_colour_ctrl is not widget:  # check not itself
                        # add dock widget in tab on top of current widget in right area
                        self.parent().mainwin.tabifyDockWidget(widget, self._dockable_colour_ctrl)
                        self.parent().mainwin.resizeDocks([widget], [widget.bind_widget.width()], Qt.Horizontal)
            elif self.parent().mainwin.dockWidgetArea(
                    widget) == 0:  # if not in any dock area assume we have new dock widget
                # no previous widget in this area then add
                self.parent().mainwin.addDockWidget(Qt.RightDockWidgetArea, self._dockable_colour_ctrl)
                self.parent().mainwin.resizeDocks([widget], [widget.bind_widget.width()], Qt.Horizontal)

    def removeDockWidget(self):
        # remove image control dock widget
        self.parent().mainwin.removeDockWidget(self._dockable_colour_ctrl)
        # get widgets to resize
        widget_list = self.parent().mainwin.findChildren(QDockWidget)
        size_list = []
        result = []
        for widget in widget_list:
            if not isinstance(widget.bind_widget, ImageControlDialog):
                size_list.append(widget.bind_widget.width())
                result.append(widget)
                dprint(2, f"{widget} width {widget.width()}")
                dprint(2, f"{widget} bind_widget width {widget.bind_widget.width()}")
                if isinstance(widget.bind_widget, LiveImageZoom):
                    widget.bind_widget.setMinimumWidth(widget.width())
        widget_list = result
        # resize dock areas
        self.parent().mainwin.resizeDocks(widget_list, size_list, Qt.Horizontal)

    def colourctrl_dockwidget_closed(self):
        self._dockable_colour_ctrl.setVisible(False)
        if self.parent().mainwin.windowState() != Qt.WindowMaximized:
            if not self.get_docked_widget_size(self._dockable_colour_ctrl):
                if not self._dockable_colour_ctrl.isFloating():
                    geo = self.parent().mainwin.geometry()
                    geo.setWidth(self.parent().mainwin.width() - self._dockable_colour_ctrl.width())
                    self.parent().mainwin.setGeometry(geo)

    def colourctrl_dockwidget_toggled(self):
        if not self._dockable_colour_ctrl.isVisible():
            return
        if self._dockable_colour_ctrl.isWindow():
            self._dockable_colour_ctrl.setFloating(False)
            if self.parent().mainwin.windowState() != Qt.WindowMaximized:
                if not self.get_docked_widget_size(self._dockable_colour_ctrl):
                    geo = self.parent().mainwin.geometry()
                    geo.setWidth(self.parent().mainwin.width() + self._dockable_colour_ctrl.width())
                    self.parent().mainwin.setGeometry(geo)
        else:
            self._dockable_colour_ctrl.setFloating(True)
            if self.parent().mainwin.windowState() != Qt.WindowMaximized:
                if not self.get_docked_widget_size(self._dockable_colour_ctrl):
                    geo = self.parent().mainwin.geometry()
                    geo.setWidth(self.parent().mainwin.width() - self._dockable_colour_ctrl.width())
                    self.parent().mainwin.setGeometry(geo)

    def get_docked_widget_size(self, _dockable):
        widget_list = self.parent().mainwin.findChildren(QDockWidget)
        size_list = []
        if _dockable:
            for widget in widget_list:
                if isinstance(widget.bind_widget, ImageControlDialog):
                    if widget is not _dockable:
                        if not widget.isWindow() and not widget.isFloating() and widget.isVisible():
                            size_list.append(widget.bind_widget.width())
        if size_list:
            return max(size_list)
        else:
            return size_list

    def _changeDisplayRangeToPercent(self, percent):
        if not self._control_dialog:
            self._control_dialog = ImageControlDialog(self, self._rc, self._imgman)
        self._control_dialog._changeDisplayRangeToPercent(percent)

    def _updateDisplayRange(self, dmin, dmax):
        """Updates display range widgets."""
        self._wmin.setText("%.4g" % dmin)
        self._wmax.setText("%.4g" % dmax)
        self._updateFullRangeIcon()

    def _changeDisplayRange(self):
        """Gets display range from widgets and updates the image with it."""
        try:
            newrange = float(str(self._wmin.text())), float(str(self._wmax.text()))
        except ValueError:
            return
        self._rc.setDisplayRange(*newrange)

    def _dataSubsetChanged(self, subset, minmax, desc, subset_type):
        """Called when the data subset changes (or is reset)"""
        # hide the subset indicator -- unless we're invoked while we're actually setting the subset itself
        if not self._setting_lmrect:
            self._subset = None
            self._subset_border.setVisible(False)
            self._subset_label.setVisible(False)

    def setLMRectSubset(self, rect):
        self._subset = rect
        l0, m0, l1, m1 = rect.getCoords()
        self._subset_border.setSamples([l0, l0, l1, l1, l0], [m0, m1, m1, m0, m0])
        self._subset_border.setVisible(True)
        self._subset_label.setValue(max(l0, l1), max(m0, m1))
        self._subset_label.setVisible(True)
        self._setting_lmrect = True
        self.renderControl().setLMRectSubset(rect)
        self._setting_lmrect = False

    def currentSlice(self):
        return self._rc.currentSlice()

    def _updateImageSlice(self, _slice):
        dprint(2, _slice)
        for i, (iextra, name, labels) in enumerate(self._rc.slicedAxes()):
            slicer = self._wslicers[i]
            if slicer.currentIndex() != _slice[iextra]:
                dprint(3, "setting widget", i, "to", _slice[iextra])
                slicer.setCurrentIndex(_slice[iextra])

    def setMarkersZ(self, z):
        self._z_markers = z
        for i, elem in enumerate(self._all_markers):
            elem.setZ(z + i)

    def setZ(self, z, top=False, depthlabel=None, can_raise=True):
        self.image.setZ(z)
        if self._z_markers is None:
            for i, elem in enumerate(self._all_markers):
                elem.setZ(z + i + i)
        # set the depth label, if any
        label = "%s: %s" % (chr(ord('a') + self._number), self.name)
        # label = "%s %s"%(depthlabel,self.name) if depthlabel else self.name
        if top:
            label = "%s: <B>%s</B>" % (chr(ord('a') + self._number), self.name)
        self._wlabel.setText(label)
        # set hotkey
        self._qa_show_rc.setShortcut(Qt.Key_F9 if top else QKeySequence())
        # set raise control
        self._can_raise = can_raise
        self._qa_raise.setVisible(can_raise)
        self._wlock.setVisible(can_raise)
        if can_raise:
            self._wraise.setToolTip(
                "<P>Click here to raise this image to the top. Click on the down-arrow to access the image menu.</P>")
        else:
            self._wraise.setToolTip("<P>Click to access the image menu.</P>")

    def _raiseButtonPressed(self):
        if self._can_raise:
            self.image.signalRaise.emit(self.image)
        else:
            self._wraise.showMenu()

    def _saveImage(self):
        filename = QFileDialog.getSaveFileName(self, "Save FITS file", self._save_dir,
                                               "FITS files(*.fits *.FITS *fts *FTS)", options=QFileDialog.DontUseNativeDialog)
        filename = str(filename[0])
        if not filename:
            return
        busy = BusyIndicator()
        self._imgman.signalShowMessage.emit("""Writing FITS image %s""" % filename, 3000)
        QApplication.flush()
        try:
            self.image.save(filename)
        except Exception as exc:
            busy.reset_cursor()
            traceback.print_exc()
            self._imgman.signalShowErrorMessage.emit("""Error writing FITS image %s: %s""" % (filename, str(sys.exc_info()[1])))
            return None
        self.renderControl().startSavingConfig(filename)
        self.setName(self.image.name)
        self._qa_save.setVisible(False)
        self._wsave.hide()
        busy.reset_cursor()

    def _exportImageResolution(self):
        sender = self.sender()
        if isinstance(sender, QCheckBox):
            if sender.isChecked():
                self._exportMaxRes = True
            else:
                self._exportMaxRes = False

    def _exportImageToPNG(self, filename=None):
        if not filename:
            if not self._export_png_dialog:
                dialog = self._export_png_dialog = QFileDialog(self, "Export image to PNG", ".", "*.png")
                dialog.setDefaultSuffix("png")
                dialog.setFileMode(QFileDialog.AnyFile)
                dialog.setAcceptMode(QFileDialog.AcceptSave)
                dialog.setModal(True)
                dialog.filesSelected['QStringList'].connect(self._exportImageToPNG)
                # attempt to add limit 4K option - not available on Ubuntu Unity
                layout = dialog.layout()
                if layout is not None:
                    checkbox = QCheckBox("Limit to 4K image")
                    checkbox.setChecked(False)
                    checkbox.setToolTip("Limits the image output to 4K")
                    checkbox.toggled.connect(self._exportImageResolution)
                    layout.addWidget(checkbox)
                    dialog.setLayout(layout)
            return self._export_png_dialog.exec_() == QDialog.Accepted
        busy = BusyIndicator()
        if isinstance(filename, QStringList):
            filename = filename[0]
        filename = str(filename)
        # get image dimensions
        nx, ny = self.image.imageDims()
        # export either max resolution possible or default to 4K. If image is small then no scaling occurs.
        if not self._exportMaxRes:
            # get free memory. Note: Linux only!
            import os
            total_memory, used_memory, free_memory = map(int, os.popen('free -t -m').readlines()[-1].split()[1:])
            # use 90% of free memory available
            free_memory = free_memory * 0.9
            # use an approximation to find the max image size that can be generated
            if nx >= ny and nx > free_memory:
                scale_factor = round(free_memory / nx, 1)
            elif ny > nx and ny > free_memory:
                scale_factor = round(free_memory / ny, 1)
            else:
                scale_factor = 1
        else:
            # default to 4K
            if nx > 4000:
                scale_factor = 4000 / nx
            elif ny > nx and ny > 4000:
                scale_factor = 4000 / ny
            else:
                scale_factor = 1

        # make QPixmap
        nx = nx * scale_factor
        ny = ny * scale_factor
        (l0, l1), (m0, m1) = self.image.getExtents()
        pixmap = QPixmap(nx, ny)
        painter = QPainter(pixmap)
        # use QwtPlot implementation of draw canvas, since we want to avoid caching
        xmap = QwtScaleMap()
        xmap.setPaintInterval(0, nx)
        xmap.setScaleInterval(l1, l0)
        ymap = QwtScaleMap()
        ymap.setPaintInterval(ny, 0)
        ymap.setScaleInterval(m0, m1)
        # call painter with clear cache option for consistent file size output.
        self.image.draw(painter, xmap, ymap, pixmap.rect(), use_cache=False)
        painter.end()
        # save to file
        try:
            pixmap.save(filename, "PNG")
            # clean up export items
            pixmap.detach()
            del xmap
            del ymap
            del pixmap
            del painter
        except Exception as exc:
            self._imgman.signalShowErrorMessage[str, int].emit("Error writing %s: %s" % (filename, str(exc)), 3000)
            busy.reset_cursor()
        else:
            busy.reset_cursor()
            self._imgman.signalShowMessage[str, int].emit("Exported image to file %s" % filename, 3000)

    def _toggleDisplayRangeLock(self):
        self.renderControl().lockDisplayRange(not self.renderControl().isDisplayRangeLocked())

    def _setDisplayRangeLock(self, locked):
        self._wlock.setIcon(pixmaps.locked.icon() if locked else pixmaps.unlocked.icon())

    def _updateFullRangeIcon(self):
        if self._rc.isSubsetDisplayRange():
            self._wfullrange.setIcon(pixmaps.zoom_range.icon())
            self._wfullrange.setToolTip(
                """<P>The current intensity range is the full range. Hold this button down briefly for additional options.</P>""")
        else:
            self._wfullrange.setIcon(pixmaps.full_range.icon())
            self._wfullrange.setToolTip(
                """<P>Click to reset to a full intensity range. Hold the button down briefly for additional options.</P>""")
