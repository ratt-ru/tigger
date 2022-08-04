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

from PyQt5.Qt import QColor, QPen
from PyQt5.QtCore import Qt
from PyQt5.Qwt import QwtPlotCurve, QwtPlotItem

from TigGUI.Widgets import TiggerPlotCurve

from TigGUI.kitties.profiles import MutableTiggerProfile


class PlottableTiggerProfile(MutableTiggerProfile):
    def __init__(self, profilename, axisname, axisunit, xdata, ydata, 
                 qwtplot=None, 
                 profilecoord=None):
        """ 
            Plottable (Mutable) Tigger Profile
            profilename: A name for this profile
            axisname: Name for the axis
            axisunit: Unit for the axis (as taken from FITS CUNIT)
            xdata: profile x axis data (1D ndarray of shape of ydata)
            ydata: profile y axis data (1D ndarray)
            qwtplot: parent plot to which this curve should be added
            profilecoord: coordinate (world) coord tuple to from which this profile is drawn, optional
                          use None to leave unset
        """
        MutableTiggerProfile.__init__(self, profilename, axisname, axisunit, xdata, ydata)
        self._curve_color = QColor("white")
        self._curve_pen = self.createPen()      
        self._curve_pen.setStyle(Qt.DashDotLine)
        self._profcurve = TiggerPlotCurve(profilename)
        self._profcurve.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._ycs = TiggerPlotCurve()
        self._ycs.setRenderHint(QwtPlotItem.RenderAntialiased)
        self._profcurve.setPen(self._curve_pen)
        self._profcurve.setStyle(QwtPlotCurve.Lines)
        self._profcurve.setOrientation(Qt.Horizontal)
        self._parentPlot = qwtplot
        self._profilecoord = None
        self.profileAssociatedCoord = profilecoord

        self._profcurve.setData(xdata, ydata)
        self._profcurve.setVisible(True)
        self._attached = False
        self.attach()

    def createPen(self):
        return QPen(self._curve_color)

    @property
    def hasAssociatedCoord(self):
        return self._profilecoord is not None
    
    @property
    def profileAssociatedCoord(self):
        return (self._profilecoord[0], 
                self._profilecoord[1])
    
    @profileAssociatedCoord.setter
    def profileAssociatedCoord(self, profilecoord):
        if profilecoord is not None:
            if not (isinstance(profilecoord, tuple) and 
                    len(profilecoord) == 2 and
                    all(map(lambda x: isinstance(x, float), profilecoord))):
                raise TypeError("profilecoord should be 2-element world coord tuple")
        self._profilecoord = profilecoord

    def setCurveColor(self, color):
        if not isinstance(color, QColor):
            raise TypeError("Color must be QColor object")
        self._curve_color = color
        self._curve_pen = QPen(self._curve_color)
        self._curve_pen.setStyle(Qt.DashDotLine)
        self._profcurve.setPen(self._curve_pen)
        if self._parentPlot is not None:
            if self._attached:
                self._parentPlot.replot()

    def attach(self):
        self.detach()
        if self._parentPlot is not None:
            self._profcurve.attach(self._parentPlot)
            self._parentPlot.replot()
            self._attached = True
    
    def detach(self):
        if self._attached:
            self._attached = False
            self._profcurve.detach()

    def setAxesData(self, xdata, ydata, shouldSetVisible=True):
        self.__verifyArrs(xdata, ydata)
        self._xdata = xdata.copy()
        self._ydata = ydata.copy()
        if shouldSetVisible:
            self._profcurve.setData(xdata, ydata)
        self._profcurve.setVisible(shouldSetVisible)
        self.attach()