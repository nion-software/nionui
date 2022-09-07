"""
Provides a user interface object that can render to an Qt host.
"""
from __future__ import annotations

# standard libraries
import abc
import asyncio
import collections
import concurrent.futures
import copy
import enum
import functools
import logging
import numbers
import operator
import pathlib
import threading
import typing
import weakref

# third party libraries
import numpy

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.utils import Binding
from nion.utils import Converter
from nion.utils import Geometry
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import Application
    from nion.ui import Window as WindowModule


def notnone(s: typing.Any) -> str:
    return str(s) if s is not None else str()


FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])

MenuItemState = collections.namedtuple("MenuItemState", ["title", "enabled", "checked"])


class KeyboardModifiers(typing.Protocol):

    def __str__(self) -> str:
        return "shift:{} control:{} alt:{} option:{} meta:{}".format(self.shift, self.control, self.alt, self.option, self.meta)

    @property
    def any_modifier(self) -> bool:
        return self.shift or self.control or self.alt or self.meta

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


class Key(typing.Protocol):

    @property
    @abc.abstractmethod
    def text(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def key(self) -> int:
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

    @property
    def key_sequence_str(self) -> str:
        # the composite key strokes are not allowed to have modifiers.
        # these are move_to_start_of_line, move_to_end_of_line, delete_to_end_of_line
        # also, they take precedence and are checked first.
        if self.is_move_to_start_of_line:
            return "move_to_start_of_line"
        elif self.is_move_to_end_of_line:
            return "move_to_end_of_line"
        elif self.is_delete_to_end_of_line:
            return "delete_to_end_of_line"

        # check the named keys
        if self.is_delete:
            ks = "delete"
        elif self.is_enter_or_return:
            ks = "enter"
        elif self.is_escape:
            ks = "esc"
        elif self.is_tab:
            ks = "tab"
        elif self.is_insert:
            ks = "insert"
        elif self.is_home:
            ks = "home"
        elif self.is_end:
            ks = "end"
        elif self.is_left_arrow:
            ks = "left_arrow"
        elif self.is_up_arrow:
            ks = "up_arrow"
        elif self.is_right_arrow:
            ks = "right_arrow"
        elif self.is_down_arrow:
            ks = "down_arrow"
        elif self.is_page_up:
            ks = "page_up"
        elif self.is_page_down:
            ks = "page_down"
        else:
            ks = self.text if self.text else "none"

        # add the modifiers. order is Ctrl+Alt+Shift+<key>
        if self.modifiers.shift:
            ks = "Shift+" + ks
        if self.modifiers.alt:
            ks = "Alt+" + ks
        if self.modifiers.control:
            ks = "Ctrl+" + ks

        return ks


class KeySequenceMatch(enum.Enum):
    NONE = 0
    PARTIAL = 1
    EXACT = 2


class KeySequence:
    def __init__(self, key_sequence_str: str):
        self.key_sequence_str = key_sequence_str

    def matches(self, key: Key) -> KeySequenceMatch:
        if key.key_sequence_str == self.key_sequence_str:
            return KeySequenceMatch.EXACT
        else:
            return KeySequenceMatch.NONE


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
    def has_file_paths(self) -> bool:
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


T = typing.TypeVar('T')

class BindablePropertyHelper(typing.Generic[T]):
    def __init__(self,
                 value_getter: typing.Optional[typing.Callable[[], T]],
                 value_setter: typing.Callable[[T], None],
                 value_validator: typing.Optional[typing.Callable[[T, T], T]] = None,
                 value_cmp: typing.Optional[typing.Callable[[T, T], bool]] = None) -> None:
        self.__value_initialized = False
        self.__value = typing.cast(T, None)
        self.__pending_value = typing.cast(T, None)
        self.__value_getter = value_getter
        self.__value_setter = value_setter
        self.__value_validator = value_validator if callable(value_validator) else lambda x, y: x
        self.__value_cmp = value_cmp if callable(value_cmp) else typing.cast(typing.Callable[[T, T], bool], operator.eq)
        self.__binding: typing.Optional[Binding.Binding] = None
        self.__task: typing.Optional[asyncio.Task[None]] = None
        self.__future: typing.Optional[concurrent.futures.Future[None]] = None

        def finalize(task: typing.Optional[asyncio.Task[None]], future: typing.Optional[concurrent.futures.Future[None]]) -> None:
            if task:
                task.cancel()
            if future:
                future.cancel()

        weakref.finalize(self, finalize, self.__task, self.__future)

    def close(self) -> None:
        if self.__task:
            self.__task.cancel()
            self.__task = None
        if self.__future:
            self.__future.cancel()
            self.__future = None

    @property
    def value(self) -> T:
        return self.__value_getter() if callable(self.__value_getter) else self.__value

    @value.setter
    def value(self, value: T) -> None:
        # when the high level user interface element changes programmatically, this method
        # should be called with the new value. it updates the low level and the binding.
        validated_value = self.__value_validator(value, self.__value)
        if not self.__value_initialized or not self.__value_cmp(validated_value, self.__value):
            self.__value_initialized = True
            self.__value = validated_value
            self.__value_setter(validated_value)
            if self.__binding:
                self.__binding.update_source(validated_value)

    def set_value(self, value: T) -> None:
        # when the binding source changes, this method should be called with the new value.
        # it updates the low level, but does not update the binding.
        validated_value = self.__value_validator(value, self.__value)
        if not self.__value_initialized or not self.__value_cmp(validated_value, self.__value):
            self.__value_initialized = True
            self.__value = validated_value
            self.__value_setter(validated_value)

    def value_changed(self, value: T) -> None:
        # when the target value changes due to a user action, this method
        # should be called with the new value. it updates the binding, but does
        # not update the low level.
        validated_value = self.__value_validator(value, self.__value)
        self.__value_initialized = True
        self.__value = validated_value
        if self.__binding:
            self.__binding.update_source(validated_value)

    # bind to value. takes ownership of binding.
    def bind_value(self, binding: Binding.Binding) -> None:
        # close the old binding
        if self.__binding:
            self.__binding.close()
            self.__binding = None

        # grab the initial value from the binding. use str method to convert value to text.
        self.value = typing.cast(T, binding.get_target_value())

        # save the binding and configure the target setter
        # which will set the text when the binding changes
        self.__binding = binding

        async def update_value_inner(bph: typing.Any) -> None:
            try:
                self_ = typing.cast(typing.Optional[BindablePropertyHelper[T]], bph())
                if self_:
                    try:
                        self_.set_value(self_.__pending_value)
                    finally:
                        self_.__task = None
                        self_.__future = None
            except Exception as e:
                import traceback
                traceback.print_exc()
                logging.debug(e)

        def update_value(bph: typing.Any, event_loop: asyncio.AbstractEventLoop, thread: threading.Thread, value: T) -> None:
            # to avoid repeated cancel/new-task situations that starve the execution during tests,
            # update the pending value and only create a new task if required.
            self_ = typing.cast(typing.Optional[BindablePropertyHelper[T]], bph())
            if self_:
                self_.__pending_value = value
                if threading.current_thread() != thread:
                    if not self_.__future:
                        self_.__future = asyncio.run_coroutine_threadsafe(update_value_inner(bph), event_loop)
                else:
                    if not self_.__task:
                        self_.__task = event_loop.create_task(update_value_inner(bph))

        self.__binding.target_setter = functools.partial(update_value, weakref.ref(self), asyncio.get_event_loop_policy().get_event_loop(), threading.current_thread())

    def unbind_value(self) -> None:
        if self.__binding:
            self.__binding.close()
            self.__binding = None


class WidgetBehavior(typing.Protocol):
    # note: behaviors are generally responsible for closing widgets that get added to them.
    # this is so behaviors which insert added widgets into another widget get closed in a
    # predictable manner (i.e. when the enclosing widget gets closed).

    focused: bool
    does_retain_focus: bool
    visible: bool
    enabled: bool
    size: Geometry.IntSize
    tool_tip: typing.Optional[str]
    on_ui_activity: typing.Optional[typing.Callable[[], None]]
    on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]]
    on_focus_changed: typing.Optional[typing.Callable[[bool], None]]

    # low level UI specific widget
    @property
    def widget(self) -> typing.Any: raise NotImplementedError()

    def close(self) -> None: ...
    def periodic(self) -> None: pass
    def _set_root_container(self, window: typing.Optional[WindowModule.Window]) -> None: ...
    def _get_content_widget(self) -> typing.Optional[Widget]: return None
    def set_property(self, key: str, value: typing.Any) -> None: ...
    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint: ...
    def drag(self, mime_data: MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None: ...
    def set_background_color(self, value: typing.Optional[str]) -> None: ...


class Widget:

    def __init__(self, widget_behavior: WidgetBehavior) -> None:
        self.__behavior = widget_behavior
        self.__behavior.on_ui_activity = self._register_ui_activity
        self.__root_container: typing.Optional[WindowModule.Window] = None  # the document window
        self.__pending_keyed_tasks: typing.List[typing.Tuple[str, typing.Callable[[], None]]] = list()
        self.__pending_queued_tasks: typing.List[typing.Callable[[], None]] = list()
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.widget_id: typing.Optional[str] = None

        def handle_context_menu_event(x: int, y: int, gx: int, gy: int) -> bool:
            if callable(self.on_context_menu_event):
                return self.on_context_menu_event(x, y, gx, gy)
            return False

        def handle_focus_changed(focused: bool) -> None:
            if callable(self.on_focus_changed):
                self.on_focus_changed(focused)

        self._behavior.on_context_menu_event = handle_context_menu_event
        self._behavior.on_focus_changed = handle_focus_changed

        def set_visible(value: bool) -> None:
            self._behavior.visible = value

        def set_enabled(value: bool) -> None:
            self._behavior.enabled = value

        def set_tool_tip(value: typing.Optional[str]) -> None:
            self._behavior.tool_tip = value

        def set_background_color(value: typing.Optional[str]) -> None:
            self._behavior.set_background_color(str(value) if value is not None else None)

        self.__visible_binding_helper = BindablePropertyHelper[bool](None, set_visible)
        self.__enabled_binding_helper = BindablePropertyHelper[bool](None, set_enabled)
        self.__tool_tip_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_tool_tip)
        self.__background_color_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_background_color)

        self.visible = True
        self.enabled = True
        self.tool_tip = None

    def close(self) -> None:
        self.__visible_binding_helper.close()
        self.__visible_binding_helper = typing.cast(typing.Any, None)
        self.__enabled_binding_helper.close()
        self.__enabled_binding_helper = typing.cast(typing.Any, None)
        self.__tool_tip_binding_helper.close()
        self.__tool_tip_binding_helper = typing.cast(typing.Any, None)
        self.__background_color_binding_helper.close()
        self.__background_color_binding_helper = typing.cast(typing.Any, None)
        content_widget = self._behavior._get_content_widget()
        if content_widget:
            content_widget.close()
        self.__behavior.close()
        self.__behavior = typing.cast(typing.Any, None)
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.__root_container = None

    @property
    def _behavior(self) -> WidgetBehavior:
        return self.__behavior

    @property
    def root_container(self) -> typing.Optional[WindowModule.Window]:
        return self.__root_container

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
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

    def _register_ui_activity(self) -> None:
        if self.__root_container:
            self.__root_container._register_ui_activity()

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        content_widget = self._behavior._get_content_widget()
        return [content_widget] if content_widget else list()

    @property
    def content_widget(self) -> Widget:
        # this is a compromise method for backwards compatibility for code expecting the widgets to be
        # based on CompositeWidgetBase.
        content_widget = self._behavior._get_content_widget()
        assert content_widget
        return content_widget

    def find_widget_by_id(self, widget_id: str) -> typing.Optional[Widget]:
        if self.widget_id == widget_id:
            return self
        for contained_widget in self._contained_widgets:
            found_widget = contained_widget.find_widget_by_id(widget_id)
            if found_widget:
                return found_widget
        return None

    # not thread safe
    def periodic(self) -> None:
        self._behavior.periodic()

    def run_pending_keyed_tasks(self) -> None:
        # used for testing
        pending_keyed_tasks = copy.copy(self.__pending_keyed_tasks)
        self.__pending_keyed_tasks.clear()
        for key, task in pending_keyed_tasks:
            if callable(task):
                task()

    @property
    def pending_keyed_tasks(self) -> typing.List[typing.Tuple[str, typing.Callable[[], None]]]:
        # used for testing
        return copy.copy(self.__pending_keyed_tasks)

    @property
    def pending_queued_tasks(self) -> typing.List[typing.Callable[[], None]]:
        # used for testing
        return copy.copy(self.__pending_queued_tasks)

    # thread safe
    # tasks are run periodically. if another task causes a widget to close,
    # the outstanding task may try to use a closed widget. any methods called
    # in a task need to verify that the widget is not yet closed. this can be
    # mitigated in several ways: 1) clear the task if possible; 2) do not queue
    # the task if widget is already closed; 3) check during task to make sure
    # widget was not already closed.
    def add_task(self, key: str, task: typing.Callable[[], None]) -> None:
        root_container = self.root_container
        if root_container:
            root_container.add_task(key + str(id(self)), task)
        else:
            self.__pending_keyed_tasks.append((key, task))

    # thread safe
    def clear_task(self, key: str) -> None:
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
    def queue_task(self, task: typing.Callable[[], None]) -> None:
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
        return self.__visible_binding_helper.value

    @visible.setter
    def visible(self, visible: bool) -> None:
        self.__visible_binding_helper.value = visible

    @property
    def enabled(self) -> bool:
        return self.__enabled_binding_helper.value

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self.__enabled_binding_helper.value = enabled

    @property
    def size(self) -> Geometry.IntSize:
        return self._behavior.size

    @size.setter
    def size(self, size: Geometry.IntSize) -> None:
        self._behavior.size = size

    @property
    def tool_tip(self) -> typing.Optional[str]:
        return self.__tool_tip_binding_helper.value

    @tool_tip.setter
    def tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.__tool_tip_binding_helper.value = tool_tip

    @property
    def background_color(self) -> typing.Optional[str]:
        return self.__background_color_binding_helper.value

    @background_color.setter
    def background_color(self, value: typing.Optional[str]) -> None:
        self.__background_color_binding_helper.value = value

    def set_property(self, key: str, value: typing.Any) -> None:
        self._behavior.set_property(key, value)

    def drag(self, mime_data: MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self._behavior.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return self._behavior.map_to_global(p)

    def _dispatch_any(self, method: str, *args: typing.Any, **kwargs: typing.Any) -> bool:
        if hasattr(self, method):
            return typing.cast(bool, getattr(self, method)(*args, **kwargs))
        return False

    def _can_dispatch_any(self, method: str) -> bool:
        return False

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[MenuItemState]:
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = typing.cast(typing.Optional[MenuItemState], getattr(self, menu_item_state_method)())
            if menu_item_state:
                return menu_item_state
        if hasattr(self, handle_method):
            return MenuItemState(title=None, enabled=True, checked=False)
        return None

    def bind_enabled(self, binding: Binding.Binding) -> None:
        self.__enabled_binding_helper.bind_value(binding)

    def unbind_enabled(self) -> None:
        self.__enabled_binding_helper.unbind_value()

    def bind_visible(self, binding: Binding.Binding) -> None:
        self.__visible_binding_helper.bind_value(binding)

    def unbind_visible(self) -> None:
        self.__visible_binding_helper.unbind_value()

    def bind_tool_tip(self, binding: Binding.Binding) -> None:
        self.__tool_tip_binding_helper.bind_value(binding)

    def unbind_tool_tip(self) -> None:
        self.__tool_tip_binding_helper.unbind_value()

    def bind_background_color(self, binding: Binding.Binding) -> None:
        self.__background_color_binding_helper.bind_value(binding)

    def unbind_background_color(self) -> None:
        self.__background_color_binding_helper.unbind_value()


class BoxWidgetBehavior(WidgetBehavior, typing.Protocol):
    def insert(self, child: Widget, before: int, fill: bool, alignment: typing.Optional[str]) -> None: ...
    def remove_all(self) -> None: ...
    def add_stretch(self) -> Widget: ...
    def add_spacing(self, spacing: int) -> Widget: ...


class BoxWidget(Widget):

    def __init__(self, widget_behavior: BoxWidgetBehavior, alignment: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)
        self.alignment = alignment
        self.children: typing.List[Widget] = []

    def close(self) -> None:
        for child in self.children:
            child.close()
        self.children = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> BoxWidgetBehavior:
        return typing.cast(BoxWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + copy.copy(self.children)

    def periodic(self) -> None:
        super().periodic()
        for child in self.children:
            child.periodic()

    @property
    def child_count(self) -> int:
        return len(self.children)

    def index(self, child: Widget) -> int:
        assert child in self.children
        return self.children.index(child)

    def insert(self, child: Widget, before: typing.Optional[typing.Union[Widget, int]], fill: bool = False, alignment: typing.Optional[str] = None) -> None:
        assert child
        if isinstance(before, numbers.Integral):
            index = before
        elif isinstance(before, Widget):
            index = self.index(before)
        else:
            index = self.child_count
        if alignment is None:
            alignment = self.alignment
        self.children.insert(index, child)
        child._set_root_container(self.root_container)
        self._behavior.insert(child, index, fill, alignment)

    def add(self, child: Widget, fill: bool = False, alignment: typing.Optional[str] = None) -> None:
        self.insert(child, None, fill, alignment)

    def remove(self, child: typing.Union[Widget, int]) -> None:
        child_widget = child if isinstance(child, Widget) else self.children[int(child)]
        child_widget._set_root_container(None)
        self.children.remove(child_widget)
        # closing the child should remove it from the layout
        child_widget.close()

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


class SplitterWidgetBehavior(WidgetBehavior, typing.Protocol):
    orientation: typing.Optional[str]
    def add(self, child: Widget) -> None: ...
    def restore_state(self, tag: str) -> None: ...
    def save_state(self, tag: str) -> None: ...
    def set_sizes(self, sizes: typing.Sequence[int]) -> None: ...


class SplitterWidget(Widget):

    def __init__(self, widget_behavior: WidgetBehavior, orientation: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)
        self.children: typing.List[Widget] = []
        self.orientation = orientation

    def close(self) -> None:
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self.children = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> SplitterWidgetBehavior:
        return typing.cast(SplitterWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + copy.copy(self.children)

    def periodic(self) -> None:
        super().periodic()
        for child in self.children:
            child.periodic()

    @property
    def orientation(self) -> typing.Optional[str]:
        return self._behavior.orientation

    @orientation.setter
    def orientation(self, value: typing.Optional[str]) -> None:
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


class TabWidgetBehavior(WidgetBehavior, typing.Protocol):
    current_index: int
    on_current_index_changed: typing.Optional[typing.Callable[[int], None]]

    def add(self, child: Widget, label: str) -> None: ...
    def restore_state(self, tag: str) -> None: ...
    def save_state(self, tag: str) -> None: ...


class TabWidget(Widget):

    def __init__(self, widget_behavior: TabWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.children: typing.List[Widget] = []
        self.on_current_index_changed: typing.Optional[typing.Callable[[int], None]] = None

        def handle_current_index_changed(index: int) -> None:
            self.__current_index_binding_helper.value_changed(index)
            if callable(self.on_current_index_changed):
                self.on_current_index_changed(index)

        self._behavior.on_current_index_changed = handle_current_index_changed

        def set_current_index(value: int) -> None:
            self._behavior.current_index = value

        self.__current_index_binding_helper = BindablePropertyHelper[int](None, set_current_index)

        self.current_index = 0

    def close(self) -> None:
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self.children = typing.cast(typing.Any, None)
        self.__current_index_binding_helper.close()
        self.__current_index_binding_helper = typing.cast(typing.Any, None)
        self.on_current_index_changed = None
        super().close()

    @property
    def _behavior(self) -> TabWidgetBehavior:
        return typing.cast(TabWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + copy.copy(self.children)

    def periodic(self) -> None:
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
    def current_index(self) -> int:
        return self.__current_index_binding_helper.value

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index_binding_helper.value = index

    def bind_current_index(self, binding: Binding.Binding) -> None:
        self.__current_index_binding_helper.bind_value(binding)

    def unbind_current_index(self) -> None:
        self.__current_index_binding_helper.unbind_value()


class StackWidgetBehavior(WidgetBehavior, typing.Protocol):
    current_index: int

    def insert(self, child: Widget, before: int) -> None: ...
    def remove(self, child: Widget) -> None: ...


class StackWidget(Widget):

    def __init__(self, widget_behavior: StackWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.children: typing.List[Widget] = []

        def set_current_index(value: int) -> None:
            self._behavior.current_index = value

        self.__current_index_binding_helper = BindablePropertyHelper[int](None, set_current_index)

        self.current_index = 0

    def close(self) -> None:
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self.children = typing.cast(typing.Any, None)
        self.__current_index_binding_helper.close()
        self.__current_index_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> StackWidgetBehavior:
        return typing.cast(StackWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + copy.copy(self.children)

    def periodic(self) -> None:
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
        elif isinstance(before, Widget):
            index = self.index(before)
        else:
            index = self.child_count
        self._behavior.insert(child, index)
        self.children.insert(index, child)
        child._set_root_container(self.root_container)

    def add(self, child: Widget) -> None:
        self.insert(child, None)

    def remove(self, child: typing.Union[Widget, int]) -> None:
        child_widget = child if isinstance(child, Widget) else self.children[int(child)]
        child_widget._set_root_container(None)
        self.children.remove(child_widget)
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self._behavior.remove(child_widget)

    def remove_all(self) -> None:
        while len(self.children) > 0:
            self.remove(self.children[-1])

    @property
    def current_index(self) -> int:
        return self.__current_index_binding_helper.value

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index_binding_helper.value = index

    def bind_current_index(self, binding: Binding.Binding) -> None:
        self.__current_index_binding_helper.bind_value(binding)

    def unbind_current_index(self) -> None:
        self.__current_index_binding_helper.unbind_value()


class GroupWidgetBehavior(WidgetBehavior, typing.Protocol):
    title: typing.Optional[str]

    def add(self, child: Widget) -> None: ...
    def remove(self, child: Widget) -> None: ...


class GroupWidget(Widget):

    def __init__(self, widget_behavior: GroupWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.children: typing.List[Widget] = []
        self.__title: typing.Optional[str] = None

    def close(self) -> None:
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self.children = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> GroupWidgetBehavior:
        return typing.cast(GroupWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        for child in self.children:
            child._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + copy.copy(self.children)

    def periodic(self) -> None:
        super().periodic()
        for child in self.children:
            child.periodic()

    def add(self, child: Widget) -> None:
        self._behavior.add(child)
        self.children.append(child)
        child._set_root_container(self.root_container)

    def remove(self, child: Widget) -> None:
        child._set_root_container(None)
        self.children.remove(child)
        # note: behavior is responsible for closing the children so that behavior can put children in another widget.
        self._behavior.remove(child)

    def remove_all(self) -> None:
        while len(self.children) > 0:
            self.remove(self.children[-1])

    @property
    def title(self) -> typing.Optional[str]:
        return self.__title

    @title.setter
    def title(self, value: typing.Optional[str]) -> None:
        self.__title = value
        self._behavior.title = value


class ScrollAreaWidgetBehavior(WidgetBehavior, typing.Protocol):
    on_size_changed: typing.Optional[typing.Callable[[int, int], None]]
    on_viewport_changed: typing.Optional[typing.Callable[[Geometry.RectIntTuple], None]]

    def set_content(self, content: typing.Optional[Widget]) -> None: ...
    def scroll_to(self, x: int, y: int) -> None: ...
    def set_scrollbar_policies(self, horizontal_policy: str, vertical_policy: str) -> None: ...
    def info(self) -> None: ...


class ScrollAreaWidget(Widget):

    def __init__(self, widget_behavior: ScrollAreaWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.__content: typing.Optional[Widget] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_viewport_changed: typing.Optional[typing.Callable[[Geometry.IntRect], None]] = None
        self.viewport: Geometry.IntRect = Geometry.IntRect.empty_rect()
        self.width = 0
        self.height = 0

        def handle_size_changed(width: int, height: int) -> None:
            self.width = width
            self.height = height
            if callable(self.on_size_changed):
                self.on_size_changed(width, height)

        self._behavior.on_size_changed = handle_size_changed

        def handle_viewport_changed(viewport: Geometry.RectIntTuple) -> None:
            self.viewport = Geometry.IntRect.make(viewport)
            if callable(self.on_viewport_changed):
                self.on_viewport_changed(self.viewport)

        self._behavior.on_viewport_changed = handle_viewport_changed

    def close(self) -> None:
        if self.__content:
            self.__content.close()
            self.__content = None
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    @property
    def _behavior(self) -> ScrollAreaWidgetBehavior:
        return typing.cast(ScrollAreaWidgetBehavior, super()._behavior)

    def _set_root_container(self, root_container: typing.Optional[WindowModule.Window]) -> None:
        super()._set_root_container(root_container)
        if self.__content:
            self.__content._set_root_container(root_container)

    @property
    def _contained_widgets(self) -> typing.List[Widget]:
        return super()._contained_widgets + ([self.__content] if self.__content else list())

    def periodic(self) -> None:
        super().periodic()
        if self.__content:
            self.__content.periodic()

    @property
    def content(self) -> typing.Optional[Widget]:
        return self.__content

    @content.setter
    def content(self, content: typing.Optional[Widget]) -> None:
        self._behavior.set_content(content)
        self.__content = content
        if self.__content:
            self.__content._set_root_container(self.root_container)

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass

    def scroll_to(self, x: int, y: int) -> None:
        self._behavior.scroll_to(x, y)

    def set_scrollbar_policies(self, horizontal_policy: str, vertical_policy: str) -> None:
        self._behavior.set_scrollbar_policies(horizontal_policy, vertical_policy)

    def info(self) -> None:
        self._behavior.info()


class ComboBoxWidgetBehavior(WidgetBehavior, typing.Protocol):
    current_text: str
    on_current_text_changed: typing.Optional[typing.Callable[[str], None]]

    def set_item_strings(self, strings: typing.Sequence[str]) -> None: ...



class ComboBoxWidget(Widget):

    def __init__(self, widget_behavior: ComboBoxWidgetBehavior, items: typing.Sequence[typing.Any], item_getter: typing.Callable[[typing.Any], str]) -> None:
        super().__init__(widget_behavior)
        self.on_items_changed : typing.Optional[typing.Callable[[typing.Sequence[typing.Any]], None]] = None
        self.on_current_text_changed : typing.Optional[typing.Callable[[str], None]]= None
        self.on_current_item_changed : typing.Optional[typing.Callable[[typing.Any], None]] = None
        self.on_current_index_changed : typing.Optional[typing.Callable[[typing.Optional[int]], None]] = None
        self.item_getter = item_getter
        self.__items_binding: typing.Optional[Binding.Binding] = None

        def handle_current_text_changed(text: str) -> None:
            self.__current_index_binding_helper.value_changed(self.current_index)
            if callable(self.on_current_text_changed):
                self.on_current_text_changed(text)
            if callable(self.on_current_item_changed):
                self.on_current_item_changed(self.current_item)
            if callable(self.on_current_index_changed):
                self.on_current_index_changed(self.current_index)

        self._behavior.on_current_text_changed = handle_current_text_changed

        def set_items(items: typing.Sequence[typing.Any]) -> None:
            current_index = self.current_index
            item_strings = list()
            for item in items:
                item_string = notnone(self.item_getter(item) if self.item_getter else item)
                item_strings.append(item_string)
            self._behavior.set_item_strings(item_strings)
            if callable(self.on_items_changed):
                self.on_items_changed(self.__items)
            self.current_index = current_index

        def set_current_index(value: typing.Optional[int]) -> None:
            self.current_item = self.items[value] if value is not None else None

        def validate_current_index(new_value: typing.Optional[int], old_value: typing.Optional[int]) -> typing.Optional[int]:
            return new_value if new_value is not None and new_value >= 0 and new_value < len(self.items) else None

        self.__current_index_binding_helper = BindablePropertyHelper[typing.Optional[int]](None, set_current_index, validate_current_index)
        self.__items_binding_helper = BindablePropertyHelper[typing.Sequence[typing.Any]](None, set_items)

        self.items = list(items) if items else list()
        self.current_index = 0

    def close(self) -> None:
        self.__current_index_binding_helper.close()
        self.__current_index_binding_helper = typing.cast(typing.Any, None)
        self.__items_binding_helper.close()
        self.__items_binding_helper = typing.cast(typing.Any, None)
        self.item_getter = typing.cast(typing.Any, None)
        self.__items = typing.cast(typing.Any, None)
        self.on_items_changed = None
        self.on_current_text_changed = None
        self.on_current_item_changed = None
        self.on_current_index_changed = None
        super().close()

    @property
    def _behavior(self) -> ComboBoxWidgetBehavior:
        return typing.cast(ComboBoxWidgetBehavior, super()._behavior)

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
    def current_index(self) -> typing.Optional[int]:
        current_item = self.current_item
        return self.items.index(current_item) if current_item in self.items else None

    @current_index.setter
    def current_index(self, value: typing.Optional[int]) -> None:
        self.__current_index_binding_helper.value = value

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return self.__items_binding_helper.value

    @items.setter
    def items(self, items: typing.Sequence[typing.Any]) -> None:
        self.__items_binding_helper.value = items

    def bind_items(self, binding: Binding.Binding) -> None:
        self.__items_binding_helper.bind_value(binding)

    def unbind_items(self) -> None:
        self.__items_binding_helper.unbind_value()

    def bind_current_index(self, binding: Binding.Binding) -> None:
        self.__current_index_binding_helper.bind_value(binding)

    def unbind_current_index(self) -> None:
        self.__current_index_binding_helper.unbind_value()


class PushButtonWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    icon: typing.Optional[DrawingContext.RGBA32Type]
    on_clicked: typing.Optional[typing.Callable[[], None]]


class PushButtonWidget(Widget):

    def __init__(self, widget_behavior: PushButtonWidgetBehavior, text: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

        def handle_clicked() -> None:
            if callable(self.on_clicked):
                self.on_clicked()

        self._behavior.on_clicked = handle_clicked

        def set_text(value: typing.Optional[str]) -> None:
            self._behavior.text = str(value) if value is not None else None

        def set_icon(value: typing.Optional[DrawingContext.RGBA32Type]) -> None:
            self._behavior.icon = value

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)
        self.__icon_binding_helper = BindablePropertyHelper[typing.Optional[DrawingContext.RGBA32Type]](None, set_icon, None, typing.cast(typing.Any, numpy.array_equal))

        self.text = text
        self.icon = None

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
        self.__icon_binding_helper.close()
        self.__icon_binding_helper = typing.cast(typing.Any, None)
        self.on_clicked = None
        super().close()

    @property
    def _behavior(self) -> PushButtonWidgetBehavior:
        return typing.cast(PushButtonWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def icon(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__icon_binding_helper.value

    @icon.setter
    def icon(self, rgba_image: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__icon_binding_helper.value = rgba_image

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()

    def bind_icon(self, binding: Binding.Binding) -> None:
        self.__icon_binding_helper.bind_value(binding)

    def unbind_icon(self) -> None:
        self.__icon_binding_helper.unbind_value()


class RadioButtonWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    icon: typing.Optional[DrawingContext.RGBA32Type]
    checked: bool
    on_clicked: typing.Optional[typing.Callable[[], None]]


class RadioButtonWidget(Widget):

    def __init__(self, widget_behavior: RadioButtonWidgetBehavior, text: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None
        self.__value: typing.Optional[int] = None

        def set_text(value: typing.Optional[str]) -> None:
            self._behavior.text = str(value) if value is not None else None

        def set_icon(value: typing.Optional[DrawingContext.RGBA32Type]) -> None:
            self._behavior.icon = value

        def set_group_value(group_value: typing.Optional[int]) -> None:
            self.checked = group_value == self.__value

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)
        self.__icon_binding_helper = BindablePropertyHelper[typing.Optional[DrawingContext.RGBA32Type]](None, set_icon, None, typing.cast(typing.Any, numpy.array_equal))
        self.__group_value_binding_helper = BindablePropertyHelper[typing.Optional[typing.Optional[int]]](None, set_group_value)

        def handle_clicked() -> None:
            if self.__value is not None:
                self.group_value = self.__value
            if callable(self.on_clicked):
                self.on_clicked()

        self._behavior.on_clicked = handle_clicked

        self.text = text
        self.icon = None
        self.group_value = None

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
        self.__icon_binding_helper.close()
        self.__icon_binding_helper = typing.cast(typing.Any, None)
        self.__group_value_binding_helper.close()
        self.__group_value_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> RadioButtonWidgetBehavior:
        return typing.cast(RadioButtonWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def icon(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__icon_binding_helper.value

    @icon.setter
    def icon(self, rgba_image: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__icon_binding_helper.value = rgba_image

    @property
    def checked(self) -> bool:
        return self._behavior.checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._behavior.checked = value

    @property
    def value(self) -> typing.Optional[int]:
        return self.__value

    @value.setter
    def value(self, value: typing.Optional[int]) -> None:
        self.__value = value
        self.checked = self.group_value == self.__value

    @property
    def group_value(self) -> typing.Optional[int]:
        return self.__group_value_binding_helper.value

    @group_value.setter
    def group_value(self, group_value: typing.Optional[int]) -> None:
        self.__group_value_binding_helper.value = group_value

    def bind_group_value(self, binding: Binding.Binding) -> None:
        self.__group_value_binding_helper.bind_value(binding)

    def unbind_group_value(self) -> None:
        self.__group_value_binding_helper.unbind_value()

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()

    def bind_icon(self, binding: Binding.Binding) -> None:
        self.__icon_binding_helper.bind_value(binding)

    def unbind_icon(self) -> None:
        self.__icon_binding_helper.unbind_value()


class CheckBoxWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    check_state: str
    tristate: bool
    on_check_state_changed: typing.Optional[typing.Callable[[str], None]]


class CheckBoxWidget(Widget):

    def __init__(self, widget_behavior: CheckBoxWidgetBehavior, text: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)
        self.on_checked_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None

        def set_text(value: typing.Optional[str]) -> None:
            self._behavior.text = str(value) if value is not None else None

        def get_check_state() -> str:
            return self._behavior.check_state

        def set_check_state(value: str) -> None:
            self._behavior.check_state = value

        def get_checked() -> bool:
            return self._behavior.check_state == "checked"

        def set_checked(value: bool) -> None:
            set_check_state("checked" if value else "unchecked")

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)

        # check state and checked are not independent, so use low level getters
        self.__check_state_binding_helper = BindablePropertyHelper[str](get_check_state, set_check_state)
        self.__checked_binding_helper = BindablePropertyHelper[bool](get_checked, set_checked)

        def handle_check_state_changed(check_state: str) -> None:
            self.__checked_binding_helper.value_changed(check_state == "checked")
            self.__check_state_binding_helper.value_changed(check_state)
            if callable(self.on_checked_changed):
                self.on_checked_changed(check_state == "checked")
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        self._behavior.on_check_state_changed = handle_check_state_changed

        self.text = text
        self.check_state = "unchecked"
        self.checked = False

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
        self.__check_state_binding_helper.close()
        self.__check_state_binding_helper = typing.cast(typing.Any, None)
        self.__checked_binding_helper.close()
        self.__checked_binding_helper = typing.cast(typing.Any, None)
        self.on_checked_changed = None
        self.on_check_state_changed = None
        super().close()

    @property
    def _behavior(self) -> CheckBoxWidgetBehavior:
        return typing.cast(CheckBoxWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def checked(self) -> bool:
        return self.__checked_binding_helper.value

    @checked.setter
    def checked(self, value: bool) -> None:
        self.__checked_binding_helper.value = value

    @property
    def tristate(self) -> bool:
        return self._behavior.tristate

    @tristate.setter
    def tristate(self, value: bool) -> None:
        self._behavior.tristate = value

    @property
    def check_state(self) -> str:
        return self.__check_state_binding_helper.value

    @check_state.setter
    def check_state(self, value: str) -> None:
        self.__check_state_binding_helper.value = value

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()

    def bind_checked(self, binding: Binding.Binding) -> None:
        self.__checked_binding_helper.bind_value(binding)

    def unbind_checked(self) -> None:
        self.__checked_binding_helper.unbind_value()

    def bind_check_state(self, binding: Binding.Binding) -> None:
        self.__check_state_binding_helper.bind_value(binding)

    def unbind_check_state(self) -> None:
        self.__check_state_binding_helper.unbind_value()


class LabelWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    word_wrap: bool
    def set_text_color(self, value: typing.Optional[str]) -> None: ...
    def set_text_font(self, value: typing.Optional[str]) -> None: ...


class LabelWidget(Widget):

    def __init__(self, widget_behavior: LabelWidgetBehavior, text: typing.Optional[str]) -> None:
        super().__init__(widget_behavior)

        def set_text(value: typing.Optional[str]) -> None:
            self._behavior.text = str(value) if value is not None else str()

        def set_text_font(value: typing.Optional[str]) -> None:
            self._behavior.set_text_font(str(value) if value is not None else None)

        def set_text_color(value: typing.Optional[str]) -> None:
            self._behavior.set_text_color(str(value) if value is not None else None)

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)
        self.__text_font_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text_font)
        self.__text_color_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text_color)

        self.text = text
        self.text_font = None
        self.text_color = "black"
        self.background_color = None

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
        self.__text_font_binding_helper.close()
        self.__text_font_binding_helper = typing.cast(typing.Any, None)
        self.__text_color_binding_helper.close()
        self.__text_color_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def _behavior(self) -> LabelWidgetBehavior:
        return typing.cast(LabelWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def text_color(self) -> typing.Optional[str]:
        return self.__text_color_binding_helper.value

    @text_color.setter
    def text_color(self, value: typing.Optional[str]) -> None:
        self.__text_color_binding_helper.value = value

    @property
    def text_font(self) -> typing.Optional[str]:
        return self.__text_font_binding_helper.value

    @text_font.setter
    def text_font(self, value: typing.Optional[str]) -> None:
        self.__text_font_binding_helper.value = value

    @property
    def word_wrap(self) -> bool:
        return self._behavior.word_wrap

    @word_wrap.setter
    def word_wrap(self, value: bool) -> None:
        self._behavior.word_wrap = value

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()

    def bind_text_font(self, binding: Binding.Binding) -> None:
        self.__text_font_binding_helper.bind_value(binding)

    def unbind_text_font(self) -> None:
        self.__text_font_binding_helper.unbind_value()

    def bind_text_color(self, binding: Binding.Binding) -> None:
        self.__text_color_binding_helper.bind_value(binding)

    def unbind_text_color(self) -> None:
        self.__text_color_binding_helper.unbind_value()


class SliderWidgetBehavior(WidgetBehavior, typing.Protocol):
    value: int
    minimum: int
    maximum: int

    @property
    def pressed(self) -> bool: raise NotImplementedError()

    on_value_changed: typing.Optional[typing.Callable[[int], None]]
    on_slider_pressed: typing.Optional[typing.Callable[[], None]]
    on_slider_released: typing.Optional[typing.Callable[[], None]]
    on_slider_moved: typing.Optional[typing.Callable[[int], None]]


class SliderWidget(Widget):
    # note: sliders with exactly the same configuration have problems on macOS.
    # see https://bugreports.qt.io/browse/QTBUG-77368
    # ensure different sliders by setting different min/max. argh.

    def __init__(self, widget_behavior: SliderWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.on_slider_pressed: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_released: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_moved: typing.Optional[typing.Callable[[int], None]] = None
        self.minimum = 0
        self.maximum = 0

        def set_value(value: int) -> None:
            old_value_changed = self.on_value_changed
            self.on_value_changed = None
            try:
                self._behavior.value = value
                if callable(self.on_value_changed):
                    self.on_value_changed(value)
            finally:
                self.on_value_changed = old_value_changed

        def validate_value(new_value: int, old_value: int) -> int:
            return min(max(new_value, self.minimum), self.maximum)

        self.__value_binding_helper = BindablePropertyHelper[int](None, set_value, validate_value)

        def handle_value_changed(value: int) -> None:
            self.__value_binding_helper.value_changed(value)
            if callable(self.on_value_changed):
                self.on_value_changed(value)

        self._behavior.on_value_changed = handle_value_changed

        def handle_slider_pressed() -> None:
            if callable(self.on_slider_pressed):
                self.on_slider_pressed()

        self._behavior.on_slider_pressed = handle_slider_pressed

        def handle_slider_released() -> None:
            if callable(self.on_slider_released):
                self.on_slider_released()

        self._behavior.on_slider_released = handle_slider_released

        def handle_slider_moved(value: int) -> None:
            if callable(self.on_slider_moved):
                self.on_slider_moved(value)

        self._behavior.on_slider_moved = handle_slider_moved

        self.value = 0

    def close(self) -> None:
        self.__value_binding_helper.close()
        self.__value_binding_helper = typing.cast(typing.Any, None)
        self.on_value_changed = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_slider_moved = None
        super().close()

    @property
    def _behavior(self) -> SliderWidgetBehavior:
        return typing.cast(SliderWidgetBehavior, super()._behavior)

    @property
    def value(self) -> int:
        return self.__value_binding_helper.value

    @value.setter
    def value(self, value: int) -> None:
        self.__value_binding_helper.value = value

    @property
    def minimum(self) -> int:
        return self._behavior.minimum

    @minimum.setter
    def minimum(self, minimum: int) -> None:
        self._behavior.minimum = minimum

    @property
    def maximum(self) -> int:
        return self._behavior.maximum

    @maximum.setter
    def maximum(self, maximum: int) -> None:
        self._behavior.maximum = maximum

    @property
    def pressed(self) -> bool:
        return self._behavior.pressed

    def bind_value(self, binding: Binding.Binding) -> None:
        self.__value_binding_helper.bind_value(binding)

    def unbind_value(self) -> None:
        self.__value_binding_helper.unbind_value()


class LineEditWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    placeholder_text: typing.Optional[str]
    editable: bool
    clear_button_enabled: bool
    on_editing_finished: typing.Optional[typing.Callable[[str], None]]
    on_escape_pressed: typing.Optional[typing.Callable[[], bool]]
    on_return_pressed: typing.Optional[typing.Callable[[], bool]]
    on_key_pressed: typing.Optional[typing.Callable[[Key], bool]]
    on_text_edited: typing.Optional[typing.Callable[[str], None]]

    def editing_finished(self, text: str) -> None: ...

    @property
    def selected_text(self) -> typing.Optional[str]: raise NotImplementedError()

    def select_all(self) -> None: ...


class LineEditWidget(Widget):

    def __init__(self, widget_behavior: LineEditWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.on_editing_finished: typing.Optional[typing.Callable[[str], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[str], None]] = None
        self.__last_text = None

        def handle_editing_finished(text: str) -> None:
            if text != self.__last_text:
                self.__text_binding_helper.value_changed(text)
            if callable(self.on_editing_finished):
                self.on_editing_finished(text)
            self.__last_text = text

        self._behavior.on_editing_finished = handle_editing_finished

        def handle_escape_pressed() -> bool:
            self.__text_binding_helper.value_changed(self.__last_text)
            self.request_refocus()
            if callable(self.on_escape_pressed):
                return self.on_escape_pressed()
            return False

        self._behavior.on_escape_pressed = handle_escape_pressed

        def handle_return_pressed() -> bool:
            self.__text_binding_helper.value_changed(self.text)
            self.request_refocus()
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

        def set_text(value: typing.Optional[str]) -> None:
            str_ = str(value) if value is not None else str()
            self.__last_text = str_
            self._behavior.text = str_

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def _behavior(self) -> LineEditWidgetBehavior:
        return typing.cast(LineEditWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def placeholder_text(self) -> typing.Optional[str]:
        return self._behavior.placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, text: typing.Optional[str]) -> None:
        self._behavior.placeholder_text = text

    @property
    def selected_text(self) -> typing.Optional[str]:
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

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()

    def editing_finished(self, text: str) -> None:
        self._behavior.editing_finished(text)


Selection = collections.namedtuple("Selection", ["start", "end"])

CursorPosition = collections.namedtuple("CursorPosition", ["position", "block_number", "column_number"])


class TextEditWidgetBehavior(WidgetBehavior, typing.Protocol):
    text: typing.Optional[str]
    placeholder: typing.Optional[str]
    editable: bool
    word_wrap_mode: str

    on_cursor_position_changed: typing.Optional[typing.Callable[[CursorPosition], None]]
    on_selection_changed: typing.Optional[typing.Callable[[Selection], None]]
    on_text_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]]
    on_text_edited: typing.Optional[typing.Callable[[typing.Optional[str]], None]]
    on_escape_pressed: typing.Optional[typing.Callable[[], bool]]
    on_return_pressed: typing.Optional[typing.Callable[[], bool]]
    on_key_pressed: typing.Optional[typing.Callable[[Key], bool]]
    on_insert_mime_data: typing.Optional[typing.Callable[[MimeData], None]]

    @property
    def selected_text(self) -> typing.Optional[str]:  raise NotImplementedError()

    @property
    def cursor_position(self) -> CursorPosition: raise NotImplementedError()

    @property
    def selection(self) -> Selection: raise NotImplementedError()

    def append_text(self, value: str) -> None: ...
    def insert_text(self, value: str) -> None: ...
    def clear_selection(self) -> None: ...
    def remove_selected_text(self) -> None: ...
    def select_all(self) -> None: ...
    def move_cursor_position(self, operation: str, mode: typing.Optional[str] = None, n: int = 1) -> None: ...
    def set_line_height_proportional(self, proportional_line_height: float) -> None: ...
    def set_text_background_color(self, color: typing.Optional[str]) -> None: ...
    def set_text_color(self, color: typing.Optional[str]) -> None: ...
    def set_text_font(self, font_str: typing.Optional[str]) -> None: ...


class TextEditWidget(Widget):

    def __init__(self, widget_behavior: TextEditWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.on_cursor_position_changed: typing.Optional[typing.Callable[[CursorPosition], None]] = None
        self.on_selection_changed: typing.Optional[typing.Callable[[Selection], None]] = None
        self.on_text_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None  # backwards compatibility
        self.on_text_edited: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_insert_mime_data: typing.Optional[typing.Callable[[MimeData], None]] = None

        def handle_cursor_position_changed(cursor_position: CursorPosition) -> None:
            if callable(self.on_cursor_position_changed):
                self.on_cursor_position_changed(cursor_position)

        self._behavior.on_cursor_position_changed = handle_cursor_position_changed

        def handle_selection_changed(selection: Selection) -> None:
            if callable(self.on_selection_changed):
                self.on_selection_changed(selection)

        self._behavior.on_selection_changed = handle_selection_changed

        def handle_text_changed(text: typing.Optional[str]) -> None:
            self.__text_binding_helper.value_changed(text)
            if callable(self.on_text_changed):
                self.on_text_changed(text)
            if callable(self.on_text_edited):
                self.on_text_edited(text)

        self._behavior.on_text_changed = handle_text_changed

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

        def handle_insert_mime_data(mime_data: MimeData) -> None:
            if callable(self.on_insert_mime_data):
                self.on_insert_mime_data(mime_data)
            else:
                text = mime_data.data_as_string("text/plain")
                self.insert_text(text)

        self._behavior.on_insert_mime_data = handle_insert_mime_data

        def set_text(value: typing.Optional[str]) -> None:
            self._behavior.text = str(value) if value is not None else str()

        self.__text_binding_helper = BindablePropertyHelper[typing.Optional[str]](None, set_text)

    def close(self) -> None:
        self.__text_binding_helper.close()
        self.__text_binding_helper = typing.cast(typing.Any, None)
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
    def _behavior(self) -> TextEditWidgetBehavior:
        return typing.cast(TextEditWidgetBehavior, super()._behavior)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text_binding_helper.value

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_binding_helper.value = text

    @property
    def placeholder(self) -> typing.Optional[str]:
        return self._behavior.placeholder

    @placeholder.setter
    def placeholder(self, text: typing.Optional[str]) -> None:
        self._behavior.placeholder = text

    @property
    def editable(self) -> bool:
        return self._behavior.editable

    @editable.setter
    def editable(self, value: bool) -> None:
        self._behavior.editable = value

    @property
    def selected_text(self) -> typing.Optional[str]:
        return self._behavior.selected_text

    @property
    def cursor_position(self) -> CursorPosition:
        return self._behavior.cursor_position

    @property
    def selection(self) -> Selection:
        return self._behavior.selection

    def append_text(self, value: str) -> None:
        self._behavior.append_text(value)

    def insert_text(self, value: str) -> None:
        self._behavior.insert_text(value)

    def clear_selection(self) -> None:
        self._behavior.clear_selection()

    def remove_selected_text(self) -> None:
        self._behavior.remove_selected_text()

    def select_all(self) -> None:
        self._behavior.select_all()

    def refocus(self) -> None:
        self.select_all()

    def move_cursor_position(self, operation: str, mode: typing.Optional[str] = None, n: int = 1) -> None:
        self._behavior.move_cursor_position(operation, mode, n)

    def handle_select_all(self) -> None:
        self.select_all()

    def set_line_height_proportional(self, proportional_line_height: float) -> None:
        self._behavior.set_line_height_proportional(proportional_line_height)

    def set_text_background_color(self, color: typing.Optional[str]) -> None:
        self._behavior.set_text_background_color(color)

    def set_text_color(self, color: typing.Optional[str]) -> None:
        self._behavior.set_text_color(color)

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        self._behavior.set_text_font(font_str)

    @property
    def word_wrap_mode(self) -> str:
        return self._behavior.word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, value: str) -> None:
        self._behavior.word_wrap_mode = value

    def bind_text(self, binding: Binding.Binding) -> None:
        self.__text_binding_helper.bind_value(binding)

    def unbind_text(self) -> None:
        self.__text_binding_helper.unbind_value()


class CanvasWidgetBehavior(WidgetBehavior, typing.Protocol):
    focusable: bool
    on_mouse_entered: typing.Optional[typing.Callable[[], None]]
    on_mouse_exited: typing.Optional[typing.Callable[[], None]]
    on_mouse_clicked: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]]
    on_mouse_double_clicked: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]]
    on_mouse_pressed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]]
    on_mouse_released: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]]
    on_mouse_position_changed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], None]]
    on_grabbed_mouse_position_changed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], None]]
    on_wheel_changed: typing.Optional[typing.Callable[[int, int, int, int, bool], bool]]
    on_size_changed: typing.Optional[typing.Callable[[int, int], None]]
    on_key_pressed: typing.Optional[typing.Callable[[Key], bool]]
    on_key_released: typing.Optional[typing.Callable[[Key], bool]]
    on_drag_enter: typing.Optional[typing.Callable[[MimeData], str]]
    on_drag_leave: typing.Optional[typing.Callable[[], str]]
    on_drag_move: typing.Optional[typing.Callable[[MimeData, int, int], str]]
    on_drop: typing.Optional[typing.Callable[[MimeData, int, int], str]]
    on_tool_tip: typing.Optional[typing.Callable[[int, int, int, int], bool]]
    on_pan_gesture: typing.Optional[typing.Callable[[int, int], bool]]

    def periodic(self) -> None: ...
    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None: ...
    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None: ...
    def remove_section(self, section_id: int) -> None: ...
    def set_cursor_shape(self, cursor_shape: typing.Optional[str]) -> None: ...
    def grab_gesture(self, gesture_type: str) -> None: ...
    def release_gesture(self, gesture_type: str) -> None: ...
    def grab_mouse(self, gx: int, gy: int) -> None: ...
    def release_mouse(self) -> None: ...
    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None: ...
    def _set_canvas_item(self, canvas_item: CanvasItem.AbstractCanvasItem) -> None: ...


class CanvasWidget(Widget):

    def __init__(self, widget_behavior: CanvasWidgetBehavior, *, layout_render: typing.Optional[str] = None) -> None:
        super().__init__(widget_behavior)
        self.on_periodic: typing.Optional[typing.Callable[[], None]] = None
        self.on_dispatch_any: typing.Optional[typing.Callable[..., typing.Any]] = None
        self.on_can_dispatch_any: typing.Optional[typing.Callable[[str], bool]] = None
        self.on_get_menu_item_state: typing.Optional[typing.Callable[[str], typing.Optional[MenuItemState]]] = None
        self.on_mouse_entered: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_exited: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_clicked: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]] = None
        self.on_mouse_double_clicked: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]] = None
        self.on_mouse_pressed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]] = None
        self.on_mouse_released: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], bool]] = None
        self.on_mouse_position_changed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], None]] = None
        self.on_grabbed_mouse_position_changed: typing.Optional[typing.Callable[[int, int, KeyboardModifiers], None]] = None
        self.on_wheel_changed: typing.Optional[typing.Callable[[int, int, int, int, bool], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_key_released: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_drag_enter: typing.Optional[typing.Callable[[MimeData], str]] = None
        self.on_drag_leave: typing.Optional[typing.Callable[[], str]] = None
        self.on_drag_move: typing.Optional[typing.Callable[[MimeData, int, int], str]] = None
        self.on_drop: typing.Optional[typing.Callable[[MimeData, int, int], str]] = None
        self.on_tool_tip: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_pan_gesture: typing.Optional[typing.Callable[[int, int], bool]] = None
        self.width = 0
        self.height = 0
        self.position_info = None

        def handle_mouse_entered() -> None:
            if callable(self.on_mouse_entered):
                self.on_mouse_entered()

        self._behavior.on_mouse_entered = handle_mouse_entered

        def handle_mouse_exited() -> None:
            if callable(self.on_mouse_exited):
                self.on_mouse_exited()
                # when the mouse exits, position info may still be pending
                # since it is serviced during periodic. clear it here so
                # nothing else gets processed. the mouse has already exited.
                self.position_info = None

        self._behavior.on_mouse_exited = handle_mouse_exited

        def handle_mouse_clicked(x: int, y: int, modifiers: KeyboardModifiers) -> bool:
            if callable(self.on_mouse_clicked):
                return self.on_mouse_clicked(x, y, modifiers)
            return False

        self._behavior.on_mouse_clicked = handle_mouse_clicked

        def handle_mouse_double_clicked(x: int, y: int, modifiers: KeyboardModifiers) -> bool:
            if callable(self.on_mouse_double_clicked):
                return self.on_mouse_double_clicked(x, y, modifiers)
            return False

        self._behavior.on_mouse_double_clicked = handle_mouse_double_clicked

        def handle_mouse_pressed(x: int, y: int, modifiers: KeyboardModifiers) -> bool:
            if callable(self.on_mouse_pressed):
                return self.on_mouse_pressed(x, y, modifiers)
            return False

        self._behavior.on_mouse_pressed = handle_mouse_pressed

        def handle_mouse_released(x: int, y: int, modifiers: KeyboardModifiers) -> bool:
            if callable(self.on_mouse_released):
                return self.on_mouse_released(x, y, modifiers)
            return False

        self._behavior.on_mouse_released = handle_mouse_released

        def handle_mouse_position_changed(x: int, y: int, modifiers: KeyboardModifiers) -> None:
            # mouse tracking takes priority over timer events in newer
            # versions of Qt, so during mouse tracking, make sure periodic
            # gets called regularly.
            self.position_info = x, y, modifiers

        self._behavior.on_mouse_position_changed = handle_mouse_position_changed

        def handle_grabbed_mouse_position_changed(dx: int, dy: int, modifiers: KeyboardModifiers) -> None:
            if callable(self.on_grabbed_mouse_position_changed):
                self.on_grabbed_mouse_position_changed(dx, dy, modifiers)

        self._behavior.on_grabbed_mouse_position_changed = handle_grabbed_mouse_position_changed

        def handle_wheel_changed(x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> bool:
            if callable(self.on_wheel_changed):
                return self.on_wheel_changed(x, y, dx, dy, is_horizontal)
            return False

        self._behavior.on_wheel_changed = handle_wheel_changed

        def handle_size_changed(width: int, height: int) -> None:
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

        def handle_drag_leave() -> str:
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

        def handle_pan_gesture(delta_x: int, delta_y: int) -> bool:
            if callable(self.on_pan_gesture):
                return self.on_pan_gesture(delta_x, delta_y)
            return False

        self._behavior.on_pan_gesture = handle_pan_gesture

        self.__canvas_item = CanvasItem.RootCanvasItem(self, layout_render=layout_render)
        self._behavior._set_canvas_item(self.__canvas_item)

    def close(self) -> None:
        if self.__canvas_item:
            self.__canvas_item.close()
            self.__canvas_item = typing.cast(typing.Any, None)
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

    @property
    def _behavior(self) -> CanvasWidgetBehavior:
        return typing.cast(CanvasWidgetBehavior, super()._behavior)

    def periodic(self) -> None:
        super().periodic()
        self._behavior.periodic()
        if self.on_periodic:
            self.on_periodic()
        if self.position_info is not None:
            if callable(self.on_mouse_position_changed):
                self.on_mouse_position_changed(*self.position_info)
            self.position_info = None

    @property
    def canvas_item(self) -> CanvasItem.RootCanvasItem:
        return self.__canvas_item

    @property
    def canvas_size(self) -> Geometry.IntSize:
        return Geometry.IntSize(h=self.height, w=self.width)

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

    def set_cursor_shape(self, cursor_shape: typing.Optional[str]) -> None:
        self._behavior.set_cursor_shape(cursor_shape)

    def simulate_mouse_click(self, x: int, y: int, modifiers: KeyboardModifiers) -> None:
        if self.on_mouse_pressed:
            self.on_mouse_pressed(x, y, modifiers)
        if self.on_mouse_released:
            self.on_mouse_released(x, y, modifiers)
        if self.on_mouse_clicked:
            self.on_mouse_clicked(x, y, modifiers)

    def grab_gesture(self, gesture_type: str) -> None:
        self._behavior.grab_gesture(gesture_type)

    def release_gesture(self, gesture_type: str) -> None:
        self._behavior.release_gesture(gesture_type)

    def grab_mouse(self, gx: int, gy: int) -> None:
        self._behavior.grab_mouse(gx, gy)

    def release_mouse(self) -> None:
        self._behavior.release_mouse()

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        self._behavior.show_tool_tip_text(text, gx, gy)

    def _dispatch_any(self, method: str, *args: typing.Any, **kwargs: typing.Any) -> bool:
        if callable(self.on_dispatch_any):
            return typing.cast(bool, self.on_dispatch_any(method, *args, **kwargs))
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


class ProgressBarWidgetBehavior(CanvasWidgetBehavior, typing.Protocol):
    pass


class ProgressBarWidget(CanvasWidget):

    def __init__(self, widget_behavior: ProgressBarWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.__minimum = 0
        self.__maximum = 0
        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None

        def set_value(value: int) -> None:
            old_value_changed = self.on_value_changed
            self.on_value_changed = None
            try:
                self.__progress_bar_canvas_item.progress = (value - self.__minimum) / (self.__maximum - self.__minimum) if self.__maximum != self.__minimum else 0.0
                if callable(self.on_value_changed):
                    self.on_value_changed(value)
            finally:
                self.on_value_changed = old_value_changed

        def validate_value(new_value: int, old_value: int) -> int:
            return min(max(new_value, self.__minimum), self.__maximum)

        self.__value_binding_helper = BindablePropertyHelper[int](None, set_value, validate_value)

        self.__progress_bar_canvas_item = CanvasItem.ProgressBarCanvasItem()
        self.__progress_bar_canvas_item.update_sizing(self.__progress_bar_canvas_item.sizing.with_fixed_size(Geometry.IntSize(w=500, h=20)))
        self.canvas_item.add_canvas_item(self.__progress_bar_canvas_item)

        self.value = 0

    def close(self) -> None:
        self.__value_binding_helper.close()
        self.__value_binding_helper = typing.cast(typing.Any, None)
        self.on_value_changed = None
        super().close()

    @property
    def _behavior(self) -> ProgressBarWidgetBehavior:
        return typing.cast(ProgressBarWidgetBehavior, super()._behavior)

    @property
    def value(self) -> int:
        return self.__value_binding_helper.value

    @value.setter
    def value(self, value: int) -> None:
        self.__value_binding_helper.value = value

    @property
    def minimum(self) -> int:
        return self.__minimum

    @minimum.setter
    def minimum(self, minimum: int) -> None:
        self.__minimum = minimum

    @property
    def maximum(self) -> int:
        return self.__maximum

    @maximum.setter
    def maximum(self, maximum: int) -> None:
        self.__maximum = maximum

    def bind_value(self, binding: Binding.Binding) -> None:
        self.__value_binding_helper.bind_value(binding)

    def unbind_value(self) -> None:
        self.__value_binding_helper.unbind_value()


class TreeWidgetBehavior(WidgetBehavior, typing.Protocol):
    selection_mode: str
    item_model_controller: typing.Any
    on_key_pressed: typing.Optional[typing.Callable[[typing.Sequence[int], Key], bool]]
    on_tree_selection_changed: typing.Optional[typing.Callable[[typing.Sequence[typing.Tuple[int, int, int]]], None]]
    on_tree_item_changed: typing.Optional[typing.Callable[[int, int, int], None]]
    on_tree_item_clicked: typing.Optional[typing.Callable[[int, int, int], bool]]
    on_tree_item_double_clicked: typing.Optional[typing.Callable[[int, int, int], bool]]
    on_tree_item_key_pressed: typing.Optional[typing.Callable[[int, int, int, Key], bool]]
    def set_current_row(self, index: int, parent_row: int, parent_id: int) -> None: ...
    def clear_current_row(self) -> None: ...
    def size_to_content(self) -> None: ...


class TreeWidget(Widget):

    def __init__(self, widget_behavior: TreeWidgetBehavior) -> None:
        super().__init__(widget_behavior)
        self.on_key_pressed: typing.Optional[typing.Callable[[typing.Sequence[int], Key], bool]] = None
        self.on_selection_changed: typing.Optional[typing.Callable[[typing.Sequence[typing.Tuple[int, int, int]]], None]] = None
        self.on_current_item_changed: typing.Optional[typing.Callable[[int, int, int], None]] = None
        self.on_item_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_item_double_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_item_key_pressed: typing.Optional[typing.Callable[[int, int, int, Key], bool]] = None

        def handle_key_pressed(indexes: typing.Sequence[int], key: Key) -> bool:
            if callable(self.on_key_pressed):
                return self.on_key_pressed(indexes, key)
            return False

        self._behavior.on_key_pressed = handle_key_pressed

        def handle_tree_item_changed(index: int, parent_row: int, parent_id: int) -> None:
            if callable(self.on_current_item_changed):
                self.on_current_item_changed(index, parent_row, parent_id)

        self._behavior.on_tree_item_changed = handle_tree_item_changed

        def handle_tree_selection_changed(selected_indexes: typing.Sequence[typing.Tuple[int, int, int]]) -> None:
            if callable(self.on_selection_changed):
                self.on_selection_changed(selected_indexes)

        self._behavior.on_tree_selection_changed = handle_tree_selection_changed

        def handle_tree_item_key_pressed(index: int, parent_row: int, parent_id: int, key: Key) -> bool:
            if callable(self.on_item_key_pressed):
                return self.on_item_key_pressed(index, parent_row, parent_id, key)
            return False

        self._behavior.on_tree_item_key_pressed = handle_tree_item_key_pressed

        def handle_tree_item_clicked(index: int, parent_row: int, parent_id: int) -> bool:
            if callable(self.on_item_clicked):
                return self.on_item_clicked(index, parent_row, parent_id)
            return False

        self._behavior.on_tree_item_clicked = handle_tree_item_clicked

        def handle_tree_item_double_clicked(index: int, parent_row: int, parent_id: int) -> bool:
            if callable(self.on_item_double_clicked):
                return self.on_item_double_clicked(index, parent_row, parent_id)
            return False

        self._behavior.on_tree_item_double_clicked = handle_tree_item_double_clicked

    def close(self) -> None:
        self.__item_model_controller = None
        self.on_key_pressed = None
        self.on_selection_changed = None
        self.on_current_item_changed = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        super().close()

    @property
    def _behavior(self) -> TreeWidgetBehavior:
        return typing.cast(TreeWidgetBehavior, super()._behavior)

    @property
    def selection_mode(self) -> str:
        return self._behavior.selection_mode

    @selection_mode.setter
    def selection_mode(self, value: str) -> None:
        self._behavior.selection_mode = value

    @property
    def item_model_controller(self) -> typing.Any:
        return self._behavior.item_model_controller

    @item_model_controller.setter
    def item_model_controller(self, value: typing.Any) -> None:
        self._behavior.item_model_controller = value

    def set_current_row(self, index: int, parent_row: int, parent_id: int) -> None:
        self._behavior.set_current_row(index, parent_row, parent_id)

    def clear_current_row(self) -> None:
        self._behavior.clear_current_row()

    def size_to_content(self) -> None:
        self._behavior.size_to_content()


class MenuAction:

    def __init__(self, action_id: typing.Optional[str] = None) -> None:
        self.action_id = action_id
        self.on_triggered: typing.Optional[typing.Callable[[], None]] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_triggered = None
        self.on_ui_activity = None

    def _register_ui_activity(self) -> None:
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
        if callable(self.on_triggered):
            self.on_triggered()

    def create(self, document_window: Window, title: str, key_sequence: typing.Optional[str], role: typing.Optional[str]) -> None:
        raise NotImplementedError()

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

    def __init__(self, *, action: typing.Optional[MenuAction] = None, is_separator: bool = False,
                 sub_menu: typing.Optional[Menu] = None) -> None:
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
    def title(self) -> str:
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
    def callback(self) -> typing.Optional[typing.Callable[[], None]]:
        # NOTE: for backwards compatibility only (tests 0.14)
        return typing.cast(typing.Optional[typing.Callable[[], None]], getattr(self.action, "callback", None))

    def __str__(self) -> str:
        if self.action:
            return f"action {self.action.title}"
        elif self.is_separator:
            return "separator"
        elif self.sub_menu:
            return self.sub_menu.title if self.sub_menu.title else "sub_menu"
        else:
            return "?item"


class Menu:

    def __init__(self, document_window: Window, title: str, menu_id: str) -> None:
        self.document_window = document_window
        self.title = title
        self.menu_id = menu_id
        self.on_about_to_show: typing.Optional[typing.Callable[[], None]] = None
        self.on_about_to_hide: typing.Optional[typing.Callable[[], None]] = None
        self.__items: typing.List[MenuItem] = list()

    def close(self) -> None:
        for item in self.__items:
            item.close()
        self.__items = typing.cast(typing.Any, None)
        self.document_window = typing.cast(typing.Any, None)
        self.on_about_to_show = None
        self.on_about_to_hide = None

    def destroy(self) -> None:
        # for backwards compatibility
        if self.__items:
            self.close()

    @property
    def items(self) -> typing.Sequence[MenuItem]:
        return self.__items

    def get_menu_actions(self) -> typing.Sequence[MenuAction]:
        return [item.action for item in self.__items if item.action]

    def _register_ui_activity(self) -> None:
        self.document_window._register_ui_activity()

    def about_to_show(self) -> None:
        self._register_ui_activity()
        if callable(self.on_about_to_show):
            self.on_about_to_show()

    def about_to_hide(self) -> None:
        self._register_ui_activity()
        if callable(self.on_about_to_hide):
            self.on_about_to_hide()

    def _prepare_action(self, action: MenuAction, title: str, action_id: typing.Optional[str],
                        callback: typing.Callable[[], None], key_sequence: typing.Optional[str] = None,
                        role: typing.Optional[str] = None) -> None:
        # subclasses should call this to prepare a newly created action
        action.create(self.document_window, title, key_sequence, role)
        action.action_id = action_id
        action.on_triggered = callback
        action.on_ui_activity = self._register_ui_activity

    def add_menu_item(self, title: str, callback: typing.Callable[[], None], key_sequence: typing.Optional[str] = None,
                      role: typing.Optional[str] = None, action_id: typing.Optional[str] = None) -> MenuAction:
        raise NotImplementedError()

    def add_action(self, action: MenuAction) -> None:
        raise NotImplementedError()

    def add_sub_menu(self, title: str, menu: Menu) -> None:
        raise NotImplementedError()

    def add_separator(self) -> None:
        raise NotImplementedError()

    def insert_menu_item(self, title: str, before_action: MenuAction, callback: typing.Callable[[], None],
                         key_sequence: typing.Optional[str] = None, role: typing.Optional[str] = None,
                         action_id: typing.Optional[str] = None) -> None:
        raise NotImplementedError()

    def insert_separator(self, before_action: MenuAction) -> None:
        raise NotImplementedError()

    def remove_action(self, action: MenuAction) -> None:
        raise NotImplementedError()

    def _item_added(self, *, action: typing.Optional[MenuAction] = None, is_separator: bool = False,
                    sub_menu: typing.Optional[Menu] = None) -> None:
        # subclasses should call this when adding a menu item
        item = MenuItem(action=action, is_separator=is_separator, sub_menu=sub_menu)
        self.__items.append(item)
        self.document_window._menu_item_added(item)

    def _item_inserted(self, before_action: MenuAction, *, action: typing.Optional[MenuAction] = None,
                       is_separator: bool = False, sub_menu: typing.Optional[Menu] = None) -> None:
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

    def popup(self, gx: int, gy: int) -> None:
        raise NotImplementedError()


class DockWidget:

    def __init__(self, document_window: Window, widget: Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> None:
        self.document_window = document_window
        self.document_window.register_dock_widget(self)
        self.widget = widget
        self.widget._set_root_container(typing.cast("WindowModule.Window", self))
        self.panel_id = panel_id
        self.title = title
        self.positions = positions
        self.position = position
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.size: typing.Optional[Geometry.IntSize] = None

    def close(self) -> None:
        self.widget.close()
        self.widget = typing.cast(typing.Any, None)
        self.document_window.unregister_dock_widget(self)
        self.document_window = typing.cast(typing.Any, None)
        self.on_size_changed = None
        self.on_focus_changed = None
        self.on_ui_activity = None

    def _register_ui_activity(self) -> None:
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    @property
    def width(self) -> int:
        size = self.size
        if size is not None:
            return size.width
        return 0

    @property
    def height(self) -> int:
        size = self.size
        if size is not None:
            return size.height
        return 0

    def refocus_widget(self, widget: Widget) -> None:
        # if the widget is one that retains focus, refocus it. this ensures that pressing return
        # on a line edit widget in a dock widget selects all for a nice user experience.
        if widget.does_retain_focus:
            widget.refocus()
        else:
            self.document_window.refocus_widget(widget)

    @property
    def focus_widget(self) -> typing.Optional[Widget]:
        def match_native_widget(widget: Widget) -> typing.Optional[Widget]:
            if widget.focused:
                return widget
            for child_widget in widget._contained_widgets:
                matched_widget = match_native_widget(child_widget)
                if matched_widget:
                    return matched_widget
            return None

        return match_native_widget(self.widget)

    def queue_task(self, task: typing.Callable[[], None]) -> None:
        self.document_window.queue_task(task)

    def clear_queued_tasks(self) -> None:
        self.document_window.clear_queued_tasks()

    def add_task(self, key: str, task: typing.Callable[[], None]) -> None:
        self.document_window.add_task(key + str(id(self)), task)

    def clear_task(self, key: str) -> None:
        self.document_window.clear_task(key + str(id(self)))

    def periodic(self) -> None:
        self.widget.periodic()

    @property
    def toggle_action(self) -> MenuAction:
        raise NotImplementedError()

    def show(self) -> None:
        self._register_ui_activity()

    def hide(self) -> None:
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

    def __init__(self, parent_window: typing.Optional[Window], title: str) -> None:
        self.parent_window = parent_window
        self.root_widget: typing.Optional[Widget] = None
        self.has_event_loop = True
        self.window_style = "window"
        # Python 3.9+: weakref.ReferenceType[DockWidget]
        self.__dock_widget_weak_refs: typing.List[typing.Any] = list()
        self.on_periodic: typing.Optional[typing.Callable[[], None]] = None
        self.on_queue_task: typing.Optional[typing.Callable[[typing.Callable[[], None]], None]] = None
        self.on_clear_queued_tasks: typing.Optional[typing.Callable[[], None]] = None
        self.on_add_task: typing.Optional[typing.Callable[[str, typing.Callable[[], None]], None]] = None
        self.on_clear_task: typing.Optional[typing.Callable[[str], None]] = None
        self.on_about_to_show: typing.Optional[typing.Callable[[], None]] = None
        self.on_about_to_close: typing.Optional[typing.Callable[[str, str], None]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_key_released: typing.Optional[typing.Callable[[Key], bool]] = None
        self.on_activation_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_position_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_refocus_widget: typing.Optional[typing.Callable[[Widget], None]] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.pos_x: typing.Optional[int] = None
        self.pos_y: typing.Optional[int] = None
        self.width: typing.Optional[int] = None
        self.height: typing.Optional[int] = None
        self.__title = title if title is not None else str()
        self.__window_file_path: typing.Optional[pathlib.Path] = None
        self.__menus: typing.List[Menu] = list()
        self.__menu_map: typing.Dict[str, Menu] = dict()
        self.__menu_actions: typing.Dict[str, MenuAction] = dict()

    def close(self) -> None:
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
        self.__menus = typing.cast(typing.Any, None)
        self.__menu_map = typing.cast(typing.Any, None)
        self.__menu_actions = typing.cast(typing.Any, None)
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

    def request_close(self) -> None:
        raise NotImplementedError()

    def _register_ui_activity(self) -> None:
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    # attach the root widget to this window
    # the root widget must respond to _set_root_container
    def attach(self, root_widget: Widget) -> None:
        self.root_widget = root_widget
        self.root_widget._set_root_container(typing.cast("WindowModule.Window", self))
        self._attach_root_widget(root_widget)

    def _attach_root_widget(self, root_widget: typing.Optional[Widget]) -> None:
        raise NotImplementedError()

    def detach(self) -> None:
        assert self.root_widget is not None
        self.root_widget.close()
        self.root_widget = None

    @property
    def dock_widgets(self) -> typing.List[DockWidget]:
        return [dock_widget_weak_ref() for dock_widget_weak_ref in self.__dock_widget_weak_refs]

    def register_dock_widget(self, dock_widget: DockWidget) -> None:
        self.__dock_widget_weak_refs.append(weakref.ref(dock_widget))

    def unregister_dock_widget(self, dock_widget: DockWidget) -> None:
        self.__dock_widget_weak_refs.remove(weakref.ref(dock_widget))

    def queue_task(self, task: typing.Callable[[], None]) -> None:
        if self.on_queue_task:
            self.on_queue_task(task)

    def clear_queued_tasks(self) -> None:
        if self.on_clear_queued_tasks:
            self.on_clear_queued_tasks()

    def add_task(self, key: str, task: typing.Callable[[], None]) -> None:
        if self.on_add_task:
            self.on_add_task(key + str(id(self)), task)

    def clear_task(self, key: str) -> None:
        if self.on_clear_task:
            self.on_clear_task(key + str(id(self)))

    @property
    def focus_widget(self) -> typing.Optional[Widget]:
        return self._get_focus_widget()

    def _get_focus_widget(self) -> typing.Optional[Widget]:
        raise NotImplementedError()

    def refocus_widget(self, widget: Widget) -> None:
        if callable(self.on_refocus_widget):
            self.on_refocus_widget(widget)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        raise NotImplementedError()

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        raise NotImplementedError()

    def get_color_dialog(self, title: str, color: str, show_alpha: bool) -> typing.Optional[str]:
        raise NotImplementedError()

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        raise NotImplementedError()

    def create_dock_widget(self, widget: Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> DockWidget:
        raise NotImplementedError()

    def tabify_dock_widgets(self, dock_widget1: DockWidget, dock_widget2: DockWidget) -> None:
        raise NotImplementedError()

    @property
    def screen_size(self) -> Geometry.IntSize:
        return self._get_screen_size()

    def _get_screen_size(self) -> Geometry.IntSize:
        raise NotImplementedError()

    @property
    def screen_logical_dpi(self) -> float:
        return self._get_screen_logical_dpi()

    def _get_screen_logical_dpi(self) -> float:
        raise NotImplementedError()

    @property
    def screen_physical_dpi(self) -> float:
        return self._get_screen_physical_dpi()

    def _get_screen_physical_dpi(self) -> float:
        raise NotImplementedError()

    @property
    def display_scaling(self) -> float:
        return self._get_display_scaling()

    def _get_display_scaling(self) -> float:
        raise NotImplementedError()

    # call show to display the window.
    def show(self, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        raise NotImplementedError()

    def activate(self) -> None:
        raise NotImplementedError()

    def fill_screen(self) -> None:
        raise NotImplementedError()

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        self.__title = value
        self._set_title(value)

    def _set_title(self, value: str) -> None:
        raise NotImplementedError()

    @property
    def window_file_path(self) -> typing.Optional[pathlib.Path]:
        return self.__window_file_path

    @window_file_path.setter
    def window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        self.__window_file_path = value
        self._set_window_file_path(value)

    def _set_window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        raise NotImplementedError()

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        raise NotImplementedError()

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        raise NotImplementedError()

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        raise NotImplementedError()

    def _handle_periodic(self) -> None:
        if self.root_widget:
            self.root_widget.periodic()
        if self.on_periodic:
            self.on_periodic()

    def _handle_about_to_show(self) -> None:
        if self.on_about_to_show:
            self.on_about_to_show()

    def _handle_activation_changed(self, activated: bool) -> None:
        if self.on_activation_changed:
            self.on_activation_changed(activated)

    def _handle_about_to_close(self, geometry: str, state: str) -> None:
        if self.on_about_to_close:
            self.on_about_to_close(geometry, state)

    def _handle_key_pressed(self, key: Key) -> bool:
        if callable(self.on_key_pressed):
            return self.on_key_pressed(key)
        return False

    def _handle_key_released(self, key: Key) -> bool:
        if callable(self.on_key_released):
            return self.on_key_released(key)
        return False

    def add_menu(self, title: str, menu_id: typing.Optional[str] = None) -> Menu:
        raise NotImplementedError()

    def insert_menu(self, title: str, before_menu: Menu, menu_id: typing.Optional[str] = None) -> Menu:
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
        return self.__menu_actions.get(action_id, MenuAction())

    def get_menu_actions(self) -> typing.Sequence[MenuAction]:
        return list(self.__menu_actions.values())

    @property
    def menus(self) -> typing.List[Menu]:
        return self.__menus

    def get_menu(self, menu_id: str) -> typing.Optional[Menu]:
        return self.__menu_map.get(menu_id)

    def save(self) -> typing.Tuple[str, str]:
        raise NotImplementedError()

    def restore(self, geometry: str, state: str) -> None:
        raise NotImplementedError()

    def _handle_size_changed(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        if callable(self.on_size_changed):
            self.on_size_changed(self.width, self.height)

    def _handle_position_changed(self, x: int, y: int) -> None:
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


class PersistenceHandler(abc.ABC):
    # interface for handling backwards compatibility of persistent values from a UserInterface object

    @abc.abstractmethod
    def get_string(self, key: str) -> typing.Tuple[bool, str]: ...

    @abc.abstractmethod
    def set_string(self, key: str, value: str) -> bool: ...

    @abc.abstractmethod
    def remove_key(self, key: str) -> bool: ...


class StringPersistentModel(Model.PropertyModel[str]):
    def __init__(self, ui: UserInterface, storage_key: str, value: typing.Optional[str] = None):
        self.__storage_key = storage_key
        self.__ui = ui
        super().__init__(self.__ui.get_persistent_string(self.__storage_key, value))

    def _set_value(self, value: typing.Optional[str]) -> None:
        super()._set_value(value)
        if value is not None:
            self.__ui.set_persistent_string(self.__storage_key, str(value))
        else:
            self.__ui.remove_persistent_key(self.__storage_key)


class FloatPersistentModel(Model.PropertyModel[float]):
    def __init__(self, ui: UserInterface, storage_key: str, value: typing.Optional[float] = None):
        self.__storage_key = storage_key
        self.__ui = ui
        value_str = self.__ui.get_persistent_string(self.__storage_key, None)
        value = Converter.FloatToStringConverter(pass_none=True).convert_back(value_str)
        super().__init__(value)

    def _set_value(self, value: typing.Optional[float]) -> None:
        super()._set_value(value)
        if value is not None:
            self.__ui.set_persistent_string(self.__storage_key, str(value))
        else:
            self.__ui.remove_persistent_key(self.__storage_key)


class ButtonGroup(typing.Protocol):
    on_button_clicked: typing.Optional[typing.Callable[[str], None]]
    def close(self) -> None: ...
    def add_button(self, radio_button: RadioButtonWidget, button_id: str) -> None: ...
    def remove_button(self, radio_button: RadioButtonWidget) -> None: ...
    def clicked(self, button_id: str) -> None: ...


class UserInterface(abc.ABC):

    @abc.abstractmethod
    def close(self) -> None:
        ...

    @abc.abstractmethod
    def run(self, app: Application.BaseApplication) -> None:
        ...

    @abc.abstractmethod
    def request_quit(self) -> None:
        ...

    # data objects

    @abc.abstractmethod
    def create_mime_data(self) -> MimeData:
        ...

    @abc.abstractmethod
    def create_item_model_controller(self) -> typing.Any:
        ...

    @abc.abstractmethod
    def create_button_group(self) -> ButtonGroup:
        ...

    # window elements

    @abc.abstractmethod
    def create_document_window(self, title: typing.Optional[str] = None, parent_window: typing.Optional[Window] = None) -> Window:
        ...

    @abc.abstractmethod
    def destroy_document_window(self, document_window: Window) -> None:
        ...

    # user interface elements

    @abc.abstractmethod
    def create_row_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> BoxWidget:
        ...

    @abc.abstractmethod
    def create_column_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> BoxWidget:
        ...

    @abc.abstractmethod
    def create_splitter_widget(self, orientation: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> SplitterWidget:
        ...

    @abc.abstractmethod
    def create_tab_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> TabWidget:
        ...

    @abc.abstractmethod
    def create_stack_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> StackWidget:
        ...

    @abc.abstractmethod
    def create_group_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> GroupWidget:
        ...

    @abc.abstractmethod
    def create_scroll_area_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> ScrollAreaWidget:
        ...

    @abc.abstractmethod
    def create_combo_box_widget(self, items: typing.Optional[typing.Sequence[typing.Any]] = None, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> ComboBoxWidget:
        ...

    @abc.abstractmethod
    def create_push_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> PushButtonWidget:
        ...

    @abc.abstractmethod
    def create_radio_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> RadioButtonWidget:
        ...

    @abc.abstractmethod
    def create_check_box_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> CheckBoxWidget:
        ...

    @abc.abstractmethod
    def create_label_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> LabelWidget:
        ...

    @abc.abstractmethod
    def create_slider_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> SliderWidget:
        ...

    @abc.abstractmethod
    def create_progress_bar_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> ProgressBarWidget:
        ...

    @abc.abstractmethod
    def create_line_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> LineEditWidget:
        ...

    @abc.abstractmethod
    def create_text_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> TextEditWidget:
        ...

    @abc.abstractmethod
    def create_canvas_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None, *, layout_render: typing.Optional[str] = None) -> CanvasWidget:
        ...

    @abc.abstractmethod
    def create_tree_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> TreeWidget:
        ...

    # file i/o

    @abc.abstractmethod
    def load_rgba_data_from_file(self, filename: str) -> typing.Optional[DrawingContext.RGBA32Type]:
        ...

    @abc.abstractmethod
    def save_rgba_data_to_file(self, data: DrawingContext.RGBA32Type, filename: str, format: typing.Optional[str]) -> None:
        ...

    @abc.abstractmethod
    def get_existing_directory_dialog(self, title: str, directory: str) -> typing.Tuple[str, str]:
        ...

    @abc.abstractmethod
    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        ...

    @abc.abstractmethod
    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        ...

    @abc.abstractmethod
    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
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
    def get_configuration_location(self) -> str:
        ...

    @abc.abstractmethod
    def set_persistence_handler(self, handler: PersistenceHandler) -> None:
        ...

    @abc.abstractmethod
    def get_persistent_string(self, key: str, default_value: typing.Optional[str] = None) -> str:
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

    def create_persistent_string_model(self, key: str, default_value: typing.Optional[str] = None) -> Model.PropertyModel[str]:
        return StringPersistentModel(self, key, default_value)

    def create_persistent_float_model(self, key: str, default_value: typing.Optional[float] = None) -> Model.PropertyModel[float]:
        return FloatPersistentModel(self, key, default_value)

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
    def set_application_info(self, application_name: str, organization_name: str, organization_domain: str) -> None:
        ...

    @abc.abstractmethod
    def create_rgba_image(self, drawing_context: DrawingContext.DrawingContext, width: int, height: int) -> typing.Optional[DrawingContext.RGBA32Type]:
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
    def create_sub_menu(self, document_window: Window, title: typing.Optional[str] = None, menu_id: typing.Optional[str] = None) -> Menu:
        ...

    @abc.abstractmethod
    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        ...

    @abc.abstractmethod
    def get_keyboard_modifiers(self, query: bool = False) -> KeyboardModifiers:
        ...
