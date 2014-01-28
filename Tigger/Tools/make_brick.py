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
from math import *
import Kittens.utils
pyfits = Kittens.utils.import_pyfits();
import os.path
import traceback

from Kittens.widgets import BusyIndicator
from Tigger.Widgets import FileSelector
from Tigger.Models import SkyModel,ModelClasses
from Tigger.Tools import Imaging

DEG = math.pi/180;

from astLib.astWCS import WCS

class MakeBrickDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=Qt.WindowFlags()):
    QDialog.__init__(self,parent,flags);
    self.setModal(modal);
    self.setWindowTitle("Convert sources to FITS brick");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # file selector
    self.wfile = FileSelector(self,label="FITS filename:",dialog_label="Output FITS file",default_suffix="fits",
                    file_types="FITS files (*.fits *.FITS)",file_mode=QFileDialog.ExistingFile);
    lo.addWidget(self.wfile);
    # reference frequency
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    label = QLabel("Frequency, MHz:",self);
    lo1.addWidget(label);
    tip = """<P>If your sky model contains spectral information (such as spectral indices), then a brick may be generated
    for a specific frequency. If a frequency is not specified here, the reference frequency of the model sources will be assumed.</P>""";
    self.wfreq = QLineEdit(self);
    self.wfreq.setValidator(QDoubleValidator(self));
    label.setToolTip(tip);
    self.wfreq.setToolTip(tip);
    lo1.addWidget(self.wfreq);
    # beam gain
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    self.wpb_apply = QCheckBox("Apply primary beam expression:",self);
    self.wpb_apply.setChecked(True);
    lo1.addWidget(self.wpb_apply);
    tip = """<P>If this option is specified, a primary power beam gain will be applied to the sources before inserting
    them into the brick. This can be any valid Python expression making use of the variables 'r' (corresponding
    to distance from field centre, in radians) and 'fq' (corresponding to frequency.)</P>""";
    self.wpb_exp = QLineEdit(self);
    self.wpb_apply.setToolTip(tip);
    self.wpb_exp.setToolTip(tip);
    lo1.addWidget(self.wpb_exp);
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
    self.wadd = QCheckBox("Add resulting brick to sky model as a FITS image component",self);
    lo.addWidget(self.wadd);
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    self.wpad = QLineEdit(self);
    self.wpad.setValidator(QDoubleValidator(self));
    self.wpad.setText("1.1");
    lab = QLabel("...with padding factor:",self);
    lab.setToolTip("""<P>The padding factor determines the amount of null padding inserted around the image during
      the prediction stage. Padding alleviates the effects of tapering and detapering in the uv-brick, which can show
      up towards the edges of the image. For a factor of N, the image will be padded out to N times its original size.
      This increases memory use, so if you have no flux at the edges of the image anyway, then a pad factor of 1 is
      perfectly fine.</P>""");
    self.wpad.setToolTip(lab.toolTip());
    QObject.connect(self.wadd,SIGNAL("toggled(bool)"),self.wpad.setEnabled);
    QObject.connect(self.wadd,SIGNAL("toggled(bool)"),lab.setEnabled);
    self.wpad.setEnabled(False);
    lab.setEnabled(False);
    lo1.addStretch(1);
    lo1.addWidget(lab,0);
    lo1.addWidget(self.wpad,1);
    self.wdel = QCheckBox("Remove from the sky model sources that go into the brick",self);
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
    pb = self.model.primaryBeam();
    if pb:
      self.wpb_exp.setText(pb);
    else:
      self.wpb_apply.setChecked(False);
      self.wpb_exp.setText("");
    if model.filename():
      self._model_dir = os.path.dirname(os.path.abspath(model.filename()));
    else:
      self._model_dir = os.path.abspath('.');
    self.wfile.setDirectory(self._model_dir);
    self._fileSelected(self.wfile.filename(),quiet=True);

  def _fileSelected (self,filename,quiet=False):
    self.wokbtn.setEnabled(False);
    if not filename:
      return None;
    # check that filename matches model
    if not os.path.samefile(self._model_dir,os.path.dirname(filename)):
      self.wfile.setFilename('');
      if not quiet:
        QMessageBox.warning(self,"Directory mismatch","""<P>The FITS file must reside in the same directory
          as the current sky model.</P>""");
      self.wfile.setDirectory(self._model_dir);
      return None;
    # read fits file
    busy = BusyIndicator();
    try:
      input_hdu = pyfits.open(filename)[0];
      hdr = input_hdu.header;
      # get frequency, if specified
      for axis in range(1,hdr['NAXIS']+1):
        if hdr['CTYPE%d'%axis].upper() == 'FREQ':
          self.wfreq.setText(str(hdr['CRVAL%d'%axis]/1e+6));
          break;
    except Exception,err:
      busy = None;
      self.wfile.setFilename('');
      if not quiet:
        QMessageBox.warning(self,"Error reading FITS","Error reading FITS file %s: %s"%(filename,str(err)));
      return None;
    self.wokbtn.setEnabled(True);
    # if filename is not in model already, enable the "add to model" control
    for src in self.model.sources:
      if isinstance(getattr(src,'shape',None),ModelClasses.FITSImage) \
          and os.path.exists(src.shape.filename) and os.path.exists(filename) \
          and os.path.samefile(src.shape.filename,filename):
        self.wadd.setChecked(True);
        self.wadd.setEnabled(False);
        self.wadd.setText("image already in sky model");
        break;
    else:
      self.wadd.setText("add image to sky model");
    return filename;

  def accept (self):
    """Tries to make a brick, and closes the dialog if successful.""";
    sources = [ src for src in self.model.sources if src.selected and src.typecode == 'pnt' ];
    filename = self.wfile.filename();
    if not self._fileSelected(filename):
      return;
    # get PB expression
    pbfunc = None;
    if self.wpb_apply.isChecked():
      pbexp = str(self.wpb_exp.text());
      try:
        pbfunc = eval("lambda r,fq:"+pbexp);
      except Exception,err:
        QMessageBox.warning(self,"Error parsing PB experssion",
              "Error parsing primary beam expression %s: %s"%(pbexp,str(err)));
        return;
    # get frequency
    freq = str(self.wfreq.text());
    freq = float(freq)*1e+6 if freq else None;
    # get pad factor
    pad = str(self.wpad.text());
    pad = max(float(pad),1) if pad else 1;
    # read fits file
    busy = BusyIndicator();
    try:
      input_hdu = pyfits.open(filename)[0];
    except Exception,err:
      busy = None;
      QMessageBox.warning(self,"Error reading FITS","Error reading FITS file %s: %s"%(filename,str(err)));
      return;
    # reset data if asked to
    if self.woverwrite.isChecked():
      input_hdu.data[...] = 0;
    # insert sources
    Imaging.restoreSources(input_hdu,sources,0,primary_beam=pbfunc,freq=freq);
    # save fits file
    try:
      # pyfits seems to produce an exception:
      #         TypeError: formatwarning() takes exactly 4 arguments (5 given)
      # when attempting to overwrite a file. As a workaround, remove the file first.
      if os.path.exists(filename):
        os.remove(filename);
      input_hdu.writeto(filename);
    except Exception,err:
      traceback.print_exc();
      busy = None;
      QMessageBox.warning(self,"Error writing FITS","Error writing FITS file %s: %s"%(filename,str(err)));
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
      # Get reference pixel coordinates
      # wcs.getCentreWCSCoords() doesn't work, as that gives us the middle of the image
      # So scan the header to get the CRPIX values
      ra0 = dec0 = 1;
      for iaxis in range(hdr['NAXIS']):
        axs = str(iaxis+1);
        name = hdr.get('CTYPE'+axs,axs).upper();
        if name.startswith("RA"):
          ra0 = hdr.get('CRPIX'+axs,1)-1;
        elif name.startswith("DEC"):
          dec0 = hdr.get('CRPIX'+axs,1)-1;
      # convert pixel to degrees
      ra0,dec0 = wcs.pix2wcs(ra0,dec0);
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
          src.pos.ra,src.pos.dec = ra0,dec0;
          src.flux.I = max_flux;
          src.shape.ex,src.shape.ey = sx,sy;
          src.shape.nx,src.shape.ny = nx,ny;
          src.shape.pad = pad;
          break;
      # not contained, make new source object
      else:
        pos = ModelClasses.Position(ra0,dec0);
        flux = ModelClasses.Flux(max_flux);
        shape = ModelClasses.FITSImage(sx,sy,0,os.path.basename(filename),nx,ny,pad=pad);
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
