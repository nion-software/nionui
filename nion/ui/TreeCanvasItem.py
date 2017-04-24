"""Display a tree of drawable cells.
"""

# standard libraries
import copy
import functools
import json

# third party libraries
# none

# local libraries
from . import CanvasItem
from nion.utils import Geometry


class TreeCanvasItem(CanvasItem.CanvasItemComposition):
    """
    Takes a delegate that supports the following properties, methods, and optional methods:

    Properties:
        None

    Methods:
        toggle_is_expanded(value_path) -> None
        build_items(get_font_metrics_fn, item_width) -> CanvasItem

    Optional methods:
        None

    Call reconstruct when data or selection changes.
    """

    def __init__(self, get_font_metrics_fn, delegate):
        super().__init__()
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__delegate = delegate
        # configure super
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__mouse_pressed = False
        self.__mouse_index = None
        self.__mouse_position = None
        self.__mouse_dragging = False
        self.__mouse_item = None
        self.__selected_value_paths = set()
        self.layout = CanvasItem.CanvasItemColumnLayout()
        self.on_content_height_changed = None

    def close(self):
        self.on_content_height_changed = None
        super().close()

    def __is_selected(self, value_path):
        return json.dumps(value_path) in self.__selected_value_paths

    def reconstruct(self):
        for canvas_item in copy.copy(self.canvas_items):
            self._remove_canvas_item(canvas_item)
        indent_size = 16
        canvas_bounds = self.canvas_bounds
        item_width = int(canvas_bounds.width) if canvas_bounds else None
        canvas_height = 0
        ITEM_HEIGHT = 18
        for canvas_item, item_type, is_expanded, value_path in self.__delegate.build_items(
                self.__get_font_metrics_fn, item_width):
            indent = (len(value_path) - 1) * indent_size
            item_row = CanvasItem.CanvasItemComposition()
            item_row.sizing.set_fixed_height(ITEM_HEIGHT)
            item_row.layout = CanvasItem.CanvasItemRowLayout()
            item_row.add_spacing(indent)
            if item_type == "parent":
                twist_down_canvas_item = CanvasItem.TwistDownCanvasItem()
                twist_down_canvas_item.sizing.set_fixed_size(Geometry.IntSize(height=ITEM_HEIGHT, width=16))
                twist_down_canvas_item.checked = is_expanded

                def twist_down_clicked(toggle_value_path):
                    self.__toggle_is_expanded(toggle_value_path)

                twist_down_canvas_item.on_button_clicked = functools.partial(twist_down_clicked, value_path)
                item_row.add_canvas_item(twist_down_canvas_item)
            else:
                item_row.add_spacing(indent_size)
            item_row.add_canvas_item(canvas_item)
            item_row.add_stretch()
            item_row.value_path = value_path
            self.add_canvas_item(item_row)
            canvas_height += ITEM_HEIGHT
        self.update()
        if callable(self.on_content_height_changed):
            self.on_content_height_changed(canvas_height)

    def __set_selection(self, value_path):
        self.__selected_value_paths.clear()
        self.__selected_value_paths.add(json.dumps(value_path))

    def __extend_selection(self, value_path):
        pass

    def __toggle_selection(self, value_path):
        value_path_key = json.dumps(value_path)
        if value_path_key in self.__selected_value_paths:
            self.__selected_value_paths.remove(value_path_key)
        else:
            self.__selected_value_paths.add(value_path_key)

    def __toggle_is_expanded(self, value_path):
        self.__delegate.toggle_is_expanded(value_path)
        self.reconstruct()

    def __context_menu_event(self, value_path, x, y, gx, gy):
        pass

    def __drag_started(self, value_path, x, y, modifiers):
        pass

    def __delete(self):
        pass

    def __adjust_selection(self, action, extend):
        pass

    def __value_path_at_point(self, p):
        for canvas_item in self.canvas_items_at_point(p.x, p.y):
            if hasattr(canvas_item, "value_path"):
                return canvas_item.value_path
        return None

    def context_menu_event(self, x, y, gx, gy):
        p = Geometry.IntPoint(y=y, x=x)
        value_path = self.__value_path_at_point(p)
        if value_path:
            if not self.__is_selected(value_path):
                self.__set_selection(value_path)
            return self.__context_menu_event(value_path, x, y, gx, gy)
        return self.__context_menu_event(None, x, y, gx, gy)

    def mouse_pressed(self, x, y, modifiers):
        p = Geometry.IntPoint(y=y, x=x)
        value_path = self.__value_path_at_point(p)
        if value_path:
            if modifiers.shift:
                self.__extend_selection(value_path)
            elif modifiers.control:
                self.__toggle_selection(value_path)
            else:
                self.__set_selection(value_path)
                self.__mouse_pressed = True
                self.__mouse_position = Geometry.IntPoint(y=y, x=x)
                self.__mouse_item = value_path
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        if self.__mouse_pressed:
            # double check whether mouse_released has been called explicitly as part of a drag.
            # see https://bugreports.qt.io/browse/QTBUG-40733
            pass  # leave this here for future reference
        self.__mouse_pressed = False
        self.__mouse_item = None
        self.__mouse_position = None
        self.__mouse_dragging = False
        return True

    def mouse_position_changed(self, x, y, modifiers):
        if self.__mouse_pressed:
            if not self.__mouse_dragging and Geometry.distance(self.__mouse_position, Geometry.IntPoint(y=y, x=x)) > 8:
                self.__mouse_dragging = True
                self.__drag_started(self.__mouse_item, x, y, modifiers)
                # once a drag starts, mouse release will not be called; call it here instead
                self.mouse_released(x, y, modifiers)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def key_pressed(self, key):
        if key.is_delete:
            self.__delete()
            return True
        if key.is_up_arrow:
            self.__adjust_selection("up", key.modifiers.shift)
            return True
        if key.is_down_arrow:
            self.__adjust_selection("down", key.modifiers.shift)
            return True
        return super().key_pressed(key)

    def handle_select_all(self):
        self.__adjust_selection("all", False)
        return True
