# standard libraries
import collections
import copy
import enum
import typing

# third party libraries
import numpy

# local libraries
from . import CanvasItem
from . import DrawingContext
from . import UserInterface as UserInterfaceModule
from nion.utils import Geometry


focused_widget = None  # simulate focus handling at the widget level


class MimeData(UserInterfaceModule.MimeData):
    def __init__(self, mime_data=None):
        self.mime_data = dict() if mime_data is None else mime_data

    @property
    def formats(self):
        return list(self.mime_data.keys())

    @property
    def file_paths(self):
        urls = self.urls
        file_paths = []
        for url in urls:
            file_paths.append(url)
        return file_paths

    def data_as_string(self, format):
        return str(self.mime_data.get(format))

    def set_data_as_string(self, format, text):
        self.mime_data[format] = text


class MenuItem(UserInterfaceModule.MenuAction):
    def __init__(self, title, action_id, callback, key_sequence, role, menu, is_separator, checked):
        super().__init__(action_id)
        self.__title = title
        self.callback = callback
        self.key_sequence = key_sequence,
        self.role = role
        self.menu = menu
        self.is_separator = is_separator
        self.__checked = checked
        self.__enabled = True
    def close(self):
        self.callback = None
        super().close()
    @property
    def title(self):
        return self.__title
    @title.setter
    def title(self, value):
        self.__title = value
    @property
    def checked(self):
        return self.__checked
    @checked.setter
    def checked(self, value):
        self.__checked = value
    @property
    def enabled(self):
        return self.__enabled
    @enabled.setter
    def enabled(self, value):
        self.__enabled = value


class Menu(UserInterfaceModule.Menu):
    def __init__(self, document_window, title=None, menu_id=None):
        super().__init__(document_window, title, menu_id)
        self.on_popup = None
    def add_menu_item(self, title: str, callback: typing.Callable[[], None], key_sequence: str = None, role: str = None, action_id: str = None) -> UserInterfaceModule.MenuAction:
        menu_item = MenuItem(title, action_id, callback, key_sequence, role, None, False, False)
        self._item_added(action=menu_item)
        return menu_item
    def add_sub_menu(self, title, menu, menu_id = None):
        menu_item = MenuItem(title, menu_id, None, None, None, menu, False, False)
        self._item_added(sub_menu=menu_item.menu)
        return menu_item
    def add_separator(self):
        self._item_added(is_separator=True)
    def popup(self, gx, gy):
        if self.on_popup:
            self.on_popup(self, gx, gy)


class ItemModelController:
    DRAG = 0
    DROP = 1
    class Item:
        def __init__(self, data=None):
            self.children = []
            self.parent = None
            self.id = None
            self.data = data if data else {}
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
            if self.parent:
                return self.parent.children.index(self)
            return -1
    def __init__(self):
        self.__next_id = 0
        self.root = self.create_item()
    def close(self):
        pass
    def create_item(self, data=None):
        item = ItemModelController.Item(data)
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
    def begin_insert(self, first_row, last_row, parent_row, parent_id):
        pass
    def end_insert(self):
        pass
    def begin_remove(self, first_row, last_row, parent_row, parent_id):
        pass
    def end_remove(self):
        pass
    def data_changed(self, row, parent_row, parent_id):
        pass
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


class ListModelController:
    DRAG = 0
    DROP = 1
    def __init__(self):
        self.model = []
    def close(self):
        pass
    def begin_insert(self, first_row, last_row):
        pass
    def end_insert(self):
        pass
    def begin_remove(self, first_row, last_row):
        pass
    def end_remove(self):
        pass
    def data_changed(self):
        pass


class Key(UserInterfaceModule.Key):
    def __init__(self, text, key, modifiers):
        self.__text = text
        self.__key = key
        self.__modifiers = modifiers if modifiers else CanvasItem.KeyboardModifiers()

    @property
    def text(self) -> str:
        return self.__text

    @property
    def key(self) -> str:
        return self.__key

    @property
    def modifiers(self) -> UserInterfaceModule.KeyboardModifiers:
        return self.__modifiers

    @property
    def is_delete(self):
        return self.key == "delete"

    @property
    def is_enter_or_return(self):
        return self.key == "enter" or self.key == "return"

    @property
    def is_tab(self):
        return self.key == "tab"

    @property
    def is_arrow(self):
        return self.is_left_arrow or self.is_up_arrow or self.is_right_arrow or self.is_down_arrow

    @property
    def is_left_arrow(self):
        return self.key == "left"

    @property
    def is_up_arrow(self):
        return self.key == "up"

    @property
    def is_right_arrow(self):
        return self.key == "right"

    @property
    def is_down_arrow(self):
        return self.key == "down"

    @property
    def is_delete_to_end_of_line(self):
        return self.key == "delete_to_end_of_line"

    @property
    def is_end(self):
        return self.key == "end"

    @property
    def is_escape(self):
        return self.key == "escape"

    @property
    def is_home(self):
        return self.key == "home"

    @property
    def is_insert(self):
        return self.key == "insert"

    @property
    def is_move_to_end_of_line(self):
        return self.key == "end_of_line"

    @property
    def is_move_to_start_of_line(self):
        return self.key == "start_of_line"

    @property
    def is_page_down(self):
        return self.key == "page_down"

    @property
    def is_page_up(self):
        return self.key == "page_up"


class ButtonGroup:

    def __init__(self):
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None

    def add_button(self, radio_button, button_id):
        pass

    def remove_button(self, radio_button):
        pass

    def clicked(self, button_id):
        if self.on_button_clicked:
            self.on_button_clicked(button_id)


class Widget:

    def __init__(self, widget_type: str):
        self.widget_type = widget_type
        self.children = list()
        self.size = None
        self.on_size_changed = None

    def close(self) -> None:
        self.children = None

    def size_changed(self, size) -> None:
        if size != self.size:
            self.size = size
            if callable(self.on_size_changed):
                self.on_size_changed(size)
        for child in self.children:
            child.size_changed(size)


class WidgetBehavior:

    def __init__(self, widget_type: str, properties: typing.Mapping):
        self.widget = Widget(widget_type)
        self.widget.on_size_changed = self._size_changed
        self.does_retain_focus = False
        self.on_ui_activity = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.on_size_changed = None
        self._no_focus = "no_focus"
        self.__focused = False
        self.visible = True
        self.enabled = True
        self.size = None
        self.tool_tip = None
        self.children = list()
        self.content = None
        self.canvas_item = None

    def close(self) -> None:
        if callable(getattr(self.widget, "close", None)):
            self.widget.close()
        self.on_ui_activity = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.on_size_changed = None
        self.children = list()
        self.content = None
        self.canvas_item = None

    def _set_root_container(self, root_container):
        pass

    def _register_ui_activity(self):
        pass

    @property
    def focused(self) -> bool:
        return self.__focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        global focused_widget
        if self.__focused != focused:
            if focused and focused_widget != self:
                if focused_widget:
                    focused_widget.focused = False
                focused_widget = self
            self.__focused = focused
            if self.on_focus_changed:
                self.on_focus_changed(focused)

    def set_property(self, key: str, value) -> None:
        pass

    def _size_changed(self, size: Geometry.IntSize) -> None:
        pass

    def map_to_global(self, p):
        return p


class NullBehavior:

    def __init__(self):
        self.focused = False
        self.enabled = True
        self.visible = True

    def close(self):
        pass

    def _set_root_container(self, root_container):
        pass


class BoxStretch(UserInterfaceModule.Widget):

    def __init__(self):
        super().__init__(NullBehavior())


class BoxSpacing(UserInterfaceModule.Widget):

    def __init__(self, spacing: int):
        super().__init__(NullBehavior())
        self.spacing = spacing


def extract_widget(widget: UserInterfaceModule.Widget) -> typing.Optional[Widget]:
    if hasattr(widget, "content_widget"):
        return extract_widget(widget.content_widget)
    elif hasattr(widget, "_behavior"):
        return widget._behavior.widget
    return None


class WidgetItemType(enum.Enum):
    WIDGET = 0
    STRETCH = 1
    SPACING = 2


class WidgetItem:

    def __init__(self, type: WidgetItemType, *, widget=None, fill: bool = False, alignment: str = None, spacing: int = 0):
        self.type = type
        self.widget = widget
        self.fill = fill
        self.alignment = alignment
        self.spacing = spacing


class BoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.__widgets = list()

    def insert(self, child, index, fill, alignment):
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = index if index is not None else len(self.__widgets)
        self.__widgets.insert(index, WidgetItem(WidgetItemType.WIDGET, widget=child_widget, fill=fill, alignment=alignment))
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size)

    def add_stretch(self) -> UserInterfaceModule.Widget:
        self.__widgets.append(WidgetItem(WidgetItemType.STRETCH))
        self.widget.children.append(Widget("stretch"))
        return BoxStretch()

    def add_spacing(self, spacing: int) -> UserInterfaceModule.Widget:
        self.__widgets.append(WidgetItem(WidgetItemType.SPACING, spacing=spacing))
        self.widget.children.append(Widget("spacing"))
        return BoxSpacing(spacing)

    def remove_all(self) -> None:
        self.__widgets.clear()
        self.widget.children.clear()


class SplitterWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)

    def add(self, child: UserInterfaceModule.Widget) -> None:
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = len(self.widget.children)
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size)

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass

    def set_sizes(self, sizes: typing.Sequence[int]) -> None:
        for child, size in zip(self.widget.children, sizes):
            child.size = size


class TabWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)


class StackWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.current_index = -1

    def insert(self, child: UserInterfaceModule.Widget, index: int) -> None:
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = index if index is not None else len(self.widget.children)
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size)

    def add(self, child: UserInterfaceModule.Widget) -> None:
        child_widget = extract_widget(child)
        self.widget.children.append(child_widget)

    def remove(self, child: UserInterfaceModule.Widget) -> None:
        child_widget = extract_widget(child)
        self.widget.children.remove(child_widget)


class GroupWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)


class ScrollAreaWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.on_size_changed = None
        self.on_viewport_changed = None

    def close(self):
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    def set_content(self, content: UserInterfaceModule.Widget) -> None:
        assert not self.widget.children
        child_widget = extract_widget(content)
        self.widget.children.append(child_widget)
        child_widget.size_changed(self.widget.size)

    # called from widget
    def _size_changed(self, size: Geometry.IntSize) -> None:
        self._register_ui_activity()
        if callable(self.on_size_changed):
            self.on_size_changed(size.width, size.height)

    def scroll_to(self, x, y):
        pass

    def set_scrollbar_policies(self, horizontal_policy, vertical_policy):
        pass


class ComboBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.on_current_text_changed = None
        self.current_index = 0
        self.item_strings = list()

    def close(self):
        self.on_current_text_changed = None
        super().close()

    @property
    def current_text(self) -> str:
        return self.item_strings[self.current_index] if 0 <= self.current_index < len(self.item_strings) else str()

    @current_text.setter
    def current_text(self, value: str) -> None:
        if 0 <= self.current_index < len(self.item_strings):
            self.item_strings[self.current_index] = value

    def set_item_strings(self, item_strings: typing.Sequence[str]) -> None:
        self.item_strings = copy.copy(item_strings)


class PushButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)


class RadioButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)


class CheckBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)


class LabelWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)

    def set_text_color(self, color: str) -> None:
        pass

    def set_text_font(self, font_str: str) -> None:
        pass


class SliderWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.value = 0


class CanvasWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
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
        self.on_tool_tip = None
        self.on_pan_gesture = None
        super().close()

    def _set_canvas_item(self, canvas_item):
        pass

    def periodic(self):
        pass

    @property
    def focusable(self):
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable):
        self.__focusable = focusable

    def draw(self, drawing_context):
        pass

    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        pass

    def remove_section(self, section_id: int) -> None:
        pass

    def set_cursor_shape(self, cursor_shape):
        cursor_shape = cursor_shape or "arrow"

    def grab_gesture(self, gesture_type):
        pass

    def release_gesture(self, gesture_type):
        pass

    def grab_mouse(self, gx, gy):
        pass

    def release_mouse(self):
        pass

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        pass


class LineEditWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_text_edited = None
        self.__clear_button_enabled = False
        self._no_focus = "click_focus"
        self.text = str()
        self.placeholder_text = str()
        self.editable = True
        self.clear_button_enabled = False

    def close(self):
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def selected_text(self) -> str:
        return self.text

    def select_all(self) -> None:
        pass

    def editing_finished(self, text: str) -> None:
        self.text = text
        if self.on_editing_finished:
            self.on_editing_finished(text)


class TextEditWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)
        self.__word_wrap_mode = "optimal"
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        self._no_focus = "click_focus"
        self.text = str()
        self.selected_text = str()
        self.placeholder = str()
        self.editable = True
        self.word_wrap_mode = None

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
    def cursor_position(self) -> UserInterfaceModule.CursorPosition:
        return UserInterfaceModule.CursorPosition(0, 0, 0)

    @property
    def selection(self) -> UserInterfaceModule.Selection:
        return UserInterfaceModule.Selection(0, 0)

    def append_text(self, value: str) -> None:
        self.text += value

    def insert_text(self, value: str) -> None:
        self.text += value

    def clear_selection(self) -> None:
        pass

    def remove_selected_text(self) -> None:
        pass

    def select_all(self) -> None:
        pass

    def move_cursor_position(self, operation, mode=None, n: int = 1) -> None:
        pass

    def set_line_height_proportional(self, proportional_line_height: float) -> None:
        pass

    def set_text_background_color(self, color: str) -> None:
        pass

    def set_text_color(self, color: str) -> None:
        pass

    def set_text_font(self, font_str: str) -> None:
        pass


class TreeWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Mapping):
        super().__init__(widget_type, properties)

    def set_current_row(self, index, parent_row, parent_id):
        pass

    def clear_current_row(self):
        pass

    def size_to_content(self):
        pass


class DocumentWindowX(UserInterfaceModule.Window):

    def __init__(self, size: typing.Optional[Geometry.IntSize] = None):
        super().__init__(None, "title")
        self.__size = size if size is not None else Geometry.IntSize(height=720, width=960)
        self.__title = None

    def request_close(self):
        if self.on_about_to_close:
            self.on_about_to_close(str(), str())

    def _attach_root_widget(self, root_widget):
        extract_widget(root_widget).size_changed(self.__size)

    def _set_title(self, value: str) -> None:
        self.__title = value

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        pass

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        pass

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        pass

    @property
    def position(self) -> Geometry.IntPoint:
        return Geometry.IntPoint(x=0, y=0)

    @property
    def size(self) -> Geometry.IntSize:
        return Geometry.IntSize(w=640, h=480)

    def create_dock_widget(self, widget: UserInterfaceModule.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> UserInterfaceModule.DockWidget:
        dock_widget = DockWidget(self, widget, panel_id, title, positions, position)
        dock_widget.size_changed(Geometry.IntSize(height=320, width=480))
        return dock_widget

    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        pass

    def insert_menu(self, title: str, before_menu, menu_id: str = None) -> UserInterfaceModule.Menu:
        menu = Menu(self)
        self._menu_inserted(menu, before_menu)
        return menu

    def add_menu(self, title: str, menu_id: str = None) -> Menu:
        menu = Menu(self, menu_id)
        self._menu_added(menu)
        return menu

    def show(self, size=None, position=None):
        pass

    def restore(self, geometry, state):
        pass

    def _get_focus_widget(self):
        global focused_widget
        return focused_widget


class DockWidget(UserInterfaceModule.DockWidget):

    def __init__(self, window, widget: UserInterfaceModule.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str):
        super().__init__(window, widget, panel_id, title, positions, position)
        self.visible = False
        self.__focus_policy = "no_focus"
        self.does_retain_focus = False

    @property
    def toggle_action(self):
        action = UserInterfaceModule.MenuAction("toggle_dock_widget_" + self.panel_id)
        action.on_ui_activity = self._register_ui_activity
        return action

    def show(self):
        self.visible = True
        self._register_ui_activity()

    def hide(self):
        self.visible = False
        self._register_ui_activity()

    def size_changed(self, size: Geometry.IntSize) -> None:
        self._handle_size_changed(size)


class UserInterface(UserInterfaceModule.UserInterface):

    def __init__(self):
        CanvasItem._threaded_rendering_enabled = False
        self.clipboard = MimeData()
        self.popup = None
        self.popup_pos = None

    def close(self):
        pass

    def request_quit(self):
        pass

    def set_application_info(self, name: str, organization: str, domain: str) -> None:
        pass

    # data objects

    def create_mime_data(self) -> MimeData:
        return MimeData()

    def create_item_model_controller(self, keys):
        return ItemModelController()

    def create_button_group(self):
        return ButtonGroup()

    # window elements

    def create_document_window(self, title=None, parent_window=None):
        return DocumentWindowX()

    def destroy_document_window(self, document_window):
        document_window.close()

    def create_row_widget(self, alignment=None, properties=None):
        return UserInterfaceModule.BoxWidget(BoxWidgetBehavior("row", properties), alignment)

    def create_column_widget(self, alignment=None, properties=None):
        return UserInterfaceModule.BoxWidget(BoxWidgetBehavior("column", properties), alignment)

    def create_splitter_widget(self, orientation="vertical", properties=None):
        return UserInterfaceModule.SplitterWidget(SplitterWidgetBehavior("splitter", properties), orientation)

    def create_tab_widget(self, properties=None):
        return UserInterfaceModule.TabWidget(TabWidgetBehavior("tab", properties))

    def create_stack_widget(self, properties=None):
        return UserInterfaceModule.StackWidget(StackWidgetBehavior("stack", properties))

    def create_group_widget(self, properties=None):
        return UserInterfaceModule.GroupWidget(GroupWidgetBehavior("group", properties))

    def create_scroll_area_widget(self, properties=None):
        return UserInterfaceModule.ScrollAreaWidget(ScrollAreaWidgetBehavior("scrollarea", properties))

    def create_combo_box_widget(self, items=None, item_getter=None, properties=None):
        return UserInterfaceModule.ComboBoxWidget(ComboBoxWidgetBehavior("combobox", properties), items, item_getter)

    def create_push_button_widget(self, text=None, properties=None):
        return UserInterfaceModule.PushButtonWidget(PushButtonWidgetBehavior("pushbutton", properties), text)

    def create_radio_button_widget(self, text=None, properties=None):
        return UserInterfaceModule.RadioButtonWidget(RadioButtonWidgetBehavior("radiobutton", properties), text)

    def create_check_box_widget(self, text=None, properties=None):
        return UserInterfaceModule.CheckBoxWidget(CheckBoxWidgetBehavior("checkbox", properties), text)

    def create_label_widget(self, text=None, properties=None):
        return UserInterfaceModule.LabelWidget(LabelWidgetBehavior("label", properties), text)

    def create_slider_widget(self, properties=None):
        return UserInterfaceModule.SliderWidget(SliderWidgetBehavior("slider", properties))

    def create_progress_bar_widget(self, properties=None):
        return UserInterfaceModule.ProgressBarWidget(CanvasWidgetBehavior("canvas", properties))

    def create_line_edit_widget(self, properties=None):
        return UserInterfaceModule.LineEditWidget(LineEditWidgetBehavior("lineedit", properties))

    def create_text_edit_widget(self, properties=None):
        return UserInterfaceModule.TextEditWidget(TextEditWidgetBehavior("textedit", properties))

    def create_canvas_widget(self, properties=None, *, layout_render: str = None):
        return UserInterfaceModule.CanvasWidget(CanvasWidgetBehavior("canvas", properties), layout_render=layout_render)

    def create_tree_widget(self, properties=None):
        return UserInterfaceModule.TreeWidget(TreeWidgetBehavior("pytree", properties))

    # file i/o

    def load_rgba_data_from_file(self, filename):
        return numpy.zeros((20,20), numpy.uint32)

    def save_rgba_data_to_file(self, data, filename, format):
        pass

    def get_existing_directory_dialog(self, title, directory):
        return directory, directory

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        raise NotImplementedError()

    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        raise NotImplementedError()

    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        raise NotImplementedError()

    # persistence (associated with application)

    def get_data_location(self):
        return str()

    def get_document_location(self):
        return str()

    def get_temporary_location(self):
        return str()

    def get_configuration_location(self):
        return str()

    def get_persistent_string(self, key, default_value=None):
        return default_value

    def set_persistent_string(self, key, value):
        pass

    def get_persistent_object(self, key, default_value=None):
        return default_value

    def set_persistent_object(self, key, value):
        pass

    def remove_persistent_key(self, key):
        pass

    # clipboard

    def clipboard_clear(self):
        self.clipboard = MimeData()

    def clipboard_mime_data(self) -> MimeData:
        return self.clipboard

    def clipboard_set_mime_data(self, mime_data: MimeData) -> None:
        self.clipboard = mime_data

    def clipboard_set_text(self, text):
        self.clipboard = MimeData()
        self.clipboard.set_data_as_string('text', text)

    def clipboard_text(self):
        self.clipboard.data_as_string('text')

    # misc

    def create_rgba_image(self, drawing_context, width, height):
        return numpy.zeros((height, width), dtype=numpy.uint32)

    def get_font_metrics(self, font_str: str, text: str) -> typing.Tuple[int, int, int, int, int]:
        FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])
        return FontMetrics(width=(len(text) * 12), height=12, ascent=10, descent=2, leading=0)

    def truncate_string_to_width(self, font_str: str, text: str, pixel_width: int, mode: UserInterfaceModule.TruncateModeType) -> str:
        return text

    def get_qt_version(self) -> str:
        return "TEST"

    def get_tolerance(self, tolerance_type: UserInterfaceModule.ToleranceType) -> float:
        return 5

    def create_context_menu(self, document_window) -> UserInterfaceModule.Menu:
        menu = Menu(document_window)
        def handle_popup(menu, gx, gy):
            self.popup = menu
            self.popup_pos = gx, gy
        menu.on_popup = handle_popup
        return menu

    def create_sub_menu(self, document_window, title: str = None, menu_id: str = None) -> UserInterfaceModule.Menu:
        return Menu(document_window, title)

    # testing

    def create_key_by_id(self, key_id: str, modifiers: CanvasItem.KeyboardModifiers = None) -> UserInterfaceModule.Key:
        return Key(None, key_id, modifiers)

    def create_modifiers_by_id_list(self, modifiers_id_list: typing.Sequence[str]) -> CanvasItem.KeyboardModifiers:
        shift = False
        control = False
        alt = False
        meta = False
        keypad = False
        for modifiers_id in modifiers_id_list:
            if modifiers_id == "shift":
                shift = True
            elif modifiers_id == "control":
                control = True
            elif modifiers_id == "alt":
                alt = True
            elif modifiers_id == "meta":
                meta = True
            elif modifiers_id == "keypad":
                keypad = True
        return CanvasItem.KeyboardModifiers(shift, control, alt, meta, keypad)
