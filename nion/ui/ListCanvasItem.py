"""
    List of drawable cells.

    TODO: ListCanvasItem should handle dragging multiple items
    TODO: ListCanvasItem should handle keyboard navigation
    TODO: ListCanvasItem should allow drag selection to select multiple
"""

# futures
from __future__ import annotations

# standard libraries
import typing

# third party libraries
# none

# local libraries
from nion.ui import CanvasItem
from nion.ui import UserInterface
from nion.utils import Event
from nion.utils import Geometry

if typing.TYPE_CHECKING:
    from nion.ui import DrawingContext
    from nion.utils import Selection


class ListCanvasItemDelegate(typing.Protocol):
    on_item_selected: typing.Optional[typing.Callable[[int], None]]
    on_cancel: typing.Optional[typing.Callable[[], None]]

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

    def key_pressed(self, key: UserInterface.Key) -> bool:
        return False

    def item_selected(self, index: int) -> bool:
        return False

    def item_tool_tip(self, index: int) -> typing.Optional[str]:
        return None

    def context_menu_event(self, index: typing.Optional[int], x: int, y: int, gx: int, gy: int) -> bool:
        return False

    def mouse_pressed_in_item(self, mouse_index: int, pos: Geometry.IntPoint, modifiers: UserInterface.KeyboardModifiers) -> bool:
        return False

    def item_can_drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> bool:
        return False

    def item_drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> str:
        return str()

    def delete_pressed(self) -> None:
        return  # required to avoid being recognized as abstract by mypy

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        return  # required to avoid being recognized as abstract by mypy

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, display_item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        return  # required to avoid being recognized as abstract by mypy


class ListCanvasItemComposer(CanvasItem.BaseComposer):
    def __init__(self,
                 canvas_item: CanvasItem.AbstractCanvasItem,
                 layout_sizing: CanvasItem.Sizing,
                 composer_cache: CanvasItem.ComposerCache,
                 delegate: ListCanvasItemDelegate,
                 item_height: int,
                 drop_index: typing.Optional[int],
                 selection: Selection.IndexedSelection,
                 focused: bool) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__delegate = delegate
        self.__item_height = item_height
        self.__drop_index = drop_index
        self.__selection = selection
        self.__focused = focused

    def _adjust_canvas_bounds(self, canvas_bounds: Geometry.IntRect) -> Geometry.IntRect:
        item_count = self.__delegate.item_count
        height = item_count * self.__item_height
        return Geometry.IntRect(canvas_bounds.origin, Geometry.IntSize(height=height, width=canvas_bounds.width))

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_bounds: Geometry.IntRect, composer_cache: CanvasItem.ComposerCache) -> None:
        canvas_size = canvas_bounds.size
        visible_rect = Geometry.IntRect(Geometry.IntPoint(), canvas_bounds.size)
        delegate = self.__delegate
        item_height = self.__item_height
        drop_index = self.__drop_index
        selection = self.__selection
        focused = self.__focused
        if canvas_size.height > 0 and canvas_size.width > 0:
            item_width = canvas_bounds.width

            with drawing_context.saver():
                drawing_context.translate(canvas_bounds.left, canvas_bounds.top)
                items = delegate.items
                max_index = len(items)
                top_visible_row = visible_rect.top // item_height
                bottom_visible_row = visible_rect.bottom // item_height
                for index in range(top_visible_row, bottom_visible_row + 1):
                    if 0 <= index < max_index:
                        rect = Geometry.IntRect(origin=Geometry.IntPoint(y=index * item_height, x=0),
                                                size=Geometry.IntSize(width=item_width, height=item_height))
                        if rect.intersects_rect(visible_rect):
                            is_selected = selection.contains(index)
                            if is_selected:
                                with drawing_context.saver():
                                    drawing_context.begin_path()
                                    drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                                    drawing_context.fill_style = "#3875D6" if focused else "#DDD"
                                    drawing_context.fill()
                            delegate.paint_item(drawing_context, items[index], rect, is_selected)
                            if index == drop_index:
                                with drawing_context.saver():
                                    drop_border_width = 2.5
                                    rect_in = rect.to_float_rect().inset(drop_border_width / 2, drop_border_width / 2).to_int_rect()
                                    drawing_context.begin_path()
                                    drawing_context.rect(rect_in.left, rect_in.top, rect_in.width, rect_in.height)
                                    drawing_context.line_width = drop_border_width
                                    drawing_context.stroke_style = "rgba(56, 117, 214, 0.8)"
                                    drawing_context.stroke()


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

    def __init__(self, delegate: ListCanvasItemDelegate, selection: Selection.IndexedSelection, item_height: int = 80) -> None:
        super().__init__()
        # store parameters
        self.__delegate: typing.Optional[ListCanvasItemDelegate] = delegate
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
        self.__dropping = True
        self.__drop_before_index: typing.Optional[int] = None
        self.__drop_index: typing.Optional[int] = None
        self.__item_height = item_height

    def close(self) -> None:
        self.__selection_changed_listener.close()
        self.__selection_changed_listener = typing.cast(Event.EventListener, None)
        super().close()

    def detach_delegate(self) -> None:
        self.__delegate = None

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        delegate = self.__delegate
        max_index = delegate.item_count if delegate else 0
        mouse_index = y // self.__item_height
        if mouse_index >= 0 and mouse_index < max_index:
            if delegate:
                text = delegate.item_tool_tip(mouse_index)
                if text:
                    self.show_tool_tip_text(text, gx, gy)
                    return True
        return super().handle_tool_tip(x, y, gx, gy)

    def __rect_for_index(self, index: int) -> Geometry.IntRect:
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            item_width = canvas_bounds.width
            item_height = self.__item_height
            return Geometry.IntRect(origin=Geometry.IntPoint(y=index * item_height, x=0),
                                    size=Geometry.IntSize(width=item_width, height=item_height))
        return Geometry.IntRect.empty_rect()

    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> typing.Optional[CanvasItem.BaseComposer]:
        assert self.__delegate
        return ListCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__delegate, self.__item_height, self.__drop_index, self.__selection, self.focused)

    def context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        delegate = self.__delegate
        if delegate:
            max_index = delegate.item_count
            mouse_index = y // self.__item_height
            if mouse_index >= 0 and mouse_index < max_index:
                if not self.__selection.contains(mouse_index):
                    self.__selection.set(mouse_index)
                return delegate.context_menu_event(mouse_index, x, y, gx, gy)
            else:
                return delegate.context_menu_event(None, x, y, gx, gy)
        return False

    def mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        delegate = self.__delegate
        max_index = delegate.item_count if delegate else 0
        mouse_index = y // self.__item_height
        if mouse_index >= 0 and mouse_index < max_index:
            if not self.__selection.contains(mouse_index):
                self.__selection.set(mouse_index)
            if delegate:
                return delegate.item_selected(mouse_index)
        return super().mouse_double_clicked(x, y, modifiers)

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        delegate = self.__delegate
        if delegate:
            mouse_index = y // self.__item_height
            max_index = delegate.item_count
            if mouse_index >= 0 and mouse_index < max_index:
                self.__mouse_index = mouse_index
                self.__mouse_pressed = True
                handled = False
                if delegate:
                    handled = delegate.mouse_pressed_in_item(mouse_index, Geometry.IntPoint(y=y - mouse_index * self.__item_height, x=x), modifiers)
                    if handled:
                        self.__mouse_index = None  # prevent selection handling
                if not handled and not modifiers.shift and not modifiers.control:
                    self.__mouse_pressed_for_dragging = True
                    self.__mouse_position = Geometry.IntPoint(y=y, x=x)
                return True
        return super().mouse_pressed(x, y, modifiers)

    def __mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers, do_select: bool) -> None:
        delegate = self.__delegate
        if delegate and self.__mouse_pressed and do_select:
            # double check whether mouse_released has been called explicitly as part of a drag.
            # see https://bugreports.qt.io/browse/QTBUG-40733
            mouse_index = self.__mouse_index
            max_index = delegate.item_count
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
                delegate = self.__delegate
                if delegate:
                    root_container = self.root_container
                    if root_container:
                        root_container.bypass_request_focus()
                    delegate.drag_started(self.__mouse_index, x, y, modifiers)
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                return True
        return super().mouse_position_changed(x, y, modifiers)

    def __make_selection_visible(self, style: int) -> None:
        if self.__delegate:
            selected_indexes = list(self.__selection.indexes)
            if len(selected_indexes) > 0 and self.canvas_bounds is not None:
                min_index = min(selected_indexes)
                max_index = max(selected_indexes)
                min_rect = self.__rect_for_index(min_index)
                max_rect = self.__rect_for_index(max_index)
                scroll_area = self.container
                if isinstance(scroll_area, CanvasItem.ScrollAreaCanvasItem):
                    scroll_area.make_selection_visible(min_rect, max_rect, False, True, style < 0)

    def make_selection_visible(self) -> None:
        self.__make_selection_visible(-1)

    def key_pressed(self, key: UserInterface.Key) -> bool:
        delegate = self.__delegate
        if delegate:
            if delegate.key_pressed(key):
                return True
            if key.is_delete:
                return self.handle_delete()
            if key.is_enter_or_return:
                indexes = self.__selection.indexes
                if len(indexes) == 1:
                    return delegate.item_selected(list(indexes)[0])
            if key.is_up_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    new_index = max(min(indexes) - 1, 0)
                elif delegate.item_count > 0:
                    new_index = delegate.item_count - 1
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(-1)
                return True
            if key.is_down_arrow:
                new_index = None
                indexes = self.__selection.indexes
                if len(indexes) > 0:
                    new_index = min(max(indexes) + 1, delegate.item_count - 1)
                elif delegate.item_count > 0:
                    new_index = 0
                if new_index is not None:
                    if key.modifiers.shift:
                        self.__selection.extend(new_index)
                    else:
                        self.__selection.set(new_index)
                self.__make_selection_visible(1)
                return True
        return super().key_pressed(key)

    def drag_enter(self, mime_data: UserInterface.MimeData) -> str:
        self.__dropping = True
        self.update()
        return "ignore"

    def drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        mouse_index = y // self.__item_height
        delegate = self.__delegate
        max_index = delegate.item_count if delegate else 0
        drop_index = None
        if mouse_index >= 0 and mouse_index < max_index:
            drop_index = mouse_index
            if delegate:
                if not delegate.item_can_drop_mime_data(mime_data, "move", drop_index):
                    drop_index = None
            else:
                drop_index = None
        if drop_index != self.__drop_index:
            self.__drop_index = drop_index
            self.update()
        return "ignore"

    def drag_leave(self) -> str:
        self.__dropping = False
        self.__drop_index = None
        self.update()
        return "ignore"

    def drop(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        drop_index = self.__drop_index
        self.__dropping = False
        self.__drop_index = None
        self.update()
        if drop_index is not None:
            delegate = self.__delegate
            if delegate:
                return delegate.item_drop_mime_data(mime_data, "move", drop_index)
        return "ignore"

    def handle_select_all(self) -> bool:
        delegate = self.__delegate
        if delegate:
            self.__selection.set_multiple(set(range(delegate.item_count)))
            return True
        return False

    def handle_delete(self) -> bool:
        delegate = self.__delegate
        if delegate:
            delegate.delete_pressed()
        return True

    def size_to_content(self) -> None:
        """Size the canvas item to the height of the items."""
        delegate = self.__delegate
        if delegate:
            height = self.__item_height * delegate.item_count
            new_sizing = self.sizing.with_minimum_height(height).with_maximum_height(height)
            self.update_sizing(new_sizing)
