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

import traceback
import re
import os
from PyQt5.Qt import  QValidator, QWidget, QHBoxLayout, QFileDialog, QComboBox, QLabel, \
    QLineEdit, QDialog, QIntValidator, QDoubleValidator, QToolButton, QListWidget, QVBoxLayout, \
    QPushButton, QMessageBox
from PyQt5.QtGui import QMouseEvent, QFont
from PyQt5.QtWidgets import QDockWidget, QStyle, QSizePolicy, QToolTip, QApplication
from PyQt5.Qwt import QwtPlotCurve, QwtPlotMarker
from PyQt5.QtCore import pyqtSignal, Qt, QEvent, QSize, QTimer

from TigGUI.init import pixmaps

QStringList = list


class TiggerPlotCurve(QwtPlotCurve):
    """Wrapper around QwtPlotCurve to make it compatible with numpy float types"""

    def setData(self, x, y):
        return QwtPlotCurve.setSamples(self, list(map(float, x)), list(map(float, y)))

    def setDataXfy(self, x, y):
        return QwtPlotCurve.setSamples(self, list(map(float, y)), list(map(float, x)))


class TiggerPlotMarker(QwtPlotMarker):
    """Wrapper around QwtPlotCurve to make it compatible with numpy float types"""

    def setValue(self, x, y):
        return QwtPlotMarker.setValue(self, float(x), float(y))


class FloatValidator(QValidator):
    """QLineEdit validator for float items in standard or scientific notation"""
    re_intermediate = re.compile("^-?([0-9]*)\.?([0-9]*)([eE]([+-])?[0-9]*)?$")

    def validate(self, _input, _pos):
        _input = str(_input)
        try:
            x = float(_input)
            return QValidator.Acceptable, _input, _pos
        except:
            pass
        if not _input or self.re_intermediate.match(_input):
            return QValidator.Intermediate, _input, _pos
        # return QValidator.Invalid, pos  # old line
        return QValidator.Acceptable, _input, _pos


class ValueTypeEditor(QWidget):
    ValueTypes = (bool, int, float, complex, str)

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(5)
        # type selector
        self.wtypesel = QComboBox(self)
        for i, tp in enumerate(self.ValueTypes):
            self.wtypesel.addItem(tp.__name__)
        self.wtypesel.activated[int].connect(self._selectTypeNum)
        typesel_lab = QLabel("&Type:", self)
        typesel_lab.setBuddy(self.wtypesel)
        lo.addWidget(typesel_lab, 0)
        lo.addWidget(self.wtypesel, 0)
        self.wvalue = QLineEdit(self)
        self.wvalue_lab = QLabel("&Value:", self)
        self.wvalue_lab.setBuddy(self.wvalue)
        self.wbool = QComboBox(self)
        self.wbool.addItems(["false", "true"])
        self.wbool.setCurrentIndex(1)
        lo.addWidget(self.wvalue_lab, 0)
        lo.addWidget(self.wvalue, 1)
        lo.addWidget(self.wbool, 1)
        self.wvalue.hide()
        # make input validators
        self._validators = {int: QIntValidator(self), float: QDoubleValidator(self)}
        # select bool type initially
        self._selectTypeNum(0)

    def _selectTypeNum(self, index):
        tp = self.ValueTypes[index]
        self.wbool.setVisible(tp is bool)
        self.wvalue.setVisible(tp is not bool)
        self.wvalue_lab.setBuddy(self.wbool if tp is bool else self.wvalue)
        self.wvalue.setValidator(self._validators.get(tp, None))

    def setValue(self, value):
        """Sets current value"""
        for i, tp in enumerate(self.ValueTypes):
            if isinstance(value, tp):
                self.wtypesel.setCurrentIndex(i)
                self._selectTypeNum(i)
                if tp is bool:
                    self.wbool.setCurrentIndex(1 if value else 0)
                else:
                    self.wvalue.setText(str(value))
                return
        # unknown value: set bool
        self.setValue(True)

    def getValue(self):
        """Returns current value, or None if no legal value is set"""
        tp = self.ValueTypes[self.wtypesel.currentIndex()]
        if tp is bool:
            return bool(self.wbool.currentIndex())
        else:
            try:
                return tp(self.wvalue.text())
            except:
                print("Error converting input to type ", tp.__name__)
                traceback.print_exc()
                return None


class FileSelector(QWidget):
    """A FileSelector is a one-line widget for selecting a file."""
    valid = pyqtSignal()
    filenameSelected = pyqtSignal()

    def __init__(self, parent, label, filename=None, dialog_label=None, file_types=None, default_suffix=None,
                 file_mode=QFileDialog.AnyFile):
        QWidget.__init__(self, parent)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(5)
        # label
        lab = QLabel(label, self)
        lo.addWidget(lab, 0)
        # text field
        self.wfname = QLineEdit(self)
        self.wfname.setReadOnly(True)
        self.setFilename(filename)
        lo.addWidget(self.wfname, 1)
        # selector
        wsel = QToolButton(self)
        wsel.setText("Choose...")
        wsel.clicked.connect(self._chooseFile)
        lo.addWidget(wsel, 0)
        # other init
        self._file_dialog = None
        self._dialog_label = dialog_label or label
        self._file_types = file_types or "All files (*)"
        self._file_mode = file_mode
        self._default_suffix = default_suffix
        self._dir = None

    def _chooseFile(self):
        if self._file_dialog is None:
            dialog = self._file_dialog = QFileDialog(self, self._dialog_label, ".", self._file_types)
            if self._default_suffix:
                dialog.setDefaultSuffix(self._default_suffix)
            dialog.setFileMode(self._file_mode)
            dialog.setModal(True)
            if self._dir is not None:
                dialog.setDirectory(self._dir)
            dialog.filesSelected['QStringList'].connect(self.setFilename)
        return self._file_dialog.exec_()

    def setFilename(self, filename):
        if isinstance(filename, QStringList):
            filename = filename[0]
        filename = (filename and str(filename)) or ''
        self.wfname.setText(filename)
        self.valid.emit(bool(filename))
        self.filenameSelected.emit(filename)

    def setDirectory(self, directory):
        self._dir = directory
        if self._file_dialog is not None:
            self._file_dialog.setDirectory(directory)

    def filename(self):
        return str(self.wfname.text())

    def isValid(self):
        return bool(self.filename())


class AddTagDialog(QDialog):
    def __init__(self, parent, modal=True, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        self.setModal(modal)
        self.setWindowTitle("Add Tag")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(10, 10, 10, 10)
        lo.setSpacing(5)
        # tag selector
        lo1 = QHBoxLayout()
        lo.addLayout(lo1)
        lo1.setSpacing(5)
        self.wtagsel = QComboBox(self)
        self.wtagsel.setEditable(True)
        wtagsel_lbl = QLabel("&Tag:", self)
        wtagsel_lbl.setBuddy(self.wtagsel)
        lo1.addWidget(wtagsel_lbl, 0)
        lo1.addWidget(self.wtagsel, 1)
        self.wtagsel.activated[int].connect(self._check_tag)
        self.wtagsel.editTextChanged['QString'].connect(self._check_tag_text)
        # value editor
        self.valedit = ValueTypeEditor(self)
        lo.addWidget(self.valedit)
        # buttons
        lo.addSpacing(10)
        lo2 = QHBoxLayout()
        lo.addLayout(lo2)
        lo2.setContentsMargins(0, 0, 0, 0)
        lo2.setContentsMargins(5, 5, 5, 5)
        self.wokbtn = QPushButton("OK", self)
        self.wokbtn.setMinimumWidth(128)
        self.wokbtn.clicked.connect(self.accept)
        self.wokbtn.setEnabled(False)
        cancelbtn = QPushButton("Cancel", self)
        cancelbtn.setMinimumWidth(128)
        cancelbtn.clicked.connect(self.reject)
        lo2.addWidget(self.wokbtn)
        lo2.addStretch(1)
        lo2.addWidget(cancelbtn)
        self.setMinimumWidth(384)

    def setTags(self, tagnames):
        self.wtagsel.clear()
        self.wtagsel.addItems(list(tagnames))
        self.wtagsel.addItem("")
        self.wtagsel.setCurrentIndex(len(tagnames))

    def setValue(self, value):
        self.valedit.setValue(value)

    def _check_tag(self, tag):
        self.wokbtn.setEnabled(True)

    def _check_tag_text(self, text):
        self.wokbtn.setEnabled(bool(str(text) != ""))

    def accept(self):
        """When dialog is accepted with a default (bool) tag type,
        check if the user hasn't entered a name=value entry in the tag name field.
        This is a common mistake, and should be treated as a shortcut for setting string tags."""
        if isinstance(self.valedit.getValue(), bool):
            tagval = str(self.wtagsel.currentText()).split("=", 1)
            if len(tagval) > 1:
                #        print tagval
                if QMessageBox.warning(self,
                                       "Set a string tag instead?", """<P>You have included an "=" sign in the tag name.
            Perhaps you actually mean to set tag "%s" to the string value "%s"?</P>""" % tuple(tagval),
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.No:
                    return
                self.wtagsel.setEditText(tagval[0])
                self.valedit.setValue(tagval[1])
        return QDialog.accept(self)

    def getTag(self):
        return str(self.wtagsel.currentText()), self.valedit.getValue()


class SelectTagsDialog(QDialog):
    def __init__(self, parent, modal=True, flags=Qt.WindowFlags(), caption="Select Tags", ok_button="Select"):
        QDialog.__init__(self, parent, flags)
        self.setModal(modal)
        self.setWindowTitle(caption)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(10, 10, 10, 10)
        lo.setSpacing(5)
        # tag selector
        self.wtagsel = QListWidget(self)
        lo.addWidget(self.wtagsel)
        #    self.wtagsel.setColumnMode(QListBox.FitToWidth)
        self.wtagsel.setSelectionMode(QListWidget.MultiSelection)
        self.wtagsel.itemSelectionChanged.connect(self._check_tag)
        # buttons
        lo.addSpacing(10)
        lo2 = QHBoxLayout()
        lo.addLayout(lo2)
        lo2.setContentsMargins(0, 0, 0, 0)
        lo2.setContentsMargins(5, 5, 5, 5)
        self.wokbtn = QPushButton(ok_button, self)
        self.wokbtn.setMinimumWidth(128)
        self.wokbtn.clicked.connect(self.accept)
        self.wokbtn.setEnabled(False)
        cancelbtn = QPushButton("Cancel", self)
        cancelbtn.setMinimumWidth(128)
        cancelbtn.clicked.connect(self.reject)
        lo2.addWidget(self.wokbtn)
        lo2.addStretch(1)
        lo2.addWidget(cancelbtn)
        self.setMinimumWidth(384)
        self._tagnames = []

    def setTags(self, tagnames):
        self._tagnames = tagnames
        self.wtagsel.clear()
        self.wtagsel.insertItems(0, list(tagnames))

    def _check_tag(self):
        for i in range(len(self._tagnames)):
            if self.wtagsel.item(i).isSelected():
                self.wokbtn.setEnabled(True)
                return
        else:
            self.wokbtn.setEnabled(False)

    def getSelectedTags(self):
        return [tag for i, tag in enumerate(self._tagnames) if self.wtagsel.item(i).isSelected()]


class TDockWidget(QDockWidget):

    def __init__(self, title="", parent=None, flags=Qt.WindowFlags(), bind_widget=None, close_slot=None, toggle_slot=None):
        QDockWidget.__init__(self, title, parent, flags)
        self.installEventFilter(self)
        self.main_win = parent
        # default stlyesheets for title bars
        self.title_stylesheet = "QWidget {background: rgb(68,68,68);}"
        self.button_style = "QPushButton:hover:!pressed {background: grey;}"
        from TigGUI.Images.ControlDialog import ImageControlDialog
        from TigGUI.Plot.SkyModelPlot import ToolDialog
        from TigGUI.Plot.SkyModelPlot import LiveImageZoom
        if bind_widget is not None:
            self.bind_widget = bind_widget
        if bind_widget is not None:
            if isinstance(bind_widget, ToolDialog):
                self.tdock_style = "ToolDialog {border: 1.5px solid rgb(68,68,68);}"
            elif isinstance(bind_widget, ImageControlDialog):
                self.tdock_style = "ImageControlDialog {border: 1.5px solid rgb(68,68,68);}"
        # set default sizes for QDockWidgets
        self.btn_w = 28
        self.btn_h = 28
        self.icon_size = QSize(20, 20)
        self.font_size = 8
        # setup custom title bar for profiles dockable
        self.dock_title_bar = QWidget()
        self.dock_title_bar.setContentsMargins(0, 0, 0, 0)
        self.dock_title_bar.setStyleSheet(self.title_stylesheet)
        self.dock_title_bar.setBaseSize(0, 0)
        self.dock_title_layout = QHBoxLayout()
        self.dock_title_layout.setContentsMargins(0, 0, 0, 0)
        self.dock_title_layout.setSpacing(0)
        self.dock_title_bar.setLayout(self.dock_title_layout)
        # custom close button
        self.close_button = QPushButton()
        self.close_button.setStyleSheet(self.button_style)
        self.close_button.setMaximumWidth(self.btn_w)
        self.close_button.setMaximumHeight(self.btn_h)
        self.close_button.setContentsMargins(0, 0, 0, 0)
        self.close_button.setBaseSize(0, 0)
        self.close_icon = self.dock_title_bar.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        self.close_button.setIcon(self.close_icon)
        self.close_button.setToolTip("Close")
        # custom toggle button
        self.toggle_button = QPushButton()
        self.toggle_button.setStyleSheet(self.button_style)
        self.toggle_button.setMaximumWidth(self.btn_w)
        self.toggle_button.setMaximumHeight(self.btn_h)
        self.toggle_button.setContentsMargins(0, 0, 0, 0)
        self.toggle_button.setBaseSize(0, 0)
        self.toggle_icon = self.dock_title_bar.style().standardIcon(QStyle.SP_TitleBarShadeButton)
        self.toggle_button.setIcon(self.toggle_icon)
        self.toggle_button.setToolTip("Dock/float widget")
        # tigger logo
        self.image0 = pixmaps.tigger_logo.pm()
        self.title_icon = QLabel()
        self.title_icon.setContentsMargins(0, 0, 0, 0)
        self.title_icon.setBaseSize(0, 0)
        self.title_icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.title_icon.setScaledContents(True)
        self.title_icon.setPixmap(self.image0)
        self.title_icon.setAlignment(Qt.AlignCenter)
        self.title_icon.setMaximumSize(self.icon_size)
        # set dock widget title
        self.title_font = QFont()
        self.title_font.setBold(True)
        self.title_font.setPointSize(self.font_size)
        if bind_widget is not None:
            if isinstance(bind_widget, ImageControlDialog):
                self.dock_title = QLabel(f"{title}: Control Dialog")
            else:
                self.dock_title = QLabel(title)
        self.dock_title.setFont(self.title_font)
        self.dock_title.setAlignment(Qt.AlignCenter)
        self.dock_title.setContentsMargins(0, 0, 0, 0)
        self.dock_title.setBaseSize(0, 0)
        self.dock_title.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        # add dock widget title items to layout
        self.dock_title_layout.addWidget(self.title_icon)
        self.dock_title_layout.addWidget(self.dock_title)
        self.dock_title_layout.addWidget(self.toggle_button)
        self.dock_title_layout.addWidget(self.close_button)
        # set up profiles as dockable
        self.setStyleSheet(self.tdock_style)
        self.setWidget(bind_widget)
        self.setFeatures(QDockWidget.AllDockWidgetFeatures)
        if bind_widget is not None:
            if isinstance(bind_widget, ToolDialog):
                self.setAllowedAreas(Qt.AllDockWidgetAreas)
            elif isinstance(bind_widget, ImageControlDialog):
                self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.setTitleBarWidget(self.dock_title_bar)
        self.setFloating(False)
        # get current sizeHints()
        if bind_widget is not None:
            self.setBaseSize(bind_widget.sizeHint())
            if isinstance(bind_widget, LiveImageZoom):
                bind_widget.livezoom_resize_signal.connect(self._resizeDockWidget)
        if close_slot is not None:
            self.close_button.clicked.connect(close_slot)
            if isinstance(bind_widget, ImageControlDialog):
                bind_widget.whide.clicked.connect(close_slot)
        if toggle_slot is not None:
            self.toggle_button.clicked.connect(toggle_slot)

    def _resizeDockWidget(self, qsize):
        # live zoom signal slot to resize dockwidget and dock areas
        self.setMinimumSize(qsize)
        self.main_win.resizeDocks([self], [qsize.width()], Qt.Horizontal)
        self.main_win.resizeDocks([self], [qsize.height()], Qt.Vertical)

    # hack to stop QDockWidget responding to drag events for undocking - work around for Qt bug
    def eventFilter(self, source, event):
        # event seq 2, 5, 3 - mouse press, mouse move, mouse release
        if event.type() == QEvent.MouseButtonPress:
            label = self.childAt(event.pos())
            if not label:
                return super(TDockWidget, self).eventFilter(source, event)
            if isinstance(label, QLabel):
                if not self.isFloating():
                    fake_mouse_event = QMouseEvent(QEvent.MouseButtonRelease, event.pos(), event.button(), event.buttons(), event.modifiers())
                    super(TDockWidget, self).event(fake_mouse_event)
                    return True
        return super(TDockWidget, self).eventFilter(source, event)


class TigToolTip(QLabel):
    """Custom QToolTip type widget based on a QLabel for plot information output."""
    def __init__(self):
        QLabel.__init__(self)
        self.installEventFilter(self)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_QuitOnClose)
        self.setStyleSheet("QLabel {background-color: white; color: black;}")
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
        self._qtimer = QTimer()
        self._qtimer.timeout.connect(self.hideText)

    def showText(self, location, text, timeout=7000):
        if self._qtimer.isActive():
            self._qtimer.start(timeout)
        self.setText(text)
        text_size = self.fontMetrics().boundingRect(self.text())
        # TODO - find a better way for the below sizes
        if text_size.width() > 900:
            max_w = 700
            max_h = text_size.height() * 4
        else:
            max_w = 900
            max_h = text_size.height()
        self.setGeometry(location.x(), location.y(), max_w, max_h)
        self.show()
        self._qtimer.start(timeout)

    def hideText(self):
        self._qtimer.stop()
        self.close()
        # available on Ubuntu by default
        # disabling for now issue #163
        # os.system('notify-send "Tigger" "Information copied to clipboard"')

    def eventFilter(self, source, event):
        # event.type() 25 == QEvent.WindowDeactivate.
        # In this context, TigToolTip is the top most window and when application has been changed in terms of state,
        # for example to another application, the TigToolTip needs to be closed, otherwise it will remain on the screen.
        if event.type() == QEvent.WindowDeactivate:
            if self._qtimer.isActive():
                self._qtimer.stop()
            self.close()
        return super(TigToolTip, self).eventFilter(source, event)
