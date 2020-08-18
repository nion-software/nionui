"""
Provides a user interface object that can render to an Qt host.
"""

# standard libraries
import abc
import collections
import copy
import enum
import numbers
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


FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])

MenuItemState = collections.namedtuple("MenuItemState", ["title", "enabled", "checked"])


class KeyboardModifiers(abc.ABC):

    def __str__(self):
        return "shift:{} control:{} alt:{} option:{} meta:{}".format(self.shift, self.control, self.alt, self.option, self.meta)

    # shift
    @property
    @abc.abstractmethod
    def shift(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_shift(self) -> bool:
        ...

    # control (command key on mac)
    @property
    @abc.abstractmethod
    def control(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_control(self) -> bool:
        ...

    # alt (option key on mac)
    @property
    @abc.abstractmethod
    def alt(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_alt(self) -> bool:
        ...

    # option (alt key on windows)
    @property
    @abc.abstractmethod
    def option(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_option(self) -> bool:
        ...

    # meta (control key on mac)
    @property
    @abc.abstractmethod
    def meta(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_meta(self) -> bool:
        ...

    # control key (all platforms)
    @property
    @abc.abstractmethod
    def native_control(self) -> bool:
        ...

    # keypad
    @property
    @abc.abstractmethod
    def keypad(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def only_keypad(self) -> bool:
        ...


class Key(abc.ABC):

    @property
    @abc.abstractmethod
    def text(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def key(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def modifiers(self) -> KeyboardModifiers:
        ...

    @property
    @abc.abstractmethod
    def is_delete(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_enter_or_return(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_escape(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_tab(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_insert(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_home(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_end(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_move_to_start_of_line(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_move_to_end_of_line(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_delete_to_end_of_line(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_arrow(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_left_arrow(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_up_arrow(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_right_arrow(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_down_arrow(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_page_up(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_page_down(self) -> bool:
        ...


class MimeData(abc.ABC):

    @property
    @abc.abstractmethod
    def formats(self) -> typing.Sequence[str]:
        ...

    def has_format(self, format: str) -> bool:
        return format in self.formats

    @property
    def has_urls(self) -> bool:
        return "text/uri-list" in self.formats

    @property
    def has_file_paths(self):
        return "text/uri-list" in self.formats

    @property
    def urls(self) -> typing.Sequence[str]:
        raw_urls = self.data_as_string("text/uri-list")
        return raw_urls.splitlines() if raw_urls and len(raw_urls) > 0 else []

    @property
    @abc.abstractmethod
    def file_paths(self) -> typing.Sequence[str]:
        ...

    @abc.abstractmethod
    def data_as_string(self, format: str) -> str:
        ...

    @abc.abstractmethod
    def set_data_as_string(self, format: str, text: str) -> None:
        ...


class Widget:

    def __init__(self, widget_behavior):
        self.__behavior = widget_behavior
        self.__behavior.on_ui_activity = self._register_ui_activity
        self.__root_container = None  # the document window
        self.__pending_keyed_tasks = list()
        self.__pending_queued_tasks = list()
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

        self.__enabled_binding = None
        self.__visible_binding = None
        self.__tool_tip_binding = None

        self.widget_id = None

    def close(self):
        if self.__enabled_binding:
            self.__enabled_binding.close()
            self.__enabled_binding = None
        if self.__visible_binding:
            self.__visible_binding.close()
            self.__visible_binding = None
        if self.__tool_tip_binding:
            self.__tool_tip_binding.close()
            self.__tool_tip_binding = None
        self.clear_task("update_enabled")
        self.clear_task("update_visible")
        self.clear_task("update_tool_tip")
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
        self._behavior._set_root_container(root_container)
        if self.__root_container:
            pending_keyed_tasks = self.__pending_keyed_tasks
            self.__pending_keyed_tasks = list()
            for key, task in pending_keyed_tasks:
                self.add_task(key, task)
            pending_queued_tasks = self.__pending_queued_tasks
            self.__pending_queued_tasks = list()
            for task in pending_queued_tasks:
                self.queue_task(task)

    def _register_ui_activity(self):
        if self.__root_container:
            self.__root_container._register_ui_activity()

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

    def run_pending_keyed_tasks(self):
        # used for testing
        pending_keyed_tasks = copy.copy(self.__pending_keyed_tasks)
        self.__pending_keyed_tasks.clear()
        for key, task in pending_keyed_tasks:
            if callable(task):
                task()

    @property
    def pending_keyed_tasks(self):
        # used for testing
        return copy.copy(self.__pending_keyed_tasks)

    @property
    def pending_queued_tasks(self):
        # used for testing
        return copy.copy(self.__pending_queued_tasks)

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
        else:
            self.__pending_keyed_tasks.append((key, task))

    # thread safe
    def clear_task(self, key):
        root_container = self.root_container
        if root_container:
            root_container.clear_task(key + str(id(self)))
        else:
            pending_keyed_tasks = copy.copy(self.__pending_keyed_tasks)
            self.__pending_keyed_tasks = list()
            for pending_key, task in pending_keyed_tasks:
                if key != pending_key:
                    self.__pending_keyed_tasks.append((pending_key, task))

    # thread safe
    def queue_task(self, task):
        root_container = self.root_container
        if root_container:
            root_container.queue_task(task)
        else:
            self.__pending_queued_tasks.append(task)

    def clear_queued_tasks(self) -> None:
        root_container = self.root_container
        if root_container:
            root_container.clear_queued_tasks()
        else:
            self.__pending_queued_tasks.clear()

    @property
    def focused(self) -> bool:
        return self._behavior.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self._behavior.focused = focused

    def refocus(self) -> None:
        pass

    def request_refocus(self) -> None:
        root_container = self.root_container
        if root_container:
            root_container.refocus_widget(self)

    @property
    def does_retain_focus(self) -> bool:
        return self._behavior.does_retain_focus

    @does_retain_focus.setter
    def does_retain_focus(self, value: bool) -> None:
        self._behavior.does_retain_focus = value

    @property
    def visible(self) -> bool:
        return self._behavior.visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        if self._behavior.visible != visible:
            self._behavior.visible = visible
            if self.__visible_binding:
                self.__visible_binding.update_source(visible)

    @property
    def enabled(self) -> bool:
        return self._behavior.enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        if self._behavior.enabled != enabled:
            self._behavior.enabled = enabled
            if self.__enabled_binding:
                self.__enabled_binding.update_source(enabled)

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
        if self._behavior.tool_tip != tool_tip:
            self._behavior.tool_tip = tool_tip
            if self.__tool_tip_binding:
                self.__tool_tip_binding.update_source(tool_tip)

    def set_property(self, key: str, value) -> None:
        self._behavior.set_property(key, value)

    def drag(self, mime_data: MimeData, thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None) -> None:
        self._behavior.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def map_to_global(self, p) -> Geometry.IntPoint:
        return self._behavior.map_to_global(p)

    def _dispatch_any(self, method: str, *args, **kwargs) -> bool:
        if hasattr(self, method):
            return getattr(self, method)(*args, **kwargs)
        return False

    def _can_dispatch_any(self, method: str) -> bool:
        return False

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[MenuItemState]:
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = getattr(self, menu_item_state_method)()
            if menu_item_state:
                return menu_item_state
        if hasattr(self, handle_method):
            return MenuItemState(title=None, enabled=True, checked=False)
        return None

    def bind_enabled(self, binding):
        if self.__enabled_binding:
            self.__enabled_binding.close()
            self.__enabled_binding = None
        self.enabled = binding.get_target_value()
        self.__enabled_binding = binding
        def update_enabled(enabled):
            def update_enabled_():
                if self._behavior:
                    self.enabled = enabled
            self.add_task("update_enabled", update_enabled_)
        self.__enabled_binding.target_setter = update_enabled

    def unbind_enabled(self):
        if self.__enabled_binding:
            self.__enabled_binding.close()
            self.__enabled_binding = None

    def bind_visible(self, binding):
        if self.__visible_binding:
            self.__visible_binding.close()
            self.__visible_binding = None
        self.visible = binding.get_target_value()
        self.__visible_binding = binding
        def update_visible(visible):
            def update_visible_():
                if self._behavior:
                    self.visible = visible
            self.add_task("update_visible", update_visible_)
        self.__visible_binding.target_setter = update_visible

    def unbind_visible(self):
        if self.__visible_binding:
            self.__visible_binding.close()
            self.__visible_binding = None

    def bind_tool_tip(self, binding):
        if self.__tool_tip_binding:
            self._tool_tipd_binding.close()
            self.__tool_tip_binding = None
        self.tool_tip = binding.get_target_value()
        self.__tool_tip_binding = binding
        def update_tool_tip(tool_tip):
            def update_tool_tip_():
                if self._behavior:
                    self.tool_tip = tool_tip
            self.add_task("update_tool_tip", update_tool_tip_)
        self.__tool_tip_binding.target_setter = update_tool_tip

    def unbind_tool_tip(self):
        if self.__tool_tip_binding:
            self.__tool_tip_binding.close()
            self.__tool_tip_binding = None


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
    def child_count(self) -> int:
        return len(self.children)

    def index(self, child: Widget) -> int:
        assert child in self.children
        return self.children.index(child)

    def insert(self, child, before: typing.Optional[typing.Union[Widget, int]], fill=False, alignment=None):
        assert child
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
            child = self.children[int(child)]
        child._set_root_container(None)
        self.children.remove(child)
        # closing the child should remove it from the layout
        child.close()

    def remove_all(self) -> None:
        for child in reversed(copy.copy(self.children)):
            self.remove(child)
        self._behavior.remove_all()  # spacing and stretches for Qt

    def add_stretch(self) -> None:
        child = self._behavior.add_stretch()
        self.children.append(child)

    def add_spacing(self, spacing: int) -> None:
        child = self._behavior.add_spacing(spacing)
        self.children.append(child)


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

    def set_sizes(self, sizes: typing.Sequence[int]) -> None:
        self._behavior.set_sizes(sizes)


class TabWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.children = []
        self.__current_index_binding = None
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

    @property
    def current_index(self):
        return self._behavior.current_index

    @current_index.setter
    def current_index(self, index):
        self._behavior.current_index = index

    def bind_current_index(self, binding):
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        current_index = binding.get_target_value()
        if current_index is not None and 0 <= current_index < len(self.children):
            self.current_index = current_index
        self.__current_index_binding = binding
        def update_current_index(current_index):
            if current_index is not None and 0 <= current_index < len(self.children):
                def update_current_index_():
                    if self._behavior:
                        self.current_index = current_index
                self.add_task("update_current_index", update_current_index_)
        self.__current_index_binding.target_setter = update_current_index
        self.on_current_index_changed = lambda index: self.__current_index_binding.update_source(index)

    def unbind_current_index(self):
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        self.on_current_index_changed = None


class StackWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.children = []
        self.__current_index_binding = None

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
    def child_count(self) -> int:
        return len(self.children)

    def index(self, child: Widget) -> int:
        assert child in self.children
        return self.children.index(child)

    def insert(self, child: Widget, before: typing.Optional[typing.Union[Widget, int]]) -> None:
        if isinstance(before, numbers.Integral):
            index = before
        else:
            index = self.index(before) if before is not None else self.child_count
        self._behavior.insert(child, index)
        self.children.insert(index, child)
        child._set_root_container(self.root_container)

    def add(self, child: Widget) -> None:
        self.insert(child, None)

    def remove(self, child: typing.Union[Widget, int]) -> None:
        if isinstance(child, numbers.Integral):
            child = self.children[int(child)]
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

    def bind_current_index(self, binding):
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        current_index = binding.get_target_value()
        if current_index is not None and 0 <= current_index < len(self.children):
            self.current_index = current_index
        self.__current_index_binding = binding
        def update_current_index(current_index):
            if current_index is not None and 0 <= current_index < len(self.children):
                def update_current_index_():
                    if self._behavior:
                        self.current_index = current_index
                self.add_task("update_current_index", update_current_index_)
        self.__current_index_binding.target_setter = update_current_index
        self.on_current_index_changed = lambda index: self.__current_index_binding.update_source(index)

    def unbind_current_index(self):
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        self.on_current_index_changed = None


class GroupWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.children = []
        self.__title = None

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
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        self.__title = value
        self._behavior.title = value


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


class ComboBoxWidget(Widget):

    def __init__(self, widget_behavior, items, item_getter):
        super().__init__(widget_behavior)
        self.__items : typing.Optional[typing.List] = None
        self.on_items_changed : typing.Optional[typing.Callable[[typing.List], None]] = None
        self.on_current_text_changed : typing.Optional[typing.Callable[[str], None]]= None
        self.on_current_item_changed : typing.Optional[typing.Callable[[typing.Any], None]] = None
        self.on_current_index_changed : typing.Optional[typing.Callable[[int], None]] = None
        self.item_getter = item_getter
        self.items = items if items else list()
        self.__current_item_binding = None
        self.__items_binding = None

        def handle_current_text_changed(text: str) -> None:
            if callable(self.on_current_text_changed):
                self.on_current_text_changed(text)
            if callable(self.on_current_item_changed):
                self.on_current_item_changed(self.current_item)
            if callable(self.on_current_index_changed):
                self.on_current_index_changed(self.current_index)

        self._behavior.on_current_text_changed = handle_current_text_changed

    def close(self) -> None:
        if self.__current_item_binding:
            self.__current_item_binding.close()
            self.__current_item_binding = None
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.clear_task("update_items")
        self.clear_task("update_current_index")
        self.item_getter = None
        self.__items = None
        self.on_items_changed = None
        self.on_current_text_changed = None
        self.on_current_item_changed = None
        self.on_current_index_changed = None
        super().close()

    @property
    def current_text(self) -> str:
        return self._behavior.current_text

    @current_text.setter
    def current_text(self, value: str) -> None:
        self._behavior.current_text = value

    @property
    def current_item(self) -> typing.Optional[typing.Any]:
        current_text = self.current_text
        for item in self.items or list():
            if current_text == notnone(self.item_getter(item) if self.item_getter else item):
                return item
        return None

    @current_item.setter
    def current_item(self, value: typing.Optional[typing.Any]) -> None:
        item_string = notnone(self.item_getter(value) if self.item_getter and value is not None else value)
        self.current_text = item_string

    @property
    def current_index(self) -> int:
        current_item = self.current_item
        return self.items.index(current_item) if current_item in self.items else None

    @current_index.setter
    def current_index(self, value: int) -> None:
        self.current_item = self.items[value] if value and value >= 0 and value < len(self.items) is not None else None

    @property
    def items(self) -> typing.List:
        return self.__items if self.__items is not None else list()

    @items.setter
    def items(self, items: typing.Sequence) -> None:
        current_index = self.current_index
        item_strings = list()
        self.__items = list()
        for item in items:
            item_string = notnone(self.item_getter(item) if self.item_getter else item)
            item_strings.append(item_string)
            self.__items.append(item)
        self._behavior.set_item_strings(item_strings)
        if callable(self.on_items_changed):
            self.on_items_changed(self.__items)
        if current_index != self.current_index:
            self.current_index = current_index

    def bind_items(self, binding) -> None:
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
            self.on_items_changed = None
        self.items = binding.get_target_value()
        self.__items_binding = binding
        def update_items(items):
            def update_items_():
                if self._behavior:
                    self.items = items
            self.add_task("update_items", update_items_)
        self.__items_binding.target_setter = update_items
        self.on_items_changed = lambda items: self.__items_binding.update_source(items)

    def unbind_items(self) -> None:
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.on_items_changed = None

    def bind_current_index(self, binding) -> None:
        if self.__current_item_binding:
            self.__current_item_binding.close()
            self.__current_item_binding = None
            self.on_current_index_changed = None
        current_index = binding.get_target_value()
        if current_index is not None and 0 <= current_index < len(self.__items):
            self.current_item = self.__items[current_index]
        self.__current_item_binding = binding
        def update_current_index(current_index: int) -> None:
            if current_index is not None and 0 <= current_index < len(self.__items):
                item = self.__items[current_index]
                def update_current_item_():
                    if self._behavior:
                        self.current_item = item
                self.add_task("update_current_index", update_current_item_)
                self.request_refocus()
        self.__current_item_binding.target_setter = update_current_index
        self.on_current_index_changed = lambda index: self.__current_item_binding.update_source(index)

    def unbind_current_index(self) -> None:
        if self.__current_item_binding:
            self.__current_item_binding.close()
            self.__current_item_binding = None
        self.on_current_index_changed = None


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

        self.__text_binding = None
        self.__icon_binding = None

    def close(self):
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None
        self.clear_task("update_text")
        self.clear_task("update_icon")
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

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        # close the old binding
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None

        # grab the initial value from the binding. use str method to convert value to text.
        value = binding.get_target_value()
        text = str(value) if value is not None else None
        self.text = text

        # save the binding and configure the the target setter
        # which will set the text when the binding changes
        self.__text_binding = binding

        def update_value(value) -> None:
            def update_value_inner() -> None:
                if self._behavior:
                    # use str method to convert value to text.
                    text = str(value) if value is not None else None
                    self.text = text
            self.add_task("update_text", update_value_inner)

        self.__text_binding.target_setter = update_value

    def unbind_text(self):
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None

    def bind_icon(self, binding):
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None
        self.icon = binding.get_target_value()
        self.__icon_binding = binding

        def update_icon(icon):
            def update_icon_():
                if self._behavior:
                    self.icon = icon

            self.add_task("update_icon", update_icon_)

        self.__icon_binding.target_setter = update_icon

    def unbind_icon(self):
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None


class RadioButtonWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.on_clicked = None
        self.text = text
        self.icon = None
        self.__value = None
        self.__group_value = None
        self.__on_group_value_changed = None
        self.__binding = None

        def handle_clicked():
            if self.__value is not None:
                self.group_value = self.__value
            if callable(self.on_clicked):
                self.on_clicked()

        self._behavior.on_clicked = handle_clicked

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_checked")
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

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = value
        self.checked = self.__group_value == self.__value

    @property
    def group_value(self):
        return self.__group_value

    @group_value.setter
    def group_value(self, group_value):
        self.__group_value = group_value
        self.checked = self.__group_value == self.__value
        if callable(self.__on_group_value_changed):
            self.__on_group_value_changed(group_value)

    # bind to value. takes ownership of binding.
    def bind_group_value(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
            self.__on_group_value_changed = None
        self.group_value = binding.get_target_value()
        self.__binding = binding
        def update_checked(group_value):
            def update_checked_():
                if self._behavior:
                    self.group_value = group_value
            self.add_task("update_checked", update_checked_)
        self.__binding.target_setter = update_checked
        self.__on_group_value_changed = lambda group_value: self.__binding.update_source(group_value)

    def unbind_group_value(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.__on_group_value_changed = None


class CheckBoxWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.on_checked_changed = None
        self.on_check_state_changed = None
        self.text = text
        self.__check_binding = None
        self.__text_binding = None

        def handle_check_state_changed(check_state):
            if callable(self.on_checked_changed):
                self.on_checked_changed(check_state == "checked")
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        self._behavior.on_check_state_changed = handle_check_state_changed

    def close(self):
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None
        if self.__check_binding:
            self.__check_binding.close()
            self.__check_binding = None
        self.clear_task("update_text")
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
        return self._behavior.check_state

    @check_state.setter
    def check_state(self, value):
        self._behavior.check_state = value

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        # close the old binding
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None

        # grab the initial value from the binding. use str method to convert value to text.
        value = binding.get_target_value()
        text = str(value) if value is not None else None
        self.text = text

        # save the binding and configure the the target setter
        # which will set the text when the binding changes
        self.__text_binding = binding

        def update_value(value) -> None:
            def update_value_inner() -> None:
                if self._behavior:
                    # use str method to convert value to text.
                    text = str(value) if value is not None else None
                    self.text = text
            self.add_task("update_text", update_value_inner)

        self.__text_binding.target_setter = update_value

    def unbind_text(self):
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None

    # bind to state. takes ownership of binding.
    def bind_checked(self, binding):
        if self.__check_binding:
            self.__check_binding.close()
            self.__check_binding = None
            self.on_checked_changed = None
        self.checked = binding.get_target_value()
        self.__check_binding = binding
        def update_checked(checked):
            def update_checked_():
                if self._behavior:
                    self.checked = checked
            self.add_task("update_checked", update_checked_)
        self.__check_binding.target_setter = update_checked
        self.on_checked_changed = lambda checked: self.__check_binding.update_source(checked)

    def unbind_checked(self):
        if self.__check_binding:
            self.__check_binding.close()
            self.__check_binding = None
        self.on_checked_changed = None

    # bind to state. takes ownership of binding.
    def bind_check_state(self, binding):
        if self.__check_binding:
            self.__check_binding.close()
            self.__check_binding = None
            self.on_check_state_changed = None
        self.check_state = binding.get_target_value()
        self.__check_binding = binding
        def update_check_state(check_state):
            def update_check_state_():
                if self._behavior:
                    self.check_state = check_state
            self.add_task("update_check_state", update_check_state_)
        self.__check_binding.target_setter = update_check_state
        self.on_check_state_changed = lambda check_state: self.__check_binding.update_source(check_state)

    def unbind_check_state(self):
        if self.__check_binding:
            self.__check_binding.close()
            self.__check_binding = None
        self.on_check_state_changed = None


class LabelWidget(Widget):

    def __init__(self, widget_behavior, text):
        super().__init__(widget_behavior)
        self.text = text
        self.__text_font = None
        self.__text_color = None
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
    def text_color(self) -> str:
        return self.__text_color

    @text_color.setter
    def text_color(self, value: str) -> None:
        self.__text_color = value
        self._behavior.set_text_color(value)

    @property
    def text_font(self) -> str:
        return self.__text_font

    @text_font.setter
    def text_font(self, value: str) -> None:
        self.__text_font = value
        self._behavior.set_text_font(value)

    @property
    def word_wrap(self):
        return self._behavior.word_wrap

    @word_wrap.setter
    def word_wrap(self, value):
        self._behavior.word_wrap = value

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        # close the old binding
        if self.__binding:
            self.__binding.close()
            self.__binding = None

        # grab the initial value from the binding. use str method to convert value to text.
        value = binding.get_target_value()
        text = str(value) if value is not None else None
        self.text = text

        # save the binding and configure the the target setter
        # which will set the text when the binding changes
        self.__binding = binding

        def update_value(value) -> None:
            def update_value_inner() -> None:
                if self._behavior:
                    # use str method to convert value to text.
                    text = str(value) if value is not None else None
                    self.text = text
            self.add_task("update_text", update_value_inner)

        self.__binding.target_setter = update_value

    def unbind_text(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None


class SliderWidget(Widget):
    # note: sliders with exactly the same configuration have problems on macOS.
    # see https://bugreports.qt.io/browse/QTBUG-77368
    # ensure different sliders by setting different min/max. argh.

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
        if value != self.value:
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
            self.on_value_changed = None
        self.value = binding.get_target_value()
        self.__binding = binding

        def update_value(value):
            def update_value_():
                if self._behavior:
                    # ensure that setting the value does not loop around with another value changed
                    old_value_changed = self.on_value_changed
                    self.on_value_changed = None
                    try:
                        self.value = value
                    finally:
                        self.on_value_changed = old_value_changed

            self.add_task("update_value", update_value_)

        self.__binding.target_setter = update_value

        def update_source(value):
            # ensure that responding to a changing slider value does not loop around with another value
            old_target_setter = self.__binding.target_setter
            self.__binding.target_setter = None
            try:
                self.__binding.update_source(value)
            finally:
                self.__binding.target_setter = old_target_setter

        self.on_value_changed = update_source

    def unbind_value(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_value_changed = None


class LineEditWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_editing_finished : typing.Optional[typing.Callable[[str], None]] = None
        self.on_escape_pressed : typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed : typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed : typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_text_edited : typing.Optional[typing.Callable[[str], None]] = None
        self.__binding = None
        self.__last_text = None

        def handle_editing_finished(text: str) -> None:
            if callable(self.on_editing_finished):
                self.on_editing_finished(text)
            self.__last_text = text

        self._behavior.on_editing_finished = handle_editing_finished

        def handle_escape_pressed() -> bool:
            if callable(self.on_escape_pressed):
                return self.on_escape_pressed()
            return False

        self._behavior.on_escape_pressed = handle_escape_pressed

        def handle_return_pressed() -> bool:
            if callable(self.on_return_pressed):
                return self.on_return_pressed()
            return False

        self._behavior.on_return_pressed = handle_return_pressed

        def handle_key_pressed(key: Key) -> bool:
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_text_edited(text: str) -> None:
            if callable(self.on_text_edited):
                self.on_text_edited(text)

        self._behavior.on_text_edited = handle_text_edited

    def close(self) -> None:
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

    def select_all(self) -> None:
        self._behavior.select_all()

    def handle_select_all(self) -> bool:
        self.select_all()
        return True

    def refocus(self) -> None:
        self.select_all()

    # bind to text. takes ownership of binding.
    def bind_text(self, binding) -> None:
        # close the old binding and clear other listener methods
        if self.__binding:
            self.__binding.close()
            self.__binding = None
            self.on_editing_finished = None
            self.on_return_pressed = None
            self.on_escape_pressed = None

        # grab the initial value from the binding. use str method to convert value to text.
        value = binding.get_target_value()
        text = str(value) if value is not None else None
        self.text = text

        # save the binding
        self.__binding = binding

        def update_value_(value) -> None:
            if self._behavior:
                text = str(value) if value is not None else None
                if self.text != text and (not self.focused or self.selected_text == self.text):
                    self.text = text
                    if self.focused:
                        self.select_all()

        def update_value(value) -> None:
            self.add_task("update_text", lambda: update_value_(value))

        # configure the the target setter which will set the text when the binding changes
        self.__binding.target_setter = update_value

        def editing_finished(text: str) -> None:
            if text != self.__last_text:
                self.__binding.update_source(text)

        # when editing is finished, update the binding value. the binding value will always
        # be set as a string.
        self.on_editing_finished = editing_finished

        def return_pressed() -> bool:
            text = self.text
            self.__binding.update_source(text)
            self.request_refocus()
            return True

        def escape_pressed() -> bool:
            text = self.__last_text
            self.__binding.update_source(text)
            self.request_refocus()
            return True

        # when return or escape are pressed, update th binding value (always a string).
        # in the case of escape, revert the value to the last text.
        self.on_return_pressed = return_pressed
        self.on_escape_pressed = escape_pressed

    def unbind_text(self) -> None:
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_editing_finished = None
        self.on_return_pressed = None
        self.on_escape_pressed = None

    def editing_finished(self, text: str) -> None:
        self._behavior.editing_finished(text)


Selection = collections.namedtuple("Selection", ["start", "end"])

CursorPosition = collections.namedtuple("CursorPosition", ["position", "block_number", "column_number"])


class TextEditWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None  # backwards compatibility
        self.on_text_edited = None
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
            if callable(self.on_text_edited):
                self.on_text_edited(text)

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

        def handle_key_pressed(key: Key) -> bool:
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_insert_mime_data(mime_data: MimeData) -> None:
            if callable(self.on_insert_mime_data):
                self.on_insert_mime_data(mime_data)
            else:
                text = mime_data.data_as_string("text/plain")
                self.insert_text(text)

        self._behavior.on_insert_mime_data = handle_insert_mime_data

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_text")
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_text_edited = None
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

    def refocus(self):
        self.select_all()

    def move_cursor_position(self, operation, mode=None, n=1):
        self._behavior.move_cursor_position(operation, mode, n)

    def handle_select_all(self):
        self.select_all()
        return True

    def set_line_height_proportional(self, proportional_line_height: float) -> None:
        self._behavior.set_line_height_proportional(proportional_line_height)

    def set_text_background_color(self, color: str) -> None:
        self._behavior.set_text_background_color(color)

    def set_text_color(self, color):
        self._behavior.set_text_color(color)

    def set_text_font(self, font_str: str) -> None:
        self._behavior.set_text_font(font_str)

    @property
    def word_wrap_mode(self):
        return self._behavior.word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, value: str) -> None:
        self._behavior.word_wrap_mode = value

    # bind to text. takes ownership of binding.
    def bind_text(self, binding):
        # close the old binding and clear other listener methods
        if self.__binding:
            self.__binding.close()
            self.__binding = None
            self.on_text_changed = None
            self.on_text_edited = None

        # grab the initial value from the binding. use str method to convert value to text.
        value = binding.get_target_value()
        text = str(value) if value is not None else None
        self.text = text

        # save the binding
        self.__binding = binding

        def update_value(value):
            def update_value_():
                if self._behavior:
                    text = str(value) if value is not None else None
                    self.text = text
            if not self.__in_update:
                self.add_task("update_text", update_value_)

        # configure the the target setter which will set the text when the binding changes
        self.__binding.target_setter = update_value

        def on_text_edited(text):
            self.__in_update = True
            self.__binding.update_source(text)
            self.__in_update = False

        # when text is edited, update the binding value (always a string).
        self.on_text_edited = on_text_edited

    def unbind_text(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_text_changed = None
        self.on_text_edited = None


class CanvasWidget(Widget):

    def __init__(self, widget_behavior, *, layout_render: str = None):
        super().__init__(widget_behavior)
        self.on_periodic = None
        self.on_dispatch_any = None
        self.on_can_dispatch_any = None
        self.on_get_menu_item_state = None
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
        self.width = 0
        self.height = 0
        self.position_info = None

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
            self.position_info = x, y, modifiers

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

        def handle_key_pressed(key: Key) -> bool:
            if callable(self.on_key_pressed):
                return self.on_key_pressed(key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_key_released(key: Key) -> bool:
            if callable(self.on_key_released):
                return self.on_key_released(key)
            return False

        self._behavior.on_key_released = handle_key_released

        def handle_drag_enter(mime_data: MimeData) -> str:
            if callable(self.on_drag_enter):
                return self.on_drag_enter(mime_data)
            return "ignore"

        self._behavior.on_drag_enter = handle_drag_enter

        def handle_drag_leave():
            if callable(self.on_drag_leave):
                return self.on_drag_leave()
            return "ignore"

        self._behavior.on_drag_leave = handle_drag_leave

        def handle_drag_move(mime_data: MimeData, x: int, y: int) -> str:
            if callable(self.on_drag_move):
                return self.on_drag_move(mime_data, x, y)
            return "ignore"

        self._behavior.on_drag_move = handle_drag_move

        def handle_drop(mime_data: MimeData, x: int, y: int) -> str:
            if callable(self.on_drop):
                return self.on_drop(mime_data, x, y)
            return "ignore"

        self._behavior.on_drop = handle_drop

        def handle_tool_tip(x: int, y: int, gx: int, gy: int) -> bool:
            if callable(self.on_tool_tip):
                return self.on_tool_tip(x, y, gx, gy)
            return False

        self._behavior.on_tool_tip = handle_tool_tip

        def handle_pan_gesture(delta_x, delta_y) -> bool:
            if callable(self.on_pan_gesture):
                return self.on_pan_gesture(delta_x, delta_y)
            return False

        self._behavior.on_pan_gesture = handle_pan_gesture

        self.__canvas_item = CanvasItem.RootCanvasItem(self, layout_render=layout_render)
        self._behavior._set_canvas_item(self.__canvas_item)

    def close(self):
        if self.__canvas_item:
            self.__canvas_item.close()
            self.__canvas_item = None
        # messages generated from this class
        self.on_periodic = None
        self.on_dispatch_any = None
        self.on_can_dispatch_any = None
        self.on_get_menu_item_state = None
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
        self.on_tool_tip = None
        self.on_pan_gesture = None
        super().close()

    def periodic(self):
        super().periodic()
        self._behavior.periodic()
        if self.on_periodic:
            self.on_periodic()
        if self.position_info is not None:
            if callable(self.on_mouse_position_changed):
                self.on_mouse_position_changed(*self.position_info)
            self.position_info = None

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

    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None:
        self._behavior.draw(drawing_context)

    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        self._behavior.draw_section(section_id, drawing_context, canvas_rect)

    def remove_section(self, section_id: int) -> None:
        self._behavior.remove_section(section_id)

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

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        self._behavior.show_tool_tip_text(text, gx, gy)

    def _dispatch_any(self, method: str, *args, **kwargs):
        if callable(self.on_dispatch_any):
            return self.on_dispatch_any(method, *args, **kwargs)
        return False

    def _can_dispatch_any(self, method: str) -> bool:
        if callable(self.on_can_dispatch_any):
            return self.on_can_dispatch_any(method)
        return False

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[MenuItemState]:
        if callable(self.on_get_menu_item_state):
            menu_item_state = self.on_get_menu_item_state(command_id)
            if menu_item_state:
                return menu_item_state
        return None


class ProgressBarWidget(CanvasWidget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.__value = 0
        self.__minimum = 0
        self.__maximum = 0
        self.on_value_changed = None
        self.__binding = None

        self.__progress_bar_canvas_item = CanvasItem.ProgressBarCanvasItem()
        self.__progress_bar_canvas_item.sizing.set_fixed_width(500)
        self.__progress_bar_canvas_item.sizing.set_fixed_height(20)
        self.canvas_item.add_canvas_item(self.__progress_bar_canvas_item)

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_task("update_value")
        self.on_value_changed = None
        super().close()

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        if value != self.__value:
            self.__value = value
            self.__progress_bar_canvas_item.progress = (value - self.__minimum) / (self.__maximum - self.__minimum) if self.__maximum != self.__minimum else 0.0
            if callable(self.on_value_changed):
                self.on_value_changed(value)

    @property
    def minimum(self):
        return self.__minimum

    @minimum.setter
    def minimum(self, minimum):
        self.__minimum = minimum

    @property
    def maximum(self):
        return self.__maximum

    @maximum.setter
    def maximum(self, maximum):
        self.__maximum = maximum

    # bind to value. takes ownership of binding.
    def bind_value(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
            self.on_value_changed = None
        self.value = binding.get_target_value()
        self.__binding = binding
        def update_value(value):
            def update_value_():
                if self._behavior:
                    self.value = value
            self.add_task("update_value", update_value_)
        self.__binding.target_setter = update_value
        self.on_value_changed = lambda value: self.__binding.update_source(value)

    def unbind_value(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_value_changed = None


class TreeWidget(Widget):

    def __init__(self, widget_behavior):
        super().__init__(widget_behavior)
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None

        def handle_key_pressed(indexes, key: Key) -> bool:
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

        def handle_tree_item_key_pressed(index, parent_row, parent_id, key: Key) -> bool:
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

    def close(self):
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
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

    def size_to_content(self):
        self._behavior.size_to_content()


class MenuAction:

    def __init__(self, action_id: str = None):
        self.action_id = action_id
        self.on_triggered = None
        self.on_ui_activity = None

    def close(self) -> None:
        self.on_triggered = None
        self.on_ui_activity = None

    def _register_ui_activity(self):
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    @property
    def title(self) -> str:
        raise NotImplementedError()

    @title.setter
    def title(self, value: str) -> None:
        raise NotImplementedError()

    @property
    def checked(self) -> bool:
        raise NotImplementedError()

    @checked.setter
    def checked(self, checked: bool) -> None:
        raise NotImplementedError()

    @property
    def enabled(self) -> bool:
        raise NotImplementedError()

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        raise NotImplementedError()

    def trigger(self) -> None:
        if self.on_triggered:
            self.on_triggered()

    def apply_state(self, menu_item_state: MenuItemState) -> None:
        if menu_item_state and menu_item_state.title is not None:
            self.title = menu_item_state.title
        else:
            self.title = self.title
        if menu_item_state and menu_item_state.checked is not None:
            self.checked = menu_item_state.checked
        else:
            self.checked = False
        if menu_item_state and menu_item_state.enabled is not None:
            self.enabled = menu_item_state.enabled
        else:
            self.enabled = False


class MenuItem:

    def __init__(self, *, action: MenuAction = None, is_separator: bool =False, sub_menu: "Menu" = None):
        self.action = action
        self.is_separator = is_separator
        self.sub_menu = sub_menu

    def close(self) -> None:
        if self.action:
            self.action.close()
        if self.sub_menu:
            self.sub_menu.close()
        self.action = None
        self.sub_menu = None

    @property
    def title(self):
        # NOTE: for backwards compatibility only (tests 0.14)
        if self.action:
            return self.action.title
        elif self.is_separator:
            return "separator"
        elif self.sub_menu:
            return self.sub_menu.title if self.sub_menu.title else "sub_menu"
        else:
            return "item"

    @property
    def callback(self):
        # NOTE: for backwards compatibility only (tests 0.14)
        return getattr(self.action, "callback", None)

    def __str__(self):
        if self.action:
            return f"action {self.action.title}"
        elif self.is_separator:
            return "separator"
        elif self.sub_menu:
            return self.sub_menu.title if self.sub_menu.title else "sub_menu"
        else:
            return "?item"


class Menu:

    def __init__(self, document_window, title, menu_id):
        self.document_window = document_window
        self.title = title
        self.menu_id = menu_id
        self.on_about_to_show = None
        self.on_about_to_hide = None
        self.__items = list()

    def close(self):
        for item in self.__items:
            item.close()
        self.__items = None
        self.document_window = None
        self.on_about_to_show = None
        self.on_about_to_hide = None

    def destroy(self):
        # for backwards compatibility
        if self.__items:
            self.close()

    @property
    def items(self) -> typing.Sequence[MenuItem]:
        return self.__items

    def get_menu_actions(self) -> typing.Sequence[MenuAction]:
        return [item.action for item in self.__items if item.action]

    def _register_ui_activity(self):
        self.document_window._register_ui_activity()

    def about_to_show(self):
        self._register_ui_activity()
        if self.on_about_to_show:
            self.on_about_to_show()

    def about_to_hide(self):
        self._register_ui_activity()
        if self.on_about_to_hide:
            self.on_about_to_hide()

    def _prepare_action(self, action, title, action_id, callback, key_sequence=None, role=None):
        # subclasses should call this to prepare a newly created action
        action.create(self.document_window, title, key_sequence, role)
        action.action_id = action_id
        action.on_triggered = callback
        action.on_ui_activity = self._register_ui_activity

    def add_menu_item(self, title: str, callback: typing.Callable[[], None], key_sequence: str = None, role: str = None, action_id: str = None) -> MenuAction:
        raise NotImplementedError()

    def add_action(self, action) -> None:
        raise NotImplementedError()

    def add_sub_menu(self, title, menu) -> None:
        raise NotImplementedError()

    def add_separator(self) -> None:
        raise NotImplementedError()

    def insert_menu_item(self, title, before_action: MenuAction, callback: typing.Callable[[], None], key_sequence: str = None, role: str = None, action_id: str = None) -> None:
        raise NotImplementedError()

    def insert_separator(self, before_action: MenuAction) -> None:
        raise NotImplementedError()

    def remove_action(self, action: MenuAction) -> None:
        raise NotImplementedError()

    def _item_added(self, *, action: MenuAction = None, is_separator: bool =False, sub_menu: "Menu" = None) -> None:
        # subclasses should call this when adding a menu item
        item = MenuItem(action=action, is_separator=is_separator, sub_menu=sub_menu)
        self.__items.append(item)
        self.document_window._menu_item_added(item)

    def _item_inserted(self, before_action: MenuAction, *, action: MenuAction = None, is_separator: bool =False, sub_menu: "Menu" = None) -> None:
        # subclasses should call this when adding a menu item
        index = 0
        for index, item in enumerate(self.__items):
            if before_action == item.action:
                break
        item = MenuItem(action=action, is_separator=is_separator, sub_menu=sub_menu)
        self.__items.insert(index, item)
        self.document_window._menu_item_added(item)

    def _item_removed(self, action: MenuAction) -> None:
        # subclasses should call this when inserting a menu.
        index = 0
        for index, item in enumerate(self.__items):
            if action == item.action:
                self.document_window._menu_item_removed(self.__items.pop(index))
                break

    def popup(self, gx, gy):
        raise NotImplementedError()


class DockWidget:

    def __init__(self, document_window: "Window", widget: Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str):
        self.document_window = document_window
        self.document_window.register_dock_widget(self)
        self.widget = widget
        self.widget._set_root_container(self)
        self.panel_id = panel_id
        self.title = title
        self.positions = positions
        self.position = position
        self.on_size_changed = None
        self.on_focus_changed = None
        self.on_ui_activity = None
        self.size = None

    def close(self):
        self.widget.close()
        self.widget = None
        self.document_window.unregister_dock_widget(self)
        self.document_window = None
        self.on_size_changed = None
        self.on_focus_changed = None
        self.on_ui_activity = None

    def _register_ui_activity(self):
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    @property
    def width(self) -> int:
        return self.size.width if self.size else 0

    @property
    def height(self) -> int:
        return self.size.height if self.size else 0

    def refocus_widget(self, widget):
        self.document_window.refocus_widget(widget)

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

    def clear_queued_tasks(self):
        self.document_window.clear_queued_tasks()

    def add_task(self, key, task):
        self.document_window.add_task(key + str(id(self)), task)

    def clear_task(self, key):
        self.document_window.clear_task(key + str(id(self)))

    def periodic(self):
        self.widget.periodic()

    @property
    def toggle_action(self) -> MenuAction:
        raise NotImplementedError()

    def show(self):
        self._register_ui_activity()

    def hide(self):
        self._register_ui_activity()

    def _handle_size_changed(self, size: Geometry.IntSize) -> None:
        self._register_ui_activity()
        self.size = size
        if callable(self.on_size_changed):
            self.on_size_changed(self.width, self.height)

    def _handle_focus_in(self) -> None:
        self._register_ui_activity()
        if callable(self.on_focus_changed):
            self.on_focus_changed(True)

    def _handle_focus_out(self) -> None:
        self._register_ui_activity()
        if callable(self.on_focus_changed):
            self.on_focus_changed(False)


class Window:

    def __init__(self, parent_window, title):
        self.parent_window = parent_window
        self.root_widget = None
        self.has_event_loop = True
        self.window_style = "window"
        self.__dock_widget_weak_refs = list()
        self.on_periodic = None
        self.on_queue_task = None
        self.on_clear_queued_tasks = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_key_pressed = None
        self.on_key_released = None
        self.on_activation_changed = None
        self.on_size_changed = None
        self.on_position_changed = None
        self.on_refocus_widget = None
        self.on_ui_activity = None
        self.pos_x = None
        self.pos_y = None
        self.width = None
        self.height = None
        self.__title = title if title is not None else str()
        self.__menus = list()
        self.__menu_map = dict()
        self.__menu_actions = dict()

    def close(self):
        # this is a callback and should not be invoked directly from Python;
        # call request_close instead.
        self.parent_window = None
        if self.root_widget:
            # care must be taken here that this method isn't somehow called while handling
            # the click in a widget. closing the root widget will destroy the widget hierarchy
            # which will potentially crash if the widget in the hierarchy triggered this call
            # directly. using request_close from a separate window will mitigate this.
            self.root_widget.close()
            self.root_widget = None
        for menu in reversed(self.__menus):
            menu.close()
        self.__menus = None
        self.__menu_map = None
        self.__menu_actions = None
        self.on_periodic = None
        self.on_queue_task = None
        self.on_clear_queued_tasks = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_key_pressed = None
        self.on_key_released = None
        self.on_activation_changed = None
        self.on_size_changed = None
        self.on_position_changed = None
        self.on_refocus_widget = None
        self.on_ui_activity = None

    def request_close(self):
        raise NotImplementedError()

    def _register_ui_activity(self):
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    # attach the root widget to this window
    # the root widget must respond to _set_root_container
    def attach(self, root_widget):
        self.root_widget = root_widget
        self.root_widget._set_root_container(self)
        self._attach_root_widget(root_widget)

    def _attach_root_widget(self, root_widget):
        raise NotImplementedError()

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

    def clear_queued_tasks(self):
        if self.on_clear_queued_tasks:
            self.on_clear_queued_tasks()

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
        raise NotImplementedError()

    def refocus_widget(self, widget):
        if callable(self.on_refocus_widget):
            self.on_refocus_widget(widget)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        raise NotImplementedError()

    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        raise NotImplementedError()

    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        raise NotImplementedError()

    def create_dock_widget(self, widget: Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> DockWidget:
        raise NotImplementedError()

    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        raise NotImplementedError()

    @property
    def screen_size(self) -> Geometry.IntSize:
        return self._get_screen_size()

    def _get_screen_size(self):
        raise NotImplementedError()

    @property
    def screen_logical_dpi(self) -> float:
        return self._get_screen_logical_dpi()

    def _get_screen_logical_dpi(self):
        raise NotImplementedError()

    @property
    def screen_physical_dpi(self) -> float:
        return self._get_screen_physical_dpi()

    def _get_screen_physical_dpi(self):
        raise NotImplementedError()

    @property
    def display_scaling(self) -> float:
        return self._get_display_scaling()

    def _get_display_scaling(self):
        raise NotImplementedError()

    # call show to display the window.
    def show(self, size=None, position=None):
        raise NotImplementedError()

    def fill_screen(self):
        raise NotImplementedError()

    @property
    def title(self):
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = value
        self._set_title(value)

    def _set_title(self, value):
        raise NotImplementedError()

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        raise NotImplementedError()

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        raise NotImplementedError()

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        raise NotImplementedError()

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

    def _handle_key_pressed(self, key) -> bool:
        if callable(self.on_key_pressed):
            return self.on_key_pressed(key)
        return False

    def _handle_key_released(self, key) -> bool:
        if callable(self.on_key_released):
            return self.on_key_released(key)
        return False

    def add_menu(self, title: str, menu_id: str = None) -> Menu:
        raise NotImplementedError()

    def insert_menu(self, title: str, before_menu: Menu, menu_id: str = None) -> Menu:
        raise NotImplementedError()

    def _menu_added(self, menu: Menu) -> None:
        # subclasses should call this when adding a menu
        self.__menus.append(menu)
        if menu.menu_id:
            self.__menu_map[menu.menu_id] = menu

    def _menu_inserted(self, menu: Menu, before_menu: Menu) -> None:
        # subclasses should call this when inserting a menu.
        self.__menus.insert(self.__menus.index(before_menu), menu)
        if menu.menu_id:
            self.__menu_map[menu.menu_id] = menu

    def _menu_item_added(self, item: MenuItem) -> None:
        if item.action and item.action.action_id:
            self.__menu_actions[item.action.action_id] = item.action

    def _menu_item_removed(self, item: MenuItem) -> None:
        if item.action and item.action.action_id:
            self.__menu_actions.pop(item.action.action_id)

    def get_menu_action(self, action_id: str) -> MenuAction:
        return self.__menu_actions.get(action_id)

    def get_menu_actions(self) -> typing.Sequence[MenuAction]:
        return self.__menu_actions.values()

    @property
    def menus(self) -> typing.List[Menu]:
        return self.__menus

    def get_menu(self, menu_id: str) -> typing.Optional[Menu]:
        return self.__menu_map.get(menu_id)

    def save(self) -> typing.Tuple[str, str]:
        raise NotImplementedError()

    def restore(self, geometry, state):
        raise NotImplementedError()

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

    @property
    def position(self) -> Geometry.IntPoint:
        raise NotImplementedError()

    @property
    def size(self) -> Geometry.IntSize:
        raise NotImplementedError()


class ToleranceType(enum.IntEnum):
    CURSOR = 1


class TruncateModeType(enum.IntEnum):
    LEFT = 0
    RIGHT = 1
    MIDDLE = 2
    NONE = 3


class UserInterface(abc.ABC):

    @abc.abstractmethod
    def close(self) -> None:
        ...

    # data objects

    @abc.abstractmethod
    def create_mime_data(self) -> MimeData:
        ...

    @abc.abstractmethod
    def create_item_model_controller(self, keys):
        ...

    @abc.abstractmethod
    def create_button_group(self):
        ...

    # window elements

    @abc.abstractmethod
    def create_document_window(self, title=None, parent_window: Window=None) -> Window:
        ...

    @abc.abstractmethod
    def destroy_document_window(self, document_window: Window) -> None:
        ...

    # user interface elements

    @abc.abstractmethod
    def create_row_widget(self, alignment=None, properties=None) -> BoxWidget:
        ...

    @abc.abstractmethod
    def create_column_widget(self, alignment=None, properties=None) -> BoxWidget:
        ...

    @abc.abstractmethod
    def create_splitter_widget(self, orientation="vertical", properties=None) -> SplitterWidget:
        ...

    @abc.abstractmethod
    def create_tab_widget(self, properties=None) -> TabWidget:
        ...

    @abc.abstractmethod
    def create_stack_widget(self, properties=None) -> StackWidget:
        ...

    @abc.abstractmethod
    def create_group_widget(self, properties=None) -> GroupWidget:
        ...

    @abc.abstractmethod
    def create_scroll_area_widget(self, properties=None) -> ScrollAreaWidget:
        ...

    @abc.abstractmethod
    def create_combo_box_widget(self, items=None, item_getter=None, properties=None) -> ComboBoxWidget:
        ...

    @abc.abstractmethod
    def create_push_button_widget(self, text: str=None, properties=None) -> PushButtonWidget:
        ...

    @abc.abstractmethod
    def create_radio_button_widget(self, text: str=None, properties=None) -> RadioButtonWidget:
        ...

    @abc.abstractmethod
    def create_check_box_widget(self, text=None, properties=None) -> CheckBoxWidget:
        ...

    @abc.abstractmethod
    def create_label_widget(self, text: str=None, properties=None) -> LabelWidget:
        ...

    @abc.abstractmethod
    def create_slider_widget(self, properties=None) -> SliderWidget:
        ...

    @abc.abstractmethod
    def create_progress_bar_widget(self, properties=None) -> ProgressBarWidget:
        ...

    @abc.abstractmethod
    def create_line_edit_widget(self, properties=None) -> LineEditWidget:
        ...

    @abc.abstractmethod
    def create_text_edit_widget(self, properties=None) -> TextEditWidget:
        ...

    @abc.abstractmethod
    def create_canvas_widget(self, properties=None, *, layout_render: str = None) -> CanvasWidget:
        ...

    @abc.abstractmethod
    def create_tree_widget(self, properties=None) -> TreeWidget:
        ...

    # file i/o

    @abc.abstractmethod
    def load_rgba_data_from_file(self, filename):
        ...

    @abc.abstractmethod
    def save_rgba_data_to_file(self, data, filename, format):
        ...

    @abc.abstractmethod
    def get_existing_directory_dialog(self, title: str, directory: str) -> typing.Tuple[str, str]:
        ...

    @abc.abstractmethod
    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        ...

    @abc.abstractmethod
    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        ...

    @abc.abstractmethod
    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        ...

    # persistence (associated with application)

    @abc.abstractmethod
    def get_data_location(self) -> str:
        ...

    @abc.abstractmethod
    def get_document_location(self) -> str:
        ...

    @abc.abstractmethod
    def get_temporary_location(self) -> str:
        ...

    @abc.abstractmethod
    def get_persistent_string(self, key: str, default_value: str=None) -> str:
        ...

    @abc.abstractmethod
    def set_persistent_string(self, key: str, value: str) -> None:
        ...

    @abc.abstractmethod
    def get_persistent_object(self, key: str, default_value: typing.Any=None) -> typing.Any:
        ...

    @abc.abstractmethod
    def set_persistent_object(self, key: str, value: typing.Any) -> None:
        ...

    @abc.abstractmethod
    def remove_persistent_key(self, key: str) -> None:
        ...

    # clipboard

    @abc.abstractmethod
    def clipboard_clear(self) -> None:
        ...

    @abc.abstractmethod
    def clipboard_mime_data(self) -> MimeData:
        ...

    @abc.abstractmethod
    def clipboard_set_mime_data(self, mime_data: MimeData) -> None:
        ...

    @abc.abstractmethod
    def clipboard_set_text(self, text: str) -> None:
        ...

    @abc.abstractmethod
    def clipboard_text(self) -> str:
        ...

    # misc

    @abc.abstractmethod
    def create_rgba_image(self, drawing_context, width, height):
        ...

    @abc.abstractmethod
    def get_font_metrics(self, font: str, text: str) -> FontMetrics:
        ...

    @abc.abstractmethod
    def truncate_string_to_width(self, font_str: str, text: str, pixel_width: int, mode: TruncateModeType) -> str:
        ...

    @abc.abstractmethod
    def get_qt_version(self) -> str:
        ...

    @abc.abstractmethod
    def get_tolerance(self, tolerance_type: ToleranceType) -> float:
        ...

    @abc.abstractmethod
    def create_context_menu(self, document_window: Window) -> Menu:
        ...

    @abc.abstractmethod
    def create_sub_menu(self, document_window: Window, title: str = None, menu_id: str = None) -> Menu:
        ...
