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

import math

from PyQt5.Qt import QApplication, QBrush, QColor, QImage, QPen
from PyQt5.QtCore import Qt
from PyQt5.Qwt import QwtPlotItem, QwtSymbol, QwtText

import TigGUI
from TigGUI.Widgets import TiggerPlotMarker
from Tigger.Models import ModelClasses

_verbosity = TigGUI.kitties.utils.verbosity(name="plot")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf

# plot Z depths for various classes of objects
Z_Image = 1000
Z_Grid = 9000
Z_Source = 10000
Z_SelectedSource = 10001
Z_CurrentSource = 10002
Z_Markup = 10010
Z_MarkupOverlays = 10011

# default stepping of grid circles
DefaultGridStep_ArcSec = 30 * 60

DEG = math.pi / 180


class SourceMarker:
    """SourceMarker implements a source marker corresponding to a SkyModel source.
  The base class implements a marker at the centre.
  """
    QwtSymbolStyles = dict(none=QwtSymbol.NoSymbol,
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
                           hexagon=QwtSymbol.Hexagon)

    def __init__(self, src, l, m, size, model):
        self.src = src
        self._lm, self._size = (l, m), size
        self.plotmarker = TiggerPlotMarker()
        self.plotmarker.setRenderHint(QwtPlotItem.RenderAntialiased)
        self.plotmarker.setValue(l, m)
        self._symbol = QwtSymbol()
        self._font = QApplication.font()
        self._model = model
        self.resetStyle()

    def lm(self):
        """Returns plot coordinates of marker, as an l,m tuple"""
        return self._lm

    def lmQPointF(self):
        """Returns plot coordinates of marker, as a QPointF"""
        return self.plotmarker.value()

    def source(self):
        """Returns model source associated with marker"""
        return self.src

    def attach(self, plot):
        """Attaches to plot"""
        self.plotmarker.attach(plot)

    def isVisible(self):
        return self.plotmarker.isVisible()

    def setZ(self, z):
        self.plotmarker.setZ(z)

    def resetStyle(self):
        """Sets the source style based on current model settings"""
        self.style, self.label = self._model.getSourcePlotStyle(self.src)
        self._selected = getattr(self.src, 'selected', False)
        # setup marker components
        self._setupMarker(self.style, self.label)
        # setup depth
        if self._model.currentSource() is self.src:
            self.setZ(Z_CurrentSource)
        elif self._selected:
            self.setZ(Z_SelectedSource)
        else:
            self.setZ(Z_Source)

    def _setupMarker(self, style, label):
        """Sets up the plot marker (self.plotmarker) based on style object and label string.
    If style=None, makes marker invisible."""
        if not style:
            self.plotmarker.setVisible(False)
            return
        self.plotmarker.setVisible(True)
        self._symbol.setStyle(self.QwtSymbolStyles.get(style.symbol, QwtSymbol.Cross))
        self._font.setPointSize(style.label_size)
        symbol_color = QColor(style.symbol_color)
        label_color = QColor(style.label_color)
        # dots have a fixed size
        if style.symbol == "dot":
            self._symbol.setSize(2)
        else:
            self._symbol.setSize(int(self._size))
        self._symbol.setPen(QPen(symbol_color, style.symbol_linewidth))
        self._symbol.setBrush(QBrush(Qt.NoBrush))
        lab_pen = QPen(Qt.NoPen)
        lab_brush = QBrush(Qt.NoBrush)
        self._label = label or ""
        self.plotmarker.setSymbol(self._symbol)
        txt = QwtText(self._label)
        txt.setColor(label_color)
        txt.setFont(self._font)
        txt.setBorderPen(lab_pen)
        txt.setBackgroundBrush(lab_brush)
        self.plotmarker.setLabel(txt)
        self.plotmarker.setLabelAlignment(Qt.AlignBottom | Qt.AlignRight)

    def checkSelected(self):
        """Checks the src.selected attribute, resets marker if it has changed.
    Returns True is something has changed."""
        sel = getattr(self.src, 'selected', False)
        if self._selected == sel:
            return False
        self._selected = sel
        self.resetStyle()
        return True

    def changeStyle(self, group):
        if group.func(self.src):
            self.resetStyle()
            return True
        return False


class ImageSourceMarker(SourceMarker):
    """This auguments SourceMarker with a FITS image."""

    def __init__(self, src, l, m, size, model, imgman):
        # load image if needed
        self.imgman = imgman
        dprint(2, "loading Image source", src.shape.filename)
        self.imagecon = imgman.loadImage(src.shape.filename, duplicate=False, to_top=False, model=src.name)
        # this will return None if the image fails to load, in which case we still produce a marker,
        # but nothing else
        if self.imagecon:
            self.imagecon.setMarkersZ(Z_Source)
        # init base class
        SourceMarker.__init__(self, src, l, m, size, model)

    def attach(self, plot):
        SourceMarker.attach(self, plot)
        if self.imagecon:
            self.imagecon.attachToPlot(plot)

    def _setupMarker(self, style, label):
        SourceMarker._setupMarker(self, style, label)
        if not style:
            return
        symbol_color = QColor(style.symbol_color)
        label_color = QColor(style.label_color)
        if self.imagecon:
            self.imagecon.setPlotBorderStyle(border_color=symbol_color, label_color=label_color)


def makeSourceMarker(src, l, m, size, model, imgman):
    """Creates source marker based on source type"""
    shape = getattr(src, 'shape', None)
    #  print type(shape),isinstance(shape,ModelClasses.FITSImage),shape.__class__,ModelClasses.FITSImage
    if isinstance(shape, ModelClasses.FITSImage):
        return ImageSourceMarker(src, l, m, size, model, imgman)
    else:
        return SourceMarker(src, l, m, size, model)


def makeDualColorPen(color1, color2, width=3):
    c1, c2 = QColor(color1).rgb(), QColor(color2).rgb()
    texture = QImage(2, 2, QImage.Format_RGB32)
    texture.setPixel(0, 0, c1)
    texture.setPixel(1, 1, c1)
    texture.setPixel(0, 1, c2)
    texture.setPixel(1, 0, c2)
    return QPen(QBrush(texture), width)
