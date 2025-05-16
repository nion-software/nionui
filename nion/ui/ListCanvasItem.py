"""
    List of drawable cells.

    TODO: ListCanvasItem should handle dragging multiple items
    TODO: ListCanvasItem should handle keyboard navigation
    TODO: ListCanvasItem should allow drag selection to select multiple
"""

# futures
from __future__ import annotations

# standard libraries
import dataclasses
import typing
import weakref

# third party libraries
# none

# local libraries
from nion.ui import CanvasItem
from nion.ui import GridFlowCanvasItem
from nion.ui import UserInterface
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Model
from nion.utils import ReferenceCounting

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

    def mouse_double_clicked_in_item(self, mouse_index: int, pos: Geometry.IntPoint, modifiers: UserInterface.KeyboardModifiers) -> bool:
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

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: CanvasItem.ComposerCache) -> None:
        canvas_size = canvas_rect.size
        visible_rect = Geometry.IntRect(Geometry.IntPoint(), canvas_rect.size)
        delegate = self.__delegate
        item_height = self.__item_height
        drop_index = self.__drop_index
        selection = self.__selection
        focused = self.__focused
        if canvas_size.height > 0 and canvas_size.width > 0:
            item_width = canvas_rect.width

            with drawing_context.saver():
                drawing_context.translate(canvas_rect.left, canvas_rect.top)
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

    def _rect_for_index(self, index: int) -> Geometry.IntRect:
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
                handled = delegate.mouse_double_clicked_in_item(mouse_index, Geometry.IntPoint(y=y - mouse_index * self.__item_height, x=x), modifiers)
                return handled or delegate.item_selected(mouse_index)
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
                min_rect = self._rect_for_index(min_index)
                max_rect = self._rect_for_index(max_index)
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


class ListRowLayout(CanvasItem.CanvasItemAbstractLayout):
    def __init__(self, item_width: int, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None, alignment: typing.Optional[str] = None) -> None:
        super().__init__(margins, spacing)
        self.item_width = item_width
        self.alignment = alignment

    def copy(self) -> CanvasItem.CanvasItemAbstractLayout:
        return ListRowLayout(self.item_width, self.margins, self.spacing, self.alignment)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[CanvasItem.LayoutItem]) -> None:
        # layout does nothing in this class. instead the items themselves are laid out with a 0,0 origin and then the repaint
        # adjusts each items position as it is drawn.
        return

    def get_sizing(self, canvas_items: typing.Sequence[CanvasItem.LayoutSizingItem]) -> CanvasItem.Sizing:
        sizing_data = CanvasItem.SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_height = 0
        if canvas_items:
            canvas_item = canvas_items[0]
            canvas_item_sizing = canvas_item.layout_sizing
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_height", max, True)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_height", max)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_height", max, True)
        canvas_item_count = len(canvas_items)
        if sizing_data.maximum_height == 0 or canvas_item_count == 0:
            sizing_data.maximum_height = None
        if sizing_data.preferred_height == 0 or canvas_item_count == 0:
            sizing_data.preferred_height = None
        return CanvasItem.Sizing(sizing_data).with_fixed_width(self.item_width * canvas_item_count + self.spacing * (max(0, canvas_item_count - 1)))

    def create_spacing_item(self, spacing: int) -> CanvasItem.AbstractCanvasItem:
        raise NotImplementedError()

    def create_stretch_item(self) -> CanvasItem.AbstractCanvasItem:
        raise NotImplementedError()


class ListColumnLayout(CanvasItem.CanvasItemAbstractLayout):
    def __init__(self, item_height: int, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None, alignment: typing.Optional[str] = None) -> None:
        super().__init__(margins, spacing)
        self.item_height = item_height
        self.alignment = alignment

    def copy(self) -> CanvasItem.CanvasItemAbstractLayout:
        return ListColumnLayout(self.item_height, self.margins, self.spacing, self.alignment)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[CanvasItem.LayoutItem]) -> None:
        # layout does nothing in this class. instead the items themselves are laid out with a 0,0 origin and then the repaint
        # adjusts each items position as it is drawn.
        return

    def get_sizing(self, canvas_items: typing.Sequence[CanvasItem.LayoutSizingItem]) -> CanvasItem.Sizing:
        sizing_data = CanvasItem.SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_width = 0
        if canvas_items:
            canvas_item = canvas_items[0]
            canvas_item_sizing = canvas_item.layout_sizing
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_width", max, True)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_width", max)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_width", max, True)
        canvas_item_count = len(canvas_items)
        if sizing_data.maximum_width == 0 or canvas_item_count == 0:
            sizing_data.maximum_width = None
        if sizing_data.preferred_width == 0 or canvas_item_count == 0:
            sizing_data.preferred_width = None
        return CanvasItem.Sizing(sizing_data).with_fixed_height(self.item_height * canvas_item_count + self.spacing * (max(0, canvas_item_count - 1)))

    def create_spacing_item(self, spacing: int) -> CanvasItem.AbstractCanvasItem:
        raise NotImplementedError()

    def create_stretch_item(self) -> CanvasItem.AbstractCanvasItem:
        raise NotImplementedError()


ListCanvasItem2ContextMenuEvent = GridFlowCanvasItem.GridFlowCanvasItemContextMenuEvent

ListCanvasItem2DeleteEvent = GridFlowCanvasItem.GridFlowCanvasItemDeleteEvent

ListCanvasItem2SelectEvent = GridFlowCanvasItem.GridFlowCanvasItemSelectEvent

ListCanvasItem2DragStartedEvent = GridFlowCanvasItem.GridFlowCanvasItemDragStartedEvent

ListCanvasItem2Delegate = GridFlowCanvasItem.GridFlowCanvasItemDelegate


class ListCanvasItemCompositionComposer(CanvasItem.CanvasItemCompositionComposer):
    def __init__(self,
                 canvas_item: CanvasItem.AbstractCanvasItem,
                 layout_sizing: CanvasItem.Sizing,
                 composer_cache: CanvasItem.ComposerCache,
                 layout: CanvasItem.CanvasItemAbstractLayout,
                 child_composers: typing.Sequence[CanvasItem.BaseComposer],
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]],
                 border_color: typing.Optional[str],
                 list_model: ListModel.ListModelLike,
                 item_width: int | None,
                 item_height: int | None) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache, layout, child_composers, background_color, border_color)
        self.__list_model = list_model
        self.__item_width = item_width
        self.__item_height = item_height

    def _repaint_children(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, child_composers: typing.Sequence[CanvasItem.BaseComposer]) -> None:
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            visible_rect -= canvas_rect.origin
            for index, child_composer in enumerate(child_composers):
                if self.__item_height:
                    child_canvas_rect = Geometry.IntRect(Geometry.IntPoint(y=index * self.__item_height, x=0), Geometry.IntSize(width=canvas_rect.width, height=self.__item_height))
                elif self.__item_width:
                    child_canvas_rect = Geometry.IntRect(Geometry.IntPoint(y=0, x=index * self.__item_width), Geometry.IntSize(width=self.__item_width, height=canvas_rect.height))
                else:
                    child_canvas_rect = Geometry.IntRect(Geometry.IntPoint(), Geometry.IntSize())
                if visible_rect.intersects_rect(child_canvas_rect):
                    with drawing_context.saver():
                        child_composer.update_layout(Geometry.IntPoint(), child_canvas_rect.size)
                        child_composer.repaint(drawing_context, child_canvas_rect, visible_rect)


class ListCanvasItem2(GridFlowCanvasItem.GridFlowCanvasItem):
    """A canvas item that displays a list of items.

    is_shared_selection parameter is used to share the selection with another canvas item and prevents the selection
    from being modified when items are inserted or removed.
    """

    def __init__(self, list_model: ListModel.ListModelLike, selection: Selection.IndexedSelection, item_factory: GridFlowCanvasItem.GridFlowItemFactory, delegate: GridFlowCanvasItem.GridFlowCanvasItemDelegate, item_width: int | None = None, item_height: int | None = None, *, key: typing.Optional[str] = None, is_shared_selection: bool = False) -> None:
        layout: CanvasItem.CanvasItemAbstractLayout | None = None
        if item_width is not None:
            layout = ListRowLayout(item_width)
        if item_height is not None:
            layout = ListColumnLayout(item_height)
        assert layout
        super().__init__(list_model, selection, layout, item_factory, delegate, key=key, is_shared_selection=is_shared_selection)
        self.__item_width = item_width
        self.__item_height = item_height

    def _get_composition_composer(self, child_composers: typing.Sequence[CanvasItem.BaseComposer], composer_cache: CanvasItem.ComposerCache) -> CanvasItem.BaseComposer:
        return ListCanvasItemCompositionComposer(self, self.layout_sizing, composer_cache, self.layout.copy(), child_composers, self.background_color, self.border_color, self._list_model, self.__item_width, self.__item_height)

    def _handle_up_arrow(self, key: UserInterface.Key) -> bool:
        return self._adjust_selection_backward(1, key.modifiers.shift)

    def _handle_down_arrow(self, key: UserInterface.Key) -> bool:
        return self._adjust_selection_forward(1, key.modifiers.shift)

    def _handle_left_arrow(self, key: UserInterface.Key) -> bool:
        return self._adjust_selection_backward(1, key.modifiers.shift)

    def _handle_right_arrow(self, key: UserInterface.Key) -> bool:
        return self._adjust_selection_forward(1, key.modifiers.shift)

    def _get_grid_flow_item_canvas_rect(self, index: int, canvas_size: Geometry.IntSize) -> Geometry.IntRect:
        if self.__item_width is not None:
            return Geometry.IntRect(Geometry.IntPoint(0, index * self.__item_width), Geometry.IntSize(width=self.__item_width, height=canvas_size.height))
        elif self.__item_height is not None:
            return Geometry.IntRect(Geometry.IntPoint(index * self.__item_height, 0), Geometry.IntSize(width=canvas_size.width, height=self.__item_height))
        return Geometry.IntRect(Geometry.IntPoint(), Geometry.IntSize())

    def _get_index_for_point(self, p: Geometry.IntPoint, canvas_size: Geometry.IntSize) -> int:
        if self.__item_width is not None:
            return round(p.x // self.__item_width)
        elif self.__item_height is not None:
            return round(p.y // self.__item_height)
        else:
            return 0
