"""
    Grid of thumbnails.

    TODO: GridCanvasItem should handle dragging multiple items
    TODO: GridCanvasItem should handle keyboard navigation
    TODO: GridCanvasItem should allow drag selection to select multiple
"""
from __future__ import annotations

# standard libraries
import enum

# third party libraries
# none

# local libraries
import typing

from nion.ui import CanvasItem
from nion.utils import Geometry

if typing.TYPE_CHECKING:
    from nion.ui import DrawingContext
    from nion.ui import UserInterface
    from nion.utils import Selection


class Direction(enum.Enum):
    """Enumeration to specify row first or column first layout."""
    Row = 0
    Column = 1


class GridCanvasItemDelegate(typing.Protocol):
    # items: see https://github.com/python/mypy/issues/4125
    # items: typing.Sequence[typing.Any]

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        raise NotImplementedError()

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int: raise NotImplementedError()

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        pass

    def context_menu_event(self, index: typing.Optional[int], x: int, y: int, gx: int, gy: int) -> bool:
        return False

    def delete_pressed(self) -> None:
        pass

    def key_pressed(self, key: UserInterface.Key) -> bool:
        return False

    def mouse_double_clicked(self, mouse_index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        return False

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


class GridCanvasItem(CanvasItem.AbstractCanvasItem):
    """
    Takes a delegate that supports the following properties, methods, and optional methods:

    Properties:
        item_count: the number of items to be displayed

    Methods:
        paint_item(drawing_context, index, rect, is_selected): paint the cell for index at the position

    Optional methods:
        content_menu_event(index, x, y, gx, gy): called when user wants context menu for given index
        key_pressed(key): called when user presses a key
        delete_pressed(): called when user presses delete key
        drag_started(index, x, y, modifiers): called when user begins drag with given index
    """

    def __init__(self, delegate: GridCanvasItemDelegate, selection: Selection.IndexedSelection,
                 direction: Direction = Direction.Row, wrap: bool = True) -> None:
        super().__init__()
        # store parameters
        self.__delegate = delegate
        self.__selection = selection
        self.__selection_changed_listener = self.__selection.changed_event.listen(self.update)
        # configure super
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__mouse_pressed = False
        self.__mouse_pressed_for_dragging = False
        self.__mouse_index: typing.Optional[int] = None
        self.__mouse_position: typing.Optional[Geometry.IntPoint] = None
        self.__mouse_dragging = False
        self.__direction = direction
        self.__wrap = wrap

    def close(self) -> None:
        self.__selection_changed_listener.close()
        self.__selection_changed_listener = typing.cast(typing.Any, None)
        super().close()

    def detach_delegate(self) -> None:
        self.__delegate = typing.cast(typing.Any, None)

    @property
    def direction(self) -> Direction:
        return self.__direction

    @direction.setter
    def direction(self, value: Direction) -> None:
        self.__direction = value
        self.refresh_layout()

    @property
    def wrap(self) -> bool:
        return self.__wrap

    def set_wrap(self, value: bool, canvas_size: Geometry.IntSize) -> None:
        self._set_canvas_origin(Geometry.IntPoint())
        self._set_canvas_size(canvas_size)
        self.__wrap = value
        self.refresh_layout()

    def __calculate_layout_size(self, canvas_size: Geometry.IntSize) -> Geometry.IntSize:
        # update the layout based on the current canvas size
        item_size = self.__calculate_item_size(canvas_size)
        item_count = self.__delegate.item_count if self.__delegate else 0
        if self.direction == Direction.Row:
            items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
            item_rows = max((item_count + items_per_row - 1) // items_per_row, 1)
            width = canvas_size.width if self.wrap else item_count * item_size.width
            canvas_size = Geometry.IntSize(height=item_rows * item_size.height, width=width)
        else:
            items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)
            item_columns = max((item_count + items_per_column - 1) // items_per_column, 1)
            height = canvas_size.height if self.wrap else item_count * item_size.height
            canvas_size = Geometry.IntSize(height=height, width=item_columns * item_size.width)
        return canvas_size

    def update_layout(self, canvas_origin: typing.Optional[Geometry.IntPoint],
                      canvas_size: typing.Optional[Geometry.IntSize], *, immediate: bool = False) -> None:
        """Override from abstract canvas item.

        Adjust the canvas height based on the constraints.
        """
        if canvas_size:
            super().update_layout(canvas_origin, self.__calculate_layout_size(canvas_size), immediate=immediate)

    def wheel_changed(self, x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> bool:
        dx = dx if is_horizontal else 0
        dy = dy if not is_horizontal else 0
        canvas_rect = self.canvas_rect
        if canvas_rect:
            new_canvas_origin = canvas_rect.origin + Geometry.IntPoint(x=dx, y=dy)
            self.update_layout(new_canvas_origin, canvas_rect.size)
            self.update()
        return True

    def __calculate_item_size(self, canvas_size: Geometry.IntSize) -> Geometry.IntSize:
        if self.wrap:
            target_size = 80
            item_width = max(60, int(canvas_size.width / max(1, ((canvas_size.width + target_size // 4) // target_size))))
            return Geometry.IntSize(item_width, item_width)
        else:
            if self.direction == Direction.Row:
                return Geometry.IntSize(canvas_size.height, canvas_size.height)
            else:
                return Geometry.IntSize(canvas_size.width, canvas_size.width)

    def __rect_for_index(self, index: int) -> Geometry.IntRect:
        canvas_size = self.canvas_size
        if canvas_size:
            item_size = self.__calculate_item_size(canvas_size)
            item_count = self.__delegate.item_count if self.__delegate else 0
            items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
            items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)
            if self.direction == Direction.Row:
                row = index // items_per_row
                column = index - row * items_per_row
            else:
                column = index // items_per_column
                row = index - column * items_per_column
            return Geometry.IntRect(origin=Geometry.IntPoint(y=row * item_size.height, x=column * item_size.width), size=Geometry.IntSize(width=item_size.width, height=item_size.height))
        return Geometry.IntRect.empty_rect()

    def _repaint_visible(self, drawing_context: DrawingContext.DrawingContext, visible_rect: Geometry.IntRect) -> None:
        canvas_size = self.canvas_size
        if self.__delegate and canvas_size and canvas_size.height > 0 and canvas_size.width > 0:
            item_size = self.__calculate_item_size(canvas_size)
            items = self.__delegate.items if self.__delegate else list()
            item_count = len(items)
            items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
            items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)

            with drawing_context.saver():
                top_visible_row = visible_rect.top // item_size.height
                bottom_visible_row = visible_rect.bottom // item_size.height
                left_visible_column = visible_rect.left // item_size.width
                right_visible_column = visible_rect.right // item_size.width
                for row in range(top_visible_row, bottom_visible_row + 1):
                    for column in range(left_visible_column, right_visible_column + 1):
                        if self.direction == Direction.Row:
                            index = row * items_per_row + column
                        else:
                            index = row + column * items_per_column
                        if 0 <= index < item_count:
                            rect = Geometry.IntRect(origin=Geometry.IntPoint(y=row * item_size.height, x=column * item_size.width),
                                                    size=Geometry.IntSize(width=item_size.width, height=item_size.height))
                            if rect.intersects_rect(visible_rect):
                                is_selected = self.__selection.contains(index)
                                if is_selected:
                                    with drawing_context.saver():
                                        drawing_context.begin_path()
                                        drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                                        drawing_context.fill_style = "#3875D6" if self.focused else "#BBB"
                                        drawing_context.fill()
                                self.__delegate.paint_item(drawing_context, items[index], rect, is_selected)

    def _repaint(self, drawing_context: DrawingContext.DrawingContext) -> None:
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            self._repaint_visible(drawing_context, canvas_bounds)

    def context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        if self.__delegate:
            mouse_index = self.__get_item_index_at(x, y)
            max_index = self.__delegate.item_count
            if mouse_index >= 0 and mouse_index < max_index:
                if not self.__selection.contains(mouse_index):
                    self.__selection.set(mouse_index)
                return self.__delegate.context_menu_event(mouse_index, x, y, gx, gy)
            else:
                return self.__delegate.context_menu_event(None, x, y, gx, gy)
        return False

    def __get_item_index_at(self, x: int, y: int) -> int:
        canvas_size = self.canvas_size
        if canvas_size:
            item_size = self.__calculate_item_size(canvas_size)
            item_count = self.__delegate.item_count if self.__delegate else 0
            items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
            items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)
            mouse_row = y // item_size.height
            mouse_column = x // item_size.width
            if self.direction == Direction.Row:
                mouse_index = mouse_row * items_per_row + mouse_column
            else:
                mouse_index = mouse_row + items_per_column * mouse_column
            return mouse_index
        return 0

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__delegate:
            mouse_index = self.__get_item_index_at(x, y)
            max_index = self.__delegate.item_count
            if mouse_index >= 0 and mouse_index < max_index:
                self.__mouse_index = mouse_index
                self.__mouse_pressed = True
                if not modifiers.shift and not modifiers.control:
                    self.__mouse_pressed_for_dragging = True
                    self.__mouse_position = Geometry.IntPoint(y=y, x=x)
                return True
            return super().mouse_pressed(x, y, modifiers)
        return False

    def __mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers, do_select: bool) -> None:
        if self.__delegate and self.__mouse_pressed and do_select:
            # double check whether mouse_released has been called explicitly as part of a drag.
            # see https://bugreports.qt.io/browse/QTBUG-40733
            mouse_index = self.__mouse_index
            max_index = self.__delegate.item_count
            if mouse_index is not None and mouse_index >= 0 and mouse_index < max_index:
                if modifiers.shift:
                    self.__selection.extend(mouse_index)
                elif modifiers.control:
                    self.__selection.toggle(mouse_index)
                else:
                    self.__selection.set(mouse_index)
        self.__mouse_pressed = False
        self.__mouse_pressed_for_dragging = False
        self.__mouse_index = None
        self.__mouse_position = None
        self.__mouse_dragging = False

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__mouse_released(x, y, modifiers, True)
        return True

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__mouse_pressed_for_dragging and self.__mouse_position and self.__mouse_index is not None:
            mouse_position_f = self.__mouse_position.to_float_point()
            point_f = Geometry.FloatPoint(y=y, x=x)
            if not self.__mouse_dragging and Geometry.distance(mouse_position_f, point_f) > 8:
                self.__mouse_dragging = True
                if self.__delegate:
                    root_container = self.root_container
                    if root_container:
                        root_container.bypass_request_focus()
                    self.__delegate.drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        mouse_index = self.__get_item_index_at(x, y)
        max_index = self.__delegate.item_count
        if mouse_index >= 0 and mouse_index < max_index:
            if self.__delegate.mouse_double_clicked(mouse_index, x, y, modifiers):
                return True
        return super().mouse_double_clicked(x, y, modifiers)

    def __make_selection_visible(self, top: bool) -> None:
        if self.__delegate:
            selected_indexes = list(self.__selection.indexes)
            if len(selected_indexes) > 0 and self.canvas_bounds is not None:
                min_index = min(selected_indexes)
                max_index = max(selected_indexes)
                min_rect = self.__rect_for_index(min_index)
                max_rect = self.__rect_for_index(max_index)
                container = self.container
                # TODO: typing here is incorrect since container has no "visible_rect" property. assuming scroll area.
                visible_rect = getattr(container, "visible_rect", Geometry.IntRect.empty_rect())
                canvas_origin = self.canvas_origin
                assert canvas_origin
                if (self.direction == Direction.Row and self.wrap) or (self.direction == Direction.Column and not self.wrap):
                    if top:
                        if min_rect.top < visible_rect.top:
                            self.update_layout(Geometry.IntPoint(y=-min_rect.top, x=canvas_origin.x), self.canvas_size)
                        elif min_rect.bottom > visible_rect.bottom:
                            self.update_layout(Geometry.IntPoint(y=-min_rect.bottom + visible_rect.height, x=canvas_origin.x), self.canvas_size)
                    else:
                        if max_rect.bottom > visible_rect.bottom:
                            self.update_layout(Geometry.IntPoint(y=-max_rect.bottom + visible_rect.height, x=canvas_origin.x), self.canvas_size)
                        elif max_rect.top < visible_rect.top:
                            self.update_layout(Geometry.IntPoint(y=-max_rect.top, x=canvas_origin.x), self.canvas_size)
                else:
                    if top:
                        if min_rect.left < visible_rect.left:
                            self.update_layout(Geometry.IntPoint(y=canvas_origin.y, x=-min_rect.left), self.canvas_size)
                        elif min_rect.right > visible_rect.right:
                            self.update_layout(Geometry.IntPoint(y=canvas_origin.y, x=-min_rect.right + visible_rect.width), self.canvas_size)
                    else:
                        if max_rect.right > visible_rect.right:
                            self.update_layout(Geometry.IntPoint(y=canvas_origin.y, x=-max_rect.right + visible_rect.width), self.canvas_size)
                        elif max_rect.left < visible_rect.left:
                            self.update_layout(Geometry.IntPoint(y=canvas_origin.y, x=-max_rect.left), self.canvas_size)

    def make_selection_visible(self) -> None:
        self.__make_selection_visible(True)

    def key_pressed(self, key: UserInterface.Key) -> bool:
        canvas_size = self.canvas_size
        assert canvas_size
        item_size = self.__calculate_item_size(canvas_size)
        item_count = self.__delegate.item_count if self.__delegate else 0
        items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
        items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)
        if self.__delegate:
            if self.__delegate.key_pressed(key):
                return True
            if key.is_delete:
                self.__delegate.delete_pressed()
                return True
            if key.is_up_arrow:
                amount = items_per_row if self.direction == Direction.Row else 1
                self.__selection.select_backward(self.__delegate.item_count, False, amount)
                self.__make_selection_visible(top=True)
                return True
            if key.is_down_arrow:
                amount = items_per_row if self.direction == Direction.Row else 1
                self.__selection.select_forward(self.__delegate.item_count, False, amount)
                self.__make_selection_visible(top=False)
                return True
            if key.is_left_arrow:
                amount = 1 if self.direction == Direction.Row else items_per_column
                self.__selection.select_backward(self.__delegate.item_count, False, amount)
                self.__make_selection_visible(top=True)
                return True
            if key.is_right_arrow:
                amount = 1 if self.direction == Direction.Row else items_per_column
                self.__selection.select_forward(self.__delegate.item_count, False, amount)
                self.__make_selection_visible(top=False)
                return True
        return super().key_pressed(key)

    def handle_select_all(self) -> bool:
        if self.__delegate:
            self.__selection.set_multiple(set(range(self.__delegate.item_count)))
            return True
        return False

    def handle_delete(self) -> bool:
        self.__delegate.delete_pressed()
        return True
