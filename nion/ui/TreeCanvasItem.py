"""Display a tree of drawable cells.
"""

from __future__ import annotations

# standard libraries
import copy
import dataclasses
import functools
import json
import typing

# third party libraries
# none

# local libraries
from nion.ui import CanvasItem
from nion.ui import UserInterface
from nion.utils import Geometry

_ValuePath = typing.Sequence[typing.Union[int, str]]


@dataclasses.dataclass
class TreeItem:
    canvas_item: CanvasItem.AbstractCanvasItem
    item_type: str
    is_expanded: bool
    value_path: _ValuePath


class TreeCanvasItemDelegate(typing.Protocol):

    def build_items(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics],
                    item_width: typing.Optional[int]) -> typing.Sequence[TreeItem]: ...

    def toggle_is_expanded(self, value_path_key: str) -> None: ...


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

    def __init__(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics], delegate: TreeCanvasItemDelegate) -> None:
        super().__init__()
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__delegate = delegate
        # configure super
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__mouse_pressed = False
        self.__mouse_index: typing.Optional[int] = None
        self.__mouse_position: typing.Optional[Geometry.IntPoint] = None
        self.__mouse_dragging = False
        self.__mouse_item: typing.Optional[_ValuePath] = None
        self.__selected_value_paths: typing.Set[str] = set()
        self.layout = CanvasItem.CanvasItemColumnLayout()
        self.on_content_height_changed: typing.Optional[typing.Callable[[int], None]] = None

    def close(self) -> None:
        self.on_content_height_changed = None
        super().close()

    def __is_selected(self, value_path: _ValuePath) -> bool:
        return json.dumps(value_path) in self.__selected_value_paths

    def reconstruct(self) -> None:
        for canvas_item in copy.copy(self.canvas_items):
            self._remove_canvas_item(canvas_item)
        indent_size = 16
        canvas_bounds = self.canvas_bounds
        item_width = int(canvas_bounds.width) if canvas_bounds else None
        canvas_height = 0
        ITEM_HEIGHT = 18
        for tree_item in self.__delegate.build_items(self.__get_font_metrics_fn, item_width):
            indent = (len(tree_item.value_path) - 1) * indent_size
            item_row = CanvasItem.CanvasItemComposition()
            item_row.update_sizing(item_row.sizing.with_fixed_height(ITEM_HEIGHT))
            item_row.layout = CanvasItem.CanvasItemRowLayout()
            item_row.add_spacing(indent)
            if tree_item.item_type == "parent":
                twist_down_canvas_item = CanvasItem.TwistDownCanvasItem()
                twist_down_canvas_item.update_sizing(twist_down_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=ITEM_HEIGHT, width=16)))
                twist_down_canvas_item.checked = tree_item.is_expanded

                def twist_down_clicked(toggle_value_path: _ValuePath) -> None:
                    self.__toggle_is_expanded(toggle_value_path)

                twist_down_canvas_item.on_button_clicked = functools.partial(twist_down_clicked, tree_item.value_path)
                item_row.add_canvas_item(twist_down_canvas_item)
            else:
                item_row.add_spacing(indent_size)
            item_row.add_canvas_item(tree_item.canvas_item)
            item_row.add_stretch()
            setattr(item_row, "value_path", tree_item.value_path)
            self.add_canvas_item(item_row)
            canvas_height += ITEM_HEIGHT
        self.update()
        if callable(self.on_content_height_changed):
            self.on_content_height_changed(canvas_height)

    def __set_selection(self, value_path: _ValuePath) -> None:
        self.__selected_value_paths.clear()
        self.__selected_value_paths.add(json.dumps(value_path))

    def __extend_selection(self, value_path: _ValuePath) -> None:
        pass

    def __toggle_selection(self, value_path: _ValuePath) -> None:
        value_path_key = json.dumps(value_path)
        if value_path_key in self.__selected_value_paths:
            self.__selected_value_paths.remove(value_path_key)
        else:
            self.__selected_value_paths.add(value_path_key)

    def __toggle_is_expanded(self, value_path: _ValuePath) -> None:
        value_path_key = json.dumps(value_path)
        self.__delegate.toggle_is_expanded(value_path_key)
        self.reconstruct()

    def __context_menu_event(self, value_path: typing.Optional[_ValuePath], x: int, y: int, gx: int, gy: int) -> bool:
        pass

    def __drag_started(self, value_path: typing.Optional[_ValuePath], x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass

    def __delete(self) -> None:
        pass

    def __adjust_selection(self, action: str, extend: bool) -> None:
        pass

    def __value_path_at_point(self, p: Geometry.IntPoint) -> typing.Optional[_ValuePath]:
        for canvas_item in self.canvas_items_at_point(p.x, p.y):
            if hasattr(canvas_item, "value_path"):
                return typing.cast(_ValuePath, getattr(canvas_item, "value_path"))
        return None

    def context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        p = Geometry.IntPoint(y=y, x=x)
        value_path = self.__value_path_at_point(p)
        if value_path:
            if not self.__is_selected(value_path):
                self.__set_selection(value_path)
            return self.__context_menu_event(value_path, x, y, gx, gy)
        return self.__context_menu_event(None, x, y, gx, gy)

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
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

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__mouse_pressed:
            # double check whether mouse_released has been called explicitly as part of a drag.
            # see https://bugreports.qt.io/browse/QTBUG-40733
            pass  # leave this here for future reference
        self.__mouse_pressed = False
        self.__mouse_item = None
        self.__mouse_position = None
        self.__mouse_dragging = False
        return True

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__mouse_pressed and self.__mouse_position:
            mouse_position_f = self.__mouse_position.to_float_point()
            point_f = Geometry.FloatPoint(y=y, x=x)
            if not self.__mouse_dragging and Geometry.distance(mouse_position_f, point_f) > 8:
                self.__mouse_dragging = True
                self.__drag_started(self.__mouse_item, x, y, modifiers)
                # once a drag starts, mouse release will not be called; call it here instead
                self.mouse_released(x, y, modifiers)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def key_pressed(self, key: UserInterface.Key) -> bool:
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

    def handle_select_all(self) -> bool:
        self.__adjust_selection("all", False)
        return True
