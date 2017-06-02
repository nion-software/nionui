"""
    Grid of thumbnails.

    TODO: GridCanvasItem should handle dragging multiple items
    TODO: GridCanvasItem should handle keyboard navigation
    TODO: GridCanvasItem should allow drag selection to select multiple
"""
# standard libraries
import enum

# third party libraries
# none

# local libraries
from . import CanvasItem
from nion.utils import Geometry


class Direction(enum.Enum):
    """Enumeration to specify row first or column first layout."""
    Row = 0
    Column = 1


class GridCanvasItem(CanvasItem.AbstractCanvasItem):
    """
    Takes a delegate that supports the following properties, methods, and optional methods:

    Properties:
        item_count: the number of items to be displayed

    Methods:
        paint_item(drawing_context, index, rect, is_selected): paint the cell for index at the position

    Optional methods:
        on_content_menu_event(index, x, y, gx, gy): called when user wants context menu for given index
        on_key_pressed(key): called when user presses a key
        on_delete_pressed(): called when user presses delete key
        on_drag_started(index, x, y, modifiers): called when user begins drag with given index
    """

    def __init__(self, delegate, selection, direction=Direction.Row, wrap=True):
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
        self.__mouse_index = None
        self.__mouse_position = None
        self.__mouse_dragging = False
        self.__direction = direction
        self.__wrap = wrap

    def close(self):
        self.__selection_changed_listener.close()
        self.__selection_changed_listener = None
        super().close()

    def detach_delegate(self):
        self.__delegate = None

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

    def set_wrap(self, value: bool, canvas_size) -> None:
        self._set_canvas_origin(Geometry.IntPoint())
        self._set_canvas_size(canvas_size)
        self.__wrap = value
        self.refresh_layout()

    def __calculate_layout_size(self, canvas_size: Geometry.IntSize) -> Geometry.IntSize:
        # update the layout based on the current canvas size
        canvas_size = Geometry.IntSize.make(canvas_size)

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

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Override from abstract canvas item.

        Adjust the canvas height based on the constraints.
        """
        super().update_layout(canvas_origin, self.__calculate_layout_size(canvas_size), immediate=immediate)

    def wheel_changed(self, x, y, dx, dy, is_horizontal):
        dx = dx if is_horizontal else 0.0
        dy = dy if not is_horizontal else 0.0
        new_canvas_origin = Geometry.IntPoint.make(self.canvas_origin) + Geometry.IntPoint(x=dx, y=dy)
        self.update_layout(new_canvas_origin, self.canvas_size)
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

    def _repaint_visible(self, drawing_context, visible_rect):
        canvas_size = self.canvas_size
        if self.__delegate and canvas_size.height > 0 and canvas_size.width > 0:
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

    def _repaint(self, drawing_context):
        self._repaint_visible(drawing_context, self.canvas_bounds)

    def context_menu_event(self, x, y, gx, gy):
        if self.__delegate:
            mouse_index = self.__get_item_index_at(x, y)
            max_index = self.__delegate.item_count
            if mouse_index >= 0 and mouse_index < max_index:
                if not self.__selection.contains(mouse_index):
                    self.__selection.set(mouse_index)
                if self.__delegate.on_context_menu_event:
                    return self.__delegate.on_context_menu_event(mouse_index, x, y, gx, gy)
            else:
                if self.__delegate.on_context_menu_event:
                    return self.__delegate.on_context_menu_event(None, x, y, gx, gy)
        return False

    def __get_item_index_at(self, x, y):
        canvas_size = self.canvas_size
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

    def mouse_pressed(self, x, y, modifiers):
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

    def __mouse_released(self, x, y, modifiers, do_select):
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
        return True

    def mouse_released(self, x, y, modifiers):
        return self.__mouse_released(x, y, modifiers, True)

    def mouse_position_changed(self, x, y, modifiers):
        if self.__mouse_pressed_for_dragging:
            if not self.__mouse_dragging and Geometry.distance(self.__mouse_position, Geometry.IntPoint(y=y, x=x)) > 8:
                self.__mouse_dragging = True
                if self.__delegate and self.__delegate.on_drag_started:
                    root_container = self.root_container
                    if root_container:
                        root_container.bypass_request_focus()
                    self.__delegate.on_drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def mouse_double_clicked(self, x, y, modifiers):
        mouse_index = self.__get_item_index_at(x, y)
        max_index = self.__delegate.item_count
        if mouse_index >= 0 and mouse_index < max_index:
            if callable(self.__delegate.on_mouse_double_clicked):
                if self.__delegate.on_mouse_double_clicked(mouse_index, x, y, modifiers):
                    return True
        return super().mouse_double_clicked(x, y, modifiers)

    def __make_selection_visible(self, top):
        if self.__delegate:
            selected_indexes = list(self.__selection.indexes)
            if len(selected_indexes) > 0 and self.canvas_bounds is not None:
                min_index = min(selected_indexes)
                max_index = max(selected_indexes)
                min_rect = self.__rect_for_index(min_index)
                max_rect = self.__rect_for_index(max_index)
                visible_rect = self.container.visible_rect
                if (self.direction == Direction.Row and self.wrap) or (self.direction == Direction.Column and not self.wrap):
                    if top:
                        if min_rect.top < visible_rect.top:
                            self.update_layout(Geometry.IntPoint(y=-min_rect.top, x=self.canvas_origin.x), self.canvas_size)
                        elif min_rect.bottom > visible_rect.bottom:
                            self.update_layout(Geometry.IntPoint(y=-min_rect.bottom + visible_rect.height, x=self.canvas_origin.x), self.canvas_size)
                    else:
                        if max_rect.bottom > visible_rect.bottom:
                            self.update_layout(Geometry.IntPoint(y=-max_rect.bottom + visible_rect.height, x=self.canvas_origin.x), self.canvas_size)
                        elif max_rect.top < visible_rect.top:
                            self.update_layout(Geometry.IntPoint(y=-max_rect.top, x=self.canvas_origin.x), self.canvas_size)
                else:
                    if top:
                        if min_rect.left < visible_rect.left:
                            self.update_layout(Geometry.IntPoint(y=self.canvas_origin.y, x=-min_rect.left), self.canvas_size)
                        elif min_rect.right > visible_rect.right:
                            self.update_layout(Geometry.IntPoint(y=self.canvas_origin.y, x=-min_rect.right + visible_rect.width), self.canvas_size)
                    else:
                        if max_rect.right > visible_rect.right:
                            self.update_layout(Geometry.IntPoint(y=self.canvas_origin.y, x=-max_rect.right + visible_rect.width), self.canvas_size)
                        elif max_rect.left < visible_rect.left:
                            self.update_layout(Geometry.IntPoint(y=self.canvas_origin.y, x=-max_rect.left), self.canvas_size)

    def make_selection_visible(self):
        self.__make_selection_visible(True)

    def key_pressed(self, key):
        canvas_size = self.canvas_size
        item_size = self.__calculate_item_size(canvas_size)
        item_count = self.__delegate.item_count if self.__delegate else 0
        items_per_row = max(1, int(canvas_size.width / item_size.width) if self.wrap else item_count)
        items_per_column = max(1, int(canvas_size.height / item_size.height) if self.wrap else item_count)
        if self.__delegate:
            if self.__delegate.on_key_pressed:
                if self.__delegate.on_key_pressed(key):
                    return True
            if key.is_delete:
                if self.__delegate.on_delete_pressed:
                    self.__delegate.on_delete_pressed()
                return True
            if key.is_up_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    if self.direction == Direction.Row:
                        new_index = max(min(indexes) - items_per_row, 0)
                    else:
                        new_index = max(min(indexes) - 1, 0)
                elif self.__delegate.item_count > 0:
                    new_index = self.__delegate.item_count - 1
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(top=True)
                return True
            if key.is_down_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    if self.direction == Direction.Row:
                        new_index = min(max(indexes) + items_per_row, self.__delegate.item_count - 1)
                    else:
                        new_index = min(max(indexes) + 1, self.__delegate.item_count - 1)
                elif self.__delegate.item_count > 0:
                    new_index = 0
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(top=False)
                return True
            if key.is_left_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    if self.direction == Direction.Row:
                        new_index = max(min(indexes) - 1, 0)
                    else:
                        new_index = max(min(indexes) - items_per_column, 0)
                elif self.__delegate.item_count > 0:
                    new_index = self.__delegate.item_count - 1
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(top=True)
                return True
            if key.is_right_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    if self.direction == Direction.Row:
                        new_index = min(max(indexes) + 1, self.__delegate.item_count - 1)
                    else:
                        new_index = min(max(indexes) + items_per_column, self.__delegate.item_count - 1)
                elif self.__delegate.item_count > 0:
                    new_index = 0
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(top=False)
                return True
        return super().key_pressed(key)

    def handle_select_all(self):
        if self.__delegate:
            self.__selection.set_multiple(set(range(self.__delegate.item_count)))
            return True
        return False

    def handle_delete(self):
        if self.__delegate.on_delete_pressed:
            self.__delegate.on_delete_pressed()
        return True
