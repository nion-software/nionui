from __future__ import annotations

# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import GridCanvasItem
from nion.ui import UserInterface
from nion.utils import Geometry
from nion.utils import Selection


class GridCanvasItemDelegate(GridCanvasItem.GridCanvasItemDelegate):
    def __init__(self, item_count:typing.Optional[int]=None)->None:
        self.__item_count = item_count if item_count is not None else 4

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return [1, 2, 3, 4]

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return self.__item_count

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


class PaintCountingGridCanvasItemDelegate(GridCanvasItem.GridCanvasItemDelegate):
    """A delegate whose items are their own indexes and which records each item it is asked to paint."""

    def __init__(self, item_count: int) -> None:
        self.__item_count = item_count
        self.painted_indexes = list[int]()

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return list(range(self.__item_count))

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return self.__item_count

    def set_item_count(self, item_count: int) -> None:
        self.__item_count = item_count

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        self.painted_indexes.append(item)


class TestGridCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_wrapped_grid_canvas_item_paints_only_the_cells_within_the_viewport(self) -> None:
        # the canvas rect of a grid inside a scroll area spans every cell of the model, so the cells to paint can
        # only be determined from the visible rect. painting them all makes each scroll step cost the whole model.
        delegate = PaintCountingGridCanvasItemDelegate(10000)
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, Selection.IndexedSelection())
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(canvas_item)
        canvas_size = Geometry.IntSize(width=320, height=400)
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        # the cells are 80x80 here, so the viewport holds four columns of five rows.
        self.assertEqual(20, len(delegate.painted_indexes))
        self.assertEqual(list(range(20)), delegate.painted_indexes)
        # growing the model without growing the viewport must not paint any more cells.
        delegate.painted_indexes.clear()
        delegate.set_item_count(20000)
        canvas_item.update()
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        self.assertEqual(20, len(delegate.painted_indexes))

    def test_scrolled_wrapped_grid_canvas_item_paints_the_cells_at_the_scroll_position(self) -> None:
        delegate = PaintCountingGridCanvasItemDelegate(10000)
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, Selection.IndexedSelection())
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(canvas_item)
        canvas_size = Geometry.IntSize(width=320, height=400)
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        delegate.painted_indexes.clear()
        scroll_area_canvas_item.update_content_origin(Geometry.IntPoint(y=-8000))
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        # 8000px down, at 80px per row and four columns per row, is the row beginning with item 400.
        self.assertEqual(list(range(400, 420)), delegate.painted_indexes)

    def test_unwrapped_grid_canvas_item_paints_only_the_cells_within_the_viewport(self) -> None:
        # a row of cells that does not wrap scrolls horizontally instead, so it is the horizontal extent of the
        # visible rect that says which cells to paint.
        delegate = PaintCountingGridCanvasItemDelegate(10000)
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, Selection.IndexedSelection(), wrap=False)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(canvas_item)
        canvas_size = Geometry.IntSize(width=320, height=100)
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        # the cells are square and as tall as the viewport, so three and a fraction of them are visible.
        self.assertEqual([0, 1, 2, 3], delegate.painted_indexes)
        delegate.painted_indexes.clear()
        scroll_area_canvas_item.update_content_origin(Geometry.IntPoint(x=-4000))
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        # 4000px across, at 100px per cell, is the cell at index 40.
        self.assertEqual([40, 41, 42, 43], delegate.painted_indexes)

    def test_shift_click_extends_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = GridCanvasItemDelegate()
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_click(Geometry.IntPoint(y=120, x=50))
        self.assertEqual(selection.indexes, {1})
        modifiers = CanvasItem.KeyboardModifiers(shift=True)
        canvas_item.simulate_click(Geometry.IntPoint(y=200, x=50), modifiers)
        self.assertEqual(selection.indexes, {1, 2})

    def test_start_drag_does_not_change_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = GridCanvasItemDelegate()
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_drag(Geometry.IntPoint(y=120, x=50), Geometry.IntPoint(y=120, x=500))
        self.assertEqual(selection.indexes, set())

    def test_layout_size_maintains_height_with_no_items_when_not_wrapped(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = GridCanvasItemDelegate(0)
        canvas_item = GridCanvasItem.GridCanvasItem(delegate, selection, wrap=False)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((40, 500)))
        canvas_bounds = canvas_item.canvas_bounds or Geometry.IntRect.empty_rect()
        self.assertEqual(canvas_bounds.height, 40)
