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

class AddBrickDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=0):
    QDialog.__init__(self,parent,Qt.WindowFlags(flags));
    self.setModal(modal);
    self.setWindowTitle("Add FITS brick");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # file selector
    self.wfile = FileSelector(self,label="FITS filename:",dialog_label="FITS file",default_suffix="fits",file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.ExistingFile);
    lo.addWidget(self.wfile);
    # overwrite or add mode
    lo1 = QGridLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    lo1.addWidget(QLabel("Padding factor:",self),0,0);
    self.wpad = QLineEdit("2",self);
    self.wpad.setValidator(QDoubleValidator(self));
    lo1.addWidget(self.wpad,0,1);
    lo1.addWidget(QLabel("Source name:",self),1,0);
    self.wname = QLineEdit(self);
    lo1.addWidget(self.wname,1,1);
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
    if not filename:
      return;
    # if filename is not in model already, enable the "add to model" control
    for src in self.model.sources:
      if isinstance(getattr(src,'shape',None),ModelClasses.FITSImage) and os.path.samefile(src.shape.filename,filename):
        QMessageBox.warning(self,"Already in model","This FITS brick is already present in the model.");
        self.wokbtn.setEnabled(False);
        return;
    self.wname.setText(os.path.splitext(os.path.basename(str(filename)))[0]);
    self.wokbtn.setEnabled(True);

  def accept (self):
    """Tries to add brick, and closes the dialog if successful.""";
    filename = self.wfile.filename();
    # read fits file
    busy = BusyIndicator();
    try:
      input_hdu = pyfits.open(filename)[0];
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error reading FITS file %s: %s"%(filename,str(err)));
      return;
    # check name
    name = str(self.wname.text()) or os.path.splitext(os.path.basename(str(filename)))[0];
    if name in set([src.name for src in self.model.sources]):
        QMessageBox.warning(self,"Already in model","<p>The model already contains a source named '%s'. Please select a different name.</p>");
        return;
    # get image parameters
    hdr = input_hdu.header;
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
    pos = ModelClasses.Position(ra0,dec0);
    flux = ModelClasses.Flux(max_flux);
    shape = ModelClasses.FITSImage(sx,sy,0,filename,nx,ny,pad=float(str(self.wpad.text())));
    img_src = SkyModel.Source(name,pos,flux,shape=shape);
    self.model.setSources(self.model.sources + [img_src]);
    self.model.emitUpdate(SkyModel.SkyModel.UpdateAll,origin=self);
    busy = None;
    return QDialog.accept(self);

def add_brick (mainwin,model):
  dialog = getattr(mainwin,'_add_brick_dialog',None);
  if not dialog:
    dialog = mainwin._add_brick_dialog = AddBrickDialog(mainwin);
  dialog.setModel(model);
  # show dialog
  return dialog.exec_();

from Tigger.Tools import registerTool
registerTool("Add FITS brick to model...",add_brick);
