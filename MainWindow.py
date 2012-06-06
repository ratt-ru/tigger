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

from Tigger import *

import os
import os.path
import time
import sys
import fnmatch
import traceback

from PyQt4.Qt import *

import Kittens.utils
from Kittens.utils import PersistentCurrier

from Models import ModelClasses
from Models import SkyModel
from Models.Formats import ModelHTML
import Widgets
import AboutDialog
from SkyModelTreeWidget import *
from Plot.SkyModelPlot import *
from Images.Manager import ImageManager
import Tigger.Tools.source_selector

_verbosity = Kittens.utils.verbosity(name="mainwin");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

class MainWindow (QMainWindow):
  ViewModelColumns = [ "name","RA","Dec","type","Iapp","I","Q","U","V","RM","spi","shape" ];
  def __init__ (self,parent,hide_on_close=False):
    QMainWindow.__init__(self,parent);
    self.setWindowIcon(pixmaps.tigger_starface.icon());
    self._currier = PersistentCurrier();
    self.hide();
    # init column constants
    for icol,col in enumerate(self.ViewModelColumns):
        setattr(self,"Column%s"%col.capitalize(),icol);
    # init GUI
    self.setWindowTitle("Tigger");
    # self.setIcon(pixmaps.purr_logo.pm());
    cw = QWidget(self);
    self.setCentralWidget(cw);
    cwlo = QVBoxLayout(cw);
    cwlo.setMargin(5);
    # make splitter
    spl1 = self._splitter1 = QSplitter(Qt.Vertical,cw);
    spl1.setOpaqueResize(False);
    cwlo.addWidget(spl1);
    # Create listview of LSM entries
    self.tw = SkyModelTreeWidget(spl1);
    self.tw.hide();

    # split bottom pane
    spl2 = self._splitter2 = QSplitter(Qt.Horizontal,spl1);
    spl2.setOpaqueResize(False);
    self._skyplot_stack = QWidget(spl2);
    self._skyplot_stack_lo = QVBoxLayout(self._skyplot_stack);
    self._skyplot_stack_lo.setContentsMargins(0,0,0,0);

    # add plot
    self.skyplot = SkyModelPlotter(self._skyplot_stack,self);
    self.skyplot.resize(128,128);
    self.skyplot.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Preferred);
    self._skyplot_stack_lo.addWidget(self.skyplot,1000);
    self.skyplot.hide();
    QObject.connect(self.skyplot,SIGNAL("imagesChanged"),self._imagesChanged);
    QObject.connect(self.skyplot,SIGNAL("showMessage"),self.showMessage);
    QObject.connect(self.skyplot,SIGNAL("showErrorMessage"),self.showErrorMessage);

    self._grouptab_stack = QWidget(spl2);
    self._grouptab_stack_lo = lo =QVBoxLayout(self._grouptab_stack);
    self._grouptab_stack_lo.setContentsMargins(0,0,0,0);
    # add groupings table
    self.grouptab = ModelGroupsTable(self._grouptab_stack);
    self.grouptab.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);
    QObject.connect(self,SIGNAL("hasSkyModel"),self.grouptab.setEnabled);
    lo.addWidget(self.grouptab,1000);
    lo.addStretch(1);
    self.grouptab.hide();

    # add image controls -- parentless for now (setLayout will reparent them anyway)
    self.imgman = ImageManager();
    self.skyplot.setImageManager(self.imgman);
    QObject.connect(self.imgman,SIGNAL("imagesChanged"),self._imagesChanged);
    QObject.connect(self.imgman,SIGNAL("showMessage"),self.showMessage);
    QObject.connect(self.imgman,SIGNAL("showErrorMessage"),self.showErrorMessage);

    # enable status line
    self.statusBar().show();
    # Create and populate main menu
    menubar = self.menuBar();
    # File menu
    file_menu = menubar.addMenu("&File");
    qa_open = file_menu.addAction("&Open model...",self._openFileCallback,Qt.CTRL+Qt.Key_O);
    qa_merge = file_menu.addAction("&Merge in model...",self._mergeFileCallback,Qt.CTRL+Qt.SHIFT+Qt.Key_O);
    QObject.connect(self,SIGNAL("hasSkyModel"),qa_merge.setEnabled);
    file_menu.addSeparator();
    qa_save = file_menu.addAction("&Save model",self.saveFile,Qt.CTRL+Qt.Key_S);
    QObject.connect(self,SIGNAL("isUpdated"),qa_save.setEnabled);
    qa_save_as = file_menu.addAction("Save model &as...",self.saveFileAs);
    QObject.connect(self,SIGNAL("hasSkyModel"),qa_save_as.setEnabled);
    qa_save_selection_as = file_menu.addAction("Save selection as...",self.saveSelectionAs);
    QObject.connect(self,SIGNAL("hasSelection"),qa_save_selection_as.setEnabled);
    file_menu.addSeparator();
    qa_close = file_menu.addAction("&Close model",self.closeFile,Qt.CTRL+Qt.Key_W);
    QObject.connect(self,SIGNAL("hasSkyModel"),qa_close.setEnabled);
    qa_quit = file_menu.addAction("Quit",self.close,Qt.CTRL+Qt.Key_Q);

    # Image menu
    menubar.addMenu(self.imgman.getMenu());
    # Plot menu
    menubar.addMenu(self.skyplot.getMenu());

    # LSM Menu
    em = QMenu("&LSM",self);
    self._qa_em = menubar.addMenu(em);
    self._qa_em.setVisible(False);
    QObject.connect(self,SIGNAL("hasSkyModel"),self._qa_em.setVisible);
    self._column_view_menu = QMenu("&Show columns",self);
    self._qa_cv_menu = em.addMenu(self._column_view_menu);
    em.addSeparator();
    em.addAction("Select &all",self._selectAll,Qt.CTRL+Qt.Key_A);
    em.addAction("&Invert selection",self._selectInvert,Qt.CTRL+Qt.Key_I);
    em.addAction("Select b&y attribute...",self._showSourceSelector,Qt.CTRL+Qt.Key_Y);
    em.addSeparator();
    qa_add_tag = em.addAction("&Tag selection...",self.addTagToSelection,Qt.CTRL+Qt.Key_T);
    QObject.connect(self,SIGNAL("hasSelection"),qa_add_tag.setEnabled);
    qa_del_tag = em.addAction("&Untag selection...",self.removeTagsFromSelection,Qt.CTRL+Qt.Key_U);
    QObject.connect(self,SIGNAL("hasSelection"),qa_del_tag.setEnabled);
    qa_del_sel = em.addAction("&Delete selection",self._deleteSelection);
    QObject.connect(self,SIGNAL("hasSelection"),qa_del_sel.setEnabled);

   # Tools menu
    tm = self._tools_menu = QMenu("&Tools",self);
    self._qa_tm = menubar.addMenu(tm);
    self._qa_tm.setVisible(False);
    QObject.connect(self,SIGNAL("hasSkyModel"),self._qa_tm.setVisible);

   # Help menu
    menubar.addSeparator();
    hm = self._help_menu = menubar.addMenu("&Help");
    hm.addAction("&About...",self._showAboutDialog);
    self._about_dialog = None;

    # message handlers
    self.qerrmsg = QErrorMessage(self);

    # set initial state
    self.setAcceptDrops(True);
    self.model = None;
    self.filename = None;
    self._display_filename = None;
    self._open_file_dialog = self._merge_file_dialog = self._save_as_dialog = self._save_sel_as_dialog = self._open_image_dialog = None;
    self.emit(SIGNAL("isUpdated"),False);
    self.emit(SIGNAL("hasSkyModel"),False);
    self.emit(SIGNAL("hasSelection"),False);
    self._exiting = False;

    # set initial layout
    self._current_layout = None;
    self.setLayout(self.LayoutEmpty);
    dprint(1,"init complete");

  # layout identifiers
  LayoutEmpty = "empty";
  LayoutImage = "image";
  LayoutImageModel = "model";
  LayoutSplit = "split";

  def _getFilenamesFromDropEvent (self,event):
    """Checks if drop event is valid (i.e. contains a local URL to a FITS file), and returns list of filenames contained therein.""";
    dprint(1,"drop event:",event.mimeData().text());
    if not event.mimeData().hasUrls():
      dprint(1,"drop event: no urls");
      return None;
    filenames = [];
    for url in event.mimeData().urls():
      name = str(url.toLocalFile());
      dprint(2,"drop event: name is",name);
      if name and Images.isFITS(name):
        filenames.append(name);
    dprint(2,"drop event: filenames are",filenames);
    return filenames;

  def dragEnterEvent (self,event):
    if self._getFilenamesFromDropEvent(event):
      dprint(1,"drag-enter accepted");
      event.acceptProposedAction();
    else:
      dprint(1,"drag-enter rejected");

  def dropEvent (self,event):
    filenames = self._getFilenamesFromDropEvent(event);
    dprint(1,"dropping",filenames);
    if filenames:
      event.acceptProposedAction();
      busy = BusyIndicator();
      for name in filenames:
        self.imgman.loadImage(name);

  def saveSizes (self):
    if self._current_layout is not None:
      dprint(1,"saving sizes for layout",self._current_layout);
      # save main window size and splitter dimensions
      sz = self.size();
      Config.set('%s-main-window-width'%self._current_layout,sz.width());
      Config.set('%s-main-window-height'%self._current_layout,sz.height());
      for spl,name in ((self._splitter1,"splitter1"),(self._splitter2,"splitter2")):
        ssz = spl.sizes();
        for i,sz in enumerate(ssz):
          Config.set('%s-%s-size%d'%(self._current_layout,name,i),sz);

  def loadSizes (self):
    if self._current_layout is not None:
      dprint(1,"loading sizes for layout",self._current_layout);
      # get main window size and splitter dimensions
      w = Config.getint('%s-main-window-width'%self._current_layout,0);
      h = Config.getint('%s-main-window-height'%self._current_layout,0);
      dprint(2,"window size is",w,h);
      if not (w and h):
        return None;
      self.resize(QSize(w,h));
      for spl,name in (self._splitter1,"splitter1"),(self._splitter2,"splitter2"):
        ssz = [ Config.getint('%s-%s-size%d'%(self._current_layout,name,i),-1) for i in 0,1 ];
        dprint(2,"splitter",name,"sizes",ssz);
        if all([ sz >=0 for sz in ssz ]):
          spl.setSizes(ssz);
        else:
          return None;
    return True;

  def setLayout (self,layout):
    """Changes the current window layout. Restores sizes etc. from config file.""";
    if self._current_layout is layout:
      return;
    dprint(1,"switching to layout",layout);
    # save sizes to config file
    self.saveSizes();
    # remove imgman widget from all layouts
    for lo in self._skyplot_stack_lo,self._grouptab_stack_lo:
      if lo.indexOf(self.imgman) >= 0:
        lo.removeWidget(self.imgman);
    # assign it to appropriate parent and parent's layout
    if layout is self.LayoutImage or layout is self.LayoutEmpty:
      lo = self._skyplot_stack_lo;
    else:
      lo = self._grouptab_stack_lo;
    self.imgman.setParent(lo.parentWidget());
    lo.addWidget(self.imgman,0);
    # show/hide panels
    if layout is self.LayoutEmpty:
      self.tw.hide();
      self.grouptab.hide();
      self.skyplot.show();
    elif layout is self.LayoutImage:
      self.tw.hide();
      self.grouptab.hide();
      self.skyplot.show();
    elif layout is self.LayoutImageModel:
      self.tw.show();
      self.grouptab.show();
      self.skyplot.show();
    # reload sizes
    self._current_layout = layout;
    if not self.loadSizes():
      dprint(1,"no sizes loaded, setting defaults");
      if layout is self.LayoutEmpty:
        self.resize(QSize(512,256));
      elif layout is self.LayoutImage:
        self.resize(QSize(512,512));
        self._splitter2.setSizes([512,0]);
      elif layout is self.LayoutImageModel:
        self.resize(QSize(1024,512));
        self._splitter1.setSizes([256,256]);
        self._splitter2.setSizes([256,256]);

  def enableUpdates (self,enable=True):
    """Enables updates of the child widgets. Usually called after startup is completed (i.e. all data loaded)""";
    self.skyplot.enableUpdates(enable);
    if enable:
      if self.model:
        self.setLayout(self.LayoutImageModel);
      elif self.imgman.getImages():
        self.setLayout(self.LayoutImage);
      else:
        self.setLayout(self.LayoutEmpty);
      self.show();

  def _showAboutDialog (self):
    if not self._about_dialog:
      self._about_dialog = AboutDialog.AboutDialog(self);
    self._about_dialog.show();

  def addTool (self,name,callback):
    """Adds a tool to the Tools menu""";
    self._tools_menu.addAction(name,self._currier.curry(self._callTool,callback));

  def _callTool (self,callback):
    callback(self,self.model);

  def _imagesChanged (self):
    """Called when the set of loaded images has changed""";
    if self.imgman.getImages():
      if self._current_layout  is self.LayoutEmpty:
       self.setLayout(self.LayoutImage);
    else:
      if not self.model:
       self.setLayout(self.LayoutEmpty);

  def _selectAll (self):
    if not self.model:
      return;
    busy = BusyIndicator();
    for src in self.model.sources:
      src.selected = True;
    self.model.emitSelection(self);

  def _selectInvert (self):
    if not self.model:
      return;
    busy = BusyIndicator();
    for src in self.model.sources:
      src.selected = not src.selected;
    self.model.emitSelection(self);

  def _deleteSelection (self):
    unselected = [ src for src in self.model.sources if not src.selected ];
    nsel = len(self.model.sources) - len(unselected);
    if QMessageBox.question(self,"Delete selection","""<P>Really deleted %d selected source(s)?
        %d unselected sources will remain in the model.</P>"""%(nsel,len(unselected)),
        QMessageBox.Ok|QMessageBox.Cancel,QMessageBox.Cancel) != QMessageBox.Ok:
      return;
    self.model.setSources(unselected);
    self.showMessage("""Deleted %d sources"""%nsel);
    self.model.emitUpdate(SkyModel.UpdateAll,origin=self);

  def _showSourceSelector (self):
    Tigger.Tools.source_selector.show_source_selector(self,self.model);

  def _updateModelSelection (self,num,origin=None):
    """Called when the model selection has been updated.""";
    self.emit(SIGNAL("hasSelection"),bool(num));

  import Tigger.Models.Formats
  _formats = [ f[1] for f in Tigger.Models.Formats.listFormatsFull() ];

  _load_file_types = [ (doc,["*"+ext for ext in extensions],load) for load,save,doc,extensions in _formats if load ];
  _save_file_types = [ (doc,["*"+ext for ext in extensions],save) for load,save,doc,extensions in _formats if save ];

  def showMessage (self,msg,time=3000):
    self.statusBar().showMessage(msg,3000);

  def showErrorMessage (self,msg,time=3000):
    self.qerrmsg.showMessage(msg);

  def loadImage (self,filename):
    return self.imgman.loadImage(filename);

  def setModel (self,model):
    self.emit(SIGNAL("modelChanged"),model);
    if model:
      self.model = model;
      self.emit(SIGNAL("hasSkyModel"),True);
      self.emit(SIGNAL("hasSelection"),False);
      self.emit(SIGNAL("isUpdated"),False);
      self.model.enableSignals();
      self.model.connect("updated",self._indicateModelUpdated);
      self.model.connect("selected",self._updateModelSelection);
      # pass to children
      self.tw.setModel(self.model);
      self.grouptab.setModel(self.model);
      self.skyplot.setModel(self.model);
      # add items to View menu
      self._column_view_menu.clear();
      self.tw.addColumnViewActionsTo(self._column_view_menu);
    else:
      self.model = None;
      self.setWindowTitle("Tigger");
      self.emit(SIGNAL("hasSelection"),False);
      self.emit(SIGNAL("isUpdated"),False);
      self.emit(SIGNAL("hasSkyModel"),False);
      self.tw.clear();
      self.grouptab.clear();
      self.skyplot.setModel(None);

  def _openFileCallback (self):
    if not self._open_file_dialog:
      filters = ";;".join([  "%s (%s)"%(name," ".join(patterns)) for name,patterns,func in self._load_file_types ]);
      dialog = self._open_file_dialog = QFileDialog(self,"Open sky model",".",filters);
      dialog.setFileMode(QFileDialog.ExistingFile);
      dialog.setModal(True);
      QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self.openFile);
    self._open_file_dialog.exec_();
    return;

  def _mergeFileCallback (self):
    if not self._merge_file_dialog:
      filters = ";;".join([  "%s (%s)"%(name," ".join(patterns)) for name,patterns,func in self._load_file_types ]);
      dialog = self._merge_file_dialog = QFileDialog(self,"Merge in sky model",".",filters);
      dialog.setFileMode(QFileDialog.ExistingFile);
      dialog.setModal(True);
      QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),
        self._currier.curry(self.openFile,merge=True));
    self._merge_file_dialog.exec_();
    return;

  def openFile (self,filename=None,format=None,merge=False,show=True):
    from Models import ModelClasses
    # check that we can close existing model
    if not merge and not self._canCloseExistingModel():
      return False;
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = str(filename);
    # try to determine the file type
    filetype,import_func,export_func,doc = Tigger.Models.Formats.resolveFormat(filename,format);
    if import_func is None:
      self.showErrorMessage("""Error loading model file %s: unknown file format"""%filename);
      return;
    # try to load the specified file
    busy = BusyIndicator();
    self.showMessage("""Reading %s file %s"""%(filetype,filename),3000);
    QApplication.flush();
    try:
      model = import_func(filename);
      model.setFilename(filename);
    except:
      busy = None;
      self.showErrorMessage("""Error loading '%s' file %s: %s"""%(filetype,filename,str(sys.exc_info()[1])));
      return;
    # set the layout
    if show:
      self.setLayout(self.LayoutImageModel);
    # add to content
    if merge and self.model:
      self.model.addSources(model.sources);
      self.showMessage("""Merged in %d sources from '%s' file %s"""%(len(model.sources),filetype,filename),3000);
      self.model.emitUpdate(SkyModel.UpdateAll);
    else:
      self.showMessage("""Loaded %d sources from '%s' file %s"""%(len(model.sources),filetype,filename),3000);
      self._display_filename = os.path.basename(filename);
      self.setModel(model);
      self._indicateModelUpdated(updated=False);
      # only set self.filename if an export function is available for this format. Otherwise set it to None, so that trying to save
      # the file results in a save-as operation (so that we don't save to a file in an unsupported format).
      self.filename = filename if export_func else None;

  def closeEvent (self,event):
    dprint(1,"closing");
    self._exiting = True;
    self.saveSizes();
    if not self.closeFile():
      self._exiting = False;
      event.ignore();
      return;
    self.skyplot.close();
    self.imgman.close();
    self.emit(SIGNAL("closing"));
    dprint(1,"invoking os._exit(0)");
    os._exit(0);
    QMainWindow.closeEvent(self,event);

  def _canCloseExistingModel (self):
    # save model if modified
    if self.model and self._model_updated:
      res = QMessageBox.question(self,"Closing sky model","<P>Model has been modified, would you like to save the changes?</P>",
                    QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save);
      if res == QMessageBox.Cancel:
        return False;
      elif res == QMessageBox.Save:
        if not self.saveFile(confirm=False,overwrite=True):
          return False;
    # unload model images, unless we are already exiting anyway
    if not self._exiting:
      self.imgman.unloadModelImages();
    return True;

  def closeFile (self):
    if not self._canCloseExistingModel():
      return False;
    # close model
    self._display_filename = None;
    self.setModel(None);
    # set the layout
    self.setLayout(self.LayoutImage if self.imgman.getTopImage() else self.LayoutEmpty);
    return True;

  def saveFile (self,filename=None,confirm=False,overwrite=True,non_native=False):
    """Saves file using the specified 'filename'. If filename is None, uses current filename, if
    that is not set, goes to saveFileAs() to open dialog and get a filename.
    If overwrite=False, will ask for confirmation before overwriting an existing file.
    If non_native=False, will ask for confirmation before exporting in non-native format.
    If confirm=True, will ask for confirmation regardless.
    Returns True if saving succeeded, False on error (or if cancelled by user).
    """;
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = ( filename and str(filename) ) or self.filename;
    if filename is None:
      return self.saveFileAs();
    else:
      warning = '';
      # try to determine the file type
      filetype,import_func,export_func,doc = Tigger.Models.Formats.resolveFormat(filename,None);
      if export_func is None:
        self.showErrorMessage("""Error saving model file %s: unsupported output format"""%filename);
        return;
      if os.path.exists(filename) and not overwrite:
        warning += "<P>The file already exists and will be overwritten.</P>";
      if filetype != 'Tigger' and not non_native:
        warning += """<P>Please note that you are exporting the model using the external format '%s'.
              Source types, tags and other model features not supported by this
              format will be omitted during the export.</P>"""%filetype;
      # get confirmation
      if confirm or warning:
        dialog = QMessageBox.warning if warning else QMessageBox.question;
        if dialog(self,"Saving sky model","<P>Save model to %s?</P>%s"%(filename,warning),
                  QMessageBox.Save|QMessageBox.Cancel,QMessageBox.Save) != QMessageBox.Save:
          return False;
      busy = BusyIndicator();
      try:
        export_func(self.model,filename);
        self.model.setFilename(filename);
      except:
          busy = None;
          self.showErrorMessage("""Error saving model file %s: %s"""%(filename,str(sys.exc_info()[1])));
          return False;
      self.showMessage("""Saved model to file %s"""%filename,3000);
      self._display_filename = os.path.basename(filename);
      self._indicateModelUpdated(updated=False);
      self.filename = filename;
      return True;

  def saveFileAs (self,filename=None):
    """Saves file using the specified 'filename'. If filename is None, opens dialog to get a filename.
    Returns True if saving succeeded, False on error (or if cancelled by user).
    """;
    if filename is None:
      if not self._save_as_dialog:
          filters = ";;".join([  "%s (%s)"%(name," ".join(patterns)) for name,patterns,func in self._save_file_types ]);
          dialog = self._save_as_dialog = QFileDialog(self,"Save sky model",".",filters);
          dialog.setDefaultSuffix(ModelHTML.DefaultExtension);
          dialog.setFileMode(QFileDialog.AnyFile);
          dialog.setAcceptMode(QFileDialog.AcceptSave);
          dialog.setConfirmOverwrite(False);
          dialog.setModal(True);
          QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self.saveFileAs);
      return self._save_as_dialog.exec_() == QDialog.Accepted;
    # filename supplied, so save
    return self.saveFile(filename,confirm=False);

  def saveSelectionAs (self,filename=None,force=False):
    if not self.model:
      return;
    if filename is None:
      if not self._save_sel_as_dialog:
          filters = ";;".join([  "%s (%s)"%(name," ".join(patterns)) for name,patterns,func in self._save_file_types ]);
          dialog = self._save_sel_as_dialog = QFileDialog(self,"Save sky model",".",filters);
          dialog.setDefaultSuffix(ModelHTML.DefaultExtension);
          dialog.setFileMode(QFileDialog.AnyFile);
          dialog.setAcceptMode(QFileDialog.AcceptSave);
          dialog.setConfirmOverwrite(True);
          dialog.setModal(True);
          QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self.saveSelectionAs);
      return self._save_sel_as_dialog.exec_() == QDialog.Accepted;
    # save selection
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename= str(filename);
    selmodel = self.model.copy();
    sources = [ src for src in self.model.sources if src.selected ];
    if not sources:
      self.showErrorMessage("""You have not selected any sources to save.""");
      return;
    # try to determine the file type
    filetype,import_func,export_func,doc = Tigger.Models.Formats.resolveFormat(filename,None);
    if export_func is None:
      self.showErrorMessage("""Error saving model file %s: unsupported output format"""%filename);
      return;
    busy = BusyIndicator();
    try:
      export_func(self.model,filename,sources=sources);
    except:
      busy = None;
      self.showErrorMessage("""Error saving selection to model file %s: %s"""%(filename,str(sys.exc_info()[1])));
      return False;
    self.showMessage("""Wrote %d selected source%s to file %s"""%(len(selmodel.sources),"" if len(selmodel.sources)==1 else "s",filename),3000);
    pass;

  def addTagToSelection (self):
    if not hasattr(self,'_add_tag_dialog'):
      self._add_tag_dialog = Widgets.AddTagDialog(self,modal=True);
    self._add_tag_dialog.setTags(self.model.tagnames);
    self._add_tag_dialog.setValue(True);
    if self._add_tag_dialog.exec_() != QDialog.Accepted:
      return;
    tagname,value = self._add_tag_dialog.getTag();
    if tagname is None or value is None:
      return None;
    dprint(1,"tagging selected sources with",tagname,value);
    # tag selected sources
    for src in self.model.sources:
      if src.selected:
        src.setAttribute(tagname,value);
    # If tag is not new, set a UpdateSelectionOnly flag on the signal
    dprint(1,"adding tag to model");
    self.model.addTag(tagname);
    dprint(1,"recomputing totals");
    self.model.getTagGrouping(tagname).computeTotal(self.model.sources);
    dprint(1,"emitting update signal");
    what = SkyModel.UpdateSourceContent+SkyModel.UpdateTags+SkyModel.UpdateSelectionOnly;
    self.model.emitUpdate(what,origin=self);

  def removeTagsFromSelection (self):
    if not hasattr(self,'_remove_tag_dialog'):
      self._remove_tag_dialog = Widgets.SelectTagsDialog(self,modal=True,caption="Remove Tags",ok_button="Remove");
    # get set of all tags in selected sources
    tags = set();
    for src in self.model.sources:
      if src.selected:
        tags.update(src.getTagNames());
    if not tags:
      return;
    tags = list(tags);
    tags.sort();
    # show dialog
    self._remove_tag_dialog.setTags(tags);
    if self._remove_tag_dialog.exec_() != QDialog.Accepted:
      return;
    tags = self._remove_tag_dialog.getSelectedTags();
    if not tags:
      return;
    # ask for confirmation
    plural = (len(tags)>1 and "s") or "";
    if QMessageBox.question(self,"Removing tags","<P>Really remove the tag%s '%s' from selected sources?</P>"%(plural,"', '".join(tags)),
            QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes) != QMessageBox.Yes:
      return;
    # remove the tags
    for src in self.model.sources:
      if src.selected:
        for tag in tags:
          src.removeAttribute(tag);
    # update model
    self.model.scanTags();
    self.model.initGroupings();
    # emit signal
    what = SkyModel.UpdateSourceContent+SkyModel.UpdateTags+SkyModel.UpdateSelectionOnly;
    self.model.emitUpdate(what,origin=self);

  def _indicateModelUpdated (self,what=None,origin=None,updated=True):
    """Marks model as updated.""";
    self._model_updated = updated;
    self.emit(SIGNAL("isUpdated"),updated);
    if self.model:
      self.setWindowTitle("Tigger - %s%s"%((self._display_filename or "(unnamed)"," (modified)" if updated else "")));

