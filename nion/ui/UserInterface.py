"""
Provides a user interface object that can render to an Qt host.
"""

# standard libraries
import collections
import copy
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


FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])
