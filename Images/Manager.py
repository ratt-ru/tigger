from PyQt4.Qt import *
import math
import numpy
import pyfits
import re
import os.path
import time
import traceback
import sys

import Kittens.utils
from Kittens.utils import curry,PersistentCurrier
from Kittens.widgets import BusyIndicator

from Controller import ImageController,dprint,dprintf

import SkyImage
from Tigger.Images import  FITS_ExtensionList

class ImageManager (QWidget):
  """An ImageManager manages a stack of images (and associated ImageControllers)"""
  def __init__ (self,*args):
    QWidget.__init__(self,*args);
    # init layout
    self._lo = QVBoxLayout(self);
    self._lo.setContentsMargins(0,0,0,0);
    self._lo.setSpacing(0);
    # init internal state
    self._currier = PersistentCurrier();
    self._z0 = 0;  # z-depth of first image, the rest count down from it
    self._updating_imap = False;
    self._locked_display_range = False;
    self._imagecons = [];
    self._imagecon_loadorder = [];
    self._center_image = None;
    self._plot = None;
    self._border_pen = None;
    self._drawing_key = None;
    self._load_image_dialog = None;
    self._model_imagecons = set();
    # init menu and standard actions
    self._menu = QMenu("&Image",self);
    qag = QActionGroup(self);
    # exclusive controls for plotting topmost or all images
    self._qa_plot_top = qag.addAction("Display topmost image only");
    self._qa_plot_all   = qag.addAction("Display all images");
    self._qa_plot_top.setCheckable(True);
    self._qa_plot_all.setCheckable(True);
    self._qa_plot_top.setChecked(True);
    QObject.connect(self._qa_plot_all,SIGNAL("toggled(bool)"),self._displayAllImages);

    # repopulate the menu
    self._repopulateMenu();

  def close (self):
    for ic in self._imagecons:
      ic.close();

  def loadImage (self,filename=None,duplicate=True,model=None):
    """Loads image. Returns ImageControlBar object.
    If image is already loaded: returns old ICB if duplicate=False, or else makes a new control bar.
    If model is set to a source name, marks the image as associated with a model source. These can be unloaded en masse by calling
    unloadModelImages().
    """;
    if filename is None:
        if not self._load_image_dialog:
            dialog = self._load_image_dialog = QFileDialog(self,"Load FITS image",".","FITS images (%s);;All files (*)"%(" ".join(["*"+ext for ext in FITS_ExtensionList])));
            dialog.setFileMode(QFileDialog.ExistingFile);
            dialog.setModal(True);
            QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self.loadImage);
        self._load_image_dialog.exec_();
        return None;
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = str(filename);
    # report error if image does not exist
    if not os.path.exists(filename):
      self.showErrorMessage("""FITS image %s does not exist."""%filename);
      return None;
    # see if image is already loaded
    if not duplicate:
      for ic in self._imagecons:
        if os.path.samefile(filename,ic.getFilename()):
          self.raiseImage(ic);
          if model:
            self._model_imagecons.add(id(ic));
          return ic;
    # load the FITS image
    busy = BusyIndicator();
    dprint(2,"reading FITS image",filename);
    self.showMessage("""Reading FITS image %s"""%filename,3000);
    QApplication.flush();
    try:
      image = SkyImage.FITSImagePlotItem(str(filename));
    except:
        busy = None;
        traceback.print_exc();
        self.showErrorMessage("""Error loading FITS image %s: %s"""%(filename,str(sys.exc_info()[1])));
        return None;
    # create control bar, add to widget stack
    ic = self._createImageController(image,"model source '%s'"%model if model else filename,model or image.name,model=model);
    self.showMessage("""Loaded FITS image %s"""%filename,3000);
    dprint(2,"image loaded");
    return ic;

  def showMessage (self,message,time=None):
    self.emit(SIGNAL("showMessage"),message,time);

  def showErrorMessage (self,message,time=None):
    self.emit(SIGNAL("showErrorMessage"),message,time);

  def setZ0 (self,z0):
    self._z0 = z0;
    if self._imagecons:
      self.raiseImage(self._imagecons[0]);

  def enableImageBorders (self,border_pen,label_color,label_bg_brush):
    self._border_pen,self._label_color,self._label_bg_brush = \
      border_pen,label_color,label_bg_brush;

  def lockDisplayRange (self,rc,lock):
    """Locks or unlocks the display range. If lock=True, propagates the range from RenderControl object rc to all other RenderControls."""
    self._locked_display_range = lock;
    self.emit(SIGNAL("displayRangeLocked"),bool(lock));
    if lock:
      self._locked_display_range = rc.displayRange();
      self._updateDisplayRange(rc,*rc.displayRange());
    else:
      self._locked_display_range = None;

  def isDisplayRangeLocked (self):
    return bool(self._locked_display_range);

  def _updateDisplayRange (self,rc,dmin,dmax):
    """This is called whenever one of the images (or rather, its associated RenderControl object) changes its display range.""";
    # If the display range is locked, propagate it to all images.
    # but don't do it if we're already propagating (otherwise we may get called in an infinte loop)
    if not self._updating_imap:
      self._updating_imap = True;
      try:
        if self.isDisplayRangeLocked():
          self._locked_display_range = dmin,dmax;
          for ic in self._imagecons:
            if ic.renderControl() is not rc:
              ic.renderControl().setDisplayRange(dmin,dmax);
      finally:
        self._updating_imap = False;

  def getImages (self):
    return [ ic.image for ic in self._imagecons ];

  def getTopImage (self):
    return (self._imagecons or None) and self._imagecons[0].image;

  def cycleImages (self):
    index = self._imagecon_loadorder.index(self._imagecons[0]);
    index = (index+1)%len(self._imagecon_loadorder);
    self.raiseImage(self._imagecon_loadorder[index]);

  def blinkImages (self):
    if len(self._imagecons)>1:
      self.raiseImage(self._imagecons[1]);

  def incrementSlice (self,axis,incr):
    self._imagecons[0].incrementSlice(axis,incr);

  def setLMRectSubset (self,rect):
    if self._imagecons:
      self._imagecons[0].renderControl().setLMRectSubset(rect);

  def unloadModelImages (self):
    """Unloads images associated with model (i.e. loaded with the model=True flag)""";
    for ic in [ ic for ic in self._imagecons if id(ic) in self._model_imagecons ]:
      self.unloadImage(ic);

  def unloadImage (self,imagecon):
    """Unloads the given imagecon object.""";
    if imagecon not in self._imagecons:
      return;
    # recenter if needed
    self._imagecons.remove(imagecon);
    self._imagecon_loadorder.remove(imagecon);
    self._model_imagecons.discard(id(imagecon));
    # reparent widget and release it
    imagecon.setParent(None);
    imagecon.close();
    # recenter image, if unloaded the center image
    if self._center_image is imagecon.image:
      self.centerImage(self._imagecons[0] if self._imagecons else None,emit=False);
    # emit signal
    self._repopulateMenu();
    self.emit(SIGNAL("imagesChanged"));
    if self._imagecons:
      self.raiseImage(self._imagecons[0]);

  def getCenterImage (self):
    return self._center_image;

  def centerImage (self,imagecon,emit=True):
    self._center_image = imagecon and imagecon.image;
    for ic in self._imagecons:
      ic.setPlotProjection(self._center_image.projection);
    if emit:
      self.emit(SIGNAL("imagesChanged"));

  def raiseImage (self,imagecon):
    # reshuffle image stack, if more than one image image
    if len(self._imagecons) > 1:
      busy = BusyIndicator();
      # reshuffle image stack
      self._imagecons.remove(imagecon);
      self._imagecons.insert(0,imagecon);
      # notify imagecons
      for i,ic in enumerate(self._imagecons):
        label = "%d"%(i+1) if i else "<B>1</B>";
        ic.setZ(self._z0-i*10,top=not i,depthlabel=label,can_raise=True);
      # adjust visibility
      for j,ic in enumerate(self._imagecons):
        ic.setImageVisible(not j or bool(self._qa_plot_all.isChecked()));
      # issue replot signal
      self.fastReplot();
    # else simply update labels
    else:
      self._imagecons[0].setZ(self._z0,top=True,depthlabel=None,can_raise=False);
      self._imagecons[0].setImageVisible(True);
    # update slice menus
    img = imagecon.image;
    axes = imagecon.renderControl().slicedAxes();
    for i,(next,prev) in enumerate(self._qa_slices):
      next.setVisible(False);
      prev.setVisible(False);
      if i < len(axes):
        iaxis,name,labels = axes[i];
        next.setVisible(True);
        prev.setVisible(True);
        next.setText("Show next slice along %s axis"%name);
        prev.setText("Show previous slice along %s axis"%name);
    # emit signasl
    self.emit(SIGNAL("imageRaised"),img);

  def resetDrawKey (self):
    """Makes and sets the current plot's drawing key"""
    if self._plot:
      key = [];
      for ic in self._imagecons:
        key.append(id(ic));
        key += ic.currentSlice();
        self._plot.setDrawingKey(tuple(key));

  def fastReplot (self,*dum):
    """Fast replot -- called when flipping images or slices. Uses the plot cache, if possible.""";
    if self._plot:
      self.resetDrawKey();
      dprint(2,"calling replot",time.time()%60);
      self._plot.replot();
      dprint(2,"replot done",time.time()%60);

  def replot (self,*dum):
    """Proper replot -- called when an image needs to be properly redrawn. Cleares the plot's drawing cache.""";
    if self._plot:
      self._plot.clearDrawCache();
      self.resetDrawKey();
      self._plot.replot();

  def attachImagesToPlot (self,plot):
    self._plot = plot;
    self.resetDrawKey();
    for ic in self._imagecons:
      ic.attachToPlot(plot);

  def getMenu (self):
    return self._menu;

  def _displayAllImages (self,enabled):
    busy = BusyIndicator();
    if enabled:
      for ic in self._imagecons:
        ic.setImageVisible(True);
    else:
      self._imagecons[0].setImageVisible(True);
      for ic in self._imagecons[1:]:
        ic.setImageVisible(False);
    self.replot();

  def _repopulateMenu (self):
    self._menu.clear();
    self._menu.addAction("&Load image...",self.loadImage,Qt.CTRL+Qt.Key_L);
    self._menu.addAction("Comp&ute image...",self.computeImage,Qt.CTRL+Qt.Key_U);
    if self._imagecons:
      self._menu.addSeparator();
      # add controls to cycle images and planes
      for i,imgcon in enumerate(self._imagecons[::-1]):
        imgcon.setNumber(i);
        self._menu.addMenu(imgcon.getMenu());
      self._menu.addSeparator();
      if len(self._imagecons) > 1:
        self._menu.addAction("Cycle images",self.cycleImages,Qt.Key_F5);
        self._menu.addAction("Blink images",self.blinkImages,Qt.Key_F6);
      self._qa_slices = ((  self._menu.addAction("Next slice along axis 1",self._currier.curry(self.incrementSlice,0,1),Qt.Key_F7),
                                            self._menu.addAction("Previous slice along axis 1",self._currier.curry(self.incrementSlice,0,-1),Qt.SHIFT+Qt.Key_F7)),
                                        (  self._menu.addAction("Next slice along axis 2",self._currier.curry(self.incrementSlice,1,1),Qt.Key_F8),
                                            self._menu.addAction("Previous slice along axis 2",self._currier.curry(self.incrementSlice,1,-1),Qt.SHIFT+Qt.Key_F8)));
      self._menu.addSeparator();
      self._menu.addAction(self._qa_plot_top);
      self._menu.addAction(self._qa_plot_all);

  def computeImage (self,expression=None):
    """Computes image from expression (if expression is None, pops up dialog)""";
    if expression is None:
      (expression,ok) = QInputDialog.getText(self,"Compute image","Enter expression to compute");
      expression = str(expression);
      if not ok or not expression:
        return;
    # try to parse expression
    arglist = [ (chr(ord('a')+i),ic.image) for i,ic in enumerate(self._imagecons[::-1]) ];
    try:
      exprfunc = eval("lambda "+(",".join([ x[0] for x in arglist ]))+":"+expression);
    except Exception,exc:
      self.showErrorMessage("""Error parsing expression "%s": %s."""%(expression,str(exc)));
      return None;
    # try to evaluate expression
    self.showMessage("Computing expression \"%s\""%expression,10000);
    busy = BusyIndicator();
    QApplication.flush();
    try:
      result = exprfunc(*[x[1].image() for x in arglist]);
    except Exception,exc:
      busy = None;
      traceback.print_exc();
      self.showErrorMessage("""Error evaluating "%s": %s."""%(expression,str(exc)));
      return None;
    busy = None;
    if type(result) != numpy.ndarray:
      self.showErrorMessage("""Result of "%s" is of invalid type "%s" (array expected)."""%(expression,type(result).__name__));
      return None;
    # determine which image this expression can be associated with
    arglist = [ x for x in arglist if hasattr(x[1],'fits_header') and x[1].image().shape == result.shape ];
    if not arglist:
      self.showErrorMessage("""Result of "%s" has shape %s, which does not match any loaded FITS image."""%(expression,"x".join(map(str,result.shape))));
      return None;
    # if all images in arglist have the same projection, then it doesn't matter what we use
    # else ask
    template = arglist[0][1];
    if len([x for x in arglist[1:] if x[1].projection == template.projection ]) != len(arglist)-1:
      options = [ x[0] for x in arglist ];
      (which,ok) = QInputDialog.getItem(self,"Compute image","Coordinate system to use for the result of \"%s\":"%expression,options,0,False);
      if not ok:
        return None;
      print options.index(which);
    # create a FITS image
    busy = BusyIndicator();
    dprint(2,"creating FITS image",expression);
    self.showMessage("""Creating image for %s"""%expression,3000);
    QApplication.flush();
    hdu = pyfits.PrimaryHDU(result.transpose(),template.fits_header);
    try:
      skyimage = SkyImage.FITSImagePlotItem(expression,expression,hdu=hdu);
    except:
      busy = None;
      traceback.print_exc();
      self.showErrorMessage("""Error loading FITS image %s: %s"""%(expression,str(sys.exc_info()[1])));
      return None;
    # create control bar, add to widget stack
    dirname = getattr(template,'filename',None);
    self._createImageController(skyimage,expression,expression,save=(dirname and (os.path.dirname(dirname) or ".")));
    self.showMessage("Created new image for %s"%expression,3000);
    dprint(2,"image created");

  def _createImageController (self,image,name,basename,model=False,save=False):
    dprint(2,"creating ImageController for",name);
    ic = ImageController(image,self,self,name,save=save);
    self._imagecons.insert(0,ic);
    self._imagecon_loadorder.append(ic);
    if model:
      self._model_imagecons.add(id(ic));
    self._lo.addWidget(ic);
    if self._border_pen:
      ic.addPlotBorder(self._border_pen,basename,self._label_color,self._label_bg_brush);
    # attach appropriate signals
    image.connect(SIGNAL("slice"),self.fastReplot);
    image.connect(SIGNAL("repaint"),self.replot);
    image.connect(SIGNAL("raise"),self._currier.curry(self.raiseImage,ic));
    image.connect(SIGNAL("unload"),self._currier.curry(self.unloadImage,ic));
    image.connect(SIGNAL("center"),self._currier.curry(self.centerImage,ic));
    if self._locked_display_range:
      ic.renderControl().setDisplayRange(*self._locked_display_range);
    QObject.connect(ic.renderControl(),SIGNAL("displayRangeChanged"),self._currier.curry(self._updateDisplayRange,ic.renderControl()));
    self._plot = None;
    # add to menus
    dprint(2,"repopulating menus");
    self._repopulateMenu();
    # center and raise to top of stack
    self.raiseImage(ic);
    self.centerImage(ic,emit=False);
    # signal
    self.emit(SIGNAL("imagesChanged"));
    return ic;

