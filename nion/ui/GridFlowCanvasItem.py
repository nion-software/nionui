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
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Model
from nion.utils import ReferenceCounting

if typing.TYPE_CHECKING:
    from nion.ui import DrawingContext
    from nion.utils import Selection


class GridFlowItemAdornmentsCanvasItemComposer(CanvasItem.BaseComposer):
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


class GridFlowItemAdornmentsCanvasItem(CanvasItem.AbstractCanvasItem):
    # ADR: since this is an internal class, we can use a weak reference to the list canvas item as a way to send messages
    def __init__(self, grid_flow_canvas_item: GridFlowCanvasItem, item: typing.Any, is_dropping: bool = False) -> None:
        super().__init__()
        self.__item = item
        self.__grid_flow_canvas_item_ref = weakref.ref(grid_flow_canvas_item)
        self.__is_dropping = is_dropping

    @property
    def is_dropping(self) -> bool:
        return self.__is_dropping

    @is_dropping.setter
    def is_dropping(self, value: bool) -> None:
        self.__is_dropping = value
        self.update()

    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> CanvasItem.BaseComposer | None:
        return GridFlowItemAdornmentsCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__is_dropping)


GridFlowItemFactory = typing.Callable[[typing.Any, Model.PropertyModel[bool]], CanvasItem.AbstractCanvasItem]


class GridFlowItemCanvasItem(CanvasItem.CanvasItemComposition):
    def __init__(self, grid_flow_canvas_item: GridFlowCanvasItem, item: typing.Any, item_factory: GridFlowItemFactory) -> None:
        super().__init__()
        self.__grid_flow_canvas_item_ref = weakref.ref(grid_flow_canvas_item)
        self.__item = item
        self.__is_selected_model = Model.PropertyModel(False)
        self.__is_focused_model = Model.PropertyModel(False)
        self.__is_dropping_model = Model.PropertyModel(False)
        self.__background_canvas_item = CanvasItem.BackgroundCanvasItem(None, None)  # no fallback color
        self.__adornments_canvas_item = GridFlowItemAdornmentsCanvasItem(grid_flow_canvas_item, item)
        self.add_canvas_item(self.__background_canvas_item)
        self._canvas_item = item_factory(item, self.__is_selected_model)
        self.add_canvas_item(self._canvas_item)
        self.add_canvas_item(self.__adornments_canvas_item)

    @property
    def __grid_flow_canvas_item(self) -> GridFlowCanvasItem:
        grid_flow_canvas_item = self.__grid_flow_canvas_item_ref()
        assert grid_flow_canvas_item
        return grid_flow_canvas_item

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
    def tool_tip(self) -> str | None:
        grid_flow_canvas_item = self.__grid_flow_canvas_item_ref()
        if grid_flow_canvas_item:
            return grid_flow_canvas_item._get_tool_tip(self.__item)
        return str()

    @tool_tip.setter
    def tool_tip(self, value: str | None) -> None:
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
        grid_flow_canvas_item = self.__grid_flow_canvas_item_ref()
        if grid_flow_canvas_item:
            if grid_flow_canvas_item._handle_context_menu_event(self.__item, Geometry.IntPoint(x=x, y=y), Geometry.IntPoint(x=gx, y=gy)):
                return True
        return super().context_menu_event(x, y, gx, gy)


@dataclasses.dataclass
class GridFlowCanvasItemKeyPressedEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    key: UserInterface.Key


@dataclasses.dataclass
class GridFlowCanvasItemDoubleClickedEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    p: Geometry.IntPoint
    modifiers: UserInterface.KeyboardModifiers


@dataclasses.dataclass
class GridFlowCanvasItemContextMenuEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    p: Geometry.IntPoint
    gp: Geometry.IntPoint


@dataclasses.dataclass
class GridFlowCanvasItemDeleteEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]


@dataclasses.dataclass
class GridFlowCanvasItemSelectEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]


@dataclasses.dataclass
class GridFlowCanvasItemDragStartedEvent:
    item: typing.Any
    selected_items: typing.Sequence[typing.Any]
    p: Geometry.IntPoint
    modifiers: UserInterface.KeyboardModifiers


class GridFlowCanvasItemDelegate:

    def key_pressed_event(self, key_event: GridFlowCanvasItemKeyPressedEvent) -> bool:
        return False

    def mouse_double_clicked_event(self, double_clicked_event: GridFlowCanvasItemDoubleClickedEvent) -> bool:
        return False

    def context_menu_event(self, context_menu_event: GridFlowCanvasItemContextMenuEvent) -> bool:
        return False

    def select_event(self, select_event: GridFlowCanvasItemSelectEvent) -> bool:
        return False

    def delete_event(self, delete_event: GridFlowCanvasItemDeleteEvent) -> bool:
        return False

    def drag_started_event(self, event: GridFlowCanvasItemDragStartedEvent) -> bool:
        return False

    def can_drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int | None) -> bool:
        return False

    def drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int | None) -> str:
        return "ignore"

    def item_tool_tip(self, item: typing.Any) -> str | None:
        return None


class GridFlowCanvasItem(CanvasItem.CanvasItemComposition):
    """A canvas item that displays a list of items in a grid flow layout.

    is_shared_selection parameter is used to share the selection with another canvas item and prevents the selection
    from being modified when items are inserted or removed.
    """

    def __init__(self, list_model: ListModel.ListModelLike, selection: Selection.IndexedSelection, layout: CanvasItem.CanvasItemAbstractLayout, item_factory: GridFlowItemFactory, delegate: GridFlowCanvasItemDelegate, *, key: str | None = None, is_shared_selection: bool = False) -> None:
        super().__init__()
        # store parameters
        self.__list_model = list_model
        self.__list_model_key = key or "items"
        self.__selection = selection
        self.__layout = layout
        self.__item_factory = item_factory
        self.__delegate = delegate
        self.__is_shared_selection = is_shared_selection
        # configure super
        self.layout = self.__layout
        self.wants_mouse_events = True
        self.focusable = True
        # internal variables
        self.__selection_changed_listener = self.__selection.changed_event.listen(ReferenceCounting.weak_partial(GridFlowCanvasItem.__handle_selection_changed, self))
        self.__needs_size_to_content = False  # delay sizing during batch updates
        self.__grid_flow_item_canvas_items = list[GridFlowItemCanvasItem]()
        self.__item_inserted_listener = list_model.item_inserted_event.listen(ReferenceCounting.weak_partial(GridFlowCanvasItem.__handle_item_inserted, self))
        self.__item_removed_listener = list_model.item_removed_event.listen(ReferenceCounting.weak_partial(GridFlowCanvasItem.__handle_item_removed, self))
        self.__mouse_index: int | None = None
        self.__mouse_canvas_item: GridFlowItemCanvasItem | None = None
        self.__mouse_pressed = False
        self.__mouse_pressed_for_dragging = False
        self.__mouse_position: Geometry.IntPoint | None = None
        self.__mouse_dragging = False
        self.__dropping = True
        self.__drop_before_index: int | None = None
        self.__drop_index: int | None = None
        # initialize
        for index, item in enumerate(list_model.items):
            self.__handle_item_inserted(self.__list_model_key, item, index)
        self.__handle_selection_changed()

    @property
    def _list_model(self) -> ListModel.ListModelLike:
        return self.__list_model

    @property
    def _delegate(self) -> GridFlowCanvasItemDelegate:
        return self.__delegate

    @property
    def _selection(self) -> Selection.IndexedSelection:
        return self.__selection

    def __handle_item_inserted(self, key: str, item: typing.Any, index: int) -> None:
        if key == self.__list_model_key:
            grid_flow_item_canvas_item = GridFlowItemCanvasItem(self, item, self.__item_factory)
            with self.batch_update():
                self.insert_canvas_item(index, grid_flow_item_canvas_item)
                self.__grid_flow_item_canvas_items.insert(index, grid_flow_item_canvas_item)
                if not self.__is_shared_selection:
                    self.__selection.insert_index(index)
                self.__needs_size_to_content = True

    def __handle_item_removed(self, key: str, item: typing.Any, index: int) -> None:
        if key == self.__list_model_key:
            with self.batch_update():
                self.remove_canvas_item(self.canvas_items[index])
                self.__grid_flow_item_canvas_items.pop(index)
                if not self.__is_shared_selection:
                    self.__selection.remove_index(index)
                self.__needs_size_to_content = True

    def _batch_update_ended(self) -> None:
        if self.__needs_size_to_content:
            self.size_to_content()
            self.__needs_size_to_content = False

    def __handle_selection_changed(self) -> None:
        for index, canvas_item in enumerate(typing.cast(typing.Sequence[GridFlowItemCanvasItem], self.canvas_items)):
            canvas_item.is_selected = self.__selection.contains(index)

    def __grid_flow_item_at_point(self, p: Geometry.IntPoint) -> GridFlowItemCanvasItem | None:
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            for index, canvas_item in enumerate(self.__grid_flow_item_canvas_items):
                canvas_rect = self._get_grid_flow_item_canvas_rect(index, canvas_bounds.size)
                if canvas_rect and canvas_rect.contains_point(p):
                    return canvas_item
        return None

    def _get_grid_flow_item_canvas_rect(self, index: int, canvas_size: Geometry.IntSize) -> Geometry.IntRect:
        raise NotImplementedError()

    def _get_index_for_point(self, p: Geometry.IntPoint, canvas_size: Geometry.IntSize) -> int:
        raise NotImplementedError()

    def canvas_items_at_point(self, x: int, y: int) -> typing.List[CanvasItem.AbstractCanvasItem]:
        canvas_items: typing.List[CanvasItem.AbstractCanvasItem] = []
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            index = self._get_index_for_point(Geometry.IntPoint(x=x, y=y), canvas_bounds.size)
            if index < len(self.canvas_items):
                child_canvas_rect = self._get_grid_flow_item_canvas_rect(index, canvas_bounds.size)
                canvas_item = self.canvas_items[index]
                canvas_point = Geometry.IntPoint(x=x, y=y) - child_canvas_rect.origin
                if child_canvas_rect.contains_point(Geometry.IntPoint(x=x, y=y)):
                    canvas_items.extend(canvas_item.canvas_items_at_point(canvas_point.x, canvas_point.y))
                    canvas_items.append(canvas_item)
            if canvas_bounds.contains_point(Geometry.IntPoint(x=x, y=y)):
                canvas_items.append(self)
        return canvas_items

    def mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        # sets the selection to the item if there is no selection and returns True.
        # otherwise returns False. False means there was an existing selection.
        canvas_item = self.__grid_flow_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            mouse_index = self.__grid_flow_item_canvas_items.index(canvas_item)
            if not self.__selection.contains(mouse_index):
                self.__selection.set(mouse_index)
                self.handle_select()
            item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
            selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
            selected_items = selected_items if item in selected_items else [item]
            self.__delegate.mouse_double_clicked_event(GridFlowCanvasItemDoubleClickedEvent(canvas_item.item, selected_items, Geometry.IntPoint(x=x, y=y), modifiers))
            return True
        return super().mouse_double_clicked(x, y, modifiers)

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        canvas_item = self.__grid_flow_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            self.__mouse_index = self.__grid_flow_item_canvas_items.index(canvas_item)
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
                if self.__delegate.drag_started_event(GridFlowCanvasItemDragStartedEvent(self.__mouse_canvas_item.item, selected_items, Geometry.IntPoint(x=x, y=y), modifiers)):
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
        return self.__delegate.context_menu_event(GridFlowCanvasItemContextMenuEvent(item, selected_items, p, gp))

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        canvas_item = self.__grid_flow_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            text = canvas_item.tool_tip
            if text:
                self.show_tool_tip_text(text, gx, gy)
                return True
        return super().handle_tool_tip(x, y, gx, gy)

    def _get_tool_tip(self, item: typing.Any) -> str | None:
        return self.__delegate.item_tool_tip(item)

    def __rect_for_index(self, index: int) -> Geometry.IntRect:
        canvas_bounds = self.canvas_bounds
        if canvas_bounds:
            canvas_rect = self._get_grid_flow_item_canvas_rect(index, canvas_bounds.size)
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
                scroll_area.make_selection_visible(min_rect, max_rect, True, True, style < 0)

    def make_selection_visible(self) -> None:
        self.__make_selection_visible(-1)

    def _set_focused(self, focused: bool) -> None:
        super()._set_focused(focused)
        for grid_flow_item_canvas_item in self.__grid_flow_item_canvas_items:
            grid_flow_item_canvas_item.is_focused = focused

    def key_pressed(self, key: UserInterface.Key) -> bool:
        if key.is_delete:
            if self.handle_delete():
                return True
        if key.is_enter_or_return:
            if self.handle_select():
                return True
        if key.is_up_arrow:
            if self._handle_up_arrow(key):
                return True
        if key.is_down_arrow:
            if self._handle_down_arrow(key):
                return True
        if key.is_left_arrow:
            if self._handle_left_arrow(key):
                return True
        if key.is_right_arrow:
            if self._handle_right_arrow(key):
                return True
        item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        if self.__delegate.key_pressed_event(GridFlowCanvasItemKeyPressedEvent(item, selected_items, key)):
            return True
        return super().key_pressed(key)

    def _handle_up_arrow(self, key: UserInterface.Key) -> bool:
        return False

    def _handle_down_arrow(self, key: UserInterface.Key) -> bool:
        return False

    def _handle_left_arrow(self, key: UserInterface.Key) -> bool:
        return False

    def _handle_right_arrow(self, key: UserInterface.Key) -> bool:
        return False

    def _adjust_selection_backward(self, n: int, extend: bool) -> bool:
        item_count = len(self._list_model.items)
        selection = self._selection
        new_index = None
        indexes = selection.indexes
        if len(indexes) > 0:
            new_index = max(min(indexes) - n, 0)
        elif item_count > 0:
            new_index = item_count - n
        if new_index is not None:
            if extend:
                selection.extend(new_index)
            else:
                selection.set(new_index)
        self.make_selection_visible()
        return True

    def _adjust_selection_forward(self, n: int, extend: bool) -> bool:
        item_count = len(self._list_model.items)
        selection = self._selection
        new_index = None
        indexes = selection.indexes
        if len(indexes) > 0:
            new_index = min(max(indexes) + n, item_count - 1)
        elif item_count > 0:
            new_index = 0
        if new_index is not None:
            if extend:
                selection.extend(new_index)
            else:
                selection.set(new_index)
        self.make_selection_visible()
        return True

    def _can_drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> bool:
        return False

    def _drop_mime_data(self, mime_data: UserInterface.MimeData, action: str, drop_index: int) -> str:
        return "ignore"

    def drag_enter(self, mime_data: UserInterface.MimeData) -> str:
        self.__dropping = True
        return "ignore"

    def drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        mouse_index = self.__get_mouse_index(x, y)
        max_index = len(self.__list_model.items)
        drop_index = None
        if mouse_index >= 0 and mouse_index < max_index:
            drop_index = mouse_index
            if not self._can_drop_mime_data(mime_data, "move", drop_index):
                drop_index = None
        if drop_index != self.__drop_index:
            self.__drop_index = drop_index
        return "ignore"

    def __get_mouse_index(self, x: int, y: int) -> int:
        canvas_item = self.__grid_flow_item_at_point(Geometry.IntPoint(x=x, y=y))
        if canvas_item:
            mouse_index = self.__grid_flow_item_canvas_items.index(canvas_item)
        elif x <= 0 or y <= 0:
            mouse_index = 0
        else:
            mouse_index = len(self.__grid_flow_item_canvas_items)
        return mouse_index

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
            internal_drop_result = self._drop_mime_data(mime_data, "move", drop_index)
            if internal_drop_result != "ignore":
                return internal_drop_result
        if self.__delegate.can_drop_mime_data(mime_data, "copy", drop_index):
            if self.__delegate.drop_mime_data(mime_data, "copy", drop_index) != "ignore":
                return "accept"
        return "ignore"

    def handle_select_all(self) -> bool:
        self.__selection.set_multiple(set(range(len(self.__list_model.items))))
        return True

    def handle_delete(self) -> bool:
        item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        if self.__delegate.delete_event(GridFlowCanvasItemDeleteEvent(item, selected_items)):
            return True
        return False

    def handle_select(self) -> bool:
        item = self.__list_model.items[self.__selection.anchor_index] if self.__selection.anchor_index is not None else None
        selected_items = [self.__list_model.items[index] for index in self.__selection.indexes]
        selected_items = selected_items if item in selected_items else [item]
        if self.__delegate.select_event(GridFlowCanvasItemSelectEvent(item, selected_items)):
            return True
        return False

    def size_to_content(self) -> None:
        """Size the canvas item to the height of the items."""
        self.update_sizing(self.__layout.get_sizing(self.canvas_items))
