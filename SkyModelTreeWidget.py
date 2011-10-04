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

import math
from PyQt4.Qt import *

import Kittens.widgets
import Kittens.utils
from Kittens.utils import PersistentCurrier
from Kittens.widgets import BusyIndicator

from Models import ModelClasses,PlotStyles
from Models.SkyModel import SkyModel

_verbosity = Kittens.utils.verbosity(name="tw");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;


ViewColumns = [ "name","RA","Dec","r","type","Iapp","I","Q","U","V","RM","spi","shape","tags" ];

for icol,col in enumerate(ViewColumns):
    globals()["Column%s"%col.capitalize()] = icol;
NumColumns = len(ViewColumns);

# Qt-4.6 and up (PyQt 4.7 and up) has very slow QTreeWidgetItem updates, determine version here
from PyQt4 import QtCore
_SLOW_QTREEWIDGETITEM = QtCore.PYQT_VERSION_STR >= '4.7';

class SkyModelTreeWidget (Kittens.widgets.ClickableTreeWidget):
  """This implements a QTreeWidget for sky models""";
  def __init__ (self,*args):
    Kittens.widgets.ClickableTreeWidget.__init__(self,*args);
    self._currier = PersistentCurrier();
    self.model = None;
    # insert columns
    self.setHeaderLabels(ViewColumns);
    self.headerItem().setText(ColumnIapp,"I(app)");
    self.header().setMovable(False);
    self.header().setClickable(True);
    self.setSortingEnabled(True);
    self.setRootIsDecorated(False);
    self.setEditTriggers(QAbstractItemView.AllEditTriggers);
    self.setMouseTracking(True);
    # set column width modes
    for icol in range(NumColumns-1):
      self.header().setResizeMode(icol,QHeaderView.ResizeToContents);
    self.header().setStretchLastSection(True);
    ## self.setTextAlignment(ColumnR,Qt.AlignRight);
    ## self.setTextAlignment(ColumnType,Qt.AlignHCenter);
    # _column_enabled[i] is True if column is available in the model.
    # _column_show[i] is True if column is currently being shown (via a view control)
    self._column_enabled = [True]*NumColumns;
    self._column_shown    = [True]*NumColumns;
    # other listview init
    self.header().show();
    self.setSelectionMode(QTreeWidget.ExtendedSelection);
    self.setAllColumnsShowFocus(True);
    ## self.setShowToolTips(True);
    self._updating_selection = False;
    self.setRootIsDecorated(False);
    # connect signals to track selected sources
    QObject.connect(self,SIGNAL("itemSelectionChanged()"),self._selectionChanged);
    QObject.connect(self,SIGNAL("itemEntered(QTreeWidgetItem*,int)"),self._itemHighlighted);
    # add "View" controls for different column categories
    self._column_views = [];
    self._column_widths = {};
    self.addColumnCategory("Position",[ColumnRa,ColumnDec]);
    self.addColumnCategory("Type",[ColumnType]);
    self.addColumnCategory("Flux",[ColumnIapp,ColumnI]);
    self.addColumnCategory("Polarization",[ColumnQ,ColumnU,ColumnV,ColumnRm]);
    self.addColumnCategory("Spectrum",[ColumnSpi]);
    self.addColumnCategory("Shape",[ColumnShape]);
    self.addColumnCategory("Tags",[ColumnTags]);

  def _showColumn (self,col,show=True):
    """Shows or hides the specified column.
    (When hiding, saves width of column to internal array so that it can be restored grouperly.)"""
    hdr = self.header();
    hdr.setSectionHidden(col,not show)
    if show:
      if not hdr.sectionSize(col):
        hdr.resizeSection(col,self._column_widths[col]);
        hdr.setResizeMode(col,QHeaderView.ResizeToContents);
    else:
      if hdr.sectionSize(col):
        self._column_widths[col] = hdr.sectionSize(col);

  def _enableColumn (self,column,enable=True):
    busy = BusyIndicator();
    self._column_enabled[column] = enable;
    self._showColumn(column,enable and self._column_shown[column]);

  def _showColumnCategory (self,columns,show):
    busy = BusyIndicator();
    for col in columns:
      self._column_shown[col] = show;
      self._showColumn(col,self._column_enabled[col] and show);

  def _selectionChanged (self):
    if self._updating_selection:
      return;
    for item in self.iterator():
      item._src.select(item.isSelected());
    self.model.emitSelection(origin=self);

  def _itemHighlighted (self,item,col):
    dprint(3,"highlighting",item._src.name);
    self.model.setCurrentSource(item._src,origin=self);

  def viewportEvent (self,event):
    if event.type() in (QEvent.Leave,QEvent.FocusOut) and self.model:
      self.model.setCurrentSource(None,origin=self);
    return QTreeWidget.viewportEvent(self,event);

  def addColumnCategory (self,name,columns):
    qa = QAction(name,self);
    qa.setCheckable(True);
    qa.setChecked(True);
    QObject.connect(qa,SIGNAL("toggled(bool)"),self._currier.curry(self._showColumnCategory,columns));
    self._column_views.append((name,qa,columns));

  def clear (self):
    Kittens.widgets.ClickableTreeWidget.clear(self);
    self.model = None;
    self._itemdict = {};

  def setModel (self,model):
    self.model = model;
    self._refreshModel(SkyModel.UpdateAll);
    self.model.connect("changeCurrentSource",self._updateCurrentSource);
    self.model.connect("changeGroupingVisibility",self.changeGroupingVisibility);
    self.model.connect("selected",self._updateModelSelection);
    self.model.connect("updated",self._refreshModel);

  def _refreshModel (self,what=SkyModel.UpdateAll,origin=None):
    if origin is self or not what&(SkyModel.UpdateSourceList|SkyModel.UpdateSourceContent):
      return;
    # if only selection was changed, take shortcut
    if what&SkyModel.UpdateSelectionOnly:
      dprint(2,"model update -- selection only");
      return self._refreshSelectedItems(origin);
    busy = BusyIndicator();
    # else repopulate widget completely
    dprint(2,"model update -- complete");
    Kittens.widgets.ClickableTreeWidget.clear(self);
    dprint(2,"creating model items");
    items = [ SkyModelTreeWidgetItem(src) for src in self.model.sources ];
    self._itemdict = dict(zip([src.name for src in self.model.sources],items));
    dprint(2,"adding to tree widget");
    self.addTopLevelItems(items);
    self.header().updateGeometry();
    # show/hide columns based on tag availability
    self._enableColumn(ColumnIapp,'Iapp' in self.model.tagnames);
    self._enableColumn(ColumnR,'r' in self.model.tagnames);
    dprint(2,"re-sorting");
    self.sortItems(('Iapp' in self.model.tagnames and ColumnIapp) or ColumnI,Qt.DescendingOrder);
    busy = None;

  def addColumnViewActionsTo (self,menu):
    for name,qa,columns in self._column_views:
      menu.addAction(qa);

  def _updateCurrentSource (self,src,src0=None,origin=None):
    # if origin is self:
    # return;
    # dehighlight old item
    item = src0 and self._itemdict.get(src0.name);
    if item:
      item.setHighlighted(False);
    # scroll to new item, if found
    item = src and self._itemdict.get(src.name);
    if item:
      item.setHighlighted(True);
      if origin is not self:
        self.scrollToItem(item);

  def _updateModelSelection (self,nsel,origin=None):
    """This is called when some other widget (origin!=self) changes the set of selected model sources""";
    if origin is self:
      return;
    self._updating_selection = True;
## this is very slow because of setSelected()
#    for item in self.iterator():
#     item.setSelected(item._src.selected);
    selection = QItemSelection();
    for item in self.iterator():
      if item._src.selected:
        selection.append(QItemSelectionRange(self.indexFromItem(item,0),self.indexFromItem(item,self.columnCount()-1)));
    self.selectionModel().select(selection,QItemSelectionModel.ClearAndSelect);
    self.changeGroupingVisibility(None,origin=origin);
    self._updating_selection = False;

  def _refreshSelectedItems (self,origin=None):
    busy = BusyIndicator();
    dprint(3,"refreshing selected items");
    for item in self.iterator():
      if item.isSelected():
        dprint(4,"resetting item",item._src.name);
        item.setSource(item._src);
    dprint(3,"refreshing selected items done");
    busy = None;

  def changeGroupingVisibility (self,group,origin=None):
    if origin is self:
      return;
    for item in self.iterator():
      # collect show_list values from groupings to which this source belongs (default group excepted)
      show = [ group.style.show_list for group in self.model.groupings if group is not self.model.defgroup and group.func(item._src) ];
      # if at least one group is showing explicitly, show
      # else if at least one group is hiding explicitly, hide
      # else use default setting
      if max(show) == PlotStyles.ShowAlways:
        visible = True;
      elif min(show) == PlotStyles.ShowNot:
        visible = False;
      else:
        visible = bool(self.model.defgroup.style.show_list);
      # set visibility accordingly
      item.setHidden(not visible);

  TagsWithOwnColumn = set(["Iapp","r"]);

class SkyModelTreeWidgetItem (QTreeWidgetItem):
  def __init__ (self,src,*args):
    QTreeWidgetItem.__init__(self,*args);
    self._src = src;
    # fonts
    stdfont = QApplication.font();
    boldfont = QFont(stdfont);
    boldfont.setBold(True);
    self._fonts = [ stdfont,boldfont ];
    # array of actual (i.e. numeric) column values
    self._values = [None]*NumColumns;
    # set text alignment
    for icol in range(NumColumns):
      self.setTextAlignment(icol,Qt.AlignLeft);
    self.setTextAlignment(ColumnR,Qt.AlignRight);
    self.setTextAlignment(ColumnType,Qt.AlignHCenter);
    # setup source
    self.setSource(src);

  def setHighlighted (self,highlighted=True):
    global _SLOW_QTREEWIDGETITEM;
    if not _SLOW_QTREEWIDGETITEM:
      brush = QApplication.palette().alternateBase() if highlighted else QApplication.palette().base();
      for col in range(self.columnCount()):
        self.setBackground(col,brush);
      self.setFont(0,self._fonts[1] if highlighted else self._fonts[0]);

  def setSource (self,src):
    # name
    dprint(3,"setSource 1",src.name);
    self.setColumn(ColumnName,src.name);
    # coordinates
    self.setColumn(ColumnRa,src.pos.ra,"%2dh%02dm%05.2fs"%src.pos.ra_hms());
    self.setColumn(ColumnDec,src.pos.dec,("%s%2d"+unichr(0xB0)+"%02d'%05.2f\"")%
        src.pos.dec_sdms());
    if hasattr(src,'r'):
      self.setColumn(ColumnR,src.r,"%.1f'"%(src.r*180*60/math.pi));
    # type
    self.setColumn(ColumnType,src.typecode);
    # flux
    if hasattr(src,'Iapp'):
      self.setColumn(ColumnIapp,src.Iapp,"%.3g"%src.Iapp);
    self.setColumn(ColumnI,src.flux.I,"%.3g"%src.flux.I);
    dprint(3,"setSource 2",src.name);
    # polarization
    if isinstance(src.flux,ModelClasses.Polarization):
      self.setColumn(ColumnQ,src.flux.Q,"%.2g"%src.flux.Q);
      self.setColumn(ColumnU,src.flux.U,"%.2g"%src.flux.U);
      self.setColumn(ColumnV,src.flux.V,"%.2g"%src.flux.V);
      if hasattr(src.flux,'rm'):
        self.setColumn(ColumnRm,src.flux.rm,"%.2f"%src.flux.rm);
    # spi
    if isinstance(src.spectrum,ModelClasses.SpectralIndex):
      self.setColumn(ColumnSpi,src.spectrum.spi,"%.2f"%getattr(src.spectrum,'spi',''));
    # shape
    shape = getattr(src,'shape',None);
    if isinstance(shape,ModelClasses.ModelItem):
      shapeval = [ val for attr,val in shape.getAttributes() ];
      shapestr = shape.strDesc(label=False);
      self.setColumn(ColumnShape,shapeval,shapestr);
    dprint(3,"setSource 3",src.name);
    # Tags. Tags are all extra attributes that do not have a dedicated column (i.e. not Iapp or r), and do not start
    # with "_" (which is reserved for internal attributes)
    
    ## the complexity below seems entirely unnecessary, since sorting the tag strings automatically puts "_" first,
    ## "-" second, and alphabet afterwards
    
    #truetags = [];
    #falsetags = [];
    #othertags = [];
    #for attr,val in src.getExtraAttributes():
      #if attr[0] != "_" and attr not in SkyModelTreeWidget.TagsWithOwnColumn:
        #if val is False:
          #falsetags.append("-"+attr);
        #elif val is True:
          #truetags.append("+"+attr);
        #else:
          #othertags.append("%s=%s"%(attr,str(val)));
    #for tags in truetags,falsetags,othertags:
      #tags.sort();
    #self.setColumn(ColumnTags,tags," ".join(truetags+falsetags+othertags));
    
    # so instead:
    tags = [ "+"+attr if val is True else "-"+attr if val is False else "%s=%s"%(attr,str(val))
      for attr,val in src.getExtraAttributes()
      if attr[0] != "_" and attr not in SkyModelTreeWidget.TagsWithOwnColumn ];
    tagstr = " ".join(sorted(tags));
    dprint(3,"setSource 4",src.name);
    self.setColumn(ColumnTags,tags,tagstr);
    dprint(3,"setSource 5",src.name);
    dprint(3,"setSource done",src.name);

  def setColumn (self,icol,value,text=None):
    """helper function to set the value of a column""";
    if text is None:
      text = str(value);
    self.setText(icol,text);
    self._values[icol] = value;

  def __lt__ (self,other):
    icol = self.treeWidget().sortColumn();
    if isinstance(other,SkyModelTreeWidgetItem):
      return self._values[icol] < other._values[icol];
    else:
      return self.text(icol) < other.text(icol);

  def __ge__ (self,other):
    return other < self;


class ModelGroupsTable (QWidget):
  EditableAttrs = [ attr for attr in PlotStyles.StyleAttributes if attr in PlotStyles.StyleAttributeOptions ];
  ColList = 3;
  ColPlot = 4;
  ColApply = 5;
  AttrByCol = dict([(i+6,attr) for i,attr in enumerate(EditableAttrs)]);

  def __init__ (self,parent,*args):
    QWidget.__init__(self,parent,*args);
    self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);
    lo = QVBoxLayout(self);
    lo.setContentsMargins(0,0,0,0);
    lo1 = QHBoxLayout();
    lo.addLayout(lo1);
    lo1.setContentsMargins(0,0,0,0);
    lbl = QLabel(QString("<nobr><b>Source groupings:</b></nobr>"),self);
    lo1.addWidget(lbl,0);
    lo1.addStretch(1);
    # add show/hide button
    self._showattrbtn = QPushButton(self);
    self._showattrbtn.setMinimumWidth(256);
    lo1.addWidget(self._showattrbtn,0);
    lo1.addStretch();
    QObject.connect(self._showattrbtn,SIGNAL("clicked()"),self._togglePlotControlsVisibility);
    # add table
    self.table  = QTableWidget(self);
    lo.addWidget(self.table);
    QObject.connect(self.table,SIGNAL("cellChanged(int,int)"),self._valueChanged);
    self.table.setSelectionMode(QTableWidget.NoSelection);
    # setup basic columns
    self.table.setColumnCount(6+len(self.EditableAttrs));
    for i,label in enumerate(("grouping","total","selection","","","")):
      self.table.setHorizontalHeaderItem(i,QTableWidgetItem(label));
    self.table.horizontalHeader().setSectionHidden(self.ColApply,True);
    # setup columns for editable grouping attributes
    for i,attr in self.AttrByCol.iteritems():
      self.table.setHorizontalHeaderItem(i,QTableWidgetItem(PlotStyles.StyleAttributeLabels[attr]));
      self.table.horizontalHeader().setSectionHidden(i,True);
    self.table.verticalHeader().hide();
    # other internal init
    self._attrs_shown = False;
    self._togglePlotControlsVisibility();
    self.model = None;
    self._setting_model = False;
    self._currier = PersistentCurrier();
    # row of 'selected' grouping
    self._irow_selgroup = 0;

  def clear (self):
    self.table.setRowCount(0);
    self.model = None;

  # setup mappings from the group.show_plot attribute to check state
  ShowAttrToCheckState = {  PlotStyles.ShowNot:Qt.Unchecked,
                                            PlotStyles.ShowDefault:Qt.PartiallyChecked,
                                            PlotStyles.ShowAlways:Qt.Checked };
  CheckStateToShowAttr = dict([(val,key) for key,val in ShowAttrToCheckState.iteritems ()]);

  def _makeCheckItem (self,name,group,attr):
    item = QTableWidgetItem(name);
    if group is self.model.defgroup:
      item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);
      item.setCheckState(Qt.Checked if getattr(group.style,attr) else Qt.Unchecked);
    else:
      item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsTristate);
      item.setCheckState(self.ShowAttrToCheckState[getattr(group.style,attr)]);
    return item;

  def _updateModel (self,what=SkyModel.UpdateAll,origin=None):
    if origin is self or not what&(SkyModel.UpdateTags|SkyModel.UpdateGroupStyle):
      return;
    model = self.model;
    self._setting_model= True;  # to ignore cellChanged() signals (in valueChanged())
    # _item_cb is a dict (with row,col keys) containing the widgets (CheckBoxes ComboBoxes) per each cell
    self._item_cb = {};
    # lists of "list" and "plot" checkboxes per each grouping (excepting the default grouping); each entry is an (row,col,item) tuple.
    # used as argument to self._showControls()
    self._list_controls = [];
    self._plot_controls = [];
    # list of selection callbacks (to which signals are connected)
    self._callbacks = [];
    # set requisite number of rows,and start filling
    self.table.setRowCount(len(model.groupings));
    for irow,group in enumerate(model.groupings):
      self.table.setItem(irow,0,QTableWidgetItem(group.name));
      if group is model.selgroup:
        self._irow_selgroup = irow;
      # total # source in group: skip for "current"
      if group is not model.curgroup:
        self.table.setItem(irow,1,QTableWidgetItem(str(group.total)));
      # selection controls: skip for current and selection
      if group not in (model.curgroup,model.selgroup):
        btns = QWidget();
        lo = QHBoxLayout(btns);
        lo.setContentsMargins(0,0,0,0);
        lo.setSpacing(0);
        # make selector buttons (depending on which group we're in)
        if group is model.defgroup:
          Buttons = (
            ("+",lambda src,grp=group:True,"select all sources"),
            ("-",lambda src,grp=group:False,"unselect all sources") );
        else:
          Buttons = (
            ("=",lambda src,grp=group:grp.func(src),"select only this grouping"),
            ("+",lambda src,grp=group:src.selected or grp.func(src),"add grouping to selection"),
            ("-",lambda src,grp=group:src.selected and not grp.func(src),"remove grouping from selection"),
            ("&&",lambda src,grp=group:src.selected and grp.func(src),"intersect selection with grouping"));
        lo.addStretch(1);
        for label,predicate,tooltip in Buttons:
          btn = QToolButton(btns);
          btn.setText(label);
          btn.setMinimumWidth(24);
          btn.setMaximumWidth(24);
          btn.setToolTip(tooltip);
          lo.addWidget(btn);
          # add callback
          QObject.connect(btn,SIGNAL("clicked()"),self._currier.curry(self.selectSources,predicate));
        lo.addStretch(1);
        self.table.setCellWidget(irow,2,btns);
      # "list" checkbox (not for current and selected groupings: these are always listed)
      if group not in (model.curgroup,model.selgroup):
        item = self._makeCheckItem("list",group,"show_list");
        self.table.setItem(irow,self.ColList,item);
        item.setToolTip("""<P>If checked, sources in this grouping will be listed in the source table. If un-checked, sources will be
            excluded from the table. If partially checked, then the default list/no list setting of "all sources" will be in effect.
            </P>""");
      # "plot" checkbox (not for the current grouping, since that's always plotted)
      if group is not model.curgroup:
        item = self._makeCheckItem("plot",group,"show_plot");
        self.table.setItem(irow,self.ColPlot,item);
        item.setToolTip("""<P>If checked, sources in this grouping will be included in the plot. If un-checked, sources will be
            excluded from the plot. If partially checked, then the default plot/no plot setting of "all sources" will be in effect.
            </P>""");
    # "apply" checkbox
      if group is not model.defgroup:
        item = QTableWidgetItem("custom:");
        item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);
        item.setCheckState(Qt.Checked if group.style.apply else Qt.Unchecked);
        self.table.setItem(irow,self.ColApply,item);
        item.setToolTip("""<P>If "custom" is checked, sources within this grouping will have their own custom plot style, as determined by the controls to the right.</P>""");
      else:
        item = QTableWidgetItem("default:");
        item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);
        item.setToolTip("""<P>This is the default plot style used for all sources for which a custom grouping style is not selected.</P>""");
        self.table.setItem(irow,self.ColApply,item);
      # attribute comboboxes
      for icol,attr in self.AttrByCol.iteritems():
        # get list of options for this style attribute. If dealing with first grouping (i==0), which is
        # the "all sources" grouping, then remove the "default" option (which is always first in the list)
        options = PlotStyles.StyleAttributeOptions[attr];
        if irow == 0:
          options = options[1:];
        # make combobox
        cb = QComboBox();
        cb.addItems(map(str,options));
        # the "label" option is also editable
        if attr == "label":
          cb.setEditable(True);
        try:
          index = options.index(getattr(group.style,attr));
          cb.setCurrentIndex(index);
        except ValueError:
          cb.setEditText(str(getattr(group.style,attr)));
        slot = self._currier.xcurry(self._valueChanged,(irow,icol));
        QObject.connect(cb,SIGNAL("activated(int)"),slot);
        QObject.connect(cb,SIGNAL("editTextChanged(const QString &)"),slot);
        cb.setEnabled(group is model.defgroup or group.style.apply);
        self.table.setCellWidget(irow,icol,cb);
        label = attr;
        if irow:
          cb.setToolTip("""<P>This is the %s used to plot sources in this grouping (if the "custom" checkbox is checked.)<P>"""%label);
        else:
          cb.setToolTip("<P>This is the default %s used for all sources for which a custom style is not specified below.<P>"%label);
    self.table.resizeColumnsToContents();
    # re-enable processing of cellChanged() signals
    self._setting_model= False;

  def setModel (self,model):
    self.model = model;
    self.model.connect("updated",self._updateModel);
    self.model.connect("selected",self.updateModelSelection);
    self._updateModel(SkyModel.UpdateAll);

  def _valueChanged (self,row,col):
    """Called when a cell has been edited""";
    if self._setting_model:
      return;
    group = self.model.groupings[row];
    item = self.table.item(row,col);
    if col == self.ColList:
      if group is not self.model.defgroup:
        # tri-state items go from unchecked to checked when user clicks them. Make them partially checked instead.
        if group.style.show_list == PlotStyles.ShowNot and item.checkState() == Qt.Checked:
          item.setCheckState(Qt.PartiallyChecked);
      group.style.show_list = self.CheckStateToShowAttr[item.checkState()];
      self.model.emitChangeGroupingVisibility(group,origin=self);
      return;
    elif col == self.ColPlot:
      if group is not self.model.defgroup:
        # tri-state items go from unchecked to checked by default. Make them partially checked instead.
        if group.style.show_plot == PlotStyles.ShowNot and item.checkState() == Qt.Checked:
          item.setCheckState(Qt.PartiallyChecked);
      group.style.show_plot = self.CheckStateToShowAttr[item.checkState()];
    elif col == self.ColApply:
      group.style.apply = item.checkState() != Qt.Unchecked;
      # enable/disable editable cells
      for j in self.AttrByCol.keys():
        item1 = self.table.item(row,j);
        if item1:
          fl = item1.flags()&~Qt.ItemIsEnabled;
          if group.style.apply:
            fl |= Qt.ItemIsEnabled;
          item1.setFlags(fl);
        cw = self.table.cellWidget(row,j);
        cw and cw.setEnabled(group.style.apply);
    elif col in self.AttrByCol:
      cb = self.table.cellWidget(row,col);
      txt = str(cb.currentText());
      attr = self.AttrByCol[col];
      if txt == "default":
        setattr(group.style,attr,PlotStyles.DefaultValue);
      else:
        setattr(group.style,attr,PlotStyles.StyleAttributeTypes.get(attr,str)(txt));
    # all other columns: return so we don't emit a signal
    else:
      return;
    # in all cases emit a signal
    self.model.emitChangeGroupingStyle(group,origin=self);

  def selectSources (self,predicate):
    """Selects sources according to predicate(src)"""
    busy = BusyIndicator();
    for src in self.model.sources:
      src.selected = predicate(src);
    self.model.emitSelection(origin=self);
    busy = None;

  def updateModelSelection (self,nsel,origin=None):
    """This is called when some other widget changes the set of selected model sources""";
    self.table.clearSelection();
    if self.model:
      self.table.item(self._irow_selgroup,1).setText(str(nsel));

  def _togglePlotControlsVisibility (self):
    if self._attrs_shown:
      self._attrs_shown = False;
      self.table.hideColumn(self.ColApply);
      for col in self.AttrByCol.iterkeys():
        self.table.hideColumn(col);
      self._showattrbtn.setText("Show plot styles >>");
    else:
      self._attrs_shown = True;
      self.table.showColumn(self.ColApply);
      for col in self.AttrByCol.iterkeys():
        self.table.showColumn(col);
      self._showattrbtn.setText("<< Hide plot styles");


