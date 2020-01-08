"""
    List of drawable cells.

    TODO: ListCanvasItem should handle dragging multiple items
    TODO: ListCanvasItem should handle keyboard navigation
    TODO: ListCanvasItem should allow drag selection to select multiple
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
# none

# third party libraries
# none

# local libraries
from . import CanvasItem
from nion.utils import Geometry


class ListCanvasItem(CanvasItem.AbstractCanvasItem):
    """
    Takes a delegate that supports the following properties, methods, and optional methods:

    Properties:
        item_count: the number of items to be displayed
        items: the items to be displayed

    Methods:
        paint_item(drawing_context, index, rect, is_selected): paint the cell for index at the position

    Optional methods:
        content_menu_event(index, x, y, gx, gy): called when user wants context menu for given index
        key_pressed(key): called when user presses a key
        delete_pressed(): called when user presses delete key
        drag_started(index, x, y, modifiers): called when user begins drag with given index
    """

    def __init__(self, delegate, selection, item_height=80):
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
        self.__dropping = True
        self.__drop_before_index = None
        self.__drop_index = None
        self.__item_height = item_height

    def close(self):
        self.__selection_changed_listener.close()
        self.__selection_changed_listener = None
        super().close()

    def detach_delegate(self):
        self.__delegate = None

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Override from abstract canvas item.

        Adjust the canvas height based on the constraints.
        """
        canvas_size = Geometry.IntSize.make(canvas_size)
        canvas_size = Geometry.IntSize(height=self.__calculate_layout_height(), width=canvas_size.width)
        super().update_layout(canvas_origin, canvas_size, immediate=immediate)

    def wheel_changed(self, x, y, dx, dy, is_horizontal):
        dy = dy if not is_horizontal else 0.0
        new_canvas_origin = Geometry.IntPoint.make(self.canvas_origin) + Geometry.IntPoint(x=0, y=dy)
        self.update_layout(new_canvas_origin, self.canvas_size)
        self.update()
        return True

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        max_index = self.__delegate.item_count
        mouse_index = y // self.__item_height
        if mouse_index >= 0 and mouse_index < max_index:
            if self.__delegate and hasattr(self.__delegate, "item_tool_tip"):
                text = self.__delegate.item_tool_tip(mouse_index)
                if text:
                    self.show_tool_tip_text(text, gx, gy)
                    return True
        return super().handle_tool_tip(x, y, gx, gy)

    def __calculate_layout_height(self):
        item_count = self.__delegate.item_count if self.__delegate else 0
        return item_count * self.__item_height

    def __rect_for_index(self, index: int) -> Geometry.IntRect:
        canvas_bounds = self.canvas_bounds
        item_width = int(canvas_bounds.width)
        item_height = self.__item_height
        return Geometry.IntRect(origin=Geometry.IntPoint(y=index * item_height, x=0),
                                size=Geometry.IntSize(width=item_width, height=item_height))

    def _repaint_visible(self, drawing_context, visible_rect):
        if self.__delegate:
            canvas_bounds = self.canvas_bounds

            item_width = int(canvas_bounds.width)
            item_height = self.__item_height

            with drawing_context.saver():
                items = self.__delegate.items
                max_index = len(items)
                top_visible_row = visible_rect.top // item_height
                bottom_visible_row = visible_rect.bottom // item_height
                for index in range(top_visible_row, bottom_visible_row + 1):
                    if 0 <= index < max_index:
                        rect = Geometry.IntRect(origin=Geometry.IntPoint(y=index * item_height, x=0),
                                                size=Geometry.IntSize(width=item_width, height=item_height))
                        if rect.intersects_rect(visible_rect):
                            is_selected = self.__selection.contains(index)
                            if is_selected:
                                with drawing_context.saver():
                                    drawing_context.begin_path()
                                    drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                                    drawing_context.fill_style = "#3875D6" if self.focused else "#DDD"
                                    drawing_context.fill()
                            self.__delegate.paint_item(drawing_context, items[index], rect, is_selected)
                            if index == self.__drop_index:
                                with drawing_context.saver():
                                    drop_border_width = 2.5
                                    rect_in = rect.inset(drop_border_width / 2, drop_border_width / 2)
                                    drawing_context.begin_path()
                                    drawing_context.rect(rect_in.left, rect_in.top, rect_in.width, rect_in.height)
                                    drawing_context.line_width = drop_border_width
                                    drawing_context.stroke_style = "rgba(56, 117, 214, 0.8)"
                                    drawing_context.stroke()

    def _repaint(self, drawing_context):
        self._repaint_visible(drawing_context, self.canvas_bounds)

    def context_menu_event(self, x, y, gx, gy):
        if self.__delegate:
            max_index = self.__delegate.item_count
            mouse_index = y // self.__item_height
            if mouse_index >= 0 and mouse_index < max_index:
                if not self.__selection.contains(mouse_index):
                    self.__selection.set(mouse_index)
                if self.__delegate and hasattr(self.__delegate, "context_menu_event") and self.__delegate.context_menu_event:
                    return self.__delegate.context_menu_event(mouse_index, x, y, gx, gy)
                # TODO: delete soon. only here for backwards compatibility.
                if self.__delegate and hasattr(self.__delegate, "on_context_menu_event") and self.__delegate.on_context_menu_event:
                    return self.__delegate.on_context_menu_event(mouse_index, x, y, gx, gy)
            else:
                if self.__delegate and hasattr(self.__delegate, "context_menu_event") and self.__delegate.context_menu_event:
                    return self.__delegate.context_menu_event(None, x, y, gx, gy)
                # TODO: delete soon. only here for backwards compatibility.
                if self.__delegate and hasattr(self.__delegate, "on_context_menu_event") and self.__delegate.on_context_menu_event:
                    return self.__delegate.on_context_menu_event(None, x, y, gx, gy)
        return False

    def mouse_double_clicked(self, x, y, modifiers):
        max_index = self.__delegate.item_count
        mouse_index = y // self.__item_height
        if mouse_index >= 0 and mouse_index < max_index:
            if not self.__selection.contains(mouse_index):
                self.__selection.set(mouse_index)
            if self.__delegate and hasattr(self.__delegate, "item_selected") and self.__delegate.item_selected:
                return self.__delegate.item_selected(mouse_index)
        return super().mouse_double_clicked(x, y, modifiers)

    def mouse_pressed(self, x, y, modifiers):
        if self.__delegate:
            mouse_index = y // self.__item_height
            max_index = self.__delegate.item_count
            if mouse_index >= 0 and mouse_index < max_index:
                self.__mouse_index = mouse_index
                self.__mouse_pressed = True
                handled = False
                if self.__delegate and hasattr(self.__delegate, "mouse_pressed_in_item") and self.__delegate.mouse_pressed_in_item:
                    handled = self.__delegate.mouse_pressed_in_item(mouse_index, Geometry.IntPoint(y=y - mouse_index * self.__item_height, x=x), modifiers)
                    if handled:
                        self.__mouse_index = None  # prevent selection handling
                if not handled and not modifiers.shift and not modifiers.control:
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
                if self.__delegate and hasattr(self.__delegate, "drag_started") and self.__delegate.drag_started:
                    root_container = self.root_container
                    if root_container:
                        root_container.bypass_request_focus()
                    self.__delegate.drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                # TODO: delete soon. only here for backwards compatibility.
                if self.__delegate and hasattr(self.__delegate, "on_drag_started") and self.__delegate.on_drag_started:
                    root_container = self.root_container
                    if root_container:
                        root_container.bypass_request_focus()
                    self.__delegate.on_drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def __make_selection_visible(self, top):
        if self.__delegate:
            selected_indexes = list(self.__selection.indexes)
            if len(selected_indexes) > 0 and self.canvas_bounds is not None:
                min_index = min(selected_indexes)
                max_index = max(selected_indexes)
                min_rect = self.__rect_for_index(min_index)
                max_rect = self.__rect_for_index(max_index)
                visible_rect = getattr(self.container, "visible_rect", None)
                if visible_rect is not None:
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

    def make_selection_visible(self):
        self.__make_selection_visible(True)

    def key_pressed(self, key):
        if self.__delegate:
            if self.__delegate and hasattr(self.__delegate, "key_pressed") and self.__delegate.key_pressed:
                if self.__delegate.key_pressed(key):
                    return True
            # TODO: delete soon. only here for backwards compatibility.
            if self.__delegate and hasattr(self.__delegate, "on_key_pressed") and self.__delegate.on_key_pressed:
                if self.__delegate.on_key_pressed(key):
                    return True
            if key.is_delete:
                return self.handle_delete()
            if key.is_enter_or_return:
                if self.__delegate and hasattr(self.__delegate, "item_selected") and self.__delegate.item_selected:
                    indexes = self.__selection.indexes
                    if len(indexes) == 1:
                        return self.__delegate.item_selected(list(indexes)[0])
            if key.is_up_arrow:
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
                self.__make_selection_visible(top=True)
                return True
            if key.is_down_arrow:
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
                self.__make_selection_visible(top=False)
                return True
        return super().key_pressed(key)

    def drag_enter(self, mime_data):
        self.__dropping = True
        self.update()
        return "ignore"

    def drag_move(self, mime_data, x, y):
        mouse_index = y // self.__item_height
        max_index = self.__delegate.item_count
        drop_index = None
        if mouse_index >= 0 and mouse_index < max_index:
            drop_index = mouse_index
            if self.__delegate and hasattr(self.__delegate, "item_can_drop_mime_data") and callable(self.__delegate.item_can_drop_mime_data):
                if not self.__delegate.item_can_drop_mime_data(mime_data, "move", drop_index):
                    drop_index = None
            else:
                drop_index = None
        if drop_index != self.__drop_index:
            self.__drop_index = drop_index
            self.update()

    def drag_leave(self):
        self.__dropping = False
        self.__drop_index = None
        self.update()
        return False

    def drop(self, mime_data, x, y):
        drop_index = self.__drop_index
        self.__dropping = False
        self.__drop_index = None
        self.update()
        if drop_index is not None:
            if self.__delegate and hasattr(self.__delegate, "item_drop_mime_data") and callable(self.__delegate.item_drop_mime_data):
                return self.__delegate.item_drop_mime_data(mime_data, "move", drop_index)
        return "ignore"

    def handle_select_all(self):
        if self.__delegate:
            self.__selection.set_multiple(set(range(self.__delegate.item_count)))
            return True
        return False

    def handle_delete(self):
        if self.__delegate and hasattr(self.__delegate, "delete_pressed") and self.__delegate.delete_pressed:
            self.__delegate.delete_pressed()
        # TODO: delete soon. only here for backwards compatibility.
        if self.__delegate and hasattr(self.__delegate, "on_delete_pressed") and self.__delegate.on_delete_pressed:
            self.__delegate.on_delete_pressed()
        return True

    def size_to_content(self) -> None:
        """Size the canvas item to the height of the items."""
        new_sizing = self.copy_sizing()
        new_sizing.minimum_height = self.__item_height * self.__delegate.item_count
        new_sizing.maximum_height = self.__item_height * self.__delegate.item_count
        self.update_sizing(new_sizing)
