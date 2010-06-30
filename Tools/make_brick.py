from PyQt4.Qt import *
import math
import pyfits
import os.path

from Kittens.widgets import BusyIndicator
from Tigger.Widgets import FileSelector
from Tigger.Models import SkyModel,ModelClasses
from Tigger.Tools import Imaging

DEG = math.pi/180;

from astLib.astWCS import WCS

class MakeBrickDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=0):
    QDialog.__init__(self,parent,Qt.WindowFlags(flags));
    self.setModal(modal);
    self.setWindowTitle("Convert sources to FITS brick");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # file selector
    self.wfile = FileSelector(self,label="FITS filename:",dialog_label="Output FITS file",default_suffix="fits",file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.ExistingFile);
    lo.addWidget(self.wfile);
    # overwrite or add mode
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    self.woverwrite = QRadioButton("overwrite image",self);
    self.woverwrite.setChecked(True);
    lo1.addWidget(self.woverwrite);
    self.waddinto = QRadioButton("add into image",self);
    lo1.addWidget(self.waddinto);
    # add to model
    self.wadd = QCheckBox("add image to sky model",self);
    lo.addWidget(self.wadd);
    self.wdel = QCheckBox("remove sources from sky model",self);
    lo.addWidget(self.wdel);
    # OK/cancel buttons
    lo.addSpacing(10);
    lo2 = QHBoxLayout();
    lo.addLayout(lo2);
    lo2.setContentsMargins(0,0,0,0);
    lo2.setMargin(5);
    self.wokbtn = QPushButton("OK",self);
    self.wokbtn.setMinimumWidth(128);
    QObject.connect(self.wokbtn,SIGNAL("clicked()"),self.accept);
    self.wokbtn.setEnabled(False);
    cancelbtn = QPushButton("Cancel",self);
    cancelbtn.setMinimumWidth(128);
    QObject.connect(cancelbtn,SIGNAL("clicked()"),self.reject);
    lo2.addWidget(self.wokbtn);
    lo2.addStretch(1);
    lo2.addWidget(cancelbtn);
    self.setMinimumWidth(384);
    # signals
    QObject.connect(self.wfile,SIGNAL("filenameSelected"),self._fileSelected);
    # internal state
    self.qerrmsg = QErrorMessage(self);

  def setModel (self,model):
    self.model = model;
    self._fileSelected(self.wfile.filename());

  def _fileSelected (self,filename):
    self.wokbtn.setEnabled(bool(filename));
    # if filename is not in model already, enable the "add to model" control
    for src in self.model.sources:
      if isinstance(getattr(src,'shape',None),ModelClasses.FITSImage) and os.path.samefile(src.shape.filename,filename):
        self.wadd.setChecked(True);
        self.wadd.setEnabled(False);
        self.wadd.setText("image already in sky model");
        break;
    else:
      self.wadd.setText("add image to sky model");

  def accept (self):
    """Tries to make a brick, and closes the dialog if successful.""";
    sources = [ src for src in self.model.sources if src.selected and src.typecode == 'pnt' ];
    filename = self.wfile.filename();
    self._fileSelected(filename);
    # read fits file
    busy = BusyIndicator();
    try:
      input_hdu = pyfits.open(filename)[0];
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error reading FITS file %s: %s"%(filename,str(err)));
      return;
    # reset data if asked to
    if self.woverwrite.isChecked():
      input_hdu.data[...] = 0;
    # insert sources
    Imaging.restoreSources(input_hdu,sources,0);
    # save fits file
    try:
      input_hdu.writeto(filename,clobber=True);
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error writing FITS file %s: %s"%(filename,str(err)));
      return;
    changed = False;
    sources = self.model.sources;
    # remove sources from model if asked to
    if self.wdel.isChecked():
      sources = [ src for src in sources if not (src.selected and src.typecode == 'pnt') ];
      changed = True;
    # add image to model if asked to
    if self.wadd.isChecked():
      hdr = input_hdu.header;
      # get image parameters
      max_flux = float(input_hdu.data.max());
      wcs = WCS(hdr,mode='pyfits');
      # center coordinates
      ra0,dec0 = wcs.getCentreWCSCoords();
      ra0 *= DEG;
      dec0 *= DEG;
      sx,sy = wcs.getHalfSizeDeg();
      sx *= DEG;
      sy *= DEG;
      nx,ny = input_hdu.data.shape[-1:-3:-1];
      # check if this image is already contained in the model
      for src in sources:
        if isinstance(getattr(src,'shape',None),ModelClasses.FITSImage) and os.path.samefile(src.shape.filename,filename):
          # update source parameters
          src.position.ra,src.position.dec = ra0,dec0;
          src.flux.I = max_flux;
          src.shape.ex,src.shape.ey = sx,sy;
          src.shape.nx,src.shape.ny = nx,ny;
          break;
      # not contained, make new source object
      else:
        pos = ModelClasses.Position(ra0,dec0);
        flux = ModelClasses.Flux(max_flux);
        shape = ModelClasses.FITSImage(sx,sy,0,filename,nx,ny);
        img_src = SkyModel.Source(os.path.splitext(os.path.basename(filename))[0],pos,flux,shape=shape);
        sources.append(img_src);
      changed = True;
    if changed:
      self.model.setSources(sources);
      self.model.emitUpdate(SkyModel.SkyModel.UpdateAll,origin=self);
    self.parent().showMessage("Wrote %d sources to FITS file %s"%(len(sources),filename));
    busy = None;
    return QDialog.accept(self);

def make_brick (mainwin,model):
  # check that something is selected
  if not [ src for src in model.sources if src.selected ]:
    mainwin.showErrorMessage("Cannot make FITS brick without a source selection. Please select some sources first.");
    return;
  dialog = getattr(mainwin,'_make_brick_dialog',None);
  if not dialog:
    dialog = mainwin._make_brick_dialog = MakeBrickDialog(mainwin);
  dialog.setModel(model);
  # show dialog
  return dialog.exec_();

from Tigger.Tools import registerTool
registerTool("Make FITS brick from selected sources...",make_brick);
