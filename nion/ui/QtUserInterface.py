"""
Provides a user interface object that can render to an Qt host.
"""

from __future__ import annotations

# standard libraries
import binascii
import copy
import os
import pathlib
import pickle
import sys
import time
import typing
import weakref

# third party libraries
# none

# local libraries
from nion.ui import DrawingContext
from nion.ui import UserInterface
from nion.utils import Color
from nion.utils import Geometry

if typing.TYPE_CHECKING:
    from nion.ui import Application
    from nion.ui import CanvasItem
    from nion.ui import Window


_QtProxy = typing.Any
_QtObject = typing.Any


def notnone(s: typing.Any) -> str:
    return str(s) if s is not None else str()


class QtKeyboardModifiers(UserInterface.KeyboardModifiers):
    def __init__(self, raw_modifiers: typing.Any) -> None:
        self.raw_modifiers = int(raw_modifiers)  # convert from internal Qt type to int (pyqt)

    def __str__(self) -> str:
        return "shift:{} control:{} alt:{} option:{} meta:{}".format(self.shift, self.control, self.alt, self.option, self.meta)

    # shift
    @property
    def shift(self) -> bool:
        return (self.raw_modifiers & 0x02000000) == 0x02000000

    @property
    def only_shift(self) -> bool:
        return self.raw_modifiers == 0x02000000

    # control (command key on mac)
    @property
    def control(self) -> bool:
        return (self.raw_modifiers & 0x04000000) == 0x04000000

    @property
    def only_control(self) -> bool:
        return self.raw_modifiers == 0x04000000

    # alt (option key on mac)
    @property
    def alt(self) -> bool:
        return (self.raw_modifiers & 0x08000000) == 0x08000000

    @property
    def only_alt(self) -> bool:
        return self.raw_modifiers == 0x08000000

    # option (alt key on windows)
    @property
    def option(self) -> bool:
        return (self.raw_modifiers & 0x08000000) == 0x08000000

    @property
    def only_option(self) -> bool:
        return self.raw_modifiers == 0x08000000

    # meta (control key on mac)
    @property
    def meta(self) -> bool:
        return (self.raw_modifiers & 0x10000000) == 0x10000000

    @property
    def only_meta(self) -> bool:
        return self.raw_modifiers == 0x10000000

    # control key (all platforms)
    @property
    def native_control(self) -> bool:
        if sys.platform == "win32":
            return self.control
        else:
            return self.meta

    # keypad
    @property
    def keypad(self) -> bool:
        return (self.raw_modifiers & 0x20000000) == 0x20000000

    @property
    def only_keypad(self) -> bool:
        return self.raw_modifiers == 0x20000000


class QtKey(UserInterface.Key):
    def __init__(self, text: str, key: int, raw_modifiers: typing.Any) -> None:
        self.__text = text
        self.__key = key
        self.__modifiers = QtKeyboardModifiers(raw_modifiers)

    @property
    def text(self) -> str:
        return self.__text

    @property
    def key(self) -> int:
        return self.__key

    @property
    def modifiers(self) -> UserInterface.KeyboardModifiers:
        return self.__modifiers

    @property
    def is_delete(self) -> bool:
        return len(self.text) == 1 and (ord(self.text[0]) == 127 or ord(self.text[0]) == 8)

    @property
    def is_enter_or_return(self) -> bool:
        return len(self.text) == 1 and (ord(self.text[0]) == 3 or ord(self.text[0]) == 13)

    @property
    def is_escape(self) -> bool:
        return self.key == 0x1000000

    @property
    def is_tab(self) -> bool:
        return self.key == 0x1000001

    @property
    def is_insert(self) -> bool:
        return self.key == 0x1000006

    @property
    def is_home(self) -> bool:
        return self.key == 0x1000010

    @property
    def is_end(self) -> bool:
        return self.key == 0x1000011

    @property
    def is_move_to_start_of_line(self) -> bool:
        return self.is_home or (self.is_left_arrow and self.modifiers.control) or (self.key == 0x41 and self.modifiers.native_control)

    @property
    def is_move_to_end_of_line(self) -> bool:
        return self.is_end or (self.is_right_arrow and self.modifiers.control) or (self.key == 0x45 and self.modifiers.native_control)

    @property
    def is_delete_to_end_of_line(self) -> bool:
        return self.key == 0x4B and self.modifiers.native_control

    @property
    def is_arrow(self) -> bool:
        return self.key in (0x1000012, 0x1000013, 0x1000014, 0x1000015)

    @property
    def is_left_arrow(self) -> bool:
        return self.key == 0x1000012

    @property
    def is_up_arrow(self) -> bool:
        return self.key == 0x1000013

    @property
    def is_right_arrow(self) -> bool:
        return self.key == 0x1000014

    @property
    def is_down_arrow(self) -> bool:
        return self.key == 0x1000015

    @property
    def is_page_up(self) -> bool:
        return self.key == 0x1000016

    @property
    def is_page_down(self) -> bool:
        return self.key == 0x1000017


class QtMimeData(UserInterface.MimeData):
    def __init__(self, proxy: _QtProxy, mime_data: typing.Optional[_QtObject] = None) -> None:
        self.proxy = proxy
        self.raw_mime_data = mime_data if mime_data else self.proxy.MimeData_create()

    @property
    def formats(self) -> typing.Sequence[str]:
        return typing.cast(typing.List[str], self.proxy.MimeData_formats(self.raw_mime_data))

    @property
    def file_paths(self) -> typing.Sequence[str]:
        urls = self.urls
        file_paths = []
        for url in urls:
            file_path = self.proxy.Core_URLToPath(url)
            if file_path and len(file_path) > 0 and os.path.exists(file_path) and os.path.isfile(file_path):
                file_paths.append(file_path)
        return file_paths

    def data_as_string(self, format: str) -> str:
        return typing.cast(str, self.proxy.MimeData_dataAsString(self.raw_mime_data, format))

    def set_data_as_string(self, format: str, text: str) -> None:
        self.proxy.MimeData_setDataAsString(self.raw_mime_data, format, text)


# pobj
class QtItemModelController:

    NONE = 0
    COPY = 1
    MOVE = 2
    LINK = 4

    DRAG = 1
    DROP = 2

    class Item:
        def __init__(self, data: typing.Any = None) -> None:
            self.id: typing.Optional[int] = None
            self.data = data if data else {}
            self.weak_parent: typing.Any = None
            self.children: typing.List[QtItemModelController.Item] = list()

        def remove_all_children(self) -> None:
            self.children = []

        def append_child(self, item: QtItemModelController.Item) -> None:
            item.parent = self
            self.children.append(item)

        def insert_child(self, before_index: int, item: QtItemModelController.Item) -> None:
            item.parent = self
            self.children.insert(before_index, item)

        def remove_child(self, item: QtItemModelController.Item) -> None:
            item.parent = None
            self.children.remove(item)

        def child(self, index: int) -> QtItemModelController.Item:
            return self.children[index]

        @property
        def row(self) -> typing.Optional[int]:
            parent: typing.Optional[QtItemModelController.Item] = self.weak_parent() if self.weak_parent else None
            if parent:
                return parent.children.index(self)
            return -1

        @property
        def parent(self) -> typing.Optional[QtItemModelController.Item]:
            return self.weak_parent() if self.weak_parent else None

        @parent.setter
        def parent(self, parent: typing.Optional[QtItemModelController.Item]) -> None:
            self.weak_parent = weakref.ref(parent) if parent else None

    def __init__(self, proxy: _QtProxy) -> None:
        self.proxy = proxy
        self.py_item_model = self.proxy.ItemModel_create()
        self.proxy.ItemModel_connect(self.py_item_model, self)
        self.__next_id = 0
        self.root = self.create_item()
        self.on_item_set_data: typing.Optional[typing.Callable[[typing.Any, typing.Optional[int], typing.Optional[int], typing.Optional[int]], bool]] = None
        self.on_can_drop_mime_data: typing.Optional[typing.Callable[[UserInterface.MimeData, str, typing.Optional[int], typing.Optional[int], typing.Optional[int]], bool]] = None
        self.on_item_drop_mime_data: typing.Optional[typing.Callable[[UserInterface.MimeData, str, typing.Optional[int], typing.Optional[int], typing.Optional[int]], bool]] = None
        self.on_item_mime_data: typing.Optional[typing.Callable[[typing.Optional[int], typing.Optional[int], typing.Optional[int]], QtMimeData]] = None
        self.on_remove_rows: typing.Optional[typing.Callable[[typing.Optional[int], int, typing.Optional[int], typing.Optional[int]], bool]] = None
        self.supported_drop_actions = 0

    def close(self) -> None:
        self.proxy.ItemModel_destroy(self.py_item_model)
        self.proxy = None
        self.py_item_model = None
        self.root = typing.cast(typing.Any, None)
        self.on_item_set_data = None
        self.on_can_drop_mime_data = None
        self.on_item_drop_mime_data = None
        self.on_item_mime_data = None
        self.on_remove_rows = None

    # these methods must be invoked from the client

    def create_item(self, data: typing.Any = None) -> QtItemModelController.Item:
        item = QtItemModelController.Item(data)
        item.id = self.__next_id
        self.__next_id = self.__next_id + 1
        return item

    def item_from_id(self, item_id: int, parent: typing.Optional[int] = None) -> typing.Optional[QtItemModelController.Item]:
        item: typing.Optional[QtItemModelController.Item] = None

        def fn(parent: typing.Optional[QtItemModelController.Item], index: typing.Optional[int], child: QtItemModelController.Item) -> bool:
            nonlocal item
            if child.id == item_id:
                item = child
                return True
            return False

        self.traverse(fn)
        return item

    def __item_id(self, index: int, parent_id: int) -> typing.Optional[int]:
        parent = self.item_from_id(parent_id)
        assert parent is not None
        if index >= 0 and index < len(parent.children):
            return parent.children[index].id
        return 0  # invalid id

    def item_value_for_item_id(self, role: str, index: typing.Optional[int], item_id: int) -> typing.Any:
        child = self.item_from_id(item_id)
        if role == "index":
            return index
        if child and role in child.data:
            return child.data[role]
        return None

    def item_value(self, role: str, index: int, parent_id: int) -> typing.Any:
        item_id = self.__item_id(index, parent_id)
        return self.item_value_for_item_id(role, index, item_id) if item_id else None

    # these methods are invoked from Qt

    def itemCount(self, parent_id: int) -> int:
        parent = self.item_from_id(parent_id)
        assert parent is not None
        return len(parent.children)

    # itemId returns the id of the item within the parent
    def itemId(self, index: int, parent_id: int) -> typing.Optional[int]:
        return self.__item_id(index, parent_id)

    def itemParent(self, index: int, item_id: int) -> typing.List[int]:
        if item_id == 0:
            return [-1, 0]
        child = self.item_from_id(item_id)
        if child:
            parent = child.parent
            if parent == self.root:
                return [-1, 0]
            if parent and parent.row is not None and parent.id is not None:
                return [parent.row, parent.id]
        return [-1, -1]

    def itemValue(self, role: str, index: int, item_id: int) -> typing.Any:
        return self.item_value_for_item_id(role, index, item_id)

    def itemSetData(self, index: int, parent_row: int, parent_id: int, data: typing.Any) -> bool:
        if self.on_item_set_data:
            return self.on_item_set_data(data, index, parent_row, parent_id)
        return False

    def canDropMimeData(self, raw_mime_data: _QtObject, action: str, row: typing.Optional[int], parent_row: typing.Optional[int], parent_id: typing.Optional[int]) -> bool:
        if self.on_can_drop_mime_data:
            return self.on_can_drop_mime_data(QtMimeData(self.proxy, raw_mime_data), action, row, parent_row, parent_id)
        return False

    def itemDropMimeData(self, raw_mime_data: _QtObject, action: str, row: typing.Optional[int], parent_row: typing.Optional[int], parent_id: typing.Optional[int]) -> bool:
        if self.on_item_drop_mime_data:
            return self.on_item_drop_mime_data(QtMimeData(self.proxy, raw_mime_data), action, row, parent_row, parent_id)
        return False

    def itemMimeData(self, row: typing.Optional[int], parent_row: typing.Optional[int], parent_id: typing.Optional[int]) -> typing.Optional[_QtObject]:
        if self.on_item_mime_data and row is not None:
            mime_data = self.on_item_mime_data(row, parent_row, parent_id)
            return mime_data.raw_mime_data if mime_data else None
        return None

    def removeRows(self, row: typing.Optional[int], count: int, parent_row: typing.Optional[int], parent_id: typing.Optional[int]) -> bool:
        if self.on_remove_rows:
            return self.on_remove_rows(row, count, parent_row, parent_id)
        return False

    def supportedDropActions(self) -> int:
        return self.supported_drop_actions

    def mimeTypesForDrop(self) -> typing.Sequence[str]:
        return list()


#abc (None, 0)
#    def (abc, 0)
#    ghi (abc, 1)
#        jkl (ghi, 0)
#        mno (ghi, 1)
#    pqr (abc, 2)
#        stu (pqr, 0)
#    vwx (abc, 3)

    def traverse_depth_first(self, fn: typing.Callable[[typing.Optional[QtItemModelController.Item], typing.Optional[int], QtItemModelController.Item], bool], parent: QtItemModelController.Item) -> bool:
        real_parent = parent if parent else self.root
        for index, child in enumerate(real_parent.children):
            if self.traverse_depth_first(fn, child):
                return True
            if fn(parent, index, child):
                return True
        return False

    def traverse(self, fn: typing.Callable[[typing.Optional[QtItemModelController.Item], typing.Optional[int], QtItemModelController.Item], bool]) -> None:
        if not fn(None, 0, self.root):
            self.traverse_depth_first(fn, self.root)

    def begin_insert(self, first_row: int, last_row: int, parent_row: int, parent_id: int) -> None:
        self.proxy.ItemModel_beginInsertRows(self.py_item_model, first_row, last_row, parent_row, parent_id)

    def end_insert(self) -> None:
        self.proxy.ItemModel_endInsertRow(self.py_item_model)

    def begin_remove(self, first_row: int, last_row: int, parent_row: int, parent_id: int) -> None:
        self.proxy.ItemModel_beginRemoveRows(self.py_item_model, first_row, last_row, parent_row, parent_id)

    def end_remove(self) -> None:
        self.proxy.ItemModel_endRemoveRow(self.py_item_model)

    def data_changed(self, row: int, parent_row: int, parent_id: int) -> None:
        self.proxy.ItemModel_dataChanged(self.py_item_model, row, parent_row, parent_id)


class QtDrag:
    def __init__(self, proxy: _QtProxy, widget: _QtObject, mime_data: QtMimeData,
                 thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None, hot_spot_x: typing.Optional[int] = None,
                 hot_spot_y: typing.Optional[int] = None,
                 drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self.proxy = proxy
        self.__raw_drag = self.proxy.Drag_create(widget, mime_data.raw_mime_data)
        self.proxy.Drag_connect(self.__raw_drag, self)
        if thumbnail is not None:
            width = thumbnail.shape[1]
            height = thumbnail.shape[0]
            rgba_data = self.proxy.encode_data(thumbnail)
            hot_spot_x = hot_spot_x if hot_spot_x is not None else width // 2
            hot_spot_y = hot_spot_y if hot_spot_y is not None else height // 2
            self.proxy.Drag_setThumbnail(self.__raw_drag, width, height, rgba_data, hot_spot_x, hot_spot_y)
        self.on_drag_finished = drag_finished_fn

    def close(self) -> None:
        pass

    def execute(self) -> None:
        self.proxy.Drag_exec(self.__raw_drag)

    def dragFinished(self, action: str) -> None:
        if self.on_drag_finished:
            self.on_drag_finished(action)


class QtWidgetBehavior:  # cannot subclass UserInterface.WidgetBehavior until mypy #4125 is available

    def __init__(self, proxy: _QtProxy, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.proxy = proxy
        self.properties = dict(properties) if properties else {}
        self.widget: typing.Optional[_QtObject] = self.proxy.Widget_loadIntrinsicWidget(widget_type) if widget_type else None
        self.update_properties()
        self.__visible = True
        self.__enabled = True
        self.__tool_tip: typing.Optional[str] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed : typing.Optional[typing.Callable[[bool], None]] = None
        self.__focus_policy = self.proxy.Widget_getFocusPolicy(self.widget)
        self.__does_retain_focus = bool(self.__focus_policy != "no_focus")
        self._no_focus = "no_focus"

    # subclasses should override to clear their variables.
    # subclasses should NOT call Qt code to delete anything here... that is done by the Qt code
    def close(self) -> None:
        # not sure if this call to close is needed. it only applies in the PyQtProxy case.
        if callable(getattr(self.widget, "close", None)):
            getattr(self.widget, "close")()
        self.proxy.Widget_removeWidget(self.widget)
        self.on_ui_activity = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.widget = typing.cast(typing.Any, None)
        self.proxy = typing.cast(typing.Any, None)

    def update_properties(self) -> None:
        for key in self.properties.keys():
            self.proxy.Widget_setWidgetProperty(self.widget, key, self.proxy.encode_variant(self.properties[key]))

    def set_property(self, key: str, value: typing.Any) -> None:
        self.proxy.Widget_setWidgetProperty(self.widget, key, self.proxy.encode_variant(value))

    def periodic(self) -> None:
        pass

    def _set_root_container(self, window: typing.Optional[Window.Window]) -> None:
        pass

    def _get_content_widget(self) -> typing.Optional[UserInterface.Widget]:
        return None

    def _register_ui_activity(self) -> None:
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    @property
    def focused(self) -> bool:
        return bool(self.proxy.Widget_hasFocus(self.widget))

    @focused.setter
    def focused(self, focused: bool) -> None:
        if focused != self.focused:
            if focused:
                self.proxy.Widget_setFocus(self.widget, 7)
            else:
                self.proxy.Widget_clearFocus(self.widget)

    @property
    def does_retain_focus(self) -> bool:
        return self.__does_retain_focus

    @does_retain_focus.setter
    def does_retain_focus(self, value: bool) -> None:
        self.__does_retain_focus = value
        # no_focus, tab_focus, click_focus, strong_focus, wheel_focus
        self.proxy.Widget_setFocusPolicy(self.widget, self.__focus_policy if value else self._no_focus)

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        if visible != self.__visible:
            self.proxy.Widget_setVisible(self.widget, visible)
            self.__visible = visible

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        if enabled != self.__enabled:
            self.proxy.Widget_setEnabled(self.widget, enabled)
            self.__enabled = enabled

    @property
    def size(self) -> Geometry.IntSize:
        w, h = self.proxy.Widget_getWidgetSize(self.widget)
        return Geometry.IntSize(width=w, height=h)

    @size.setter
    def size(self, size: Geometry.IntSize) -> None:
        self.proxy.Widget_setWidgetSize(self.widget, int(size[1]), int(size[0]))

    @property
    def tool_tip(self) -> typing.Optional[str]:
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        if tool_tip != self.__tool_tip:
            self.proxy.Widget_setToolTip(self.widget, notnone(tool_tip) if tool_tip else str())
            self.__tool_tip = tool_tip

    def set_background_color(self, color: typing.Optional[str]) -> None:
        if color:
            self.proxy.Widget_setPaletteColor(self.widget, "background", *(Color.Color(color or str()).to_rgba_255()))
        else:
            self.proxy.Widget_setPaletteColor(self.widget, "background", 0, 0, 0, 0)

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self._register_ui_activity()

        def drag_finished(action: str) -> None:
            self._register_ui_activity()
            if drag_finished_fn:
                drag_finished_fn(action)

        drag = QtDrag(self.proxy, self.widget, typing.cast(QtMimeData, mime_data), thumbnail, hot_spot_x, hot_spot_y, drag_finished)
        drag.execute()

    def contextMenuEvent(self, x: int, y: int, gx: int, gy: int) -> None:
        self._register_ui_activity()
        if self.on_context_menu_event:
            self.on_context_menu_event(x, y, gx, gy)

    def focusIn(self) -> None:
        self._register_ui_activity()
        if self.on_focus_changed:
            self.on_focus_changed(True)

    def focusOut(self) -> None:
        self._register_ui_activity()
        if self.on_focus_changed:
            self.on_focus_changed(False)

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        gx, gy = self.proxy.Widget_mapToGlobal(self.widget, p.x, p.y)
        return Geometry.IntPoint(x=gx, y=gy)


class QtNullBehavior:  # cannot subclass UserInterface.WidgetBehavior until mypy #4125 is available
    def __init__(self) -> None:
        self.focused = False
        self.does_retain_focus = False
        self.visible = True
        self.enabled = True
        self.size = Geometry.IntSize()
        self.tool_tip: typing.Optional[str] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.widget = None

    def close(self) -> None:
        pass

    def periodic(self) -> None:
        pass

    def _set_root_container(self, window: typing.Optional[Window.Window]) -> None:
        pass

    def _get_content_widget(self) -> typing.Optional[UserInterface.Widget]:
        return None

    def set_property(self, key: str, value: typing.Any) -> None:
        pass

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return Geometry.IntPoint()

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        pass

    def set_background_color(self, value: typing.Optional[str]) -> None:
        pass


class QtBoxStretch(UserInterface.Widget):

    def __init__(self) -> None:
        super().__init__(QtNullBehavior())


class QtBoxSpacing(UserInterface.Widget):

    def __init__(self, spacing: int):
        super().__init__(QtNullBehavior())
        self.spacing = spacing


def extract_widget(widget: typing.Any) -> typing.Optional[UserInterface.Widget]:
    content_widget = widget._behavior._get_content_widget() if widget else None
    if content_widget:
        return extract_widget(content_widget)
    return typing.cast(typing.Optional[UserInterface.Widget], widget._behavior.widget if widget else None)


class QtBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, widget_type, properties)
        self.__widget_type = widget_type

    def insert(self, child: UserInterface.Widget, index: typing.Optional[typing.Union[UserInterface.Widget, int]],
               fill: bool = False, alignment: typing.Optional[str] = None) -> None:
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert self.widget is not None
        assert child_widget is not None
        index = index if index is not None else self.proxy.Widget_widgetCount(self.widget)
        self.proxy.Widget_insertWidget(self.widget, child_widget, index, fill, alignment)

    def add_stretch(self) -> UserInterface.Widget:
        self.proxy.Widget_addStretch(self.widget)
        return QtBoxStretch()

    def add_spacing(self, spacing: int) -> UserInterface.Widget:
        if self.__widget_type == "row":
            space_widget = UserInterface.BoxWidget(QtBoxWidgetBehavior(self.proxy, "row", dict()), None)
            space_widget.set_property("min-width", spacing)
            space_widget.set_property("max-width", spacing)
        else:
            space_widget = UserInterface.BoxWidget(QtBoxWidgetBehavior(self.proxy, "column", dict()), None)
            space_widget.set_property("min-height", spacing)
            space_widget.set_property("max-height", spacing)
        self.insert(space_widget, None)
        return space_widget

    def remove_all(self) -> None:
        self.proxy.Widget_removeAll(self.widget)


class QtSplitterWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "splitter", properties)
        self.__orientation: typing.Optional[str] = "vertical"
        self.__children: typing.List[UserInterface.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    @property
    def orientation(self) -> typing.Optional[str]:
        return self.__orientation

    @orientation.setter
    def orientation(self, value: typing.Optional[str]) -> None:
        self.__orientation = value
        self.proxy.Splitter_setOrientation(self.widget, self.__orientation)

    def add(self, child: UserInterface.Widget) -> None:
        self.__children.append(child)
        self.proxy.Widget_addWidget(self.widget, extract_widget(child))

    def restore_state(self, tag: str) -> None:
        self.proxy.Splitter_restoreState(self.widget, tag)

    def save_state(self, tag: str) -> None:
        self.proxy.Splitter_saveState(self.widget, tag)

    def set_sizes(self, sizes: typing.Sequence[int]) -> None:
        self.proxy.Splitter_setSizes(self.widget, sizes)


class QtTabWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "tab", properties)
        self.__current_index = -1
        self.on_current_index_changed : typing.Optional[typing.Callable[[int], None]] = None
        self.proxy.TabWidget_connect(self.widget, self)
        self.__children: typing.List[UserInterface.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        self.on_current_index_changed = None
        super().close()

    def add(self, child: UserInterface.Widget, label: str) -> None:
        self.__children.append(child)
        self.proxy.TabWidget_addTab(self.widget, extract_widget(child), notnone(label))

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass

    def currentTabChanged(self, index: int) -> None:
        self._register_ui_activity()
        if callable(self.on_current_index_changed):
            self.on_current_index_changed(index)

    @property
    def current_index(self) -> int:
        return self.__current_index

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index = index
        self.proxy.TabWidget_setCurrentIndex(self.widget, index)


class QtStackWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "stack", properties)
        self.__current_index = -1
        self.__children: typing.List[UserInterface.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def insert(self, child: UserInterface.Widget, index: int) -> None:
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert self.widget is not None
        assert child_widget is not None
        index = index if index is not None else self.proxy.Widget_widgetCount(self.widget)
        self.__children.insert(index, child)
        self.proxy.StackWidget_insertWidget(self.widget, child_widget, index)

    def add(self, child: UserInterface.Widget) -> None:
        self.__children.append(child)
        self.proxy.StackWidget_addWidget(self.widget, extract_widget(child))

    def remove(self, child: UserInterface.Widget) -> None:
        self.proxy.StackWidget_removeWidget(self.widget, extract_widget(child))
        self.__children.remove(child)
        child.close()

    @property
    def current_index(self) -> int:
        return self.__current_index

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index = index
        self.proxy.StackWidget_setCurrentIndex(self.widget, index)
        # see sizing notes:
        # https://wiki.qt.io/Technical_FAQ#How_can_I_get_a_QStackedWidget_to_automatically_switch_size_depending_on_the_content_of_the_page.3F
        # https://stackoverflow.com/questions/14480696/resize-qstackedwidget-to-the-page-which-is-opened
        for i in range(self.proxy.Widget_widgetCount(self.widget)):
            widget = self.proxy.Widget_widgetByIndex(self.widget, i)
            self.proxy.Widget_setWidgetProperty(widget, "size-policy-horizontal", "preferred" if i == index else "ignored")
            self.proxy.Widget_setWidgetProperty(widget, "size-policy-vertical", "preferred" if i == index else "ignored")
            self.proxy.Widget_adjustSize(widget)
        self.proxy.Widget_adjustSize(self.widget)


class QtGroupWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "group", properties)
        self.__title: typing.Optional[str] = None
        self.__children: typing.List[UserInterface.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def add(self, child: UserInterface.Widget) -> None:
        self.__children.append(child)
        self.proxy.Widget_addWidget(self.widget, extract_widget(child))

    def remove(self, child: UserInterface.Widget) -> None:
        self.proxy.Widget_removeWidget(self.widget, extract_widget(child))
        self.__children.remove(child)
        child.close()

    @property
    def title(self) -> typing.Optional[str]:
        return self.__title

    @title.setter
    def title(self, value: typing.Optional[str]) -> None:
        self.__title = value
        self.proxy.GroupBoxWidget_setTitle(self.widget, notnone(value))


class QtScrollAreaWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "scrollarea", properties)
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_viewport_changed: typing.Optional[typing.Callable[[Geometry.RectIntTuple], None]] = None
        self.proxy.ScrollArea_connect(self.widget, self)

    def close(self) -> None:
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    def set_content(self, content: typing.Optional[UserInterface.Widget]) -> None:
        self.proxy.ScrollArea_setWidget(self.widget, extract_widget(content))

    def sizeChanged(self, width: int, height: int) -> None:
        self._register_ui_activity()
        if callable(self.on_size_changed):
            self.on_size_changed(width, height)

    def viewportChanged(self, left: int, top: int, width: int, height: int) -> None:
        if callable(self.on_viewport_changed):
            viewport = (top, left), (height, width)
            self.on_viewport_changed(viewport)

    def scroll_to(self, x: int, y: int) -> None:
        self.proxy.ScrollArea_setHorizontal(self.widget, float(x))
        self.proxy.ScrollArea_setVertical(self.widget, float(y))

    def set_scrollbar_policies(self, horizontal_policy: str, vertical_policy: str) -> None:
        self.proxy.ScrollArea_setScrollbarPolicies(self.widget, horizontal_policy, vertical_policy)

    def info(self) -> None:
        self.proxy.ScrollArea_info(self.widget)


class QtComboBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "combobox", properties)
        self.on_current_text_changed: typing.Optional[typing.Callable[[str], None]] = None
        self.proxy.ComboBox_connect(self.widget, self)

    def close(self) -> None:
        self.on_current_text_changed = None
        super().close()

    @property
    def current_text(self) -> str:
        return typing.cast(str, self.proxy.ComboBox_getCurrentText(self.widget))

    @current_text.setter
    def current_text(self, value: str) -> None:
        self.proxy.ComboBox_setCurrentText(self.widget, notnone(value))

    def set_item_strings(self, item_strings: typing.Sequence[str]) -> None:
        # note: do not send on_current_text_changed during this method
        # this problem occurred in camera panel during binning init
        on_current_text_changed = self.on_current_text_changed
        try:
            self.on_current_text_changed = None
            self.proxy.ComboBox_removeAllItems(self.widget)
            for item_string in item_strings:
                self.proxy.ComboBox_addItem(self.widget, item_string)
        finally:
            self.on_current_text_changed = on_current_text_changed

    # this message comes from Qt implementation
    def currentTextChanged(self, text: str) -> None:
        self._register_ui_activity()
        if callable(self.on_current_text_changed):
            self.on_current_text_changed(text)


class QtPushButtonWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "pushbutton", properties)
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None
        self.__text: typing.Optional[str] = None
        self.__icon: typing.Optional[DrawingContext.RGBA32Type] = None
        self.proxy.PushButton_connect(self.widget, self)

    def close(self) -> None:
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text = self.proxy.encode_text(text)
        self.proxy.PushButton_setText(self.widget, self.__text)

    @property
    def icon(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__icon

    @icon.setter
    def icon(self, rgba_image: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        # rgba_image should be a uint32 numpy array with the pixel order bgra
        self.__icon = rgba_image
        width = rgba_image.shape[1] if rgba_image is not None else 0
        height = rgba_image.shape[0] if rgba_image is not None else 0
        rgba_data = self.proxy.encode_data(rgba_image)
        self.proxy.PushButton_setIcon(self.widget, width, height, rgba_data)

    def clicked(self) -> None:
        self._register_ui_activity()
        if callable(self.on_clicked):
            self.on_clicked()


class QtRadioButtonWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "radiobutton", properties)
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None
        self.__text: typing.Optional[str] = None
        self.__icon: typing.Optional[DrawingContext.RGBA32Type] = None
        self.proxy.RadioButton_connect(self.widget, self)

    def close(self) -> None:
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text = self.proxy.encode_text(text)
        self.proxy.RadioButton_setText(self.widget, self.__text)

    @property
    def icon(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__icon

    @icon.setter
    def icon(self, rgba_image: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        # rgba_image should be a uint32 numpy array with the pixel order bgra
        self.__icon = rgba_image
        self.__width = rgba_image.shape[1] if rgba_image is not None else 0
        self.__height = rgba_image.shape[0] if rgba_image is not None else 0
        rgba_data = self.proxy.encode_data(rgba_image)
        self.proxy.RadioButton_setIcon(self.widget, self.__width, self.__height, rgba_data)

    @property
    def checked(self) -> bool:
        return bool(self.proxy.RadioButton_getChecked(self.widget))

    @checked.setter
    def checked(self, value: bool) -> None:
        self.proxy.RadioButton_setChecked(self.widget, value)

    def clicked(self) -> None:
        self._register_ui_activity()
        if callable(self.on_clicked):
            self.on_clicked()


class QtButtonGroup:

    def __init__(self, proxy: _QtProxy):
        self.proxy = proxy
        self.py_button_group = self.proxy.ButtonGroup_create()
        self.proxy.ButtonGroup_connect(self.py_button_group, self)
        self.on_button_clicked: typing.Optional[typing.Callable[[str], None]] = None

    def close(self) -> None:
        self.proxy.ButtonGroup_destroy(self.py_button_group)
        self.proxy = None
        self.on_button_clicked = None

    def add_button(self, radio_button: UserInterface.RadioButtonWidget, button_id: str) -> None:
        self.proxy.ButtonGroup_addButton(self.py_button_group, extract_widget(radio_button), button_id)

    def remove_button(self, radio_button: UserInterface.RadioButtonWidget) -> None:
        self.proxy.ButtonGroup_removeButton(self.py_button_group, extract_widget(radio_button))

    def clicked(self, button_id: str) -> None:
        if self.on_button_clicked:
            self.on_button_clicked(button_id)


class QtCheckBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "checkbox", properties)
        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None
        self.__blocked = False  # setting check state programmatically shouldn't notify
        self.__text: typing.Optional[str] = None
        self.proxy.CheckBox_connect(self.widget, self)

    def close(self) -> None:
        self.on_check_state_changed = None
        super().close()

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.__text = value
        self.proxy.CheckBox_setText(self.widget, notnone(value))

    @property
    def tristate(self) -> bool:
        return bool(self.proxy.CheckBox_getIsTristate(self.widget))

    @tristate.setter
    def tristate(self, value: bool) -> None:
        self.proxy.CheckBox_setIsTristate(self.widget, bool(value))

    @property
    def check_state(self) -> str:
        return typing.cast(str, self.proxy.CheckBox_getCheckState(self.widget))

    @check_state.setter
    def check_state(self, value: str) -> None:
        self.__blocked = True
        try:
            self.proxy.CheckBox_setCheckState(self.widget, str(value))
        finally:
            self.__blocked = False

    def stateChanged(self, check_state: str) -> None:
        if not self.__blocked:
            self._register_ui_activity()
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)


class QtLabelWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "label", properties)
        self.__text: typing.Optional[str] = None
        self.__word_wrap = False

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text = text if text else ""
        self.proxy.Label_setText(self.widget, self.__text)

    def set_text_color(self, color: typing.Optional[str]) -> None:
        self.proxy.Label_setTextColor(self.widget, *(Color.Color(color or str()).to_rgb_255()))

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        self.proxy.Label_setTextFont(self.widget, font_str or str())

    @property
    def word_wrap(self) -> bool:
        return self.__word_wrap

    @word_wrap.setter
    def word_wrap(self, value: bool) -> None:
        self.__word_wrap = value
        self.proxy.Label_setWordWrap(self.widget, value)


class QtSliderWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "slider", properties)
        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.on_slider_pressed: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_released: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_moved: typing.Optional[typing.Callable[[int], None]] = None
        self.__pressed = False
        self.__min = 0
        self.__max = 0
        self.proxy.Slider_connect(self.widget, self)

    def close(self) -> None:
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        super().close()

    @property
    def value(self) -> int:
        return typing.cast(int, self.proxy.Slider_getValue(self.widget))

    @value.setter
    def value(self, value: int) -> None:
        self.proxy.Slider_setValue(self.widget, value)

    @property
    def minimum(self) -> int:
        return self.__min

    @minimum.setter
    def minimum(self, value: int) -> None:
        self.__min = value
        self.proxy.Slider_setMinimum(self.widget, value)

    @property
    def maximum(self) -> int:
        return self.__max

    @maximum.setter
    def maximum(self, value: int) -> None:
        self.__max = value
        self.proxy.Slider_setMaximum(self.widget, value)

    @property
    def pressed(self) -> bool:
        return self.__pressed

    def valueChanged(self, value: int) -> None:
        self._register_ui_activity()
        if callable(self.on_value_changed):
            self.on_value_changed(value)

    def sliderPressed(self) -> None:
        self._register_ui_activity()
        self.__pressed = True
        if callable(self.on_slider_pressed):
            self.on_slider_pressed()

    def sliderReleased(self) -> None:
        self._register_ui_activity()
        self.__pressed = False
        if callable(self.on_slider_released):
            self.on_slider_released()

    def sliderMoved(self, value: int) -> None:
        self._register_ui_activity()
        if callable(self.on_slider_moved):
            self.on_slider_moved(value)


class QtLineEditWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "lineedit", properties)
        self.on_editing_finished: typing.Optional[typing.Callable[[str], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[str], None]] = None
        self.proxy.LineEdit_connect(self.widget, self)
        self.__clear_button_enabled = False
        self._no_focus = "click_focus"

    def close(self) -> None:
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def text(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.LineEdit_getText(self.widget))

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.proxy.LineEdit_setText(self.widget, notnone(text))

    @property
    def placeholder_text(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.LineEdit_getPlaceholderText(self.widget))

    @placeholder_text.setter
    def placeholder_text(self, text: typing.Optional[str]) -> None:
        self.proxy.LineEdit_setPlaceholderText(self.widget, notnone(text))

    @property
    def selected_text(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.LineEdit_getSelectedText(self.widget))

    @property
    def clear_button_enabled(self) -> bool:
        return self.__clear_button_enabled

    @clear_button_enabled.setter
    def clear_button_enabled(self, enabled: bool) -> None:
        self.__clear_button_enabled = enabled
        self.proxy.LineEdit_setClearButtonEnabled(self.widget, enabled)

    @property
    def editable(self) -> bool:
        return bool(self.proxy.LineEdit_getEditable(self.widget))

    @editable.setter
    def editable(self, editable: bool) -> None:
        self.proxy.LineEdit_setEditable(self.widget, editable)

    def select_all(self) -> None:
        self.proxy.LineEdit_selectAll(self.widget)

    def editing_finished(self, text: str) -> None:
        pass

    def editingFinished(self, text: str) -> None:
        self._register_ui_activity()
        if self.on_editing_finished:
            self.on_editing_finished(text)

    def escapePressed(self) -> bool:
        self._register_ui_activity()
        if callable(self.on_escape_pressed):
            return self.on_escape_pressed()
        return False

    def returnPressed(self) -> bool:
        self._register_ui_activity()
        if callable(self.on_return_pressed):
            return self.on_return_pressed()
        return False

    def keyPressed(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def textEdited(self, text: str) -> None:
        self._register_ui_activity()
        if callable(self.on_text_edited):
            self.on_text_edited(text)


class QtTextEditWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "textedit", properties)
        self.__word_wrap_mode = "optimal"
        self.on_cursor_position_changed: typing.Optional[typing.Callable[[UserInterface.CursorPosition], None]] = None
        self.on_selection_changed: typing.Optional[typing.Callable[[UserInterface.Selection], None]] = None
        self.on_text_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_insert_mime_data: typing.Optional[typing.Callable[[UserInterface.MimeData], None]] = None
        self.proxy.TextEdit_connect(self.widget, self)
        self._no_focus = "click_focus"

    def close(self) -> None:
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        super().close()

    @property
    def text(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.TextEdit_getText(self.widget))

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.proxy.TextEdit_setText(self.widget, notnone(value))

    @property
    def placeholder(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.TextEdit_getPlaceholderText(self.widget))

    @placeholder.setter
    def placeholder(self, value: typing.Optional[str]) -> None:
        self.proxy.TextEdit_setPlaceholderText(self.widget, notnone(value))

    @property
    def editable(self) -> bool:
        return bool(self.proxy.TextEdit_getEditable(self.widget))

    @editable.setter
    def editable(self, value: bool) -> None:
        self.proxy.TextEdit_setEditable(self.widget, value)

    @property
    def selected_text(self) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.TextEdit_getSelectedText(self.widget))

    @property
    def cursor_position(self) -> UserInterface.CursorPosition:
        position, block_number, column_number, _, _ = self.proxy.TextEdit_getCursorInfo(self.widget)
        return UserInterface.CursorPosition(position, block_number, column_number)

    @property
    def selection(self) -> UserInterface.Selection:
        _, _, _, start, end = self.proxy.TextEdit_getCursorInfo(self.widget)
        return UserInterface.Selection(start, end)

    def append_text(self, value: str) -> None:
        self.proxy.TextEdit_appendText(self.widget, notnone(value))

    def insert_text(self, value: str) -> None:
        self.proxy.TextEdit_insertText(self.widget, notnone(value))

    def clear_selection(self) -> None:
        self.proxy.TextEdit_clearSelection(self.widget)

    def remove_selected_text(self) -> None:
        self.proxy.TextEdit_removeSelectedText(self.widget)

    def select_all(self) -> None:
        self.proxy.TextEdit_selectAll(self.widget)

    def move_cursor_position(self, operation: str, mode: typing.Optional[str] = None, n: int = 1) -> None:
        self.proxy.TextEdit_moveCursorPosition(self.widget, operation, mode, n)

    def set_line_height_proportional(self, proportional_line_height: float) -> None:
        self.proxy.TextEdit_setProportionalLineHeight(self.widget, proportional_line_height)

    def set_text_background_color(self, color: typing.Optional[str]) -> None:
        self.proxy.TextEdit_setTextBackgroundColor(self.widget, *(Color.Color(color or str()).to_rgb_255()))

    def set_text_color(self, color: typing.Optional[str]) -> None:
        self.proxy.TextEdit_setTextColor(self.widget, *(Color.Color(color or str()).to_rgb_255()))

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        self.proxy.TextEdit_setTextFont(self.widget, font_str or str())

    @property
    def word_wrap_mode(self) -> str:
        return self.__word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, value: str) -> None:
        self.__word_wrap_mode = value
        self.proxy.TextEdit_setWordWrapMode(self.widget, value)

    def cursorPositionChanged(self) -> None:
        self._register_ui_activity()
        if callable(self.on_cursor_position_changed):
            self.on_cursor_position_changed(self.cursor_position)

    def selectionChanged(self) -> None:
        self._register_ui_activity()
        if callable(self.on_selection_changed):
            self.on_selection_changed(self.selection)

    def textChanged(self) -> None:
        self._register_ui_activity()
        if callable(self.on_text_changed):
            self.on_text_changed(self.text)
        if callable(self.on_text_edited):
            self.on_text_edited(self.text)

    def escapePressed(self) -> bool:
        self._register_ui_activity()
        if callable(self.on_escape_pressed):
            return self.on_escape_pressed()
        return False

    def returnPressed(self) -> bool:
        self._register_ui_activity()
        if callable(self.on_return_pressed):
            return self.on_return_pressed()
        return False

    def keyPressed(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def insertFromMimeData(self, raw_mime_data: _QtObject) -> None:
        self._register_ui_activity()
        mime_data = QtMimeData(self.proxy, raw_mime_data)
        if callable(self.on_insert_mime_data):
            self.on_insert_mime_data(mime_data)
        else:
            self.insert_text(mime_data.data_as_string("text/plain"))


class QtCanvasWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(proxy, "canvas", properties)
        self.proxy.Canvas_connect(self.widget, self)
        self.on_mouse_entered: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_exited: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_clicked: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_double_clicked: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_pressed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_released: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], None]] = None
        self.on_grabbed_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], None]] = None
        self.on_wheel_changed: typing.Optional[typing.Callable[[int, int, int, int, bool], bool]] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_key_released: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_drag_enter: typing.Optional[typing.Callable[[UserInterface.MimeData], str]] = None
        self.on_drag_leave: typing.Optional[typing.Callable[[], str]] = None
        self.on_drag_move: typing.Optional[typing.Callable[[UserInterface.MimeData, int, int], str]] = None
        self.on_drop: typing.Optional[typing.Callable[[UserInterface.MimeData, int, int], str]] = None
        self.on_tool_tip: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_pan_gesture: typing.Optional[typing.Callable[[int, int], bool]] = None
        self.__focusable = False

    def close(self) -> None:
        self.on_mouse_entered = None
        self.on_mouse_exited = None
        self.on_mouse_clicked = None
        self.on_mouse_double_clicked = None
        self.on_mouse_pressed = None
        self.on_mouse_released = None
        self.on_mouse_position_changed = None
        self.on_grabbed_mouse_position_changed = None
        self.on_wheel_changed = None
        self.on_key_pressed = None
        self.on_key_released = None
        self.on_size_changed = None
        self.on_drag_enter = None
        self.on_drag_leave = None
        self.on_drag_move = None
        self.on_drop = None
        self.on_tool_tip = None
        self.on_pan_gesture = None
        super().close()

    def _set_canvas_item(self, canvas_item: CanvasItem.AbstractCanvasItem) -> None:
        pass

    @property
    def focusable(self) -> bool:
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        self.__focusable = focusable
        self.proxy.Widget_setFocusPolicy(self.widget, "wheel_focus" if focusable else "no_focus")

    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None:
        if hasattr(self.proxy, "Canvas_draw_binary"):
            self.proxy.Canvas_draw_binary(self.widget, drawing_context.binary_commands, drawing_context.images)
        else:
            self.proxy.Canvas_draw(self.widget, self.proxy.convert_drawing_commands(drawing_context.commands), drawing_context.images)

    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        if hasattr(self.proxy, "Canvas_drawSection_binary"):
            self.proxy.Canvas_drawSection_binary(self.widget, section_id, drawing_context.binary_commands, drawing_context.images, canvas_rect.left, canvas_rect.top, canvas_rect.width, canvas_rect.height)
        else:
            self.proxy.Canvas_drawSection(self.widget, section_id, self.proxy.convert_drawing_commands(drawing_context.commands), drawing_context.images, canvas_rect.left, canvas_rect.top, canvas_rect.width, canvas_rect.height)

    def remove_section(self, section_id: int) -> None:
        self.proxy.Canvas_removeSection(self.widget, section_id)

    def set_cursor_shape(self, cursor_shape: typing.Optional[str]) -> None:
        cursor_shape = cursor_shape or "arrow"
        self.proxy.Canvas_setCursorShape(self.widget, cursor_shape)

    def grab_gesture(self, gesture_type: str) -> None:
        self.proxy.Widget_grabGesture(self.widget, gesture_type)

    def release_gesture(self, gesture_type: str) -> None:
        self.proxy.Widget_ungrabGesture(self.widget, gesture_type)

    def grab_mouse(self, gx: int, gy: int) -> None:
        self.proxy.Canvas_grabMouse(self.widget, gx, gy)

    def release_mouse(self) -> None:
        self.proxy.Canvas_releaseMouse(self.widget)

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        self.proxy.ToolTip_show(self.widget, gx, gy, text, 0, 0, 0, 0)

    def mouseEntered(self) -> None:
        if callable(self.on_mouse_entered):
            self.on_mouse_entered()

    def mouseExited(self) -> None:
        if callable(self.on_mouse_exited):
            self.on_mouse_exited()

    def mouseClicked(self, x: int, y: int, raw_modifiers: int) -> None:
        self._register_ui_activity()
        if callable(self.on_mouse_clicked):
            self.on_mouse_clicked(x, y, QtKeyboardModifiers(raw_modifiers))

    def mouseDoubleClicked(self, x: int, y: int, raw_modifiers: int) -> None:
        self._register_ui_activity()
        if callable(self.on_mouse_double_clicked):
            self.on_mouse_double_clicked(x, y, QtKeyboardModifiers(raw_modifiers))

    def mousePressed(self, x: int, y: int, raw_modifiers: int) -> None:
        self._register_ui_activity()
        if callable(self.on_mouse_pressed):
            self.on_mouse_pressed(x, y, QtKeyboardModifiers(raw_modifiers))

    def mouseReleased(self, x: int, y: int, raw_modifiers: int) -> None:
        self._register_ui_activity()
        if callable(self.on_mouse_released):
            self.on_mouse_released(x, y, QtKeyboardModifiers(raw_modifiers))

    def mousePositionChanged(self, x: int, y: int, raw_modifiers: int) -> None:
        if callable(self.on_mouse_position_changed):
            self.on_mouse_position_changed(x, y, QtKeyboardModifiers(raw_modifiers))

    def grabbedMousePositionChanged(self, dx: int, dy: int, raw_modifiers: int) -> None:
        self._register_ui_activity()
        if callable(self.on_grabbed_mouse_position_changed):
            self.on_grabbed_mouse_position_changed(dx, dy, QtKeyboardModifiers(raw_modifiers))

    def wheelChanged(self, x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> None:
        self._register_ui_activity()
        if callable(self.on_wheel_changed):
            self.on_wheel_changed(x, y, dx, dy, is_horizontal)

    def sizeChanged(self, width: int, height: int) -> None:
        self._register_ui_activity()
        if callable(self.on_size_changed):
            self.on_size_changed(width, height)

    def keyPressed(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def keyReleased(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_key_released):
            return self.on_key_released(QtKey(text, key, raw_modifiers))
        return False

    def dragEnterEvent(self, raw_mime_data: _QtObject) -> str:
        self._register_ui_activity()
        if callable(self.on_drag_enter):
            return self.on_drag_enter(QtMimeData(self.proxy, raw_mime_data))
        return "ignore"

    def dragLeaveEvent(self) -> str:
        self._register_ui_activity()
        if callable(self.on_drag_leave):
            return self.on_drag_leave()
        return "ignore"

    def dragMoveEvent(self, raw_mime_data: _QtObject, x: int, y: int) -> str:
        self._register_ui_activity()
        if callable(self.on_drag_move):
            return self.on_drag_move(QtMimeData(self.proxy, raw_mime_data), x, y)
        return "ignore"

    def dropEvent(self, raw_mime_data: _QtObject, x: int, y: int) -> str:
        self._register_ui_activity()
        if callable(self.on_drop):
            return self.on_drop(QtMimeData(self.proxy, raw_mime_data), x, y)
        return "ignore"

    def helpEvent(self, x: int, y: int, gx: int, gy: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_tool_tip):
            return self.on_tool_tip(x, y, gx, gy)
        return False

    def panGesture(self, delta_x: int, delta_y: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_pan_gesture):
            return self.on_pan_gesture(delta_x, delta_y)
        return False


class QtTreeWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy: _QtProxy, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        properties = dict(properties) if properties is not None else dict()
        properties["stylesheet"] = "* { border: none; background-color: '#EEEEEE'; } TreeWidget { margin-top: 0px }"
        super().__init__(proxy, "pytree", properties)
        self.proxy.TreeWidget_connect(self.widget, self)
        self.__item_model_controller = None
        self.on_key_pressed: typing.Optional[typing.Callable[[typing.Sequence[int], UserInterface.Key], bool]] = None
        self.on_tree_selection_changed: typing.Optional[typing.Callable[[typing.Sequence[typing.Tuple[int, int, int]]], None]] = None
        self.on_tree_item_changed: typing.Optional[typing.Callable[[int, int, int], None]] = None
        self.on_tree_item_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_tree_item_double_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_tree_item_key_pressed: typing.Optional[typing.Callable[[int, int, int, UserInterface.Key], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.__selection_mode = "single"
        self.__block_selected_changed = False

    def close(self) -> None:
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_tree_selection_changed = None
        self.on_tree_item_changed = None
        self.on_tree_item_clicked = None
        self.on_tree_item_double_clicked = None
        self.on_tree_item_key_pressed = None
        self.on_focus_changed = None
        super().close()

    @property
    def selection_mode(self) -> str:
        return self.__selection_mode

    @selection_mode.setter
    def selection_mode(self, selection_mode: str) -> None:
        self.__selection_mode = selection_mode
        self.proxy.TreeWidget_setSelectionMode(self.widget, selection_mode)

    @property
    def item_model_controller(self) -> typing.Any:
        return self.__item_model_controller

    @item_model_controller.setter
    def item_model_controller(self, item_model_controller: typing.Any) -> None:
        self.__item_model_controller = item_model_controller
        self.proxy.TreeWidget_setModel(self.widget, item_model_controller.py_item_model)

    def set_current_row(self, index: int, parent_row: int, parent_id: int) -> None:
        old_block_selected_changed = self.__block_selected_changed
        self.__block_selected_changed = True
        try:
            self.proxy.TreeWidget_setCurrentRow(self.widget, index, parent_row, parent_id)
        finally:
            self.__block_selected_changed = old_block_selected_changed

    def clear_current_row(self) -> None:
        old_block_selected_changed = self.__block_selected_changed
        self.__block_selected_changed = True
        try:
            self.proxy.TreeWidget_setCurrentRow(self.widget, -1, -1, 0)
        finally:
            self.__block_selected_changed = old_block_selected_changed

    def size_to_content(self) -> None:
        self.proxy.TreeWidget_resizeToContent(self.widget)

    def keyPressed(self, indexes: typing.Sequence[int], text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_key_pressed):
            return self.on_key_pressed(indexes, QtKey(text, key, raw_modifiers))
        return False

    def treeItemChanged(self, index: int, parent_row: int, parent_id: int) -> None:
        if callable(self.on_tree_item_changed):
            self.on_tree_item_changed(index, parent_row, parent_id)

    def treeSelectionChanged(self, selected_indexes: typing.Sequence[typing.Tuple[int, int, int]]) -> None:
        self._register_ui_activity()
        if not self.__block_selected_changed:
            if callable(self.on_tree_selection_changed):
                self.on_tree_selection_changed(selected_indexes)

    def treeItemKeyPressed(self, index: int, parent_row: int, parent_id: int, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_tree_item_key_pressed):
            return self.on_tree_item_key_pressed(index, parent_row, parent_id, QtKey(text, key, raw_modifiers))
        return False

    def treeItemClicked(self, index: int, parent_row: int, parent_id: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_tree_item_clicked):
            return self.on_tree_item_clicked(index, parent_row, parent_id)
        return False

    def treeItemDoubleClicked(self, index: int, parent_row: int, parent_id: int) -> bool:
        self._register_ui_activity()
        if callable(self.on_tree_item_double_clicked):
            return self.on_tree_item_double_clicked(index, parent_row, parent_id)
        return False

    def focusIn(self) -> None:
        self._register_ui_activity()
        if callable(self.on_focus_changed):
            self.on_focus_changed(True)

    def focusOut(self) -> None:
        self._register_ui_activity()
        if callable(self.on_focus_changed):
            self.on_focus_changed(False)


class QtAction(UserInterface.MenuAction):

    def __init__(self, proxy: _QtProxy, native_action: typing.Optional[_QtObject] = None) -> None:
        super().__init__()
        self.proxy = proxy
        self.native_action = native_action  # action is not connected since native_action will not by PyAction
        self.__title = str()

    def close(self) -> None:
        self.proxy = None
        self.native_action = None
        super().close()

    def create(self, document_window: UserInterface.Window, title: str, key_sequence: typing.Optional[str], role: typing.Optional[str]) -> None:
        self.native_action = self.proxy.Action_create(typing.cast(QtWindow, document_window).native_document_window, title, key_sequence, role)
        self.proxy.Action_connect(self.native_action, self)
        self.__title = title

    @property
    def title(self) -> str:
        return typing.cast(str, self.proxy.Action_getTitle(self.native_action) if self.native_action else str())

    @title.setter
    def title(self, value: str) -> None:
        self.proxy.Action_setTitle(self.native_action, value)
        self.__title = value

    @property
    def checked(self) -> bool:
        return bool(self.proxy.Action_getChecked(self.native_action)) if self.native_action else False

    @checked.setter
    def checked(self, checked: bool) -> None:
        self.proxy.Action_setChecked(self.native_action, checked)

    @property
    def enabled(self) -> bool:
        return bool(self.proxy.Action_getEnabled(self.native_action)) if self.native_action else True

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self.proxy.Action_setEnabled(self.native_action, enabled)

    # comes from the Qt code
    def triggered(self) -> None:
        self._register_ui_activity()
        self.trigger()


class QtMenu(UserInterface.Menu):

    def __init__(self, document_window: QtWindow, title: str, menu_id: str, proxy: _QtProxy, native_menu: _QtObject) -> None:
        super().__init__(document_window, title, menu_id)
        self.proxy = proxy
        self.native_menu = native_menu
        self.proxy.Menu_connect(self.native_menu, self)

    def close(self) -> None:
        # what looks like a bug in Qt 5.13 - aboutToHide is called twice. watch for that here.
        # seen in PySide2 and Qt native. reproduce by right clicking context menu and not choosing anything.
        if self.native_menu:
            self.proxy.Menu_destroy(self.native_menu)
        self.native_menu = None
        super().close()

    def aboutToShow(self) -> None:
        self.about_to_show()

    def aboutToHide(self) -> None:
        self.about_to_hide()

    def add_menu_item(self, title: str, callback: typing.Callable[[], None], key_sequence: typing.Optional[str] = None,
                      role: typing.Optional[str] = None, action_id: typing.Optional[str] = None) -> UserInterface.MenuAction:
        action = QtAction(self.proxy)
        self._prepare_action(action, title, action_id, callback, key_sequence, role)
        self.proxy.Menu_addAction(self.native_menu, action.native_action)
        self._item_added(action=action)
        return action

    def add_action(self, action: UserInterface.MenuAction) -> None:
        self.proxy.Menu_addAction(self.native_menu, typing.cast(QtAction, action).native_action)
        self._item_added(action=action)

    def add_sub_menu(self, title: str, menu: UserInterface.Menu) -> None:
        self.proxy.Menu_addMenu(self.native_menu, notnone(title), typing.cast(QtMenu, menu).native_menu)
        self._item_added(sub_menu=menu)

    def add_separator(self) -> None:
        self.proxy.Menu_addSeparator(self.native_menu)
        self._item_added(is_separator=True)

    def insert_menu_item(self, title: str, before_action: UserInterface.MenuAction, callback: typing.Callable[[], None],
                         key_sequence: typing.Optional[str] = None, role: typing.Optional[str] = None,
                         action_id: typing.Optional[str] = None) -> None:
        action = QtAction(self.proxy)
        self._prepare_action(action, title, action_id, callback, key_sequence, role)
        self.proxy.Menu_insertAction(self.native_menu, action.native_action, typing.cast(QtAction, before_action).native_action)
        self._item_inserted(before_action, action=action)

    def insert_separator(self, before_action: UserInterface.MenuAction) -> None:
        self.proxy.Menu_insertSeparator(self.native_menu, typing.cast(QtAction, before_action).native_action)
        self._item_inserted(before_action, is_separator=True)

    def remove_action(self, action: UserInterface.MenuAction) -> None:
        self.proxy.Menu_removeAction(self.native_menu, typing.cast(QtAction, action).native_action)
        self._item_removed(action=action)

    def popup(self, gx: int, gy: int) -> None:
        self.proxy.Menu_popup(self.native_menu, gx, gy)


class QtWindow(UserInterface.Window):

    def __init__(self, proxy: _QtProxy, parent: typing.Optional[UserInterface.Window], title: str) -> None:
        super().__init__(parent, title)
        self.proxy = proxy
        parent_native: typing.Optional[_QtObject] = typing.cast(QtWindow, parent).native_document_window if parent else None
        self.native_document_window: _QtObject = self.proxy.DocumentWindow_create(parent_native, title)
        self.proxy.DocumentWindow_connect(self.native_document_window, self)

    def close(self) -> None:
        # this is a callback and should not be invoked directly from Python;
        # call request_close instead.
        assert self.native_document_window is not None
        self.native_document_window = None
        self.proxy = None
        super().close()

    def request_close(self) -> None:
        self.proxy.DocumentWindow_close(self.native_document_window)

    def _attach_root_widget(self, root_widget: typing.Optional[UserInterface.Widget]) -> None:
        self.proxy.DocumentWindow_setCentralWidget(self.native_document_window, extract_widget(root_widget))

    def _get_focus_widget(self) -> typing.Optional[UserInterface.Widget]:
        def match_native_widget(widget: typing.Optional[UserInterface.Widget]) -> typing.Optional[UserInterface.Widget]:
            if widget and widget.focused:
                return widget
            for child_widget in (widget._contained_widgets if widget else list()):
                matched_widget = match_native_widget(child_widget)
                if matched_widget:
                    return matched_widget
            return None
        return match_native_widget(self.root_widget)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_paths, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "loadmany", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_paths, filter, directory

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "load", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "save", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        return typing.cast(typing.Optional[str], self.proxy.DocumentWindow_getColorDialog(self.native_document_window, color, show_alpha))

    def create_dock_widget(self, widget: UserInterface.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> UserInterface.DockWidget:
        return QtDockWidget(self.proxy, self, widget, panel_id, title, positions, position)

    def tabify_dock_widgets(self, dock_widget1: UserInterface.DockWidget, dock_widget2: UserInterface.DockWidget) -> None:
        self.proxy.DocumentWindow_tabifyDockWidgets(self.native_document_window,
                                                    typing.cast(QtDockWidget, dock_widget1).native_dock_widget,
                                                    typing.cast(QtDockWidget, dock_widget2).native_dock_widget)

    def _get_screen_size(self) -> Geometry.IntSize:
        w, h = self.proxy.DocumentWindow_getScreenSize(self.native_document_window)
        return Geometry.IntSize(width=w, height=h)

    def _get_screen_logical_dpi(self) -> float:
        return typing.cast(float, self.proxy.DocumentWindow_getScreenDPIInfo(self.native_document_window)[0])

    def _get_screen_physical_dpi(self) -> float:
        return typing.cast(float, self.proxy.DocumentWindow_getScreenDPIInfo(self.native_document_window)[1])

    def _get_display_scaling(self) -> float:
        return typing.cast(float, self.proxy.DocumentWindow_getDisplayScaling(self.native_document_window))

    def show(self, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        if size is not None:
            self.proxy.DocumentWindow_setSize(self.native_document_window, size.width, size.height)
        if position is not None:
            self.proxy.DocumentWindow_setPosition(self.native_document_window, position.x, position.y)
        if not hasattr(self.proxy, "Widget_setPaletteColor"):
            self.window_style = self.window_style or "tool"
        self.proxy.DocumentWindow_show(self.native_document_window, self.window_style)

    def activate(self) -> None:
        if self.proxy.has_method("DocumentWindow_activate"):
            self.proxy.DocumentWindow_activate(self.native_document_window)

    def fill_screen(self) -> None:
        screen_size = self.screen_size
        self.proxy.DocumentWindow_setPosition(self.native_document_window, 0, 0)
        self.proxy.DocumentWindow_setSize(self.native_document_window, screen_size.width, screen_size.height)

    def _set_title(self, value: str) -> None:
        self.proxy.DocumentWindow_setTitle(self.native_document_window, notnone(value))

    def _set_window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        if self.proxy.has_method("DocumentWindow_setWindowFilePath"):
            self.proxy.DocumentWindow_setWindowFilePath(self.native_document_window, str(value) if value else str())

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        if hasattr(self.proxy, "Widget_setPaletteColor"):
            self.proxy.Widget_setPaletteColor(self.native_document_window, role, r, g, b, a)

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        if hasattr(self.proxy, "DocumentWindow_setWindowStyle"):
            self.proxy.DocumentWindow_setWindowStyle(self.native_document_window, styles)
        else:
            self.window_style = "tool"

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        if hasattr(self.proxy, "Widget_setAttributes"):
            self.proxy.Widget_setAttributes(self.native_document_window, attributes)

    def periodic(self) -> None:
        self._handle_periodic()

    def aboutToShow(self) -> None:
        self._register_ui_activity()
        self._handle_about_to_show()

    def activationChanged(self, activated: bool) -> None:
        self._register_ui_activity()
        self._handle_activation_changed(activated)

    def aboutToClose(self, geometry: str, state: str) -> None:
        self._register_ui_activity()
        self._handle_about_to_close(geometry, state)

    def keyPressed(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        return self._handle_key_pressed(QtKey(text, key, raw_modifiers))

    def keyReleased(self, text: str, key: int, raw_modifiers: int) -> bool:
        self._register_ui_activity()
        return self._handle_key_released(QtKey(text, key, raw_modifiers))

    def add_menu(self, title: str, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        native_menu = self.proxy.DocumentWindow_addMenu(self.native_document_window, notnone(title))
        menu = QtMenu(self, title, menu_id or str(), self.proxy, native_menu)
        self._menu_added(menu)
        return menu

    def insert_menu(self, title: str, before_menu: UserInterface.Menu, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        before_menu = typing.cast(QtMenu, before_menu)
        native_menu = self.proxy.DocumentWindow_insertMenu(self.native_document_window, notnone(title), before_menu.native_menu)
        menu = QtMenu(self, title, menu_id or str(), self.proxy, native_menu)
        self._menu_inserted(menu, before_menu)
        return menu

    def restore(self, geometry: str, state: str) -> None:
        self.proxy.DocumentWindow_restore(self.native_document_window, geometry, state)

    def save(self) -> typing.Tuple[str, str]:
        geometry, state = self.proxy.DocumentWindow_save(self.native_document_window)
        return geometry, state

    def sizeChanged(self, width: int, height: int) -> None:
        self._register_ui_activity()
        self._handle_size_changed(width, height)

    def positionChanged(self, x: int, y: int) -> None:
        self._register_ui_activity()
        self._handle_position_changed(x, y)

    @property
    def position(self) -> Geometry.IntPoint:
        gx, gy = self.proxy.Widget_mapToGlobal(self.native_document_window, 0, 0)
        return Geometry.IntPoint(x=gx, y=gy)

    @property
    def size(self) -> Geometry.IntSize:
        w, h = self.proxy.Widget_getWidgetSize(self.native_document_window)
        return Geometry.IntSize(w=w, h=h)


class QtDockWidget(UserInterface.DockWidget):

    def __init__(self, proxy: _QtProxy, document_window: QtWindow, widget: UserInterface.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> None:
        super().__init__(document_window, widget, panel_id, title, positions, position)
        self.proxy = proxy
        self.__native_document_window = document_window.native_document_window
        self.native_dock_widget: _QtObject = self.proxy.DocumentWindow_addDockWidget(self.__native_document_window, extract_widget(widget), panel_id, notnone(title), positions, position)
        self.proxy.DockWidget_connect(self.native_dock_widget, self)
        self.__focus_policy = self.proxy.Widget_getFocusPolicy(self.native_dock_widget)

    def close(self) -> None:
        # close the child widgets before remove dock widget.
        super().close()
        # this must go after close since remove dock widget will delete all of the widgets.
        self.proxy.DocumentWindow_removeDockWidget(self.__native_document_window, self.native_dock_widget)
        self.native_dock_widget = None
        self.proxy = None

    @property
    def does_retain_focus(self) -> bool:
        return bool(self.proxy.Widget_getFocusPolicy(self.native_dock_widget) == "click_focus")

    @does_retain_focus.setter
    def does_retain_focus(self, does_retain_focus: bool) -> None:
        self.widget.does_retain_focus = does_retain_focus
        if does_retain_focus:
            self.proxy.Widget_setFocusPolicy(self.native_dock_widget, self.__focus_policy)
        else:
            self.proxy.Widget_setFocusPolicy(self.native_dock_widget, "click_focus")

    @property
    def toggle_action(self) -> UserInterface.MenuAction:
        action = QtAction(self.proxy, self.proxy.DockWidget_getToggleAction(self.native_dock_widget))
        action.on_ui_activity = self._register_ui_activity
        return action

    def show(self) -> None:
        self.proxy.Widget_show(self.native_dock_widget)
        self._register_ui_activity()

    def hide(self) -> None:
        self.proxy.Widget_hide(self.native_dock_widget)
        self._register_ui_activity()

    def sizeChanged(self, width: int, height: int) -> None:
        self._handle_size_changed(Geometry.IntSize(width=width, height=height))

    def focusIn(self) -> None:
        self._handle_focus_in()

    def focusOut(self) -> None:
        self._handle_focus_out()


class QtUserInterface(UserInterface.UserInterface):

    def __init__(self, proxy: _QtProxy) -> None:
        self.proxy = proxy
        self.persistence_root = "0"
        self.persistence_handler: typing.Optional[UserInterface.PersistenceHandler] = None
        self.proxy.Core_syncLatencyTimer(time.perf_counter())

    def close(self) -> None:
        self.proxy.Application_close()
        self.proxy = None

    def request_quit(self) -> None:
        self.proxy.Application_close()

    def set_application_info(self, application_name: str, organization_name: str, organization_domain: str) -> None:
        self.proxy.Core_setApplicationInfo(application_name, organization_name, organization_domain)

    def run(self, app: Application.BaseApplication) -> None:
        self.proxy.run(app)

    # data objects

    def create_mime_data(self) -> QtMimeData:
        return QtMimeData(self.proxy)

    def create_item_model_controller(self) -> typing.Any:
        return QtItemModelController(self.proxy)

    def create_button_group(self) -> UserInterface.ButtonGroup:
        return QtButtonGroup(self.proxy)

    # window elements

    def create_document_window(self, title: typing.Optional[str] = None, parent_window: typing.Optional[UserInterface.Window] = None) -> UserInterface.Window:
        return QtWindow(self.proxy, parent_window, title or str())

    def destroy_document_window(self, document_window: UserInterface.Window) -> None:
        document_window.close()

    # user interface elements

    def create_row_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.BoxWidget:
        return UserInterface.BoxWidget(QtBoxWidgetBehavior(self.proxy, "row", properties), alignment)

    def create_column_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.BoxWidget:
        return UserInterface.BoxWidget(QtBoxWidgetBehavior(self.proxy, "column", properties), alignment)

    def create_splitter_widget(self, orientation: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.SplitterWidget:
        return UserInterface.SplitterWidget(QtSplitterWidgetBehavior(self.proxy, properties), orientation)

    def create_tab_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TabWidget:
        return UserInterface.TabWidget(QtTabWidgetBehavior(self.proxy, properties))

    def create_stack_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.StackWidget:
        return UserInterface.StackWidget(QtStackWidgetBehavior(self.proxy, properties))

    def create_group_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.GroupWidget:
        return UserInterface.GroupWidget(QtGroupWidgetBehavior(self.proxy, properties))

    def create_scroll_area_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ScrollAreaWidget:
        return UserInterface.ScrollAreaWidget(QtScrollAreaWidgetBehavior(self.proxy, properties))

    def create_combo_box_widget(self, items: typing.Optional[typing.Sequence[typing.Any]] = None, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ComboBoxWidget:
        return UserInterface.ComboBoxWidget(QtComboBoxWidgetBehavior(self.proxy, properties), items or list(), item_getter or (lambda x: str(x)))

    def create_push_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.PushButtonWidget:
        return UserInterface.PushButtonWidget(QtPushButtonWidgetBehavior(self.proxy, properties), text)

    def create_radio_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.RadioButtonWidget:
        return UserInterface.RadioButtonWidget(QtRadioButtonWidgetBehavior(self.proxy, properties), text)

    def create_check_box_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.CheckBoxWidget:
        return UserInterface.CheckBoxWidget(QtCheckBoxWidgetBehavior(self.proxy, properties), text)

    def create_label_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.LabelWidget:
        return UserInterface.LabelWidget(QtLabelWidgetBehavior(self.proxy, properties), text)

    def create_slider_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.SliderWidget:
        return UserInterface.SliderWidget(QtSliderWidgetBehavior(self.proxy, properties))

    def create_progress_bar_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ProgressBarWidget:
        return UserInterface.ProgressBarWidget(QtCanvasWidgetBehavior(self.proxy, properties))

    def create_line_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.LineEditWidget:
        return UserInterface.LineEditWidget(QtLineEditWidgetBehavior(self.proxy, properties))

    def create_text_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TextEditWidget:
        return UserInterface.TextEditWidget(QtTextEditWidgetBehavior(self.proxy, properties))

    def create_canvas_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None, *, layout_render: typing.Optional[str] = None) -> UserInterface.CanvasWidget:
        return UserInterface.CanvasWidget(QtCanvasWidgetBehavior(self.proxy, properties), layout_render=layout_render)

    def create_tree_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TreeWidget:
        return UserInterface.TreeWidget(QtTreeWidgetBehavior(self.proxy, properties))

    # file i/o

    def load_rgba_data_from_file(self, filename: str) -> typing.Optional[DrawingContext.RGBA32Type]:
        # returns data packed as uint32
        return self.proxy.decode_data(self.proxy.Core_readImageToBinary(notnone(filename)))

    def save_rgba_data_to_file(self, data: DrawingContext.RGBA32Type, filename: str, format: typing.Optional[str]) -> None:
        self.proxy.Core_writeBinaryToImage(data.shape[1], data.shape[0], data, notnone(filename), str(format))

    def get_existing_directory_dialog(self, title: str, directory: str) -> typing.Tuple[str, str]:
        existing_directory, filter, directory = self.proxy.DocumentWindow_getFilePath(None, "directory", notnone(title), notnone(directory), str(), str())
        return existing_directory, directory

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_paths, filter, directory = self.proxy.DocumentWindow_getFilePath(None, "loadmany", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_paths, filter, directory

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(None, "load", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(None, "save", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    # persistence (associated with application)

    def get_data_location(self) -> str:
        return typing.cast(str, self.proxy.Core_getLocation("data"))

    def get_document_location(self) -> str:
        return typing.cast(str, self.proxy.Core_getLocation("documents"))

    def get_temporary_location(self) -> str:
        return typing.cast(str, self.proxy.Core_getLocation("temporary"))

    def get_configuration_location(self) -> str:
        return typing.cast(str, self.proxy.Core_getLocation("configuration"))

    def set_persistence_handler(self, handler: UserInterface.PersistenceHandler) -> None:
        self.persistence_handler = handler

    def get_persistent_string(self, key: str, default_value: typing.Optional[str] = None) -> str:
        key = "/".join([self.persistence_root, key])
        if self.persistence_handler:
            handled, value = self.persistence_handler.get_string(key)
            if handled:
                return value
        value = self.proxy.Settings_getString(key)
        return value if value else (default_value or str())

    def set_persistent_string(self, key: str, value: str) -> None:
        if value is not None:
            key = "/".join([self.persistence_root, key])
            if self.persistence_handler:
                if self.persistence_handler.set_string(key, value):
                    return
            self.proxy.Settings_setString(key, value)
        else:
            self.remove_persistent_key(key)

    def get_persistent_object(self, key: str, default_value: typing.Optional[typing.Any] = None) -> typing.Any:
        key = "/".join([self.persistence_root, key])
        value = self.get_persistent_string(key)
        return pickle.loads(binascii.unhexlify(value.encode("utf-8"))) if value else default_value

    def set_persistent_object(self, key: str, value: typing.Optional[typing.Any]) -> None:
        if value is not None:
            key = "/".join([self.persistence_root, key])
            self.set_persistent_string(key, binascii.hexlify(pickle.dumps(value, 0)).decode("utf-8"))
        else:
            self.remove_persistent_key(key)

    def remove_persistent_key(self, key: str) -> None:
        key = "/".join([self.persistence_root, key])
        if self.persistence_handler:
            if self.persistence_handler.remove_key(key):
                return
        self.proxy.Settings_remove(key)

    # clipboard

    def clipboard_clear(self) -> None:
        self.proxy.Clipboard_clear()

    def clipboard_mime_data(self) -> QtMimeData:
        return QtMimeData(self.proxy, self.proxy.Clipboard_mimeData())

    def clipboard_set_mime_data(self, mime_data: UserInterface.MimeData) -> None:
        assert isinstance(mime_data, QtMimeData)
        self.proxy.Clipboard_setMimeData(mime_data.raw_mime_data)

    def clipboard_set_text(self, text: str) -> None:
        self.proxy.Clipboard_setText(text)

    def clipboard_text(self) -> str:
        return typing.cast(str, self.proxy.Clipboard_text())

    # misc

    def create_rgba_image(self, drawing_context: DrawingContext.DrawingContext, width: int, height: int) -> typing.Optional[DrawingContext.RGBA32Type]:
        if hasattr(self.proxy, "Canvas_draw_binary"):
            return self.proxy.decode_data(self.proxy.DrawingContext_paintRGBA_binary(drawing_context.binary_commands, copy.copy(drawing_context.images), width, height))
        else:
            return self.proxy.decode_data(self.proxy.DrawingContext_paintRGBA(self.proxy.convert_drawing_commands(drawing_context.commands), width, height))

    def get_font_metrics(self, font_str: str, text: str) -> UserInterface.FontMetrics:
        return typing.cast(UserInterface.FontMetrics, self.proxy.decode_font_metrics(self.proxy.Core_getFontMetrics(font_str, text)))

    def truncate_string_to_width(self, font_str: str, text: str, pixel_width: int, mode: UserInterface.TruncateModeType) -> str:
        if self.proxy.has_method("Core_truncateToWidth"):
            return typing.cast(str, self.proxy.Core_truncateToWidth(font_str, text, pixel_width, int(mode)))
        return text

    def get_qt_version(self) -> str:
        return typing.cast(str, self.proxy.Core_getQtVersion())

    def get_tolerance(self, tolerance_type: UserInterface.ToleranceType) -> float:
        return 5

    def create_context_menu(self, document_window: UserInterface.Window) -> UserInterface.Menu:
        context_menu = QtMenu(typing.cast(QtWindow, document_window), str(), str(), self.proxy, self.proxy.Menu_create())
        # the original code would destroy the menu when it was being hidden.
        # this caused crashes (right-click, Export...). the menu seems to be
        # still in use at the time it is hidden on Windows. so, delay its
        # destruction.
        context_menu.on_about_to_hide = lambda: document_window.queue_task(context_menu.destroy)
        return context_menu

    def create_sub_menu(self, document_window: UserInterface.Window, title: typing.Optional[str] = None, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        sub_menu = QtMenu(typing.cast(QtWindow, document_window), title or str(), menu_id or str(), self.proxy, self.proxy.Menu_create())
        return sub_menu

    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        if self.proxy.has_method("DocumentWindow_getColorDialog"):
            return typing.cast(str, self.proxy.DocumentWindow_getColorDialog(None, color, show_alpha))
        return color

    def get_keyboard_modifiers(self, query: bool = False) -> UserInterface.KeyboardModifiers:
        if self.proxy.has_method("Application_getKeyboardModifiers"):
            return QtKeyboardModifiers(self.proxy.Application_getKeyboardModifiers(query))
        return QtKeyboardModifiers(0)
