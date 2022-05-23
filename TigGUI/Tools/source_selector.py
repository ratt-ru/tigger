# Copyright (C) 2002-2022
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
import numpy as np
import operator

from PyQt5.QtWidgets import *
import traceback

from PyQt5.Qt import QObject, QHBoxLayout, QComboBox, QLabel, QLineEdit, QDialog, QVBoxLayout, Qt, QErrorMessage,\
    QSlider

import TigGUI.kitties.utils
from TigGUI.kitties.utils import curry
from TigGUI.kitties.widgets import BusyIndicator

QString = str

_verbosity = TigGUI.kitties.utils.verbosity(name="source_selector")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf

# list of standard tags to be sorted by
StandardTags = ["ra", "dec", "r", "Iapp", "I", "Q", "U", "V", "rm", "spi"]

# dict of accessors for nested source attributes
TagAccessors = dict()
for tag in "ra", "dec":
    TagAccessors[tag] = lambda src, t=tag: getattr(src.pos, t)
for tag in list("IQUV") + ["rm"]:
    TagAccessors[tag] = lambda src, t=tag: getattr(src.flux, t, 0.0)
for tag in ["spi"]:
    TagAccessors[tag] = lambda src, t=tag: getattr(src.spectrum, t, 0.0)

# tags for which sorting is not available
NonSortingTags = set(["name", "typecode"])


class SourceSelectorDialog(QDialog):
    def __init__(self, parent, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        self.setModal(False)
        self.setWindowTitle("Select sources by...")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(10, 10, 10, 10)
        lo.setSpacing(5)
        # select by
        lo1 = QHBoxLayout()
        lo.addLayout(lo1)
        lo1.setContentsMargins(0, 0, 0, 0)
        #    lab = QLabel("Select:")
        #   lo1.addWidget(lab)
        self.wselby = QComboBox(self)
        lo1.addWidget(self.wselby, 0)
        self.wselby.activated[str].connect(self._setup_selection_by)
        # under/over
        self.wgele = QComboBox(self)
        lo1.addWidget(self.wgele, 0)
        self.wgele.addItems([">", ">=", "<=", "<", "sum<=", "sum>", "=="])
        self.wgele.activated[str].connect(self._select_threshold)
        # threshold value
        self.wthreshold = QLineEdit(self)
        self.wthreshold.editingFinished.connect(self._select_threshold)
        lo1.addWidget(self.wthreshold, 1)
        # min and max label
        self.wminmax = QLabel(self)
        lo.addWidget(self.wminmax)
        # selection slider
        lo1 = QHBoxLayout()
        lo.addLayout(lo1)
        self.wpercent = QSlider(self)
        self.wpercent.setTracking(False)
        self.wpercent.valueChanged[int].connect(self._select_percentile)
        self.wpercent.sliderMoved[int].connect(self._select_percentile_threshold)
        self.wpercent.setRange(0, 100)
        self.wpercent.setOrientation(Qt.Horizontal)
        lo1.addWidget(self.wpercent)
        self.wpercent_lbl = QLabel("0%", self)
        self.wpercent_lbl.setMinimumWidth(64)
        lo1.addWidget(self.wpercent_lbl)
        #    # hide button
        #    lo.addSpacing(10)
        #    lo2 = QHBoxLayout()
        #    lo.addLayout(lo2)
        #    lo2.setContentsMargins(0,0,0,0)
        #    hidebtn = QPushButton("Close",self)
        #    hidebtn.setMinimumWidth(128)
        #    QObject.connect(hidebtn,pyqtSignal("clicked()"),self.hide)
        #    lo2.addStretch(1)
        #    lo2.addWidget(hidebtn)
        #    lo2.addStretch(1)
        #    self.setMinimumWidth(384)
        self._in_select_threshold = False
        self._sort_index = None
        self.qerrmsg = QErrorMessage(self)

    def resetModel(self):
        """Resets dialog based on current model."""
        if not self.model:
            return
        # getset of model tags, and remove the non-sorting tags
        alltags = set(self.model.tagnames)
        alltags -= NonSortingTags
        # make list of tags from StandardTags that are present in model
        self.sorttags = [tag for tag in StandardTags if tag in alltags or tag in TagAccessors]
        # append model tags that were not in StandardTags
        self.sorttags += list(alltags - set(self.sorttags))
        # set selector
        self.wselby.clear()
        self.wselby.addItems(self.sorttags)
        for tag in "Iapp", "I":
            if tag in self.sorttags:
                self.wselby.setCurrentIndex(self.sorttags.index(tag))
                break
        self._setup_selection_by(self.wselby.currentText())

    def _reset_percentile(self):
        self.wthreshold.setText("")
        self.wpercent.setValue(50)
        self.wpercent_lbl.setText("--%")

    def _setup_selection_by(self, tag):
        tag = str(tag)  # may be QString
        # clear threshold value and percentiles
        self._reset_percentile()
        # get min/max values, and sort indices
        # _sort_index will be an array of (value,src,cumsum) tuples, sorted by tag value (high to low),
        # where src is the source, and cumsum is the sum of all values in the list from 0 up to and including the current one
        self._sort_index = []
        minval = maxval = value = None
        for isrc, src in enumerate(self.model.sources):
            try:
                if hasattr(src, tag):
                    # test if item can be cast to float
                    try:
                        float(getattr(src, tag))
                    except:
                        continue
                    else:
                        value = float(getattr(src, tag))

                elif tag in TagAccessors:
                    value = float(TagAccessors[tag](src))
                else: # not existant for this source (maybe a tag or something??)
                    value = np.nan
            # skip source if failed to access this tag as a float
            except:
                traceback.print_exc()
                continue
            if value is not None:
                self._sort_index.append([value if not np.isnan(value) else -np.inf, src, 0.])
                minval = min(minval, value if not np.isnan(value) else np.inf) if minval is not None else value
                maxval = max(maxval, value if not np.isnan(value) else -np.inf) if maxval is not None else value
        # add label
        if minval is None:
            self._range = None
            self.wminmax.setText("<font color=red>'%s' is not a numeric attribute</font>" % tag)
            for w in self.wgele, self.wthreshold, self.wpercent, self.wpercent_lbl:
                w.setEnabled(False)
        else:
            self._range = (minval, maxval)
            self.wminmax.setText("min: %g max: %g" % self._range)
            for w in self.wgele, self.wthreshold, self.wpercent, self.wpercent_lbl:
                w.setEnabled(True)
        # sort index by descending values
        self._sort_index.sort(reverse=True, key=operator.itemgetter(0))
        # generate cumulative sums
        cumsum = 0.
        for entry in self._sort_index:
            if not np.isneginf(entry[0]):
                cumsum += entry[0]
            entry[2] = cumsum

    # Maps comparison operators to callables. Used in _select_threshold.
    # Each callable takes two arguments: e is a tuple of (value,src,cumsum) (see _sort_index above), and x is a threshold
    # Second argument is a flag: if False, selection is inverted w.r.t. operator
    Operators = {
        "<": ((lambda e, x: e[0] >= x), False),
        "<=": ((lambda e, x: e[0] > x), False),
        ">": ((lambda e, x: e[0] > x), True),
        ">=": ((lambda e, x: e[0] >= x), True),
        "sum<=": ((lambda e, x: e[2] <= x), True),
        "sum>": ((lambda e, x: e[2] <= x), False),
        "==": ((lambda e, x: np.abs(e[0] - x) < 1.0e-8), True),
    }

    def _select_threshold(self, *dum):
        dprint(1, "select_threshold", dum)
        self._in_select_threshold = True
        busy = BusyIndicator()
        try:
            # get threshold, ignore if not set
            threshold = str(self.wthreshold.text())
            if not threshold:
                self._reset_percentile()
                return
            # try to parse threshold, ignore if invalid
            try:
                threshold = float(threshold)
            except:
                self._reset_percentile()
                return
            # get comparison operator
            op, select = self.Operators[str(self.wgele.currentText())]
            # apply to initial segment (that matches operator)
            for num, entry in enumerate(self._sort_index):
                if not op(entry, threshold):
                    break
                entry[1].selected = select
            else:
                num = len(self._sort_index)
            # apply to remaining segment
            for val, src, cumsum in self._sort_index[num:]:
                src.selected = not select
            # set percentile
            percent = round(float(num * 100) / len(self._sort_index))
            if not select:
                percent = 100 - percent
            self.wpercent.setValue(percent)
            self.wpercent_lbl.setText("%3d%%" % percent)
            # emit signal
            self.model.emitSelection(self)
        finally:
            self._in_select_threshold = False
            busy.reset_cursor()

    def _select_percentile(self, percent):
        self._select_percentile_threshold(percent, do_select=True)

    def _select_percentile_threshold(self, percent, do_select=False):
        # ignore if no sort index set up, or if _select_threshold() is being called
        if self._sort_index is None or self._in_select_threshold:
            return
        dprint(1, "select_precentile_threshold", percent)
        busy = BusyIndicator()
        # number of objects to select
        nsrc = len(self._sort_index)
        nsel = int(math.ceil(nsrc * float(percent) / 100))
        # get comparison operator
        opstr = str(self.wgele.currentText())
        op, select = self.Operators[opstr]
        # select head or tail of list, depending on direction of operator
        if select:
            thr = self._sort_index[min(nsel, nsrc - 1)]
            slc1 = slice(0, nsel)
            slc2 = slice(nsel, None)
        else:
            thr = self._sort_index[-min(nsel + 1, nsrc)]
            slc1 = slice(nsrc - nsel, None)
            slc2 = slice(0, nsrc - nsel)
        if do_select:
            for val, src, cumsum in self._sort_index[slc1]:
                src.selected = True
            for val, src, cumsum in self._sort_index[slc2]:
                src.selected = False
            self.model.emitSelection(self)
        self.wpercent_lbl.setText("%3d%%" % percent)
        self.wthreshold.setText("%g" % (thr[2] if opstr.startswith("sum") else thr[0]))
        busy.reset_cursor()
        return nsel

    def setModel(self, model):
        """Sets the current model. If dialog is visible, applies the changes"""
        self.model = model
        if self.isVisible():
            self.resetModel()
        if not model:
            self.hide()

    def show(self):
        """Shows dialog, resetting the model if it was invisible."""
        if not self.isVisible():
            self.resetModel()
        QDialog.show(self)


def show_source_selector(mainwin, model):
    dialog = getattr(mainwin, '_source_selector_dialog', None)
    if not dialog:
        dialog = mainwin._source_selector_dialog = SourceSelectorDialog(mainwin)
        mainwin.modelChanged.connect(dialog.setModel)
        mainwin.closing.connect(dialog.close)
    dialog.setModel(model)
    # show dialog
    dialog.show()
    dialog.raise_()

# from TigGUI.Tools import registerTool
# registerTool("Source selector...",show_source_selector)
