"""
Provides a user interface object that can render to an HTML canvas.
"""

# standard libraries
import binascii
import collections
import numbers
import pickle
import queue
import threading
import time

# third party libraries
# None

# local libraries
from . import CanvasItem
from . import DrawingContext
from . import UserInterface
from nion.utils import Geometry


class WidgetBehavior:

    def __init__(self, canvas_item, properties):
        self.properties = properties if properties else {}
        self.canvas_item = canvas_item
        self.__root_container = None
        self.__is_focused = False
        self.__visible = True
        self.__enabled = True
        self.__tool_tip = None
        self.on_context_menu_event = None
        self.on_focus_changed = None

    def close(self):
        self.canvas_item = None

    def _set_root_container(self, root_container):
        self.__root_container = root_container

    @property
    def _root_container(self):
        return self.__root_container

    @property
    def focused(self):
        return self.__root_container.get_is_focused(self.canvas_item)

    @focused.setter
    def focused(self, focused):
        self.__root_container.set_is_focused(self.canvas_item, focused)

    @property
    def visible(self):
        return self.__visible

    @visible.setter
    def visible(self, visible):
        if visible != self.__visible:
            self.__root_container.set_visible(self.canvas_item, visible)
            self.__visible = visible

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled):
        if enabled != self.__enabled:
            self.__root_container.set_enabled(self.canvas_item, enabled)
            self.__enabled = enabled

    @property
    def size(self):
        return self.__root_container.get_widget_size(self.canvas_item)

    @size.setter
    def size(self, size):
        self.__root_container.set_widget_size(self.canvas_item, size)

    @property
    def tool_tip(self):
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip):
        if tool_tip != self.__tool_tip:
            self.__tool_tip = tool_tip

    def handle_drag(self, mime_data: UserInterface.MimeData, thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None):
        raise NotImplementedError()

    def handle_context_menu_event(self, x, y, gx, gy):
        if callable(self.on_context_menu_event):
            return self.on_context_menu_event(x, y, gx, gy)
        return False

    def handle_focus_in(self):
        if callable(self.on_focus_changed):
            self.on_focus_changed(True)

    def handle_focus_out(self):
        if callable(self.on_focus_changed):
            self.on_focus_changed(False)

    def map_to_global(self, p):
        return self.canvas_item.map_to_root_container(p)


def extract_canvas_item(widget):
    if hasattr(widget, "content_widget"):
        return extract_canvas_item(widget.content_widget)
    elif hasattr(widget, "_behavior"):
        return widget._behavior.canvas_item
    return None


ChildDescription = collections.namedtuple("ChildDescription", ["widget", "fill", "alignment"])


class BoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type, properties):
        super().__init__(CanvasItem.CanvasItemComposition(), properties)
        if widget_type == "row":
            self.canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        else:
            self.canvas_item.layout = CanvasItem.CanvasItemColumnLayout()

    def insert(self, child, index, fill, alignment):
        # behavior must handle index of None, meaning insert at end
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        index = index if index is not None else self.canvas_item.canvas_items_count
        # TODO: handle fille and alignment
        self.canvas_item.insert_canvas_item(index, extract_canvas_item(child))

    def add_stretch(self) -> UserInterface.Widget:
        return UserInterface.Widget(WidgetBehavior(self.canvas_item.add_stretch(), None))

    def add_spacing(self, spacing: int) -> UserInterface.Widget:
        return UserInterface.Widget(WidgetBehavior(self.canvas_item.add_spacing(spacing), None))


class PushButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, get_font_metrics_fn, properties):
        super().__init__(CanvasItem.TextButtonCanvasItem(), properties)
        self.canvas_item.font = "normal 15px sans-serif"
        self.canvas_item.on_button_clicked = self.__clicked
        self.on_clicked = None
        self.__get_font_metrics_fn = get_font_metrics_fn

    def close(self):
        self.on_clicked = None
        super().close()

    @property
    def text(self):
        return self.canvas_item.text

    @text.setter
    def text(self, text):
        self.canvas_item.text = text
        self.canvas_item.size_to_content(self.__get_font_metrics_fn)

    @property
    def icon(self):
        return self.__icon

    @icon.setter
    def icon(self, rgba_image):  # bgra
        self.__icon = rgba_image
        self.__width = rgba_image.shape[1] if rgba_image is not None else 0
        self.__height = rgba_image.shape[0] if rgba_image is not None else 0

    def __clicked(self):
        if callable(self.on_clicked):
            self.on_clicked()


class CheckBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, get_font_metrics_fn, properties):
        super().__init__(CanvasItem.CheckBoxCanvasItem(), properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.canvas_item.font = "normal 15px sans-serif"
        self.on_check_state_changed = None

        def check_state_changed(check_state):
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        self.canvas_item.on_check_state_changed = check_state_changed

    def close(self):
        self.on_check_state_changed = None
        super().close()

    @property
    def text(self):
        return self.canvas_item.text

    @text.setter
    def text(self, value):
        self.canvas_item.text = value
        self.canvas_item.size_to_content(self.__get_font_metrics_fn)

    @property
    def tristate(self):
        return self.canvas_item.tristate

    @tristate.setter
    def tristate(self, value):
        self.canvas_item.tristate = value

    @property
    def check_state(self):
        return self.canvas_item.check_state

    @check_state.setter
    def check_state(self, value):
        self.canvas_item.check_state = value


class LabelWidgetBehavior(WidgetBehavior):

    def __init__(self, get_font_metrics_fn, properties):
        super().__init__(CanvasItem.StaticTextCanvasItem(), properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__text = None

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, text):
        self.__text = text if text else ""
        self.canvas_item.text = self.text
        self.canvas_item.size_to_content(self.__get_font_metrics_fn)


class CanvasWidgetBehavior(WidgetBehavior):

    def __init__(self, properties):
        super().__init__(CanvasItem.CanvasItemComposition(), properties)
        self.on_periodic = None
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
        self.width = properties.get("width", 0) if properties else 0
        self.height = properties.get("height", 0) if properties else 0
        self.__focusable = False
        self.__draw_mutex = threading.Lock()  # don't delete while drawing
        if self.width > 0:
            self.canvas_item.sizing.set_fixed_width(self.width)
        if self.height > 0:
            self.canvas_item.sizing.set_fixed_height(self.height)

    def close(self):
        with self.__draw_mutex:
            # if self.canvas_item:
            #     self.canvas_item.close()
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
        self.canvas_item.add_canvas_item(canvas_item)

    def periodic(self):
        if callable(self.on_periodic):
            self.on_periodic()

    @property
    def canvas_size(self):
        return self.height, self.width

    @property
    def focusable(self):
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable):
        self.__focusable = focusable
        self._root_container.set_focusable(self, focusable)

    def draw(self, drawing_context):
        # thread safe. take care to make sure widget hasn't been deleted from underneath.
        with self.__draw_mutex:
            if self._root_container:
                self._root_container.draw(self.canvas_item, drawing_context)

    def set_cursor_shape(self, cursor_shape):
        pass

    def handle_mouse_entered(self):
        if callable(self.on_mouse_entered):
            self.on_mouse_entered()

    def handle_mouse_exited(self):
        if callable(self.on_mouse_exited):
            self.on_mouse_exited()

    def handle_mouse_clicked(self, x, y, modifiers):
        if callable(self.on_mouse_clicked):
            self.on_mouse_clicked(x, y, modifiers)

    def handle_mouse_double_clicked(self, x, y, modifiers):
        if callable(self.on_mouse_double_clicked):
            self.on_mouse_double_clicked(x, y, modifiers)

    def handle_mouse_pressed(self, x, y, modifiers):
        if callable(self.on_mouse_pressed):
            self.on_mouse_pressed(x, y, modifiers)

    def handle_mouse_released(self, x, y, modifiers):
        if callable(self.on_mouse_released):
            self.on_mouse_released(x, y, modifiers)

    def handle_mouse_position_changed(self, x, y, modifiers):
        if callable(self.on_mouse_position_changed):
            self.on_mouse_position_changed(x, y, modifiers)

    def handle_grabbed_mouse_position_changed(self, dx, dy, modifiers):
        if callable(self.on_grabbed_mouse_position_changed):
            self.on_grabbed_mouse_position_changed(dx, dy, modifiers)

    def handle_wheel_changed(self, x, y, dx, dy, is_horizontal):
        if callable(self.on_wheel_changed):
            self.on_wheel_changed(x, y, dx, dy, is_horizontal)

    def handle_size_changed(self, width, height):
        self.width = width
        self.height = height
        if self.width > 0:
            self.canvas_item.sizing.set_fixed_width(self.width)
        if self.height > 0:
            self.canvas_item.sizing.set_fixed_height(self.height)
        if callable(self.on_size_changed):
            self.on_size_changed(self.width, self.height)

    def handle_key_pressed(self, key):
        if callable(self.on_key_pressed):
            return self.on_key_pressed(key)
        return False

    def handle_key_released(self, key):
        if callable(self.on_key_released):
            return self.on_key_released(key)
        return False

    def handle_drag_enter_event(self, mime_data: UserInterface.MimeData) -> str:
        if callable(self.on_drag_enter):
            return self.on_drag_enter(mime_data)
        return "ignore"

    def handle_drag_leave_event(self):
        if callable(self.on_drag_leave):
            return self.on_drag_leave()
        return "ignore"

    def handle_drag_move_event(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        if callable(self.on_drag_move):
            return self.on_drag_move(mime_data, x, y)
        return "ignore"

    def handle_drop_event(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        if callable(self.on_drop):
            return self.on_drop(mime_data, x, y)
        return "ignore"

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        if callable(self.on_tool_tip):
            return self.on_tool_tip(x, y, gx, gy)
        return False

    def grab_gesture(self, gesture_type):
        self._root_container.grab_geture(self, gesture_type)

    def release_gesture(self, gesture_type):
        self._root_container.release_gesture(self, gesture_type)

    def handle_pan_gesture(self, delta_x, delta_y) -> bool:
        if callable(self.on_pan_gesture):
            return self.on_pan_gesture(delta_x, delta_y)
        return False


class Window(UserInterface.Window):

    def __init__(self, ui, parent_window, title):
        super().__init__(parent_window, title)
        self.ui = ui

    def close(self):
        super().close()

    # attach the root widget to this window
    # the root widget must either respond to _set_root_container or canvas_item
    def attach(self, root_widget):
        if not isinstance(root_widget, UserInterface.CanvasWidget):
            canvas_widget = self.ui.create_canvas_widget()
            canvas_widget.canvas_item.add_canvas_item(extract_canvas_item(root_widget))
            root_widget._set_root_container(self)
            root_widget = canvas_widget
        # root_widget should be a CanvasWidget
        super().attach(root_widget)
        size = self.__size
        if size is not None:
            self.root_widget._behavior.handle_size_changed(size.width, size.height)

    def _attach_root_widget(self, root_widget):
        pass

    # periodic is called periodically from the user interface object to service the window.
    def periodic(self):
        self._handle_periodic()

    # call show to display the window.
    def show(self, size=None, position=None):
        if self.on_about_to_show:
            self.on_about_to_show()

    def _set_title(self, value):
        pass

    def draw(self, canvas_item, drawing_context):
        """Render the drawing context by called draw on the ui object."""
        assert canvas_item == self.root_widget._behavior.canvas_item
        self.ui._draw(drawing_context)

    # called when the document size changes
    # typically by the UI object
    def handle_size_changed(self, size):
        self.__size = size
        if self.root_widget:
            if size is not None:
                self.root_widget._behavior.handle_size_changed(size.width, size.height)
        self._handle_size_changed(size.width, size.height)


class CanvasUserInterface(UserInterface.UserInterface):

    def __init__(self, draw_fn, get_font_metrics_fn):
        self.persistence_root = "0"
        self.__draw_fn = draw_fn
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__done = False
        self.__document_windows = list()

    def close(self):
        self.__done = True

    def run(self, event_queue):
        """Run the Python event loop.

        Wait for messages to arrive on event_queue and process them.
        """
        start = time.time()
        while not self.__done and time.time() - start < 1000.0:
            try:
                event_dict = event_queue.get(timeout=1/50.0)
                event_type = event_dict.get("type")
                document_window = self.__document_windows[0] if len(self.__document_windows) > 0 else None
                root_widget = document_window.root_widget if document_window else None

                if event_type == "quit":
                    return 0

                if root_widget:
                    if event_type == "mouse_enter":
                        root_widget._behavior.handle_mouse_entered()
                    elif event_type == "mouse_leave":
                        root_widget._behavior.handle_mouse_exited()
                    elif event_type == "mouse_down":
                        root_widget._behavior.handle_mouse_pressed(event_dict.get("x", 0.0), event_dict.get("y", 0.0), CanvasItem.KeyboardModifiers())
                    elif event_type == "mouse_up":
                        root_widget._behavior.handle_mouse_released(event_dict.get("x", 0.0), event_dict.get("y", 0.0), CanvasItem.KeyboardModifiers())
                    elif event_type == "mouse_move":
                        root_widget._behavior.handle_mouse_position_changed(event_dict.get("x", 0.0), event_dict.get("y", 0.0), CanvasItem.KeyboardModifiers())
                    elif event_type == "click":
                        root_widget._behavior.handle_mouse_clicked(event_dict.get("x", 0.0), event_dict.get("y", 0.0), CanvasItem.KeyboardModifiers())
                    elif event_type == "double_click":
                        root_widget._behavior.handle_mouse_double_clicked(event_dict.get("x", 0.0), event_dict.get("y", 0.0), CanvasItem.KeyboardModifiers())
                event_queue.task_done()
            except queue.Empty as e:
                pass
            try:
                for document_window in self.__document_windows:
                    document_window.periodic()
            except Exception as e:
                import traceback
                traceback.print_exc()
                traceback.print_stack()

    def _draw(self, drawing_context):
        """Render the drawing context.

        This will be called from the Window, which will, in turn, be called from a thread from its
        RootCanvasItem object."""
        dc = DrawingContext.DrawingContext()
        canvas_width = 960
        canvas_height = 720
        with dc.saver():
            dc.begin_path()
            dc.rect(0, 0, canvas_width, canvas_height)
            dc.fill_style = "#FFF"
            dc.fill()
        dc.add(drawing_context)
        self.__draw_fn(dc)

    # data objects

    def create_mime_data(self) -> UserInterface.MimeData:
        raise NotImplementedError()

    def create_item_model_controller(self, keys):
        raise NotImplementedError()

    def create_button_group(self):
        raise NotImplementedError()

    # window elements

    def create_document_window(self, title=None, parent_window=None):
        document_window = Window(self, parent_window, title)
        self.__document_windows.append(document_window)
        document_window.handle_size_changed(Geometry.IntSize(height=720, width=960))
        return document_window

    def destroy_document_window(self, document_window):
        if document_window in self.__document_windows:
            self.__document_windows.remove(document_window)

    # user interface elements

    def create_row_widget(self, alignment=None, properties=None):
        return UserInterface.BoxWidget(BoxWidgetBehavior("row", properties), alignment)

    def create_column_widget(self, alignment=None, properties=None):
        return UserInterface.BoxWidget(BoxWidgetBehavior("column", properties), alignment)

    def create_splitter_widget(self, orientation="vertical", properties=None):
        raise NotImplementedError()

    def create_tab_widget(self, properties=None):
        raise NotImplementedError()

    def create_stack_widget(self, properties=None):
        raise NotImplementedError()

    def create_scroll_area_widget(self, properties=None):
        raise NotImplementedError()

    def create_combo_box_widget(self, items=None, item_getter=None, properties=None):
        raise NotImplementedError()

    def create_push_button_widget(self, text=None, properties=None):
        return UserInterface.PushButtonWidget(PushButtonWidgetBehavior(self.__get_font_metrics_fn, properties), text)

    def create_radio_button_widget(self, text: str=None, properties=None):
        raise NotImplementedError()

    def create_check_box_widget(self, text=None, properties=None):
        return UserInterface.CheckBoxWidget(CheckBoxWidgetBehavior(self.__get_font_metrics_fn, properties), text)

    def create_label_widget(self, text=None, properties=None):
        return UserInterface.LabelWidget(LabelWidgetBehavior(self.get_font_metrics, properties), text)

    def create_slider_widget(self, properties=None):
        raise NotImplementedError()

    def create_progress_bar_widget(self, properties=None):
        raise NotImplementedError()

    def create_line_edit_widget(self, properties=None):
        raise NotImplementedError()

    def create_text_edit_widget(self, properties=None):
        raise NotImplementedError()

    def create_canvas_widget(self, properties=None):
        return UserInterface.CanvasWidget(CanvasWidgetBehavior(properties))

    def create_tree_widget(self, properties=None):
        raise NotImplementedError()

    # file i/o

    def load_rgba_data_from_file(self, filename):
        # returns data packed as uint32
        raise NotImplementedError()

    def save_rgba_data_to_file(self, data, filename, format):
        raise NotImplementedError()

    def get_existing_directory_dialog(self, title, directory):
        raise NotImplementedError()

    # persistence (associated with application)

    def get_data_location(self):
        raise NotImplementedError()

    def get_document_location(self):
        raise NotImplementedError()

    def get_temporary_location(self):
        raise NotImplementedError()

    def get_persistent_string(self, key, default_value=None):
        raise NotImplementedError()

    def set_persistent_string(self, key, value):
        raise NotImplementedError()

    def get_persistent_object(self, key, default_value=None):
        key = "/".join([self.persistence_root, key])
        value = self.get_persistent_string(key)
        return pickle.loads(binascii.unhexlify(value.encode("utf-8"))) if value else default_value

    def set_persistent_object(self, key, value):
        key = "/".join([self.persistence_root, key])
        self.set_persistent_string(key, binascii.hexlify(pickle.dumps(value, 0)).decode("utf-8"))

    def remove_persistent_key(self, key):
        raise NotImplementedError()

    # clipboard

    def clipboard_clear(self):
        raise NotImplementedError()

    def clipboard_mime_data(self) -> UserInterface.MimeData:
        raise NotImplementedError()

    def clipboard_set_mime_data(self, mime_data: UserInterface.MimeData) -> None:
        raise NotImplementedError()

    def clipboard_set_text(self, text):
        raise NotImplementedError()

    def clipboard_text(self):
        raise NotImplementedError()

    # misc

    def create_rgba_image(self, drawing_context, width, height):
        raise NotImplementedError()

    def get_font_metrics(self, font, text):
        return self.__get_font_metrics_fn(font, text)

    def create_context_menu(self, document_window):
        raise NotImplementedError()

    def create_sub_menu(self, document_window):
        raise NotImplementedError()
