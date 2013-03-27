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
import math
import Kittens.utils
pyfits = Kittens.utils.import_pyfits();
import os.path

from Kittens.widgets import BusyIndicator
from Tigger.Widgets import FileSelector
from Tigger.Models import SkyModel,ModelClasses
from Tigger.Tools import Imaging

DEG = math.pi/180;

from astLib.astWCS import WCS

class RestoreImageDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=Qt.WindowFlags()):
    QDialog.__init__(self,parent,flags);
    self.setModal(modal);
    self.setWindowTitle("Restore model into image");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # file selector
    self.wfile_in = FileSelector(self,label="Input FITS file:",dialog_label="Input FITS file",default_suffix="fits",file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.ExistingFile);
    lo.addWidget(self.wfile_in);
    self.wfile_out = FileSelector(self,label="Output FITS file:",dialog_label="Output FITS file",default_suffix="fits",file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.AnyFile);
    lo.addWidget(self.wfile_out);
    # beam size
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    lo1.addWidget(QLabel("Restoring beam FWHM, major axis:",self));
    self.wbmaj = QLineEdit(self);
    lo1.addWidget(self.wbmaj);
    lo1.addWidget(QLabel("\"     minor axis:",self));
    self.wbmin = QLineEdit(self);
    lo1.addWidget(self.wbmin);
    lo1.addWidget(QLabel("\"     P.A.:",self));
    self.wbpa = QLineEdit(self);
    lo1.addWidget(self.wbpa);
    lo1.addWidget(QLabel(u"\u00B0",self));
    for w in self.wbmaj,self.wbmin,self.wbpa:
      w.setValidator(QDoubleValidator(self));
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    self.wfile_psf = FileSelector(self,label="Set restoring beam by fitting PSF image:",dialog_label="PSF FITS file",default_suffix="fits",file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.ExistingFile);
    lo1.addSpacing(32);
    lo1.addWidget(self.wfile_psf);
    # selection only
    self.wselonly = QCheckBox("restore selected model sources only",self);
    lo.addWidget(self.wselonly );
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
    QObject.connect(self.wfile_in,SIGNAL("filenameSelected"),self._fileSelected);
    QObject.connect(self.wfile_in,SIGNAL("filenameSelected"),self._inputFileSelected);
    QObject.connect(self.wfile_out,SIGNAL("filenameSelected"),self._fileSelected);
    QObject.connect(self.wfile_psf,SIGNAL("filenameSelected"),self._psfFileSelected);
    # internal state
    self.qerrmsg = QErrorMessage(self);

  def setModel (self,model):
    nsel = len([ src for src in model.sources if src.selected ]);
    self.wselonly.setVisible(nsel>0 and nsel<len(model.sources));
    self.model = model;
    self._fileSelected(None);

  def _fileSelected (self,filename):
    self.wokbtn.setEnabled(bool(self.wfile_in.filename() and self.wfile_out.filename()));
    
  def _inputFileSelected (self,filename):
    if filename:
      try:
        header = pyfits.open(filename)[0].header;
      except:
        self.qerrmsg.showMessage("Error reading FITS file %s: %s"%(filename,str(err)));
        self.wfile_in.setFilename("");
        return;
      # try to get beam extents
      gx,gy,grot = [ header.get(x,None) for x in 'BMAJ','BMIN','BPA' ];
      if all([x is not None for x in gx,gy,grot]):
        # if beam size is already set, ask before overwriting
        print [ str(x.text()) for x in self.wbmaj,self.wbmin,self.wbpa ]
        if any([ bool(str(x.text())) for x in self.wbmaj,self.wbmin,self.wbpa ]) and \
          QMessageBox.question(self,"Set restoring beam","Also reset restoring beam size from this FITS file?",
            QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
          return;
        self.wbmaj.setText("%.2f"%(gx*3600));
        self.wbmin.setText("%.2f"%(gy*3600));
        self.wbpa.setText("%.2f"%grot);
    
  def _psfFileSelected (self,filename):
    busy = BusyIndicator();
    filename = str(filename);
    self.parent().showMessage("Fitting gaussian to PSF file %s"%filename);
    try:
      bmaj,bmin,pa = [ x/DEG for x in Imaging.fitPsf(filename) ];
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error fitting PSF file %s: %s"%(filename,str(err)));
      return;
    bmaj *= 3600*Imaging.FWHM;
    bmin *= 3600*Imaging.FWHM;
    self.wbmaj.setText(str(bmaj));
    self.wbmin.setText(str(bmin));
    self.wbpa.setText(str(pa));

  def accept (self):
    """Tries to restore the image, and closes the dialog if successful.""";
    # get list of sources to restore
    sources = self.model.sources;
    sel_sources = filter(lambda src:src.selected,sources);
    if len(sel_sources) > 0 and len(sel_sources) < len(sources) and self.wselonly.isChecked():
      sources = sel_sources;
    if not sources:
      self.qerrmsg.showMessage("No sources to restore.");
      return;
    busy = BusyIndicator();
    # get filenames
    infile = self.wfile_in.filename();
    outfile = self.wfile_out.filename();
    self.parent().showMessage("Restoring %d model sources to image %s, writing to %s"%(len(sources),infile,outfile));
    # read fits file
    try:
      input_hdu = pyfits.open(infile)[0];
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error reading FITS file %s: %s"%(infile,str(err)));
      return;
    # get beam sizes
    try:
      bmaj = float(str(self.wbmaj.text()));
      bmin = float(str(self.wbmin.text()));
      pa = float(str(self.wbpa.text()) or "0");
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Invalid beam size specified");
      return;
    bmaj = bmaj/(Imaging.FWHM*3600)*DEG;
    bmin = bmin/(Imaging.FWHM*3600)*DEG;
    pa = pa*DEG;
    # restore
    try:
      Imaging.restoreSources(input_hdu,sources,bmaj,bmin,pa);
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error restoring model into image: %s"%str(err));
      return;
    # save fits file
    try:
      input_hdu.writeto(outfile,clobber=True);
    except Exception,err:
      busy = None;
      self.qerrmsg.showMessage("Error writing FITS file %s: %s"%(outfile,str(err)));
      return;
    self.parent().loadImage(outfile);
    busy = None;
    return QDialog.accept(self);

def restore_into_image (mainwin,model):
  dialog = getattr(mainwin,'_restore_into_image_dialog',None);
  if not dialog:
    dialog = mainwin._restore_into_image_dialog = RestoreImageDialog(mainwin);
  dialog.setModel(model);
  # show dialog
  return dialog.exec_();

from Tigger.Tools import registerTool
registerTool("Restore model into image...",restore_into_image);
