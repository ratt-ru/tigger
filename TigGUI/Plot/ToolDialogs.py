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

import os
import numpy

from PyQt5.Qt import (QAction, QApplication, QCheckBox, QColor, QColorDialog,
                      QComboBox, QDialog, QFileDialog, QGridLayout,
                      QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
                      QPen, QPoint, QRectF, QSize, QSizePolicy, QToolButton,
                      QTransform, QVBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDockWidget, QLayout
from PyQt5.Qwt import QwtLegend, QwtPlot, QwtPlotCurve, QwtPlotItem, QwtText

import TigGUI
from TigGUI.Widgets import TiggerPlotCurve
from TigGUI.init import Config, pixmaps
import TigGUI.kitties.utils
from TigGUI.kitties.utils import curry

from TigGUI.Plot.PlottableProfiles import PlottableTiggerProfile
from TigGUI.Plot.Utils import makeDualColorPen
from TigGUI.kitties.profiles import TiggerProfile, TiggerProfileFactory
QStringList = list


_verbosity = TigGUI.kitties.utils.verbosity(name="plot")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf


class ToolDialog(QDialog):
    signalIsVisible = pyqtSignal(bool)

    def __init__(self, parent, mainwin, configname, menuname, show_shortcut=None):
        QDialog.__init__(self, parent)
        self.setModal(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.mainwin = mainwin
        self.hide()
        self._configname = configname
        self._geometry = None
        # make hide/show qaction
        self._qa_show = qa = QAction("Show %s" % menuname.replace("&", "&&"), self)
        if show_shortcut:
            qa.setShortcut(show_shortcut)
        qa.setCheckable(True)
        qa.setChecked(Config.getbool("%s-show" % configname, False))
        qa.setVisible(False)
        qa.setToolTip("""<P>The quick zoom & cross-sections window shows a zoom of the current image area
      under the mose pointer, and X/Y cross-sections through that area.</P>""")
        qa.triggered[bool].connect(self.setVisible)
        self._closing = False
        self._write_config = curry(Config.set, "%s-show" % configname)
        qa.triggered[bool].connect(self._write_config)
        self.signalIsVisible.connect(qa.setChecked)

    def getShowQAction(self):
        return self._qa_show

    def makeAvailable(self, available=True):
        """Makes the tool available (or unavailable)-- shows/hides the "show" control,
        and shows/hides the dialog according to this control."""
        self._qa_show.setVisible(available)
        self.setVisible(self._qa_show.isChecked() if available else False)

    def initGeometry(self):
        x0 = Config.getint('%s-x0' % self._configname, 0)
        y0 = Config.getint('%s-y0' % self._configname, 0)
        w = Config.getint('%s-width' % self._configname, 0)
        h = Config.getint('%s-height' % self._configname, 0)
        if w and h:
            self.resize(w, h)
            self.move(x0, y0)
            return True
        return False

    def _saveGeometry(self):
        Config.set('%s-x0' % self._configname, self.pos().x())
        Config.set('%s-y0' % self._configname, self.pos().y())
        Config.set('%s-width' % self._configname, self.width())
        Config.set('%s-height' % self._configname, self.height())

    def close(self):
        self._closing = True
        QDialog.close(self)

    def closeEvent(self, event):
        QDialog.closeEvent(self, event)
        if not self._closing:
            self._write_config(False)

    def moveEvent(self, event):
        self._saveGeometry()
        QDialog.moveEvent(self, event)

    def resizeEvent(self, event):
        self._saveGeometry()
        QDialog.resizeEvent(self, event)

    def setVisible(self, visible, emit=True):
        if not visible:
            self._geometry = self.geometry()
        else:
            if self._geometry:
                self.setGeometry(self._geometry)
        if emit:
            self.signalIsVisible.emit(visible)
        QDialog.setVisible(self, visible)
        # This section aligns the dockwidget with its subqwidget's visibility
        if visible and not self.parent().isVisible():
            self.parent().setGeometry(self.geometry())
            self.parent().setVisible(True)
            _area = self.mainwin.dockWidgetArea(self.parent())  # in right dock area
            if self.mainwin.windowState() != Qt.WindowMaximized:
                if not self.get_docked_widget_size(self.parent(), _area):
                    geo = self.mainwin.geometry()
                    geo.setWidth(self.mainwin.width() + self.parent().width())
                    center = geo.center()
                    if self.mainwin.dockWidgetArea(self.parent()) == 2:  # in right dock area
                        geo.moveCenter(QPoint(center.x() + self.parent().width(), geo.y()))
                    elif self.mainwin.dockWidgetArea(self.parent()) == 1:
                        geo.moveCenter(QPoint(center.x() - self.width(), geo.y()))
                    self.mainwin.setGeometry(geo)
            if _area == 2 and isinstance(self.parent().bind_widget, TigGUI.Plot.SkyModelPlot.LiveImageZoom):
                self.mainwin.addDockWidgetToArea(self.parent(), _area)
            else:
                self.mainwin.addDockWidgetToArea(self.parent(), _area)
        elif not visible and self.parent().isVisible():
            _area = self.mainwin.dockWidgetArea(self.parent())  # in right dock area
            if self.mainwin.windowState() != Qt.WindowMaximized:
                if not self.get_docked_widget_size(self.parent(), _area):
                    geo = self.mainwin.geometry()
                    geo.setWidth(self.mainwin.width() - self.parent().width())
                    center = geo.center()
                    if self.mainwin.dockWidgetArea(self.parent()) == 1:  # in left dock area
                        geo.moveCenter(QPoint(center.x() + self.parent().width(), geo.y()))
                    self.mainwin.setGeometry(geo)
            self.parent().setVisible(False)
            self.mainwin.restoreDockArea(_area)

    def get_docked_widget_size(self, _dockable, _area):
        widget_list = self.mainwin.findChildren(QDockWidget)
        size_list = []
        if _dockable:
            for widget in widget_list:
                if self.mainwin.dockWidgetArea(widget) == _area:
                    if widget is not _dockable:
                        if (not widget.isWindow() and not widget.isFloating()
                                and widget.isVisible()):
                            size_list.append(widget.bind_widget.width())
        if size_list:
            return max(size_list)
        else:
            return size_list


class LiveImageZoom(ToolDialog):
    livezoom_resize_signal = pyqtSignal(QSize)

    def __init__(self, parent, mainwin, radius=10, factor=12):
        ToolDialog.__init__(self, parent, mainwin, configname="livezoom", menuname="live zoom & cross-sections",
                            show_shortcut=Qt.Key_F2)
        self.setWindowTitle("Zoom & Cross-sections")
        radius = Config.getint("livezoom-radius", radius)
        # create size polixy for livezoom
        livezoom_policy = QSizePolicy()
        livezoom_policy.setWidthForHeight(True)
        livezoom_policy.setHeightForWidth(True)
        self.setSizePolicy(livezoom_policy)
        # add plots
        self._lo0 = lo0 = QVBoxLayout(self)
        self._lo0.setSizeConstraint(QLayout.SetFixedSize)
        lo1 = QHBoxLayout()
        lo1.setContentsMargins(0, 0, 0, 0)
        lo1.setSpacing(0)
        lo0.addLayout(lo1)
        # control checkboxes
        self._showzoom = QCheckBox("show zoom", self)
        self._showcs = QCheckBox("show cross-sections", self)
        self._showzoom.setChecked(True)
        self._showcs.setChecked(True)
        self._showzoom.toggled[bool].connect(self._showZoom)
        self._showcs.toggled[bool].connect(self._showCrossSections)
        lo1.addWidget(self._showzoom, 0)
        lo1.addSpacing(5)
        lo1.addWidget(self._showcs, 0)
        lo1.addStretch(1)
        self._smaller = QToolButton(self)
        self._smaller.setIcon(pixmaps.window_smaller.icon())
        self._smaller.clicked.connect(self._shrink)
        self._larger = QToolButton(self)
        self._larger.setIcon(pixmaps.window_larger.icon())
        self._larger.clicked.connect(self._enlarge)
        lo1.addWidget(self._smaller)
        lo1.addWidget(self._larger)
        self._has_zoom = self._has_xcs = self._has_ycs = False
        # setup zoom plot
        font = QApplication.font()
        font.setPointSize(8)
        axis_font = QApplication.font()
        axis_font.setBold(True)
        axis_font.setPointSize(10)
        self._zoomplot = QwtPlot(self)
        self._zoomplot.setContentsMargins(5, 5, 5, 5)
        axes = {QwtPlot.xBottom: "X pixel coordinate",
                QwtPlot.yLeft: "Y pixel coordinate",
                QwtPlot.xTop: "X cross-section value",
                QwtPlot.yRight: "Y cross-section value"}
        for axis, title in axes.items():
            self._zoomplot.enableAxis(True)
            self._zoomplot.setAxisScale(axis, 0, 1)
            self._zoomplot.setAxisFont(axis, font)
            self._zoomplot.setAxisMaxMajor(axis, 3)
            self._zoomplot.axisWidget(axis).setMinBorderDist(5, 5)
            self._zoomplot.axisWidget(axis).show()
            text = QwtText(title)
            text.setFont(font)
            self._zoomplot.axisWidget(axis).setTitle(text.text())
            axis_text = QwtText(title)
            axis_text.setFont(axis_font)
            self._zoomplot.setAxisTitle(axis, axis_text)
        self._zoomplot.setAxisLabelRotation(QwtPlot.yLeft, -90)
        self._zoomplot.setAxisLabelAlignment(QwtPlot.yLeft, Qt.AlignVCenter)
        self._zoomplot.setAxisLabelRotation(QwtPlot.yRight, 90)
        self._zoomplot.setAxisLabelAlignment(QwtPlot.yRight, Qt.AlignVCenter)
        # self._zoomplot.plotLayout().setAlignCanvasToScales(True)
        lo0.addWidget(self._zoomplot, 0)
        # setup ZoomItem for zoom plot
        self._zi = self.ImageItem()
        self._zi.attach(self._zoomplot)
        self._zi.setZ(0)
        # setup targeting reticule for zoom plot
        self._reticules = TiggerPlotCurve(), TiggerPlotCurve()
        for curve in self._reticules:
            curve.setRenderHint(QwtPlotItem.RenderAntialiased)
            curve.setPen(QPen(QColor("green")))
            curve.setStyle(QwtPlotCurve.Lines)
            curve.attach(self._zoomplot)
            curve.setZ(1)
        # setup cross-section curves
        self._xcs = TiggerPlotCurve()
        self._xcs.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._ycs = TiggerPlotCurve()
        self._ycs.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._xcs.setPen(makeDualColorPen("navy", "yellow"))
        self._ycs.setPen(makeDualColorPen("black", "cyan"))
        for curve in self._xcs, self._ycs:
            curve.setStyle(QwtPlotCurve.Steps)
            curve.attach(self._zoomplot)
            curve.setZ(2)
        self._xcs.setXAxis(QwtPlot.xBottom)
        self._xcs.setYAxis(QwtPlot.yRight)
        self._ycs.setXAxis(QwtPlot.xTop)
        self._ycs.setYAxis(QwtPlot.yLeft)
        # self._ycs.setCurveType(QwtPlotCurve.Xfy)  # old qwt5
        self._ycs.setOrientation(Qt.Vertical)  # Qwt 6 version
        self._xcs.setOrientation(Qt.Horizontal)  # Qwt 6 version
        # make QTransform for flipping images upside-down
        self._xform = QTransform()
        self._xform.scale(1, -1)
        # init geometry
        self.setPlotSize(radius, factor)
        self.initGeometry()

    def _showZoom(self, show):
        if not show:
            self._zi.setVisible(False)

    def _showCrossSections(self, show):
        self._zoomplot.enableAxis(QwtPlot.xTop, show)
        self._zoomplot.enableAxis(QwtPlot.yRight, show)
        if not show:
            self._xcs.setVisible(False)
            self._ycs.setVisible(False)

    def _enlarge(self):
        self.setPlotSize(int(self._radius * 2), self._magfac)

    def _shrink(self):
        self.setPlotSize(int(self._radius / 2), self._magfac)

    def setPlotSize(self, radius, factor):
        Config.set('livezoom-radius', radius)
        self._radius = radius
        # enable smaller/larger buttons based on radius
        self._smaller.setEnabled(radius > 5)
        self._larger.setEnabled(radius < 40)
        # compute other sizes
        self._npix = radius * 2 + 1
        self._magfac = factor
        width = height = self._npix * self._magfac
        self._zoomplot.setMinimumHeight(height + 80)
        self._zoomplot.setMinimumWidth(width + 80)
        # set data array
        self._data = numpy.ma.masked_array(numpy.zeros((self._npix, self._npix), float),
                                           numpy.zeros((self._npix, self._npix), bool))
        # reset window size
        self._lo0.update()
        self.resize(self._lo0.minimumSize())
        self.livezoom_resize_signal.emit(self._lo0.minimumSize())

    def _getZoomSlice(self, ix, nx):
        ix0, ix1 = ix - self._radius, ix + self._radius + 1
        zx0 = -min(ix0, 0)
        ix0 = max(ix0, 0)
        zx1 = self._npix - max(ix1, nx - 1) + (nx - 1)
        ix1 = min(ix1, nx - 1)
        return ix0, ix1, zx0, zx1

    class ImageItem(QwtPlotItem):
        """ImageItem subclass used by LiveZoomer to display zoomed-in images"""

        def __init__(self):
            QwtPlotItem.__init__(self)
            self._qimg = None
            self.RenderAntialiased

        def setImage(self, qimg):
            self._qimg = qimg

        def draw(self, painter, xmap, ymap, rect):
            """Implements QwtPlotItem.draw(), to render the image on the given painter."""
            # drawImage expects QRectF
            self._qimg and painter.drawImage(QRectF(xmap.p1(), ymap.p2(), xmap.pDist(), ymap.pDist()), self._qimg)

    def trackImage(self, image, ix, iy):
        if not self.isVisible():
            return
        # update zoomed image
        # find overlap of zoom window with image, mask invisible pixels
        nx, ny = image.imageDims()
        ix0, ix1, zx0, zx1 = self._getZoomSlice(ix, nx)
        iy0, iy1, zy0, zy1 = self._getZoomSlice(iy, ny)
        if ix0 < nx and ix1 >= 0 and iy0 < ny and iy1 >= 0:
            if self._showzoom.isChecked():
                # There was an error here when using zoom window zoom buttons
                # (TypeError: slice indices must be integers or None or have an __index__ method).
                # Therefore indexes have been cast as int()
                # 16/05/2022: the error no longer occurs, therefore code has been reverted.
                self._data.mask[...] = False
                self._data.mask[:zx0, ...] = True
                self._data.mask[zx1:, ...] = True
                self._data.mask[..., :zy0] = True
                self._data.mask[..., zy1:] = True
                # copy & colorize region
                self._data[zx0:zx1, zy0:zy1] = image.image()[ix0:ix1, iy0:iy1]
                intensity = image.intensityMap().remap(self._data)
                self._zi.setImage(
                    image.colorMap().colorize(image.intensityMap().remap(self._data)).transformed(self._xform))
                self._zi.setVisible(True)
            # set cross-sections
            if self._showcs.isChecked():
                if iy >= 0 and iy < ny and ix1 > ix0:
                    # added fix for masked arrays and mosaic images
                    xcs = [float(x) for x in numpy.ma.filled(image.image()[ix0:ix1, iy], fill_value=0.0)]
                    self._xcs.setData(numpy.arange(ix0 - 1, ix1) + .5, [xcs[0]] + xcs)
                    self._xcs.setVisible(True)
                    self._zoomplot.setAxisAutoScale(QwtPlot.yRight)
                    self._has_xcs = True
                else:
                    self._xcs.setVisible(False)
                    self._zoomplot.setAxisScale(QwtPlot.yRight, 0, 1)
                if ix >= 0 and ix < nx and iy1 > iy0:
                    # added fix for masked arrays and mosaic images
                    ycs = [float(y) for y in numpy.ma.filled(image.image()[ix, iy0:iy1], fill_value=0.0)]
                    self._ycs.setData([ycs[0]] + ycs, numpy.arange(iy0 - 1, iy1) + .5)
                    self._ycs.setVisible(True)
                    self._zoomplot.setAxisAutoScale(QwtPlot.xTop)
                    self._has_ycs = True
                else:
                    self._ycs.setVisible(False)
                    self._zoomplot.setAxisScale(QwtPlot.xTop, 0, 1)
        else:
            for plotitem in self._zi, self._xcs, self._ycs:
                plotitem.setVisible(False)
        # set zoom plot scales
        x0, x1 = ix - self._radius - .5, ix + self._radius + .5
        y0, y1 = iy - self._radius - .5, iy + self._radius + .5
        self._reticules[0].setData([ix, ix], [y0, y1])
        self._reticules[1].setData([x0, x1], [iy, iy])
        self._zoomplot.setAxisScale(QwtPlot.xBottom, x0, x1)
        self._zoomplot.setAxisScale(QwtPlot.yLeft, y0, y1)
        self._zoomplot.enableAxis(QwtPlot.xTop, self._showcs.isChecked())
        # update plots
        self._zoomplot.replot()


class LiveProfile(ToolDialog):
    def __init__(self, parent, mainwin, configname="liveprofile", menuname="profiles", show_shortcut=Qt.Key_F3):
        ToolDialog.__init__(self, parent, mainwin, configname=configname, menuname=menuname, show_shortcut=show_shortcut)
        self.setWindowTitle("Profiles")
        self._profplot = None
        self._setupLayout()
        self._axes = []
        self._lastsel = None
        self._image_id = None
        self._image_hnd = None
        self._last_x = None
        self._last_y = None
        self._parent_picker = None
        self._last_data_x = None
        self._last_data_y = None
        self._selaxis = None

    def _setupAxisSelectorLayout(self, lo1):
        lo1.setContentsMargins(0, 0, 0, 0)
        lab = QLabel("Axis: ", self)
        self._wprofile_axis = QComboBox(self)
        self._wprofile_axis.activated[int].connect(self.selectAxis)
        lo1.addWidget(lab, 0)
        lo1.addWidget(self._wprofile_axis, 0)
        lo1.addStretch(1)

    def _setupPlot(self):
        lo0 = self._lo0
        liveprofile_policy = self._liveprofile_policy
        self._font = font = QApplication.font()

        # detach and release plots if already initialized
        if self._profplot is not None:
            self._profcurve.setData([0, 0], [0, 0])
            self._profcurve.setVisible(True)
            self._profplot.replot()
            self._profplot.setMaximumHeight(256)
            self._profplot.setMinimumHeight(256)
        else:
            self._profplot = QwtPlot(self)
            self._profplot.setContentsMargins(0, 0, 0, 0)
            self._profplot.enableAxis(QwtPlot.xBottom)
            self._profplot.enableAxis(QwtPlot.yLeft)
            self._profplot.setAxisFont(QwtPlot.xBottom, font)
            self._profplot.setAxisFont(QwtPlot.yLeft, font)
            #    self._profplot.setAxisMaxMajor(QwtPlot.xBottom,3)
            self._profplot.setAxisAutoScale(QwtPlot.yLeft)
            self._profplot.setAxisMaxMajor(QwtPlot.yLeft, 3)
            self._profplot.axisWidget(QwtPlot.yLeft).setMinBorderDist(16, 16)
            self._profplot.setAxisLabelRotation(QwtPlot.yLeft, -90)
            self._profplot.setAxisLabelAlignment(QwtPlot.yLeft, Qt.AlignVCenter)
            self._profplot.plotLayout().setAlignCanvasToScales(True)
            self._profplot.setMaximumHeight(256)
            self._profplot.setMinimumHeight(56)
            # self._profplot.setMinimumWidth(256)
            # self._profplot.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            self._profplot.setSizePolicy(liveprofile_policy)
            lo0.addWidget(self._profplot, 0)
            # and new profile curve
            self._profcurve = TiggerPlotCurve("Active")
            self._profcurve.setRenderHint(QwtPlotItem.RenderAntialiased)
            self._ycs = TiggerPlotCurve()
            self._ycs.setRenderHint(QwtPlotItem.RenderAntialiased)
            self._profcurve.setPen(QPen(QColor("white")))
            self._profcurve.setStyle(QwtPlotCurve.Lines)
            self._profcurve.setOrientation(Qt.Horizontal)
            self._profcurve.attach(self._profplot)

    def _setupLayout(self):
        # create size policy for live profile
        liveprofile_policy = QSizePolicy()
        liveprofile_policy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        liveprofile_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self._liveprofile_policy = liveprofile_policy
        self.setSizePolicy(liveprofile_policy)
        # add plots
        lo0 = QVBoxLayout(self)
        lo0.setSpacing(0)
        self._lo0 = lo0

        lo1 = QHBoxLayout()
        lo1.setContentsMargins(0, 0, 0, 0)
        lo0.addLayout(lo1)
        self._setupAxisSelectorLayout(lo1)
        # add profile plot
        self._setupPlot()
        # config geometry
        if not self.initGeometry():
            self.resize(300, 192)

    def setImage(self, image, force_repopulate=False):
        if image is None:
            return
        if id(image) == self._image_id and not force_repopulate:
            return
        self._image_id = id(image)
        self._image_hnd = image

        # build list of axes -- first X and Y
        self._axes = []
        for n, label in enumerate(("X", "Y")):
            iaxis, np = image.getSkyAxis(n)
            self._axes.append((label, iaxis, list(range(np)), "pixels"))
        self._xaxis = self._axes[0][1]
        self._yaxis = self._axes[1][1]
        # then, extra axes
        for i in range(image.numExtraAxes()):
            iaxis, name, labels = image.extraAxisNumberNameLabels(i)
            if len(labels) > 1 and name.upper() not in ("STOKES", "COMPLEX"):
                values = image.extraAxisValues(i)
                unit, scale = image.extraAxisUnitScale(i)
                self._axes.append((name, iaxis, [x / scale for x in values], unit))
        # put them into the selector
        names = [name for name, iaxis, vals, unit in self._axes]
        self._wprofile_axis.addItems(names)
        if self._lastsel in names:
            axis = names.index(self._lastsel)
        elif len(self._axes) > 2:
            axis = 2
        else:
            axis = 0
        self._wprofile_axis.setCurrentIndex(axis)
        self.selectAxis(axis, remember=False)

    def selectAxis(self, i, remember=True):
        if i is None:
            return
        if i < len(self._axes):
            name, iaxis, values, unit = self._axes[i]
            self._selaxis = iaxis, values
            self._profplot.setAxisScale(QwtPlot.xBottom, min(values), max(values))
            title = QwtText("%s, %s" % (name, unit) if unit else name)
            title.setFont(self._font)
            self._profplot.setAxisTitle(QwtPlot.xBottom, title)
            # save selection
            if remember:
                self._lastsel = name

    def trackImage(self, image, ix, iy, il, im):
        if not self.isVisible():
            return
        if ix is None or iy is None:
            return

        nx, ny = image.imageDims()
        inrange = ix < nx and ix >= 0 and iy < ny and iy >= 0
        if inrange:
            # check if image has changed
            self.setImage(image)
            # make profile slice
            iaxis, xval = self._selaxis
            slicer = image.currentSlice()
            slicer[self._xaxis] = ix
            slicer[self._yaxis] = iy
            slicer[iaxis] = slice(None)
            yval = image.data()[tuple(slicer)]
            i0, i1 = 0, len(xval)
            # if X or Y profile, set axis scale to match that of window
            if iaxis == 0:
                rect = image.currentRectPix()
                i0 = rect.topLeft().x()
                i1 = i0 + rect.width()
                self._profplot.setAxisScale(QwtPlot.xBottom, xval[i0], xval[i1 - 1])
            elif iaxis == 1:
                rect = image.currentRectPix()
                i0 = rect.topLeft().y()
                i1 = i0 + rect.height()
                self._profplot.setAxisScale(QwtPlot.xBottom, xval[i0], xval[i1 - 1])
            # added fix for masked arrays and mosaic images
            yval = numpy.ma.filled(yval[i0:i1], fill_value=0.0)
            xval = numpy.ma.filled(xval[i0:i1], fill_value=0.0)
            self._profcurve.setData(xval, yval)
            # store the data slice for the last pixel coordinate
            self._last_data_x = xval
            self._last_data_y = yval
            # store profile last update coordinates
            self._last_x = ix
            self._last_y = iy
            self._last_l = il
            self._last_m = im
        self._profcurve.setVisible(inrange)
        # update plots
        self._profplot.replot()


class SelectedProfile(LiveProfile):
    """ 'Freezed' profile showing profile for axis at selected cube pierce point """
    def __init__(self,
                 parent,
                 mainwin,
                 configname="liveprofile",
                 menuname="profiles",
                 show_shortcut=Qt.Key_F4,
                 picker_parent=None):
        self.profiles_info = {}
        self._legend = None
        self._numprofiles = 0
        self._currentprofile = 0
        self._parent_picker = None
        self._current_profile_name = None
        self._export_profile_dialog = None
        self._load_profile_dialog = None
        self._overlay_static_profiles = None
        self._lastxmin = None
        self._lastxmax = None
        self._lastxtitle = None
        LiveProfile.__init__(self, parent, mainwin, configname, menuname, show_shortcut)
        self.addProfile()
        self._parent_picker = picker_parent

    def _setupAxisSelectorLayout(self, lo1):
        """ Adds controls for freeze pane profile dialog """
        lo2 = QGridLayout()
        self._menu = QMenu("Selected Profile", self)

        def __inputNewName():
            text, ok = QInputDialog.getText(
                self,
                "Set profile name",
                "<P>Enter new name for profile:</P>",
                text=self._current_profile_name)
            if text:
                self.setProfileName(text)
        self._menu.addAction("Clear profile", self.clearProfile)
        self._menu.addAction("Set profile name", __inputNewName)
        self._menu.addAction("Save active profile as", self.saveProfile)
        self._menu.addAction("Overlay TigProf static profile from file", self.loadProfile)
        self._menu_opt_paste = self._menu.addAction(
            "Overlay another active profile as static profile",
            self.pasteActiveProfileAsStatic)

        def __sepaction():
            pass
        self._menu.addAction("-- Global settings --", __sepaction).setEnabled(False)
        self._menu.addAction("Set active selected profile marker colour", self.setSelProfileMarkerColour)
        self._menu.addAction("Set inactive selected profile marker colour", self.setUnselProfileMarkerColour)
        self._profile_ctrl_btn = QToolButton()
        self._profile_ctrl_btn.setMenu(self._menu)
        self._profile_ctrl_btn.setToolTip("<P> Click to show options for this profile </P>")
        self._profile_ctrl_btn.setIcon(pixmaps.raise_up.icon())
        lo2.addWidget(self._profile_ctrl_btn, 0, 0, 1, 1)

        lab = QLabel("Selected profile: ")
        lo2.addWidget(lab, 0, 1, 1, 1)
        self._static_profile_select = QComboBox(self)
        lo2.addWidget(self._static_profile_select, 0, 2, 1, 1)

        self._static_profile_select.activated[int].connect(self.selectProfile)
        self._add_profile_btn = QToolButton()
        self._add_profile_btn.setIcon(pixmaps.big_plus.icon())
        self._add_profile_btn.setToolTip("<P> Click to add another freezed profile </P>")
        lo2.addWidget(self._add_profile_btn, 0, 3, 1, 1)
        self._add_profile_btn.clicked.connect(self.addProfile)

        lo3 = QHBoxLayout()
        lo3.setContentsMargins(0, 0, 0, 0)
        lab = QLabel("Axis: ", self)
        self._wprofile_axis = QComboBox(self)
        self._wprofile_axis.activated[int].connect(self.selectAxis)
        lo3.addWidget(lab, 0)
        lo3.addWidget(self._wprofile_axis, 0)

        lo2.addLayout(lo3, 0, 4, 1, 2, alignment=Qt.AlignRight)

        lo1.setContentsMargins(0, 0, 0, 0)
        lo1.addLayout(lo2)

    def selectProfile(self, i):
        """ event handler for switching profiles """
        self._storeSelectedProfileInfos()
        # detach overlay profiles for previous profile
        if self._overlay_static_profiles is not None:
            for p in self._overlay_static_profiles:
                p.detach()
        # pick new state from the stack and restore
        self._currentprofile = i
        self._restoreSelectedProfileInfos()
        self._wprofile_axis.clear()
        # switch to corresponding image and set the axis
        self.setImage(self._image_hnd, force_repopulate=True)
        if self._lastsel is not None:
            names = [name for name, iaxis, vals, unit in self._axes]
            axisno = names.index(self._lastsel)
            # select axis, which in turn redraws the plot
            self.selectAxis(axisno)
            self._wprofile_axis.setCurrentIndex(axisno)
        else:
            self.clearProfile(keep_overlays=True)
        # update marker on the SkyPlot
        if self._parent_picker is not None:
            self._parent_picker.setSelectedProfileIndex(i)
        # overlay other static plots for current profile
        if self._overlay_static_profiles is not None:
            for p in self._overlay_static_profiles:
                p.attach()
            # restore temporary vmin, vmax and xtitle
            # if the profile has no active profile
            # -- other static profiles may have been loaded
            # to an empty profile
            if ((self._last_data_x is None or self._last_data_y is None)
                    and len(self._overlay_static_profiles) > 0):
                if self._lastxmin is not None and self._lastxmax is not None:
                    self._profplot.setAxisScale(QwtPlot.xBottom,
                                                self._lastxmin, self._lastxmax)
                    self._profplot.replot()
                if self._lastxtitle is not None:
                    self.setPlotAxisTitle()
                    self._profplot.replot()

    def _profileInfosKeys(self):
        return ["_lastsel", "_image_id", "_image_hnd",
                "_last_x", "_last_y",
                "_last_l", "_last_m",
                "_last_data_x", "_last_data_y",
                "_lastxmin", "_lastxmax", "_lastxtitle",
                "_current_profile_name", "_overlay_static_profiles",
                "_axes", "_selaxis"]

    def _restoreSelectedProfileInfos(self):
        """ restores the profile infos for the currently selected profile """
        profiles_info_keys = self._profileInfosKeys()
        for k in profiles_info_keys:
            setattr(self, k, self.profiles_info[self._currentprofile].get(k))

    def _storeSelectedProfileInfos(self):
        """ store the profile infos for selected profile switching """
        profiles_info_keys = self._profileInfosKeys()
        self.profiles_info[self._currentprofile] = dict(zip(profiles_info_keys,
                                                            map(lambda k: getattr(self, k, None),
                                                                profiles_info_keys)))

    def clearProfile(self, keep_overlays=False):
        self._last_x = None
        self._last_y = None
        self._last_data_x = None
        self._last_data_y = None
        if not keep_overlays:
            if self._overlay_static_profiles is not None:
                for p in self._overlay_static_profiles:
                    p.detach()
            self._overlay_static_profiles = None
        if self._legend is not None:
            self._legend = None

        self._setupPlot()
        if self._parent_picker is not None:
            if not keep_overlays:
                self._parent_picker.removeSelectedProfileMarkings(self._currentprofile,
                                                                  purge_history=True)

    def setProfileName(self, name):
        self._current_profile_name = name
        self._static_profile_select.setItemText(self._currentprofile, name)

    def addProfile(self):
        """ event handler for adding new selected profiles """
        self._numprofiles += 1
        self._static_profile_select.addItems(["tmp"])

        profiles_info_keys = self._profileInfosKeys()
        self.profiles_info[self._numprofiles-1] = dict(zip(profiles_info_keys,
                                                           [None] * len(profiles_info_keys)))

        # switch to newly created profile
        self.selectProfile(self._numprofiles-1)
        self._static_profile_select.setCurrentIndex(self._numprofiles-1)
        self._wprofile_axis.clear()
        # refresh profile for blank profile
        self.clearProfile()
        self._overlay_static_profiles = None
        # reinitialize axes
        self.setImage(self._image_hnd, force_repopulate=False)

        self.setProfileName(f"Profile {self._numprofiles}")

    def selectAxis(self, i, remember=True):
        LiveProfile.selectAxis(self, i, remember=True)
        self.trackImage(self._image_hnd, self._last_x, self._last_y, self._last_l, self._last_m)
        # clear profile if no coordinate is set
        if self._last_y is None or self._last_x is None:
            self.clearProfile(keep_overlays=True)

    def setImage(self, image, force_repopulate=False):
        if self._image_id != id(image):
            self._wprofile_axis.clear()
        LiveProfile.setImage(self, image, force_repopulate=force_repopulate)

    def setVisible(self, visible, emit=True):
        LiveProfile.setVisible(self, visible, emit=emit)
        if self._parent_picker is not None:
            if visible:
                self._parent_picker.setSelectedProfileIndex(self._currentprofile)
            else:
                self._parent_picker.removeAllSelectedProfileMarkings()

    def saveProfile(self, filename=None):
        """ Saves current profile to disk """
        if self._selaxis and self._selaxis[0] < len(self._axes) and \
           self._last_x is not None and \
           self._last_y is not None and \
           self._last_data_x is not None and \
           self._last_data_y is not None:
            if filename is None:
                if not self._export_profile_dialog:
                    dialog = self._export_profile_dialog = QFileDialog(
                        self, "Export profile data", ".", "*.tigprof")
                    dialog.setDefaultSuffix("tigprof")
                    dialog.setFileMode(QFileDialog.AnyFile)
                    dialog.setAcceptMode(QFileDialog.AcceptSave)
                    dialog.setNameFilter("Tigger profile files (*.tigprof)")
                    dialog.setModal(True)
                    dialog.filesSelected.connect(self.saveProfile)
                return self._export_profile_dialog.exec_() == QDialog.Accepted

            axisname, axisindx, axisvals, axisunit = self._axes[self._selaxis[0]]

            if isinstance(filename, QStringList):
                filename = filename[0]
            if os.path.exists(filename):
                ret = QMessageBox.question(
                    self, "Overwrite file?",
                    f"File {filename} exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No:
                    return
            prof = TiggerProfile(self._current_profile_name,
                                 axisname,
                                 axisunit,
                                 self._last_data_x,
                                 self._last_data_y)
            try:
                prof.saveProfile(filename)
            except IOError:
                QMessageBox.critical(
                    self, "Could not store profile to disk",
                    "<P> An IO error occurred while trying to write out profile. "
                    "Check that the location is writable and you have sufficient space </P>"
                )

        else:  # no axes selected yet
            QMessageBox.critical(
                self, "Nothing to save",
                "<P> Profile is empty. Capture profile using CTRL+ALT+LeftClick "
                "somewhere on the image first!</P>")

    def loadProfile(self, filename=None):
        """ Loads TigProf profile from disk """
        if filename is None:
            if not self._load_profile_dialog:
                dialog = self._load_profile_dialog = QFileDialog(
                    self, "Load TigProf profile data", ".", "*.tigprof")
                dialog.setDefaultSuffix("tigprof")
                dialog.setFileMode(QFileDialog.ExistingFile)
                dialog.setAcceptMode(QFileDialog.AcceptOpen)
                dialog.setNameFilter("Tigger profile files (*.tigprof)")
                dialog.setModal(True)
                dialog.filesSelected.connect(self.loadProfile)
            return self._load_profile_dialog.exec_() == QDialog.Accepted

        if isinstance(filename, QStringList):
            filename = filename[0]

        try:
            prof = TiggerProfileFactory.load(filename)
        except IOError as e:
            QMessageBox.critical(
                self,
                "Error loading TigProf profile",
                f"Loading failed with message '{str(e)}'"
            )
        else:
            self.addStaticProfile(prof)

    def addStaticProfile(self, prof, curvecol=None, coord=None):
        pastedname, ok = QInputDialog.getText(self,
                                              "Set pasted profile name",
                                              "<P> Set name of pasted profile </P>",
                                              text=prof.profileName)
        plottableprof = PlottableTiggerProfile(pastedname,
                                               prof.axisName,
                                               prof.axisUnit,
                                               prof.xdata,
                                               prof.ydata,
                                               qwtplot=self._profplot,
                                               profilecoord=coord)
        if curvecol is None:
            curvecol = QColorDialog.getColor(initial=Qt.white,
                                             parent=self,
                                             title="Select color for loaded TigProf profile",)
        if curvecol.isValid():
            plottableprof.setCurveColor(curvecol)

        if self._overlay_static_profiles is None:
            self._overlay_static_profiles = []
        self._overlay_static_profiles.append(plottableprof)
        if ((self._last_data_x is None or self._last_data_y is None
             or self._last_data_x is None or self._last_data_y is None)
                and len(self._overlay_static_profiles) > 0):
            # temporary titles and labels from pasted profiles
            xmin = numpy.nanmin(list(map(lambda x: numpy.nanmin(x.xdata),
                                         self._overlay_static_profiles)))
            xmax = numpy.nanmax(list(map(lambda x: numpy.nanmax(x.xdata),
                                         self._overlay_static_profiles)))
            self._lastxmin = xmin
            self._lastxmax = xmax
            self._profplot.setAxisScale(QwtPlot.xBottom, self._lastxmin, self._lastxmax)
            # set custom label if first loaded profile
            if len(self._overlay_static_profiles) == 1:
                name, ok = QInputDialog.getText(self,
                                                "Set custom axis name",
                                                "<P> Set custom axis name for loaded static profile </P>",
                                                text=self._overlay_static_profiles[0].axisName)
                unit, ok = QInputDialog.getText(self,
                                                "Set custom axis unit",
                                                "<P> Set custom axis unit for loaded static profile </P>",
                                                text=self._overlay_static_profiles[0].axisUnit)
                self._lastxtitle = "%s, %s" % (name, unit) if unit else name
                self.setPlotAxisTitle()
        if self._legend is None:
            self._legend = QwtLegend()
            self._profplot.insertLegend(self._legend, QwtPlot.BottomLegend)

        if self._parent_picker is not None and coord is not None:
            self._parent_picker.addOverlayMarkerToCurrentProfile(
                pastedname, coord, plottableprof.createPen(), index=self._currentprofile)

    def setPlotAxisTitle(self):
        title = QwtText(self._lastxtitle)
        title.setFont(self._font)
        self._profplot.setAxisTitle(QwtPlot.xBottom, title)

    def pasteActiveProfileAsStatic(self):
        def __constructProfileIndex(i):
            last_x = self.profiles_info.get(i, {}).get("_last_x", None)
            last_y = self.profiles_info.get(i, {}).get("_last_y", None)
            last_l = self.profiles_info.get(i, {}).get("_last_l", None)
            last_m = self.profiles_info.get(i, {}).get("_last_m", None)
            last_data_x = self.profiles_info.get(i, {}).get("_last_data_x", None)
            last_data_y = self.profiles_info.get(i, {}).get("_last_data_y", None)
            selaxis = self.profiles_info.get(i, {}).get("_selaxis", None)
            axes = self.profiles_info.get(i, {}).get("_axes", None)

            if (selaxis and selaxis[0] < len(axes) and last_x is not None
                    and last_y is not None and last_l is not None
                    and last_m is not None and last_data_x is not None
                    and last_data_y is not None and selaxis is not None
                    and axes is not None):
                profname = self.profiles_info.get(i, {}).get("_current_profile_name", "Unnamed")
                axisname, axisindx, axisvals, axisunit = axes[selaxis[0]]
                prof = TiggerProfile(profname, axisname, axisunit, last_data_x, last_data_y)
                return (prof, i, (last_l, last_m))
            return None

        avail_profs = list(filter(lambda x: x is not None,
                                  map(lambda i: __constructProfileIndex(i),
                                      filter(lambda i: i != self._currentprofile,
                                             range(self._static_profile_select.count())))))
        if len(avail_profs) == 0:
            QMessageBox.critical(
                self, "No active profiles available",
                "<P> There are currently no active profiles available for selection in any other profile. "
                "You need to use CTRL+ALT+leftclick on another profile to first in order to paste </P>"
            )
            return

        selitem, ok = QInputDialog.getItem(self,
                                           "Paste active profile from",
                                           "<P>Select from currently defined profiles:</P>",
                                           list(map(lambda x: x[0].profileName, avail_profs)),
                                           current=0,
                                           editable=False)
        if ok:
            selprof, iselitem, coord = list(filter(lambda x: x[0].profileName == selitem, avail_profs))[0]
            dprint(0, f"Pasting active profile from '{selprof.profileName}'")
            self.addStaticProfile(selprof, coord=coord)

    def setSelProfileMarkerColour(self, color=None):
        """ Set marker colour for the selected profile active profile curve """
        if self._parent_picker is not None:
            default = self._parent_picker.activeSelectedProfileMarkerColor
            if color is None:
                color = QColorDialog.getColor(initial=default,
                                              parent=self,
                                              title="Select color for selected active profile marker",)
            if color.isValid():
                self._parent_picker.activeSelectedProfileMarkerColor = color

    def setUnselProfileMarkerColour(self, color=None):
        """ Set marker colour for the non-selected profile active profile curve """
        if self._parent_picker is not None:
            default = self._parent_picker.inactiveSelectedProfileMarkerColor
            if color is None:
                color = QColorDialog.getColor(initial=default,
                                              parent=self,
                                              title="Select color for selected active profile marker",)
            if color.isValid():
                self._parent_picker.inactiveSelectedProfileMarkerColor = color
