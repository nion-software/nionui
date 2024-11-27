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


class ListColumnLayout(CanvasItem.CanvasItemAbstractLayout):
    def __init__(self, item_height: int, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None, alignment: typing.Optional[str] = None) -> None:
        super().__init__(margins, spacing)
        self.item_height = item_height
        self.alignment = alignment

    def copy(self) -> CanvasItem.CanvasItemAbstractLayout:
        return ListColumnLayout(self.item_height, self.margins, self.spacing, self.alignment)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[CanvasItem.LayoutItem]) -> None:
        # calculate the vertical placement
        origins = [canvas_origin.y + self.margins.top + index * (self.item_height + self.spacing) for index in range(len(canvas_items))]
        sizes = [self.item_height] * len(canvas_items)
        column_layout = CanvasItem.ConstraintResultType(origins, sizes)
        widths = [canvas_item.layout_sizing.get_unrestrained_width(canvas_size.width - self.margins.left - self.margins.right) for canvas_item in canvas_items]
        available_width = canvas_size.width - self.margins.left - self.margins.right
        if self.alignment == "start":
            x_positions = [canvas_origin.x + self.margins.left for width in widths]
        elif self.alignment == "end":
            x_positions = [canvas_origin.x + self.margins.left + (available_width - width) for width in widths]
        else:
            x_positions = [round(canvas_origin.x + self.margins.left + (available_width - width) * 0.5) for width in widths]
        self.layout_canvas_items(x_positions, column_layout.origins, widths, column_layout.sizes, canvas_items)

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


class ListItemAdornmentsCanvasItemComposer(CanvasItem.BaseComposer):
    def __init__(self, canvas_item: CanvasItem.AbstractCanvasItem, layout_sizing: CanvasItem.Sizing, composer_cache: CanvasItem.ComposerCache, is_dropping: bool) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__is_dropping = is_dropping

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: CanvasItem.ComposerCache) -> None:
        if self.__is_dropping:
            with drawing_context.saver():
                drop_border_width = 2.5
                rect_in = canvas_rect.to_float_rect().inset(drop_border_width / 2, drop_border_width / 2).to_int_rect()
                drawing_context.begin_path()
                drawing_context.rect(rect_in.left, rect_in.top, rect_in.width, rect_in.height)
                drawing_context.line_width = drop_border_width
                drawing_context.stroke_style = "rgba(56, 117, 214, 0.8)"
                drawing_context.stroke()


class ListItemAdornmentsCanvasItem(CanvasItem.AbstractCanvasItem):
    # ADR: since this is an internal class, we can use a weak reference to the list canvas item as a way to send messages
    def __init__(self, list_canvas_item: ListCanvasItem2, item: typing.Any, is_dropping: bool = False) -> None:
        super().__init__()
        self.__item = item
        self.__list_canvas_item_ref = weakref.ref(list_canvas_item)
        self.__is_dropping = is_dropping

    @property
    def is_dropping(self) -> bool:
        return self.__is_dropping

    @is_dropping.setter
    def is_dropping(self, value: bool) -> None:
        self.__is_dropping = value
        self.update()

    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> typing.Optional[CanvasItem.BaseComposer]:
        return ListItemAdornmentsCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__is_dropping)


ListItemFactory = typing.Callable[[typing.Any, Model.PropertyModel[bool]], CanvasItem.AbstractCanvasItem]


class ListItemCanvasItem(CanvasItem.CanvasItemComposition):
    def __init__(self, list_canvas_item: ListCanvasItem2, item: typing.Any, item_factory: ListItemFactory) -> None:
        super().__init__()
        self.__list_canvas_item_ref = weakref.ref(list_canvas_item)
        self.__item = item
        self.__is_selected_model = Model.PropertyModel(False)
        self.__is_focused_model = Model.PropertyModel(False)
        self.__is_dropping_model = Model.PropertyModel(False)
        self.__background_canvas_item = CanvasItem.BackgroundCanvasItem(None, None)  # no fallback color
        self.__adornments_canvas_item = ListItemAdornmentsCanvasItem(list_canvas_item, item)
        self.add_canvas_item(self.__background_canvas_item)
        self._canvas_item = item_factory(item, self.__is_selected_model)
        self.add_canvas_item(self._canvas_item)
        self.add_canvas_item(self.__adornments_canvas_item)

    @property
    def __list_canvas_item(self) -> ListCanvasItem2:
        list_canvas_item = self.__list_canvas_item_ref()
        assert list_canvas_item
        return list_canvas_item

    @property
    def item(self) -> typing.Any:
        return self.__item

    @property
    def is_selected(self) -> bool:
        return self.__is_selected_model.value or False

    @is_selected.setter
    def is_selected(self, value: bool) -> None:
        if value != self.is_selected:
            self.__is_selected_model.value = value
            self.__update_background_color()
            self.update()

    @property
    def is_focused(self) -> bool:
        return self.__is_focused_model.value or False

    @is_focused.setter
    def is_focused(self, value: bool) -> None:
        if value != self.is_focused:
            self.__is_focused_model.value = value
            self.__update_background_color()
            self.update()

    @property
    def tool_tip(self) -> typing.Optional[str]:
        list_canvas_item = self.__list_canvas_item_ref()
        if list_canvas_item:
            return list_canvas_item._get_tool_tip(self.__item)
        return str()

    @tool_tip.setter
    def tool_tip(self, value: typing.Optional[str]) -> None:
        pass

    def __update_background_color(self) -> None:
        if self.is_selected:
            background_color = "#3875D6" if self.is_focused else "#DDD"
        else:
            background_color = None
        self.__background_canvas_item.background_color = background_color

    @property
    def is_dropping(self) -> bool:
        return self.__is_dropping_model.value or False

    @is_dropping.setter
    def is_dropping(self, value: bool) -> None:
        if value != self.is_dropping:
            self.__is_dropping_model.value = value
            self.update()

    def context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        list_canvas_item = self.__list_canvas_item_ref()
        if list_canvas_item:
            if list_canvas_item._handle_context_menu_event(self.__item, Geometry.IntPoint(x=x, y=y), Geometry.IntPoint(x=gx, y=gy)):
                return True
        return super().context_menu_event(x, y, gx, gy)


@dataclasses.dataclass
class ListCanvasItem2ContextMenuEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    p: Geometry.IntPoint
    gp: Geometry.IntPoint


@dataclasses.dataclass
class ListCanvasItem2DeleteEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]


@dataclasses.dataclass
class ListCanvasItem2SelectEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]


@dataclasses.dataclass
class ListCanvasItem2DragStartedEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    p: Geometry.IntPoint
    modifiers: UserInterface.KeyboardModifiers


class ListCanvasItem2Delegate:

    def context_menu_event(self, context_menu_event: ListCanvasItem2ContextMenuEvent) -> bool:
        return False

    def select_event(self, select_event: ListCanvasItem2SelectEvent) -> bool:
        return False

    def delete_event(self, delete_event: ListCanvasItem2DeleteEvent) -> bool:
        return False

    def drag_started_event(self, event: ListCanvasItem2DragStartedEvent) -> bool:
        return False

    def item_tool_tip(self, item: typing.Any) -> typing.Optional[str]:
        return None


class ListCanvasItem2(CanvasItem.CanvasItemComposition):
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

    def __init__(self, list_model: ListModel.ListModelLike, selection: Selection.IndexedSelection, item_factory: ListItemFactory, delegate: ListCanvasItem2Delegate, item_height: int = 80, *, key: typing.Optional[str] = None) -> None:
        super().__init__()
        # store parameters
        self.__list_model = list_model
        self.__list_model_key = key or "items"
        self.__selection = selection
        self.__selection_changed_listener = self.__selection.changed_event.listen(ReferenceCounting.weak_partial(ListCanvasItem2.__handle_selection_changed, self))
        self.__item_factory = item_factory
        self.__delegate = delegate
        # configure super
        self.__layout = ListColumnLayout(item_height)
        self.layout = self.__layout
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__needs_size_to_content = False  # delay sizing during batch updates
        self.__list_item_canvas_items = list[ListItemCanvasItem]()
        self.__item_inserted_listener = list_model.item_inserted_event.listen(ReferenceCounting.weak_partial(ListCanvasItem2.__handle_item_inserted, self))
        self.__item_removed_listener = list_model.item_removed_event.listen(ReferenceCounting.weak_partial(ListCanvasItem2.__handle_item_removed, self))
        self.__mouse_index: typing.Optional[int] = None
        self.__mouse_canvas_item: typing.Optional[ListItemCanvasItem] = None
        self.__mouse_pressed = False
        self.__mouse_pressed_for_dragging = False
        self.__mouse_position: typing.Optional[Geometry.IntPoint] = None
        self.__mouse_dragging = False
        self.__dropping = True
        self.__drop_before_index: typing.Optional[int] = None
        self.__drop_index: typing.Optional[int] = None
        self.__item_height = item_height
        # initialize
        for index, item in enumerate(list_model.items):
            self.__handle_item_inserted(self.__list_model_key, item, index)
        self.__handle_selection_changed()

    @property
    def _delegate(self) -> ListCanvasItem2Delegate:
        return self.__delegate

    def __handle_item_inserted(self, key: str, item: typing.Any, index: int) -> None:
        if key == self.__list_model_key:
            list_item_canvas_item = ListItemCanvasItem(self, item, self.__item_factory)
            with self.batch_update():
                self.insert_canvas_item(index, list_item_canvas_item)
                self.__list_item_canvas_items.insert(index, list_item_canvas_item)
                self.__needs_size_to_content = True

    def __handle_item_removed(self, key: str, item: typing.Any, index: int) -> None:
        if key == self.__list_model_key:
            with self.batch_update():
                self.remove_canvas_item(self.canvas_items[index])
                self.__list_item_canvas_items.pop(index)
                self.__needs_size_to_content = True

    def _batch_update_ended(self) -> None:
        if self.__needs_size_to_content:
            self.size_to_content()
            self.__needs_size_to_content = False

    def __handle_selection_changed(self) -> None:
        for index, canvas_item in enumerate(typing.cast(typing.Sequence[ListItemCanvasItem], self.canvas_items)):
            canvas_item.is_selected = self.__selection.contains(index)

    def __list_item_at_point(self, p: Geometry.IntPoint) -> typing.Optional[ListItemCanvasItem]:
        for canvas_item in self.__list_item_canvas_items:
            canvas_rect = canvas_item.canvas_rect
            if canvas_rect and canvas_rect.contains_point(p):
                return canvas_item
        return None

    def mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        # sets the selection to the item if there is no selection and returns True.
        # otherwise returns False. False means there was an existing selection.
        canvas_item = self.__list_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            mouse_index = self.__list_item_canvas_items.index(canvas_item)
            if not self.__selection.contains(mouse_index):
                self.__selection.set(mouse_index)
                self.handle_select()
                return True
        return super().mouse_double_clicked(x, y, modifiers)

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        canvas_item = self.__list_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            self.__mouse_index = self.__list_item_canvas_items.index(canvas_item)
            self.__mouse_canvas_item = canvas_item
            self.__mouse_pressed = True
            if not modifiers.shift and not modifiers.control:
                self.__mouse_pressed_for_dragging = True
                self.__mouse_position = Geometry.IntPoint(y=y, x=x)
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__mouse_released(x, y, modifiers, True)
        return True

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__mouse_pressed_for_dragging and self.__mouse_position and self.__mouse_index is not None:
            mouse_position_f = self.__mouse_position.to_float_point()
            point_f = Geometry.FloatPoint(y=y, x=x)
            if self.__mouse_canvas_item and not self.__mouse_dragging and Geometry.distance(mouse_position_f, point_f) > 8:
                self.__mouse_dragging = True
                root_container = self.root_container
                if root_container:
                    root_container.bypass_request_focus()
                selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
                selected_items = selected_items if self.__mouse_canvas_item in selected_items else [self.__mouse_canvas_item]
                if self.__delegate.drag_started_event(ListCanvasItem2DragStartedEvent(self.__mouse_canvas_item.item, selected_items, Geometry.IntPoint(x=x, y=y), modifiers)):
                    # once a drag starts, mouse release will not be called; call it here instead
                    self.__mouse_released(x, y, modifiers, False)
                    return True
        return super().mouse_position_changed(x, y, modifiers)

    def __mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers, do_select: bool) -> None:
        if self.__mouse_pressed and do_select:
            # double check whether mouse_released has been called explicitly as part of a drag.
            # see https://bugreports.qt.io/browse/QTBUG-40733
            mouse_index = self.__mouse_index
            if mouse_index is not None:
                if modifiers.shift:
                    self.__selection.extend(mouse_index)
                elif modifiers.control:
                    self.__selection.toggle(mouse_index)
                else:
                    self.__selection.set(mouse_index)
        self.__mouse_pressed = False
        self.__mouse_pressed_for_dragging = False
        self.__mouse_index = None
        self.__mouse_canvas_item = None
        self.__mouse_position = None
        self.__mouse_dragging = False

    def _handle_context_menu_event(self, item: typing.Any, p: Geometry.IntPoint, gp: Geometry.IntPoint) -> bool:
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        return self.__delegate.context_menu_event(ListCanvasItem2ContextMenuEvent(item, selected_items, p, gp))

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        canvas_item = self.__list_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            text = canvas_item.tool_tip
            if text:
                self.show_tool_tip_text(text, gx, gy)
                return True
        return super().handle_tool_tip(x, y, gx, gy)

    def _get_tool_tip(self, item: typing.Any) -> typing.Optional[str]:
        return self.__delegate.item_tool_tip(item)

    def __rect_for_index(self, index: int) -> Geometry.IntRect:
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            canvas_rect = self.canvas_items[index].canvas_rect
            if canvas_rect:
                return canvas_rect
        return Geometry.IntRect.empty_rect()

    def __make_selection_visible(self, style: int) -> None:
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

    def _set_focused(self, focused: bool) -> None:
        super()._set_focused(focused)
        for list_item_canvas_item in self.__list_item_canvas_items:
            list_item_canvas_item.is_focused = focused

    def key_pressed(self, key: UserInterface.Key) -> bool:
        item_count = len(self.__list_model.items)
        if key.is_delete:
            if self.handle_delete():
                return True
        if key.is_enter_or_return:
            if self.handle_select():
                return True
        if key.is_up_arrow:
            new_index = None
            indexes = self.__selection.indexes
            if len(indexes) > 0:
                new_index = max(min(indexes) - 1, 0)
            elif item_count > 0:
                new_index = item_count - 1
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
                new_index = min(max(indexes) + 1, item_count - 1)
            elif item_count > 0:
                new_index = 0
            if new_index is not None:
                if key.modifiers.shift:
                    self.__selection.extend(new_index)
                else:
                    self.__selection.set(new_index)
            self.__make_selection_visible(1)
            return True
        return super().key_pressed(key)

    def _can_drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> bool:
        return False

    def _drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> str:
        return "ignore"

    def drag_enter(self, mime_data: UserInterface.MimeData) -> str:
        self.__dropping = True
        return "ignore"

    def drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        mouse_index = y // self.__item_height
        max_index = len(self.__list_model.items)
        drop_index = None
        if mouse_index >= 0 and mouse_index < max_index:
            drop_index = mouse_index
            if not self._can_drop_mime_data(mime_data, "move", drop_index):
                drop_index = None
        if drop_index != self.__drop_index:
            self.__drop_index = drop_index
        return "ignore"

    def drag_leave(self) -> str:
        self.__dropping = False
        self.__drop_index = None
        return "ignore"

    def drop(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        drop_index = self.__drop_index
        self.__dropping = False
        self.__drop_index = None
        self.update()
        if drop_index is not None:
            return self._drop_mime_data(mime_data, "move", drop_index)
        return "ignore"

    def handle_select_all(self) -> bool:
        self.__selection.set_multiple(set(range(len(self.__list_model.items))))
        return True

    def handle_delete(self) -> bool:
        item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        if self.__delegate.delete_event(ListCanvasItem2DeleteEvent(item, selected_items)):
            return True
        return False

    def handle_select(self) -> bool:
        item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        if self.__delegate.select_event(ListCanvasItem2SelectEvent(item, selected_items)):
            return True
        return False

    def size_to_content(self) -> None:
        """Size the canvas item to the height of the items."""
        self.update_sizing(self.__layout.get_sizing(self.canvas_items))
