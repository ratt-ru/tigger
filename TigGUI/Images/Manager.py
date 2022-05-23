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

import os.path
from re import split
import sys
import time
import traceback

import numpy
from PyQt5.Qt import (QWidget, QFileDialog, QVBoxLayout, QApplication, QMenu, QClipboard, QInputDialog, QActionGroup, QTextOption, QFont)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDockWidget, QLabel, QPlainTextEdit
from astropy.io import fits as pyfits
from astropy.wcs import WCS
from astropy.io.fits import Header

from TigGUI.Images import FITS_ExtensionList
from TigGUI.Images import SkyImage
from TigGUI.Images.SkyImage import FITSImagePlotItem
from TigGUI.Images.Controller import ImageController, dprint
from TigGUI.kitties.utils import PersistentCurrier
from TigGUI.kitties.widgets import BusyIndicator

QStringList = list


class ImageManager(QWidget):
    """An ImageManager manages a stack of images (and associated ImageControllers)"""
    showErrorMessage = pyqtSignal(str, int)
    imagesChanged = pyqtSignal()
    imageRaised = pyqtSignal(FITSImagePlotItem)
    imagePlotRaised = pyqtSignal()

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.mainwin = None
        # init layout
        self._lo = QVBoxLayout(self)
        self._lo.setContentsMargins(0, 0, 0, 0)
        self._lo.setSpacing(0)
        # init internal state
        self._currier = PersistentCurrier()
        self._z0 = 0  # z-depth of first image, the rest count down from it
        self._updating_imap = False
        self._locked_display_range = False
        self._imagecons = []
        self._imagecon_loadorder = []
        self._center_image = None
        self._plot = None
        self._border_pen = None
        self._drawing_key = None
        self._load_image_dialog = None
        self._label_color = None
        self._label_bg_brush = None
        self._model_imagecons = set()
        # init menu and standard actions
        self._menu = QMenu("&Image", self)
        qag = QActionGroup(self)
        # exclusive controls for plotting topmost or all images
        self._qa_plot_top = qag.addAction("Display topmost image only")
        self._qa_plot_all = qag.addAction("Display all images")
        self._qa_plot_top.setCheckable(True)
        self._qa_plot_all.setCheckable(True)
        self._qa_plot_top.setChecked(True)
        self._qa_plot_all.toggled[bool].connect(self._displayAllImages)
        self._closing = False

        self._qa_load_clipboard = None
        self._clipboard_mode = QClipboard.Clipboard
        QApplication.clipboard().changed[QClipboard.Mode].connect(self._checkClipboardPath)
        # populate the menu
        self._repopulateMenu()
        self.signalShowMessage = None
        self.signalShowErrorMessage = None
        # FITS header preview pane
        self.fits_info = QPlainTextEdit()

    def close(self):
        dprint(1, "closing Manager")
        self._closing = True
        for ic in self._imagecons:
            ic.close()

    def setShowMessageSignal(self, _signal):
        self.signalShowMessage = _signal

    def setShowErrorMessageSignal(self, _signal):
        self.signalShowErrorMessage = _signal

    def setMainWindow(self, _mainwin):
        self.mainwin = _mainwin

    def FITSHeaderPreview(self, fname):
        """Loads information for the FITS header preview pane.
        Connected via the QFileDialog currentChanged signal.
        """
        if os.path.isfile(fname):
            name = os.path.basename(fname)
            split_name = os.path.splitext(name)
            if split_name[1].startswith(tuple(FITS_ExtensionList)):
                try:
                    with pyfits.open(fname) as hdu:
                        hdu.verify('silentfix')
                        hdr = hdu[0].header
                        self.fits_info.setPlainText(
                            "[File size: " + str(round(hdu._file.tell()/1024/1024, 2)) + " MiB]\n" + hdr.tostring(sep='\n', padding=True))
                except:
                    self.fits_info.setPlainText("Error Reading FITS file")
        else:
            self.fits_info.clear()

    def loadImage(self, filename=None, duplicate=True, to_top=True, model=None):
        """Loads image. Returns ImageControlBar object.
        If image is already loaded: returns old ICB if duplicate=False (raises to top if to_top=True),
        or else makes a new control bar.
        If model is set to a source name, marks the image as associated with a model source. These can be unloaded en masse by calling
        unloadModelImages().
        """
        if filename is None:
            if not self._load_image_dialog:
                dialog = self._load_image_dialog = QFileDialog(self, "Load FITS image", ".",
                                                               "FITS images (%s);;All files (*)" % (" ".join(
                                                                   ["*" + ext for ext in FITS_ExtensionList])),
                                                               options=QFileDialog.DontUseNativeDialog)
                dialog.setFileMode(QFileDialog.ExistingFile)
                dialog.setModal(True)
                dialog.filesSelected['QStringList'].connect(self.loadImage)
                layout = dialog.layout()
                if layout:
                    # FITS header preview pane
                    dialog.currentChanged.connect(self.FITSHeaderPreview)
                    self.fits_info.setMinimumWidth(263)
                    dialog.setMinimumWidth(dialog.width() + self.fits_info.minimumWidth())
                    self.fits_info.setWordWrapMode(QTextOption.NoWrap)
                    self.fits_info.setLineWrapMode(QPlainTextEdit.NoWrap)
                    self.fits_info.setTabStopWidth(40)
                    f = QFont()
                    f.setFamily("Monospace")
                    f.setPointSize(10)
                    f.setFixedPitch(True)
                    self.fits_info.setFont(f)
                    self.fits_info.setReadOnly(True)
                    _flabel = QLabel("FITS File Information")
                    _flabel.setAlignment(Qt.AlignHCenter)
                    layout.addWidget(_flabel, 0, 3)
                    layout.addWidget(self.fits_info, 1, 3, 3, 1)
                    dialog.setLayout(layout)
            self._load_image_dialog.exec_()
            return None
        if isinstance(filename, QStringList):
            filename = filename[0]
        filename = str(filename)
        # report error if image does not exist
        if not os.path.exists(filename):
            self.signalShowErrorMessage.emit("""FITS image %s does not exist.""" % filename)
            return None
        # see if image is already loaded
        if not duplicate:
            for ic in self._imagecons:
                if ic.getFilename() and os.path.samefile(filename, ic.getFilename()):
                    if to_top:
                        self.raiseImage(ic)
                    if model:
                        self._model_imagecons.add(id(ic))
                    return ic
        # load the FITS image
        busy = BusyIndicator()
        dprint(2, "reading FITS image", filename)
        self.signalShowMessage.emit("""Reading FITS image %s""" % filename, 3000)
        QApplication.flush()
        try:
            image = SkyImage.FITSImagePlotItem(str(filename))
        except KeyboardInterrupt:
            raise
        except:
            busy.reset_cursor()
            traceback.print_exc()
            print("""Error loading FITS image %s: %s. This may be due to a bug in Tigger; if the FITS file loads fine in another viewer,
          please send the FITS file, along with a copy of any error messages from the text console, to osmirnov@gmail.com.""" % (
                filename, str(sys.exc_info()[1])))
            self.signalShowErrorMessage.emit("""<P>Error loading FITS image %s: %s. This may be due to a bug in Tigger; if the FITS file loads fine in another viewer,
          please send the FITS file, along with a copy of any error messages from the text console, to osmirnov@gmail.com.</P>""" % (
                filename, str(sys.exc_info()[1])))
            return None
        # create control bar, add to widget stack
        ic = self._createImageController(image, "model source '%s'" % model if model else filename, model or image.name,
                                         model=model)
        print("""Loaded FITS image %s""" % filename)
        self.signalShowMessage.emit("""Loaded FITS image %s""" % filename, 3000)
        busy.reset_cursor()
        return ic

    def setZ0(self, z0):
        self._z0 = z0
        if self._imagecons:
            self.raiseImage(self._imagecons[0])

    def enableImageBorders(self, border_pen, label_color, label_bg_brush):
        self._border_pen, self._label_color, self._label_bg_brush = \
            border_pen, label_color, label_bg_brush

    def lockAllDisplayRanges(self, rc0, curry=False):
        """Locks all display ranges, and sets the intensity from rc0"""
        if not self._updating_imap:
            self._updating_imap = True
            rc0.lockDisplayRange()
            try:
                for ic in self._imagecons:
                    rc1 = ic.renderControl()
                    if rc1 is not rc0:
                        rc1.setDisplayRange(*rc0.displayRange())
                        rc1.lockDisplayRange()
            finally:
                self._updating_imap = False

    def unlockAllDisplayRanges(self):
        """Unlocks all display range."""
        for ic in self._imagecons:
            ic.renderControl().lockDisplayRange(False)

    def _lockDisplayRange(self, rc0, lock):
        """Locks or unlocks the display range of a specific controller."""
        if lock and not self._updating_imap:
            self._updating_imap = True
            try:
                # if something is already locked, copy display range from it
                for ic in self._imagecons:
                    rc1 = ic.renderControl()
                    if rc1 is not rc0 and rc1.isDisplayRangeLocked():
                        rc0.setDisplayRange(*rc1.displayRange())
            finally:
                self._updating_imap = False

    def _updateDisplayRange(self, rc, dmin, dmax):
        """This is called whenever one of the images (or rather, its associated RenderControl object) changes its display range."""
        if not rc.isDisplayRangeLocked():
            return
        # If the display range is locked, propagate it to all images.
        # but don't do it if we're already propagating (otherwise we may get called in an infinte loop)
        if not self._updating_imap:
            self._updating_imap = True
            try:
                for ic in self._imagecons:
                    rc1 = ic.renderControl()
                    if rc1 is not rc and rc1.isDisplayRangeLocked():
                        rc1.setDisplayRange(dmin, dmax)
            finally:
                self._updating_imap = False

    def getImages(self):
        return [ic.image for ic in self._imagecons]

    def getTopImage(self):
        return (self._imagecons or None) and self._imagecons[0].image

    def cycleImages(self):
        index = self._imagecon_loadorder.index(self._imagecons[0])
        index = (index + 1) % len(self._imagecon_loadorder)
        self.raiseImage(self._imagecon_loadorder[index])

    def blinkImages(self):
        if len(self._imagecons) > 1:
            self.raiseImage(self._imagecons[1])

    def incrementSlice(self, extra_axis, incr):
        if self._imagecons:
            rc = self._imagecons[0].renderControl()
            sliced_axes = rc.slicedAxes()
            if extra_axis < len(sliced_axes):
                rc.incrementSlice(sliced_axes[extra_axis][0], incr)

    def setLMRectSubset(self, rect):
        if self._imagecons:
            self._imagecons[0].setLMRectSubset(rect)

    def getLMRectStats(self, rect):
        if self._imagecons:
            return self._imagecons[0].renderControl().getLMRectStats(rect)

    def unloadModelImages(self):
        """Unloads images associated with model (i.e. loaded with the model=True flag)"""
        for ic in [ic for ic in self._imagecons if id(ic) in self._model_imagecons]:
            self.unloadImage(ic)

    def unloadImage(self, imagecon, foo=None):
        """Unloads the given imagecon object."""
        if imagecon not in self._imagecons:
            return
        # recenter if needed
        self._imagecons.remove(imagecon)
        self._imagecon_loadorder.remove(imagecon)
        self._model_imagecons.discard(id(imagecon))
        # remove dockable widget
        imagecon.removeDockWidget()
        # reparent widget and release it
        imagecon.setParent(None)
        imagecon.close()
        # recenter image, if unloaded the center image
        if self._center_image is imagecon.image:
            self.centerImage(self._imagecons[0] if self._imagecons else None, emit=False)
        # emit signal
        self._repopulateMenu()
        self.imagesChanged.emit()
        if self._imagecons:
            self.raiseImage(self._imagecons[0])
        else:
            # remove all dock widgets
            widget_list = self.mainwin.findChildren(QDockWidget)
            for widget in widget_list:
                self.mainwin.removeDockWidget(widget)
                widget.bind_widget.setVisible(False)
                widget.close()
            if self.mainwin._current_layout is not self.mainwin.LayoutImageModel:
                self.mainwin.skyplot.setVisible(False)
            # reset size to be minus dockables - workaround for bug #164
            # self.mainwin.setMaximumWidth(self.mainwin.width() - 700)

    def getCenterImage(self):
        return self._center_image

    def centerImage(self, imagecon, emit=True):
        self._center_image = imagecon and imagecon.image
        for ic in self._imagecons:
            ic.setPlotProjection(self._center_image.projection)
        if emit or emit is None:  # added this check as curry() call to this method via signal can be emit=None.
            self.imagesChanged.emit()

    def raiseImage(self, imagecon, foo=None):
        busy = None
        # reshuffle image stack, if more than one image image
        if len(self._imagecons) > 1:
            busy = BusyIndicator()
            # reshuffle image stack
            self._imagecons.remove(imagecon)
            self._imagecons.insert(0, imagecon)
            # notify imagecons
            for i, ic in enumerate(self._imagecons):
                label = "%d" % (i + 1) if i else "<B>1</B>"
                ic.setZ(self._z0 - i * 10, top=not i, depthlabel=label, can_raise=True)
            # adjust visibility
            for j, ic in enumerate(self._imagecons):
                ic.setImageVisible(not j or bool(self._qa_plot_all.isChecked()))
            # issue replot signal fixed with assumption that this signal is now correct according to the old version
            # self.imageRaised.emit(self._imagecons[0])  # This was the old signal
            self.imagePlotRaised.emit()
            self.fastReplot()
        # else simply update labels
        else:
            self._imagecons[0].setZ(self._z0, top=True, depthlabel=None, can_raise=False)
            self._imagecons[0].setImageVisible(True)
        # update slice menus
        img = imagecon.image
        axes = imagecon.renderControl().slicedAxes()
        for i, (_next, _prev) in enumerate(self._qa_slices):
            _next.setVisible(False)
            _prev.setVisible(False)
            if i < len(axes):
                iaxis, name, labels = axes[i]
                _next.setVisible(True)
                _prev.setVisible(True)
                _next.setText("Show next slice along %s axis" % name)
                _prev.setText("Show previous slice along %s axis" % name)
        # emit signals
        self.imageRaised.emit(img)
        # if dockable control dialog is docked and tabbed then raise to front
        if imagecon._dockable_colour_ctrl is not None:
            if imagecon._dockable_colour_ctrl.isVisible():
                if not imagecon._dockable_colour_ctrl.isFloating():
                    list_of_tabbed_widgets = self.mainwin.tabifiedDockWidgets(imagecon._dockable_colour_ctrl)
                    if list_of_tabbed_widgets:
                        imagecon._dockable_colour_ctrl.raise_()
        if busy is not None:
            busy.reset_cursor()

    def resetDrawKey(self):
        """Makes and sets the current plot's drawing key"""
        if self._plot:
            key = []
            for ic in self._imagecons:
                key.append(id(ic))
                key += ic.currentSlice()
                self._plot.setDrawingKey(tuple(key))

    def fastReplot(self, *dum):
        """Fast replot -- called when flipping images or slices. Uses the plot cache, if possible."""
        if self._plot:
            self.resetDrawKey()
            dprint(2, "calling replot", time.time() % 60)
            self._plot.replot()
            dprint(2, "replot done", time.time() % 60)

    def replot(self, *dum):
        """Proper replot -- called when an image needs to be properly redrawn. Cleares the plot's drawing cache."""
        if self._plot:
            self._plot.clearDrawCache()
            self.resetDrawKey()
            self._plot.replot()

    def attachImagesToPlot(self, plot):
        self._plot = plot
        self.resetDrawKey()
        for ic in self._imagecons:
            ic.attachToPlot(plot)

    def getMenu(self):
        return self._menu

    def _displayAllImages(self, enabled):
        busy = BusyIndicator()
        if enabled:
            for ic in self._imagecons:
                ic.setImageVisible(True)
        else:
            self._imagecons[0].setImageVisible(True)
            for ic in self._imagecons[1:]:
                ic.setImageVisible(False)
        self.replot()
        busy.reset_cursor()

    def _checkClipboardPath(self, mode=QClipboard.Clipboard):
        if self._qa_load_clipboard:
            self._clipboard_mode = mode
            try:
                path = str(QApplication.clipboard().text(mode))
            except:
                path = None
            self._qa_load_clipboard.setEnabled(bool(path and os.path.isfile(path)))

    def _loadClipboardPath(self):
        try:
            path = QApplication.clipboard().text(self._clipboard_mode)
        except:
            return
        self.loadImage(path)

    def _repopulateMenu(self):
        self._menu.clear()
        self._menu.addAction("&Load image...", self.loadImage, Qt.CTRL + Qt.Key_L)
        self._menu.addAction("&Compute image...", self.computeImage, Qt.CTRL + Qt.Key_M)
        self._qa_load_clipboard = self._menu.addAction("Load from clipboard &path", self._loadClipboardPath,
                                                       Qt.CTRL + Qt.Key_P)
        self._checkClipboardPath()
        if self._imagecons:
            self._menu.addSeparator()
            # add controls to cycle images and planes
            for i, imgcon in enumerate(self._imagecons[::-1]):
                self._menu.addMenu(imgcon.getMenu())
            self._menu.addSeparator()
            if len(self._imagecons) > 1:
                self._menu.addAction("Cycle images", self.cycleImages, Qt.Key_F5)
                self._menu.addAction("Blink images", self.blinkImages, Qt.Key_F6)
            self._qa_slices = (
                (self._menu.addAction("Next slice along axis 1", self._currier.curry(self.incrementSlice, 0, 1),
                                      Qt.Key_F7),
                 self._menu.addAction("Previous slice along axis 1", self._currier.curry(self.incrementSlice, 0, -1),
                                      Qt.SHIFT + Qt.Key_F7)),
                (self._menu.addAction("Next slice along axis 2", self._currier.curry(self.incrementSlice, 1, 1),
                                      Qt.Key_F8),
                 self._menu.addAction("Previous slice along axis 2", self._currier.curry(self.incrementSlice, 1, -1),
                                      Qt.SHIFT + Qt.Key_F8)))
            self._menu.addSeparator()
            self._menu.addAction(self._qa_plot_top)
            self._menu.addAction(self._qa_plot_all)

    def computeImage(self, expression=None):
        """Computes image from expression (if expression is None, pops up dialog)"""
        if expression is None:
            (expression, ok) = QInputDialog.getText(self, "Compute image",
                                                    """Enter an image expression to compute.
                                              Any valid numpy expression is supported, and
                                              all functions from the numpy module are available (including sub-modules such as fft).
                                              Use 'a', 'b', 'c' to refer to images.
                                              Examples:  "(a+b)/2", "cos(a)+sin(b)", "a-a.mean()", "fft.fft2(a)", etc.""")
            #      (expression,ok) = QInputDialog.getText(self,"Compute image","""<P>Enter an expression to compute.
            #        Use 'a', 'b', etc. to refer to loaded images. Any valid numpy expression is supported, and all the
            #       functions from the numpy module are available. Examples of valid expressions include "(a+b)/2",
            #       "cos(a)+sin(b)", "a-a.mean()", etc.
            #        </P>
            #      """)
            expression = str(expression)
            if not ok or not expression:
                return
        # try to parse expression
        arglist = [(chr(ord('a') + ic.getNumber()), ic.image) for ic in self._imagecons]
        try:
            exprfunc = eval("lambda " + (",".join([x[0] for x in arglist])) + ":" + expression,
                            numpy.__dict__, {})
        except Exception as exc:
            self.signalShowErrorMessage.emit("""Error parsing expression "%s": %s.""" % (expression, str(exc)))
            return None
        # try to evaluate expression
        self.signalShowMessage.emit("Computing expression \"%s\"" % expression, 10000)
        busy = BusyIndicator()
        QApplication.flush()

        # trim trivial trailing dimensions. This avoids the problem of when an NxMx1 and an NxMx1x1 arrays are added,
        # the result is promoted to NxMxMx1 following the numpy rules.
        def trimshape(shape):
            out = shape
            while out and out[-1] == 1:
                out = out[:-1]
            return out

        def trimarray(array):
            return array.reshape(trimshape(array.shape))

        try:
            result = exprfunc(*[trimarray(x[1].data()) for x in arglist])
        except Exception as exc:
            busy.reset_cursor()
            traceback.print_exc()
            self.signalShowErrorMessage.emit("""Error evaluating "%s": %s.""" % (expression, str(exc)))
            return None
        busy.reset_cursor()
        if type(result) != numpy.ma.masked_array and type(result) != numpy.ndarray:
            self.signalShowErrorMessage.emit(
                """Result of "%s" is of invalid type "%s" (array expected).""" % (expression, type(result).__name__))
            return None
        # convert coomplex results to real
        if numpy.iscomplexobj(result):
            self.signalShowErrorMessage.emit("""Result of "%s" is complex. Complex images are currently
      not fully supported, so we'll implicitly use the absolute value instead.""" % (expression))
            expression = "abs(%s)" % expression
            result = abs(result)
        # determine which image this expression can be associated with
        res_shape = trimshape(result.shape)
        arglist = [x for x in arglist if hasattr(x[1], 'fits_header') and trimshape(x[1].data().shape) == res_shape]
        if not arglist:
            self.signalShowErrorMessage.emit("""Result of "%s" has shape %s, which does not match any loaded FITS image.""" % (
                expression, "x".join(map(str, result.shape))))
            return None
        # look for an image in the arglist with the same projection, and with a valid dirname
        # (for the where-to-save hint)
        template = arglist[0][1]
        # if all images in arglist have the same projection, then it doesn't matter what we use
        # else ask
        if len([x for x in arglist[1:] if x[1].projection == template.projection]) != len(arglist) - 1:
            options = [x[0] for x in arglist]
            (which, ok) = QInputDialog.getItem(self, "Compute image",
                                               "Coordinate system to use for the result of \"%s\":" % expression,
                                               options, 0, False)
            if not ok:
                return None
            try:
                template = arglist[options.index(which)][1]
            except:
                pass
        # create a FITS image
        busy = BusyIndicator()
        dprint(2, "creating FITS image", expression)
        self.signalShowMessage.emit("""Creating image for %s""" % expression, 3000)
        QApplication.flush()
        try:
            # check and fix header
            if numpy.ndim(result) < template.fits_header.get('NAXIS'):
                dprint(2, "Fixing image header", expression)
                self.signalShowMessage.emit(f"Fixing image header for {expression}", 3000)

                # get NAXIS diff
                _naxis = template.fits_header.get('NAXIS')
                _ndims = numpy.ndim(result)

                # sub() WCS to new NAXIS
                _wcs = WCS(template.fits_header)
                _new_wcs = _wcs.wcs.sub(_ndims)

                # create new header
                _new_header = _new_wcs.to_header()
                _header = Header.fromstring(_new_header)

                # create keyword ignore list
                ignore_list = []
                for i in range(_ndims):
                    ignore_list.append(f'NAXIS{i + 1 + _ndims}')
                    ignore_list.append(f'CTYPE{i + 1 + _ndims}')
                    ignore_list.append(f'CRVAL{i + 1 + _ndims}')
                    ignore_list.append(f'CDELT{i + 1 + _ndims}')
                    ignore_list.append(f'CUNIT{i + 1 + _ndims}')
                    ignore_list.append(f'CRPIX{i + 1 + _ndims}')
                ignore_list.append('HISTORY')
                ignore_list.append('COMMENT')

                # diff the two headers
                _diff_header = pyfits.HeaderDiff(template.fits_header,
                                                 _header,
                                                 ignore_keywords=ignore_list,
                                                 ignore_comments='*')

                # update new header with missing cards
                for key in _diff_header.diff_keywords[0]:
                    _header[key] = template.fits_header[key]

                # check for PC and remove
                # a brute force approach for now
                if template.fits_header.get('PC01_01'):
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC0{i+1+_ndims}_0{n + 1}')
                            except:
                                continue
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC0{i+1}_0{n + 1+_ndims}')
                            except:
                                continue
                elif template.fits_header.get('PC1_1'):
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC{i+1+_ndims}_{n + 1}')
                            except:
                                continue
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC{i+1}_{n + 1+_ndims}')
                            except:
                                continue
                elif template.fits_header.get('PC001001'):
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC00{i+1+_ndims}00{n + 1}')
                            except:
                                continue
                    for i in range(_naxis):
                        for n in range(_naxis):
                            try:
                                _header.remove(f'PC00{i+1}00{n + 1+_ndims}')
                            except:
                                continue

                # add comments
                _comms = template.fits_header.get('COMMENT')
                if _comms:
                    for card in _comms:
                        _header.append(('COMMENT', card))

                # add history
                _hist = template.fits_header.get('HISTORY')
                if _hist:
                    for card in _hist:
                        _header.append(('HISTORY', card))

                # restore card comments
                for card in template.fits_header.keys():
                    if card in _header:
                        _comm = template.fits_header.comments[card]
                        if _comm:
                            _header.set(keyword=card, comment=_comm)

                # set new header
                template.fits_header = _header

            # create new FITS file
            hdu = pyfits.PrimaryHDU(result.transpose(), template.fits_header)
            hdu.verify('fix')
            skyimage = SkyImage.FITSImagePlotItem(name=expression,
                                                  filename=None,
                                                  hdu=hdu)
        except:
            busy.reset_cursor()
            traceback.print_exc()
            self.signalShowErrorMessage.emit("""Error creating FITS image %s: %s""" % (expression, str(sys.exc_info()[1])))
            return None
        # get directory name for save-to hint
        dirname = getattr(template, 'filename', None)
        if not dirname:
            dirnames = [getattr(img, 'filename') for x, img in arglist if hasattr(img, 'filename')]
            dirname = dirnames[0] if dirnames else None
        # create control bar, add to widget stack
        self._createImageController(skyimage, expression, expression,
                                    save=((dirname and os.path.dirname(dirname)) or "."))
        self.signalShowMessage.emit("Created new image for %s" % expression, 3000)
        dprint(2, "image created")
        busy.reset_cursor()

    def _createImageController(self, image, name, basename, model=False, save=False):
        dprint(2, "creating ImageController for", name)
        ic = ImageController(image, self, self, name, save=save)
        # attach appropriate signals
        ic.imageSignalRepaint.connect(self.replot)
        ic.imageSignalSlice.connect(self.fastReplot)
        image.connectPlotRiased(self.imagePlotRaised)
        ic.imageSignalRaise.connect(self._currier.curry(self.raiseImage, ic))
        ic.imageSignalUnload.connect(self._currier.curry(self.unloadImage, ic))
        ic.imageSignalCenter.connect(self._currier.curry(self.centerImage, ic))
        ic.setNumber(len(self._imagecons))
        self._imagecons.insert(0, ic)
        self._imagecon_loadorder.append(ic)
        if model:
            self._model_imagecons.add(id(ic))
        self._lo.addWidget(ic)
        if self._border_pen:
            ic.addPlotBorder(self._border_pen, basename, self._label_color, self._label_bg_brush)
        ic.renderControl().displayRangeChanged.connect(
            self._currier.curry(self._updateDisplayRange, ic.renderControl()))
        ic.renderControl().displayRangeLocked.connect(self._currier.curry(self._lockDisplayRange, ic.renderControl()))
        self._plot = None
        # add to menus
        dprint(2, "repopulating menus")
        self._repopulateMenu()
        # center and raise to top of stack
        self.raiseImage(ic)
        if not self._center_image:
            self.centerImage(ic, emit=False)
        else:
            ic.setPlotProjection(self._center_image.projection)
        # signal
        self.imagesChanged.emit()
        return ic
