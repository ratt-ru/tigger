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
import os.path
from Kittens.widgets import BusyIndicator
from Tigger.Widgets import FileSelector

DEG = math.pi/180;


class ExportKarmaDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=Qt.WindowFlags()):
    QDialog.__init__(self,parent,flags);
    self.setModal(modal);
    self.setWindowTitle("Export Karma annotations");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # file selector
    self.wfile = FileSelector(self,label="Filename:",dialog_label="Karma annotations filename",default_suffix="ann",file_types="Karma annotations (*.ann)");
    lo.addWidget(self.wfile);
    # selected sources checkbox
    self.wsel = QCheckBox("selected sources only",self);
    lo.addWidget(self.wsel);
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
    QObject.connect(self.wfile,SIGNAL("valid"),self.wokbtn.setEnabled);
    # internal state
    self.qerrmsg = QErrorMessage(self);
    self._model_filename = None;

  def setModel (self,model):
    self.model = model;
    # set the default annotations filename, whenever a new model filename is set
    filename = self.model.filename();
    if filename and filename != self._model_filename:
      self._model_filename = filename;
      self.wfile.setFilename(os.path.splitext(filename)[0] + ".ann");

  def accept (self):
    """Tries to export annotations, and closes the dialog if successful.""";
    try:
      filename = self.wfile.filename();
      if os.path.exists(filename) and QMessageBox.question(self,"Exporting Karma annotations","<P>Overwrite the file %s?</P>"%filename,
                QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes) != QMessageBox.Yes:
          return;
      f = file(self.wfile.filename(),"wt");
      f.write('COORD W\nPA STANDARD\nCOLOR GREEN\nFONT hershey12\n');
      # source list
      if self.wsel.isChecked():
        sources = [ src for src in self.model.sources if src.selected ];
      else:
        sources = self.model.sources;
      # calculate basis size for crosses (TODO: replace min_size with something more sensible, as this value is in degrees)
      brightnesses = [ abs(src.brightness()) for src in sources if src.brightness() != 0 ];
      min_bright = brightnesses and min(brightnesses) ;
      min_size = 0.01;
      # loop over sources
      busy = BusyIndicator();
      for src in sources:
        ra = src.pos.ra/DEG;
        dec = src.pos.dec/DEG;
        # figure out source size
        if src.brightness() and min_bright:
          ysize = (math.log10(abs(src.brightness())) - math.log10(min_bright) + 1)*min_size;
        else:
          ysize = min_size;
        xsize = ysize/(math.cos(src.pos.dec) or 1);
        # figure out source style
        style,label = self.model.getSourcePlotStyle(src);
        if style:
          f.write('# %s\n'%src.name);
          # write symbol for source
          f.write('COLOR %s\n'%style.symbol_color);
          if style.symbol == "plus":
            f.write('CROSS %.12f %.12f %f %f\n'%(ra,dec,xsize,ysize));
          elif style.symbol == "cross":
            f.write('CROSS %.12f %.12f %f %f 45\n'%(ra,dec,ysize,ysize));
          elif style.symbol == "circle":
            f.write('CIRCLE %.12f %.12f %f\n'%(ra,dec,ysize));
          elif style.symbol == "dot":
            f.write('DOT %.12f %.12f\n'%(ra,dec));
          elif style.symbol == "square":
            f.write('CBOX %.12f %.12f %f %f\n'%(ra,dec,xsize,ysize));
          elif style.symbol == "diamond":
            f.write('CBOX %.12f %.12f %f %f 45\n'%(ra,dec,xsize,ysize));
          # write label
          if label:
            f.write('FONT hershey%d\n'%(style.label_size*2));
            f.write('COLOR %s\n'%style.label_color);
            f.write('TEXT %.12f %.12f %s\n'%(ra,dec,label));
      f.close();
    except IOError,err:
      busy = None;
      self.qerrmsg.showMessage("Error writing Karma annotations file %s: %s"%(filename,str(err)));
      return;
    busy = None;
    self.parent().showMessage("Wrote Karma annotations for %d sources to file %s"%(len(sources),filename));
    return QDialog.accept(self);

def export_karma_annotations (mainwin,model):
  dialog = getattr(mainwin,'_export_karma_dialog',None);
  if not dialog:
    dialog = mainwin._export_karma_dialog = ExportKarmaDialog(mainwin);
  dialog.setModel(model);
  # show dialog
  return dialog.exec_();

from Tigger.Tools import registerTool
registerTool("Export Karma annotations...",export_karma_annotations);