"""
biggest chnange is signals stuff:

http://pyqt.sourceforge.net/Docs/PyQt5/pyqt4_differences.html
https://web.archive.org/web/20180106033531/http://pyqt.sourceforge.net/Docs/PyQt5/pyqt4_differences.html

rewriting is quite easy:

QObject.connect(qa,SIGNAL("triggered(bool)"),self._write_config)

becomes

qa.triggered.connect(self._write_config)

It is a bit more work in case of custom signals, those need to be registered with a pyqtSignal. There is also
a decorated available for functions, but then the function name need to be specially formatted.


"""
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget
from qwt import QwtPlot


class QwtEventPattern(QObject):
    def __init__(self, parent=None):
        super().__init__(parent=parent)


class QwtPicker(QwtEventPattern):
    """
    TODO: implement this

    https://skozlovf.github.io/doxygen-qmi-style/qwt/class_qwt_picker.html
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    RectSelection = 1
    DragSelection = 2
    PointSelection = 4
    PolygonSelection = 8

    PolygonRubberBand = None
    RectRubberBand = None
    VLineRubberBand = None

    ActiveOnly = None
    AlwaysOn = None

    selected = pyqtSignal()


class QwtEventPattern:
    """
    TODO: implement this
    """
    MouseSelect1 = 1
    MouseSelect2 = 2
    MouseSelect3 = 4
    MouseSelect4 = 8
    MouseSelect5 = 16
    MouseSelect6 = 32


class QwtPlotPicker(QwtPicker):
    """
    TODO: implement this
    """

    def __init__(self, xBottom=None, yLeft=None, mode=None, rubber_band=None, ActiveOnly=None, canvas=None,
                 parent=None):
        super().__init__(parent=parent)

    def setRubberBandPen(self, pen):
        pass

    def setTrackerMode(self, mode):
        pass

    def setMousePattern(self, sel, x, y):
        pass

    def setEnabled(self, state):
        pass

    def setKeyPattern(self, patt, *kpat):
        pass

    def plot(self):
        return QwtPlot()


class QwtPlotZoomer(QwtPlotPicker):
    """
    TODO: implement this

    http://qwt.sourceforge.net/class_qwt_plot_zoomer.html
    """

    zoomed = pyqtSignal()
    provisionalZoom = pyqtSignal()  # todo: custom oleg signal?

    def __init__(self, canvas, parent=None):
        super().__init__(parent=parent)

    def setMaxStackDepth(self, depth):
        pass

    def setRubberBandPen(self, pen):
        pass

    def setTrackerPen(self, pen):
        pass

    def setSelectionFlags(self, selection):
        pass

    def setMousePattern(self, sel, x, y):
        pass

    def setTrackerMode(self, mode):
        pass

    def setEnabled(self, state):
        pass

    def setKeyPattern(self, patt, *kpat):
        pass

    def zoomRectIndex(self):
        pass

    def setZoomStack(self, stack, index):
        pass

    def zoomStack(self):
        pass

    def maxStackDepth(self):
        pass

    def zoom(self, rect):
        pass

    def setZoomBase(self):
        pass


class QwtSlider(QWidget):
    pass


class QwtWheel(QWidget):
    pass


class QwtScaleEngine:
    pass