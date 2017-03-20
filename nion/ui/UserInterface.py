"""
Provides a user interface object that can render to an Qt host.
"""

# standard libraries
import binascii
import collections
import copy
import numbers
import os
import pickle
import sys
import threading
import time
import typing
import weakref

# third party libraries
# none

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.utils import Geometry


def notnone(s: typing.Any) -> str:
    return str(s) if s is not None else str()


class QtKeyboardModifiers:
    def __init__(self, raw_modifiers):
        self.raw_modifiers = raw_modifiers

    def __str__(self):
        return "shift:{} control:{} alt:{} option:{} meta:{}".format(self.shift, self.control, self.alt, self.option, self.meta)

    # shift
    @property
    def shift(self):
        return (self.raw_modifiers & 0x02000000) == 0x02000000

    @property
    def only_shift(self):
        return self.raw_modifiers == 0x02000000

    # control (command key on mac)
    @property
    def control(self):
        return (self.raw_modifiers & 0x04000000) == 0x04000000

    @property
    def only_control(self):
        return self.raw_modifiers == 0x04000000

    # alt (option key on mac)
    @property
    def alt(self):
        return (self.raw_modifiers & 0x08000000) == 0x08000000

    @property
    def only_alt(self):
        return self.raw_modifiers == 0x08000000

    # option (alt key on windows)
    @property
    def option(self):
        return (self.raw_modifiers & 0x08000000) == 0x08000000

    @property
    def only_option(self):
        return self.raw_modifiers == 0x08000000

    # meta (control key on mac)
    @property
    def meta(self):
        return (self.raw_modifiers & 0x10000000) == 0x10000000

    @property
    def only_meta(self):
        return self.raw_modifiers == 0x10000000

    # control key (all platforms)
    @property
    def native_control(self):
        if sys.platform == "win32":
            return self.control
        else:
            return self.meta

    # keypad
    @property
    def keypad(self):
        return (self.raw_modifiers & 0x20000000) == 0x20000000

    @property
    def only_keypad(self):
        return self.raw_modifiers == 0x20000000


class QtKey:
    def __init__(self, text, key, raw_modifiers):
        self.text = text
        self.key = key
        self.modifiers = QtKeyboardModifiers(raw_modifiers)

    @property
    def is_delete(self):
        return len(self.text) == 1 and (ord(self.text[0]) == 127 or ord(self.text[0]) == 8)

    @property
    def is_enter_or_return(self):
        return len(self.text) == 1 and (ord(self.text[0]) == 3 or ord(self.text[0]) == 13)

    @property
    def is_escape(self):
        return self.key == 0x1000000

    @property
    def is_tab(self):
        return self.key == 0x1000001

    @property
    def is_insert(self):
        return self.key == 0x1000006

    @property
    def is_home(self):
        return self.key == 0x1000010

    @property
    def is_end(self):
        return self.key == 0x1000011

    @property
    def is_move_to_start_of_line(self):
        return self.is_home or (self.is_left_arrow and self.modifiers.control) or (self.key == 0x41 and self.modifiers.native_control)

    @property
    def is_move_to_end_of_line(self):
        return self.is_end or (self.is_right_arrow and self.modifiers.control) or (self.key == 0x45 and self.modifiers.native_control)

    @property
    def is_delete_to_end_of_line(self):
        return self.key == 0x4B and self.modifiers.native_control

    @property
    def is_arrow(self):
        return self.key in (0x1000012, 0x1000013, 0x1000014, 0x1000015)

    @property
    def is_left_arrow(self):
        return self.key == 0x1000012

    @property
    def is_up_arrow(self):
        return self.key == 0x1000013

    @property
    def is_right_arrow(self):
        return self.key == 0x1000014

    @property
    def is_down_arrow(self):
        return self.key == 0x1000015

    @property
    def is_page_up(self):
        return self.key == 0x1000016

    @property
    def is_page_down(self):
        return self.key == 0x1000017


class QtMimeData:
    def __init__(self, proxy, mime_data=None):
        self.proxy = proxy
        self.raw_mime_data = mime_data if mime_data else self.proxy.MimeData_create()

    @property
    def formats(self):
        return self.proxy.MimeData_formats(self.raw_mime_data)

    def has_format(self, format):
        return format in self.formats

    @property
    def has_urls(self):
        return "text/uri-list" in self.formats

    @property
    def has_file_paths(self):
        return "text/uri-list" in self.formats

    @property
    def urls(self):
        raw_urls = self.data_as_string("text/uri-list")
        return raw_urls.splitlines() if raw_urls and len(raw_urls) > 0 else []

    @property
    def file_paths(self):
        urls = self.urls
        file_paths = []
        for url in urls:
            file_path = self.proxy.Core_URLToPath(url)
            if file_path and len(file_path) > 0 and os.path.exists(file_path) and os.path.isfile(file_path):
                file_paths.append(file_path)
        return file_paths

    def data_as_string(self, format):
        return self.proxy.MimeData_dataAsString(self.raw_mime_data, format)

    def set_data_as_string(self, format, text):
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
        def __init__(self, data=None):
            self.id = None
            self.data = data if data else {}
            self.weak_parent = None
            self.children = []

        def __str__(self):
            return "Item %i (row %i parent %s)" % (self.id, self.row, self.parent)

        def remove_all_children(self):
            self.children = []

        def append_child(self, item):
            item.parent = self
            self.children.append(item)

        def insert_child(self, before_index, item):
            item.parent = self
            self.children.insert(before_index, item)

        def remove_child(self, item):
            item.parent = None
            self.children.remove(item)

        def child(self, index):
            return self.children[index]

        @property
        def row(self):
            parent = self.weak_parent() if self.weak_parent else None
            if parent:
                return parent.children.index(self)
            return -1

        @property
        def parent(self):
            return self.weak_parent() if self.weak_parent else None

        @parent.setter
        def parent(self, parent):
            self.weak_parent = weakref.ref(parent) if parent else None

    def __init__(self, proxy, keys):
        self.proxy = proxy
        self.py_item_model = self.proxy.ItemModel_create(["index"] + keys)
        self.proxy.ItemModel_connect(self.py_item_model, self)
        self.__next_id = 0
        self.root = self.create_item()
        self.on_item_set_data = None
        self.on_can_drop_mime_data = None
        self.on_item_drop_mime_data = None
        self.on_item_mime_data = None
        self.on_remove_rows = None
        self.supported_drop_actions = 0
        self.mime_types_for_drop = []

    def close(self):
        self.proxy.ItemModel_destroy(self.py_item_model)
        self.proxy = None
        self.py_item_model = None
        self.root = None
        self.on_item_set_data = None
        self.on_can_drop_mime_data = None
        self.on_item_drop_mime_data = None
        self.on_item_mime_data = None
        self.on_remove_rows = None

    # these methods must be invoked from the client

    def create_item(self, data=None):
        item = QtItemModelController.Item(data)
        item.id = self.__next_id
        self.__next_id = self.__next_id + 1
        return item

    def item_from_id(self, item_id, parent=None):
        item = []  # nonlocal in Python 3.1+
        def fn(parent, index, child):
            if child.id == item_id:
                item.append(child)
                return True
        self.traverse(fn)
        return item[0] if item else None

    def __item_id(self, index, parent_id):
        parent = self.item_from_id(parent_id)
        assert parent is not None
        if index >= 0 and index < len(parent.children):
            return parent.children[index].id
        return 0  # invalid id

    def item_value_for_item_id(self, role, index, item_id):
        child = self.item_from_id(item_id)
        if role == "index":
            return index
        if role in child.data:
            return child.data[role]
        return None

    def item_value(self, role, index, parent_id):
        return self.item_value_for_item_id(role, index, self.__item_id(index, parent_id))

    # these methods are invoked from Qt

    def itemCount(self, parent_id):
        parent = self.item_from_id(parent_id)
        assert parent is not None
        return len(parent.children)

    # itemId returns the id of the item within the parent
    def itemId(self, index, parent_id):
        return self.__item_id(index, parent_id)

    def itemParent(self, index, item_id):
        if item_id == 0:
            return [-1, 0]
        child = self.item_from_id(item_id)
        parent = child.parent
        if parent == self.root:
            return [-1, 0]
        return [parent.row, parent.id]

    def itemValue(self, role, index, item_id):
        return self.item_value_for_item_id(role, index, item_id)

    def itemSetData(self, index, parent_row, parent_id, data):
        if self.on_item_set_data:
            return self.on_item_set_data(data, index, parent_row, parent_id)
        return False

    def canDropMimeData(self, raw_mime_data, action, row, parent_row, parent_id):
        if self.on_can_drop_mime_data:
            return self.on_can_drop_mime_data(QtMimeData(self.proxy, raw_mime_data), action, row, parent_row, parent_id)
        return False

    def itemDropMimeData(self, raw_mime_data, action, row, parent_row, parent_id):
        if self.on_item_drop_mime_data:
            return self.on_item_drop_mime_data(QtMimeData(self.proxy, raw_mime_data), action, row, parent_row, parent_id)
        return False

    def itemMimeData(self, row, parent_row, parent_id):
        if self.on_item_mime_data:
            mime_data = self.on_item_mime_data(row, parent_row, parent_id)
            return mime_data.raw_mime_data if mime_data else None
        return None

    def removeRows(self, row, count, parent_row, parent_id):
        if self.on_remove_rows:
            return self.on_remove_rows(row, count, parent_row, parent_id)
        return False

    def supportedDropActions(self):
        return self.supported_drop_actions

    def mimeTypesForDrop(self):
        return self.mime_types_for_drop


#abc (None, 0)
#    def (abc, 0)
#    ghi (abc, 1)
#        jkl (ghi, 0)
#        mno (ghi, 1)
#    pqr (abc, 2)
#        stu (pqr, 0)
#    vwx (abc, 3)

    def traverse_depth_first(self, fn, parent):
        real_parent = parent if parent else self.root
        for index, child in enumerate(real_parent.children):
            if self.traverse_depth_first(fn, child):
                return True
            if fn(parent, index, child):
                return True
        return False

    def traverse(self, fn):
        if not fn(None, 0, self.root):
            self.traverse_depth_first(fn, self.root)

    def begin_insert(self, first_row, last_row, parent_row, parent_id):
        self.proxy.ItemModel_beginInsertRows(self.py_item_model, first_row, last_row, parent_row, parent_id)

    def end_insert(self):
        self.proxy.ItemModel_endInsertRow(self.py_item_model)

    def begin_remove(self, first_row, last_row, parent_row, parent_id):
        self.proxy.ItemModel_beginRemoveRows(self.py_item_model, first_row, last_row, parent_row, parent_id)

    def end_remove(self):
        self.proxy.ItemModel_endRemoveRow(self.py_item_model)

    def data_changed(self, row, parent_row, parent_id):
        self.proxy.ItemModel_dataChanged(self.py_item_model, row, parent_row, parent_id)


class QtDrag:
    def __init__(self, proxy, widget, mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn):
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

    def close(self):
        pass

    def execute(self):
        return self.proxy.Drag_exec(self.__raw_drag)

    def dragFinished(self, action):
        if self.on_drag_finished:
            self.on_drag_finished(action)


class Widget:

    def __init__(self, widget_behavior):
        self.__behavior = widget_behavior
        self.__root_container = None  # the document window
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.widget_id = None

        def handle_context_menu_event(x, y, gx, gy):
            if callable(self.on_context_menu_event):
                self.on_context_menu_event(x, y, gx, gy)

        def handle_focus_changed(focused):
            if callable(self.on_focus_changed):
                self.on_focus_changed(focused)

        self._behavior.on_context_menu_event = handle_context_menu_event
        self._behavior.on_focus_changed = handle_focus_changed
        self.widget_id = None

    def close(self):
        self.__behavior.close()
        self.__behavior = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.__root_container = None

    @property
    def _behavior(self):
        return self.__behavior

    @property
    def root_container(self):
        return self.__root_container

    def _set_root_container(self, root_container):
        self.__root_container = root_container

    @property
    def _contained_widgets(self):
        return list()

    def find_widget_by_id(self, widget_id: str):
        if self.widget_id == widget_id:
            return self
        for contained_widget in self._contained_widgets:
            found_widget = contained_widget.find_widget_by_id(widget_id)
            if found_widget:
                return found_widget
        return None

    # not thread safe
    def periodic(self):
        pass

    # thread safe
    # tasks are run periodically. if another task causes a widget to close,
    # the outstanding task may try to use a closed widget. any methods called
    # in a task need to verify that the widget is not yet closed. this can be
    # mitigated in several ways: 1) clear the task if possible; 2) do not queue
    # the task if widget is already closed; 3) check during task to make sure
    # widget was not already closed.
    def add_task(self, key, task):
        root_container = self.root_container
        if root_container:
            root_container.add_task(key + str(id(self)), task)

    # thread safe
    def clear_task(self, key):
        root_container = self.root_container
        if root_container:
            root_container.clear_task(key + str(id(self)))

    # thread safe
    def queue_task(self, task):
        root_container = self.root_container
        if root_container:
            root_container.queue_task(task)

    @property
    def focused(self) -> bool:
        return self._behavior.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self._behavior.focused = focused

    @property
    def visible(self) -> bool:
        return self._behavior.visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        self._behavior.visible = visible

    @property
    def enabled(self) -> bool:
        return self._behavior.enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._behavior.enabled = enabled

    @property
    def size(self) -> Geometry.IntSize:
        return self._behavior.size

    @size.setter
    def size(self, size: Geometry.IntSize) -> None:
        self._behavior.size = size

    @property
    def tool_tip(self) -> str:
        return self._behavior.tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip: str) -> None:
        self._behavior.tool_tip = tool_tip

    def drag(self, mime_data, thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None) -> None:
        self._behavior.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def map_to_global(self, p) -> Geometry.IntPoint:
        return self._behavior.map_to_global(p)

    def _dispatch_any(self, method: str, *args, **kwargs) -> bool:
        if hasattr(self, method):
            return getattr(self, method)(*args, **kwargs)
        return False

    def _will_dispatch(self, method) -> bool:
        return hasattr(self, method)


class QtWidgetBehavior:

    def __init__(self, proxy, widget_type, properties):
        self.proxy = proxy
        self.properties = properties if properties else {}
        self.widget = self.proxy.Widget_loadIntrinsicWidget(widget_type) if widget_type else None
        self.update_properties()
        self.__visible = True
        self.__enabled = True
        self.__tool_tip = None
        self.on_context_menu_event = None
        self.on_focus_changed = None

    # subclasses should override to clear their variables.
    # subclasses should NOT call Qt code to delete anything here... that is done by the Qt code
    def close(self):
        self.proxy.Widget_removeWidget(self.widget)
        self.widget = None
        self.proxy = None

    def update_properties(self):
        for key in self.properties.keys():
            self.proxy.Widget_setWidgetProperty(self.widget, key, self.proxy.encode_variant(self.properties[key]))

    @property
    def focused(self):
        return self.proxy.Widget_hasFocus(self.widget)

    @focused.setter
    def focused(self, focused):
        if focused != self.focused:
            if focused:
                self.proxy.Widget_setFocus(self.widget, 7)
            else:
                self.proxy.Widget_clearFocus(self.widget)

    @property
    def visible(self):
        return self.__visible

    @visible.setter
    def visible(self, visible):
        if visible != self.__visible:
            self.proxy.Widget_setVisible(self.widget, visible)
            self.__visible = visible

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled):
        if enabled != self.__enabled:
            self.proxy.Widget_setEnabled(self.widget, enabled)
            self.__enabled = enabled

    @property
    def size(self):
        w, h = self.proxy.Widget_getWidgetSize(self.widget)
        return Geometry.IntSize(width=w, height=h)

    @size.setter
    def size(self, size):
        self.proxy.Widget_setWidgetSize(self.widget, int(size[1]), int(size[0]))

    @property
    def tool_tip(self):
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip):
        if tool_tip != self.__tool_tip:
            self.proxy.Widget_setToolTip(self.widget, notnone(tool_tip) if tool_tip else str())
            self.__tool_tip = tool_tip

    def drag(self, mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn):
        def drag_finished(action):
            if drag_finished_fn:
                drag_finished_fn(action)
        drag = QtDrag(self.proxy, self.widget, mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished)
        drag.execute()

    def contextMenuEvent(self, x, y, gx, gy):
        if self.on_context_menu_event:
            self.on_context_menu_event(x, y, gx, gy)

    def focusIn(self):
        if self.on_focus_changed:
            self.on_focus_changed(True)

    def focusOut(self):
        if self.on_focus_changed:
            self.on_focus_changed(False)

    def map_to_global(self, p):
        gx, gy = self.proxy.Widget_mapToGlobal(self.widget, p.x, p.y)
        return Geometry.IntPoint(x=gx, y=gy)


class QtNullBehavior:

    def __init__(self):
        self.focused = False
        self.enabled = True
        self.visible = True

    def close(self):
        pass


class QtBoxStretch(Widget):

    def __init__(self):
        super().__init__(QtNullBehavior())


class QtBoxSpacing(Widget):

    def __init__(self, spacing: int):
        super().__init__(QtNullBehavior())
        self.spacing = spacing


def extract_widget(widget):
    if hasattr(widget, "_behavior"):
        return widget._behavior.widget
    elif hasattr(widget, "content_widget"):
        return extract_widget(widget.content_widget)
    return None


class QtBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, widget_type, properties):
        super().__init__(proxy, widget_type, properties)

    def insert(self, child, index, fill, alignment):
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert self.widget is not None
        assert child_widget is not None
        index = index if index is not None else self.proxy.Widget_widgetCount(self.widget)
        self.proxy.Widget_insertWidget(self.widget, child_widget, index, fill, alignment)

    def add_stretch(self) -> Widget:
        self.proxy.Widget_addStretch(self.widget)
        return QtBoxStretch()

    def add_spacing(self, spacing: int) -> Widget:
        self.proxy.Widget_addSpacing(self.widget, spacing)
        return QtBoxSpacing(spacing)


class BoxWidget(Widget):

    def __init__(self, widget_behavior, alignment):
        super().__init__(widget_behavior)
        self.alignment = alignment
        self.children = []

    def close(self):
        for child in self.children:
            child.close()
        self.children = None
        super().close()

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self):
        return copy.copy(self.children)

    def periodic(self):
        super().periodic()
        for child in self.children:
            child.periodic()

    @property
    def child_count(self):
        return len(self.children)

    def index(self, child):
        assert child in self.children
        return self.children.index(child)

    def insert(self, child, before, fill=False, alignment=None):
        if isinstance(before, numbers.Integral):
            index = before
        else:
            index = self.index(before) if before is not None else self.child_count
        if alignment is None:
            alignment = self.alignment
        self.children.insert(index, child)
        child._set_root_container(self.root_container)
        self._behavior.insert(child, index, fill, alignment)

    def add(self, child, fill=False, alignment=None):
        self.insert(child, None, fill, alignment)

    def remove(self, child: typing.Union[Widget, int]) -> None:
        if isinstance(child, numbers.Integral):
            child = self.children[child]
        child._set_root_container(None)
        self.children.remove(child)
        # closing the child should remove it from the layout
        child.close()

    def remove_all(self) -> None:
        while self.child_count > 0:
            self.remove(0)

    def add_stretch(self) -> None:
        child = self._behavior.add_stretch()
        self.children.append(child)

    def add_spacing(self, spacing: int) -> None:
        child = self._behavior.add_spacing(spacing)
        self.children.append(child)


class QtSplitterWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "splitter", properties)
        self.children = []
        self.__orientation = "vertical"

    @property
    def orientation(self):
        return self.__orientation

    @orientation.setter
    def orientation(self, value):
        self.__orientation = value
        self.proxy.Splitter_setOrientation(self.widget, self.__orientation)

    def add(self, child: Widget) -> None:
        self.proxy.Widget_addWidget(self.widget, extract_widget(child))

    def restore_state(self, tag):
        self.proxy.Splitter_restoreState(self.widget, tag)

    def save_state(self, tag):
        self.proxy.Splitter_saveState(self.widget, tag)


class SplitterWidget(Widget):

    def __init__(self, widget_behavior, orientation):
        super().__init__(widget_behavior)
        self.children = []
        self.orientation = orientation

    def close(self):
        for child in self.children:
            child.close()
        self.children = None
        super().close()

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self):
        return copy.copy(self.children)

    def periodic(self):
        super().periodic()
        for child in self.children:
            child.periodic()

    @property
    def orientation(self):
        return self._behavior.orientation

    @orientation.setter
    def orientation(self, value):
        self._behavior.orientation = value

    def add(self, child: Widget) -> None:
        self._behavior.add(child)
        self.children.append(child)
        child._set_root_container(self.root_container)

    def restore_state(self, tag: str) -> None:
        self._behavior.restore_state(tag)

    def save_state(self, tag: str) -> None:
        self._behavior.save_state(tag)


class QtTabWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        properties = copy.deepcopy(properties) if properties is not None else dict()
        properties["stylesheet"] = "background-color: '#FFF'"
        super().__init__(proxy, "tab", properties)
        self.on_current_index_changed = None
        self.proxy.TabWidget_connect(self.widget, self)

    def close(self):
        self.on_current_index_changed = None
        super().close()

    def add(self, child: Widget, label: str) -> None:
        self.proxy.TabWidget_addTab(self.widget, extract_widget(child), notnone(label))

    def restore_state(self, tag):
        pass

    def save_state(self, tag):
        pass

    def currentTabChanged(self, index):
        if callable(self.on_current_index_changed):
            self.on_current_index_changed(index)


class TabWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.children = []
        self.on_current_index_changed = None

        def handle_current_index_changed(index):
            if callable(self.on_current_index_changed):
                self.on_current_index_changed(index)

        self._behavior.on_current_index_changed = handle_current_index_changed

    def close(self):
        for child in self.children:
            child.close()
        self.children = None
        self.on_current_index_changed = None
        super().close()

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self):
        return copy.copy(self.children)

    def periodic(self):
        super().periodic()
        for child in self.children:
            child.periodic()

    def add(self, child: Widget, label: str) -> None:
        self._behavior.add(child, label)
        self.children.append(child)
        child._set_root_container(self.root_container)

    def restore_state(self, tag: str) -> None:
        self._behavior.restore_state(tag)

    def save_state(self, tag: str) -> None:
        self._behavior.save_state(tag)


class QtStackWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "stack", properties)
        self.__current_index = -1

    def add(self, child: Widget) -> None:
        self.proxy.StackWidget_addWidget(self.widget, extract_widget(child))

    def remove(self, child: Widget) -> None:
        self.proxy.StackWidget_removeWidget(self.widget, extract_widget(child))

    @property
    def current_index(self):
        return self.__current_index

    @current_index.setter
    def current_index(self, index):
        self.__current_index = index
        self.proxy.StackWidget_setCurrentIndex(self.widget, index)


class StackWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.children = []

    def close(self):
        for child in self.children:
            child.close()
        self.children = None
        super().close()

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self):
        return copy.copy(self.children)

    def periodic(self):
        super().periodic()
        for child in self.children:
            child.periodic()

    def add(self, child: Widget) -> None:
        self._behavior.add(child)
        self.children.append(child)
        child._set_root_container(self.root_container)

    def remove(self, child: Widget) -> None:
        self._behavior.remove(child)
        child._set_root_container(None)
        self.children.remove(child)
        child.close()

    def remove_all(self):
        while len(self.children) > 0:
            self.remove(self.children[-1])

    @property
    def current_index(self):
        return self._behavior.current_index

    @current_index.setter
    def current_index(self, index):
        self._behavior.current_index = index


class QtScrollAreaWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "scrollarea", properties)
        self.on_size_changed = None
        self.on_viewport_changed = None
        self.proxy.ScrollArea_connect(self.widget, self)

    def close(self):
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    def set_content(self, content: Widget) -> None:
        self.proxy.ScrollArea_setWidget(self.widget, extract_widget(content))

    def sizeChanged(self, width, height):
        if callable(self.on_size_changed):
            self.on_size_changed(width, height)

    def viewportChanged(self, left, top, width, height):
        if callable(self.on_viewport_changed):
            viewport = (top, left), (height, width)
            self.on_viewport_changed(viewport)

    def scroll_to(self, x, y):
        self.proxy.ScrollArea_setHorizontal(self.widget, float(x))
        self.proxy.ScrollArea_setVertical(self.widget, float(y))

    def set_scrollbar_policies(self, horizontal_policy, vertical_policy):
        self.proxy.ScrollArea_setScrollbarPolicies(self.widget, horizontal_policy, vertical_policy)

    def info(self):
        self.proxy.ScrollArea_info(self.widget)


class ScrollAreaWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.__content = None
        self.on_size_changed = None
        self.on_viewport_changed = None
        self.viewport = ((0, 0), (0, 0))
        self.width = 0
        self.height = 0

        def handle_size_changed(width, height):
            self.width = width
            self.height = height
            if callable(self.on_size_changed):
                self.on_size_changed(width, height)

        self._behavior.on_size_changed = handle_size_changed

        def handle_viewport_changed(viewport):
            self.viewport = viewport
            if callable(self.on_viewport_changed):
                self.on_viewport_changed(viewport)

        self._behavior.on_viewport_changed = handle_viewport_changed

    def close(self):
        self.__content.close()
        self.__content = None
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        self.__content._set_root_container(root_container)

    @property
    def _contained_widgets(self):
        return [self.__content] if self.__content else list()

    def periodic(self):
        super().periodic()
        self.__content.periodic()

    @property
    def content(self) -> Widget:
        return self.__content

    @content.setter
    def content(self, content: Widget) -> None:
        self._behavior.set_content(content)
        self.__content = content
        content._set_root_container(self.root_container)

    def restore_state(self, tag):
        pass

    def save_state(self, tag):
        pass

    def scroll_to(self, x, y):
        self._behavior.scroll_to(x, y)

    def set_scrollbar_policies(self, horizontal_policy, vertical_policy):
        self._behavior.set_scrollbar_policies(horizontal_policy, vertical_policy)

    def info(self):
        self._behavior.info()


class QtComboBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "combobox", properties)
        self.on_current_text_changed = None
        self.proxy.ComboBox_connect(self.widget, self)

    def close(self):
        self.on_current_text_changed = None
        super().close()

    @property
    def current_text(self):
        return self.proxy.ComboBox_getCurrentText(self.widget)

    @current_text.setter
    def current_text(self, value):
        self.proxy.ComboBox_setCurrentText(self.widget, notnone(value))

    def set_item_strings(self, item_strings):
        self.proxy.ComboBox_removeAllItems(self.widget)
        for item_string in item_strings:
            self.proxy.ComboBox_addItem(self.widget, item_string)

    # this message comes from Qt implementation
    def currentTextChanged(self, text):
        if callable(self.on_current_text_changed):
            self.on_current_text_changed(text)


class ComboBoxWidget(Widget):

    def __init__(self, widget_behavior, items, item_getter):
        super().__init__(widget_behavior)
        self.on_items_changed = None
        self.on_current_text_changed = None
        self.on_current_item_changed = None
        self.item_getter = item_getter
        self.items = items if items else []
        self.__current_item_binding = None
        self.__items_binding = None

        def handle_current_text_changed(text):
            if callable(self.on_current_text_changed):
                self.on_current_text_changed(text)
            if callable(self.on_current_item_changed):
                self.on_current_item_changed(self.current_item)

        self._behavior.on_current_text_changed = handle_current_text_changed

    def close(self):
        if self.__current_item_binding:
            self.__current_item_binding.close()
            self.__current_item_binding = None
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.clear_task("update_current_index")
        self.item_getter = None
        self.__items = None
        self.on_items_changed = None
        self.on_current_text_changed = None
        self.on_current_item_changed = None
        super().close()

    @property
    def current_text(self) -> str:
        return self._behavior.current_text

    @current_text.setter
    def current_text(self, value: str) -> None:
        self._behavior.current_text = value

    @property
    def current_item(self):
        current_text = self.current_text
        for item in self.items:
            if current_text == notnone(self.item_getter(item) if self.item_getter else item):
                return item
        return None

    @current_item.setter
    def current_item(self, value):
        item_string = notnone(self.item_getter(value) if self.item_getter and value is not None else value)
        self.current_text = item_string

    @property
    def current_index(self) -> int:
        return self.items.index(self.current_text) if self.current_text in self.items else None

    @current_index.setter
    def current_index(self, value: int) -> None:
        self.current_item = self.items[value] if value is not None else None

    @property
    def items(self):
        return self.__items

    @items.setter
    def items(self, items):
        item_strings = list()
        self.__items = list()
        for item in items:
            item_string = notnone(self.item_getter(item) if self.item_getter else item)
            item_strings.append(item_string)
            self.__items.append(item)
        self._behavior.set_item_strings(item_strings)
        if callable(self.on_items_changed):
            self.on_items_changed(self.__items)

    def bind_items(self, binding):
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.items = binding.get_target_value()
        self.__items_binding = binding
        def update_items(items):
            self.add_task("update_items", lambda: setattr(self, "items", items))
        self.__items_binding.target_setter = update_items
        self.on_items_changed = lambda items: self.__items_binding.update_source(items)

    def bind_current_index(self, binding):
        if self.__current_item_binding:
            self.__current_item_binding.close()
            self.__current_item_binding = None
        current_index = binding.get_target_value()
        if current_index is not None and 0 <= current_index < len(self.__items):
            self.current_item = self.__items[current_index]
        self.__current_item_binding = binding
        def update_current_index(current_index):
            if current_index is not None and 0 <= current_index < len(self.__items):
                item = self.__items[current_index]
                self.add_task("update_current_index", lambda: setattr(self, "current_item", item))
        self.__current_item_binding.target_setter = update_current_index
        self.on_current_item_changed = lambda item: self.__current_item_binding.update_source(self.__items.index(item))


class QtPushButtonWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "pushbutton", properties)
        self.on_clicked = None
        self.__text = None
        self.__icon = None
        self.proxy.PushButton_connect(self.widget, self)

    def close(self):
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: str) -> None:
        self.__text = self.proxy.encode_text(text)
        self.proxy.PushButton_setText(self.widget, self.__text)

    @property
    def icon(self):
        return self.__icon

    @icon.setter
    def icon(self, rgba_image) -> None:
        # rgba_image should be a uint32 numpy array with the pixel order bgra
        self.__icon = rgba_image
        width = rgba_image.shape[1] if rgba_image is not None else 0
        height = rgba_image.shape[0] if rgba_image is not None else 0
        rgba_data = self.proxy.encode_data(rgba_image)
        self.proxy.PushButton_setIcon(self.widget, width, height, rgba_data)

    def clicked(self):
        if callable(self.on_clicked):
            self.on_clicked()


class PushButtonWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.on_clicked = None
        self.text = text
        self.icon = None

        def handle_clicked():
            if callable(self.on_clicked):
                self.on_clicked()

        self._behavior.on_clicked = handle_clicked

    def close(self):
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self._behavior.text = text

    @property
    def icon(self):
        return self._behavior.icon

    @icon.setter
    def icon(self, rgba_image) -> None:
        self._behavior.icon = rgba_image


class QtRadioButtonWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "radiobutton", properties)
        self.on_clicked = None
        self.__text = None
        self.__icon = None
        self.proxy.RadioButton_connect(self.widget, self)

    def close(self):
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: str) -> None:
        self.__text = self.proxy.encode_text(text)
        self.proxy.RadioButton_setText(self.widget, self.__text)

    @property
    def icon(self):
        return self.__icon

    @icon.setter
    def icon(self, rgba_image) -> None:
        # rgba_image should be a uint32 numpy array with the pixel order bgra
        self.__icon = rgba_image
        self.__width = rgba_image.shape[1] if rgba_image is not None else 0
        self.__height = rgba_image.shape[0] if rgba_image is not None else 0
        rgba_data = self.proxy.encode_data(rgba_image)
        self.proxy.RadioButton_setIcon(self.widget, self.__width, self.__height, rgba_data)

    @property
    def checked(self):
        return self.proxy.RadioButton_getChecked(self.widget)

    @checked.setter
    def checked(self, value):
        self.proxy.RadioButton_setChecked(self.widget, value)

    def clicked(self):
        if callable(self.on_clicked):
            self.on_clicked()


class RadioButtonWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.on_clicked = None
        self.text = text
        self.icon = None

        def handle_clicked():
            if callable(self.on_clicked):
                self.on_clicked()

        self._behavior.on_clicked = handle_clicked

    def close(self):
        self.on_clicked = None
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self._behavior.text = text

    @property
    def icon(self):
        return self._behavior.icon

    @icon.setter
    def icon(self, rgba_image) -> None:
        self._behavior.icon = rgba_image

    @property
    def checked(self):
        return self._behavior.checked

    @checked.setter
    def checked(self, value):
        self._behavior.checked = value


class QtButtonGroup:

    def __init__(self, proxy):
        self.proxy = proxy
        self.py_button_group = self.proxy.ButtonGroup_create()
        self.proxy.ButtonGroup_connect(self.py_button_group, self)
        self.on_button_clicked = None

    def close(self):
        self.proxy.ButtonGroup_destroy(self.py_button_group)
        self.proxy = None
        self.on_button_clicked = None

    def add_button(self, radio_button, button_id):
        self.proxy.ButtonGroup_addButton(self.py_button_group, radio_button.widget, button_id)

    def remove_button(self, radio_button):
        self.proxy.ButtonGroup_removeButton(self.py_button_group, radio_button.widget)

    def clicked(self, button_id):
        if self.on_button_clicked:
            self.on_button_clicked(button_id)


class QtCheckBoxWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "checkbox", properties)
        self.on_check_state_changed = None
        self.__text = None
        self.proxy.CheckBox_connect(self.widget, self)

    def close(self):
        self.on_check_state_changed = None
        super().close()

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, value):
        self.__text = value
        self.proxy.CheckBox_setText(self.widget, notnone(value))

    @property
    def tristate(self):
        return self.proxy.CheckBox_getIsTristate(self.widget)

    @tristate.setter
    def tristate(self, value):
        self.proxy.CheckBox_setIsTristate(self.widget, bool(value))

    @property
    def check_state(self):
        return self.proxy.CheckBox_getCheckState(self.widget)

    @check_state.setter
    def check_state(self, value):
        self.proxy.CheckBox_setCheckState(self.widget, str(value))

    def stateChanged(self, check_state):
        if callable(self.on_check_state_changed):
            self.on_check_state_changed(check_state)


class CheckBoxWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.on_checked_changed = None
        self.on_check_state_changed = None
        self.text = text
        self.__binding = None

        def handle_check_state_changed(check_state):
            if callable(self.on_checked_changed):
                self.on_checked_changed(check_state == "checked")
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        self._behavior.on_check_state_changed = handle_check_state_changed

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_check_state")
        self.on_checked_changed = None
        self.on_check_state_changed = None
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self._behavior.text = text

    @property
    def checked(self):
        return self.check_state == "checked"

    @checked.setter
    def checked(self, value):
        self.check_state = "checked" if value else "unchecked"

    @property
    def tristate(self):
        return self._behavior.tristate

    @tristate.setter
    def tristate(self, value):
        self._behavior.tristate = value

    @property
    def check_state(self):
        return self._behavior.checkstate

    @check_state.setter
    def check_state(self, value):
        self._behavior.checkstate = value

    # bind to state. takes ownership of binding.
    def bind_checked(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.checked = binding.get_target_value()
        self.__binding = binding
        def update_checked(checked):
            self.add_task("update_checked", lambda: setattr(self, "checked", checked))
        self.__binding.target_setter = update_checked
        self.on_checked_changed = lambda checked: self.__binding.update_source(checked)

    # bind to state. takes ownership of binding.
    def bind_check_state(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.check_state = binding.get_target_value()
        self.__binding = binding
        def update_check_state(check_state):
            self.add_task("update_check_state", lambda: setattr(self, "check_state", check_state))
        self.__binding.target_setter = update_check_state
        self.on_check_state_changed = lambda check_state: self.__binding.update_source(check_state)


class QtLabelWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "label", properties)
        self.__text = None
        self.__word_wrap = False

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, text):
        self.__text = text if text else ""
        self.proxy.Label_setText(self.widget, notnone(self.__text))

    @property
    def word_wrap(self):
        return self.__word_wrap

    @word_wrap.setter
    def word_wrap(self, value):
        self.__word_wrap = value
        self.proxy.Label_setWordWrap(self.widget, value)


class LabelWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.text = text
        self.__binding = None

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_text")
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self._behavior.text = text

    @property
    def word_wrap(self):
        return self._behavior.word_wrap

    @word_wrap.setter
    def word_wrap(self, value):
        self._behavior.word_wrap = value

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.text = binding.get_target_value()
        self.__binding = binding
        def update_text(text):
            self.add_task("update_text", lambda: setattr(self, "text", text))
        self.__binding.target_setter = update_text

    def unbind_text(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None


class QtSliderWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "slider", properties)
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        self.__pressed = False
        self.__min = 0
        self.__max = 0
        self.proxy.Slider_connect(self.widget, self)

    def close(self):
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        super().close()

    @property
    def value(self):
        return self.proxy.Slider_getValue(self.widget)

    @value.setter
    def value(self, value):
        self.proxy.Slider_setValue(self.widget, value)

    @property
    def minimum(self):
        return self.__min

    @minimum.setter
    def minimum(self, value):
        self.__min = value
        self.proxy.Slider_setMinimum(self.widget, value)

    @property
    def maximum(self):
        return self.__max

    @maximum.setter
    def maximum(self, value):
        self.__max = value
        self.proxy.Slider_setMaximum(self.widget, value)

    @property
    def pressed(self):
        return self.__pressed

    def valueChanged(self, value):
        if callable(self.on_value_changed):
            self.on_value_changed(value)

    def sliderPressed(self):
        self.__pressed = True
        if callable(self.on_slider_pressed):
            self.on_slider_pressed()

    def sliderReleased(self):
        self.__pressed = False
        if callable(self.on_slider_released):
            self.on_slider_released()

    def sliderMoved(self, value):
        if callable(self.on_slider_moved):
            self.on_slider_moved(value)


class SliderWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        self.minimum = 0
        self.maximum = 0
        self.__binding = None

        def handle_value_changed(value):
            if callable(self.on_value_changed):
                self.on_value_changed(value)

        self._behavior.on_value_changed = handle_value_changed

        def handle_slider_pressed():
            if callable(self.on_slider_pressed):
                self.on_slider_pressed()

        self._behavior.on_slider_pressed = handle_slider_pressed

        def handle_slider_released():
            if callable(self.on_slider_released):
                self.on_slider_released()

        self._behavior.on_slider_released = handle_slider_released

        def handle_slider_moved(value):
            if callable(self.on_slider_moved):
                self.on_slider_moved(value)

        self._behavior.on_slider_moved = handle_slider_moved

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_value")
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        super().close()

    @property
    def value(self):
        return self._behavior.value

    @value.setter
    def value(self, value):
        self._behavior.value = value

    @property
    def minimum(self):
        return self._behavior.minimum

    @minimum.setter
    def minimum(self, minimum):
        self._behavior.minimum = minimum

    @property
    def maximum(self):
        return self._behavior.maximum

    @maximum.setter
    def maximum(self, maximum):
        self._behavior.maximum = maximum

    @property
    def pressed(self):
        return self._behavior.pressed

    # bind to value. takes ownership of binding.
    def bind_value(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.value = binding.get_target_value()
        self.__binding = binding
        def update_value(value):
            self.add_task("update_value", lambda: setattr(self, "value", value))
        self.__binding.target_setter = update_value
        self.on_value_changed = lambda value: self.__binding.update_source(value)


class QtLineEditWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "lineedit", properties)
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_text_edited = None
        self.proxy.LineEdit_connect(self.widget, self)
        self.__binding = None
        self.__clear_button_enabled = False

    def close(self):
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def text(self) -> str:
        return self.proxy.LineEdit_getText(self.widget)

    @text.setter
    def text(self, text: str) -> None:
        self.proxy.LineEdit_setText(self.widget, notnone(text))

    @property
    def placeholder_text(self) -> str:
        return self.proxy.LineEdit_getPlaceholderText(self.widget)

    @placeholder_text.setter
    def placeholder_text(self, text: str) -> None:
        self.proxy.LineEdit_setPlaceholderText(self.widget, notnone(text))

    @property
    def selected_text(self):
        return self.proxy.LineEdit_getSelectedText(self.widget)

    @property
    def clear_button_enabled(self) -> bool:
        return self.__clear_button_enabled

    @clear_button_enabled.setter
    def clear_button_enabled(self, enabled: bool) -> None:
        self.__clear_button_enabled = enabled
        self.proxy.LineEdit_setClearButtonEnabled(self.widget, enabled)

    @property
    def editable(self) -> bool:
        return self.proxy.LineEdit_getEditable(self.widget)

    @editable.setter
    def editable(self, editable: bool) -> None:
        self.proxy.LineEdit_setEditable(self.widget, editable)

    def select_all(self):
        self.proxy.LineEdit_selectAll(self.widget)

    def editingFinished(self, text):
        if self.on_editing_finished:
            self.on_editing_finished(text)

    def escapePressed(self):
        if callable(self.on_escape_pressed):
            return self.on_escape_pressed()
        return False

    def returnPressed(self):
        if callable(self.on_return_pressed):
            return self.on_return_pressed()
        return False

    def keyPressed(self, text, key, raw_modifiers):
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def textEdited(self, text):
        if callable(self.on_text_edited):
            self.on_text_edited(text)


class LineEditWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_text_edited = None
        self.__binding = None
        self.__last_text = None

        def handle_editing_finished(text):
            if callable(self.on_editing_finished):
                self.on_editing_finished(text)
            self.__last_text = text

        self._behavior.on_editing_finished = handle_editing_finished

        def handle_escape_pressed():
            if callable(self.on_escape_pressed):
                self.on_escape_pressed()
                return True
            return False

        self._behavior.on_escape_pressed = handle_escape_pressed

        def handle_return_pressed():
            if callable(self.on_return_pressed):
                self.on_return_pressed()
                return True
            return False

        self._behavior.on_return_pressed = handle_return_pressed

        def handle_key_pressed(key):
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_text_edited(text):
            if callable(self.on_text_edited):
                self.on_text_edited(text)

        self._behavior.on_text_edited = handle_text_edited

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_text")
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self.__last_text = notnone(text)
        self._behavior.text = text

    @property
    def placeholder_text(self) -> str:
        return self._behavior.placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, text: str) -> None:
        self._behavior.placeholder_text = text

    @property
    def selected_text(self):
        return self._behavior.selected_text

    @property
    def clear_button_enabled(self) -> bool:
        return self._behavior.clear_button_enabled

    @clear_button_enabled.setter
    def clear_button_enabled(self, enabled: bool) -> None:
        self._behavior.clear_button_enabled = enabled

    @property
    def editable(self) -> bool:
        return self._behavior.editable

    @editable.setter
    def editable(self, editable: bool) -> None:
        self._behavior.editable = editable

    def select_all(self):
        self._behavior.select_all()

    def handle_select_all(self):
        self.select_all()
        return True

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.text = binding.get_target_value()
        def update_field(text):
            if self.text != text and (not self.focused or self.selected_text == self.text):
                self.text = text
                if self.focused:
                    self.select_all()
        self.__binding = binding
        def update_text(text):
            self.add_task("update_text", lambda: update_field(text))
        self.__binding.target_setter = update_text
        self.on_editing_finished = lambda text: self.__binding.update_source(text)
        def return_pressed():
            text = self.text
            self.select_all()
            self.__binding.update_source(text)
        def escape_pressed():
            text = self.__last_text
            self.select_all()
            self.__binding.update_source(text)
        self.on_return_pressed = return_pressed
        self.on_escape_pressed = escape_pressed

    def unbind_text(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_editing_finished = None


Selection = collections.namedtuple("Selection", ["start", "end"])

CursorPosition = collections.namedtuple("CursorPosition", ["position", "block_number", "column_number"])


class QtTextEditWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "textedit", properties)
        self.__word_wrap_mode = "optimal"
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        self.proxy.TextEdit_connect(self.widget, self)

    def close(self):
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        super().close()

    @property
    def text(self):
        return self.proxy.TextEdit_getText(self.widget)

    @text.setter
    def text(self, value):
        self.proxy.TextEdit_setText(self.widget, notnone(value))

    @property
    def placeholder(self):
        return self.proxy.TextEdit_getPlaceholderText(self.widget)

    @placeholder.setter
    def placeholder(self, value):
        self.proxy.TextEdit_setPlaceholderText(self.widget, notnone(value))

    @property
    def editable(self):
        return self.proxy.TextEdit_getEditable(self.widget)

    @editable.setter
    def editable(self, value):
        self.proxy.TextEdit_setEditable(self.widget, value)

    @property
    def selected_text(self):
        return self.proxy.TextEdit_getSelectedText(self.widget)

    @property
    def cursor_position(self):
        position, block_number, column_number, _, _ = self.proxy.TextEdit_getCursorInfo(self.widget)
        return CursorPosition(position, block_number, column_number)

    @property
    def selection(self):
        _, _, _, start, end = self.proxy.TextEdit_getCursorInfo(self.widget)
        return Selection(start, end)

    def append_text(self, value):
        self.proxy.TextEdit_appendText(self.widget, notnone(value))

    def insert_text(self, value):
        self.proxy.TextEdit_insertText(self.widget, notnone(value))

    def clear_selection(self):
        self.proxy.TextEdit_clearSelection(self.widget)

    def remove_selected_text(self):
        self.proxy.TextEdit_removeSelectedText(self.widget)

    def select_all(self):
        self.proxy.TextEdit_selectAll(self.widget)

    def move_cursor_position(self, operation, mode=None, n=1):
        self.proxy.TextEdit_moveCursorPosition(self.widget, operation, mode, n)

    def set_text_color(self, color):
        if color == "red":
            self.proxy.TextEdit_setTextColor(self.widget, 255, 0, 0)
        elif color == "green":
            self.proxy.TextEdit_setTextColor(self.widget, 0, 255, 0)
        elif color == "blue":
            self.proxy.TextEdit_setTextColor(self.widget, 0, 0, 255)
        elif color == "orange":
            self.proxy.TextEdit_setTextColor(self.widget, 255, 128, 0)
        elif color == "purple":
            self.proxy.TextEdit_setTextColor(self.widget, 128, 0, 128)
        elif color == "brown":
            self.proxy.TextEdit_setTextColor(self.widget, 150, 75, 0)
        elif color == "black":
            self.proxy.TextEdit_setTextColor(self.widget, 0, 0, 0)
        else:
            self.proxy.TextEdit_setTextColor(self.widget, 255, 255, 255)

    @property
    def word_wrap_mode(self):
        return self.__word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, value: str) -> None:
        self.__word_wrap_mode = value
        self.proxy.TextEdit_setWordWrapMode(self.widget, value)

    def cursorPositionChanged(self):
        if callable(self.on_cursor_position_changed):
            self.on_cursor_position_changed(self.cursor_position)

    def selectionChanged(self):
        if callable(self.on_selection_changed):
            self.on_selection_changed(self.selection)

    def textChanged(self):
        if callable(self.on_text_changed):
            self.on_text_changed(self.text)

    def escapePressed(self):
        if callable(self.on_escape_pressed):
            return self.on_escape_pressed()
        return False

    def returnPressed(self):
        if callable(self.on_return_pressed):
            return self.on_return_pressed()
        return False

    def keyPressed(self, text, key, raw_modifiers):
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def insertFromMimeData(self, raw_mime_data):
        mime_data = QtMimeData(self.proxy, raw_mime_data)
        if callable(self.on_insert_mime_data):
            self.on_insert_mime_data(mime_data)
        else:
            self.insert_text(mime_data.data_as_string("text/plain"))


class TextEditWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        self.__binding = None
        self.__in_update = False

        def handle_cursor_position_changed(cursor_position):
            if callable(self.on_cursor_position_changed):
                self.on_cursor_position_changed(cursor_position)

        self._behavior.on_cursor_position_changed = handle_cursor_position_changed

        def handle_selection_changed(selection):
            if callable(self.on_selection_changed):
                self.on_selection_changed(selection)

        self._behavior.on_selection_changed = handle_selection_changed

        def handle_text_changed(text):
            if callable(self.on_text_changed):
                self.on_text_changed(text)

        self._behavior.on_text_changed = handle_text_changed

        def handle_escape_pressed():
            if callable(self.on_escape_pressed):
                return self.on_escape_pressed()
            return False

        self._behavior.on_escape_pressed = handle_escape_pressed

        def handle_return_pressed():
            if callable(self.on_return_pressed):
                return self.on_return_pressed()
            return False

        self._behavior.on_return_pressed = handle_return_pressed

        def handle_key_pressed(key):
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_insert_from_mime_data(mime_data):
            if callable(self.on_insert_mime_data):
                self.on_insert_mime_data(mime_data)

        self._behavior.on_insert_from_mime_data = handle_insert_from_mime_data

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_text")
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        super().close()

    @property
    def text(self) -> str:
        return self._behavior.text

    @text.setter
    def text(self, text: str) -> None:
        self._behavior.text = text

    @property
    def placeholder(self) -> str:
        return self._behavior.placeholder

    @placeholder.setter
    def placeholder(self, text: str) -> None:
        self._behavior.placeholder = text

    @property
    def editable(self) -> bool:
        return self._behavior.editable

    @editable.setter
    def editable(self, value: bool) -> None:
        self._behavior.editable = value

    @property
    def selected_text(self) -> str:
        return self._behavior.selected_text

    @property
    def cursor_position(self):
        return self._behavior.cursor_position

    @property
    def selection(self):
        return self._behavior.selection

    def append_text(self, value):
        self._behavior.append_text(value)

    def insert_text(self, value):
        self._behavior.insert_text(value)

    def clear_selection(self):
        self._behavior.clear_selection()

    def remove_selected_text(self):
        self._behavior.remove_selected_text()

    def select_all(self):
        self._behavior.select_all()

    def move_cursor_position(self, operation, mode=None, n=1):
        self._behavior.move_cursor_position(operation, mode, n)

    def handle_select_all(self):
        self.select_all()
        return True

    def set_text_color(self, color):
        self._behavior.set_text_color(color)

    @property
    def word_wrap_mode(self):
        return self._behavior.word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, value: str) -> None:
        self._behavior.word_wrap_mode = value

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.text = binding.get_target_value()
        def update_field(text):
            self.text = text
            if self.focused:
                pass # self.select_all()
        self.__binding = binding
        def update_text(text):
            if not self.__in_update:
                self.add_task("update_text", lambda: update_field(text))
        self.__binding.target_setter = update_text
        def on_text_changed(text):
            self.__in_update = True
            self.__binding.update_source(text)
            self.__in_update = False
        self.on_text_changed = on_text_changed

    def unbind_text(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_text_changed = None


class QtCanvasWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        super().__init__(proxy, "canvas", properties)
        self.proxy.Canvas_connect(self.widget, self)
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
        self.on_pan_gesture = None
        self.__focusable = False

    def close(self):
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
        self.on_pan_gesture = None
        super().close()

    @property
    def focusable(self):
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable):
        self.__focusable = focusable
        self.proxy.Canvas_setFocusPolicy(self.widget, 15 if focusable else 0)

    def draw(self, drawing_context):
        # self.proxy.Canvas_draw(self.widget, self.proxy.convert_drawing_commands(drawing_context.commands), drawing_context_storage)
        self.proxy.Canvas_draw_binary(self.widget, drawing_context.binary_commands, drawing_context.images)

    def set_cursor_shape(self, cursor_shape):
        cursor_shape = cursor_shape or "arrow"
        self.proxy.Canvas_setCursorShape(self.widget, cursor_shape)

    def grab_gesture(self, gesture_type):
        self.proxy.Widget_grabGesture(self.widget, gesture_type)

    def release_gesture(self, gesture_type):
        self.proxy.Widget_ungrabGesture(self.widget, gesture_type)

    def grab_mouse(self, gx, gy):
        self.proxy.Canvas_grabMouse(self.widget, gx, gy)

    def release_mouse(self):
        self.proxy.Canvas_releaseMouse(self.widget)

    def mouseEntered(self):
        if callable(self.on_mouse_entered):
            self.on_mouse_entered()

    def mouseExited(self):
        if callable(self.on_mouse_exited):
            self.on_mouse_exited()

    def mouseClicked(self, x, y, raw_modifiers):
        if callable(self.on_mouse_clicked):
            self.on_mouse_clicked(x, y, QtKeyboardModifiers(raw_modifiers))

    def mouseDoubleClicked(self, x, y, raw_modifiers):
        if callable(self.on_mouse_double_clicked):
            self.on_mouse_double_clicked(x, y, QtKeyboardModifiers(raw_modifiers))

    def mousePressed(self, x, y, raw_modifiers):
        if callable(self.on_mouse_pressed):
            self.on_mouse_pressed(x, y, QtKeyboardModifiers(raw_modifiers))

    def mouseReleased(self, x, y, raw_modifiers):
        if callable(self.on_mouse_released):
            self.on_mouse_released(x, y, QtKeyboardModifiers(raw_modifiers))

    def mousePositionChanged(self, x, y, raw_modifiers):
        if callable(self.on_mouse_position_changed):
            self.on_mouse_position_changed(x, y, QtKeyboardModifiers(raw_modifiers))

    def grabbedMousePositionChanged(self, dx, dy, raw_modifiers):
        if callable(self.on_grabbed_mouse_position_changed):
            self.on_grabbed_mouse_position_changed(dx, dy, QtKeyboardModifiers(raw_modifiers))

    def wheelChanged(self, x, y, dx, dy, is_horizontal):
        if callable(self.on_wheel_changed):
            self.on_wheel_changed(x, y, dx, dy, is_horizontal)

    def sizeChanged(self, width, height):
        if callable(self.on_size_changed):
            self.on_size_changed(width, height)

    def keyPressed(self, text, key, raw_modifiers):
        if callable(self.on_key_pressed):
            return self.on_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def keyReleased(self, text, key, raw_modifiers):
        if callable(self.on_key_released):
            return self.on_key_released(QtKey(text, key, raw_modifiers))
        return False

    def dragEnterEvent(self, raw_mime_data):
        if callable(self.on_drag_enter):
            return self.on_drag_enter(QtMimeData(self.proxy, raw_mime_data))
        return "ignore"

    def dragLeaveEvent(self):
        if callable(self.on_drag_leave):
            return self.on_drag_leave()
        return "ignore"

    def dragMoveEvent(self, raw_mime_data, x, y):
        if callable(self.on_drag_move):
            return self.on_drag_move(QtMimeData(self.proxy, raw_mime_data), x, y)
        return "ignore"

    def dropEvent(self, raw_mime_data, x, y):
        if callable(self.on_drop):
            return self.on_drop(QtMimeData(self.proxy, raw_mime_data), x, y)
        return "ignore"

    def panGesture(self, delta_x, delta_y):
        if callable(self.on_pan_gesture):
            self.on_pan_gesture(delta_x, delta_y)


class CanvasWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_periodic = None
        self.on_dispatch_any = None
        self.on_will_dispatch = None
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
        self.on_pan_gesture = None
        self.width = 0
        self.height = 0
        self.__canvas_item = CanvasItem.RootCanvasItem(self)

        def handle_mouse_entered():
            if callable(self.on_mouse_entered):
                self.on_mouse_entered()

        self._behavior.on_mouse_entered = handle_mouse_entered

        def handle_mouse_exited():
            if callable(self.on_mouse_exited):
                self.on_mouse_exited()

        self._behavior.on_mouse_exited = handle_mouse_exited

        def handle_mouse_clicked(x, y, modifiers):
            if callable(self.on_mouse_clicked):
                self.on_mouse_clicked(x, y, modifiers)

        self._behavior.on_mouse_clicked = handle_mouse_clicked

        def handle_mouse_double_clicked(x, y, modifiers):
            if callable(self.on_mouse_double_clicked):
                self.on_mouse_double_clicked(x, y, modifiers)

        self._behavior.on_mouse_double_clicked = handle_mouse_double_clicked

        def handle_mouse_pressed(x, y, modifiers):
            if callable(self.on_mouse_pressed):
                self.on_mouse_pressed(x, y, modifiers)

        self._behavior.on_mouse_pressed = handle_mouse_pressed

        def handle_mouse_released(x, y, modifiers):
            if callable(self.on_mouse_released):
                self.on_mouse_released(x, y, modifiers)

        self._behavior.on_mouse_released = handle_mouse_released

        def handle_mouse_position_changed(x, y, modifiers):
            # mouse tracking takes priority over timer events in newer
            # versions of Qt, so during mouse tracking, make sure periodic
            # gets called regularly.
            self.periodic()
            if callable(self.on_mouse_position_changed):
                self.on_mouse_position_changed(x, y, modifiers)

        self._behavior.on_mouse_position_changed = handle_mouse_position_changed

        def handle_grabbed_mouse_position_changed(dx, dy, modifiers):
            if callable(self.on_grabbed_mouse_position_changed):
                self.on_grabbed_mouse_position_changed(dx, dy, modifiers)

        self._behavior.on_grabbed_mouse_position_changed = handle_grabbed_mouse_position_changed

        def handle_wheel_changed(x, y, dx, dy, is_horizontal):
            if callable(self.on_wheel_changed):
                self.on_wheel_changed(x, y, dx, dy, is_horizontal)

        self._behavior.on_wheel_changed = handle_wheel_changed

        def handle_size_changed(width, height):
            self.width = width
            self.height = height
            if callable(self.on_size_changed):
                self.on_size_changed(width, height)

        self._behavior.on_size_changed = handle_size_changed

        def handle_key_pressed(key):
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_key_released(key):
            if callable(self.on_key_released):
                return self.on_key_released(key)
            return False

        self._behavior.on_key_released = handle_key_released

        def handle_drag_enter_event(mime_data):
            if callable(self.on_drag_enter):
                return self.on_drag_enter(mime_data)
            return "ignore"

        self._behavior.on_drag_enter_event = handle_drag_enter_event

        def handle_drag_leave_event():
            if callable(self.on_drag_leave):
                return self.on_drag_leave()
            return "ignore"

        self._behavior.on_drag_leave_event = handle_drag_leave_event

        def handle_drag_move_event(mime_data, x, y):
            if callable(self.on_drag_move):
                return self.on_drag_move(mime_data, x, y)
            return "ignore"

        self._behavior.on_drag_move_event = handle_drag_move_event

        def handle_drop_event(mime_data, x, y):
            if callable(self.on_drop):
                return self.on_drop(mime_data, x, y)
            return "ignore"

        self._behavior.on_drop_event = handle_drop_event

        def handle_pan_gesture(delta_x, delta_y):
            if callable(self.on_pan_gesture):
                self.on_pan_gesture(delta_x, delta_y)

        self._behavior.on_pan_gesture = handle_pan_gesture

    def close(self):
        if self.__canvas_item:
            self.__canvas_item.close()
            self.__canvas_item = None
        # messages generated from this class
        self.on_periodic = None
        self.on_dispatch_any = None
        self.on_will_dispatch = None
        # messages passed on from the behavior
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
        self.on_pan_gesture = None
        super().close()

    def periodic(self):
        super().periodic()
        if self.on_periodic:
            self.on_periodic()

    @property
    def canvas_item(self):
        return self.__canvas_item

    @property
    def canvas_size(self):
        return (self.height, self.width)

    @property
    def focusable(self) -> bool:
        return self._behavior.focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        self._behavior.focusable = focusable

    def create_drawing_context(self) -> DrawingContext.DrawingContext:
        return DrawingContext.DrawingContext()

    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None:
        self._behavior.draw(drawing_context)

    def set_cursor_shape(self, cursor_shape: str) -> None:
        self._behavior.set_cursor_shape(cursor_shape)

    def simulate_mouse_click(self, x, y, modifiers):
        if self.on_mouse_pressed:
            self.on_mouse_pressed(x, y, modifiers)
        if self.on_mouse_released:
            self.on_mouse_released(x, y, modifiers)
        if self.on_mouse_clicked:
            self.on_mouse_clicked(x, y, modifiers)

    def grab_gesture(self, gesture_type):
        self._behavior.grab_gesture(gesture_type)

    def release_gesture(self, gesture_type):
        self._behavior.release_gesture(gesture_type)

    def grab_mouse(self, gx, gy):
        self._behavior.grab_mouse(gx, gy)

    def release_mouse(self):
        self._behavior.release_mouse()

    def _dispatch_any(self, method: str, *args, **kwargs):
        if callable(self.on_dispatch_any):
            return self.on_dispatch_any(method, *args, **kwargs)
        return False

    def _will_dispatch(self, method) -> bool:
        if callable(self.on_will_dispatch):
            return self.on_will_dispatch(method)
        return False


class QtTreeWidgetBehavior(QtWidgetBehavior):

    def __init__(self, proxy, properties):
        properties = copy.deepcopy(properties) if properties is not None else dict()
        properties["stylesheet"] = "* { border: none; background-color: '#EEEEEE'; } TreeWidget { margin-top: 4px }"
        super().__init__(proxy, "pytree", properties)
        self.proxy.TreeWidget_connect(self.widget, self)
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        self.on_focus_changed = None
        self.__selection_mode = "single"

    def close(self):
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        self.on_focus_changed = None
        super().close()

    @property
    def selection_mode(self):
        return self.__selection_mode

    @selection_mode.setter
    def selection_mode(self, selection_mode):
        self.__selection_mode = selection_mode
        self.proxy.TreeWidget_setSelectionMode(self.widget, selection_mode)

    @property
    def item_model_controller(self):
        return self.__item_model_controller

    @item_model_controller.setter
    def item_model_controller(self, item_model_controller):
        self.__item_model_controller = item_model_controller
        self.proxy.TreeWidget_setModel(self.widget, item_model_controller.py_item_model)

    def set_current_row(self, index, parent_row, parent_id):
        self.proxy.TreeWidget_setCurrentRow(self.widget, index, parent_row, parent_id)

    def clear_current_row(self):
        self.proxy.TreeWidget_setCurrentRow(self.widget, -1, -1, 0)

    def keyPressed(self, indexes, text, key, raw_modifiers):
        if callable(self.on_key_pressed):
            return self.on_key_pressed(indexes, QtKey(text, key, raw_modifiers))
        return False

    def treeItemChanged(self, index, parent_row, parent_id):
        if callable(self.on_current_item_changed):
            self.on_current_item_changed(index, parent_row, parent_id)

    def treeSelectionChanged(self, selected_indexes):
        if callable(self.on_selection_changed):
            self.on_selection_changed(selected_indexes)

    def treeItemKeyPressed(self, index, parent_row, parent_id, text, key, raw_modifiers):
        if callable(self.on_item_key_pressed):
            return self.on_item_key_pressed(index, parent_row, parent_id, QtKey(text, key, raw_modifiers))
        return False

    def treeItemClicked(self, index, parent_row, parent_id):
        if callable(self.on_item_clicked):
            return self.on_item_clicked(index, parent_row, parent_id)
        return False

    def treeItemDoubleClicked(self, index, parent_row, parent_id):
        if callable(self.on_item_double_clicked):
            return self.on_item_double_clicked(index, parent_row, parent_id)
        return False

    def focusIn(self):
        if callable(self.on_focus_changed):
            self.on_focus_changed(True)

    def focusOut(self):
        if callable(self.on_focus_changed):
            self.on_focus_changed(False)


class TreeWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        self.on_focus_changed = None

        def handle_key_pressed(indexes, key):
            if callable(self.on_key_pressed):
                return self.on_key_pressed(indexes, key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_tree_item_changed(index, parent_row, parent_id):
            if callable(self.on_current_item_changed):
                self.on_current_item_changed(index, parent_row, parent_id)

        self._behavior.on_tree_item_changed = handle_tree_item_changed

        def handle_tree_selection_changed(selected_indexes):
            if callable(self.on_selection_changed):
                self.on_selection_changed(selected_indexes)

        self._behavior.on_tree_selection_changed = handle_tree_selection_changed

        def handle_tree_item_key_pressed(index, parent_row, parent_id, key):
            if callable(self.on_item_key_pressed):
                return self.on_item_key_pressed(index, parent_row, parent_id, key)
            return False

        self._behavior.on_tree_item_key_pressed = handle_tree_item_key_pressed

        def handle_tree_item_clicked(index, parent_row, parent_id):
            if callable(self.on_item_clicked):
                return self.on_item_clicked(index, parent_row, parent_id)
            return False

        self._behavior.on_tree_item_clicked = handle_tree_item_clicked

        def handle_tree_item_double_clicked(index, parent_row, parent_id):
            if callable(self.on_item_double_clicked):
                return self.on_item_double_clicked(index, parent_row, parent_id)
            return False

        self._behavior.on_tree_item_double_clicked = handle_tree_item_double_clicked

        def handle_focus_changed(self, focused):
            if callable(self.on_focus_changed):
                self.on_focus_changed(focused)

        self._behavior.on_focus_changed = handle_focus_changed

    def close(self):
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        self.on_focus_changed = None
        super().close()

    @property
    def selection_mode(self):
        return self._behavior.selection_mode

    @selection_mode.setter
    def selection_mode(self, value):
        self._behavior.selection_mode = value

    @property
    def item_model_controller(self):
        return self._behavior.item_model_controller

    @item_model_controller.setter
    def item_model_controller(self, value):
        self._behavior.item_model_controller = value

    def set_current_row(self, index, parent_row, parent_id):
        self._behavior.set_current_row(index, parent_row, parent_id)

    def clear_current_row(self):
        self._behavior.clear_current_row()


class QtAction:

    def __init__(self, proxy, native_action=None):
        self.proxy = proxy
        self.native_action = native_action  # action is not connected since native_action will not by PyAction
        self.on_triggered = None

    def close(self):
        self.proxy = None
        self.native_action = None
        self.on_triggered = None

    def create(self, document_window, title, key_sequence, role):
        self.native_action = self.proxy.Action_create(document_window.native_document_window, title, key_sequence, role)
        self.proxy.Action_connect(self.native_action, self)

    # public method to trigger button
    def trigger(self):
        if self.on_triggered:
            self.on_triggered()

    # comes from the Qt code
    def triggered(self):
        self.trigger()

    @property
    def title(self):
        return self.proxy.Action_getTitle(self.native_action) if self.native_action else str()

    @title.setter
    def title(self, value):
        self.proxy.Action_setTitle(self.native_action, value)

    @property
    def checked(self):
        return self.proxy.Action_getChecked(self.native_action) if self.native_action else False

    @checked.setter
    def checked(self, checked):
        self.proxy.Action_setChecked(self.native_action, checked)

    @property
    def enabled(self):
        return self.proxy.Action_getEnabled(self.native_action) if self.native_action else True

    @enabled.setter
    def enabled(self, enabled):
        self.proxy.Action_setEnabled(self.native_action, enabled)


class QtMenu:

    def __init__(self, proxy, document_window, native_menu):
        self.proxy = proxy
        self.document_window = document_window
        self.native_menu = native_menu
        self.proxy.Menu_connect(self.native_menu, self)
        self.on_about_to_show = None
        self.on_about_to_hide = None

    def destroy(self):
        self.proxy.Menu_destroy(self.native_menu)
        self.native_menu = None
        self.on_about_to_show = None
        self.on_about_to_hide = None

    def aboutToShow(self):
        if self.on_about_to_show:
            self.on_about_to_show()

    def aboutToHide(self):
        if self.on_about_to_hide:
            self.on_about_to_hide()

    def add_menu_item(self, title, callback, key_sequence=None, role=None):
        action = QtAction(self.proxy)
        action.create(self.document_window, title, key_sequence, role)
        action.on_triggered = callback
        self.proxy.Menu_addAction(self.native_menu, action.native_action)
        return action

    def add_action(self, action):
        self.proxy.Menu_addAction(self.native_menu, action.native_action)

    def add_sub_menu(self, title, menu):
        self.proxy.Menu_addMenu(self.native_menu, notnone(title), menu.native_menu)

    def add_separator(self):
        self.proxy.Menu_addSeparator(self.native_menu)

    def insert_menu_item(self, title, before_action, callback, key_sequence=None, role=None):
        action = QtAction(self.proxy)
        action.create(self.document_window, title, key_sequence, role)
        action.on_triggered = callback
        self.proxy.Menu_insertAction(self.native_menu, action.native_action, before_action.native_action)
        return action

    def insert_separator(self, before_action):
        self.proxy.Menu_insertSeparator(self.native_menu, before_action.native_action)

    def remove_action(self, action):
        self.proxy.Menu_removeAction(self.native_menu, action.native_action)

    def popup(self, gx, gy):
        self.proxy.Menu_popup(self.native_menu, gx, gy)


class Window:

    def __init__(self, title):
        self.root_widget = None
        self.has_event_loop = True
        self.window_style = "window"
        self.__dock_widget_weak_refs = list()
        self.on_periodic = None
        self.on_queue_task = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_activation_changed = None
        self.on_size_changed = None
        self.on_position_changed = None
        self.pos_x = None
        self.pos_y = None
        self.width = None
        self.height = None
        self.__title = title if title is not None else str()

    def close(self):
        # this is a callback and should not be invoked directly from Python;
        # call request_close instead.
        if self.root_widget:
            self.root_widget.close()
            self.root_widget = None
        self.on_periodic = None
        self.on_queue_task = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_activation_changed = None
        self.on_size_changed = None
        self.on_position_changed = None

    def request_close(self):
        raise NotImplemented()

    # attach the root widget to this window
    # the root widget must respond to _set_root_container
    def attach(self, root_widget):
        self.root_widget = root_widget
        self.root_widget._set_root_container(self)
        self._attach_root_widget(root_widget)

    def _attach_root_widget(self, root_widget):
        raise NotImplemented()

    def detach(self):
        assert self.root_widget is not None
        self.root_widget.close()
        self.root_widget = None

    @property
    def dock_widgets(self):
        return [dock_widget_weak_ref() for dock_widget_weak_ref in self.__dock_widget_weak_refs]

    def register_dock_widget(self, dock_widget):
        self.__dock_widget_weak_refs.append(weakref.ref(dock_widget))

    def unregister_dock_widget(self, dock_widget):
        self.__dock_widget_weak_refs.remove(weakref.ref(dock_widget))

    def queue_task(self, task):
        if self.on_queue_task:
            self.on_queue_task(task)

    def add_task(self, key, task):
        if self.on_add_task:
            self.on_add_task(key + str(id(self)), task)

    def clear_task(self, key):
        if self.on_clear_task:
            self.on_clear_task(key + str(id(self)))

    @property
    def focus_widget(self):
        return self._get_focus_widget()

    def _get_focus_widget(self):
        raise NotImplemented()

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        raise NotImplemented()

    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        raise NotImplemented()

    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        raise NotImplemented()

    def create_dock_widget(self, widget, panel_id, title, positions, position):
        raise NotImplemented()

    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        raise NotImplemented()

    @property
    def screen_size(self) -> Geometry.IntSize:
        return self._get_screen_size()

    def _get_screen_size(self):
        raise NotImplemented()

    @property
    def display_scaling(self) -> float:
        return self._get_display_scaling()

    def _get_display_scaling(self):
        raise NotImplemented()

    # call show to display the window.
    def show(self, size=None, position=None):
        raise NotImplemented()

    def fill_screen(self):
        raise NotImplemented()

    @property
    def title(self):
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = value
        self._set_title(value)

    def _set_title(self, value):
        raise NotImplemented()

    def _handle_periodic(self):
        if self.root_widget:
            self.root_widget.periodic()
        if self.on_periodic:
            self.on_periodic()

    def _handle_about_to_show(self):
        if self.on_about_to_show:
            self.on_about_to_show()

    def _handle_activation_changed(self, activated):
        if self.on_activation_changed:
            self.on_activation_changed(activated)

    def _handle_about_to_close(self, geometry, state):
        if self.on_about_to_close:
            self.on_about_to_close(geometry, state)

    def add_menu(self, title):
        raise NotImplemented()

    def insert_menu(self, title, before_menu):
        raise NotImplemented()

    def restore(self, geometry, state):
        raise NotImplemented()

    def _handle_size_changed(self, width, height):
        self.width = width
        self.height = height
        if callable(self.on_size_changed):
            self.on_size_changed(self.width, self.height)

    def _handle_position_changed(self, x, y):
        self.pos_x = x
        self.pos_y = y
        if callable(self.on_position_changed):
            self.on_position_changed(self.pos_x, self.pos_y)


class QtWindow(Window):

    def __init__(self, proxy, title):
        super().__init__(title)
        self.proxy = proxy
        self.native_document_window = self.proxy.DocumentWindow_create(title)
        self.proxy.DocumentWindow_connect(self.native_document_window, self)

    def close(self):
        # this is a callback and should not be invoked directly from Python;
        # call request_close instead.
        assert self.native_document_window is not None
        self.native_document_window = None
        self.proxy = None
        super().close()

    def request_close(self):
        self.proxy.DocumentWindow_close(self.native_document_window)

    def _attach_root_widget(self, root_widget: Widget) -> None:
        self.proxy.DocumentWindow_setCentralWidget(self.native_document_window, extract_widget(root_widget))

    def _get_focus_widget(self):
        def match_native_widget(widget):
            if widget.focused:
                return widget
            for child_widget in widget._contained_widgets:
                matched_widget = match_native_widget(child_widget)
                if matched_widget:
                    return matched_widget
            return None
        return match_native_widget(self.root_widget)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        selected_filter = selected_filter if selected_filter else str()
        file_paths, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "loadmany", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_paths, filter, directory

    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "load", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        selected_filter = selected_filter if selected_filter else str()
        file_path, filter, directory = self.proxy.DocumentWindow_getFilePath(self.native_document_window, "save", notnone(title), notnone(directory), notnone(filter), notnone(selected_filter))
        return file_path, filter, directory

    def create_dock_widget(self, widget, panel_id, title, positions, position):
        return QtDockWidget(self.proxy, self, widget, panel_id, title, positions, position)

    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        self.proxy.DocumentWindow_tabifyDockWidgets(self.native_document_window, dock_widget1.native_dock_widget, dock_widget2.native_dock_widget)

    def _get_screen_size(self):
        w, h = self.proxy.DocumentWindow_getScreenSize(self.native_document_window)
        return Geometry.IntSize(width=w, height=h)

    def _get_display_scaling(self):
        return self.proxy.DocumentWindow_getDisplayScaling(self.native_document_window)

    def show(self, size=None, position=None):
        if size is not None:
            self.proxy.DocumentWindow_setSize(self.native_document_window, size.width, size.height)
        if position is not None:
            self.proxy.DocumentWindow_setPosition(self.native_document_window, position.x, position.y)
        self.proxy.DocumentWindow_show(self.native_document_window, self.window_style)

    def fill_screen(self):
        screen_size = self.screen_size
        self.proxy.DocumentWindow_setPosition(self.native_document_window, 0, 0)
        self.proxy.DocumentWindow_setSize(self.native_document_window, screen_size.width, screen_size.height)

    def _set_title(self, value):
        self.proxy.DocumentWindow_setTitle(self.native_document_window, notnone(value))

    def periodic(self):
        self._handle_periodic()

    def aboutToShow(self):
        self._handle_about_to_show()

    def activationChanged(self, activated):
        self._handle_activation_changed(activated)

    def aboutToClose(self, geometry, state):
        self._handle_about_to_close(geometry, state)

    def add_menu(self, title):
        native_menu = self.proxy.DocumentWindow_addMenu(self.native_document_window, notnone(title))
        menu = QtMenu(self.proxy, self, native_menu)
        return menu

    def insert_menu(self, title, before_menu):
        native_menu = self.proxy.DocumentWindow_insertMenu(self.native_document_window, notnone(title), before_menu.native_menu)
        menu = QtMenu(self.proxy, self, native_menu)
        return menu

    def restore(self, geometry, state):
        self.proxy.DocumentWindow_restore(self.native_document_window, geometry, state)

    def save(self):
        geometry, state = self.proxy.DocumentWindow_save(self.native_document_window)
        return geometry, state

    def sizeChanged(self, width, height):
        self._handle_size_changed(width, height)

    def positionChanged(self, x, y):
        self._handle_position_changed(x, y)


class QtDockWidget:

    def __init__(self, proxy, document_window, widget, panel_id, title, positions, position):
        self.proxy = proxy
        self.document_window = document_window
        self.document_window.register_dock_widget(self)
        self.widget = widget
        self.widget._set_root_container(self)
        self.on_size_changed = None
        self.width = None
        self.height = None
        self.native_dock_widget = self.proxy.DocumentWindow_addDockWidget(self.document_window.native_document_window, extract_widget(widget), panel_id, notnone(title), positions, position)
        self.proxy.DockWidget_connect(self.native_dock_widget, self)

    def close(self):
        self.proxy.DocumentWindow_removeDockWidget(self.document_window.native_document_window, self.native_dock_widget)
        self.widget.close()
        self.document_window.unregister_dock_widget(self)
        self.document_window = None
        self.on_size_changed = None
        self.widget = None
        self.native_dock_widget = None
        self.proxy = None

    @property
    def focus_widget(self):
        def match_native_widget(widget):
            if widget.focused:
                return widget
            for child_widget in widget._contained_widgets:
                matched_widget = match_native_widget(child_widget)
                if matched_widget:
                    return matched_widget
            return None
        return match_native_widget(self.widget)

    def queue_task(self, task):
        self.document_window.queue_task(task)

    def add_task(self, key, task):
        self.document_window.add_task(key + str(id(self)), task)

    def clear_task(self, key):
        self.document_window.clear_task(key + str(id(self)))

    def periodic(self):
        self.widget.periodic()

    @property
    def toggle_action(self):
        return QtAction(self.proxy, self.proxy.DockWidget_getToggleAction(self.native_dock_widget))

    def show(self):
        self.proxy.Widget_show(self.native_dock_widget)

    def hide(self):
        self.proxy.Widget_hide(self.native_dock_widget)

    def sizeChanged(self, width, height):
        self.width = width
        self.height = height
        if callable(self.on_size_changed):
            self.on_size_changed(self.width, self.height)


FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])


class QtUserInterface:

    def __init__(self, proxy):
        self.proxy = proxy
        self.persistence_root = "0"
        self.proxy.Core_syncLatencyTimer(time.perf_counter())

    def close(self):
        self.proxy.Application_close()
        self.proxy = None

    # data objects

    def create_mime_data(self):
        return QtMimeData(self.proxy)

    def create_item_model_controller(self, keys):
        return QtItemModelController(self.proxy, keys)

    def create_button_group(self):
        return QtButtonGroup(self.proxy)

    # window elements

    def create_document_window(self, title=None):
        return QtWindow(self.proxy, title)

    def destroy_document_window(self, document_window):
        document_window.close()

    # user interface elements

    def create_row_widget(self, alignment=None, properties=None):
        return BoxWidget(QtBoxWidgetBehavior(self.proxy, "row", properties), alignment)

    def create_column_widget(self, alignment=None, properties=None):
        return BoxWidget(QtBoxWidgetBehavior(self.proxy, "column", properties), alignment)

    def create_splitter_widget(self, orientation="vertical", properties=None):
        return SplitterWidget(QtSplitterWidgetBehavior(self.proxy, properties), orientation)

    def create_tab_widget(self, properties=None):
        return TabWidget(QtTabWidgetBehavior(self.proxy, properties))

    def create_stack_widget(self, properties=None):
        return StackWidget(QtStackWidgetBehavior(self.proxy, properties))

    def create_scroll_area_widget(self, properties=None):
        return ScrollAreaWidget(QtScrollAreaWidgetBehavior(self.proxy, properties))

    def create_combo_box_widget(self, items=None, item_getter=None, properties=None):
        return ComboBoxWidget(QtComboBoxWidgetBehavior(self.proxy, properties), items, item_getter)

    def create_push_button_widget(self, text=None, properties=None):
        return PushButtonWidget(QtPushButtonWidgetBehavior(self.proxy, properties), text)

    def create_radio_button_widget(self, text=None, properties=None):
        return RadioButtonWidget(QtRadioButtonWidgetBehavior(self.proxy, properties), text)

    def create_check_box_widget(self, text=None, properties=None):
        return CheckBoxWidget(QtCheckBoxWidgetBehavior(self.proxy, properties), text)

    def create_label_widget(self, text=None, properties=None):
        return LabelWidget(QtLabelWidgetBehavior(self.proxy, properties), text)

    def create_slider_widget(self, properties=None):
        return SliderWidget(QtSliderWidgetBehavior(self.proxy, properties))

    def create_line_edit_widget(self, properties=None):
        return LineEditWidget(QtLineEditWidgetBehavior(self.proxy, properties))

    def create_text_edit_widget(self, properties=None):
        return TextEditWidget(QtTextEditWidgetBehavior(self.proxy, properties))

    def create_canvas_widget(self, properties=None):
        return CanvasWidget(QtCanvasWidgetBehavior(self.proxy, properties))

    def create_tree_widget(self, properties=None):
        return TreeWidget(QtTreeWidgetBehavior(self.proxy, properties))

    # file i/o

    def load_rgba_data_from_file(self, filename):
        # returns data packed as uint32
        return self.proxy.decode_data(self.proxy.Core_readImageToBinary(notnone(filename)))

    def save_rgba_data_to_file(self, data, filename, format):
        return self.proxy.Core_writeBinaryToImage(data.shape[1], data.shape[0], data, notnone(filename), str(format))

    def get_existing_directory_dialog(self, title, directory):
        existing_directory, filter, directory = self.proxy.DocumentWindow_getFilePath(None, "directory", notnone(title), notnone(directory), str(), str())
        return existing_directory, directory

    # persistence (associated with application)

    def get_data_location(self):
        return self.proxy.Core_getLocation("data")

    def get_document_location(self):
        return self.proxy.Core_getLocation("documents")

    def get_temporary_location(self):
        return self.proxy.Core_getLocation("temporary")

    def get_persistent_string(self, key, default_value=None):
        key = "/".join([self.persistence_root, key])
        value = self.proxy.Settings_getString(key)
        return value if value else default_value

    def set_persistent_string(self, key, value):
        if value is not None:
            key = "/".join([self.persistence_root, key])
            self.proxy.Settings_setString(key, value)
        else:
            self.remove_persistent_key(key)

    def get_persistent_object(self, key, default_value=None):
        key = "/".join([self.persistence_root, key])
        value = self.get_persistent_string(key)
        return pickle.loads(binascii.unhexlify(value.encode("utf-8"))) if value else default_value

    def set_persistent_object(self, key, value):
        if value is not None:
            key = "/".join([self.persistence_root, key])
            self.set_persistent_string(key, binascii.hexlify(pickle.dumps(value, 0)).decode("utf-8"))
        else:
            self.remove_persistent_key(key)

    def remove_persistent_key(self, key):
        key = "/".join([self.persistence_root, key])
        self.proxy.Settings_remove(key)

    # clipboard

    def clipboard_clear(self):
        self.proxy.Clipboard_clear()

    def clipboard_mime_data(self):
        return QtMimeData(self.proxy, self.proxy.Clipboard_mimeData())

    def clipboard_set_mime_data(self, mime_data):
        self.proxy.Clipboard_setMimeData(mime_data.raw_mime_data)

    def clipboard_set_text(self, text):
        self.proxy.Clipboard_setText(text)

    def clipboard_text(self):
        return self.proxy.Clipboard_text()

    # misc

    def create_rgba_image(self, drawing_context, width, height):
        # return self.proxy.decode_data(self.proxy.DrawingContext_paintRGBA(self.proxy.convert_drawing_commands(drawing_context.commands), width, height))
        return self.proxy.decode_data(self.proxy.DrawingContext_paintRGBA_binary(drawing_context.binary_commands, copy.copy(drawing_context.images), width, height))

    def get_font_metrics(self, font, text):
        return self.proxy.decode_font_metrics(self.proxy.Core_getFontMetrics(font, text))

    def create_context_menu(self, document_window):
        context_menu = QtMenu(self.proxy, document_window, self.proxy.Menu_create())
        # the original code would destroy the menu when it was being hidden.
        # this caused crashes (right-click, Export...). the menu seems to be
        # still in use at the time it is hidden on Windows. so, delay its
        # destruction.
        context_menu.on_about_to_hide = lambda: document_window.queue_task(context_menu.destroy)
        return context_menu

    def create_sub_menu(self, document_window):
        sub_menu = QtMenu(self.proxy, document_window, self.proxy.Menu_create())
        return sub_menu
