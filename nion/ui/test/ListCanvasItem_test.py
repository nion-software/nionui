# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.utils import Geometry
from nion.utils import Selection


class ListCanvasItemDelegate(ListCanvasItem.ListCanvasItemDelegate):
    def __init__(self) -> None:
        self.on_item_selected: typing.Optional[typing.Callable[[int], None]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None

    @property
    def item_count(self) -> int:
        return 4

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


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
