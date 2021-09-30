# type: ignore

from __future__ import annotations

import collections
import copy
import logging
import math
import numpy
import pkgutil
import sys
import time
import typing

# third party libraries
if 'PyQt5' in sys.modules:
    from PyQt5 import QtCore
    from PyQt5 import QtGui
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
else:
    from PySide2 import QtCore
    from PySide2 import QtGui
    from PySide2 import QtWidgets
    from PySide2.QtCore import Signal, Slot

if typing.TYPE_CHECKING:
    from nion.ui import QtUserInterface


app: PyApplication = typing.cast("PyApplication", None)

lastVisitedDir = str()

g_timer = None
g_timer_offset_ns = 0

g_stylesheet = None


_QtObject = typing.Any


def GetDirectory(path: str) -> str:
    info = QtCore.QFileInfo(QtCore.QDir.current(), path)
    if info.exists() and info.isDir():
        return QtCore.QDir.cleanPath(info.absoluteFilePath())
    info.setFile(info.absolutePath())
    if info.exists() and info.isDir():
        return info.absoluteFilePath()
    return str()


def WorkingDirectory(path: str) -> str:
    global lastVisitedDir
    if path:
        directory = GetDirectory(path)
        if directory:
            return directory
    directory = GetDirectory(lastVisitedDir)
    if directory:
        return directory
    return QtCore.QDir.currentPath()


def InitialSelection(path: str) -> str:
    if path:
        info = QtCore.QFileInfo(path)
        if not info.isDir():
            return info.fileName()
    return str()


def GetSaveFileName(parent: QtWidgets.QWidget, caption: str, dir: str, filter: str, selected_filter_ref: typing.List[str], selected_directory_ref: typing.List[typing.Optional[str]]) -> str:
    # create a qt dialog
    dialog = QtWidgets.QFileDialog(parent, caption, WorkingDirectory(dir), filter)
    dialog.selectFile(InitialSelection(dir))
    dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
    dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
    if selected_filter_ref[0]:
        dialog.selectNameFilter(selected_filter_ref[0])
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        selected_filter_ref[0] = dialog.selectedNameFilter()
        selected_directory_ref[0] = dialog.directory()
        return dialog.selectedFiles()[0]
    return str()


def GetOpenFileName(parent: QtWidgets.QWidget, caption: str, dir: str, filter: str, selected_filter_ref: typing.List[str], selected_directory_ref: typing.List[typing.Optional[str]]) -> str:
    # create a qt dialog
    dialog = QtWidgets.QFileDialog(parent, caption, WorkingDirectory(dir), filter)
    dialog.selectFile(InitialSelection(dir))
    dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
    if selected_filter_ref[0]:
        dialog.selectNameFilter(selected_filter_ref[0])
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        selected_filter_ref[0] = dialog.selectedNameFilter()
        selected_directory_ref[0] = dialog.directory()
        return dialog.selectedFiles()[0]
    return str()


def GetExistingDirectory(parent: QtWidgets.QWidget, caption: str, dir: str, selected_directory_ref: typing.List[typing.Optional[str]]) -> str:
    # create a qt dialog
    dialog = QtWidgets.QFileDialog(parent, caption, WorkingDirectory(dir))
    dialog.selectFile(InitialSelection(dir))
    dialog.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)  # also QtWidgets.QFileDialog.Directory
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        selected_directory_ref[0] = dialog.directory()
        return dialog.selectedFiles()[0]
    return str()


def GetOpenFileNames(parent: QtWidgets.QWidget, caption: str, dir: str, filter: str, selected_filter_ref: typing.List[str], selected_directory_ref: typing.List[typing.Optional[str]]) -> typing.List[str]:
    # create a qt dialog
    dialog = QtWidgets.QFileDialog(parent, caption, WorkingDirectory(dir), filter)
    dialog.selectFile(InitialSelection(dir))
    dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
    if selected_filter_ref[0]:
        dialog.selectNameFilter(selected_filter_ref[0])
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        selected_filter_ref[0] = dialog.selectedNameFilter()
        selected_directory_ref[0] = dialog.directory()
        return dialog.selectedFiles()
    return []


def GetDisplayScaling() -> float:
    logical_dpi = app.primaryScreen().logicalDotsPerInch()
    if sys.platform == 'darwin':
        return logical_dpi / 72
    else:
        return logical_dpi / 96


def ParseScrollBarPolicy(policy_str: str) -> QtCore.Qt.ScrollBarPolicy:
    policy_str_lower = policy_str.lower()
    if policy_str_lower == "off":
        return QtCore.Qt.ScrollBarAlwaysOff
    elif policy_str_lower == "on":
        return QtCore.Qt.ScrollBarAlwaysOn
    else:
        return QtCore.Qt.ScrollBarAsNeeded


def ParseSizePolicy(policy_str: str, policy: QtWidgets.QSizePolicy.Policy) -> QtWidgets.QSizePolicy.Policy:
    policy_str_lower = policy_str.lower()
    if policy_str_lower == "fixed":
        return QtWidgets.QSizePolicy.Fixed
    elif policy_str_lower == "maximum":
        return QtWidgets.QSizePolicy.Maximum
    elif policy_str_lower == "minimum":
        return QtWidgets.QSizePolicy.Minimum
    elif policy_str_lower == "preferred":
        return QtWidgets.QSizePolicy.Preferred
    elif policy_str_lower == "expanding":
        return QtWidgets.QSizePolicy.Expanding
    elif policy_str_lower == "min-expanding":
        return QtWidgets.QSizePolicy.MinimumExpanding
    elif policy_str_lower == "ignored":
        return QtWidgets.QSizePolicy.Ignored
    else:
        return policy


class PyApplication(QtWidgets.QApplication):

    def __init__(self, application, args):
        super().__init__(args)
        self.application = application
        global g_timer
        if g_timer is None:
            g_timer = QtCore.QElapsedTimer()
        g_timer.start()
        # setQuitOnLastWindowClosed should be false so that we can handle it explicitly.
        self.setQuitOnLastWindowClosed(False)
        self.aboutToQuit.connect(self.__about_to_quit)

    def __about_to_quit(self):
        if self.application and hasattr(self.application, "stop"):
            self.application.stop()


class PyAction(QtWidgets.QAction):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.object = None
        self.triggered.connect(self.__triggered)

    def __triggered(self) -> None:
        if self.object:
            try:
                self.object.triggered()
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyDrag(QtGui.QDrag):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.object = None

    def execute(self):
        if self.object:
            action = self.exec_(QtCore.Qt.CopyAction | QtCore.Qt.MoveAction)
            mapping = {
                QtCore.Qt.CopyAction: "copy",
                QtCore.Qt.MoveAction: "move",
                QtCore.Qt.LinkAction: "link",
                QtCore.Qt.IgnoreAction: "ignore",
            }
            try:
                self.object.dragFinished(mapping[action])
            except Exception as e:
                import traceback
                traceback.print_exc()

class PyMenu(QtWidgets.QMenu):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.aboutToShow.connect(self.__about_to_show)
        self.aboutToHide.connect(self.__about_to_hide)

    def __about_to_show(self):
        if self.object:
            try:
                self.object.aboutToShow()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __about_to_hide(self):
        if self.object:
            try:
                self.object.aboutToHide()
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyDocumentWindow(QtWidgets.QMainWindow):

    def __init__(self, title: str, parent_window):
        super().__init__(parent_window)
        self.object: PyDocumentWindow = typing.cast("PyDocumentWindow", None)
        self.__closed = False
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setDockOptions(QtWidgets.QMainWindow.AllowNestedDocks | QtWidgets.QMainWindow.AllowTabbedDocks)
        if title:
            self.setWindowTitle(title)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.__cleanDocument()

    def initialize(self):
        self.__periodic_timer = QtCore.QTimer(self)
        self.__periodic_timer.timeout.connect(self.__periodic)
        self.__periodic_timer.start(1000 // 50)  # 20ms, 50fps
        self.__cleanDocument()

    def __cleanDocument(self):
        self.setWindowModified(False)

    def __periodic(self):
        if self.isVisible():
            try:
                self.object.periodic()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def showEvent(self, show_event: QtGui.QShowEvent) -> None:
        super().showEvent(show_event)
        try:
            self.object.aboutToShow()
        except Exception as e:
            import traceback
            traceback.print_exc()
        self.setFocus()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.sizeChanged(int(event.size().width() / display_scaling), int(event.size().height() / display_scaling))
            except Exception as e:
                import traceback
                traceback.print_exc()

    def moveEvent(self, event: QtGui.QMoveEvent) -> None:
        super().moveEvent(event)
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.positionChanged(int(event.pos().x() / display_scaling), int(event.pos().y() / display_scaling))
            except Exception as e:
                import traceback
                traceback.print_exc()

    def changeEvent(self, event: QtCore.QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.ActivationChange:
            try:
                self.object.activationChanged(self.isActiveWindow())
            except Exception as e:
                import traceback
                traceback.print_exc()

    def closeEvent(self, close_event: QtGui.QCloseEvent) -> None:
        # see closing issue when closing from dock widget on OS X:
        # https://bugreports.qt.io/browse/QTBUG-43344
        if not self.__closed:
            geometry = self.saveGeometry().toHex().data().decode("utf8")
            state = self.saveState().toHex().data().decode("utf8")
            try:
                self.object.aboutToClose(geometry, state)
            except Exception as e:
                import traceback
                traceback.print_exc()
            self.__closed = True
        close_event.accept()
        # window will be automatically hidden, according to Qt documentation

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.type() == QtCore.QEvent.KeyPress:
            if self.object:
                try:
                    if self.object.keyPressed(event.text(), event.key(), event.modifiers()):
                        event.accept()
                        return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.type() == QtCore.QEvent.KeyRelease:
            if self.object:
                try:
                    if self.object.keyReleased(event.text(), event.key(), event.modifiers()):
                        event.accept()
                        return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        super().keyReleaseEvent(event)


class DockWidget(QtWidgets.QDockWidget):

    def __init__(self, title: str, parent: QtWidgets.QWidget):
        super().__init__(title, parent)
        self.object = None

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.sizeChanged(int(event.size().width() / display_scaling), int(event.size().height() / display_scaling))
            except Exception as e:
                import traceback
                traceback.print_exc()

    def focusInEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusIn()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusOut()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusOutEvent(event)


class PyPushButton(QtWidgets.QPushButton):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.clicked.connect(self.__clicked)

    def __clicked(self):
        if self.object:
            try:
                self.object.clicked()
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyRadioButton(QtWidgets.QRadioButton):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.setAutoExclusive(False)
        self.clicked.connect(self.__clicked)

    def __clicked(self):
        if self.object:
            try:
                self.object.clicked()
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyButtonGroup(QtWidgets.QButtonGroup):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.buttonClicked.connect(self.__button_clicked)

    def __button_clicked(self, button_id: int) -> None:
        if self.object:
            try:
                self.object.clicked(button_id)
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyCheckBox(QtWidgets.QCheckBox):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.stateChanged.connect(self.__state_changed)

    def __state_changed(self, state: int) -> None:
        if self.object:
            try:
                self.object.stateChanged(["unchecked", "partial", "checked"][state])
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyComboBox(QtWidgets.QComboBox):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.currentTextChanged.connect(self.__current_text_changed)

    def __current_text_changed(self, current_text: str) -> None:
        if self.object:
            try:
                self.object.currentTextChanged(current_text)
            except Exception as e:
                import traceback
                traceback.print_exc()


class PySlider(QtWidgets.QSlider):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.setOrientation(QtCore.Qt.Horizontal)
        self.setTracking(True)
        self.valueChanged.connect(self.__value_changed)
        self.sliderPressed.connect(self.__slider_pressed)
        self.sliderReleased.connect(self.__slider_released)
        self.sliderMoved.connect(self.__slider_moved)

    def __value_changed(self, value: int) -> None:
        if self.object:
            try:
                self.object.valueChanged(value)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __slider_pressed(self) -> None:
        if self.object:
            try:
                self.object.sliderPressed()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __slider_released(self) -> None:
        if self.object:
            try:
                self.object.sliderReleased()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __slider_moved(self, value: int) -> None:
        if self.object:
            try:
                self.object.sliderMoved(value)
            except Exception as e:
                import traceback
                traceback.print_exc()


class PyLineEdit(QtWidgets.QLineEdit):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.editingFinished.connect(self.__editing_finished)
        self.textEdited.connect(self.__text_edited)

    def __editing_finished(self) -> None:
        if self.object:
            try:
                self.object.editingFinished(self.text())
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __text_edited(self, text: str) -> None:
        if self.object:
            try:
                self.object.textEdited(text)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def keyPressEvent(self, key_event):
        if key_event.type() == QtCore.QEvent.KeyPress:
            if key_event.key() == QtCore.Qt.Key_Escape:
                if self.object:
                    try:
                        if self.object.escapePressed():
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            elif key_event.key() == QtCore.Qt.Key_Return or key_event.key() == QtCore.Qt.Key_Enter:
                if self.object:
                    try:
                        if self.object.returnPressed():
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            else:
                if self.object:
                    try:
                        if self.object.keyPressed(key_event.text(), key_event.key(), key_event.modifiers()):
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
        super().keyPressEvent(key_event)


class PyTextEdit(QtWidgets.QTextEdit):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(True)
        self.cursorPositionChanged.connect(self.__cursor_position_changed)
        self.selectionChanged.connect(self.__selection_changed)
        self.textChanged.connect(self.__text_changed)

    def __cursor_position_changed(self) -> None:
        if self.object:
            try:
                self.object.cursorPositionChanged()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __selection_changed(self) -> None:
        if self.object:
            try:
                self.object.selectionChanged()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __text_changed(self) -> None:
        if self.object:
            try:
                self.object.textChanged()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def keyPressEvent(self, key_event):
        if key_event.type() == QtCore.QEvent.KeyPress:
            if key_event.key() == QtCore.Qt.Key_Escape:
                if self.object:
                    try:
                        if self.object.escapePressed():
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            elif key_event.key() == QtCore.Qt.Key_Return or key_event.key() == QtCore.Qt.Key_Enter:
                if self.object:
                    try:
                        if self.object.returnPressed():
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            else:
                if self.object:
                    try:
                        if self.object.keyPressed(key_event.text(), key_event.key(), key_event.modifiers()):
                            key_event.accept()
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
        super().keyPressEvent(key_event)

    def focusInEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusIn()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusOut()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusOutEvent(event)

    def insertFromMimeData(self, mime_data):
        if self.object:
            try:
                self.object.insertFromMimeData(mime_data)
            except Exception as e:
                import traceback
                traceback.print_exc()


class Overlay(QtWidgets.QWidget):

    def __init__(self, parent: QtWidgets.QWidget, child: QtWidgets.QWidget):
        super().__init__(parent)
        self.__child = child
        self.installEventFilter(self)  # for resize
        self.setPalette(QtCore.Qt.transparent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        if self.__child:
            self.__child.setPalette(QtCore.Qt.transparent)
            self.__child.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            self.__child.setParent(self)

    def eventFilter(self, source, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Resize and source == self.parent():
            self.resize(event.size())
        return super().eventFilter(source, event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        if self.__child:
            self.__child.resize(event.size())
        super().resizeEvent(event)


class PyScrollArea(QtWidgets.QScrollArea):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.viewport().installEventFilter(self)  # for initial resize
        self.horizontalScrollBar().valueChanged.connect(self.__scroll_bar_changed)
        self.verticalScrollBar().valueChanged.connect(self.__scroll_bar_changed)

    def eventFilter(self, source, event: QtCore.QEvent) -> bool:
        result = super().eventFilter(source, event)
        if event.type() == QtCore.QEvent.Resize and source == self.viewport():
            self.__notify_viewport_changed()
        return result

    def __notify_viewport_changed(self):
        if self.object:
            display_scaling = GetDisplayScaling()
            offset = self.widget().mapFrom(self.viewport(), QtCore.QPoint(0, 0))
            viewport_rect = self.viewport().rect().translated(offset.x(), offset.y())
            try:
                self.object.viewportChanged(viewport_rect.left() / display_scaling, viewport_rect.top() / display_scaling, viewport_rect.width() / display_scaling, viewport_rect.height() / display_scaling)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __scroll_bar_changed(self, value: int) -> None:
        self.__notify_viewport_changed()

    def focusInEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusIn()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusOut()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusOutEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.sizeChanged(int(event.size().width() / display_scaling), int(event.size().height() / display_scaling))
            except Exception as e:
                import traceback
                traceback.print_exc()
            self.__notify_viewport_changed()


class PyTabWidget(QtWidgets.QTabWidget):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.currentChanged.connect(self.__current_changed)

    def __current_changed(self, index: int) -> None:
        if self.object:
            try:
                self.object.currentTabChanged(index)
            except Exception as e:
                import traceback
                traceback.print_exc()


class TreeWidget(QtWidgets.QTreeView):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setDragEnabled(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.clicked.connect(self.__clicked)
        self.doubleClicked.connect(self.__double_clicked)
        self.__saved_index = None

    def focusInEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusIn()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusOut()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusOutEvent(event)

    def setModelAndConnect(self, item_model: "ItemModel") -> None:
        self.setModel(item_model)
        item_model.modelAboutToBeReset.connect(self.__model_about_to_be_reset)
        item_model.modelReset.connect(self.__model_reset)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.type() == QtCore.QEvent.KeyPress:
            if self.__handle_key(event.text(), event.key(), int(event.modifiers())):
                return
        super().keyPressEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        super().dropEvent(event)
        if event.isAccepted():
            event.setDropAction(self.model().lastDropAction())

    def currentChanged(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        super().currentChanged(current, previous)
        row = current.row()
        parent_row = -1
        parent_id = 0
        if current.parent().isValid():
            parent_row = current.parent().row()
            parent_id = int(current.parent().internalId())
        if self.object:
            try:
                self.object.treeItemChanged(row, parent_row, parent_id)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def selectionChanged(self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection) -> None:
        # note the parameters passed represent the CHANGES not the new and old selection
        super().selectionChanged(selected, deselected)
        selected_indexes = list()
        for index in self.selectedIndexes():
            row = index.row()
            parent_row = -1
            parent_id = 0
            if index.parent().isValid():
                parent_row = index.parent().row()
                parent_id = int(index.parent().internalId())
            selected_index = row, parent_row, parent_id
            selected_indexes.append(selected_index)
        if self.object:
            try:
                self.object.treeSelectionChanged(selected_indexes)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def __model_about_to_be_reset(self):
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        self.__saved_index = self.currentIndex().row()

    def __model_reset(self):
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        self.setCurrentIndex(self.model().index(self.__saved_index, 0))

    def __handle_key(self, text: str, key: int, modifiers: int) -> bool:
        selected_indexes = list()
        for index in self.selectedIndexes():
            row = index.row()
            parent_row = -1
            parent_id = 0
            if index.parent().isValid():
                parent_row = index.parent().row()
                parent_id = int(index.parent().internalId())
            selected_index = row, parent_row, parent_id
            selected_indexes.append(selected_index)
        if len(selected_indexes) == 1:
            selected_index = selected_indexes[0]
            row = selected_index[0]
            parent_row = selected_index[1]
            parent_id = selected_index[2]
            try:
                if self.object and self.object.treeItemKeyPressed(row, parent_row, parent_id, text, key, modifiers):
                    return True
            except Exception as e:
                import traceback
                traceback.print_exc()
        try:
            if self.object:
                return self.object.keyPressed(selected_indexes, text, key, modifiers)
            return False
        except Exception as e:
            import traceback
            traceback.print_exc()
        return False

    def __clicked(self, index: QtCore.QModelIndex) -> None:
        row = index.row()
        parent_row = -1
        parent_id = 0
        if index.parent().isValid():
            parent_row = index.parent().row()
            parent_id = int(index.parent().internalId())

        try:
            if self.object:
                self.object.treeItemClicked(row, parent_row, parent_id)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def __double_clicked(self, index: QtCore.QModelIndex) -> None:
        row = index.row()
        parent_row = -1
        parent_id = 0
        if index.parent().isValid():
            parent_row = index.parent().row()
            parent_id = int(index.parent().internalId())

        try:
            if self.object:
                self.object.treeItemDoubleClicked(row, parent_row, parent_id)
        except Exception as e:
            import traceback
            traceback.print_exc()


class ItemModel(QtCore.QAbstractItemModel):

    def __init__(self, parent: QtCore.QObject):
        super().__init__(parent)
        self.object: QtUserInterface.QtItemModelController = typing.cast("QtUserInterface.QtItemModelController", None)
        self.__last_drop_action = QtCore.Qt.IgnoreAction

    def supportedDropActions(self) -> QtCore.Qt.DropActions:
        try:
            return self.object.supportedDropActions()
        except Exception as e:
            import traceback
            traceback.print_exc()
        return QtCore.Qt.DropActions(QtCore.Qt.IgnoreAction)

    def columnCount(self, parent: QtCore.QModelIndex) -> int:
        return 1

    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        try:
            return self.object.itemCount(parent.internalId())
        except Exception as e:
            import traceback
            traceback.print_exc()
        return 0

    # All (id=1, parent=0, row=0)
    #   Checker (id=11, parent=1, row=0)
    #   Green (id=12, parent=1, row=1)
    #   Simulator (id=13, parent=1 row=2)
    # Some (id=2, parent=0, row=1)
    #   Checker (id=21, parent=2, row=0)
    #   Green (id=22, parent=2, row=1)

    def index(self, row: int, column: int, parent: QtCore.QModelIndex) -> QtCore.QModelIndex:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()
        try:
            item_id = self.object.itemId(row, parent.internalId())
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        if row >= 0:
            return self.createIndex(row, 0, item_id)
        return QtCore.QModelIndex()

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        try:
            result = self.object.itemParent(index.row(), index.internalId())
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        row = result[0]
        item_id = result[1]
        if row >= 0:
            return self.createIndex(row, 0, item_id)
        return QtCore.QModelIndex()

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEnabled
        else:
            return default_flags | QtCore.Qt.ItemIsDropEnabled

    def data(self, index: QtCore.QModelIndex, role: int) -> typing.Any:
        global app
        assert app.thread() == QtCore.QThread.currentThread()

        if role == QtCore.Qt.DisplayRole:
            role_name = "display"
        elif role == QtCore.Qt.EditRole:
            role_name = "edit"
        else:
            role_name = str()

        if role_name in ["display", "edit"]:
            if index.column() == 0:
                try:
                    return self.object.itemValue(role_name, index.row(), index.internalId())
                except Exception as e:
                    import traceback
                    traceback.print_exc()

        return None

    def setData(self, index: QtCore.QModelIndex, value, role: int) -> bool:
        if role != QtCore.Qt.EditRole:
            return False
        row = index.row()
        parent_row = -1
        parent_id = 0
        if index.parent().isValid():
            parent_row = index.parent().row()
            parent_id = int(index.parent().internalId())
        try:
            result = self.object.itemSetData(row, parent_row, parent_id, value)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        if result:
            self.dataChanged.emit(index, index)
        return result

    def mimeTypes(self) -> typing.List[str]:
        try:
            return self.object.mimeTypesForDrop()
        except Exception as e:
            import traceback
            traceback.print_exc()
        return list()

    def mimeData(self, indexes: typing.List[QtCore.QModelIndex]) -> typing.Optional[QtCore.QMimeData]:
        # simplifying assumption for now
        if len(indexes) != 1:
            return None
        index = indexes[0]
        row = index.row()
        parent_row = -1
        parent_id = 0
        if index.parent().isValid():
            parent_row = index.parent().row()
            parent_id = int(index.parent().internalId())
        try:
            return self.object.itemMimeData(row, parent_row, parent_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
        return None

    def canDropMimeData(self, mime_data: QtCore.QMimeData, action: QtCore.Qt.DropAction, row: int, column: int, parent: QtCore.QModelIndex) -> bool:
        if column > 0:
            return False
        parent_row = -1
        parent_id = 0
        if parent.isValid():
            parent_row = parent.row()
            parent_id = int(parent.internalId())
        return self.canDropMimeData(mime_data, action, row, parent_row, QtCore.QModelIndex(parent_id))

    def dropMimeData(self, mime_data: QtCore.QMimeData, action: QtCore.Qt.DropAction, row: int, column: int, parent: QtCore.QModelIndex) -> bool:
        if action == QtCore.Qt.IgnoreAction:
            return True
        if column > 0:
            return False
        parent_row = -1
        parent_id = 0
        if parent.isValid():
            parent_row = parent.row()
            parent_id = int(parent.internalId())
        drop_action = self.itemDropMimeData(mime_data, action, row, parent_row, parent_id)
        self.__last_drop_action = drop_action
        return drop_action != QtCore.Qt.IgnoreAction

    def beginInsertRowsInParent(self, first_row: int, last_row: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        parent = QtCore.QModelIndex() if parent_row < 0 else self.createIndex(parent_row, 0, parent_item_id)
        self.beginInsertRows(parent, first_row, last_row)

    def beginRemoveRowsInParent(self, first_row: int, last_row: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        parent = QtCore.QModelIndex() if parent_row < 0 else self.createIndex(parent_row, 0, parent_item_id)
        self.beginRemoveRows(parent, first_row, last_row)

    def endInsertRowsInParent(self):
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        self.endInsertRows()

    def endRemoveRowsInParent(self):
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        self.endRemoveRows()

    def removeRows(self, row: int, count: int, parent: QtCore.QModelIndex) -> bool:
        parent_row = parent.row()
        parent_id = int(parent.internalId())
        try:
            return self.object.removeRows(row, count, parent_row, parent_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
        return False

    def dataChangedInParent(self, row: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        parent = QtCore.QModelIndex() if parent_row < 0 else self.createIndex(parent_row, 0, parent_item_id)
        self.dataChanged.emit(self.index(row, 0, parent), self.index(row, 0, parent))

    def indexInParent(self, row: int, parent_row: int, parent_item_id: int) -> QtCore.QModelIndex:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        parent = QtCore.QModelIndex() if parent_row < 0 else self.createIndex(parent_row, 0, parent_item_id)
        return self.index(row, 0, parent)


# see http://www.mathopenref.com/coordtrianglearea.html
def triangleArea(p1: QtCore.QPointF, p2: QtCore.QPointF, p3: QtCore.QPointF) -> float:
    return math.fabs(0.5 * (p1.x() * (p2.y() - p3.y()) + p2.x() * (p3.y() - p1.y()) + p3.x() * (p1.y() - p2.y())))


# see http://www.dbp-consulting.com/tutorials/canvas/CanvasArcTo.html
def addArcToPath(path: QtGui.QPainterPath, x: float, y: float, radius: float, start_angle_radians: float, end_angle_radians: float, counter_clockwise: bool) -> None:
    # print(f"{arc} {x},{y},{radius},{start_angle_radians},{end_angle_radians},"counter_clockwise}")
    x_start = x - radius
    y_start = y - radius
    width  = radius * 2
    height = radius * 2
    clockwise = not counter_clockwise

    # first check if drawing more than the circumference of the circle
    if clockwise and (end_angle_radians - start_angle_radians >= 2 * math.pi):
        end_angle_radians = start_angle_radians + 2 * math.pi
    elif not clockwise and (start_angle_radians - end_angle_radians >= 2 * math.pi):
        start_angle_radians = end_angle_radians - 2 * math.pi

    # on canvas, angles and sweep_length are in degrees clockwise from positive x-axis
    # in Qt, angles are counter-clockwise from positive x-axis; position sweep_length draws counter-clockwise
    # calculate accordingly.

    start_angle_degrees = -180 * start_angle_radians / math.pi
    end_angle_degrees = -180 * end_angle_radians / math.pi

    sweep_angle_degrees = 0.0

    if clockwise:
        # clockwise from 10 to 20 (canvas) => -10 to -20 (qt) => -10 + -10 (qt)
        # clockwise from -20 to -10 (canvas) => 20 to 10 (qt) => 20 + -10 (qt)
        # clockwise from 10 to -20 (canvas) => -10 to 20 (qt) => -10 to 340 => -10 - 330 (qt)
        # remember, degrees have already been negated here, i.e. in qt degrees.
        if start_angle_degrees < end_angle_degrees:
            sweep_angle_degrees = end_angle_degrees - start_angle_degrees - 360.0
        else:
            sweep_angle_degrees = end_angle_degrees - start_angle_degrees
    else:
        # counterclockwise from 20 to 10 (canvas) => -20 to -10 (qt) => -20 + 10 (qt)
        # counterclockwise from -20 to -10 (canvas) => 20 to 10 (qt) => 20 + 350 (qt)
        # counterclockwise from 10 to -20 (canvas) => -10 to 20 (qt) => -10 + 30 (qt)
        # remember, degrees have already been negated here, i.e. in qt degrees.
        if end_angle_degrees < start_angle_degrees:
            sweep_angle_degrees = end_angle_degrees - start_angle_degrees + 360.0
        else:
            sweep_angle_degrees = end_angle_degrees - start_angle_degrees

    if radius == 0.0:
        # just draw the center point
        path.lineTo(x, y)
    else:
        # arcTo angle is counter-clockwise from positive x-axis; position sweep_length draws counter-clockwise
        path.arcTo(x_start, y_start, width, height, start_angle_degrees, sweep_angle_degrees)


def ParseFontString(font_string: str, display_scaling: float = 1.0) -> QtGui.QFont:
    font = QtGui.QFont()
    family_parts = list()
    is_family = False
    for font_part in font_string.strip().split(" "):
        if not is_family:
            if font_part == "italic":
                font.setStyle(QtGui.QFont.StyleItalic)
            elif font_part == "normal":
                pass
            elif font_part == "oblique":
                font.setStyle(QtGui.QFont.StyleOblique)
            elif font_part == "small-caps":
                font.setCapitalization(QtGui.QFont.SmallCaps)
            elif font_part == "bold":
                font.setWeight(QtGui.QFont.Bold)
            elif font_part == "medium":
                font.setWeight(QtGui.QFont.Medium)
            elif font_part == "system":
                font.setStyleHint(QtGui.QFont.System)
            elif font_part.endswith("pt") and int(font_part[:-2]) > 0:
                font.setPointSizeF(int(font_part[:-2]) * display_scaling)
            elif font_part.endswith("px") and int(font_part[:-2]) > 0:
                font.setPixelSize(int(int(font_part[:-2]) * display_scaling))
            else:
                is_family = True
        if is_family:
            family_parts.append(font_part)

    family_list = list()
    family_str = " ".join(family_parts)
    quote = None
    family = str()
    for current in family_str:
        if quote is None:
            if current == ',':
                family_list.append(family.strip())
                family = str()
            elif current == '\'' or current == '\"':
                quote = current
            else:
                family += current
        else:
            if current == quote:
                quote = 0
            else:
                family += current
    family_list.append(family.strip())

    families = [f.lower() for f in QtGui.QFontDatabase().families()]
    for family in family_list:
        if family in families:
            font.setFamily(family)
            break
        elif family == "monospace":
            font.setFamily(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont).family())
        elif family == "serif":
            font.setStyleHint(QtGui.QFont.Serif)
        elif family == "sans-serif":
            font.setStyleHint(QtGui.QFont.SansSerif)

    font.setStyleStrategy(QtGui.QFont.PreferAntialias)

    return font


def imageFromRGBA(array: numpy.ndarray) -> QtGui.QImage:
    if array is not None:
        return QtGui.QImage(array, array.shape[1], array.shape[0], QtGui.QImage.Format_ARGB32)
    else:
        return QtGui.QImage()


def image_from_uint8_data(data: numpy.ndarray, data_shape, lookup_table: numpy.ndarray) -> QtGui.QImage:
    image = QtGui.QImage(data, data_shape[1], data_shape[0], QtGui.QImage.Format_Indexed8)
    color_table = list()
    if lookup_table is not None:
        for i in range(lookup_table.shape[0]):
            color_table.append(lookup_table[i])
    else:
        for i in range(256):
            color_table.append((0xFF << 24) + (i << 16) + (i << 8) + i)
    image.setColorTable(color_table)
    return image


def normalize_data(array: numpy.ndarray, display_limit_low: float, display_limit_high: float) -> numpy.ndarray:
    width = array.shape[1]
    height = array.shape[0]
    m = 255.0 / (display_limit_high - display_limit_low) if display_limit_high != display_limit_low else 1
    row_bytes = int(math.floor((width + 3) / 4) * 4)
    data = numpy.empty((height, row_bytes), dtype=numpy.float32)
    data[0:height, 0:width] = (numpy.minimum(numpy.maximum(array, display_limit_low), display_limit_high) - display_limit_low) * m
    data[0:height, width:row_bytes] = 0
    return data


def rescale(data: numpy.ndarray, rect, context_scaling) -> numpy.ndarray:
    scaling = 1.0
    height_ratio = (rect.height() / data.shape[0]) if data is not None and data.shape[0] > 0 else 1
    width_ratio = (rect.width() / data.shape[1]) if data is not None and data.shape[1] > 0 else 1
    if height_ratio < 1 or width_ratio < 1:
        scaling = 1 / min(width_ratio, height_ratio)
    scaling /= context_scaling
    if scaling > 1.5:
        new_shape = (int(data.shape[0] / int(scaling + 0.05)), int(data.shape[1] / int(scaling + 0.05)))
        expanded_shape = (new_shape[0], data.shape[0] // new_shape[0], new_shape[1], data.shape[1] // new_shape[1])
        slices = (slice(0, expanded_shape[1] * new_shape[0]), slice(0, expanded_shape[3] * new_shape[1]))
        data = data[slices].reshape(expanded_shape).mean(-1).mean(1)
    return data


CanvasDrawingCommand = collections.namedtuple("CanvasDrawingCommand", ["command", "args"])

class PaintImageCacheEntry:
    def __init__(self, image_id, used, image):
        self.image_id = image_id
        self.used = used
        self.image = image

LayerCacheEntry = collections.namedtuple("LayerCacheEntry", ["layer_seed", "layer_image", "layer_rect"])

timer_map: typing.Dict[str, typing.Any] = dict()
times_map: typing.Dict[str, typing.Any] = dict()
count_map: typing.Dict[str, typing.Any] = dict()


RenderedTimestamp = collections.namedtuple("RenderedTimestamp", ["transform", "timestamp", "section_id"])


def PaintCommands(painter: QtGui.QPainter, commands: typing.List[CanvasDrawingCommand],
                  image_cache: typing.MutableMapping[int, PaintImageCacheEntry], display_scaling: float = 1.0, *,
                  layer_cache: typing.MutableMapping[int, LayerCacheEntry] = None,
                  section_id: int = 0) -> typing.List[RenderedTimestamp]:
    global timer_map
    global times_map
    global count_map
    global g_timer
    global g_timer_offset_ns

    rendered_timestamps: typing.List[RenderedTimestamp] = list()

    display_scaling = GetDisplayScaling()

    path = QtGui.QPainterPath()

    if image_cache:
        for image_id, entry in image_cache.items():
            entry.used = False

    fill_color = QtGui.QColor(QtCore.Qt.transparent)
    fill_gradient = -1

    line_color = QtGui.QColor(QtCore.Qt.black)
    line_width = 1.0
    line_dash = 0.0
    line_cap = QtCore.Qt.PenCapStyle(QtCore.Qt.SquareCap)
    line_join = QtCore.Qt.PenJoinStyle(QtCore.Qt.BevelJoin)

    text_font = QtGui.QFont()
    text_baseline = 4  # alphabetic
    text_align = 1  # start

    context_scaling_x = 1.0
    context_scaling_y = 1.0

    gradients: typing.Dict[int, QtGui.QLinearGradient] = dict()

    painter.fillRect(painter.viewport(), QtGui.QBrush(fill_color))

    layers_used = set()

    # print("BEGIN")

    stack = list()

    layer_skip = False
    layer_image = None
    painter_stack: typing.List[QtGui.QPainter] = list()
    layer_image_stack: typing.List[QtGui.QImage] = list()
    layer_skip_stack: typing.List[bool] = list()

    for command in commands:
        args = command.args
        cmd = command.command

        # print(f"{cmd}: {args}")

        if layer_skip and cmd != "end_layer" and cmd != "begin_layer":
            continue

        if cmd == "save":
            stack.append((fill_color, fill_gradient, line_color, line_width, line_dash, line_cap, line_join, text_font, text_baseline, text_align, context_scaling_x, context_scaling_y))
            painter.save()
        elif cmd == "restore":
            fill_color, fill_gradient, line_color, line_width, line_dash, line_cap, line_join, text_font, text_baseline, text_align, context_scaling_x, context_scaling_y = stack.pop()
            painter.restore()
        elif cmd == "beginPath":
            path = QtGui.QPainterPath()
        elif cmd == "closePath":
            path.closeSubpath()
        elif cmd == "clip":
            painter.setClipRect(args[0] * display_scaling, args[1] * display_scaling, args[2] * display_scaling, args[3] * display_scaling, QtCore.Qt.IntersectClip)
        elif cmd == "translate":
            painter.translate(args[0] * display_scaling, args[1] * display_scaling)
        elif cmd == "scale":
            painter.scale(args[0] * display_scaling, args[1] * display_scaling)
            context_scaling_x *= args[0]
            context_scaling_y *= args[1]
        elif cmd == "rotate":
            painter.rotate(args[0])
        elif cmd == "moveTo":
            path.moveTo(args[0] * display_scaling, args[1] * display_scaling)
        elif cmd == "lineTo":
            path.lineTo(args[0] * display_scaling, args[1] * display_scaling)
        elif cmd == "rect":
            path.addRect(args[0] * display_scaling, args[1] * display_scaling, args[2] * display_scaling, args[3] * display_scaling)
        elif cmd == "arc":
            # see http://www.w3.org/TR/2dcontext/#dom-context-2d-arc
            # see https://qt.gitorious.org/qt/qtdeclarative/source/e3eba2902fcf645bf88764f5272e2987e8992cd4:src/quick/items/context2d/qquickcontext2d.cpp#L3801-3815
            x = args[0] * display_scaling
            y = args[1] * display_scaling
            radius = args[2] * display_scaling
            start_angle_radians = args[3]
            end_angle_radians = args[4]
            clockwise = not args[5]
            addArcToPath(path, x, y, radius, start_angle_radians, end_angle_radians, not clockwise)
        elif cmd == "arcTo":
            # see https://github.com/WebKit/webkit/blob/master/Source/WebCore/platform/graphics/cairo/PathCairo.cpp
            # see https://code.google.com/p/chromium/codesearch#chromium/src/third_party/skia/src/core/SkPath.cpp&sq=package:chromium&type=cs&l=1381&rcl=1424120049
            # see https://bug-23003-attachments.webkit.org/attachment.cgi?id=26267
            p0 = path.currentPosition()
            p1 = QtCore.QPointF(args[0] * display_scaling, args[1] * display_scaling)
            p2 = QtCore.QPointF(args[2] * display_scaling, args[3] * display_scaling)
            radius = args[4] * display_scaling

            # Draw only a straight line to p1 if any of the points are equal or the radius is zero
            # or the points are collinear (triangle that the points form has area of zero value).
            if (p1 == p0) or (p1 == p2) or (radius == 0.0) or (triangleArea(p0, p1, p2) == 0.0):
                # just draw a line
                path.lineTo(p1.x(), p1.y())
                return rendered_timestamps

            p1p0 = QtCore.QPointF(p0.x() - p1.x(), p0.y() - p1.y())
            p1p2 = QtCore.QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            p1p0_length = math.sqrt(p1p0.x() * p1p0.x() + p1p0.y() * p1p0.y())
            p1p2_length = math.sqrt(p1p2.x() * p1p2.x() + p1p2.y() * p1p2.y())

            cos_phi = (p1p0.x() * p1p2.x() + p1p0.y() * p1p2.y()) / (p1p0_length * p1p2_length)
            # all points on a line logic
            if cos_phi == -1:
                path.lineTo(p1.x(), p1.y())
                return rendered_timestamps
            if cos_phi == 1:
                # add infinite far away point
                max_length = 65535
                factor_max = max_length / p1p0_length
                ep = QtCore.QPointF((p0.x() + factor_max * p1p0.x()), (p0.y() + factor_max * p1p0.y()))
                path.lineTo(ep.x(), ep.y())
                return rendered_timestamps

            tangent = radius / math.tan(math.acos(cos_phi) / 2)
            factor_p1p0 = tangent / p1p0_length
            t_p1p0 = QtCore.QPointF(p1.x() + factor_p1p0 * p1p0.x(), p1.y() + factor_p1p0 * p1p0.y())

            orth_p1p0 = QtCore.QPointF(p1p0.y(), -p1p0.x())
            orth_p1p0_length = math.sqrt(orth_p1p0.x() * orth_p1p0.x() + orth_p1p0.y() * orth_p1p0.y())
            factor_ra = radius / orth_p1p0_length

            # angle between orth_p1p0 and p1p2 to get the right vector orthographic to p1p0
            cos_alpha = (orth_p1p0.x() * p1p2.x() + orth_p1p0.y() * p1p2.y()) / (orth_p1p0_length * p1p2_length)
            if cos_alpha < 0:
                orth_p1p0 = QtCore.QPointF(-orth_p1p0.x(), -orth_p1p0.y())

            p = QtCore.QPointF(t_p1p0.x() + factor_ra * orth_p1p0.x(), t_p1p0.y() + factor_ra * orth_p1p0.y())

            # calculate angles for addArc
            orth_p1p0 = QtCore.QPointF(-orth_p1p0.x(), -orth_p1p0.y())
            sa = math.acos(orth_p1p0.x() / orth_p1p0_length)
            if orth_p1p0.y() < 0:
                sa = 2 * math.pi - sa

            # anticlockwise logic
            anticlockwise = False

            factor_p1p2 = tangent / p1p2_length
            t_p1p2 = QtCore.QPointF(p1.x() + factor_p1p2 * p1p2.x(), p1.y() + factor_p1p2 * p1p2.y())
            orth_p1p2 = QtCore.QPointF(t_p1p2.x() - p.x(), t_p1p2.y() - p.y())
            orth_p1p2_length = math.sqrt(orth_p1p2.x() * orth_p1p2.x() + orth_p1p2.y() * orth_p1p2.y())
            ea = math.acos(orth_p1p2.x() / orth_p1p2_length)
            if orth_p1p2.y() < 0:
                ea = 2 * math.pi - ea
            if (sa > ea) and ((sa - ea) < math.pi):
                anticlockwise = True
            if ((sa < ea) and ((ea - sa) > math.pi)):
                anticlockwise = True

            path.lineTo(t_p1p0.x(), t_p1p0.y())

            addArcToPath(path, p.x(), p.y(), radius, sa, ea, anticlockwise)
        elif cmd == "cubicTo":
            path.cubicTo(args[0] * display_scaling, args[1] * display_scaling, args[2] * display_scaling, args[3] * display_scaling, args[4] * display_scaling, args[5] * display_scaling)
        elif cmd == "quadraticTo":
            path.quadTo(args[0] * display_scaling, args[1] * display_scaling, args[2] * display_scaling, args[3] * display_scaling)
        elif cmd == "statistics":
            label = args[0].strip()

            timer = timer_map.setdefault(label, QtCore.QElapsedTimer())
            times = times_map.setdefault(label, collections.deque(maxlen=50))
            count_ref = count_map.setdefault(label, [0])

            if timer.isValid():
                times.append(timer.elapsed() / 1000)

                count_ref[0] += 1
                if count_ref[0] == 50:
                    sum = 0.0
                    mn = 9999.0
                    mx = 0.0
                    for t in times:
                        sum += t
                        mn = min(mn, t)
                        mx = max(mx, t)
                    mean = sum / times.length()
                    sum_of_squares = 0.0
                    for t in times:
                        sum_of_squares += (t - mean) * (t - mean)
                    std_dev = math.sqrt(sum_of_squares / times.length())
                    print(f"{label} fps {int(100 * (1.0 / mean))/100.0} mean {mean} dev {std_dev} min {mn} max {mx}")
                    count_ref[0] = 0

            timer.restart()
        elif cmd == "image":
            image_id = args[3]

            if image_cache and image_id in image_cache:
                image_cache[image_id].used = True
                image = image_cache[image_id].image
                destination_rect = QtCore.QRectF(QtCore.QPointF(args[4] * display_scaling, args[5] * display_scaling), QtCore.QSizeF(args[6] * display_scaling, args[7] * display_scaling))
                painter.drawImage(destination_rect, image)
            else:
                image = QtGui.QImage()

                # Grab the ndarray
                array = args[2]
                if array is not None:
                    image = imageFromRGBA(array)

                if not image.isNull():
                    destination_rect = QtCore.QRectF(QtCore.QPointF(args[4] * display_scaling, args[5] * display_scaling), QtCore.QSizeF(args[6] * display_scaling, args[7] * display_scaling))
                    context_scaling = min(context_scaling_x, context_scaling_y)
                    scaling = max(destination_rect.height() / image.height(), destination_rect.width() / image.width()) * context_scaling
                    if scaling < 0.75:
                        image = image.scaled((destination_rect.size() * context_scaling).toSize(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    painter.drawImage(destination_rect, image)
                    if image_cache:
                        image_cache[image_id] = PaintImageCacheEntry(image_id, True, image)
        elif cmd == "data":
            image_id = args[3]

            if image_cache and image_id in image_cache:
                image_cache[image_id].used = True
                image = image_cache[image_id].image
                destination_rect = QtCore.QRectF(QtCore.QPointF(args[4] * display_scaling, args[5] * display_scaling), QtCore.QSizeF(args[6] * display_scaling, args[7] * display_scaling))
                painter.drawImage(destination_rect, image)
            else:
                image = QtGui.QImage()
                destination_rect = QtCore.QRectF(QtCore.QPointF(args[4] * display_scaling, args[5] * display_scaling), QtCore.QSizeF(args[6] * display_scaling, args[7] * display_scaling))
                context_scaling = min(context_scaling_x, context_scaling_y)

                # Grab the ndarray
                array = args[2]
                if array is not None:
                    display_limit_low = args[8]
                    display_limit_high = args[9]
                    colormap = args[10]

                    # order here is: rescale, normalize, make image
                    data = rescale(array, destination_rect, context_scaling)
                    data_shape = data.shape
                    data = normalize_data(data, display_limit_low, display_limit_high).astype(numpy.uint8)
                    image = image_from_uint8_data(data, data_shape, colormap)

                if not image.isNull():
                    painter.drawImage(destination_rect, image)
                    if image_cache:
                        image_cache[image_id] = PaintImageCacheEntry(image_id, True, image)
        elif cmd == "stroke":
            pen = QtGui.QPen(line_color)
            pen.setWidthF(line_width * display_scaling)
            pen.setJoinStyle(line_join)
            pen.setCapStyle(line_cap)
            if line_dash > 0:
                dashes = [line_dash * display_scaling, line_dash * display_scaling]
                pen.setDashPattern(dashes)
            painter.strokePath(path, pen)
        elif cmd == "fill":
            brush = QtGui.QBrush(gradients[fill_gradient]) if fill_gradient >= 0 else QtGui.QBrush(fill_color)
            painter.fillPath(path, brush)
        elif cmd == "fillStyle":
            color_arg = args[0].strip()
            re1 = QtCore.QRegExp("^rgba\\(([0-9]+),\\s*([0-9]+),\\s*([0-9]+),\\s*([0-9.]+)\\)$")
            re2 = QtCore.QRegExp("^rgb\\(([0-9]+),\\s*([0-9]+),\\s*([0-9]+)\\)$")
            pos1 = re1.indexIn(color_arg)
            pos2 = re2.indexIn(color_arg)
            if pos1 > -1:
                fill_color = QtGui.QColor(int(re1.cap(1)), int(re1.cap(2)), int(re1.cap(3)), int(float(re1.cap(4)) * 255))
            elif pos2 > -1:
                fill_color = QtGui.QColor(int(re2.cap(1)), int(re2.cap(2)), int(re2.cap(3)))
            else:
                fill_color = QtGui.QColor(color_arg)
            fill_gradient = -1
        elif cmd == "fillStyleGradient":
            fill_gradient = args[0]
        elif cmd == "fillText" or cmd == "strokeText":
            text = args[0]
            text_pos = QtCore.QPointF(args[1] * display_scaling, args[2] * display_scaling)
            fm = QtGui.QFontMetrics(text_font)
            text_width = fm.width(text)
            if text_align == 2 or text_align == 5:  # end or right
                text_pos.setX(text_pos.x() - text_width)
            elif text_align == 4:  # center
                text_pos.setX(text_pos.x() - text_width*0.5)
            if text_baseline == 1:  # top
                text_pos.setY(text_pos.y() + fm.ascent())
            elif text_baseline == 2:  # hanging
                text_pos.setY(text_pos.y() + 2 * fm.ascent() - fm.height())
            elif text_baseline == 3:  # middle
                text_pos.setY(text_pos.y() + fm.xHeight() * 0.5)
            elif text_baseline == 4 or text_baseline == 5:  # alphabetic or ideographic
                text_pos.setY(text_pos.y())
            elif text_baseline == 5:  # bottom
                text_pos.setY(text_pos.y() + fm.ascent() - fm.height())
            path = QtGui.QPainterPath()
            path.addText(text_pos, text_font, text)
            if cmd == "fillText":
                brush = QtGui.QBrush(gradients[fill_gradient]) if fill_gradient >= 0 else QtGui.QBrush(fill_color)
                painter.fillPath(path, brush)
            else:
                pen = QtGui.QPen(line_color)
                pen.setWidth(line_width * display_scaling)
                pen.setJoinStyle(line_join)
                pen.setCapStyle(line_cap)
                painter.strokePath(path, pen)
        elif cmd == "font":
            text_font = ParseFontString(args[0], display_scaling)
        elif cmd == "textAlign":
            if args[0] == "start":
                text_align = 1
            if args[0] == "end":
                text_align = 2
            if args[0] == "left":
                text_align = 3
            if args[0] == "center":
                text_align = 4
            if args[0] == "right":
                text_align = 5
        elif cmd == "textBaseline":
            if args[0] == "top":
                text_baseline = 1
            if args[0] == "hanging":
                text_baseline = 2
            if args[0] == "middle":
                text_baseline = 3
            if args[0] == "alphabetic":
                text_baseline = 4
            if args[0] == "ideographic":
                text_baseline = 5
            if args[0] == "bottom":
                text_baseline = 6
        elif cmd == "strokeStyle":
            color_arg = args[0].strip()
            re1 = QtCore.QRegExp("^rgba\\(([0-9]+),\\s*([0-9]+),\\s*([0-9]+),\\s*([0-9.]+)\\)$")
            re2 = QtCore.QRegExp("^rgb\\(([0-9]+),\\s*([0-9]+),\\s*([0-9]+)\\)$")
            pos1 = re1.indexIn(color_arg)
            pos2 = re2.indexIn(color_arg)
            if pos1 > -1:
                line_color = QtGui.QColor(int(re1.cap(1)), int(re1.cap(2)), int(re1.cap(3)), int(float(re1.cap(4)) * 255))
            elif pos2 > -1:
                line_color = QtGui.QColor(int(re2.cap(1)), int(re2.cap(2)), int(re2.cap(3)))
            else:
                line_color = QtGui.QColor(color_arg)
        elif cmd == "lineDash":
            line_dash = args[0]
        elif cmd == "lineWidth":
            line_width = args[0]
        elif cmd == "lineCap":
            if args[0] == "square":
                line_cap = QtCore.Qt.SquareCap
            if args[0] == "round":
                line_cap = QtCore.Qt.RoundCap
            if args[0] == "butt":
                line_cap = QtCore.Qt.FlatCap
        elif cmd == "lineJoin":
            if args[0] == "round":
                line_join = QtCore.Qt.RoundJoin
            if args[0] == "miter":
                line_join = QtCore.Qt.MiterJoin
            if args[0] == "bevel":
                line_join = QtCore.Qt.BevelJoin
        elif cmd == "gradient":
            gradients[args[0]] = QtGui.QLinearGradient(args[3] * display_scaling, args[4] * display_scaling, args[3] * display_scaling + args[5] * display_scaling, args[4] * display_scaling + args[6] * display_scaling)
        elif cmd == "colorStop":
            gradients[args[0]].setColorAt(args[1], QtGui.QColor(args[2]))
        elif cmd == "sleep":
            duration = args[0] * 1000000
            QtCore.QThread.usleep(duration)
        elif cmd == "latency":
            if g_timer is None:
                g_timer = QtCore.QElapsedTimer()
            print(f"Latency {g_timer.nsecsElapsed() - (args[0] * 1E9 - g_timer_offset_ns) / 1E6}ms")
        elif cmd == "message":
            print(args[0])
        elif cmd == "timestamp":
            text = args[0]
            date_time = QtCore.QDateTime.fromString(text, QtCore.Qt.ISODateWithMs)
            painter.save()
            date_time.setTimeSpec(QtCore.Qt.UTC)
            text_pos = QtCore.QPointF(12, 12)
            text_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            fm = QtGui.QFontMetrics(text_font)
            text_width = fm.width(text)
            text_ascent = fm.ascent()
            text_height = fm.height()
            background = QtGui.QPainterPath()
            background.addRect(text_pos.x() - 4, text_pos.y() - 4, text_width + 8, text_height + 8)
            painter.fillPath(background, QtCore.Qt.white)
            path = QtGui.QPainterPath()
            path.addText(text_pos.x(), text_pos.y() + text_ascent, text_font, text)
            painter.fillPath(path, QtCore.Qt.black)
            painter.restore()
            transform = painter.transform()
            for p in reversed(painter_stack):
                transform = p.transform() * transform
            rendered_timestamps.append(RenderedTimestamp(transform, date_time, section_id))
        elif cmd == "begin_layer":
            layer_id = int(args[0])
            layer_seed = int(args[1])
            layer_rect = QtCore.QRect(int(args[3] * display_scaling), int(args[2] * display_scaling), int(args[5] * display_scaling), int(args[4] * display_scaling))
            layer_skip_stack.append(layer_skip)
            if not layer_skip:
                if layer_cache and layer_id in layer_cache and layer_seed == layer_cache[layer_id].layer_seed:
                    layer_skip = True
                else:
                    painter_stack.append(painter)
                    layer_image_stack.append(layer_image)
                    layer_image = QtGui.QImage(layer_rect.size(), QtGui.QImage.Format_ARGB32)
                    layer_image.fill(QtGui.QColor(0,0,0,0))
                    painter = QtGui.QPainter(layer_image)
                    painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing | QtGui.QPainter.HighQualityAntialiasing)
                    painter.translate(layer_rect.left(), layer_rect.top())
            layers_used.add(layer_id)
        elif cmd == "end_layer":
            layer_id = int(args[0])
            layer_seed = int(args[1])
            layer_rect = QtCore.QRect(int(args[3] * display_scaling), int(args[2] * display_scaling), int(args[5] * display_scaling), int(args[4] * display_scaling))
            layer_skip = layer_skip_stack.pop()
            if not layer_skip:
                assert layer_cache is not None
                if layer_id in layer_cache and layer_seed == layer_cache[layer_id].layer_seed:
                    layer_image_to_draw = layer_cache[layer_id].layer_image
                    layer_rect = layer_cache[layer_id].layer_rect
                    painter.drawImage(layer_rect, layer_image_to_draw)
                else:
                    painter.end()
                    layer_cache[layer_id] = LayerCacheEntry(layer_seed, layer_image, layer_rect)
                    painter = painter_stack.pop()
                    painter.drawImage(layer_rect, layer_image)
                    layer_image = layer_image_stack.pop()

    if image_cache is not None:
        for image_id, entry in copy.copy(image_cache).items():
            if not entry.used:
                del image_cache[image_id]

    if layer_cache is not None:
        for layer_id in copy.copy(list(layer_cache.keys())):
            if not layer_id in layers_used:
                del layer_cache[layer_id]

    return rendered_timestamps


class PyCanvasRenderTaskSignals(QtCore.QObject):

    renderingReady = Signal(QtCore.QRect)


class PyCanvasRenderTask(QtCore.QRunnable):

    def __init__(self, canvas: "PyCanvas"):
        super().__init__()
        self.__canvas = canvas
        self.signals = PyCanvasRenderTaskSignals()

    def run(self):
        repaint_rect = self.__canvas.render_one()
        if repaint_rect is not None:
            self.signals.renderingReady.emit(repaint_rect)


class PyCanvas(QtWidgets.QWidget):

    def __init__(self) -> None:
        super().__init__()
        self.object = None
        self.__pressed = False
        self.__grab_mouse_count = 0
        self.__known_dts: typing.Dict[str, _QtObject] = dict()
        self.__commands_mutex = QtCore.QMutex()
        self.__sections: typing.Dict[int, PyCanvas.CanvasSection] = dict()
        self.__last_pos = QtCore.QPoint()
        self.__grab_reference_point = QtCore.QPoint()
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def repaint_rect(self, rect: QtCore.QRect) -> None:
        self.update(rect)

    def focusInEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusIn()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if self.object:
            try:
                self.object.focusOut()
            except Exception as e:
                import traceback
                traceback.print_exc()
        super().focusOutEvent(event)

    def render_one(self) -> typing.Optional[QtCore.QRect]:
        rect = None
        with QtCore.QMutexLocker(self.__commands_mutex):
            sections = list(self.__sections.values())
        next_section = None
        for section in sections:
            with QtCore.QMutexLocker(section.mutex):
                # first check whether the section can be rendered (not rendering already and has commands to render)
                if not section.rendering and section.commands:
                    # next check whether it is earlier than the current next_section
                    # if so, make this the new next section
                    if next_section is None or section.time < next_section.time:
                        next_section = section
        if next_section:
            with QtCore.QMutexLocker(next_section.mutex):
                # mark this section as being rendered, but check to make sure it's not being rendered
                # on another thread (avoids race condition). also check to see if it was deleted.
                if not next_section.rendering and next_section.commands:
                    next_section.rendering = True
                else:
                    return None
            rect = self.render_section(next_section)
            with QtCore.QMutexLocker(next_section.mutex):
                # mark this section as being finished. no race condition. just clear it and update the time.
                next_section.rendering = False
                next_section.time = time.perf_counter()
            self.wakeRenderer()
        return rect

    def render_section(self, section) -> typing.Optional[QtCore.QRect]:
        with QtCore.QMutexLocker(section.mutex):
            commands = section.commands
            rect = section.rect
            section_id = section.section_id
            section.commands = None
            section.rect = None
        if commands and rect:
            image = QtGui.QImage(rect.size(), QtGui.QImage.Format_ARGB32)
            image.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter()
            painter.begin(image)
            try:
                painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing | QtGui.QPainter.HighQualityAntialiasing)
                rendered_timestamps = PaintCommands(painter, commands, section.image_cache, layer_cache=section.layer_cache, section_id=section_id)
            finally:
                painter.end()

            with QtCore.QMutexLocker(section.mutex):
                section.image = image
                section.image_rect = rect
                section.rendered_timestamps = list()
                for rendered_timestamp in rendered_timestamps:
                    transform = rendered_timestamp.transform
                    transform.translate(rect.left(), rect.top())
                    section.rendered_timestamps.append(RenderedTimestamp(transform, rendered_timestamp.timestamp, rendered_timestamp.section_id))
        return rect

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter()
        painter.begin(self)
        try:
            with QtCore.QMutexLocker(self.__commands_mutex):
                sections = list(self.__sections.values())
            for section in sections:
                with QtCore.QMutexLocker(section.mutex):
                    image = section.image
                    image_rect = section.image_rect
                    rendered_timestamps = section.rendered_timestamps
                if image and image_rect.intersects(event.rect()):
                    painter.drawImage(image_rect.topLeft(), image)

                known_dts = self.__known_dts
                self.__known_dts.clear()

                for rendered_timestamp in rendered_timestamps:
                    painter.save()
                    painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing | QtGui.QPainter.HighQualityAntialiasing)
                    dt = rendered_timestamp.timestamp
                    utc = known_dts.get(dt, QtCore.QDateTime.currentDateTimeUtc())
                    self.__known_dts[dt] = utc
                    millisecondsDiff = dt.msecsTo(utc)
                    latency_average = 0
                    if rendered_timestamp.section_id > 0:
                        with QtCore.QMutexLocker(self.__commands_mutex):
                            section = self.__sections[rendered_timestamp.section_id]
                        with QtCore.QMutexLocker(section.latencies_mutex):
                            section.latencies.append(millisecondsDiff)
                            if len(section.latencies) > 100:
                                section.latencies.pop(0)
                            for latency in section.latencies:
                                latency_average += latency
                            latency_average //= len(section.latencies)
                    text = "Latency " + str(millisecondsDiff)
                    if latency_average > 0:
                        text += " [" + str(latency_average) + "]"
                    text_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
                    fm = QtGui.QFontMetrics(text_font)
                    text_width = fm.width(text)
                    text_ascent = fm.ascent()
                    text_height = fm.height()
                    text_pos = QtCore.QPointF(12, 12 + text_height + 16)
                    world_transform = rendered_timestamp.transform
                    painter.setWorldTransform(world_transform)
                    background = QtGui.QPainterPath()
                    background.addRect(text_pos.x() - 4, text_pos.y() - 4, text_width + 8, text_height + 8)
                    painter.fillPath(background, QtCore.Qt.white)
                    path = QtGui.QPainterPath()
                    path.addText(text_pos.x(), text_pos.y() + text_ascent, text_font, text)
                    painter.fillPath(path, QtCore.Qt.black)
                    painter.restore()
        finally:
            painter.end()

    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Gesture:
            gesture_event = event
            pan_gesture = gesture_event.gesture(QtCore.Qt.PanGesture)
            if pan_gesture is not None:
                display_scaling = GetDisplayScaling()
                try:
                    if self.object and self.object.panGesture(pan_gesture.delta().x() / display_scaling, pan_gesture.delta().y() / display_scaling):
                        return True
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        if event.type() == QtCore.QEvent.ToolTip:
            display_scaling = GetDisplayScaling()
            try:
                if self.object and self.object.helpEvent(event.pos().x() // display_scaling, event.pos().y() // display_scaling, event.globalPos().x() // display_scaling, event.globalPos().y() // display_scaling):
                    return True
            except Exception as e:
                import traceback
                traceback.print_exc()
        return super().event(event)

    def enterEvent(self, event: QtCore.QEvent) -> None:
        if self.object:
            try:
                self.object.mouseEntered()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if self.object:
            try:
                self.object.mouseExited()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.object and event.button() == QtCore.Qt.LeftButton:
            display_scaling = GetDisplayScaling()
            try:
                self.object.mousePressed(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
            except Exception as e:
                import traceback
                traceback.print_exc()
            self.__last_pos = event.pos()
            self.__pressed = True

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.object and event.button() == QtCore.Qt.LeftButton:
            display_scaling = GetDisplayScaling()
            try:
                self.object.mouseReleased(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
            except Exception as e:
                import traceback
                traceback.print_exc()
            self.__pressed = False
            if (event.pos() - self.__last_pos).manhattanLength() < 6 * display_scaling:
                try:
                    self.object.mouseClicked(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
                except Exception as e:
                    import traceback
                    traceback.print_exc()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.object and event.button() == QtCore.Qt.LeftButton:
            display_scaling = GetDisplayScaling()
            try:
                self.object.mouseDoubleClicked(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
            except Exception as e:
                import traceback
                traceback.print_exc()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.object:
            display_scaling = GetDisplayScaling()

            if self.__grab_mouse_count > 0:
                delta = event.pos() - self.__grab_reference_point
                try:
                    self.object.grabbedMousePositionChanged(delta.x() // display_scaling, delta.y() // display_scaling, event.modifiers())
                except Exception as e:
                    import traceback
                    traceback.print_exc()

            try:
                self.object.mousePositionChanged(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
            except Exception as e:
                import traceback
                traceback.print_exc()

            # handle case of not getting mouse released event after drag.
            if self.__pressed and (event.buttons() & QtCore.Qt.LeftButton == 0):
                try:
                    self.object.mouseReleased(event.x() // display_scaling, event.y() // display_scaling, event.modifiers())
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                self.__pressed = False

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self.object:
            wheel_event = event
            is_horizontal = wheel_event.angleDelta().x() != 0
            delta = wheel_event.angleDelta() if wheel_event.pixelDelta().isNull() else wheel_event.pixelDelta()
            display_scaling = GetDisplayScaling()
            try:
                self.object.wheelChanged(wheel_event.x() // display_scaling, wheel_event.y() // display_scaling, delta.x() / display_scaling, delta.y() // display_scaling, is_horizontal)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.sizeChanged(int(event.size().width() / display_scaling), int(event.size().height() / display_scaling))
            except Exception as e:
                import traceback
                traceback.print_exc()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.type() == QtCore.QEvent.KeyPress:
            if self.object:
                try:
                    if self.object.keyPressed(event.text(), event.key(), event.modifiers()):
                        event.accept()
                        return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.type() == QtCore.QEvent.KeyRelease:
            if self.object:
                try:
                    if self.object.keyReleased(event.text(), event.key(), event.modifiers()):
                        event.accept()
                        return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        super().keyReleaseEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                self.object.contextMenuEvent(event.pos().x() // display_scaling, event.pos().y() // display_scaling, event.globalPos().x() // display_scaling, event.globalPos().y() // display_scaling)
            except Exception as e:
                import traceback
                traceback.print_exc()

    def grabMouse0(self, gp: QtCore.QPoint) -> None:
        grab_mouse_count = self.__grab_mouse_count
        self.__grab_mouse_count += 1
        if grab_mouse_count == 0:
            self.grabMouse()
            self.grabKeyboard()
            self.__grab_reference_point = gp
            QtGui.QCursor.setPos(gp)
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BlankCursor)

    def releaseMouse0(self) -> None:
        self.__grab_mouse_count -= 1
        if self.__grab_mouse_count == 0:
            self.releaseMouse()
            self.releaseKeyboard()
            QtWidgets.QApplication.restoreOverrideCursor()

    class CanvasSection:
        def __init__(self, section_id: int, commands: typing.List[CanvasDrawingCommand], rect: QtCore.QRect):
            self.section_id = section_id
            self.mutex = QtCore.QMutex()
            self.commands = commands
            self.rect = rect
            self.image_rect = None
            self.image = None
            self.image_cache: typing.Dict[int, PaintImageCacheEntry] = dict()
            self.layer_cache: typing.Dict[int, LayerCacheEntry] = dict()
            self.rendered_timestamps: typing.List[RenderedTimestamp] = list()
            self.rendering = False
            self.time = 0.0
            self.latencies_mutex = QtCore.QMutex()
            self.latencies: typing.List[int] = list()

    def setCommands(self, commands: typing.List[CanvasDrawingCommand]) -> None:
        self.setSectionCommands(0, commands, 0, 0, self.width(), self.height())

    def setSectionCommands(self, section_id: int, commands: typing.List[CanvasDrawingCommand], left: int, top: int, width: int, height: int) -> None:
        display_scaling = GetDisplayScaling()
        with QtCore.QMutexLocker(self.__commands_mutex):
            rect = QtCore.QRect(left * display_scaling, top * display_scaling, width * display_scaling, height * display_scaling)
            section = self.__sections.setdefault(section_id, PyCanvas.CanvasSection(section_id, commands, rect))
        with QtCore.QMutexLocker(section.mutex):
            section.commands = commands
            section.rect = rect
        self.wakeRenderer()

    def wakeRenderer(self) -> None:
        task = PyCanvasRenderTask(self)
        task.signals.renderingReady.connect(self.repaint_rect)
        QtCore.QThreadPool.globalInstance().start(task)

    def removeSection(self, section_id: int) -> None:
        with QtCore.QMutexLocker(self.__commands_mutex):
            self.__sections.pop(section_id, None)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if self.object:
            try:
                action = self.object.dragEnterEvent(event.mimeData())
            except Exception as e:
                import traceback
                traceback.print_exc()
                action = "ignore"
            if action == "copy":
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()
            elif action == "move":
                event.setDropAction(QtCore.Qt.MoveAction)
                event.accept()
            elif action == "accept":
                event.accept()
            else:
                super().dragEnterEvent(event)
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:
        if self.object:
            try:
                action = self.object.dragLeaveEvent()
            except Exception as e:
                import traceback
                traceback.print_exc()
                action = "ignore"
            if action == "accept":
                event.accept()
            else:
                super().dragLeaveEvent(event)
        else:
            super().dragLeaveEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                action = self.object.dragMoveEvent(event.mimeData(), event.pos().x() // display_scaling, event.pos().y() // display_scaling)
            except Exception as e:
                import traceback
                traceback.print_exc()
                action = "ignore"
            if action == "copy":
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()
            elif action == "move":
                event.setDropAction(QtCore.Qt.MoveAction)
                event.accept()
            elif action == "accept":
                event.accept()
            else:
                super().dragMoveEvent(event)
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if self.object:
            display_scaling = GetDisplayScaling()
            try:
                action = self.object.dropEvent(event.mimeData(), event.pos().x() // display_scaling, event.pos().y() // display_scaling)
            except Exception as e:
                import traceback
                traceback.print_exc()
                action = "ignore"
            if action == "copy":
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()
            elif action == "move":
                event.setDropAction(QtCore.Qt.MoveAction)
                event.accept()
            elif action == "accept":
                event.accept()
            else:
                super().dropEvent(event)
        else:
            super().dropEvent(event)


class PyDrawingContext(QtCore.QObject):

    def __init__(self, painter: QtGui.QPainter):
        super().__init__()
        self.object = None
        self.__painter = painter
        self.__image_cache: typing.Dict[int, PaintImageCacheEntry] = dict()

    def paintCommands(self, commands: typing.List[CanvasDrawingCommand]) -> None:
        PaintCommands(self.__painter, commands, self.__image_cache)


class PyQtProxy:

    def __init__(self) -> None:
        self.__timer = QtCore.QElapsedTimer()
        self.__timer_offset_ns = 0

        # we try to set up std out catching as soon as possible
        # we call this from HostLib, so we should be able to import
        # this safely
        class StdoutCatcher:

            def __init__(self) -> None:
                pass

            def write(self, stuff):
                out_str = str(stuff) if stuff is not None else str()
                logging.info(out_str)

            def flush(self):
                pass

        sys.stdout = StdoutCatcher()  # type: ignore
        sys.stderr = sys.stdout

    def has_method(self, name: str) -> bool:
        return hasattr(self, name)

    # main event loop

    def run(self, application):
        global app
        app = PyApplication(application, [])

        if application.start():
            return app.exec_()

        return None

    # conversions

    def convert_drawing_commands(self, commands):
        return commands

    def decode_data(self, data):
        return data

    def decode_font_metrics(self, font_metrics):
        from nion.ui import UserInterface
        return UserInterface.FontMetrics(width=font_metrics[0], height=font_metrics[1], ascent=font_metrics[2], descent=font_metrics[3], leading=font_metrics[4])

    def encode_data(self, data):
        return data

    def encode_text(self, text):
        return str(text) if text else str()

    def encode_variant(self, value):
        return value

    # methods

    def Action_connect(self, action: PyAction, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        assert object is not None
        action.object = object

    def Action_create(self, document_window: PyDocumentWindow, title: str, key_sequence: str, role: str) -> PyAction:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        action = PyAction(document_window)
        action.setText(title)
        if key_sequence:
            if key_sequence == "new":
                action.setShortcut(QtGui.QKeySequence.New)
            elif key_sequence == "open":
                action.setShortcut(QtGui.QKeySequence.Open)
            elif key_sequence == "close":
                action.setShortcut(QtGui.QKeySequence.Close)
            elif key_sequence == "save":
                action.setShortcut(QtGui.QKeySequence.Save)
            elif key_sequence == "save-as":
                action.setShortcut(QtGui.QKeySequence.SaveAs)
            elif key_sequence == "quit":
                action.setShortcut(QtGui.QKeySequence.Quit)
            elif key_sequence == "undo":
                action.setShortcut(QtGui.QKeySequence.Undo)
            elif key_sequence == "redo":
                action.setShortcut(QtGui.QKeySequence.Redo)
            elif key_sequence == "cut":
                action.setShortcut(QtGui.QKeySequence.Cut)
            elif key_sequence == "copy":
                action.setShortcut(QtGui.QKeySequence.Copy)
            elif key_sequence == "paste":
                action.setShortcut(QtGui.QKeySequence.Paste)
            elif key_sequence == "delete":
                action.setShortcut(QtGui.QKeySequence.Delete)
            elif key_sequence == "select-all":
                action.setShortcut(QtGui.QKeySequence.SelectAll)
            elif key_sequence == "help":
                action.setShortcut(QtGui.QKeySequence.HelpContents)
            else:
                action.setShortcut(QtGui.QKeySequence(key_sequence))

        if role:
            if role == "preferences":
                action.setMenuRole(QtWidgets.QAction.PreferencesRole)
            elif role == "about":
                action.setMenuRole(QtWidgets.QAction.AboutRole)
            elif role == "application":
                action.setMenuRole(QtWidgets.QAction.ApplicationSpecificRole)
            elif role == "quit":
                action.setMenuRole(QtWidgets.QAction.QuitRole)

        return action

    def Action_getChecked(self, action: PyAction) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        return action.isChecked()

    def Action_getEnabled(self, action: PyAction) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        return action.isEnabled()

    def Action_getTitle(self, action: PyAction) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        return action.text()

    def Action_setChecked(self, action: PyAction, checked: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        action.setCheckable(checked)
        action.setChecked(checked)

    def Action_setEnabled(self, action: PyAction, enabled: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        action.setEnabled(enabled)

    def Action_setTitle(self, action: PyAction, title: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert action is not None
        action.setText(title)

    def Application_close(self) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        app.closeAllWindows()
        app.quit()

    def Application_getKeyboardModifiers(self, query: bool) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        return app.queryKeyboardModifiers() if query else app.keyboardModifiers()

    def ButtonGroup_addButton(self, button_group: PyButtonGroup, radio_button: PyRadioButton, button_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert button_group is not None
        button_group.addButton(radio_button, button_id)

    def ButtonGroup_connect(self, button_group: PyButtonGroup, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert button_group is not None
        assert object is not None
        button_group.object = object

    def ButtonGroup_checkedButton(self, button_group: PyButtonGroup) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert button_group is not None
        return button_group.checkedId()

    def ButtonGroup_create(self) -> PyButtonGroup:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        return PyButtonGroup()

    def ButtonGroup_destroy(self, button_group: PyButtonGroup) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert button_group is not None
        button_group.deleteLater()

    def ButtonGroup_removeButton(self, button_group: PyButtonGroup, radio_button: PyRadioButton) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert button_group is not None
        button_group.removeButton(radio_button)

    def Canvas_connect(self, canvas: PyCanvas, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert canvas is not None
        assert object is not None
        canvas.object = object

    def Canvas_draw(self, canvas: PyCanvas, commands: list, storage) -> None:
        assert canvas is not None
        drawing_commands = list()
        for command in commands:
            drawing_commands.append(CanvasDrawingCommand(command[0], command[1:]))
        canvas.setCommands(drawing_commands)

    def Canvas_drawSection(self, canvas: PyCanvas, section_id, commands: list, storage, left, top, width, height) -> None:
        assert canvas is not None
        drawing_commands = list()
        for command in commands:
            drawing_commands.append(CanvasDrawingCommand(command[0], command[1:]))
        canvas.setSectionCommands(section_id, drawing_commands, left, top, width, height)

    def Canvas_grabMouse(self, canvas: PyCanvas, gx: int, gy: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert canvas is not None
        display_scaling = GetDisplayScaling()
        canvas.grabMouse0(QtCore.QPoint(gx * display_scaling, gy * display_scaling))

    def Canvas_releaseMouse(self, canvas: PyCanvas) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert canvas is not None
        canvas.releaseMouse0()

    def Canvas_removeSection(self, canvas: PyCanvas, section_id: int) -> None:
        canvas.removeSection(section_id)

    def Canvas_setCursorShape(self, canvas: PyCanvas, shape_id: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert canvas is not None

        cursor_shape = QtCore.Qt.CursorShape(QtCore.Qt.ArrowCursor)

        if shape_id == "arrow":
            cursor_shape = QtCore.Qt.ArrowCursor
        elif shape_id == "up_arrow":
            cursor_shape = QtCore.Qt.UpArrowCursor
        elif shape_id == "cross":
            cursor_shape = QtCore.Qt.CrossCursor
        elif shape_id == "wait":
            cursor_shape = QtCore.Qt.WaitCursor
        elif shape_id == "ibeam":
            cursor_shape = QtCore.Qt.IBeamCursor
        elif shape_id == "wait":
            cursor_shape = QtCore.Qt.WaitCursor
        elif shape_id == "size_vertical":
            cursor_shape = QtCore.Qt.SizeVerCursor
        elif shape_id == "size_horizontal":
            cursor_shape = QtCore.Qt.SizeHorCursor
        elif shape_id == "size_backward_diagonal":
            cursor_shape = QtCore.Qt.SizeBDiagCursor
        elif shape_id == "size_forward_diagonal":
            cursor_shape = QtCore.Qt.SizeFDiagCursor
        elif shape_id == "blank":
            cursor_shape = QtCore.Qt.BlankCursor
        elif shape_id == "split_vertical":
            cursor_shape = QtCore.Qt.SplitVCursor
        elif shape_id == "split_horizontal":
            cursor_shape = QtCore.Qt.SplitHCursor
        elif shape_id == "pointing_hand":
            cursor_shape = QtCore.Qt.PointingHandCursor
        elif shape_id == "forbidden":
            cursor_shape = QtCore.Qt.ForbiddenCursor
        elif shape_id == "hand":
            cursor_shape = QtCore.Qt.OpenHandCursor
        elif shape_id == "closed_hand":
            cursor_shape = QtCore.Qt.ClosedHandCursor
        elif shape_id == "question":
            cursor_shape = QtCore.Qt.WhatsThisCursor
        elif shape_id == "busy":
            cursor_shape = QtCore.Qt.BusyCursor
        elif shape_id == "move":
            cursor_shape = QtCore.Qt.DragMoveCursor
        elif shape_id == "copy":
            cursor_shape = QtCore.Qt.DragCopyCursor
        elif shape_id == "link":
            cursor_shape = QtCore.Qt.DragLinkCursor

        canvas.setCursor(QtGui.QCursor(cursor_shape))

    def CheckBox_connect(self, check_box: PyCheckBox, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        check_box.object = object

    def CheckBox_getCheckState(self, check_box: PyCheckBox) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        return ["unchecked", "partial", "checked"][check_box.checkState()]

    def CheckBox_getIsTristate(self, check_box: PyCheckBox) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        return check_box.isTristate()

    def CheckBox_setCheckState(self, check_box: PyCheckBox, check_state: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        if check_state == "checked":
            check_box.setCheckState(QtCore.Qt.Checked)
        elif check_state == "partial":
            check_box.setCheckState(QtCore.Qt.PartiallyChecked)
        else:
            check_box.setCheckState(QtCore.Qt.Unchecked)

    def CheckBox_setIsTristate(self, check_box: PyCheckBox, tristate: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        check_box.setTristate(tristate)

    def CheckBox_setText(self, check_box: PyCheckBox, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert check_box is not None
        check_box.setText(text)

    def Clipboard_clear(self) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear()

    def Clipboard_mimeData(self) -> QtCore.QMimeData:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        clipboard = QtWidgets.QApplication.clipboard()
        return clipboard.mimeData()

    def Clipboard_setMimeData(self, mime_data: QtCore.QMimeData) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setMimeData(mime_data)

    def Clipboard_setText(self, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)

    def Clipboard_text(self) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        clipboard = QtWidgets.QApplication.clipboard()
        return clipboard.text()

    def ComboBox_addItem(self, combobox: PyComboBox, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert combobox is not None
        combobox.addItem(text)

    def ComboBox_connect(self, combobox: PyComboBox, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert combobox is not None
        combobox.object = object

    def ComboBox_getCurrentText(self, combobox) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert combobox is not None
        return combobox.currentText()

    def ComboBox_removeAllItems(self, combobox) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert combobox is not None
        while combobox.count() > 0:
            combobox.removeItem(0)

    def ComboBox_setCurrentText(self, combobox: PyComboBox, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert combobox is not None
        combobox.setCurrentText(text)

    def Core_getFontMetrics(self, font_str: str, text: str) -> typing.Tuple[int, int, int, int, int]:
        text = text if text else str()
        display_scaling = GetDisplayScaling()
        font = ParseFontString(font_str, display_scaling)
        font_metrics = QtGui.QFontMetrics(font)
        return font_metrics.width(text) / display_scaling, font_metrics.height() / display_scaling, font_metrics.ascent() / display_scaling, font_metrics.descent() / display_scaling, font_metrics.leading() / display_scaling

    def Core_getQtVersion(self) -> str:
        return QtCore.qVersion()

    def Core_getLocation(self, location_id: str) -> str:
        location = QtCore.QStandardPaths.DocumentsLocation
        if location_id == "data":
            location = QtCore.QStandardPaths.AppDataLocation
        elif location_id == "documents":
            location = QtCore.QStandardPaths.DocumentsLocation
        elif location_id == "temporary":
            location = QtCore.QStandardPaths.TempLocation
        elif location_id == "configuration":
            location = QtCore.QStandardPaths.AppConfigLocation
        dir = QtCore.QDir(QtCore.QStandardPaths.writableLocation(location))
        data_location = dir.absolutePath()
        QtCore.QDir().mkpath(data_location)
        return data_location

    def Core_out(self, output: str) -> None:
        output_stripped = output.strip()
        if output_stripped:
            print(output_stripped)

    def Core_pathToURL(self, path: str) -> str:
        return QtCore.QUrl.fromLocalFile(path).toString()

    def Core_readImageToBinary(self, filename: str) -> typing.Optional[numpy.ndarray]:
        reader = QtGui.QImageReader(filename)
        if reader.canRead():
            image = reader.read()
            if image.format() != QtGui.QImage.Format_ARGB32_Premultiplied:
                image = image.convertToFormat(QtGui.QImage.Format_ARGB32_Premultiplied)
                b = image.bits()
                # sip.voidptr must know size to support python buffer interface
                b.setsize(image.size().width() * image.size().height() * 4)
                return numpy.copy(numpy.frombuffer(b, numpy.uint32).reshape((image.size().height(), image.size().width())))
        return None

    def Core_setApplicationInfo(self, application_name: str, organization_name: str, organization_domain: str):
        QtWidgets.QApplication.setApplicationName(application_name)
        QtWidgets.QApplication.setOrganizationName(organization_name)
        QtWidgets.QApplication.setOrganizationDomain(organization_domain)

    def Core_syncLatencyTimer(self, value):
        self.__timer_offset_ns = value * 1E9 - self.__timer.nsecsElapsed()
        return self.__timer.nsecsElapsed()

    def Core_truncateToWidth(self, font_str: str, text: str, pixel_width: int, mode: int) -> str:
        text = text if text else str()
        display_scaling = GetDisplayScaling()
        font = ParseFontString(font_str, display_scaling)
        font_metrics = QtGui.QFontMetrics(font)
        mapping = {
            0: QtCore.Qt.ElideLeft,
            1: QtCore.Qt.ElideRight,
            2: QtCore.Qt.ElideMiddle,
            3: QtCore.Qt.ElideNone
        }
        return font_metrics.elidedText(text, mapping[mode], pixel_width)

    def Core_URLToPath(self, url: str) -> str:
        qurl = QtCore.QUrl(url)
        file_path = qurl.toLocalFile()
        return file_path

    def Core_writeBinaryToImage(self, w: int, h: int, array: numpy.ndarray, filename: str, format: str) -> None:
        image = imageFromRGBA(array)
        assert not image.isNull()
        writer = QtGui.QImageWriter(filename, format.encode('utf-8'))
        if writer.canWrite():
            writer.write(image)

    def DockWidget_connect(self, dock_widget: DockWidget, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert dock_widget is not None
        assert object is not None
        dock_widget.object = object

    def DockWidget_getToggleAction(self, dock_widget: DockWidget) -> PyAction:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert dock_widget is not None
        return dock_widget.toggleViewAction()

    def DocumentWindow_activate(self, document_window: PyDocumentWindow) -> None:
        assert document_window is not None
        document_window.activateWindow()

    def DocumentWindow_addDockWidget(self, document_window: PyDocumentWindow, widget: QtWidgets.QWidget, identifier: str, title: str, allowed_positions: typing.List[str], position: str) -> DockWidget:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        mapping = {
            "top": QtCore.Qt.TopDockWidgetArea,
            "left": QtCore.Qt.LeftDockWidgetArea,
            "bottom": QtCore.Qt.BottomDockWidgetArea,
            "right": QtCore.Qt.RightDockWidgetArea,
            "all": QtCore.Qt.AllDockWidgetAreas,
            "none": QtCore.Qt.NoDockWidgetArea,
        }
        allowed_positions_mask = 0
        for allowed_position in allowed_positions:
            allowed_positions_mask |= mapping[allowed_position]
        allowed_positions_mask = QtCore.Qt.DockWidgetAreas(allowed_positions_mask)

        dock_widget = DockWidget(title, None)
        dock_widget.setAllowedAreas(allowed_positions_mask)
        dock_widget.setWidget(widget)
        dock_widget.setObjectName(identifier)
        document_window.addDockWidget(mapping[position], dock_widget)

        return dock_widget

    def DocumentWindow_addMenu(self, document_window: PyDocumentWindow, title: str) -> PyMenu:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        menu = PyMenu()
        menu.setTitle(title)
        document_window.menuBar().addMenu(menu)
        return menu

    def DocumentWindow_close(self, document_window: PyDocumentWindow) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.close()

    def DocumentWindow_connect(self, document_window: PyDocumentWindow, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        assert object is not None
        document_window.object = object
        document_window.initialize()

    def DocumentWindow_create(self, parent_window: PyDocumentWindow, title: str):
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        return PyDocumentWindow(title, parent_window)

    def DocumentWindow_getColorDialog(self, parent: QtWidgets.QWidget, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        q_color = QtGui.QColor(color)
        dialog = QtWidgets.QColorDialog(q_color, parent)
        if show_alpha:
            dialog.setOptions(QtWidgets.QColorDialog.ShowAlphaChannel)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            if dialog.selectedColor().alpha() != 255:
                return f"#{dialog.selectedColor().alpha():02x}{dialog.selectedColor().name()[1:]}"
            else:
                return dialog.selectedColor().name()
        return color

    def DocumentWindow_getDisplayScaling(self, document_window: PyDocumentWindow) -> None:
        assert document_window is not None
        if sys.platform == 'darwin':
            return document_window.logicalDpiY() / 72.0
        else:
            return document_window.logicalDpiY() / 96.0

    def DocumentWindow_getFilePath(self, document_window: PyDocumentWindow, mode: str, caption: str, dir: str, filter: str, selected_filter: str) -> typing.Optional[typing.Tuple[typing.Union[str, typing.List[str]], str, str]]:
        # simple wrapper for the QtFile dialogs. This way plugins can
        # display file dialogs when needed.
        # Args are document window, mode ("save" | "load" | "loadmany") , caption, dir, filter
        # returns the path or an empty string if the dialog was cancelled
        global app
        assert app.thread() == QtCore.QThread.currentThread()

        if mode == "save":
            selected_filter_ref = [selected_filter]
            selected_dir_ref = [QtCore.QDir(WorkingDirectory(dir))]
            # Python_ThreadAllow thread_allow;
            result = GetSaveFileName(document_window, caption, dir, filter, selected_filter_ref, selected_dir_ref)
            return result, selected_filter_ref[0], selected_dir_ref[0].absolutePath()
        elif mode == "load":
            selected_filter_ref = [selected_filter]
            selected_dir_ref = [QtCore.QDir(WorkingDirectory(dir))]
            # Python_ThreadAllow thread_allow;
            result = GetOpenFileName(document_window, caption, dir, filter, selected_filter_ref, selected_dir_ref)
            return result, selected_filter_ref[0], selected_dir_ref[0].absolutePath()
        elif mode == "directory":
            selected_dir_ref = [QtCore.QDir(WorkingDirectory(dir))]
            QtCore.QDir.setCurrent(dir)
            # Python_ThreadAllow thread_allow;
            directory = GetExistingDirectory(document_window, caption, dir, selected_dir_ref)
            return directory, str(), selected_dir_ref[0].absolutePath()
        elif mode == "loadmany":
            selected_filter_ref = [selected_filter]
            selected_dir_ref = [QtCore.QDir(WorkingDirectory(dir))]
            # Python_ThreadAllow thread_allow;
            file_names = GetOpenFileNames(document_window, caption, dir, filter, selected_filter_ref, selected_dir_ref)
            return file_names, str(), selected_dir_ref[0].absolutePath()
        # error
        return None

    def DocumentWindow_getScreenSize(self, document_window: PyDocumentWindow) -> typing.Tuple[int, int]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        size = document_window.windowHandle().screen().size()
        return size.width(), size.height()

    def DocumentWindow_insertMenu(self, document_window: PyDocumentWindow, title: str, before_menu: QtWidgets.QMenu) -> PyMenu:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        menu = PyMenu()
        menu.setTitle(title)
        document_window.menuBar().insertMenu(before_menu.menuAction(), menu)
        return menu

    def DocumentWindow_removeDockWidget(self, document_window: PyDocumentWindow, dock_widget: QtWidgets.QDockWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.removeDockWidget(dock_widget)

    def DocumentWindow_restore(self, document_window: PyDocumentWindow, geometry: str, state: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        # state, then geometry, otherwise the size isn't handled right. ugh.
        if state:
            document_window.restoreState(QtCore.QByteArray.fromHex(bytearray(state, "utf8")))
        if geometry:
            document_window.restoreGeometry(QtCore.QByteArray.fromHex(bytearray(geometry, "utf8")))

    def DocumentWindow_save(self, document_window: PyDocumentWindow) -> typing.Tuple[str, str]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        # state, then geometry, otherwise the size isn't handled right. ugh.
        geometry = document_window.saveGeometry().toHex().data().decode("utf8")
        state = document_window.saveState().toHex().data().decode("utf8")
        return geometry, state

    def DocumentWindow_setCentralWidget(self, document_window: PyDocumentWindow, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.setCentralWidget(widget)

    def DocumentWindow_setPosition(self, document_window: PyDocumentWindow, gx: int, gy: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        display_scaling = GetDisplayScaling()
        document_window.move(QtCore.QPoint(gx * display_scaling, gy * display_scaling))

    def DocumentWindow_setSize(self, document_window: PyDocumentWindow, width: int, height: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.resize(QtCore.QSize(width, height))

    def DocumentWindow_setTitle(self, document_window: PyDocumentWindow, title: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.setWindowTitle(title)

    def DocumentWindow_setWindowFilePath(self, document_window: PyDocumentWindow, window_file_path: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        document_window.setWindowFilePath(window_file_path)

    def DocumentWindow_setWindowStyle(self, document_window: PyDocumentWindow, styles: typing.Sequence[str]) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        style_mapping = {
            "dialog": QtCore.Qt.Dialog,
            "popup": QtCore.Qt.Popup,
            "tool": QtCore.Qt.Tool,
            "floating-hint": QtCore.Qt.WindowStaysOnTopHint,
            "frameless-hint": QtCore.Qt.FramelessWindowHint,
            "title-hint": QtCore.Qt.WindowTitleHint,
            "customize-hint": QtCore.Qt.CustomizeWindowHint,
            "close-button-hint": QtCore.Qt.WindowCloseButtonHint,
            "min-button-hint": QtCore.Qt.WindowMinimizeButtonHint,
            "max-button-hint": QtCore.Qt.WindowMaximizeButtonHint,
            "system-menu-hint": QtCore.Qt.WindowSystemMenuHint,
            "help-hint": QtCore.Qt.WindowContextHelpButtonHint,
            "fullscreen-hint": QtCore.Qt.WindowFullscreenButtonHint,
            "input-transparent": QtCore.Qt.WindowTransparentForInput,
            "no-focus": QtCore.Qt.WindowDoesNotAcceptFocus,
        }
        window_flags = 0
        for style in styles:
            window_flags |= style_mapping.get(style, 0)
        document_window.setWindowFlags(window_flags)

    def DocumentWindow_show(self, document_window: PyDocumentWindow, window_style: typing.Optional[str]) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert document_window is not None
        if window_style:
            assert window_style in ["window", "dialog", "popup", "mousegrab", "tool"]
        if window_style == "dialog":
            document_window.setWindowFlags(QtCore.Qt.Dialog)
        elif window_style == "popup":
            document_window.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        elif window_style == "mousegrab":
            document_window.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
            document_window.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        elif window_style == "tool":
            document_window.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        document_window.show()

    def Drag_connect(self, drag: PyDrag, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert drag is not None
        assert object is not None
        drag.object = object

    def Drag_create(self, widget: QtWidgets.QWidget, mime_data: QtCore.QMimeData) -> PyDrag:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        drag = PyDrag(widget)
        drag.setMimeData(mime_data)
        return drag

    def Drag_exec(self, drag: PyDrag) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert drag is not None
        QtCore.QTimer.singleShot(0, drag.execute)

    def Drag_setThumbnail(self, drag: PyDrag, w: int, h: int, thumbnail: numpy.ndarray, x: int, y: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert drag is not None
        assert thumbnail is not None
        image = imageFromRGBA(thumbnail)
        display_scaling = GetDisplayScaling()
        assert not image.isNull()
        drag.setPixmap(QtGui.QPixmap.fromImage(image))
        drag.setHotSpot(QtCore.QPoint(int(x * display_scaling), int(y * display_scaling)))

    def DrawingContext_drawCommands(self, drawing_context: PyDrawingContext, commands: list) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert drawing_context is not None
        drawing_commands = list()
        for command in commands:
            drawing_commands.append(CanvasDrawingCommand(command[0], command[1:]))
        drawing_context.paintCommands(drawing_commands)

    def DrawingContext_paintRGBA(self, commands: list, width: int, height: int) -> typing.Optional[numpy.ndarray]:
        image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
        image.fill(QtGui.QColor(0,0,0,0))
        image_cache: typing.Dict[int, PaintImageCacheEntry] = dict()
        drawing_commands = list()
        for command in commands:
            drawing_commands.append(CanvasDrawingCommand(command[0], command[1:]))
        painter = QtGui.QPainter()
        painter.begin(image)
        try:
            PaintCommands(painter, drawing_commands, image_cache, 1.0)
        finally:
            painter.end()
        if image.format() != QtGui.QImage.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QtGui.QImage.Format_ARGB32_Premultiplied)
            b = image.bits()
            # sip.voidptr must know size to support python buffer interface
            if hasattr(b, "setsize"):
                b.setsize(image.size().width() * image.size().height() * 4)
            return numpy.copy(numpy.frombuffer(b, numpy.uint32).reshape((image.size().height(), image.size().width())))
        return None

    def GroupBoxWidget_setTitle(self, group_box: QtWidgets.QGroupBox, title: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert group_box is not None
        group_box.setTitle(title)

    def ItemModel_beginInsertRows(self, item_model: ItemModel, first_index: int, last_index: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.beginInsertRowsInParent(first_index, last_index, parent_row, parent_item_id)

    def ItemModel_beginRemoveRows(self, item_model: ItemModel, first_index: int, last_index: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.beginRemoveRowsInParent(first_index, last_index, parent_row, parent_item_id)

    def ItemModel_connect(self, item_model: ItemModel, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        assert object is not None
        item_model.object = object

    def ItemModel_create(self) -> ItemModel:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        return ItemModel(None)

    def ItemModel_dataChanged(self, item_model: ItemModel, index: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.dataChangedInParent(index, parent_row, parent_item_id)

    def ItemModel_destroy(self, item_model: ItemModel) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.deleteLater()

    def ItemModel_endInsertRow(self, item_model: ItemModel) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.endInsertRowsInParent()

    def ItemModel_endRemoveRow(self, item_model: ItemModel) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert item_model is not None
        item_model.endRemoveRowsInParent()

    def Label_setText(self, label: QtWidgets.QLabel, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert label is not None
        if len(text) > 0:
            label.setText(text)
        else:
            label.clear()

    def Label_setTextColor(self, label: QtWidgets.QLabel, r: int, g: int, b: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert label is not None
        palette = label.palette()
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(r, g, b))
        palette.setColor(label.foregroundRole(), QtGui.QColor(r, g, b))
        label.setPalette(palette)

    def Label_setTextFont(self, label: QtWidgets.QLabel, font_str: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert label is not None
        display_scaling = GetDisplayScaling()
        font = ParseFontString(font_str, display_scaling)
        label.setFont(font)

    def Label_setWordWrap(self, label: QtWidgets.QLabel, word_wrap: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert label is not None
        label.setWordWrap(word_wrap)

    def LineEdit_connect(self, line_edit: PyLineEdit, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.object = object

    def LineEdit_getEditable(self, line_edit: PyLineEdit) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        return line_edit.isReadOnly()

    def LineEdit_getPlaceholderText(self, line_edit: PyLineEdit) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        return line_edit.placeholderText()

    def LineEdit_getSelectedText(self, line_edit: PyLineEdit) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        return line_edit.selectedText()

    def LineEdit_getText(self, line_edit: PyLineEdit) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        return line_edit.text()

    def LineEdit_selectAll(self, line_edit: PyLineEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.selectAll()

    def LineEdit_setClearButtonEnabled(self, line_edit: PyLineEdit, enabled: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.setClearButtonEnabled(enabled)

    def LineEdit_setEditable(self, line_edit: PyLineEdit, editable: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.setReadOnly(not editable)

    def LineEdit_setPlaceholderText(self, line_edit: PyLineEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.setPlaceholderText(text)

    def LineEdit_setText(self, line_edit: PyLineEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert line_edit is not None
        line_edit.setText(text)

    def Menu_addAction(self, menu: PyMenu, action: PyAction) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        assert action is not None
        menu.addAction(action)

    def Menu_addMenu(self, menu: PyMenu, title: str, sub_menu: PyMenu) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        sub_menu.setTitle(title)
        menu.addMenu(sub_menu)

    def Menu_addSeparator(self, menu: PyMenu) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        menu.addSeparator()

    def Menu_connect(self, menu: PyMenu, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        assert object is not None
        menu.object = object

    def Menu_create(self) -> PyMenu:
        return PyMenu()

    def Menu_destroy(self, menu: PyMenu) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        menu.deleteLater()

    def Menu_insertAction(self, menu: PyMenu, action: PyAction, before_action: PyAction) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        menu.insertAction(before_action, action)

    def Menu_insertSeparator(self, menu: PyMenu, before_action: PyAction) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        menu.insertSeparator(before_action)

    def Menu_popup(self, menu: PyMenu, gx: int, gy: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        if not menu.isEmpty():
            display_scaling = GetDisplayScaling()
            menu.popup(QtCore.QPoint(gx * display_scaling, gy * display_scaling))

    def Menu_removeAction(self, menu: PyMenu, action: PyAction) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert menu is not None
        menu.removeAction(action)

    def MimeData_create(self) -> QtCore.QMimeData:
        return QtCore.QMimeData()

    def MimeData_dataAsString(self, mime_data: QtCore.QMimeData, format: str) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert mime_data is not None
        return mime_data.data(format).data().decode("utf8")

    def MimeData_formats(self, mime_data: QtCore.QMimeData) -> typing.List[str]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert mime_data is not None
        return mime_data.formats()

    def MimeData_setDataAsString(self, mime_data: QtCore.QMimeData, format: str, s: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert mime_data is not None
        mime_data.setData(format, bytearray(s, "utf8"))

    def PushButton_connect(self, push_button_widget: PyPushButton, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert push_button_widget is not None
        push_button_widget.object = object

    def PushButton_setIcon(self, push_button_widget: PyPushButton, width: int, height: int, icon: numpy.ndarray) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert push_button_widget is not None
        if icon is not None:
            image = imageFromRGBA(icon)
            assert not image.isNull()
            display_scaling = GetDisplayScaling()
            push_button_widget.setIcon(QtGui.QIcon(QtGui.QPixmap.fromImage(image)))
            push_button_widget.setIconSize(QtCore.QSize(width * display_scaling, height * display_scaling))
        else:
            push_button_widget.setIcon(QtGui.QIcon())

    def PushButton_setText(self, push_button_widget: PyPushButton, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert push_button_widget is not None
        push_button_widget.setText(text)

    def RadioButton_connect(self, radio_button: PyRadioButton, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert radio_button is not None
        assert object is not None
        radio_button.object = object

    def RadioButton_getChecked(self, radio_button: PyRadioButton) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert radio_button is not None
        return radio_button.isChecked()

    def RadioButton_setChecked(self, radio_button: PyRadioButton, checked: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert radio_button is not None
        radio_button.setChecked(checked)

    def RadioButton_setIcon(self, radio_button: PyRadioButton, width: int, height: int, icon: numpy.ndarray) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert radio_button is not None
        if icon is not None:
            image = imageFromRGBA(icon)
            assert not image.isNull()
            display_scaling = GetDisplayScaling()
            radio_button.setIcon(QtGui.QIcon(QtGui.QPixmap.fromImage(image)))
            radio_button.setIconSize(QtCore.QSize(width * display_scaling, height * display_scaling))
        else:
            radio_button.setIcon(QtGui.QIcon())

    def RadioButton_setText(self, radio_button: PyRadioButton, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert radio_button is not None
        radio_button.setText(text)

    def ScrollArea_connect(self, scroll_area: PyScrollArea, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert scroll_area is not None
        assert object is not None
        scroll_area.object = object

    def ScrollArea_setHorizontal(self, scroll_area: PyScrollArea, value: float) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert scroll_area is not None
        scroll_area.horizontalScrollBar().setValue(int(scroll_area.horizontalScrollBar().maximum() * value))

    def ScrollArea_setScrollbarPolicies(self, scroll_area: PyScrollArea, horizontal_policy: str, vertical_policy: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert scroll_area is not None
        scroll_area.setHorizontalScrollBarPolicy(ParseScrollBarPolicy(horizontal_policy))
        scroll_area.setVerticalScrollBarPolicy(ParseScrollBarPolicy(vertical_policy))

    def ScrollArea_setVertical(self, scroll_area: PyScrollArea, value: float) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert scroll_area is not None
        scroll_area.verticalScrollBar().setValue(int(scroll_area.verticalScrollBar().maximum() * value))

    def ScrollArea_setWidget(self, scroll_area: PyScrollArea, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert scroll_area is not None
        scroll_area.setWidget(widget)
        widget.layout().setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)

    def Settings_getString(self, key: str) -> typing.Optional[str]:
        return QtCore.QSettings().value(key)

    def Settings_remove(self, key: str) -> None:
        QtCore.QSettings().remove(key)

    def Settings_setString(self, key: str, value: str) -> None:
        QtCore.QSettings().setValue(key, value)

    def Slider_connect(self, slider: PySlider, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert slider is not None
        assert object is not None
        slider.object = object

    def Slider_getValue(self, slider: PySlider) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert slider is not None
        return slider.value()

    def Slider_setMaximum(self, slider: PySlider, value: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert slider is not None
        slider.setMaximum(value)

    def Slider_setMinimum(self, slider: PySlider, value: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert slider is not None
        slider.setMinimum(value)

    def Slider_setValue(self, slider: PySlider, value: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert slider is not None
        slider.setValue(value)

    def Splitter_restoreState(self, splitter: QtWidgets.QSplitter, settings_id: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert splitter is not None
        settings_value = QtCore.QSettings().value(settings_id)
        if settings_value:
            splitter.restoreState(QtCore.QByteArray(settings_value))

    def Splitter_setOrientation(self, splitter: QtWidgets.QSplitter, orientation: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert splitter is not None
        splitter.setOrientation(QtCore.Qt.Horizontal if orientation == "horizontal" else QtCore.Qt.Vertical)

    def Splitter_saveState(self, splitter: QtWidgets.QSplitter, settings_id: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert splitter is not None
        QtCore.QSettings().setValue(settings_id, splitter.saveState())

    def Splitter_setSizes(self, splitter: QtWidgets.QSplitter, sizes: typing.List[int]) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert splitter is not None
        display_scaling = GetDisplayScaling()
        splitter.setSizes([int(size * display_scaling) for size in sizes])

    def StackWidget_addWidget(self, stack_widget: QtWidgets.QStackedWidget, widget: QtWidgets.QWidget) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert stack_widget is not None
        assert widget is not None
        return stack_widget.addWidget(widget)

    def StackWidget_insertWidget(self, stack_widget: QtWidgets.QStackedWidget, widget: QtWidgets.QWidget, index: int) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert stack_widget is not None
        assert widget is not None
        return stack_widget.insertWidget(index, widget)

    def StackWidget_removeWidget(self, stack_widget: QtWidgets.QStackedWidget, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert stack_widget is not None
        assert widget is not None
        stack_widget.removeWidget(widget)

    def StackWidget_setCurrentIndex(self, stack_widget: QtWidgets.QStackedWidget, index: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert stack_widget is not None
        stack_widget.setCurrentIndex(index)

    def TabWidget_addTab(self, tab_widget: PyTabWidget, widget: QtWidgets.QWidget, label: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert tab_widget is not None
        tab_widget.addTab(widget, label)

    def TabWidget_connect(self, tab_widget: PyTabWidget, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert tab_widget is not None
        tab_widget.object = object

    def TabWidget_setCurrentIndex(self, tab_widget: PyTabWidget, index: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert tab_widget is not None
        tab_widget.setCurrentIndex(index)

    def TextEdit_appendText(self, text_edit: PyTextEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.append(text)

    def TextEdit_clearSelection(self, text_edit: PyTextEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_cursor = text_edit.textCursor()
        text_cursor.clearSelection()
        text_edit.setTextCursor(text_cursor)

    def TextEdit_connect(self, text_edit: PyTextEdit, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        assert object is not None
        text_edit.object = object

    def TextEdit_getCursorInfo(self, text_edit: PyTextEdit) -> typing.Tuple[int, int, int, int, int]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_cursor = text_edit.textCursor()
        return text_cursor.position(), text_cursor.blockNumber(), text_cursor.columnNumber(), text_cursor.selectionStart(), text_cursor.selectionEnd()

    def TextEdit_getEditable(self, text_edit: PyTextEdit) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        return not text_edit.isReadOnly()

    def TextEdit_getPlaceholderText(self, text_edit: PyTextEdit) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        if sys.platform == "linux":
            return str()
        else:
            return text_edit.placeholderText()

    def TextEdit_getSelectedText(self, text_edit: PyTextEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        return text_edit.textCursor().selectedText()

    def TextEdit_getText(self, text_edit: PyTextEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        return text_edit.toPlainText()

    def TextEdit_insertText(self, text_edit: PyTextEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.insertPlainText(text)

    def TextEdit_moveCursorPosition(self, text_edit: PyTextEdit, operation_id: str, mode_id: str, n: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None

        if operation_id == "start":
            operation = QtGui.QTextCursor.Start
        elif operation_id == "end":
            operation = QtGui.QTextCursor.End
        elif operation_id == "start_line":
            operation = QtGui.QTextCursor.StartOfLine
        elif operation_id == "end_line":
            operation = QtGui.QTextCursor.EndOfLine
        elif operation_id == "start_para":
            operation = QtGui.QTextCursor.StartOfBlock
        elif operation_id == "end_para":
            operation = QtGui.QTextCursor.EndOfBlock
        elif operation_id == "previous":
            operation = QtGui.QTextCursor.PreviousCharacter
        elif operation_id == "next":
            operation = QtGui.QTextCursor.NextCharacter
        elif operation_id == "up":
            operation = QtGui.QTextCursor.Up
        elif operation_id == "down":
            operation = QtGui.QTextCursor.Down
        elif operation_id == "left":
            operation = QtGui.QTextCursor.Left
        elif operation_id == "right":
            operation = QtGui.QTextCursor.Right
        else:
            operation = QtGui.QTextCursor.NoMove

        if mode_id == "move":
            mode = QtGui.QTextCursor.MoveAnchor
        elif mode_id == "keep":
            mode = QtGui.QTextCursor.KeepAnchor
        else:
            mode = QtGui.QTextCursor.MoveAnchor

        for i in range(n):
            text_edit.moveCursor(operation, mode)

    def TextEdit_removeSelectedText(self, text_edit: PyTextEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_cursor = text_edit.textCursor()
        text_cursor.removeSelectedText()

    def TextEdit_selectAll(self, text_edit: PyTextEdit) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.selectAll()

    def TextEdit_setEditable(self, text_edit: PyTextEdit, editable: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.setReadOnly(not editable)

    def TextEdit_setPlaceholderText(self, text_edit: PyTextEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        if sys.platform != "linux":
            text_edit.setPlaceholderText(text)

    def TextEdit_setProportionalLineHeight(self, text_edit: PyTextEdit, proportional_line_height: float) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        bf = text_edit.textCursor().blockFormat()
        bf.setLineHeight(int(proportional_line_height * 100), QtGui.QTextBlockFormat.ProportionalHeight)
        text_edit.textCursor().setBlockFormat(bf)

    def TextEdit_setText(self, text_edit: PyTextEdit, text: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.setText(text)

    def TextEdit_setTextBackgroundColor(self, text_edit: PyTextEdit, r: int, g: int, b: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        palette = text_edit.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(r, g, b))
        text_edit.setPalette(palette)

    def TextEdit_setTextColor(self, text_edit: PyTextEdit, r: int, g: int, b: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.setTextColor(QtGui.QColor(r, g, b))

    def TextEdit_setTextFont(self, text_edit: PyTextEdit, font_str: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        display_scaling = GetDisplayScaling()
        font = ParseFontString(font_str, display_scaling)
        text_edit.setFont(font)

    def TextEdit_setWordWrapMode(self, text_edit: PyTextEdit, wrap_mode: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert text_edit is not None
        text_edit.setWordWrapMode(QtGui.QTextOption.WrapMode(["none", "word", "manual", "anywhere", "optional"].index(wrap_mode)))

    def ToolTip_hide(self) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        QtWidgets.QToolTip.hideText()

    def ToolTip_show(self, widget: QtWidgets.QWidget, gx: int, gy: int, text: str, t: int, l: int, b: int, r: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        QtWidgets.QToolTip.showText(QtCore.QPoint(gx, gy), text, widget, QtCore.QRect(QtCore.QPoint(l, t), QtCore.QSize(r - l, b - t)))

    def TreeWidget_connect(self, content_view: QtWidgets.QWidget, object) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        tree_widget.object = object

    def TreeWidget_resizeToContent(self, content_view: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        item_model = tree_widget.model()
        assert item_model is not None
        size = tree_widget.size()
        row_count = item_model.rowCount(QtCore.QModelIndex())
        if row_count > 0:
            margins = tree_widget.contentsMargins()
            last = tree_widget.visualRect(item_model.index(row_count - 1, 0, QtCore.QModelIndex()))
            new_height = last.bottom() + margins.top() + margins.bottom() + 2
        else:
            new_height = 20
        new_size = QtCore.QSize(size.width(), new_height)
        content_view.setMinimumHeight(new_height)
        content_view.setMinimumHeight(new_height)
        content_view.resize(new_size)
        scroll_area.setMinimumHeight(new_height)
        scroll_area.setMinimumHeight(new_height)
        scroll_area.resize(new_size)
        tree_widget.setMinimumHeight(new_height)
        tree_widget.setMinimumHeight(new_height)
        tree_widget.resize(new_size)

    def TreeWidget_setCurrentRow(self, content_view: QtWidgets.QWidget, index: int, parent_row: int, parent_item_id: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        item_model = tree_widget.model()
        assert item_model is not None
        model_index = item_model.indexInParent(index, parent_row, parent_item_id)
        tree_widget.setCurrentIndex(model_index)
        tree_widget.scrollTo(model_index)

    def TreeWidget_setModel(self, content_view: QtWidgets.QWidget, item_model: ItemModel) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        tree_widget.setModelAndConnect(item_model)

    def TreeWidget_setSelectedIndexes(self, content_view: QtWidgets.QWidget, indexes: typing.List[typing.Tuple[int, int, int]]) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        item_model = tree_widget.model()
        assert item_model is not None
        model_index_list = [item_model.indexInParent(index, parent_row, parent_item_id) for index, parent_row, parent_item_id in indexes]
        tree_widget.selectionModel().reset()
        for model_index in model_index_list:
            tree_widget.selectionModel().setCurrentIndex(model_index, QtCore.QItemSelectionModel.Select)

    def TreeWidget_setSelectionMode(self, content_view: QtWidgets.QWidget, selection_mode: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert content_view is not None
        scroll_area = content_view.layout().itemAt(0).widget()
        assert scroll_area is not None
        tree_widget = scroll_area.widget()
        assert tree_widget is not None
        selection_modes = ["none", "single", "multi_unused", "extended", "contiguous"]
        assert selection_mode in selection_modes
        tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode(selection_modes.index(selection_mode)))

    def Widget_addOverlay(self, widget: QtWidgets.QWidget, child_widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        Overlay(widget, child_widget)

    def Widget_addSpacing(self, widget: QtWidgets.QWidget, spacing: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        display_scaling = GetDisplayScaling()
        layout = widget.layout()
        layout.addSpacing(spacing * display_scaling)

    def Widget_addStretch(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        layout = widget.layout()
        layout.addStretch()

    def Widget_addWidget(self, widget: QtWidgets.QWidget, child_widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        if isinstance(widget, QtWidgets.QSplitter):
            widget.addWidget(child_widget)
        else:
            widget.layout().addWidget(child_widget)
            # now force the layout to re-layout
            widget.layout().setGeometry(widget.layout().geometry())

    def Widget_adjustSize(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        # force size to adjust
        widget.adjustSize()

    def Widget_clearFocus(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.clearFocus()

    def Widget_getFocusPolicy(self, widget: QtWidgets.QWidget) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return {
            QtCore.Qt.TabFocus: "tab_focus",
            QtCore.Qt.ClickFocus: "click_focus",
            QtCore.Qt.StrongFocus: "strong_focus",
            QtCore.Qt.WheelFocus: "wheel_focus",
        }.get(widget.focusPolicy(), "no_focus")

    def Widget_getWidgetProperty(self, widget: QtWidgets.QWidget, property: str) -> str:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        if property:
            raise NotImplementedError()
        return str()

    def Widget_getWidgetSize(self, widget: QtWidgets.QWidget) -> typing.Tuple[int, int]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        display_scaling = GetDisplayScaling()
        return int(widget.size().width() / display_scaling), int(widget.size().height() / display_scaling)

    def Widget_grabGesture(self, widget: QtWidgets.QWidget, gesture_type: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        gesture_types = ["tap", "long-tap", "pan", "pinch", "swipe"]
        assert gesture_type in gesture_types
        widget.grabGesture(gesture_types.index(gesture_type) + 1)

    def Widget_hasFocus(self, widget: QtWidgets.QWidget) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return widget.hasFocus()

    def Widget_hide(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.hide()

    def Widget_insertWidget(self, widget: QtWidgets.QWidget, child_widget: QtWidgets.QWidget, index: int, fill: bool, alignment: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        alignment_value = {
            "left": QtCore.Qt.AlignLeft,
            "right": QtCore.Qt.AlignRight,
            "hcenter": QtCore.Qt.AlignHCenter,
            "justify": QtCore.Qt.AlignJustify,
            "top": QtCore.Qt.AlignTop,
            "bottom": QtCore.Qt.AlignBottom,
            "vcenter": QtCore.Qt.AlignVCenter,
            "center": QtCore.Qt.AlignCenter,
        }.get(alignment, QtCore.Qt.AlignmentFlag(0))
        stretch = 0  # hard coded
        box_layout = widget.layout()
        assert box_layout is not None
        box_layout.insertWidget(index, child_widget, stretch, alignment_value)
        if fill:
            child_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # force re-layout
        widget.layout().setGeometry(widget.layout().geometry())

    def Widget_isEnabled(self, widget: QtWidgets.QWidget) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return widget.isEnabled()

    def Widget_isVisible(self, widget: QtWidgets.QWidget) -> bool:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return widget.isVisible()

    def Widget_loadIntrinsicWidget(self, intrinsic_id: str) -> QtWidgets.QWidget:
        global app
        assert app.thread() == QtCore.QThread.currentThread()

        def apply_stylesheet(widget: QtWidgets.QWidget) -> None:
            global g_stylesheet
            if not g_stylesheet:
                stylesheet_bytes = pkgutil.get_data(__name__, "resources/stylesheet.qss")
                stylesheet = stylesheet_bytes.decode('UTF-8', 'ignore') if stylesheet_bytes else str()
                if sys.platform == "win32":
                    stylesheet = "QWidget { font-size: 11px }\n" + stylesheet
                display_scaling = GetDisplayScaling()
                while True:
                    re = QtCore.QRegularExpression("(\\d+)px")
                    match = re.match(stylesheet)
                    if match.hasMatch():
                        new_size = int(int(match.captured(1)) * display_scaling)
                        stylesheet = stylesheet.replace(match.captured(0), str(new_size) + "QZ")
                    else:
                        break
                stylesheet = stylesheet.replace("QZ", "px")
                g_stylesheet = stylesheet
                app.setStyleSheet(g_stylesheet)  # required for Win Qt 5.9 (conda), panel headers, after resolution change.
            widget.setStyleSheet(g_stylesheet)

        if intrinsic_id == "row":
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            apply_stylesheet(row)
            return row
        elif intrinsic_id == "column":
            column = QtWidgets.QWidget()
            column_layout = QtWidgets.QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(0)
            apply_stylesheet(column)
            return column
        elif intrinsic_id == "tab":
            group = PyTabWidget()
            group.setTabsClosable(False)
            group.setMovable(False)
            apply_stylesheet(group)
            return group
        elif intrinsic_id == "stack":
            stack = QtWidgets.QStackedWidget()
            apply_stylesheet(stack)
            return stack
        elif intrinsic_id == "group":
            group_box = QtWidgets.QGroupBox()
            column_layout = QtWidgets.QVBoxLayout(group_box)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(0)
            apply_stylesheet(group_box)
            return group_box
        elif intrinsic_id == "scrollarea":
            scroll_area = PyScrollArea()
            apply_stylesheet(scroll_area)
            return scroll_area
        elif intrinsic_id == "splitter":
            splitter = QtWidgets.QSplitter()
            splitter.setOrientation(QtCore.Qt.Vertical)
            apply_stylesheet(splitter)
            return splitter
        elif intrinsic_id == "pushbutton":
            button = PyPushButton()
            return button
        elif intrinsic_id == "radiobutton":
            button = PyRadioButton()
            return button
        elif intrinsic_id == "checkbox":
            checkbox = PyCheckBox()
            return checkbox
        elif intrinsic_id == "combobox":
            combobox = PyComboBox()
            return combobox
        elif intrinsic_id == "label":
            label = QtWidgets.QLabel()
            return label
        elif intrinsic_id == "slider":
            slider = PySlider()
            return slider
        elif intrinsic_id == "lineedit":
            line_edit = PyLineEdit()
            return line_edit
        elif intrinsic_id == "textedit":
            text_edit = PyTextEdit()
            return text_edit
        elif intrinsic_id == "canvas":
            canvas = PyCanvas()
            return canvas
        elif intrinsic_id == "pytree":
            data_view = TreeWidget()
            data_view.setStyleSheet("QListView { border: none; }")
            data_view.setHeaderHidden(True)
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(data_view)
            scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            apply_stylesheet(scroll_area)
            content_view = QtWidgets.QWidget()
            content_view.setContentsMargins(0, 0, 0, 0)
            content_view.setStyleSheet("border: none; background-color: transparent")
            content_view_layout = QtWidgets.QVBoxLayout(content_view)
            content_view_layout.setContentsMargins(0, 0, 0, 0)
            content_view_layout.setSpacing(0)
            content_view_layout.addWidget(scroll_area)
            return content_view
        return None

    def Widget_mapToGlobal(self, widget: QtWidgets.QWidget, x: int, y: int) -> typing.Tuple[int, int]:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        display_scaling = GetDisplayScaling()
        p = widget.mapToGlobal(QtCore.QPoint(x, y))
        return int(p.x() / display_scaling), int(p.y() / display_scaling)

    def Widget_removeAll(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        while widget.layout().count() > 0:
            widget.layout().removeItem(widget.layout().takeAt(0))

    def Widget_removeWidget(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        # deleting a some items (canvas) requires a render thread to finish.
        # but the render thread may need the GIL to finish. so release
        # the GIL here until the render thread finishes and this object
        # has been deleted.
        # Python_ThreadAllow thread_allow
        widget.setParent(None)

    def Widget_setAttributes(self, widget: QtWidgets.QWidget, attributes: typing.Sequence[str]) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        attribute_mapping = {
            "translucent-background": QtCore.Qt.WA_TranslucentBackground,
            "mouse-transparent": QtCore.Qt.WA_TransparentForMouseEvents,
            "accept-drops": QtCore.Qt.WA_AcceptDrops,
        }
        for attribute in attributes:
            if attribute.startswith("!"):
                attribute = attribute[1:]
                if attribute in attribute_mapping:
                    widget.setAttribute(attribute_mapping[attribute], False)
            else:
                if attribute in attribute_mapping:
                    widget.setAttribute(attribute_mapping[attribute], True)

    def Widget_setEnabled(self, widget: QtWidgets.QWidget, enabled: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.setEnabled(enabled)

    def Widget_setFocus(self, widget: QtWidgets.QWidget, reason: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.setFocus(QtCore.Qt.FocusReason(reason))

    def Widget_setFocusPolicy(self, widget: QtWidgets.QWidget, policy: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        focus_policy = {
            "tab_focus": QtCore.Qt.TabFocus,
            "click_focus": QtCore.Qt.ClickFocus,
            "strong_focus": QtCore.Qt.StrongFocus,
            "wheel_focus": QtCore.Qt.WheelFocus,
        }.get(policy, QtCore.Qt.NoFocus)
        widget.setFocusPolicy(focus_policy)

    def Widget_setPaletteColor(self, widget: QtWidgets.QWidget, role: str, r: int, g: int, b: int, a: int) -> None:
        palette = widget.palette()
        if role == "background":
            palette.setColor(widget.backgroundRole(), QtGui.QColor(r, g, b, a))
        widget.setPalette(palette)

    def Widget_setToolTip(self, widget: QtWidgets.QWidget, tool_tip: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.setToolTip(tool_tip)

    def Widget_setVisible(self, widget: QtWidgets.QWidget, visible: bool) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.setVisible(visible)

    def Widget_setWidgetProperty(self, widget: QtWidgets.QWidget, property: str, value) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        display_scaling = GetDisplayScaling()
        if property == "margin":
            widget.setContentsMargins(value * display_scaling, value * display_scaling, value * display_scaling, value * display_scaling)
        elif property == "margin-top":
            margin = widget.contentsMargins()
            margin.setTop(value * display_scaling)
            widget.setContentsMargins(margin)
        elif property == "margin-left":
            margin = widget.contentsMargins()
            margin.setLeft(value * display_scaling)
            widget.setContentsMargins(margin)
        elif property == "margin-bottom":
            margin = widget.contentsMargins()
            margin.setBottom(value * display_scaling)
            widget.setContentsMargins(margin)
        elif property == "margin-right":
            margin = widget.contentsMargins()
            margin.setRight(value * display_scaling)
            widget.setContentsMargins(margin)
        elif property == "min-width":
            widget.setMinimumWidth(value * display_scaling)
        elif property == "max-width":
            widget.setMaximumWidth(value * display_scaling)
        elif property == "min-height":
            widget.setMinimumHeight(value * display_scaling)
        elif property == "max-height":
            widget.setMaximumHeight(value * display_scaling)
        elif property == "size-policy-horizontal":
            size_policy = widget.sizePolicy()
            size_policy.setHorizontalPolicy(ParseSizePolicy(value, size_policy.horizontalPolicy()))
            widget.setSizePolicy(size_policy)
        elif property == "size-policy-vertical":
            size_policy = widget.sizePolicy()
            size_policy.setVerticalPolicy(ParseSizePolicy(value, size_policy.verticalPolicy()))
            widget.setSizePolicy(size_policy)
        elif property == "width":
            widget.setMinimumWidth(value * display_scaling)
            widget.setMaximumWidth(value * display_scaling)
        elif property == "height":
            widget.setMinimumHeight(value * display_scaling)
            widget.setMaximumHeight(value * display_scaling)
        elif property == "spacing":
            layout = widget.layout()
            if layout is not None:
                layout.setSpacing(value * display_scaling)
        elif property == "font-size":
            font = widget.font()
            font.setPointSize(value * display_scaling)
            widget.setFont(font)
        elif property == "stylesheet":
            widget.setStyleSheet(value)

    def Widget_setWidgetSize(self, widget: QtWidgets.QWidget, width: int, height: int) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        # force size to adjust
        display_scaling = GetDisplayScaling()
        widget.setMinimumSize(QtCore.QSize(width * display_scaling, height * display_scaling))  # required within scroll area. ugh.
        widget.resize(QtCore.QSize(width * display_scaling, height * display_scaling))

    def Widget_show(self, widget: QtWidgets.QWidget) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        widget.show()

    def Widget_ungrabGesture(self, widget: QtWidgets.QWidget, gesture_type: str) -> None:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        gesture_types = ["tap", "long-tap", "pan", "pinch", "swipe"]
        assert gesture_type in gesture_types
        widget.ungrabGesture(gesture_types.index(gesture_type) + 1)

    def Widget_widgetByIndex(self, widget: QtWidgets.QWidget, index: int) -> QtWidgets.QWidget:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return widget.layout().itemAt(index).widget()

    def Widget_widgetCount(self, widget: QtWidgets.QWidget) -> int:
        global app
        assert app.thread() == QtCore.QThread.currentThread()
        assert widget is not None
        return widget.layout().count()
