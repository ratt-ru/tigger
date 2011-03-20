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

_verbosity = Kittens.utils.verbosity(name="rc");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Images import SkyImage,Colormaps
from Tigger import pixmaps
from Tigger.Widgets import FloatValidator


class RenderControl (QObject):
  """RenderControl represents all the options (slices, color and intensity policy data) associated with an image. This object is shared by various GUI elements
  that control the rendering of images.
  """;

  def __init__ (self,image,parent):
    QObject.__init__(self,parent);
    self.image = image;

    # figure out the slicing -- find extra axes with size > 1
    # self._current_slice contains all extra axis, including the size-1 ones
    # self._sliced_axes is a list of (iextra,axisname,labels) tuples for size>1 axes
    # where iextra is an index into self._current_slice.
    self._current_slice = [0]*image.numExtraAxes();
    self._sliced_axes = [];
    for i in range(image.numExtraAxes()):
      iaxis,axisname,labels = image.extraAxisNumberNameLabels(i);
      if len(labels) > 1:
        self._sliced_axes.append((i,axisname,labels));

    # set the full image range (i.e. mix/max) and current slice range
    dprint(2,"getting data min/max");
    self._fullrange = self._slicerange = image.dataMinMax()[:2];
    dprint(2,"done");
    # create dict of intensity maps
    self._imap_list = (
      ( 'Linear',   Colormaps.LinearIntensityMap()    ),
      ( 'Histogram-equalized',  Colormaps.HistEqIntensityMap()   ),
      ( 'log(val-min)', Colormaps.LogIntensityMap() )
    );
    # set the initial intensity map
    self._current_imap_index = 0;
    self.image.setIntensityMap(self._imap_list[0][1]);
    self.image.setColorMap(Colormaps.ColormapOrdering[0]);
    # cache of min/max values for each slice, as these can be slowish to recompute when flipping slices
    self._sliceranges = {};
    # This is the data subset corresponding to the current display range. When the display range is set to
    # _fullrange, this is the image cube. When it is set to _slicerange, this is the current image slice. When
    # setLMRectDisplayRange() or setWindowDisplayRange() is used to set the range to the specified window,
    # this is the a subset of the current slice. The data subset is passed to setDataSubset() of the intensity mapper object
    self._displaydata = None;
    # This is a tuple of the extrema of the current data subset. This is not quite the same thing as self._displayrange below.
    # When the display range is reset to cube/slice/window, _displayrange is set to _displaydata_minmax. But if
    # setDisplayRange() is subsequently called (e.g. if the user manually enters new values into the Range boxes), then
    # _displayrange will be set to something else until the next reset....() call.
    self._displaydata_minmax = None;
    # This is a low,high tuple of the current display range -- will be initialized by resetFullDisplayRange()
    self._displayrange = None;
    self._lock_display_range = False;
    self.setFullSubset();
    # setup initial slice
    if self.hasSlicing():
      self.selectSlice(self._current_slice);

  def hasSlicing (self):
    """Returns True if image is a cube, and so has non-trivial slicing axes""";
    return bool(self._sliced_axes);

  def slicedAxes (self):
    """Returns list of (axis_num,name,label_list) tuples per each non-trivial slicing axis""";
    return self._sliced_axes;

  def selectSlice (self,indices):
    """Selects slice given by indices (must be as many as there are items in self._wslicer)""";
    dprint(2,"selectSlice",time.time()%60);
    indices = tuple(indices);
    busy = BusyIndicator();
    self._current_slice = indices;
    self.image.selectSlice(*indices);
    dprint(2,"image slice selected",time.time()%60);
    img = self.image.image();
    self._slicerange = self._sliceranges.get(indices);
    if self._slicerange is None:
      self._slicerange = self._sliceranges[indices] = self.image.imageMinMax()[:2];
    dprint(2,"min/max updated",time.time()%60);
    self.setSliceSubset(set_display_range=False);

  def displayRange (self):
    return self._displayrange;

  def currentSlice (self):
    return self._current_slice;

  def getIntensityMapNames (self):
    return [ name for name,imap in self._imap_list ];

  def currentIntensityMapNumber (self):
    return self._current_imap_index;

  def currentIntensityMap (self):
    return self.image.intensityMap();

  def setIntensityMapNumber (self,index):
    busy = BusyIndicator();
    self._current_imap_index = index;
    imap = self._imap_list[index][1];
    imap.setDataSubset(self._displaydata,self._displaydata_minmax);
    imap.setDataRange(*self._displayrange);
    self.image.setIntensityMap(imap);
    self.emit(SIGNAL("intensityMapChanged"),imap,index);

  def setIntensityMapLogCycles (self,cycles,notify_image=True):
    busy = BusyIndicator();
    imap = self.currentIntensityMap();
    if isinstance(imap,Colormaps.LogIntensityMap):
      imap.log_cycles = cycles;
      if notify_image:
        self.image.setIntensityMap();
      self.emit(SIGNAL("intensityMapChanged"),imap,self._current_imap_index);

  def lockDisplayRangeForAxis (self,iaxis,lock):
    pass;

  def setColorMap (self,cmap):
    busy = BusyIndicator();
    self.image.setColorMap(cmap);
    self.emit(SIGNAL("colorMapChanged"),cmap);

  def currentSubset (self):
    """Returns tuple of subset,(dmin,dmax),description for current data subset""";
    return self._displaydata,self._displaydata_minmax,self._displaydata_desc;

  def _resetDisplaySubset (self,subset,desc,range=None,set_display_range=True):
    dprint(4,"setting display subset");
    self._displaydata = subset;
    self._displaydata_desc = desc;
    self._displaydata_minmax = range = range or measurements.extrema(subset)[:2];
    dprint(4,"range set");
    self.image.intensityMap().setDataSubset(self._displaydata,minmax=range);
    self.image.setIntensityMap(emit=False);
    self.emit(SIGNAL("dataSubsetChanged"),subset,range,desc);
    if set_display_range:
      self.setDisplayRange(*range);

  def setFullSubset (self):
    shapedesc = u"\u00D7".join(["%d"%x for x in list(self.image.imageDims()) + [len(labels) for iaxis,name,labels in self._sliced_axes]]);
    desc = "full cube" if self._sliced_axes else "full image";
    return self._resetDisplaySubset(self.image.data(),desc,self._fullrange);

  def _makeSliceDesc (self):
    """Makes a description of the current slice""";
    if not self._sliced_axes:
      return "full image";
    descs = [];
    for iextra,name,labels in self._sliced_axes:
      if name.upper() not in ["STOKES","COMPLEX"]:
        descs.append("%s=%s"%(name,labels[self._current_slice[iextra]]));
      else:
        descs.append(labels[self._current_slice[iextra]]);
    return "%s plane"%(" ".join(descs),);

  def setSliceSubset (self,set_display_range=True):
    return self._resetDisplaySubset(self.image.image(),self._makeSliceDesc(),self._slicerange,set_display_range=set_display_range);

  def _setRectangularSubset (self,xx1,xx2,yy1,yy2):
    descs = [];
    nx,ny = self.image.imageDims();
    if xx1 or xx2 != nx:
      descs.append("x=%d:%d"%(xx1,xx2));
    if yy1 or yy2 != ny:
      descs.append("y=%d:%d"%(yy1,yy2));
    if descs:
      descs.append("in");
    descs.append(self._makeSliceDesc());
    return self._resetDisplaySubset(self.image.image()[xx1:xx2,yy1:yy2]," ".join(descs));

  def setLMRectSubset (self,rect):
    if rect.width() and rect.height():
      # convert to pixel coordinates
      x1,y1,x2,y2 = rect.getCoords();
      x1,y1 = self.image.lmToPix(x1,y1);
      x2,y2 = self.image.lmToPix(x2,y2);
      dprint(0,x1,y1,x2,y2);
      xx1,xx2 = int(math.floor(min(x1,x2))),int(math.ceil(max(x1,x2)));
      yy1,yy2 = int(math.floor(min(y1,y2))),int(math.ceil(max(y1,y2)));
      dprint(0,xx1,yy1,xx2,yy2);
      # ensure limits
      nx,ny = self.image.imageDims();
      xx1,xx2 = max(xx1,0),min(xx2,nx);
      yy1,yy2 = max(yy1,0),min(yy2,ny);
      dprint(0,xx1,yy1,xx2,yy2);
      # check that we actually selected some valid pixels
      if xx1 >= xx2 or yy1 >= yy2:
        return;
      return self._setRectangularSubset(xx1,xx2,yy1,yy2);

  def setWindowSubset (self,rect=None):
    rect = rect or self.image.currentRectPix();
    if rect.width() and rect.height():
      tl = rect.topLeft();
      return self._setRectangularSubset(tl.x(),tl.x()+rect.width(),tl.y(),tl.y()+rect.height());

  def resetSubsetDisplayRange (self):
    self.setDisplayRange(*self._displaydata_minmax);

  def setDisplayRange (self,dmin,dmax,notify_image=True):
    if dmax < dmin:
      dmin,dmax = dmax,dmin;
    if (dmin,dmax) != self._displayrange:
      self._displayrange = dmin,dmax;
      self.image.intensityMap().setDataRange(dmin,dmax);
      if notify_image:
        busy = BusyIndicator();
        self.image.setIntensityMap(emit=True);
      self.emit(SIGNAL("displayRangeChanged"),dmin,dmax);

  def isDisplayRangeLocked (self):
    return self._lock_display_range;

  def lockDisplayRange (self,lock=True):
    self._lock_display_range = lock;
    self.emit(SIGNAL("displayRangeLocked"),lock);

