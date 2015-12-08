"""
Provides a user interface object that can render to an HTML canvas.
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
import collections
import copy
import json
import threading
import time

# conditional imports
import sys
if sys.version < '3':
    import Queue as queue
else:
    import queue

# third party libraries
# None

# local libraries
from . import DrawingContext
from . import Geometry
from . import Unicode

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


class CanvasWidget(object):

    def __init__(self, properties):
        self.properties = properties if properties else {}
        self.__root_container = None  # the document window
        self.update_properties()
        self.__visible = True
        self.__enabled = True
        self.__tool_tip = None
        self.on_context_menu_event = None
        self.on_focus_changed = None

    # subclasses should override to clear their variables.
    # subclasses should NOT call Qt code to delete anything here... that is done by the Qt code
    def close(self):
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.__root_container = None

    @property
    def root_container(self):
        return self.__root_container

    def _set_root_container(self, root_container):
        self.__root_container = root_container

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

    def update_properties(self):
        pass

    @property
    def focused(self):
        return self.__root_container.is_focused(self)

    @focused.setter
    def focused(self, focused):
        self.__root_container.set_focused(self, focused)

    @property
    def visible(self):
        return self.__visible

    @visible.setter
    def visible(self, visible):
        if visible != self.__visible:
            self.__root_container.set_visible(self, visible)
            self.__visible = visible

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled):
        if enabled != self.__enabled:
            self.__root_container.set_enabled(self, enabled)
            self.__enabled = enabled

    @property
    def size(self):
        raise NotImplementedError()

    @size.setter
    def size(self, size):
        self.__root_container.set_widget_size(self, size)

    @property
    def tool_tip(self):
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip):
        if tool_tip != self.__tool_tip:
            self.__tool_tip = tool_tip

    def handle_drag(self, mime_data, thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None):
        raise NotImplementedError()

    def handle_context_menu_event(self, x, y, gx, gy):
        if self.on_context_menu_event:
            return self.on_context_menu_event(x, y, gx, gy)
        return False

    def handle_focus_in(self):
        if self.on_focus_changed:
            self.on_focus_changed(True)

    def handle_focus_out(self):
        if self.on_focus_changed:
            self.on_focus_changed(False)


class DrawingContextStorage(object):

    def __init__(self):
        self.__storage = dict()
        self.__keys_to_remove = list()

    def close(self):
        self.__storage = None

    def mark(self):
        self.__keys_to_remove = list(self.__storage.keys())

    def clean(self):
        list(map(self.__storage.__delitem__, self.__keys_to_remove))

    def begin_layer(self, drawing_context, layer_id):
        self.__storage.setdefault(layer_id, dict())["start"] = len(drawing_context.commands)

    def end_layer(self, drawing_context, layer_id):
        start = self.__storage.get(layer_id, dict())["start"]
        self.__storage.setdefault(layer_id, dict())["commands"] = copy.copy(drawing_context.commands[start:])

    def draw_layer(self, drawing_context, layer_id):
        commands = self.__storage.get(layer_id, dict())["commands"]
        drawing_context.commands.extend(commands)
        self.__keys_to_remove.remove(layer_id)


class CanvasCanvasWidget(CanvasWidget):

    def __init__(self, properties):
        super(CanvasCanvasWidget, self).__init__(properties)
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
        self.on_size_changed = None
        self.on_drag_enter = None
        self.on_drag_leave = None
        self.on_drag_move = None
        self.on_drop = None
        self.width = 0
        self.height = 0
        self.__focusable = False
        self.__draw_mutex = threading.Lock()  # don't delete while drawing

    def close(self):
        with self.__draw_mutex:
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
            self.on_size_changed = None
            self.on_drag_enter = None
            self.on_drag_leave = None
            self.on_drag_move = None
            self.on_drop = None
            super(CanvasCanvasWidget, self).close()

    def periodic(self):
        super(CanvasCanvasWidget, self).periodic()
        if self.on_periodic:
            self.on_periodic()

    @property
    def canvas_item(self):
        return self

    @property
    def canvas_size(self):
        return (self.height, self.width)

    @property
    def focusable(self):
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable):
        self.__focusable = focusable
        self.root_container.set_focusable(self, focusable)

    def create_drawing_context(self, storage=None):
        return DrawingContext.DrawingContext(storage)

    def create_drawing_context_storage(self):
        return DrawingContextStorage()

    def draw(self, drawing_context, drawing_context_storage):
        # thread safe. take care to make sure widget hasn't been deleted from underneath.
        with self.__draw_mutex:
            if self.root_container:
                self.root_container.draw(self, drawing_context, drawing_context_storage)

    def set_cursor_shape(self, cursor_shape):
        pass

    def handle_mouse_entered(self):
        if self.on_mouse_entered:
            self.on_mouse_entered()

    def handle_mouse_exited(self):
        if self.on_mouse_exited:
            self.on_mouse_exited()

    def handle_mouse_clicked(self, x, y, modifiers):
        if self.on_mouse_clicked:
            self.on_mouse_clicked(x, y, modifiers)

    def handle_mouse_double_clicked(self, x, y, modifiers):
        if self.on_mouse_double_clicked:
            self.on_mouse_double_clicked(x, y, modifiers)

    def handle_mouse_pressed(self, x, y, modifiers):
        if self.on_mouse_pressed:
            self.on_mouse_pressed(x, y, modifiers)

    def handle_mouse_released(self, x, y, modifiers):
        if self.on_mouse_released:
            self.on_mouse_released(x, y, modifiers)

    def handle_mouse_position_changed(self, x, y, modifiers):
        if self.on_mouse_position_changed:
            self.on_mouse_position_changed(x, y, modifiers)

    def handle_grabbed_mouse_position_changed(self, dx, dy, modifiers):
        if self.on_grabbed_mouse_position_changed:
            self.on_grabbed_mouse_position_changed(dx, dy, modifiers)

    def handle_wheel_changed(self, dx, dy, is_horizontal):
        if self.on_wheel_changed:
            self.on_wheel_changed(dx, dy, is_horizontal)

    def handle_size_changed(self, width, height):
        self.width = width
        self.height = height
        if self.on_size_changed:
            self.on_size_changed(self.width, self.height)

    def handle_key_pressed(self, key):
        if self.on_key_pressed:
            return self.on_key_pressed(key)
        return False

    def handle_drag_enter_event(self, mime_data):
        if self.on_drag_enter:
            return self.on_drag_enter(mime_data)
        return "ignore"

    def handle_drag_leave_event(self):
        if self.on_drag_leave:
            return self.on_drag_leave()
        return "ignore"

    def handle_drag_move_event(self, mime_data, x, y):
        if self.on_drag_move:
            return self.on_drag_move(mime_data, x, y)
        return "ignore"

    def handle_drop_event(self, mime_data, x, y):
        if self.on_drop:
            return self.on_drop(mime_data, x, y)
        return "ignore"

    def grab_gesture(self, gesture_type):
        self.root_container.grab_geture(self, gesture_type)

    def release_gesture(self, gesture_type):
        self.root_container.release_gesture(self, gesture_type)

    def handle_pan_gesture(self, delta_x, delta_y):
        if self.on_pan_gesture:
            self.on_pan_gesture(delta_x, delta_y)


class CanvasDocumentWindow(object):

    def __init__(self, ui):
        self.ui = ui
        self.root_widget = None  # a CanvasCanvasWidget
        self.has_event_loop = True
        self.on_periodic = None
        self.on_queue_task = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None  # when code shows the window
        self.on_about_to_close = None  # when user closes the window
        self.__title = Unicode.u()

    def close(self):
        self.root_widget.close()
        self.root_widget = None
        self.on_periodic = None
        self.on_queue_task = None
        self.on_add_task = None
        self.on_clear_task = None
        self.on_about_to_show = None
        self.on_about_to_close = None
        self.on_activation_changed = None

    # attach the root widget to this window
    # the root widget must respond to _set_root_container
    def attach(self, root_widget):
        # root_widget should be a CanvasCanvasWidget
        self.root_widget = root_widget
        self.root_widget._set_root_container(self)
        size = self.__size
        if size is not None:
            self.root_widget.handle_size_changed(size.width, size.height)

    # periodic is called periodically from the user interface object to service the window.
    def periodic(self):
        if self.root_widget:
            self.root_widget.periodic()
        if self.on_periodic:
            self.on_periodic()

    # call show to display the window.
    def show(self):
        if self.on_about_to_show:
            self.on_about_to_show()

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
    def title(self):
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = value

    def draw(self, widget, drawing_context, drawing_context_storage):
        assert widget == self.root_widget
        self.ui._draw(drawing_context, drawing_context_storage)

    # called when the document size changes
    # typically by the UI object
    def handle_size_changed(self, size):
        self.__size = size
        if self.root_widget:
            if size is not None:
                self.root_widget.handle_size_changed(size.width, size.height)


class CanvasUserInterface(object):

    def __init__(self, draw_fn, get_font_metrics_fn):
        self.__draw_fn = draw_fn
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__done = False
        self.__document_windows = list()

    def close(self):
        self.__done = True

    def run(self, event_queue):
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
                        root_widget.handle_mouse_entered()
                    elif event_type == "mouse_leave":
                        root_widget.handle_mouse_exited()
                    elif event_type == "mouse_down":
                        root_widget.handle_mouse_pressed(event_dict.get("x", 0.0), event_dict.get("y", 0.0), KeyboardModifiers())
                    elif event_type == "mouse_up":
                        root_widget.handle_mouse_released(event_dict.get("x", 0.0), event_dict.get("y", 0.0), KeyboardModifiers())
                    elif event_type == "mouse_move":
                        root_widget.handle_mouse_position_changed(event_dict.get("x", 0.0), event_dict.get("y", 0.0), KeyboardModifiers())
                    elif event_type == "click":
                        root_widget.handle_mouse_clicked(event_dict.get("x", 0.0), event_dict.get("y", 0.0), KeyboardModifiers())
                    elif event_type == "double_click":
                        root_widget.handle_mouse_double_clicked(event_dict.get("x", 0.0), event_dict.get("y", 0.0), KeyboardModifiers())
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

    def create_document_window(self, title=None):
        document_window = CanvasDocumentWindow(self)
        self.__document_windows.append(document_window)
        document_window.handle_size_changed(Geometry.IntSize(height=800, width=1200))
        return document_window

    def destroy_document_window(self, document_window):
        if document_window in self.__document_windows:
            self.__document_windows.remove(document_window)

    def create_canvas_widget(self, properties=None):
        return CanvasCanvasWidget(properties)

    def create_canvas_widget_new(self, properties=None):
        return CanvasCanvasWidget(properties)

    def get_font_metrics(self, font, text):
        return self.__get_font_metrics_fn(font, text)

    def _draw(self, drawing_context, drawing_context_storage):
        self.__draw_fn(drawing_context, drawing_context_storage)
