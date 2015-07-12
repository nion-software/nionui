# standard libraries
import logging
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import Geometry
from nion.ui import Test


class TestCanvasItem(CanvasItem.AbstractCanvasItem):
    def __init__(self):
        super(TestCanvasItem, self).__init__()
        self.wants_mouse_events = True
        self._mouse_released = False
        self.key = None
    def mouse_pressed(self, x, y, modifiers):
        return True
    def mouse_released(self, x, y, modifiers):
        self._mouse_released = True
    def key_pressed(self, key):
        self.key = key

class TestCanvasItemClass(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def simulate_drag(self, root_canvas_item, p1, p2, modifiers=None):
        modifiers = Test.KeyboardModifiers() if not modifiers else modifiers
        root_canvas_item.canvas_widget.on_mouse_pressed(p1[1], p1[0], modifiers)
        root_canvas_item.canvas_widget.on_mouse_position_changed(p1[1], p1[0], modifiers)
        midp = Geometry.midpoint(p1, p2)
        root_canvas_item.canvas_widget.on_mouse_position_changed(midp[1], midp[0], modifiers)
        root_canvas_item.canvas_widget.on_mouse_position_changed(p2[1], p2[0], modifiers)
        root_canvas_item.canvas_widget.on_mouse_released(p2[1], p2[0], modifiers)

    def test_drag_inside_bounds(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        canvas_item = TestCanvasItem()
        root_canvas.add_canvas_item(canvas_item)
        root_canvas.update_layout((0, 0), (100, 100))
        self.simulate_drag(root_canvas, (50, 50), (30, 50))
        self.assertTrue(canvas_item._mouse_released)

    def test_drag_outside_bounds(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        canvas_item = TestCanvasItem()
        root_canvas.add_canvas_item(canvas_item)
        root_canvas.update_layout((0, 0), (100, 100))
        self.simulate_drag(canvas_item, (50, 50), (-30, 50))
        self.assertTrue(canvas_item._mouse_released)

    def test_drag_within_composition(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        canvas_item = TestCanvasItem()
        container = CanvasItem.CanvasItemComposition()
        container.add_canvas_item(canvas_item)
        root_canvas.add_canvas_item(container)
        root_canvas.update_layout((0, 0), (100, 100))
        self.simulate_drag(container, (50, 50), (30, 50))
        self.assertTrue(canvas_item._mouse_released)

    def test_drag_within_composition_but_outside_bounds(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        canvas_item = TestCanvasItem()
        container = CanvasItem.CanvasItemComposition()
        container.add_canvas_item(canvas_item)
        root_canvas.add_canvas_item(container)
        root_canvas.update_layout((0, 0), (100, 100))
        self.simulate_drag(container, (50, 50), (-30, 50))
        self.assertTrue(canvas_item._mouse_released)

    def test_layout_uses_minimum_aspect_ratio(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.canvas_items[0].sizing.minimum_aspect_ratio = 2.0
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=80))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=320))

    def test_layout_uses_maximum_aspect_ratio(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.canvas_items[0].sizing.maximum_aspect_ratio = 1.0
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=80, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=480, height=480))

    def test_composition_layout_uses_preferred_aspect_ratio(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        child_canvas = CanvasItem.RootCanvasItem(ui)
        child_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(child_canvas)
        child_canvas.sizing.preferred_aspect_ratio = 1.0
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=80, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=480, height=480))

    def test_composition_layout_sizing_includes_margins_but_not_spacing(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout.margins = Geometry.Margins(top=4, bottom=6, left=8, right=10)
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.canvas_items[0].sizing.minimum_width = 16
        root_canvas.canvas_items[0].sizing.maximum_height = 24
        self.assertEqual(root_canvas.layout_sizing.minimum_width, 16 + 8 + 10)
        self.assertEqual(root_canvas.layout_sizing.maximum_height, 24 + 4 + 6)

    def test_row_layout_sizing_includes_margins_and_spacing(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout(spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.canvas_items[0].sizing.minimum_width = 16
        root_canvas.canvas_items[0].sizing.maximum_height = 12
        root_canvas.canvas_items[1].sizing.minimum_width = 32
        root_canvas.canvas_items[1].sizing.maximum_height = 24
        root_canvas.canvas_items[2].sizing.minimum_width = 48
        root_canvas.canvas_items[2].sizing.maximum_height = 36
        self.assertEqual(root_canvas.layout_sizing.minimum_width, 16 + 32 + 48 + 2 * 7 + 8 + 10)  # includes margins and spacing
        self.assertEqual(root_canvas.layout_sizing.maximum_height, 12 + 4 + 6)  # includes margins only

    def test_column_layout_sizing_includes_margins_and_spacing(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout(spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.canvas_items[0].sizing.minimum_width = 16
        root_canvas.canvas_items[0].sizing.maximum_height = 12
        root_canvas.canvas_items[1].sizing.minimum_width = 32
        root_canvas.canvas_items[1].sizing.maximum_height = 24
        root_canvas.canvas_items[2].sizing.minimum_width = 48
        root_canvas.canvas_items[2].sizing.maximum_height = 36
        self.assertEqual(root_canvas.layout_sizing.minimum_width, 48 + 8 + 10)  # includes margins only
        self.assertEqual(root_canvas.layout_sizing.maximum_height, 12 + 24 + 36 + 2 * 7 + 4 + 6)  # includes margins and spacing

    def test_grid_layout_sizing_includes_margins_and_spacing(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2), spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=0, y=1))
        #root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=1, y=1))
        root_canvas.canvas_items[0].sizing.minimum_width = 16
        root_canvas.canvas_items[0].sizing.maximum_height = 12
        root_canvas.canvas_items[1].sizing.minimum_width = 32
        root_canvas.canvas_items[1].sizing.maximum_height = 24
        root_canvas.canvas_items[2].sizing.minimum_width = 48
        root_canvas.canvas_items[2].sizing.maximum_height = 36
        self.assertEqual(root_canvas.layout_sizing.minimum_width, 32 + 48 + 1 * 7 + 8 + 10)  # includes margins only
        self.assertEqual(root_canvas.layout_sizing.maximum_height, 12 + 36 + 1 * 7 + 4 + 6)  # includes margins and spacing

#        for i, canvas_item in enumerate(root_canvas.canvas_items):
#            logging.debug("%s %s %s", i, canvas_item.canvas_origin, canvas_item.canvas_size)

    def test_layout_splits_evening_between_two_items(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=320, height=480))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=320, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=320, height=480))
        # test column layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=240))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=240))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=240))

    def test_layout_splits_evening_between_three_items_with_spacing_and_margins(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout(spacing=10, margins=Geometry.Margins(top=3, left=5, bottom=7, right=11))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=5, y=3))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=201, height=470))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=216, y=3))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=201, height=470))
        self.assertEqual(root_canvas.canvas_items[2].canvas_origin, Geometry.IntPoint(x=427, y=3))
        self.assertEqual(root_canvas.canvas_items[2].canvas_size, Geometry.IntSize(width=202, height=470))
        # test column layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout(spacing=10, margins=Geometry.Margins(top=3, left=5, bottom=7, right=11))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=5, y=3))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=624, height=150))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=5, y=163))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=624, height=150))
        self.assertEqual(root_canvas.canvas_items[2].canvas_origin, Geometry.IntPoint(x=5, y=323))
        self.assertEqual(root_canvas.canvas_items[2].canvas_size, Geometry.IntSize(width=624, height=150))

    def test_layout_splits_two_with_first_one_minimum_size(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[0].sizing.minimum_width = 500
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=500, height=480))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=500, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=140, height=480))
        # test column layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[0].sizing.minimum_height = 300
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=300))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=300))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=180))

    def test_layout_splits_two_with_second_one_minimum_size(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[1].sizing.minimum_width = 500
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=140, height=480))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=140, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=500, height=480))
        # test column layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[1].sizing.minimum_height = 300
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=180))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=180))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=300))

    def test_layout_splits_two_with_first_one_maximum_size(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[0].sizing.maximum_width = 100
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=100, height=480))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=100, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=540, height=480))

    def test_layout_splits_two_with_second_one_maximum_size(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.canvas_items[1].sizing.maximum_width = 100
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=540, height=480))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=540, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=100, height=480))

    def test_layout_splits_three_with_maximum_making_room_for_minimized_item(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.canvas_items[0].sizing.minimum_width = 230
        root_canvas.canvas_items[1].sizing.maximum_width = 100
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        if False:
            for i, canvas_item in enumerate(root_canvas.canvas_items):
                logging.debug("%s %s %s", i, canvas_item.canvas_origin, canvas_item.canvas_size)
            self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
            self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=270, height=480))
            self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=270, y=0))
            self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=100, height=480))
            self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=370, y=0))
            self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=270, height=480))

    def test_grid_layout_2x2_works(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=320, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(root_canvas.canvas_items[2].canvas_origin, Geometry.IntPoint(x=0, y=240))
        self.assertEqual(root_canvas.canvas_items[2].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(root_canvas.canvas_items[3].canvas_origin, Geometry.IntPoint(x=320, y=240))
        self.assertEqual(root_canvas.canvas_items[3].canvas_size, Geometry.IntSize(width=320, height=240))

    def test_grid_layout_splits_with_one_min_size_specified(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        root_canvas.canvas_items[1].sizing.minimum_height = 300
        root_canvas.canvas_items[1].sizing.minimum_width = 500
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=140, height=300))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=140, y=0))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=500, height=300))
        self.assertEqual(root_canvas.canvas_items[2].canvas_origin, Geometry.IntPoint(x=0, y=300))
        self.assertEqual(root_canvas.canvas_items[2].canvas_size, Geometry.IntSize(width=140, height=180))
        self.assertEqual(root_canvas.canvas_items[3].canvas_origin, Geometry.IntPoint(x=140, y=300))
        self.assertEqual(root_canvas.canvas_items[3].canvas_size, Geometry.IntSize(width=500, height=180))

    def test_grid_layout_within_column_layout(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        grid_canvas = CanvasItem.CanvasItemComposition()
        grid_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        background = CanvasItem.BackgroundCanvasItem("#F00")
        root_canvas.add_canvas_item(background)
        root_canvas.add_canvas_item(grid_canvas)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background.canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(background.canvas_size, Geometry.IntSize(width=320, height=480))
        self.assertEqual(grid_canvas.canvas_origin, Geometry.IntPoint(x=320, y=0))
        self.assertEqual(grid_canvas.canvas_size, Geometry.IntSize(width=320, height=480))
        self.assertEqual(grid_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(grid_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=160, height=240))
        self.assertEqual(grid_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=160, y=0))
        self.assertEqual(grid_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=160, height=240))
        self.assertEqual(grid_canvas.canvas_items[2].canvas_origin, Geometry.IntPoint(x=0, y=240))
        self.assertEqual(grid_canvas.canvas_items[2].canvas_size, Geometry.IntSize(width=160, height=240))
        self.assertEqual(grid_canvas.canvas_items[3].canvas_origin, Geometry.IntPoint(x=160, y=240))
        self.assertEqual(grid_canvas.canvas_items[3].canvas_size, Geometry.IntSize(width=160, height=240))

    def test_focus_changed_messages_sent_when_focus_changes(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item1.focusable = True
        canvas_item2.focusable = True
        focus_changed_set = set()
        def focus_changed1(focused):
            focus_changed_set.add(canvas_item1)
        def focus_changed2(focused):
            focus_changed_set.add(canvas_item2)
        canvas_item1.on_focus_changed = focus_changed1
        canvas_item2.on_focus_changed = focus_changed2
        root_canvas.add_canvas_item(canvas_item1)
        root_canvas.add_canvas_item(canvas_item2)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertIsNone(root_canvas.focused_item)
        self.assertFalse(canvas_item1.focused)
        self.assertFalse(canvas_item2.focused)
        # click in item 1 and check that focus was updated and changed
        modifiers = Test.KeyboardModifiers()
        root_canvas.canvas_widget.on_mouse_clicked(160, 240, modifiers)
        self.assertTrue(canvas_item1.focused)
        self.assertTrue(canvas_item1 in focus_changed_set)
        self.assertFalse(canvas_item2.focused)
        self.assertFalse(canvas_item2 in focus_changed_set)
        self.assertEqual(root_canvas.focused_item, canvas_item1)
        # click in item 2 and check that focus was updated and changed
        focus_changed_set.clear()
        root_canvas.canvas_widget.on_mouse_clicked(160 + 320, 240, modifiers)
        self.assertFalse(canvas_item1.focused)
        self.assertTrue(canvas_item1 in focus_changed_set)
        self.assertTrue(canvas_item2.focused)
        self.assertTrue(canvas_item2 in focus_changed_set)
        self.assertEqual(root_canvas.focused_item, canvas_item2)

    def test_root_canvas_item_loses_focus_too_when_canvas_widget_loses_focus(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.focusable = True
        root_canvas.wants_mouse_events = True
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        modifiers = Test.KeyboardModifiers()
        self.assertIsNone(root_canvas.focused_item)
        self.assertFalse(root_canvas.focused)
        root_canvas.canvas_widget.on_mouse_clicked(320, 240, modifiers)
        self.assertTrue(root_canvas.focused)
        self.assertEqual(root_canvas.focused_item, root_canvas)  # refers to itself??
        # become unfocused
        root_canvas.canvas_widget.on_focus_changed(False)
        self.assertFalse(root_canvas.focused)
        self.assertIsNone(root_canvas.focused_item)

    def test_keys_go_to_focused_item(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item1.focusable = True
        canvas_item2.focusable = True
        root_canvas.add_canvas_item(canvas_item1)
        root_canvas.add_canvas_item(canvas_item2)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # click in item 1, then 2 and check key goes to 2nd item
        modifiers = Test.KeyboardModifiers()
        root_canvas.canvas_widget.on_mouse_clicked(160, 240, modifiers)
        root_canvas.canvas_widget.on_mouse_clicked(160 + 320, 240, modifiers)
        # check assumptions
        self.assertFalse(canvas_item1.focused)
        self.assertTrue(canvas_item2.focused)
        # key should go to 2nd item
        root_canvas.canvas_widget.on_key_pressed('a')
        # check result
        self.assertIsNone(canvas_item1.key)
        self.assertEqual(canvas_item2.key, 'a')
        # now back to first item
        canvas_item1.key = None
        canvas_item2.key = None
        root_canvas.canvas_widget.on_mouse_clicked(160, 240, modifiers)
        root_canvas.canvas_widget.on_key_pressed('a')
        self.assertEqual(canvas_item1.key, 'a')
        self.assertIsNone(canvas_item2.key)

    def test_composition_layout_sizing_has_infinite_maximum_if_first_child_is_finite_and_one_is_infinite(self):
        ui = Test.UserInterface()
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[0].sizing.maximum_height = 40
        composition.canvas_items[0].sizing.minimum_height = 40
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_composition_layout_sizing_has_infinite_maximum_if_last_child_is_finite_and_one_is_infinite(self):
        ui = Test.UserInterface()
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[1].sizing.maximum_height = 40
        composition.canvas_items[1].sizing.minimum_height = 40
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_column_layout_sizing_has_infinite_maximum_if_one_child_is_finite_and_one_is_infinite(self):
        ui = Test.UserInterface()
        composition = CanvasItem.CanvasItemComposition()
        composition.layout = CanvasItem.CanvasItemColumnLayout()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[0].sizing.maximum_height = 40
        composition.canvas_items[0].sizing.minimum_height = 40
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_grid_layout_sizing_has_infinite_maximum_if_one_child_is_finite_and_one_is_infinite(self):
        ui = Test.UserInterface()
        grid_canvas = CanvasItem.CanvasItemComposition()
        grid_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        grid_canvas.canvas_items[0].sizing.maximum_height = 40
        grid_canvas.canvas_items[0].sizing.minimum_height = 40
        grid_canvas.canvas_items[0].sizing.maximum_width = 40
        grid_canvas.canvas_items[0].sizing.minimum_width = 40
        grid_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(grid_canvas.layout_sizing.minimum_height, 40)
        self.assertIsNone(grid_canvas.layout_sizing.maximum_height)
        self.assertEqual(grid_canvas.layout_sizing.minimum_width, 40)
        self.assertIsNone(grid_canvas.layout_sizing.maximum_width)

    def test_height_constraint_inside_layout_with_another_height_constraint_results_in_proper_layout(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        root_canvas.canvas_items[0].sizing.maximum_height = 10
        root_canvas.canvas_items[0].sizing.minimum_height = 10
        composition = CanvasItem.CanvasItemComposition()
        composition.layout = CanvasItem.CanvasItemColumnLayout()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[1].sizing.maximum_height = 40
        composition.canvas_items[1].sizing.minimum_height = 40
        root_canvas.add_canvas_item(composition)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(root_canvas.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=10))
        self.assertEqual(root_canvas.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=10))
        self.assertEqual(root_canvas.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=470))

    def test_grid_layout_2x2_canvas_item_at_point(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2), spacing=20, margins=Geometry.Margins(top=10, bottom=10, left=10, right=10))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(root_canvas.canvas_item_at_point(5, 5), root_canvas)
        self.assertEqual(root_canvas.canvas_item_at_point(20, 20), root_canvas.canvas_items[0])
        self.assertEqual(root_canvas.canvas_item_at_point(320, 20), root_canvas)
        self.assertEqual(root_canvas.canvas_item_at_point(340, 20), root_canvas.canvas_items[1])
        self.assertEqual(root_canvas.canvas_item_at_point(320, 240), root_canvas)
        self.assertEqual(root_canvas.canvas_item_at_point(300, 260), root_canvas.canvas_items[2])
        self.assertEqual(root_canvas.canvas_item_at_point(340, 260), root_canvas.canvas_items[3])

    class TestCanvasItem(CanvasItem.CanvasItemComposition):

        def __init__(self):
            super(TestCanvasItemClass.TestCanvasItem, self).__init__()
            self.mouse_inside = False
            self.mouse_pos = None
            self.mouse_pressed_pos = None
            self.drag_inside = False
            self.drag_pos = None

        def mouse_entered(self):
            self.mouse_inside = True

        def mouse_exited(self):
            self.mouse_inside = False
            self.mouse_pos = None

        def mouse_position_changed(self, x, y, modifiers):
            self.mouse_pos = Geometry.IntPoint(y=y, x=x)

        def mouse_pressed(self, x, y, modifiers):
            self.mouse_pressed_pos = Geometry.IntPoint(y=y, x=x)

        def mouse_released(self, x, y, modifiers):
            self.mouse_pressed_pos = None

        def drag_enter(self, mime_data):
            self.drag_inside = True

        def drag_leave(self):
            self.drag_inside = False
            self.drag_pos = None

        def drag_move(self, mime_data, x, y):
            self.drag_pos = Geometry.IntPoint(y=y, x=x)

        def drop(self, mime_data, x, y):
            return "copy"

    def test_mouse_tracking_on_topmost_non_overlapped_canvas_item(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        container_canvas_item = CanvasItem.CanvasItemComposition()
        test_canvas_item = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item.wants_mouse_events = True
        container_canvas_item.add_canvas_item(test_canvas_item)
        root_canvas.add_canvas_item(container_canvas_item)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        modifiers = Test.KeyboardModifiers()
        # check assumptions
        self.assertFalse(test_canvas_item.mouse_inside)
        # run test
        root_canvas.canvas_widget.on_mouse_entered()
        root_canvas.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
        self.assertTrue(test_canvas_item.mouse_inside)
        self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
        root_canvas.canvas_widget.on_mouse_exited()
        self.assertFalse(test_canvas_item.mouse_inside)

    def test_mouse_tracking_on_container_with_non_overlapped_canvas_item(self):
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        test_canvas_item = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item.wants_mouse_events = True
        test_canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.add_canvas_item(test_canvas_item)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        modifiers = Test.KeyboardModifiers()
        # check assumptions
        self.assertFalse(test_canvas_item.mouse_inside)
        # run test
        root_canvas.canvas_widget.on_mouse_entered()
        root_canvas.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
        self.assertTrue(test_canvas_item.mouse_inside)
        self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
        root_canvas.canvas_widget.on_mouse_exited()
        self.assertFalse(test_canvas_item.mouse_inside)

    def test_mouse_tracking_on_container_with_two_overlapped_canvas_items(self):
        # tests case where container contains a mouse tracking canvas item with a non-mouse
        # tracking canvas item overlayed.
        ui = Test.UserInterface()
        # test row layout
        root_canvas = CanvasItem.RootCanvasItem(ui)
        test_canvas_item = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item.wants_mouse_events = True
        test_canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        root_canvas.add_canvas_item(test_canvas_item)
        root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        modifiers = Test.KeyboardModifiers()
        # check assumptions
        self.assertFalse(test_canvas_item.mouse_inside)
        # run test
        root_canvas.canvas_widget.on_mouse_entered()
        root_canvas.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
        self.assertTrue(test_canvas_item.mouse_inside)
        self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
        root_canvas.canvas_widget.on_mouse_exited()
        self.assertFalse(test_canvas_item.mouse_inside)

    def test_drag_tracking_on_topmost_non_overlapped_canvas_item(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        container_canvas_item = CanvasItem.CanvasItemComposition()
        test_canvas_item = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item.wants_drag_events = True
        container_canvas_item.add_canvas_item(test_canvas_item)
        root_canvas.add_canvas_item(container_canvas_item)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertFalse(test_canvas_item.drag_inside)
        # run test
        self.assertEqual(root_canvas.canvas_widget.on_drag_enter(None), "accept")
        root_canvas.canvas_widget.on_drag_move(None, 320, 240)
        self.assertTrue(test_canvas_item.drag_inside)
        self.assertEqual(test_canvas_item.drag_pos, Geometry.IntPoint(x=320, y=240))
        self.assertEqual(root_canvas.canvas_widget.on_drop(None, 320, 240), "copy")
        self.assertFalse(test_canvas_item.drag_inside)

    def test_drag_tracking_from_one_item_to_another(self):
        ui = Test.UserInterface()
        modifiers = Test.KeyboardModifiers()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        container_canvas_item = CanvasItem.CanvasItemComposition()
        container_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        test_canvas_item1 = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item1.wants_mouse_events = True
        test_canvas_item1.wants_drag_events = True
        container_canvas_item.add_canvas_item(test_canvas_item1)
        root_canvas.add_canvas_item(container_canvas_item)
        test_canvas_item2 = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item2.wants_mouse_events = True
        container_canvas_item.add_canvas_item(test_canvas_item2)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        root_canvas.canvas_widget.on_mouse_entered()
        root_canvas.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_pressed(160, 160, modifiers)
        self.assertEqual(test_canvas_item1.mouse_pressed_pos, (160, 160))
        root_canvas.canvas_widget.on_mouse_released(160, 160, modifiers)
        self.assertIsNone(test_canvas_item1.mouse_pressed_pos)
        # now the drag. start in the right item, press mouse, move to left item
        # release mouse; press mouse again in left pane and verify it is in the left pane
        root_canvas.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_pressed(480, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_released(160, 160, modifiers)
        # immediate mouse press after mouse release
        root_canvas.canvas_widget.on_mouse_pressed(160, 160, modifiers)
        self.assertEqual(test_canvas_item1.mouse_pressed_pos, (160, 160))
        self.assertIsNone(test_canvas_item2.mouse_pressed_pos)
        root_canvas.canvas_widget.on_mouse_released(160, 160, modifiers)

    def test_mouse_tracking_after_drag_from_one_item_to_another(self):
        ui = Test.UserInterface()
        modifiers = Test.KeyboardModifiers()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        container_canvas_item = CanvasItem.CanvasItemComposition()
        container_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        test_canvas_item1 = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item1.wants_mouse_events = True
        test_canvas_item1.wants_drag_events = True
        container_canvas_item.add_canvas_item(test_canvas_item1)
        root_canvas.add_canvas_item(container_canvas_item)
        test_canvas_item2 = TestCanvasItemClass.TestCanvasItem()
        test_canvas_item2.wants_mouse_events = True
        container_canvas_item.add_canvas_item(test_canvas_item2)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        root_canvas.canvas_widget.on_mouse_entered()
        root_canvas.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
        self.assertTrue(test_canvas_item1.mouse_inside)
        self.assertFalse(test_canvas_item2.mouse_inside)
        self.assertEqual(test_canvas_item1.mouse_pos, (160, 160))
        self.assertEqual(test_canvas_item2.mouse_pos, None)
        root_canvas.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
        self.assertFalse(test_canvas_item1.mouse_inside)
        self.assertTrue(test_canvas_item2.mouse_inside)
        self.assertEqual(test_canvas_item1.mouse_pos, None)
        self.assertEqual(test_canvas_item2.mouse_pos, (160, 160))  # relative pos
        # now the drag. start in the right item, press mouse, move to left item
        # release mouse; press mouse again in left pane and verify it is in the left pane
        root_canvas.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_pressed(480, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
        root_canvas.canvas_widget.on_mouse_released(160, 160, modifiers)
        # check mouse tracking
        self.assertTrue(test_canvas_item1.mouse_inside)
        self.assertFalse(test_canvas_item2.mouse_inside)
        self.assertEqual(test_canvas_item1.mouse_pos, (160, 160))
        self.assertEqual(test_canvas_item2.mouse_pos, None)

    def test_dragging_splitter_resizes_children(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # drag splitter
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=320, y=240), Geometry.IntPoint(x=480, y=240))
        self.assertAlmostEqual(splitter.splits[0], 0.75)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=480, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=480, y=0), size=Geometry.IntSize(width=160, height=480)))

    def test_setting_splitter_initial_values_results_in_correct_layout(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        splitter.splits = [0.4, 0.6]
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check layout
        self.assertAlmostEqual(splitter.splits[0], 0.4)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=256, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=256, y=0), size=Geometry.IntSize(width=640-256, height=480)))

    def test_dragging_splitter_enforces_minimum_size(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # drag splitter
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=320, y=240), Geometry.IntPoint(x=0, y=240))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=64, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=64, y=0), size=Geometry.IntSize(width=576, height=480)))

    def test_resizing_splitter_keeps_relative_sizes(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # update layout
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=720, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=360, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=360, y=0), size=Geometry.IntSize(width=360, height=480)))

    def test_resizing_splitter_slowly_keeps_relative_sizes(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # update layout
        for w in range(640, 801, 4):
            root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=w, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=400, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=400, y=0), size=Geometry.IntSize(width=400, height=480)))

    def test_dragging_splitter_with_three_children_resizes_third_child(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item3 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        splitter.add_canvas_item(canvas_item3)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
        self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
        # drag splitter
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=426, y=240), Geometry.IntPoint(x=500, y=240))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=500 - 213, height=480)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=500, y=0), size=Geometry.IntSize(width=140, height=480)))

    def test_dragging_splitter_with_three_children_should_only_resize_the_two_items_involved(self):
        # problem occurred when resizing to minimum; it pulled space from uninvolved item
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item3 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        splitter.add_canvas_item(canvas_item3)
        root_canvas.add_canvas_item(splitter)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
        self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
        # drag splitter
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=213, y=240), Geometry.IntPoint(x=0, y=240))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=64, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=64, y=0), size=Geometry.IntSize(width=640 - 64 - 214, height=480)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=640 - 214, y=0), size=Geometry.IntSize(width=214, height=480)))

    def test_scroll_area_content_gets_added_at_offset_zero(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        self.assertEqual(content.canvas_origin, Geometry.IntPoint())

    def test_scroll_bar_thumb_rect_disappears_when_visible_larger_than_content(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=100))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=100)))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=0)))

    def test_scroll_bar_can_adjust_full_range_of_content(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
        # drag the thumb down as far as possible
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=90, y=125), Geometry.IntPoint(x=90, y=500))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))

    def test_scroll_bar_can_adjust_full_range_of_content_when_thumb_is_minimum_size(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=30000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=32)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=30000)))
        # drag the thumb down as far as possible
        self.simulate_drag(root_canvas, Geometry.IntPoint(x=90, y=8), Geometry.IntPoint(x=90, y=500))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=468), size=Geometry.IntSize(width=16, height=32)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-29500), size=Geometry.IntSize(width=100, height=30000)))

    def test_resizing_scroll_area_with_scroll_bar_adjusts_thumb_rect(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
        # resize the root
        root_canvas.size_changed(100, 750)
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=int(750 * 0.75))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))

    def test_resizing_scroll_area_with_scroll_bar_adjusts_thumb_rect_when_canvas_is_offset_already(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        content._set_canvas_origin(Geometry.IntPoint(x=0, y=-500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))
        # resize the root
        root_canvas.size_changed(100, 750)
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=750 - int(750 * 0.75)), size=Geometry.IntSize(width=16, height=int(750 * 0.75))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-250), size=Geometry.IntSize(width=100, height=1000)))

    def test_resizing_scroll_area_content_with_adjusts_thumb_rect(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
        # resize the content. make sure the thumb_rect is correct.
        content.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=750))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=int(500*2.0/3))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=750)))

    def test_resizing_scroll_area_content_with_scroll_bar_adjusts_content_position(self):
        # setup canvas
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        root_canvas.add_canvas_item(scroll_area)
        root_canvas.add_canvas_item(scroll_bar)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        content._set_canvas_origin(Geometry.IntPoint(x=0, y=-500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))
        # resize the content. make sure that it will not let the origin be wrong.
        content.update_layout(Geometry.IntPoint(x=0, y=-500), Geometry.IntSize(width=100, height=750))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=int(500*1.0/3+0.5)), size=Geometry.IntSize(width=16, height=int(500*2.0/3))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-250), size=Geometry.IntSize(width=100, height=750)))

    def test_removing_item_from_layout_causes_container_to_relayout(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        empty1 = CanvasItem.EmptyCanvasItem()
        empty2 = CanvasItem.EmptyCanvasItem()
        empty2.sizing.set_fixed_height(40)
        root_canvas.add_canvas_item(empty1)
        root_canvas.add_canvas_item(empty2)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100))
        # check assumptions
        self.assertEqual(empty1.canvas_bounds.height, 60)
        self.assertEqual(empty2.canvas_bounds.height, 40)
        # remove 2nd canvas item
        root_canvas.remove_canvas_item(empty2)
        # check that column was laid out again
        self.assertEqual(empty1.canvas_bounds.height, 100)

    def test_removing_item_from_collapsible_layout_that_gets_resized_causes_container_to_relayout(self):
        ui = Test.UserInterface()
        root_canvas = CanvasItem.RootCanvasItem(ui)
        root_canvas.layout = CanvasItem.CanvasItemColumnLayout()
        empty1 = CanvasItem.EmptyCanvasItem()
        row = CanvasItem.CanvasItemComposition()
        row.sizing.collapsible = True
        row.layout = CanvasItem.CanvasItemRowLayout()
        empty2 = CanvasItem.EmptyCanvasItem()
        empty2.sizing.set_fixed_height(40)
        root_canvas.add_canvas_item(empty1)
        row.add_canvas_item(empty2)
        root_canvas.add_canvas_item(row)
        root_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100))
        # check assumptions
        self.assertEqual(empty1.canvas_bounds.height, 60)
        self.assertEqual(row.canvas_bounds.height, 40)
        self.assertEqual(empty2.canvas_bounds.height, 40)
        # remove 2nd canvas item
        row.remove_canvas_item(empty2)
        # check that column was laid out again
        self.assertEqual(empty1.canvas_bounds.height, 100)
        self.assertEqual(row.canvas_bounds.height, 0)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
