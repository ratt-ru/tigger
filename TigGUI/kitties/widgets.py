# -*- coding: utf-8 -*-
from PyQt4.Qt import SIGNAL, QCursor, Qt, QWidgetAction, QLabel, QFrame, QTreeWidget, QObject, QApplication, \
    QTreeWidgetItemIterator, QListWidget


def PYSIGNAL(sig):
    """PyQt4 no longer supports PYSIGNAL(). Instead, everything goes through SIGNAL(). "Proper" user-defined
    signals must include an argument list, just like standard Qt signals. This will prove troublesome
    to old code using a lot of PYSIGNALS(), since proper argument lists would have to be inserted.
    Fortunately, PyQt3-PYSIGNAL-style argument passing -- where an arbitrary argument list was passed to
    emit(), and from there on to the slot -- is available in PyQt4 via "short-circuited" signals:.

      http://www.riverbankcomputing.co.uk/static/Docs/PyQt4/pyqt4ref.html#new-style-signal-and-slot-support

    A short-circuited signal has no parentheses at the end. Hence this function here to turn
    PYSIGNAL("x()") into SIGNAL("x"), to support old PyQt3-derived code.
    """
    if sig.endswith("()"):
        return SIGNAL(sig[:-2])
    else:
        return SIGNAL(sig)


class BusyIndicator(object):
    """A BusyIndicator object is created to set the cursor to a hourglass.
    When the object is destroyed (i.e. when local variable goes out of scope), the cursor is reset."""

    def __init__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __del__(self):
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
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        QObject.connect(self, SIGNAL('customContextMenuRequested(const QPoint &)'), self._request_context_menu)
        QObject.connect(self, SIGNAL('itemExpanded(QTreeWidgetItem *)'), self._item_expanded_collapsed)
        QObject.connect(self, SIGNAL('itemCollapsed(QTreeWidgetItem *)'), self._item_expanded_collapsed)

    def mousePressEvent(self, ev):
        self._expanded_item = None
        self._mouse_press_pos = ev.pos()
        QTreeWidget.mousePressEvent(self, ev)

    def mouseReleaseEvent(self, ev):
        item = self.itemAt(self._mouse_press_pos)
        if item:
            col = self.header().logicalIndexAt(self._mouse_press_pos)
        # pass event to parent
        QTreeWidget.mouseReleaseEvent(self, ev)
        # now see if the item was expanded or collapsed because of the event. Only emit signal if this was
        # not the case (i.e. swallow the clicks that have to do with expansion/collapse of items)
        if item and item is not self._expanded_item:
            self.emit(SIGNAL("mouseButtonClicked"), ev.button(), item, self._mouse_press_pos, col)

    def _item_expanded_collapsed(self, item):
        self._expanded_item = item

    def _request_context_menu(self, pos):
        item = self.itemAt(pos)
        if item:
            col = self.header().logicalIndexAt(pos)
            self.emit(SIGNAL("itemContextMenuRequested"), item, pos, col)

    class Iterator(QTreeWidgetItemIterator):
        def __init__(self, *args, **kw):
            QTreeWidgetItemIterator.__init__(self, *args)
            self._include_children = kw.get('children', False)
            parent = args[0]
            if isinstance(parent, QTreeWidget):
                if hasattr(QTreeWidget, 'invisibleRootItem'):
                    self._parent = parent.invisibleRootItem()
                else:
                    self._parent = None;  # Qt 4.1 item.parent() returns None for top-level items
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
        QObject.connect(self, SIGNAL('customContextMenuRequested(const QPoint &)'), self._request_context_menu)

    def _request_context_menu(self, pos):
        item = self.itemAt(pos)
        if item:
            self.emit(SIGNAL("itemContextMenuRequested"), item, pos)
