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
import sys
import time
import os.path
from scipy.ndimage import measurements

import Kittens.utils
from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

_verbosity = Kittens.utils.verbosity(name="rc");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

from Tigger.Images import SkyImage,Colormaps
from Tigger import pixmaps,ConfigFile
from Tigger.Widgets import FloatValidator

import Kittens.config
ImageConfigFile = Kittens.config.DualConfigParser("tigger.images.conf");

class RenderControl (QObject):
  """RenderControl represents all the options (slices, color and intensity policy data) associated with an image. This object is shared by various GUI elements
  that control the rendering of images.
  """;
  
  SUBSET_FULL = "full";
  SUBSET_SLICE = "slice";
  SUBSET_RECT = "rect";

  def __init__ (self,image,parent):
    QObject.__init__(self,parent);
    self.image = image;
    self._config = Kittens.config.SectionParser(ImageConfigFile,os.path.normpath(os.path.abspath(image.filename))) if image.filename else None;
    # figure out the slicing -- find extra axes with size > 1
    # self._current_slice contains all extra axis, including the size-1 ones
    # self._sliced_axes is a list of (iextra,axisname,labels) tuples for size>1 axes
    # where iextra is an index into self._current_slice.
    self._current_slice = [0]*image.numExtraAxes();
    self._slice_dims    = [1]*image.numExtraAxes();
    self._sliced_axes   = [];
    for i in range(image.numExtraAxes()):
      iaxis,axisname,labels = image.extraAxisNumberNameLabels(i);
      self._slice_dims[i] = len(labels);
      if len(labels) > 1:
        self._sliced_axes.append((i,axisname,labels));
    # set the full image range (i.e. mix/max) and current slice range
    dprint(2,"getting data min/max");
    self._fullrange = self._slicerange = image.dataMinMax()[:2];
    dprint(2,"done");
    # create dict of intensity maps
    log_cycles = self._config.getfloat("intensity-log-cycles",6) if self._config else 6;
    self._imap_list = (
      ( 'Linear',   Colormaps.LinearIntensityMap()    ),
      ( 'Histogram-equalized',  Colormaps.HistEqIntensityMap()   ),
      ( 'log(val-min)', Colormaps.LogIntensityMap(log_cycles) )
    );
    # create list of color maps
    self._cmap_list = Colormaps.getColormapList();
    default_cmap = 0;
    for i,cmap in enumerate(self._cmap_list):
      if isinstance(cmap,Colormaps.ColormapWithControls):
        if self._config:
          cmap.loadConfig(self._config);
        QObject.connect(cmap,SIGNAL("colormapChanged"),self.updateColorMapParameters);
      if isinstance(cmap,Colormaps.CubeHelixColormap):
        default_cmap = i;
    # set the initial intensity map
    imap = self._config.getint("intensity-map-number",0) if self._config else 0;
    cmap = self._config.getint("colour-map-number",default_cmap) if self._config else default_cmap;
    imap = max(min(len(self._imap_list)-1,imap),0);
    cmap = max(min(len(self._cmap_list)-1,cmap),0);
    self._current_imap_index = imap;
    self._current_cmap_index = cmap;
    self.image.setIntensityMap(self._imap_list[imap][1]);
    self.image.setColorMap(self._cmap_list[cmap]);

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
    if self._config and self._config.has_option("range-min") and self._config.has_option("range-max"):
      display_range = self._config.getfloat("range-min"),self._config.getfloat("range-max");
    else:
      display_range = None;
    self.setFullSubset(display_range,write_config=False);
    # setup initial slice
    if self.hasSlicing():
      if self._config and self._config.has_option("slice"):
        try:
          curslice = map(int,self._config.get("slice").split());
        except:
          curslice = [];
        if len(curslice) == len(self._current_slice):
          for iaxis,i in enumerate(curslice):
            naxis = len(self.image.extraAxisValues(iaxis));
            i = min(naxis-1,max(0,i));
            self._current_slice[iaxis] = i;
      self.selectSlice(self._current_slice,write_config=False);
    # lock display range if so configured
    self._lock_display_range = self._config.getbool("lock-range",0) if self._config else False;
    if self._lock_display_range:
      self.lockDisplayRange(True,write_config=False);


  def startSavingConfig(self,image_filename):
    """Saves the current configuration under the specified image filename""";
    self._config = Kittens.config.SectionParser(ImageConfigFile,os.path.normpath(os.path.abspath(image_filename)));
    if self._displayrange:
      self._config.set("range-min",self._displayrange[0],save=False);
      self._config.set("range-max",self._displayrange[1],save=False);
    if self._current_slice:
      self._config.set("slice"," ".join(map(str,self._current_slice)),save=False);
    for cmap in self._cmap_list:
      if isinstance(cmap,Colormaps.ColormapWithControls):
        cmap.saveConfig(self._config,save=False);
    self._config.set("intensity-map-number",self._current_imap_index,save=False);
    self._config.set("colour-map-number",self._current_cmap_index,save=False);
    self._config.set("lock-range",self._lock_display_range,save=True);
    

  def hasSlicing (self):
    """Returns True if image is a cube, and so has non-trivial slicing axes""";
    return bool(self._sliced_axes);

  def slicedAxes (self):
    """Returns list of (axis_num,name,label_list) tuples per each non-trivial slicing axis""";
    return self._sliced_axes;

  def incrementSlice (self,iaxis,incr,write_config=True):
    dprint(2,"incrementing slice axis",iaxis,"by",incr);
    self._current_slice[iaxis] = (self._current_slice[iaxis] + incr)%self._slice_dims[iaxis];
    self._updateSlice(write_config);
      
  def changeSlice (self,iaxis,index,write_config=True):
    dprint(2,"changing slice axis",iaxis,"to",index);
    if self._current_slice[iaxis] != index:
      self._current_slice[iaxis] = index;
      self._updateSlice(write_config);

  def selectSlice (self,indices,write_config=True):
    """Selects slice given by indices""";
    dprint(2,"selecting slice",indices);
    self._current_slice = list(indices);
    self._updateSlice(write_config);

  def _updateSlice (self,write_config=True):
    """Common internal method called to finalize changes to _current_slice""";
    busy = BusyIndicator();
    dprint(2,"_updateSlice",self._current_slice,time.time()%60);
    indices = tuple(self._current_slice);
    self.image.selectSlice(*indices);
    dprint(2,"image slice selected",time.time()%60);
    img = self.image.image();
    self._slicerange = self._sliceranges.get(indices);
    if self._slicerange is None:
      self._slicerange = self._sliceranges[indices] = self.image.imageMinMax()[:2];
    dprint(2,"min/max updated",time.time()%60);
    self.setSliceSubset(set_display_range=False);
    if write_config and self._config:
      self._config.set("slice"," ".join(map(str,indices)));

  def displayRange (self):
    return self._displayrange;

  def currentSlice (self):
    return self._current_slice;
    
  def sliceDimensions (self):
    return self._slice_dims;

  def getIntensityMapNames (self):
    return [ name for name,imap in self._imap_list ];

  def currentIntensityMapNumber (self):
    return self._current_imap_index;

  def currentIntensityMap (self):
    return self.image.intensityMap();

  def setIntensityMapNumber (self,index,write_config=True):
    busy = BusyIndicator();
    self._current_imap_index = index;
    imap = self._imap_list[index][1];
    imap.setDataSubset(self._displaydata,self._displaydata_minmax);
    imap.setDataRange(*self._displayrange);
    self.image.setIntensityMap(imap);
    self.emit(SIGNAL("intensityMapChanged"),imap,index);
    if self._config and write_config:
      self._config.set("intensity-map-number",index);

  def setIntensityMapLogCycles (self,cycles,notify_image=True,write_config=True):
    busy = BusyIndicator();
    imap = self.currentIntensityMap();
    if isinstance(imap,Colormaps.LogIntensityMap):
      imap.log_cycles = cycles;
      if notify_image:
        self.image.setIntensityMap();
      self.emit(SIGNAL("intensityMapChanged"),imap,self._current_imap_index);
    if self._config and write_config:
      self._config.set("intensity-log-cycles",cycles);

  def lockDisplayRangeForAxis (self,iaxis,lock):
    pass;
    
  def getColormapList (self):
    return self._cmap_list;
    
  def updateColorMapParameters (self):
    """Call this when the colormap parameters have changed""";
    busy = BusyIndicator();
    self.image.updateCurrentColorMap();
    if self._config:
      self._cmap_list[self._current_cmap_index].saveConfig(self._config);

  def setColorMapNumber (self,index,write_config=True):
    busy = BusyIndicator();
    self._current_cmap_index = index;
    cmap = self._cmap_list[index];
    self.image.setColorMap(cmap);
    self.emit(SIGNAL("colorMapChanged"),cmap);
    if self._config and write_config:
      self._config.set("colour-map-number",index);

  def currentSubset (self):
    """Returns tuple of subset,(dmin,dmax),description for current data subset""";
    return self._displaydata,self._displaydata_minmax,self._displaydata_desc,self._displaydata_type;

  def _resetDisplaySubset (self,subset,desc,range=None,set_display_range=True,write_config=True,subset_type=None):
    dprint(4,"setting display subset");
    self._displaydata = subset;
    self._displaydata_desc = desc;
    self._displaydata_minmax = range = range or measurements.extrema(subset)[:2];
    self._displaydata_type = subset_type;
    dprint(4,"range set");
    self.image.intensityMap().setDataSubset(self._displaydata,minmax=range);
    self.image.setIntensityMap(emit=False);
    self.emit(SIGNAL("dataSubsetChanged"),subset,range,desc,subset_type);
    if set_display_range:
      self.setDisplayRange(write_config=write_config,*range);

  def setFullSubset (self,display_range=None,write_config=True):
    shapedesc = u"\u00D7".join(["%d"%x for x in list(self.image.imageDims()) + [len(labels) for iaxis,name,labels in self._sliced_axes]]);
    desc = "full cube" if self._sliced_axes else "full image";
    self._resetDisplaySubset(self.image.data(),desc,range=self._fullrange,subset_type=self.SUBSET_FULL,
        write_config=write_config,set_display_range=False);
    self.setDisplayRange(write_config=write_config,*(display_range or self._fullrange))

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

  def setSliceSubset (self,set_display_range=True,write_config=True):\
    return self._resetDisplaySubset(self.image.image(),self._makeSliceDesc(),self._slicerange,
        subset_type=self.SUBSET_SLICE,
        set_display_range=set_display_range,write_config=write_config);

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
    return self._resetDisplaySubset(self.image.image()[xx1:xx2,yy1:yy2]," ".join(descs),subset_type=self.SUBSET_RECT);
    
  def _lmRectToPix (self,rect):
    """helper function -- converts an LM rectangle to pixel coordinates""";
    if rect.width() and rect.height():
      # convert to pixel coordinates
      x1,y1,x2,y2 = rect.getCoords();
      x1,y1 = self.image.lmToPix(x1,y1);
      x2,y2 = self.image.lmToPix(x2,y2);
      dprint(2,x1,y1,x2,y2);
      xx1,xx2 = int(math.floor(min(x1,x2))),int(math.ceil(max(x1,x2)));
      yy1,yy2 = int(math.floor(min(y1,y2))),int(math.ceil(max(y1,y2)));
      dprint(2,xx1,yy1,xx2,yy2);
      # ensure limits
      nx,ny = self.image.imageDims();
      xx1,xx2 = max(xx1,0),min(xx2,nx);
      yy1,yy2 = max(yy1,0),min(yy2,ny);
      dprint(2,xx1,yy1,xx2,yy2);
      # check that we actually selected some valid pixels
      if xx1 < xx2 and yy1 < yy2:
        return xx1,xx2,yy1,yy2;
    return None,None,None,None;

  def setLMRectSubset (self,rect):
    xx1,xx2,yy1,yy2 = self._lmRectToPix(rect);
    if xx1 is not None:
      return self._setRectangularSubset(xx1,xx2,yy1,yy2);
      
  def getLMRectStats (self,rect):
    xx1,xx2,yy1,yy2 = self._lmRectToPix(rect);
    if xx1 is not None:
      subset = self.image.image()[xx1:xx2,yy1:yy2];
      subset,mask = self.image.optimalRavel(subset);
      mmin,mmax = measurements.extrema(subset,labels=mask,index=None if mask is None else False)[:2];
      mean = measurements.mean(subset,labels=mask,index=None if mask is None else False);
      std = measurements.standard_deviation(subset,labels=mask,index=None if mask is None else False);
      ssum = measurements.sum(subset,labels=mask,index=None if mask is None else False);
      return xx1,xx2,yy1,yy2,mmin,mmax,mean,std,ssum,subset.size;
    return None;

  def setWindowSubset (self,rect=None):
    rect = rect or self.image.currentRectPix();
    if rect.width() and rect.height():
      tl = rect.topLeft();
      return self._setRectangularSubset(tl.x(),tl.x()+rect.width(),tl.y(),tl.y()+rect.height());

  def resetSubsetDisplayRange (self):
    self.setDisplayRange(*self._displaydata_minmax);

  def isSubsetDisplayRange (self):
    return self._displayrange == self._displaydata_minmax;

  def setDisplayRange (self,dmin,dmax,notify_image=True,write_config=True):
    if dmax < dmin:
      dmin,dmax = dmax,dmin;
    if (dmin,dmax) != self._displayrange:
      self._displayrange = dmin,dmax;
      self.image.intensityMap().setDataRange(dmin,dmax);
      if notify_image:
        busy = BusyIndicator();
        self.image.setIntensityMap(emit=True);
      self.emit(SIGNAL("displayRangeChanged"),dmin,dmax);
      if self._config and write_config:
        self._config.set("range-min",dmin,save=False);
        self._config.set("range-max",dmax);

  def isDisplayRangeLocked (self):
    return self._lock_display_range;

  def lockDisplayRange (self,lock=True,write_config=True):
    self._lock_display_range = lock;
    self.emit(SIGNAL("displayRangeLocked"),lock);
    if self._config and write_config:
      self._config.set("lock-range",bool(lock));

