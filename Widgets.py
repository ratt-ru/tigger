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

import sys
import math
import traceback
import re

from PyQt4.Qt import *
from PyQt4.Qwt5 import *

class TiggerPlotCurve (QwtPlotCurve):
  """Wrapper around QwtPlotCurve to make it compatible with numpy float types"""
  def setData (self,x,y):
    return QwtPlotCurve.setData(self,map(float,x),map(float,y));

class TiggerPlotMarker (QwtPlotMarker):
  """Wrapper around QwtPlotCurve to make it compatible with numpy float types"""
  def setValue (self,x,y):
    return QwtPlotMarker.setValue(self,float(x),float(y));


class FloatValidator (QValidator):
  """QLineEdit validator for float items in standard or scientific notation""";
  re_intermediate = re.compile("^-?([0-9]*)\.?([0-9]*)([eE]([+-])?[0-9]*)?$");
  def validate (self,input,pos):
    input = str(input);
    try:
      x = float(input);
      return QValidator.Acceptable,pos;
    except:
      pass;
    if not input or self.re_intermediate.match(input):
      return QValidator.Intermediate,pos;
    return QValidator.Invalid,pos;

class ValueTypeEditor (QWidget):
  ValueTypes = (bool,int,float,complex,str);
  def __init__ (self,*args):
    QWidget.__init__(self,*args);
    lo = QHBoxLayout(self);
    lo.setContentsMargins(0,0,0,0);
    lo.setSpacing(5);
    # type selector
    self.wtypesel = QComboBox(self);
    for i,tp in enumerate(self.ValueTypes):
      self.wtypesel.addItem(tp.__name__);
    QObject.connect(self.wtypesel,SIGNAL("activated(int)"),self._selectTypeNum);
    typesel_lab = QLabel("&Type:",self);
    typesel_lab.setBuddy(self.wtypesel);
    lo.addWidget(typesel_lab,0);
    lo.addWidget(self.wtypesel,0);
    self.wvalue = QLineEdit(self);
    self.wvalue_lab = QLabel("&Value:",self);
    self.wvalue_lab.setBuddy(self.wvalue);
    self.wbool = QComboBox(self);
    self.wbool.addItems(["false","true"]);
    self.wbool.setCurrentIndex(1);
    lo.addWidget(self.wvalue_lab,0);
    lo.addWidget(self.wvalue,1);
    lo.addWidget(self.wbool,1);
    self.wvalue.hide();
    # make input validators
    self._validators = {int:QIntValidator(self),float:QDoubleValidator(self) };
    # select bool type initially
    self._selectTypeNum(0);

  def _selectTypeNum (self,index):
    tp = self.ValueTypes[index];
    self.wbool.setShown(tp is bool);
    self.wvalue.setShown(tp is not bool);
    self.wvalue_lab.setBuddy(self.wbool if tp is bool else self.wvalue);
    self.wvalue.setValidator(self._validators.get(tp,None));

  def setValue (self,value):
    """Sets current value""";
    for i,tp in enumerate(self.ValueTypes):
      if isinstance(value,tp):
        self.wtypesel.setCurrentIndex(i);
        self._selectTypeNum(i);
        if tp is bool:
          self.wbool.setCurrentIndex(1 if value else 0);
        else:
          self.wvalue.setText(str(value));
        return;
    # unknown value: set bool
    self.setValue(True);

  def getValue (self):
    """Returns current value, or None if no legal value is set""";
    tp = self.ValueTypes[self.wtypesel.currentIndex()];
    if tp is bool:
      return bool(self.wbool.currentIndex());
    else:
      try:
        return tp(self.wvalue.text());
      except:
        print "Error converting input to type ",tp.__name__;
        traceback.print_exc();
        return None;


class FileSelector (QWidget):
  """A FileSelector is a one-line widget for selecting a file.""";
  def __init__ (self,parent,label,filename=None,dialog_label=None,file_types=None,default_suffix=None,file_mode=QFileDialog.AnyFile):
    QWidget.__init__(self,parent);
    lo = QHBoxLayout(self);
    lo.setContentsMargins(0,0,0,0);
    lo.setSpacing(5);
    # label
    lab = QLabel(label,self);
    lo.addWidget(lab,0);
    # text field
    self.wfname = QLineEdit(self);
    self.wfname.setReadOnly(True);
    self.setFilename(filename);
    lo.addWidget(self.wfname,1);
    # selector
    wsel = QToolButton(self);
    wsel.setText("Choose...");
    QObject.connect(wsel,SIGNAL("clicked()"),self._chooseFile);
    lo.addWidget(wsel,0);
    # other init
    self._file_dialog = None;
    self._dialog_label = dialog_label or label;
    self._file_types = file_types or "All files (*)";
    self._file_mode = file_mode;
    self._default_suffix = default_suffix;
    self._dir = None;

  def _chooseFile (self):
    if self._file_dialog is None:
      dialog = self._file_dialog = QFileDialog(self,self._dialog_label,".",self._file_types);
      if self._default_suffix:
        dialog.setDefaultSuffix(self._default_suffix);
      dialog.setFileMode(self._file_mode);
      dialog.setModal(True);
      if self._dir is not None:
        dialog.setDirectory(self._dir);
      QObject.connect(dialog,SIGNAL("filesSelected(const QStringList &)"),self.setFilename);
    return self._file_dialog.exec_();

  def setFilename (self,filename):
    if isinstance(filename,QStringList):
      filename = filename[0];
    filename = (filename and str(filename) ) or '';
    self.wfname.setText(filename);
    self.emit(SIGNAL("valid"),bool(filename));
    self.emit(SIGNAL("filenameSelected"),filename);
    
  def setDirectory (self,directory):
    self._dir = directory;
    if self._file_dialog is not None:
      self._file_dialog.setDirectory(directory);

  def filename (self):
    return str(self.wfname.text());

  def isValid (self):
    return bool(self.filename());



class AddTagDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=Qt.WindowFlags()):
    QDialog.__init__(self,parent,flags);
    self.setModal(modal);
    self.setWindowTitle("Add Tag");
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # tag selector
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setSpacing(5);
    self.wtagsel = QComboBox(self);
    self.wtagsel.setEditable(True);
    wtagsel_lbl = QLabel("&Tag:",self);
    wtagsel_lbl.setBuddy(self.wtagsel);
    lo1.addWidget(wtagsel_lbl,0);
    lo1.addWidget(self.wtagsel,1);
    QObject.connect(self.wtagsel,SIGNAL("activated(int)"),self._check_tag);
    QObject.connect(self.wtagsel,SIGNAL("editTextChanged(const QString &)"),self._check_tag_text);
    # value editor
    self.valedit = ValueTypeEditor(self);
    lo.addWidget(self.valedit);
    # buttons
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

  def setTags (self,tagnames):
    self.wtagsel.clear();
    self.wtagsel.addItems(list(tagnames));
    self.wtagsel.addItem("");
    self.wtagsel.setCurrentIndex(len(tagnames));

  def setValue (self,value):
    self.valedit.setValue(value);

  def _check_tag (self,tag):
    self.wokbtn.setEnabled(True);

  def _check_tag_text (self,text):
    self.wokbtn.setEnabled(bool(str(text)!=""));
    
  def accept (self):
    """When dialog is accepted with a default (bool) tag type,
    check if the user hasn't entered a name=value entry in the tag name field.
    This is a common mistake, and should be treated as a shortcut for setting string tags.""";
    if isinstance(self.valedit.getValue(),bool):
      tagval = str(self.wtagsel.currentText()).split("=",1);
      if len(tagval) > 1:
#        print tagval;
        if QMessageBox.warning(self,
            "Set a string tag instead?","""<P>You have included an "=" sign in the tag name. 
            Perhaps you actually mean to set tag "%s" to the string value "%s"?</P>"""%tuple(tagval),
                  QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes) == QMessageBox.No:
          return;
        self.wtagsel.setEditText(tagval[0]);
        self.valedit.setValue(tagval[1]);
    return QDialog.accept(self);

  def getTag (self):
    return str(self.wtagsel.currentText()),self.valedit.getValue();

class SelectTagsDialog (QDialog):
  def __init__ (self,parent,modal=True,flags=Qt.WindowFlags(),caption="Select Tags",ok_button="Select"):
    QDialog.__init__(self,parent,flags);
    self.setModal(modal);
    self.setWindowTitle(caption);
    lo = QVBoxLayout(self);
    lo.setMargin(10);
    lo.setSpacing(5);
    # tag selector
    self.wtagsel = QListWidget(self);
    lo.addWidget(self.wtagsel);
#    self.wtagsel.setColumnMode(QListBox.FitToWidth);
    self.wtagsel.setSelectionMode(QListWidget.MultiSelection);
    QObject.connect(self.wtagsel,SIGNAL("itemSelectionChanged()"),self._check_tag);
    # buttons
    lo.addSpacing(10);
    lo2 = QHBoxLayout();
    lo.addLayout(lo2);
    lo2.setContentsMargins(0,0,0,0);
    lo2.setMargin(5);
    self.wokbtn = QPushButton(ok_button,self);
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
    self._tagnames = [];

  def setTags (self,tagnames):
    self._tagnames = tagnames;
    self.wtagsel.clear();
    self.wtagsel.insertItems(0,list(tagnames));

  def _check_tag (self):
    for i in range(len(self._tagnames)):
      if self.wtagsel.item(i).isSelected():
        self.wokbtn.setEnabled(True);
        return;
    else:
      self.wokbtn.setEnabled(False);

  def getSelectedTags (self):
    return [ tag for i,tag in enumerate(self._tagnames) if self.wtagsel.item(i).isSelected() ];
