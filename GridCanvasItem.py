"""
    Grid of thumbnails.

    TODO: GridCanvasItem should handle dragging multiple items
    TODO: GridCanvasItem should handle keyboard navigation
    TODO: GridCanvasItem should allow drag selection to select multiple
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
# none

# third party libraries
# none

# local libraries
from nion.ui import CanvasItem
from nion.ui import Geometry


class GridCanvasItem(CanvasItem.AbstractCanvasItem):
    """
    Takes a delegate that supports the following properties, methods, and optional methods:

    Properties:
        item_count: the number of items to be displayed

    Methods:
        get_item_thumbnail(index): return the thumbnail for the given index
        is_item_selected(index): return whether the given index is selected
        extend_selection(index): extend the selection to the given index
        toggle_selection(index): toggle the selection at the given index
        set_selection(index): set the selection to the given index

    Optional methods:
        on_content_menu_event(index, x, y, gx, gy): called when user wants context menu for given index
        on_delete_pressed(): called when user presses delete key
        on_drag_started(index, x, y, modifiers): called when user begins drag with given index
    """

    def __init__(self, delegate, selection):
        super(GridCanvasItem, self).__init__()
        # store parameters
        self.__delegate = delegate
        self.__selection = selection
        self.__selection_changed_listener = self.__selection.changed_event.listen(self.update)
        # configure super
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__mouse_pressed = False
        self.__mouse_index = None
        self.__mouse_position = None
        self.__mouse_dragging = False

    def close(self):
        self.__selection_changed_listener.close()
        self.__selection_changed_listener = None
        super(GridCanvasItem, self).close()

    def update_layout(self, canvas_origin, canvas_size, trigger_update=True):
        """Override from abstract canvas item.

        Adjust the canvas height based on the constraints.
        """
        canvas_size = Geometry.IntSize.make(canvas_size)
        canvas_size = Geometry.IntSize(height=self.__calculate_layout_height(canvas_size.width),
                                       width=canvas_size.width)
        super(GridCanvasItem, self).update_layout(canvas_origin, canvas_size, trigger_update)

    def wheel_changed(self, dx, dy, is_horizontal):
        dy = dy if not is_horizontal else 0.0
        new_canvas_origin = Geometry.IntPoint.make(self.canvas_origin) + Geometry.IntPoint(x=0, y=dy)
        self.update_layout(new_canvas_origin, self.canvas_size)
        self.update()

    def __calculate_layout_height(self, width):
        items_per_row = 4
        item_width = width // items_per_row
        item_height = item_width
        item_rows = (self.__delegate.item_count + items_per_row - 1) // items_per_row
        return item_rows * item_height

    def update(self):
        if self.canvas_origin is not None and self.canvas_size is not None:
            if self.__calculate_layout_height(self.canvas_size.width) != self.canvas_size.height:
                self.refresh_layout()
        super(GridCanvasItem, self).update()

    def _repaint_visible(self, drawing_context, visible_rect):
        canvas_bounds = self.canvas_bounds

        items_per_row = 4
        item_width = canvas_bounds.width // items_per_row
        item_height = item_width

        drawing_context.save()
        try:
            max_index = self.__delegate.item_count
            top_visible_row = visible_rect.top // item_height
            bottom_visible_row = visible_rect.bottom // item_height
            for row in range(top_visible_row, bottom_visible_row + 1):
                for column in range(items_per_row):
                    index = row * items_per_row + column
                    if index < max_index:
                        rect = Geometry.IntRect(origin=Geometry.IntPoint(y=row * item_height, x=column * item_width),
                                                size=Geometry.IntSize(width=item_width, height=item_height))
                        if rect.intersects_rect(visible_rect):
                            thumbnail_data = self.__delegate.get_item_thumbnail(index)
                            is_selected = self.__selection.contains(index)
                            if is_selected:
                                drawing_context.save()
                                drawing_context.begin_path()
                                drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                                drawing_context.fill_style = "#3875D6" if self.focused else "#BBB"
                                drawing_context.fill()
                                drawing_context.restore()
                            if thumbnail_data is not None:
                                draw_rect = rect.inset(6)
                                draw_rect = Geometry.fit_to_size(draw_rect, thumbnail_data.shape)
                                drawing_context.draw_image(thumbnail_data, draw_rect[0][1], draw_rect[0][0],
                                                           draw_rect[1][1], draw_rect[1][0])
        finally:
            drawing_context.restore()

    def _repaint(self, drawing_context):
        self._repaint_visible(drawing_context, self.canvas_bounds)

    def context_menu_event(self, x, y, gx, gy):
        canvas_bounds = self.canvas_bounds

        items_per_row = 4
        item_width = canvas_bounds.width // items_per_row
        item_height = item_width

        max_index = self.__delegate.item_count
        mouse_row = y // item_height
        mouse_column = x // item_width
        mouse_index = mouse_row * items_per_row + mouse_column

        if mouse_index >= 0 and mouse_index < max_index:
            if not self.__selection.contains(mouse_index):
                self.__selection.set(mouse_index)
            if self.__delegate.on_context_menu_event:
                return self.__delegate.on_context_menu_event(mouse_index, x, y, gx, gy)
        else:
            if self.__delegate.on_context_menu_event:
                return self.__delegate.on_context_menu_event(None, x, y, gx, gy)
        return False

    def mouse_pressed(self, x, y, modifiers):
        canvas_bounds = self.canvas_bounds

        items_per_row = 4
        item_width = canvas_bounds.width // items_per_row
        item_height = item_width

        max_index = self.__delegate.item_count
        mouse_row = y // item_height
        mouse_column = x // item_width
        mouse_index = mouse_row * items_per_row + mouse_column

        if mouse_index >= 0 and mouse_index < max_index:
            if modifiers.shift:
                self.__selection.extend(mouse_index)
            elif modifiers.control:
                self.__selection.toggle(mouse_index)
            else:
                self.__selection.set(mouse_index)
                self.__mouse_pressed = True
                self.__mouse_position = Geometry.IntPoint(y=y, x=x)
                self.__mouse_index = mouse_index
            return True

        return super(GridCanvasItem, self).mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        self.__mouse_pressed = False
        self.__mouse_index = None
        self.__mouse_position = None
        self.__mouse_dragging = False
        return True

    def mouse_position_changed(self, x, y, modifiers):
        if self.__mouse_pressed:
            if not self.__mouse_dragging and Geometry.distance(self.__mouse_position, Geometry.IntPoint(y=y, x=x)) > 8:
                self.__mouse_dragging = True
                if self.__delegate.on_drag_started:
                    self.__delegate.on_drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.mouse_released(x, y, modifiers)
                return True
        return super(GridCanvasItem, self).mouse_position_changed(x, y, modifiers)

    def key_pressed(self, key):
        if key.is_delete:
            if self.__delegate.on_delete_pressed:
                self.__delegate.on_delete_pressed()
            return True
        if key.key == ord('A') and key.modifiers.only_control:
            self.select_all()
            return True
        if key.is_up_arrow:
            new_index = None
            items_per_row = 4
            indexes = self.__selection.indexes
            if len(indexes) > 0:
                new_index = max(min(indexes) - items_per_row, 0)
            elif self.__delegate.item_count > 0:
                new_index = self.__delegate.item_count - 1
            if new_index is not None:
                if key.modifiers.shift:
                    self.__selection.extend(new_index)
                else:
                    self.__selection.set(new_index)
            return True
        if key.is_down_arrow:
            new_index = None
            items_per_row = 4
            indexes = self.__selection.indexes
            if len(indexes) > 0:
                new_index = min(max(indexes) + items_per_row, self.__delegate.item_count - 1)
            elif self.__delegate.item_count > 0:
                new_index = 0
            if new_index is not None:
                if key.modifiers.shift:
                    self.__selection.extend(new_index)
                else:
                    self.__selection.set(new_index)
            return True
        if key.is_left_arrow:
            new_index = None
            indexes = self.__selection.indexes
            if len(indexes) > 0:
                new_index = max(min(indexes) - 1, 0)
            elif self.__delegate.item_count > 0:
                new_index = self.__delegate.item_count - 1
            if new_index is not None:
                if key.modifiers.shift:
                    self.__selection.extend(new_index)
                else:
                    self.__selection.set(new_index)
            return True
        if key.is_right_arrow:
            new_index = None
            indexes = self.__selection.indexes
            if len(indexes) > 0:
                new_index = min(max(indexes) + 1, self.__delegate.item_count - 1)
            elif self.__delegate.item_count > 0:
                new_index = 0
            if new_index is not None:
                if key.modifiers.shift:
                    self.__selection.extend(new_index)
                else:
                    self.__selection.set(new_index)
            return True
        return super(GridCanvasItem, self).key_pressed(key)

    def select_all(self):
        self.__selection.set_multiple(set(range(self.__delegate.item_count)))
