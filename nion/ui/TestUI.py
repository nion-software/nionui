# standard libraries
import collections
import numbers
import logging

# third party libraries
import numpy

# local libraries
from . import CanvasItem
from . import DrawingContext
from . import UserInterface
from nion.utils import Geometry


focused_widget = None  # simulate focus handling at the widget level


class MimeData(UserInterface.MimeData):
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


class Widget:
    def __init__(self):
        self.widget_id = None
        self.drawing_context = DrawingContext.DrawingContext()
        self.width = 640
        self.height = 480
        self.current_index = 0
        self.children = []
        self.index = -1
        self.parent_row = -1
        self.parent_id = 0
        self.current_index = -1
        self.viewport = ((0, 0), (480, 640))
        self.__size = None
        self.__focused = False
        self.on_editing_finished = None
        self.on_focus_changed = None
        self.on_text_edited = None
        self.on_periodic = None
        self.on_size_changed = None
        self.__text_binding = None
        self.__binding = None
        self.__content = None
        self.widget = None
        self.focusable = False
        self.__text = None
        self.canvas_item = None
    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None
        for child in self.children:
            child.close()
        self.children = []
        if self.content:
            self.content.close()
            self.content = None
        if self.widget:
            self.widget.close()
            self.widget = None
        if self.canvas_item:
            self.canvas_item.close()
            self.canvas_item = None
        self.delegate = None
        self.item_getter = None
        self.items = []
        self.item_model_controller = None
        self.list_model_controller = None
        self.root_container = None
        self.header_widget = None
        self.header_for_empty_list_widget = None
        self.on_check_state_changed = None
        self.on_clicked = None
        self.on_context_menu_event = None
        self.on_current_index_changed = None
        self.on_current_item_changed = None
        self.on_current_text_changed = None
        self.on_drag_enter = None
        self.on_drag_leave = None
        self.on_drag_move = None
        self.on_drop = None
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_focus_changed = None
        self.on_interpret_command = None
        self.on_item_clicked = None
        self.on_item_double_clicked = None
        self.on_item_key_pressed = None
        self.on_item_size = None
        self.on_key_pressed = None
        self.on_key_released = None
        self.on_mouse_clicked = None
        self.on_mouse_double_clicked = None
        self.on_mouse_entered = None
        self.on_mouse_exited = None
        self.on_mouse_position_changed = None
        self.on_grabbed_mouse_position_changed = None
        self.on_mouse_pressed = None
        self.on_mouse_released = None
        self.on_paint = None
        self.on_periodic = None
        self.on_return_pressed = None
        self.on_selection_changed = None
        self.on_size_changed = None
        self.on_slider_moved = None
        self.on_slider_pressed = None
        self.on_slider_released = None
        self.on_text_changed = None
        self.on_text_edited = None
        self.on_tool_tip = None
        self.on_value_changed = None
        self.on_viewport_changed = None
        self.on_wheel_changed = None
    def periodic(self):
        for child in self.children:
            child.periodic()
        if self.content:
            self.content.periodic()
        if callable(self.on_periodic):
            self.on_periodic()
    @property
    def size(self):
        return self.__size
    @size.setter
    def size(self, size):
        self.size_changed(size)
    def size_changed(self, size):
        self.__size = size
        for child in self.children:
            child.size_changed(size)
        if self.content:
            self.width = size[1] if size is not None else None
            self.height = size[0] if size is not None else None
            self.content.size_changed(size)
            if self.on_size_changed:
                self.on_size_changed(self.width, self.height)
        if self.canvas_item and size is not None:
            self.width = size[1] if size is not None else None
            self.height = size[0] if size is not None else None
            if self.on_size_changed:
                self.on_size_changed(self.width, self.height)
    def send(self, text):
        pass
    @property
    def child_count(self):
        return len(self.children)
    def add(self, widget, fill=False, alignment=None):
        self.insert(widget, len(self.children), fill, alignment)
    def insert(self, widget, before, fill=False, alignment=None):
        self.children.insert(before, widget)
        widget.size_changed(self.size)
    def remove(self, widget):
        if isinstance(widget, numbers.Integral):
            widget = self.children[widget]
        widget.close()
        self.children.remove(widget)
    def remove_all(self):
        for widget in self.children:
            widget.close()
        self.children = list()
    @property
    def content(self):
        return self.__content
    @content.setter
    def content(self, value):
        self.__content = value
        if self.__content:
            self.__content.size_changed(self.size)
    def add_stretch(self):
        self.children.append(Widget())
    def add_spacing(self, spacing):
        self.children.append(Widget())
    def draw(self, drawing_context):
        pass
    def save_state(self, tag):
        pass
    def restore_state(self, tag):
        pass
    def set_current_row(self, index, parent_row, parent_id):
        self.index = index
        self.parent_row = parent_row
        self.parent_id = parent_id
    def clear_current_row(self):
        self.set_current_row(-1, -1, 0)
    def set_selected_indexes(self, selected_indexes):
        pass
    def scroll_to(self, x, y):
        pass
    def set_scrollbar_policies(self, h, v):
        pass
    def show(self):
        pass
    def hide(self):
        pass
    def select_all(self):
        pass
    def request_refocus(self):
        pass
    @property
    def text(self):
        return self.__text
    @text.setter
    def text(self, value):
        if self.__text != value:
            self.__text = value
    def bind_text(self, binding):
        self.__text_binding = binding
        self.__text = self.__text_binding.get_target_value()
        self.__text_binding.target_setter = lambda t: setattr(self, "text", t)
        self.on_editing_finished = lambda text: self.__text_binding.update_source(text)
    def unbind_text(self):
        if self.__text_binding:
            self.__text_binding.close()
            self.__text_binding = None
    def bind_checked(self, binding):
        self.__binding = binding
        self.checked = self.__binding.get_target_value()
        self.on_checked_changed = lambda value: self.__binding.update_source(value)
    def unbind_checked(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
    def bind_check_state(self, binding):
        self.__binding = binding
        self.check_state = self.__binding.get_target_value()
    def unbind_check_state(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
    def editing_finished(self, text):
        if self.on_editing_finished:
            self.on_editing_finished(text)
    def bind_value(self, binding):
        self.__binding = binding
        self.value = self.__binding.get_target_value()
        self.on_value_changed = lambda value: self.__binding.update_source(value)
    def unbind_value(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.on_value_changed = None
    def bind_current_index(self, binding):
        self.__binding = binding
        self.value = self.__binding.get_target_value()
        self.current_item = self.items[self.value]
    def unbind_current_index(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
    @property
    def focused(self):
        return self.__focused
    @focused.setter
    def focused(self, focused):
        global focused_widget
        if self.__focused != focused:
            if focused and focused_widget != self:
                if focused_widget:
                    focused_widget.focused = False
                focused_widget = self
            self.__focused = focused
            if self.on_focus_changed:
                self.on_focus_changed(focused)
    def drag(self, mime_data: MimeData, thumbnail_data, drag_finished_fn) -> None:
        drag_finished_fn("none")
    def set_cursor_shape(self, cursor_shape):
        self.cursor_shape = cursor_shape
    def append_text(self, value):
        pass
    def insert_text(self, value):
        pass
    def move_cursor_position(self, operation, mode=None, n=1):
        pass
    def simulate_mouse_click(self, x, y, modifiers):
        if self.on_mouse_pressed:
            self.on_mouse_pressed(x, y, modifiers)
        if self.on_mouse_released:
            self.on_mouse_released(x, y, modifiers)
        if self.on_mouse_clicked:
            self.on_mouse_clicked(x, y, modifiers)
    @property
    def _contained_widgets(self):
        return [self.__content] if self.__content else self.children
    def find_widget_by_id(self, widget_id):
        if self.widget_id == widget_id:
            return self
        for contained_widget in self._contained_widgets:
            found_widget = contained_widget.find_widget_by_id(widget_id)
            if found_widget:
                return found_widget
        return None
    def size_to_content(self):
        pass
    def set_sizes(self, sizes):
        pass
    def set_property(self, k, v):
        pass


class MenuItem:
    def __init__(self, title, callback, key_sequence, role, menu, is_separator, checked):
        self.title = title
        self.callback = callback
        self.key_sequence = key_sequence,
        self.role = role
        self.menu = menu
        self.is_separator = is_separator
        self.checked = checked
    def close(self):
        self.callback = None

class Menu:
    def __init__(self):
        self.on_popup = None
        self.items = list()
    def close(self):
        for item in self.items:
            item.close()
        self.items = None
    def add_menu_item(self, title, callback, key_sequence=None, role=None):
        menu_item = MenuItem(title, callback, key_sequence, role, None, False, False)
        self.items.append(menu_item)
        return menu_item
    def add_sub_menu(self, title, menu):
        menu_item = MenuItem(title, None, None, None, menu, False, False)
        self.items.append(menu_item)
        return menu_item
    def add_separator(self):
        self.items.append(MenuItem(None, None, None, None, None, True, False))
    def popup(self, gx, gy):
        if self.on_popup:
            self.on_popup(self, gx, gy)


class DocumentWindow:
    def __init__(self, size=None):
        self.has_event_loop = False
        self.root_widget = None
        self.__menus = list()
        self.__size = size if size is not None else Geometry.IntSize(height=720, width=960)
        self.__dock_widgets = list()
        self.display_scaling = 1.0
    def close(self):
        if self.root_widget:
            self.root_widget.close()
            self.root_widget = None
        for dock_widget in self.__dock_widgets:
            dock_widget.close()
        self.__dock_widgets = None
        self.on_periodic = None
        self.on_queue_task = None
        self.on_clear_queued_tasks = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_activation_changed = None
        for menu in self.__menus:
            menu.close()
        self.__menus = None
    def request_close(self):
        if self.on_about_to_close:
            self.on_about_to_close(str(), str())
    def attach(self, root_widget):
        self.root_widget = root_widget
        self.root_widget.size_changed(self.__size)
    def detach(self):
        assert self.root_widget is not None
        self.root_widget.close()
        self.root_widget = None
    def create_dock_widget(self, widget, panel_id, title, positions, position):
        dock_widget = Widget()
        dock_widget.add(widget)
        dock_widget.size_changed(Geometry.IntSize(height=320, width=480))
        self.__dock_widgets.append(dock_widget)
        return dock_widget
    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        pass
    def insert_menu(self, title, before_menu):
        menu = Menu()
        self.__menus.append(menu)
        return menu
    def add_menu(self, title):
        menu = Menu()
        self.__menus.append(menu)
        return menu
    def show(self, size, position):
        pass
    def restore(self, geometry, state):
        pass


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


class Key(UserInterface.Key):
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
    def modifiers(self) -> UserInterface.KeyboardModifiers:
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


# define a dummy user interface to use during tests
class UserInterface:
    def __init__(self):
        CanvasItem._threaded_rendering_enabled = False
        self.popup = None
        self.popup_pos = None
        self.clipboard = MimeData()
    def close(self):
        pass
    def set_application_info(self, name: str, organization: str, domain: str) -> None:
        pass
    def create_mime_data(self) -> MimeData:
        return MimeData()
    def create_item_model_controller(self, keys):
        return ItemModelController()
    def create_document_window(self, title=None, parent_window=None):
        return DocumentWindow()
    def destroy_document_window(self, document_window):
        document_window.close()
    def create_button_group(self):
        return ButtonGroup()
    def create_row_widget(self, alignment=None, properties=None):
        return Widget()
    def create_column_widget(self, alignment=None, properties=None):
        return Widget()
    def create_splitter_widget(self, orientation="vertical", properties=None):
        return Widget()
    def create_tab_widget(self, properties=None):
        return Widget()
    def create_stack_widget(self, properties=None):
        return Widget()
    def create_scroll_area_widget(self, properties=None):
        return Widget()
    def create_combo_box_widget(self, items=None, item_getter=None, properties=None):
        widget = Widget()
        widget.items = items
        return widget
    def create_push_button_widget(self, text=None, properties=None):
        return Widget()
    def create_radio_button_widget(self, text=None, properties=None):
        return Widget()
    def create_check_box_widget(self, text=None, properties=None):
        return Widget()
    def create_label_widget(self, text=None, properties=None):
        return Widget()
    def create_slider_widget(self, properties=None):
        return Widget()
    def create_progress_bar_widget(self, properties=None):
        return Widget()
    def create_line_edit_widget(self, properties=None):
        return Widget()
    def create_text_edit_widget(self, properties=None):
        return Widget()
    def create_canvas_widget(self, properties=None):
        widget = Widget()
        widget.canvas_item = CanvasItem.RootCanvasItem(widget)
        return widget
    def create_tree_widget(self, properties=None):
        return Widget()
    def load_rgba_data_from_file(self, filename):
        return numpy.zeros((20,20), numpy.uint32)
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
    def get_data_location(self):
        return str()
    def get_document_location(self):
        return str()
    def get_temporary_location(self):
        return str()
    def create_key_by_id(self, key_id, modifiers=None):
        return Key(None, key_id, modifiers)
    def create_modifiers_by_id_list(self, modifiers_id_list):
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
    def get_font_metrics(self, font, text):
        FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])
        return FontMetrics(width=(len(text) * 12), height=12, ascent=10, descent=2, leading=0)
    def create_rgba_image(self, drawing_context, width, height):
        return numpy.zeros((height, width), dtype=numpy.uint32)
    def create_context_menu(self, document_window):
        menu = Menu()
        def handle_popup(menu, gx, gy):
            self.popup = menu
            self.popup_pos = gx, gy
        menu.on_popup = handle_popup
        return menu
    def create_sub_menu(self, document_window):
        return Menu()

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
