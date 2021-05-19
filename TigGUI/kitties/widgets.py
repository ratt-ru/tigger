# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
from PyQt5.Qt import QCursor, Qt, QWidgetAction, QLabel, QFrame, QTreeWidget, QObject, QApplication, \
    QTreeWidgetItemIterator, QListWidget
from PyQt5.QtWidgets import *
from PyQt5 import *
from PyQt5.QtCore import *


class BusyIndicator:
    """A BusyIndicator object is created to set the cursor to a hourglass.
    When the object is destroyed (i.e. when local variable goes out of scope), the cursor is reset."""

    def __init__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __del__(self):
        QApplication.restoreOverrideCursor()

    def reset_cursor(self):
        QApplication.restoreOverrideCursor()


def addMenuLabel(menu, text):
    """Adds a QLabel contaning text to the given menu"""
    qaw = QWidgetAction(menu)
    lab = QLabel(text, menu)
    qaw.setDefaultWidget(lab)
    lab.setAlignment(Qt.AlignCenter)
    lab.setFrameShape(QFrame.StyledPanel)
    lab.setFrameShadow(QFrame.Sunken)
    menu.addAction(qaw)
    return lab


class ClickableTreeWidget(QTreeWidget):

    def __init__(self, *args):
        QTreeWidget.__init__(self, *args)
        self._expanded_item = None
        self._mouse_press_pos = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested[QPoint].connect(self._request_context_menu)
        self.itemExpanded[QTreeWidgetItem].connect(self._item_expanded_collapsed)
        self.itemCollapsed[QTreeWidgetItem].connect(self._item_expanded_collapsed)

    def mousePressEvent(self, ev):
        self._expanded_item = None
        self._mouse_press_pos = ev.pos()
        QTreeWidget.mousePressEvent(self, ev)

    def mouseReleaseEvent(self, ev):
        item = self.itemAt(self._mouse_press_pos)
        col = None
        if item:
            col = self.header().logicalIndexAt(self._mouse_press_pos)
        # pass event to parent
        QTreeWidget.mouseReleaseEvent(self, ev)
        # now see if the item was expanded or collapsed because of the event. Only emit signal if this was
        # not the case (i.e. swallow the clicks that have to do with expansion/collapse of items)
        if item and item is not self._expanded_item and col is not None:
            self.itemClicked.emit(item, col)

    def _item_expanded_collapsed(self, item):
        self._expanded_item = item

    def _request_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return

        item = self.itemAt(pos)
        if item:
            name = item.text(0)
            col = self.header().logicalIndexAt(pos)

            menu = QtWidgets.QMenu()
            menu.addSection("Menu")
            action = menu.addAction(name)
            action.setEnabled(False)
            menu.exec_(self.mapToGlobal(pos))

            # old line below fails
            # self.itemContextMenuRequested.emit(item, pos, col)

    class Iterator(QTreeWidgetItemIterator):
        def __init__(self, *args, **kw):
            QTreeWidgetItemIterator.__init__(self, *args)
            self._include_children = kw.get('children', False)
            parent = args[0]
            if isinstance(parent, QTreeWidget):
                if hasattr(QTreeWidget, 'invisibleRootItem'):
                    self._parent = parent.invisibleRootItem()
                else:
                    self._parent = None  # Qt 4.1 item.parent() returns None for top-level items
            else:
                self._parent = parent

        def __iter__(self):
            return self

        def __next__(self):
            while True:
                value = self.value()
                self.__iadd__(1)
                if not value:
                    raise StopIteration
                if self._include_children or value.parent() is None or value.parent() is self._parent:
                    return value

        def next(self):
            return self.__next__()

    def iterator(self, *args):
        """Returns a child item iterator.
        iterator([flags]) returns an iterator for the tree widget itself
        iterator(item,[flags]) returns an iterator for a tree widget item
        """
        if len(args) > 1:
            return ClickableTreeWidget.Iterator(*args)
        else:
            return ClickableTreeWidget.Iterator(self, *args)


TreeWidgetItemIterator = ClickableTreeWidget.Iterator


class ClickableListWidget(QListWidget):
    def __init__(self, *args):
        QListWidget.__init__(self, *args)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested[QPoint].connect(self._request_context_menu)

    def _request_context_menu(self, pos):
        item = self.itemAt(pos)
        if item:
            self.itemContextMenuRequested.emit(item, pos)
