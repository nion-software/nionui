"""Lists and grids holding far more items than fit on screen.

The chooser picks which kind of list or grid displays the model; each of them holds the same items. The point of the page is that the model
is much larger than the viewport, so that scrolling only ever shows a small part of it: a list or grid which paints
every item of its model instead of only the items on screen still looks right, but does the whole model's worth of
work on every scroll step. The painted counts below say which items were actually painted, so the difference shows
as a number rather than as a feeling about how smoothly the page scrolls.

The list box and the two grids paint their items themselves, from a delegate. The list view and the grid view build
a canvas item for each item of the model instead, which is why they take a moment to appear.
"""

# standard libraries
import collections
import gettext
import typing

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import Declarative
from nion.ui import DrawingContext
from nion.ui import GridCanvasItem
from nion.ui import GridFlowCanvasItem
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Model
from nion.utils import ReferenceCounting
from nion.utils import Registry
from nion.utils import Selection

_ = gettext.gettext

# the number of items in each list and grid of this page. it is meant to be far larger than any viewport, so that
# only a small part of it can be on screen at once. raising it does not change what the page shows, only how much
# a list or grid which paints its whole model has to do to show the same thing.
ITEM_COUNT: typing.Final[int] = 10000

LIST_ITEM_HEIGHT: typing.Final[int] = 20
VIEW_ITEM_HEIGHT: typing.Final[int] = 24
GRID_ITEM_SIZE: typing.Final[Geometry.IntSize] = Geometry.IntSize(80, 80)
VIEWPORT_HEIGHT: typing.Final[int] = 240
ROW_VIEWPORT_HEIGHT: typing.Final[int] = 100
SCROLL_BAR_SIZE: typing.Final[int] = 16

_colors: typing.Sequence[str] = ("#5AA0E6", "#E6965A", "#8CC878", "#C878C8")


# each item painted anywhere on this page is counted here, under the name of the list or grid which painted it.
# the counts are read by the page's handler and reported on demand; nothing reads them while painting, so counting
# cannot itself cause a repaint.
_paint_counts: typing.DefaultDict[str, int] = collections.defaultdict(int)

LIST_BOX = "List Box"
LIST_VIEW = "List View"
GRID = "Grid"
GRID_ROW = "Grid Row"
GRID_VIEW = "Grid View"

_kinds: typing.Sequence[str] = (LIST_BOX, LIST_VIEW, GRID, GRID_ROW, GRID_VIEW)


def _paint_cell(drawing_context: DrawingContext.DrawingContext, item: typing.Any, rect: Geometry.IntRect,
                is_selected: bool) -> None:
    """Paint one item of a grid: a block of color with the item's number on it."""
    inner = rect.to_float_rect().inset(2, 2).to_int_rect()
    with drawing_context.saver():
        drawing_context.begin_path()
        drawing_context.rect(inner.left, inner.top, inner.width, inner.height)
        drawing_context.fill_style = "#3875D6" if is_selected else _colors[int(item) % len(_colors)]
        drawing_context.fill()
        drawing_context.font = "12px"
        drawing_context.text_align = "center"
        drawing_context.text_baseline = "middle"
        drawing_context.fill_style = "#FFF"
        drawing_context.fill_text(str(item), inner.center.x, inner.center.y)


class CountingStringListDelegate(Widgets.StringListCanvasItemDelegate):
    """Paint the rows of the list box, counting each row painted."""

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, display_item: typing.Any,
                   rect: Geometry.IntRect, is_selected: bool) -> None:
        _paint_counts[LIST_BOX] += 1
        super().paint_item(drawing_context, display_item, rect, is_selected)


class CountingGridDelegate(GridCanvasItem.GridCanvasItemDelegate):
    """Paint the cells of a grid, counting each cell painted."""

    def __init__(self, kind: str, items: typing.Sequence[typing.Any]) -> None:
        self.__kind = kind
        self.__items = list(items)

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return self.__items

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        self.__items = list(value)

    @property
    def item_count(self) -> int:
        return len(self.__items)

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, item: typing.Any, rect: Geometry.IntRect,
                   is_selected: bool) -> None:
        _paint_counts[self.__kind] += 1
        _paint_cell(drawing_context, item, rect, is_selected)


class ItemCanvasItemComposer(CanvasItem.BaseComposer):
    def __init__(self, canvas_item: CanvasItem.AbstractCanvasItem, layout_sizing: CanvasItem.Sizing,
                 composer_cache: CanvasItem.ComposerCache, kind: str, item: typing.Any, is_selected: bool) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__kind = kind
        self.__item = item
        self.__is_selected = is_selected

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect,
                 composer_cache: CanvasItem.ComposerCache) -> None:
        _paint_counts[self.__kind] += 1
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            _paint_cell(drawing_context, self.__item, canvas_rect - canvas_rect.origin, self.__is_selected)


class ItemCanvasItem(CanvasItem.AbstractCanvasItem):
    """Display one item of the list view or the grid view, counting each time it is painted.

    A list view and a grid view give each item of the model a canvas item of its own, where a list box and a grid
    paint their items from a delegate. This is the item canvas item for both of them.
    """

    def __init__(self, kind: str, item: typing.Any, is_selected_model: Model.PropertyModel[bool]) -> None:
        super().__init__()
        self.__kind = kind
        self.__item = item
        self.__is_selected_model = is_selected_model
        self.__listener = is_selected_model.property_changed_event.listen(
            ReferenceCounting.weak_partial(ItemCanvasItem.__is_selected_changed, self))

    def __is_selected_changed(self, key: str) -> None:
        if key == "value":
            self.update()

    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> typing.Optional[CanvasItem.BaseComposer]:
        return ItemCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__kind, self.__item,
                                      self.__is_selected_model.value or False)


def _make_scrolling_canvas_widget(ui: UserInterface.UserInterface, canvas_item: CanvasItem.AbstractCanvasItem,
                                  orientation: CanvasItem.Orientation,
                                  properties: typing.Mapping[str, typing.Any]) -> UserInterface.CanvasWidget:
    """Put a canvas item in a scroll area with a scroll bar, in a canvas widget of its own.

    The scroll area is what makes this page worth looking at: it is what gives the list or grid a viewport smaller
    than its content, and so what decides which items are on screen.
    """
    scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(canvas_item)
    scroll_area_canvas_item.auto_resize_contents = True
    scroll_bar_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item, orientation)
    scroll_group_canvas_item = CanvasItem.CanvasItemComposition()
    scroll_group_canvas_item.border_color = "#CCC"
    if orientation == CanvasItem.Orientation.Vertical:
        scroll_group_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        scroll_bar_canvas_item.update_sizing(scroll_bar_canvas_item.sizing.with_fixed_width(SCROLL_BAR_SIZE))
    else:
        scroll_group_canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        scroll_bar_canvas_item.update_sizing(scroll_bar_canvas_item.sizing.with_fixed_height(SCROLL_BAR_SIZE))
    scroll_group_canvas_item.add_canvas_item(scroll_area_canvas_item)
    scroll_group_canvas_item.add_canvas_item(scroll_bar_canvas_item)
    canvas_widget = ui.create_canvas_widget(properties=properties)
    canvas_widget.canvas_item.add_canvas_item(scroll_group_canvas_item)
    return canvas_widget


class LargeListConstructor:
    """Construct the lists and grids of this page.

    The declarative ui describes neither a grid nor a canvas item, and its list box is the list view kind rather
    than the delegate-painted kind, so each of this page's widgets is built here and named by its own ui description
    type. A page which only needed the widgets the declarative ui already describes would not need any of this.
    """

    def construct(self, d_type: str, ui: UserInterface.UserInterface, window: typing.Optional[Window.Window],
                  d: Declarative.UIDescription, handler: Declarative.HandlerLike,
                  finishes: typing.Optional[typing.List[typing.Callable[[], None]]] = None
                  ) -> typing.Optional[UserInterface.Widget]:
        if not d_type.startswith("demo_large_"):
            return None
        properties = Declarative.construct_sizing_properties(d)
        page_handler = typing.cast("Handler", handler)
        if d_type == "demo_large_list_box":
            # a list box paints its rows from a delegate; this is the one list or grid on this page which is
            # available as a widget already.
            return Widgets.ListWidget(ui, CountingStringListDelegate(), items=page_handler.items,
                                      selection_style=Selection.Style.multiple, properties=properties)
        if d_type == "demo_large_list_view":
            return Widgets.ListViewWidget(ui, page_handler.list_model,
                                          lambda item, is_selected_model: ItemCanvasItem(LIST_VIEW, item, is_selected_model),
                                          item_height=VIEW_ITEM_HEIGHT, key="items", properties=properties)
        if d_type == "demo_large_grid":
            # a grid which wraps fills the width it is given and scrolls down through its rows.
            grid_canvas_item = GridCanvasItem.GridCanvasItem(CountingGridDelegate(GRID, page_handler.items),
                                                             Selection.IndexedSelection(Selection.Style.multiple))
            return _make_scrolling_canvas_widget(ui, grid_canvas_item, CanvasItem.Orientation.Vertical, properties)
        if d_type == "demo_large_grid_row":
            # a grid which does not wrap is a single row of cells as tall as its viewport, scrolling sideways. it is
            # the one list or grid here whose content is wider than its viewport rather than taller.
            grid_canvas_item = GridCanvasItem.GridCanvasItem(CountingGridDelegate(GRID_ROW, page_handler.items),
                                                             Selection.IndexedSelection(Selection.Style.multiple),
                                                             wrap=False)
            return _make_scrolling_canvas_widget(ui, grid_canvas_item, CanvasItem.Orientation.Horizontal, properties)
        if d_type == "demo_large_grid_view":
            grid_canvas_item2 = GridCanvasItem.GridCanvasItem2(page_handler.list_model,
                                                               Selection.IndexedSelection(Selection.Style.multiple),
                                                               lambda item, is_selected_model: ItemCanvasItem(GRID_VIEW, item, is_selected_model),
                                                               GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                               item_size=GRID_ITEM_SIZE, key="items")
            return _make_scrolling_canvas_widget(ui, grid_canvas_item2, CanvasItem.Orientation.Vertical, properties)
        return None


Registry.register_component(LargeListConstructor(), {"declarative_constructor"})


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.items = list(range(ITEM_COUNT))
        # the list view and the grid view take their items from a list model; the list box and the grids take
        # theirs from a delegate. they are given the same items either way.
        self.list_model = ListModel.ListModel[int]("items", items=self.items)
        # the stack holding the lists and grids, reached by name so that the chooser can switch it.
        self.page_stack: typing.Optional[UserInterface.StackWidget] = None
        self.status_model = Model.PropertyModel(_("Scroll a list or a grid, then sample the painted counts."))

    def select_page(self, widget: UserInterface.ComboBoxWidget, current_index: int) -> None:
        assert self.page_stack
        self.page_stack.current_index = current_index

    def sample_counts(self, widget: UserInterface.PushButtonWidget) -> None:
        # report how many items each list and grid has painted since the counts were last reset. a list or grid
        # painting only what its viewport holds stays in the tens however far it is scrolled; one painting its
        # whole model climbs by the size of the model on every scroll step.
        self.status_model.value = "  ·  ".join(f"{kind}: {_paint_counts[kind]}" for kind in _kinds)

    def reset_counts(self, widget: UserInterface.PushButtonWidget) -> None:
        _paint_counts.clear()
        self.status_model.value = _("Painted counts reset.")


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # a chooser and a stack rather than a tab widget: the canvas backend draws every widget itself and has no tab
    # widget yet, where it has both of these, so this is the form of the page which runs under either backend.
    def create_page(content: Declarative.UIDescription, note: str) -> Declarative.UIDescription:
        note_row = u.create_row(u.create_label(text=note), u.create_stretch())
        return u.create_column(content, note_row, u.create_stretch(), spacing=8)

    pages = [
        create_page(typing.cast(Declarative.UIDescription, {"type": "demo_large_list_box", "height": VIEWPORT_HEIGHT}),
                    _("Rows painted from a delegate.")),
        create_page(typing.cast(Declarative.UIDescription, {"type": "demo_large_list_view", "height": VIEWPORT_HEIGHT}),
                    _("A canvas item for each item of the model.")),
        create_page(typing.cast(Declarative.UIDescription, {"type": "demo_large_grid", "height": VIEWPORT_HEIGHT}),
                    _("Cells painted from a delegate; wraps and scrolls down.")),
        create_page(typing.cast(Declarative.UIDescription, {"type": "demo_large_grid_row", "height": ROW_VIEWPORT_HEIGHT}),
                    _("One row of cells as tall as the viewport, scrolling sideways.")),
        create_page(typing.cast(Declarative.UIDescription, {"type": "demo_large_grid_view", "height": VIEWPORT_HEIGHT}),
                    _("A canvas item for each item of the model.")),
        ]

    chooser_row = u.create_row(u.create_combo_box(items=list(_kinds), on_current_index_changed="select_page"),
                               u.create_stretch(), spacing=8)

    # each list and grid is built as it is first shown rather than all of them at startup: the list view and the
    # grid view build a canvas item for every item of the model, which takes a moment at this size.
    page_stack = u.create_stack(*pages, name="page_stack", item_construction="deferred")

    sample_button = u.create_push_button(text=_("Sample Painted Counts"), on_clicked="sample_counts")
    reset_button = u.create_push_button(text=_("Reset"), on_clicked="reset_counts")
    button_row = u.create_row(sample_button, reset_button, u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    count_row = u.create_row(u.create_label(text=_("Items in each list and grid: {:,}").format(ITEM_COUNT)),
                             u.create_stretch())

    return u.create_column(count_row, chooser_row, page_stack, button_row, status_label, spacing=8)
