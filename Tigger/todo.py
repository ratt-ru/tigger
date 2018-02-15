"""
biggest chnange is signals stuff:

http://pyqt.sourceforge.net/Docs/PyQt5/pyqt4_differences.html

rewriting is quite easy:

QObject.connect(qa,SIGNAL("triggered(bool)"),self._write_config)

becomes

qa.triggered.connect(self._write_config)

It is a bit more work in case of custom signals, those need to be registered with a pyqtSignal. There is also
a decorated available for functions, but then the function name need to be specially formatted.


"""
class QwtPlotZoomer:
    """
    TODO: implement this

    http://qwt.sourceforge.net/class_qwt_plot_zoomer.html
    """

    def __init__(self, canvas):
        pass

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

    def plot(self):
        class Plot:
            def size(self):
                return 0, 0
        return Plot()

    def zoomRectIndex(self):
        pass

    def setZoomStack(self, stack, index):
        pass

    def zoomStack(self):
        pass

    def maxStackDepth(self):
        pass


class QwtPlotPicker:
    """
    TODO: implement this
    """
    def __init__(self, xBottom, yLeft, mode, rubber_band, ActiveOnly, canvas):
        pass

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


class QwtPicker:
    """
    TODO: implement this
    """
    RectSelection = 1
    DragSelection = 2
    PointSelection = 4
    PolygonSelection = 8

    PolygonRubberBand = None
    RectRubberBand = None
    VLineRubberBand = None

    ActiveOnly = None
    AlwaysOn = None


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