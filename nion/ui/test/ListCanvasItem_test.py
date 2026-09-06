# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Selection


class ListCanvasItemDelegate(ListCanvasItem.ListCanvasItemDelegate):
    def __init__(self) -> None:
        self.on_item_selected: typing.Optional[typing.Callable[[int], None]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return [1, 2, 3, 4]

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return 4

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


def make_list_canvas_item(*, item_width: typing.Optional[int] = None, item_height: typing.Optional[int] = None) -> ListCanvasItem.ListCanvasItem2:
    list_model = ListModel.ListModel[int]("items", items=list(range(100)))
    selection = Selection.IndexedSelection()

    def item_factory(item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
        return CanvasItem.EmptyCanvasItem()

    return ListCanvasItem.ListCanvasItem2(list_model, selection, item_factory, GridFlowCanvasItem.GridFlowCanvasItemDelegate(), item_width=item_width, item_height=item_height, key="items")


class TestListCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_shift_click_extends_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = ListCanvasItemDelegate()
        canvas_item = ListCanvasItem.ListCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_click(Geometry.IntPoint(y=120, x=50))
        self.assertEqual(selection.indexes, {1})
        modifiers = CanvasItem.KeyboardModifiers(shift=True)
        canvas_item.simulate_click(Geometry.IntPoint(y=200, x=50), modifiers)
        self.assertEqual(selection.indexes, {1, 2})

    def test_start_drag_does_not_change_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = ListCanvasItemDelegate()
        canvas_item = ListCanvasItem.ListCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_drag(Geometry.IntPoint(y=120, x=50), Geometry.IntPoint(y=120, x=500))
        self.assertEqual(selection.indexes, set())

    def test_list_canvas_item_2_column_layout_tracks_width_and_preserves_scrollable_height(self) -> None:
        # a scroll area with auto_resize_contents enabled should stretch the content to its own width on every
        # layout (so rows always span the full available width), without collapsing the content's height down to
        # the viewport height (which would make the scroll area think there is nothing left to scroll).
        item_height = 20
        list_canvas_item = make_list_canvas_item(item_height=item_height)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=300, height=400))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=300, height=2000))
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=500, height=400))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=500, height=2000))

    def test_list_canvas_item_2_row_layout_tracks_height_and_preserves_scrollable_width(self) -> None:
        # same as above, but for a row of fixed-width columns: height should track the scroll area, while width
        # (the scrollable axis) must remain the full content extent.
        item_width = 20
        list_canvas_item = make_list_canvas_item(item_width=item_width)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=300))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=2000, height=300))
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=500))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=2000, height=500))
