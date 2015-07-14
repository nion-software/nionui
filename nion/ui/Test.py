# futures
from __future__ import absolute_import

# standard libraries
import collections
import logging

# third party libraries
import numpy

# local libraries
from . import DrawingContext


focused_widget = None  # simulate focus handling at the widget level


class Widget(object):
    def __init__(self):
        self.widget = ()
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
        self.__focused = False
        self.on_focus_changed = None
        self.__binding = None
        self.content = None
        self.widget = None
        self.focusable = False
        self.content_section = None
    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        for child in self.children:
            child.close()
        self.children = []
        if self.content:
            self.content.close()
            self.content = None
        if self.widget:
            self.widget.close()
            self.widget = None
        self.delegate = None
        self.item_getter = None
        self.items = []
        self.item_model_controller = None
        self.list_model_controller = None
        self.root_container = None
        self.content_section = None
        self.header_widget = None
        self.header_for_empty_list_widget = None
        self.create_list_item_widget = None
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
        self.on_mouse_clicked = None
        self.on_mouse_double_clicked = None
        self.on_mouse_entered = None
        self.on_mouse_exited = None
        self.on_mouse_position_changed = None
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
        self.on_value_changed = None
        self.on_viewport_changed = None
        self.on_wheel_changed = None
    def periodic(self):
        pass
    def send(self, text):
        pass
    def count(self):
        return len(self.children)
    def add(self, widget, fill=False, alignment=None):
        self.insert(widget, len(self.children), fill, alignment)
    def insert(self, widget, before, fill=False, alignment=None):
        self.children.insert(before, widget)
    def remove(self, widget):
        widget.close()
        self.children.remove(widget)
    def remove_all(self):
        for widget in self.children:
            widget.close()
        self.children = list()
    def add_stretch(self):
        pass
    def add_spacing(self, spacing):
        pass
    def create_drawing_context(self, storage=None):
        return DrawingContext.DrawingContext(storage)
    def create_drawing_context_storage(self):
        return None
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
        if self.on_selection_changed:
            self.on_selection_changed([(self.index, self.parent_row, self.parent_id)])
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
    def bind_text(self, binding):
        self.__binding = binding
        self.text = self.__binding.get_target_value()
        self.__binding.target_setter = lambda t: setattr(self, "text", t)
    def bind_check_state(self, binding):
        self.__binding = binding
        self.check_state = self.__binding.get_target_value()
    def insert_item(self, item, before_index):
        item_row = self.create_list_item_widget(item)
        if not self.content_section:
            self.content_section = Widget()
        self.content_section.insert(item_row, before_index)
    def remove_item(self, index):
        pass
    def bind_items(self, binding):
        self.__binding = binding
        self.__binding.inserter = self.insert_item
        self.__binding.remover = self.remove_item
        for index, item in enumerate(binding.items):
            self.insert_item(item, index)
    def bind_value(self, binding):
        self.__binding = binding
        self.value = self.__binding.get_target_value()
    def bind_current_index(self, binding):
        self.__binding = binding
        self.value = self.__binding.get_target_value()
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
    def drag(self, mime_data, thumbnail_data, drag_finished_fn):
        drag_finished_fn("none")
    def set_cursor_shape(self, cursor_shape):
        self.cursor_shape = cursor_shape


class Menu:
    def __init__(self):
        self.on_popup = None
        self.items = list()
    def add_menu_item(self, title, callback, key_sequence=None, role=None):
        self.items.append(callback)
    def add_sub_menu(self, title, menu):
        self.items.append(menu)
    def add_separator(self):
        self.items.append(None)
    def popup(self, gx, gy):
        if self.on_popup:
            self.on_popup(self, gx, gy)


class DocumentWindow:
    def __init__(self):
        self.has_event_loop = False
        self.widget = None
    def close(self):
        if self.widget:
            self.widget.close()
        self.on_periodic = None
        self.on_queue_task = None
        self.on_add_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_activation_changed = None
    def attach(self, widget):
        self.widget = widget
    def create_dock_widget(self, widget, panel_id, title, positions, position):
        dock_widget = Widget()
        dock_widget.add(widget)
        return dock_widget
    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        pass
    def add_menu(self, title):
        return Menu()


class ItemModelController:
    DRAG = 0
    DROP = 1
    class Item(object):
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


class Key(object):
    def __init__(self, text, key, modifiers):
        self.text = text
        self.key = key
        self.modifiers = modifiers if modifiers else KeyboardModifiers()

    @property
    def is_delete(self):
        return self.key == "delete"

    @property
    def is_enter_or_return(self):
        return self.key == "enter" or self.key == "return"

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


class MimeData(object):
    def __init__(self, mime_data=None):
        self.mime_data = dict() if mime_data is None else mime_data
    @property
    def formats(self):
        return list(self.mime_data.keys())
    def has_format(self, format):
        return format in self.formats
    @property
    def has_urls(self):
        return "text/uri-list" in self.formats
    @property
    def has_file_paths(self):
        return self.has_urls
    @property
    def urls(self):
        raw_urls = self.data_as_string("text/uri-list")
        return raw_urls.splitlines() if raw_urls and len(raw_urls) > 0 else []
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


# define a dummy user interface to use during tests
class UserInterface(object):
    def __init__(self):
        self.popup = None
        self.popup_pos = None
    def create_mime_data(self):
        return MimeData()
    def create_item_model_controller(self, keys):
        return ItemModelController()
    def create_list_model_controller(self, keys):
        return ListModelController()
    def create_document_window(self):
        return DocumentWindow()
    def destroy_document_window(self, document_window):
        pass
    def tabify_dock_widgets(self, document_controller, dock_widget1, dock_widget2):
        pass
    def create_row_widget(self, properties=None):
        return Widget()
    def create_column_widget(self, properties=None):
        return Widget()
    def create_splitter_widget(self, orientation="vertical", properties=None):
        return Widget()
    def create_tab_widget(self, properties=None):
        return Widget()
    def create_stack_widget(self, properties=None):
        return Widget()
    def create_scroll_area_widget(self, properties=None):
        return Widget()
    def create_combo_box_widget(self, items=None, properties=None):
        return Widget()
    def create_push_button_widget(self, text=None, properties=None):
        return Widget()
    def create_check_box_widget(self, text=None, properties=None):
        return Widget()
    def create_label_widget(self, text=None, properties=None):
        return Widget()
    def create_slider_widget(self, properties=None):
        return Widget()
    def create_line_edit_widget(self, properties=None):
        return Widget()
    def create_text_edit_widget(self, properties=None):
        return Widget()
    def create_canvas_widget(self, properties=None):
        return Widget()
    def create_tree_widget(self, properties=None):
        return Widget()
    def create_list_widget(self, properties=None):
        return Widget()
    def create_new_list_widget(self, create_list_item_widget, header_widget=None, header_for_empty_list_widget=None, properties=None):
        widget = Widget()
        widget.create_list_item_widget = create_list_item_widget
        return widget
    def create_output_widget(self, properties=None):
        return Widget()
    def create_console_widget(self, properties=None):
        return Widget()
    def load_rgba_data_from_file(self, filename):
        return numpy.zeros((20,20), numpy.uint32)
    def get_persistent_string(self, key, default_value=None):
        return default_value
    def set_persistent_string(self, key, value):
        pass
    def get_persistent_object(self, key, default_value=None):
        pass
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
        return KeyboardModifiers(shift, control, alt, meta, keypad)
    def create_offscreen_drawing_context(self):
        return DrawingContext.DrawingContext()
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


class KeyboardModifiers(object):
    def __init__(self, shift=False, control=False, alt=False, meta=False, keypad=False):
        self.__shift = shift
        self.__control = control
        self.__alt = alt
        self.__meta = meta
        self.__keypad = keypad
    # shift
    @property
    def shift(self):
        return self.__shift
    @property
    def only_shift(self):
        return self.__shift and not self.__control and not self.__alt and not self.__meta
    # control (command key on mac)
    @property
    def control(self):
        return self.__control
    @property
    def only_control(self):
        return self.__control and not self.__shift and not self.__alt and not self.__meta
    # alt (option key on mac)
    @property
    def alt(self):
        return self.__alt
    @property
    def only_alt(self):
        return self.__alt and not self.__control and not self.__shift and not self.__meta
    # option (alt key on windows)
    @property
    def option(self):
        return self.__alt
    @property
    def only_option(self):
        return self.__alt and not self.__control and not self.__shift and not self.__meta
    # meta (control key on mac)
    @property
    def meta(self):
        return self.__meta
    @property
    def only_meta(self):
        return self.__meta and not self.__control and not self.__shift and not self.__alt
    # keypad
    @property
    def keypad(self):
        return self.__keypad
    @property
    def only_keypad(self):
        return self.__keypad
