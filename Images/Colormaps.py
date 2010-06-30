from PyQt4.Qt import *
from PyQt4.Qwt5 import *

import math
import  numpy
import numpy.ma
from scipy.ndimage import measurements

import Kittens.utils
import copy

_verbosity = Kittens.utils.verbosity(name="colormap");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

class IntensityMap (object):
  """An IntensityMap maps a float array into a 0...1 range."""
  def __init__ (self,dmin=None,dmax=None):
    """Constructor. An optional data range may be supplied.""";
    self.range = None;
    if dmin is not None:
      if dmax is None:
        raise TypeError,"both dmin and dmax must be specified, or neither.""";
      self.setDataRange(dmin,dmax);

  def copy (self):
    return copy.copy(self);

  def setDataRange (self,dmin,dmax):
    """Sets the data range.""";
    self.range = dmin,dmax;

  def setDataSubset (self,subset,minmax=None):
    """Sets the data subset.""";
    self.subset = subset;
    self.subset_minmax = minmax;

  def getDataSubset (self):
    return self.subset,self.subset_minmax;

  def getDataRange (self,data):
    """Returns the set data range, or uses data min/max if it is not set""";
    # use data min/max if no explicit ranges are set
    return self.range or measurements.extrema(data)[:2];

  def remap (self,data):
    """Remaps data into 0...1 range""";
    raise RuntimeError,"remap() not implemented in "+str(type(self));

class LinearIntensityMap (IntensityMap):
  """This scales data linearly between preset min and max values."""
  def remap (self,data):
    d0,d1 = self.getDataRange(data);
    dd = d1 - d0;
    if dd:
      return ((data-d0)/dd).clip(0,1);
    else:
      return numpy.zeros(data.shape,float);

class LogIntensityMap (IntensityMap):
  """This scales data linearly between preset min and max values."""
  def __init__ (self):
    self.log_cycles = 6;

  def remap (self,data):
    # d0,d1 is current data range
    d0,d1 = self.getDataRange(data);
    if d0 == d1:
      return numpy.zeros(data.shape,float);
    dmax  = d1 - d0;
    data = data - d0;
    dmin = dmax*(10**(-self.log_cycles));
    # clip data to between dmin and dmax, and take log
    data = numpy.ma.log10(data.clip(dmin,dmax));
    # now rescale
    return (data - math.log10(dmin))/(math.log10(dmax) - math.log10(dmin));


class HistEqIntensityMap (IntensityMap):
  def __init__ (self,nbins=256):
    """Creates intensity mapper which uses histogram equalization.""";
    IntensityMap.__init__(self);
    self._nbins = nbins;
    self._cdf = self._bins = self.subset = None;

  def setDataSubset (self,subset,minmax=None):
    IntensityMap.setDataSubset(self,subset,minmax);
    self._bins = None;  # to recompute the CDF

  def setDataRange (self,*range):
    IntensityMap.setDataRange(self,*range);
    self._bins = None;  # to recompute the CDF

  def _computeCDF (self,data):
    """Recomputes the CDF using the current data subset and range""";
    dmin,dmax = self.getDataRange(self.subset if self.subset is not None else data);
    if dmin == dmax:
      self._cdf = None;
    else:
      dprint(1,"computing CDF for range",dmin,dmax);
      # make cumulative histogram, normalize to 0...1
      hist = measurements.histogram(self.subset if self.subset is not None else data,dmin,dmax,self._nbins);
      cdf = numpy.cumsum(hist);
      cdf = cdf/float(cdf[-1]);
      # append 0 at beginning, as left side of bin
      self._cdf = numpy.zeros(len(cdf)+1,float);
      self._cdf[1:] = cdf[...];
      # make array of bin edges
      self._bins = dmin + (dmax-dmin)*numpy.arange(self._nbins+1)/float(self._nbins);

  def remap (self,data):
    if self._bins is None:
      self._computeCDF(data);
    if self._cdf is None:
      return numpy.zeros(data.shape,float);
    values = numpy.interp(data.ravel(),self._bins,self._cdf).reshape(data.shape);
    if hasattr(data,'mask'):
      values = numpy.ma.masked_array(values,data.mask);
    return values;

class Colormap (object):
  """A Colormap provides operations for turning normalized float arrays into QImages. The default implementation is a linear colormap between two colors.
  """;
  def __init__ (self,name,color0=QColor("black"),color1=QColor("white"),alpha=(1,1)):
    self.name = name;
    # color is either specified as one argument (which should then be a [3,n] or [4,n] array),
    # or as two QColors orstring names.
    if isinstance(color0,(list,tuple)):
      self._rgb = numpy.array(color0);
      if self._rgb.shape[1] != 3 or self._rgb.shape[0] < 2:
        raise TypeError,"expected [N,3] (N>=2) array as first argument";
    else:
      if isinstance(color0,str):
        color0 = QColor(color0);
      if isinstance(color1,str):
        color1 = QColor(color1);
      self._rgb = numpy.array([[color0.red(),color0.green(),color0.blue()],
                                             [color1.red(),color1.green(),color1.blue()]])/255.;
    self._rgb_arg = numpy.arange(self._rgb.shape[0])/(self._rgb.shape[0]-1.0)
    # alpha array
    self._alpha = numpy.array(alpha).astype(float);
    self._alpha_arg = numpy.arange(len(alpha))/(len(alpha)-1.0);
    # background brush
    self._brush = None;

  def makeQImage (self,width,height):
    data = numpy.zeros((width,height),float);
    data[...] = (numpy.arange(width)/(width-1.))[:,numpy.newaxis];
    # make brush image -- diag background, with colormap on top
    img = QImage(width,height,QImage.Format_RGB32);
    painter = QPainter(img);
    painter.fillRect(0,0,width,height,QBrush(QColor("white")));
    painter.fillRect(0,0,width,height,QBrush(Qt.BDiagPattern));
    painter.drawImage(0,0,self.colorize(data));
    painter.end();
    return img;

  def makeQPixmap (self,width,height):
    data = numpy.zeros((width,height),float);
    data[...] = (numpy.arange(width)/(width-1.))[:,numpy.newaxis];
    # make brush image -- diag background, with colormap on top
    img = QPixmap(width,height);
    painter = QPainter(img);
    painter.fillRect(0,0,width,height,QBrush(QColor("white")));
    painter.fillRect(0,0,width,height,QBrush(Qt.BDiagPattern));
    painter.drawImage(0,0,self.colorize(data));
    painter.end();
    return img;

  def makeBrush (self,width,height):
    return QBrush(self.makeQImage(width,height));

  def colorize (self,data,alpha=None):
    """Converts normalized data (0...1) array into a QImage of the same dimensions.
    'alpha', if set, is a 0...1 array of the same size, which is mapped to the alpha channel
    (i.e. 0 for fully transparent and 1 for fully opaque).
    If data is a masked array, masked pixels will be fully transparent.""";
    # setup alpha channel
    if alpha is None:
      alpha = numpy.interp(data.ravel(),self._alpha_arg,self._alpha).reshape(data.shape);
    alpha = numpy.round(255*alpha).astype(numpy.int32);
    # make RGB arrays
    rgbs = [ (numpy.interp(data.ravel(),self._rgb_arg,self._rgb[:,i]).reshape(data.shape)*255).round().astype(numpy.int32)
                  for i in range(3) ];
    # add data mask
    mask = getattr(data,'mask',None);
    if mask is not None and mask is not False:
      alpha[mask] = 0;
      for x in rgbs:
        x[mask] = 0;
    # do the deed
    return self.QARGBImage(alpha,*rgbs);

  class QARGBImage (QImage):
    """This is a QImage which is constructed from an A,R,G,B arrays.""";
    def __init__ (self,a,r,g,b):
      nx,ny = r.shape;
      argb = (a<<24) | (r<<16) | (g<<8) | b;
      # transpose array, as it is in column-major (C order), while QImages are in row-major order
      dprint(5,"making qimage of size",nx,ny);
      self._buffer = argb.transpose().tostring();
      QImage.__init__(self,self._buffer,nx,ny,QImage.Format_ARGB32);

# default greyscale colormap
Greyscale = Colormap("Greyscale");

# a pure-orange colormap where intensity maps to alpha
TransparentOrange = Colormap("Transparent Fuchsia",color0="fuchsia",color1="fuchsia",alpha=(0,1));

# some Karma-derived colormaps
from ColormapTables import Karma
_karma_colormaps = [ Colormap(cmap,getattr(Karma,cmap))
    for cmap in [
    "Background",
    "Heat",
    "Isophot",
    "Mousse",
    "Rainbow",
    "RGB",
    "RGB2",
    "Smooth",
    "Staircase",
    "Mirp",
    "Random" ]
];

# list of colormaps in some kind of logical order
ColormapOrdering = [
  Greyscale,
  TransparentOrange ] + _karma_colormaps;

class ColormapMenu (QMenu):
  def __init__ (self,*args):
    QMenu.__init__(self,*args);
    self._currier = Kittens.utils.PersistentCurrier();
    self._qas = {};
    qag = QActionGroup(self);
    for cmap in ColormapOrdering:
      qa = self.addAction(cmap.name,self._currier.curry(self.select,cmap));
      self._qas[id(cmap)] = qa;
      qa.setCheckable(True);
      qag.addAction(qa);

  def select (self,cmap=ColormapOrdering[0]):
    if id(cmap) not in self._qas:
      raise KeyError,"colormap object not in colormap list";
    self._qas[id(cmap)].setChecked(True);
    self.emit(SIGNAL("select"),cmap);

#      pm =QPixmap.fromImage(img);

