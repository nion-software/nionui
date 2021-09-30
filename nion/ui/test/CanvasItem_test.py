# standard libraries
import contextlib
import logging
import time
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.utils import Geometry


class TestCanvasItem(CanvasItem.AbstractCanvasItem):
    def __init__(self) -> None:
        super(TestCanvasItem, self).__init__()
        self.wants_mouse_events = True
        self._mouse_released = False
        self.key: typing.Optional[UserInterface.Key] = None

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        return True

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._mouse_released = True
        return True

    def key_pressed(self, key: UserInterface.Key) -> bool:
        self.key = key
        return True

    def key_released(self, key: UserInterface.Key) -> bool:
        self.key_r = key
        return True


class TestCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        CanvasItem._threaded_rendering_enabled = False

    def tearDown(self) -> None:
        pass

    def simulate_drag(self, canvas_widget: UserInterface.CanvasWidget, p1: Geometry.IntPointTuple, p2: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers = typing.cast(UserInterface.KeyboardModifiers, CanvasItem.KeyboardModifiers()) if not modifiers else modifiers
        if callable(canvas_widget.on_mouse_pressed):
            canvas_widget.on_mouse_pressed(p1[1], p1[0], modifiers)
        if callable(canvas_widget.on_mouse_position_changed):
            canvas_widget.on_mouse_position_changed(p1[1], p1[0], modifiers)
            midp = Geometry.FloatPoint.make(Geometry.midpoint(Geometry.IntPoint.make(p1).to_float_point(), Geometry.IntPoint.make(p2).to_float_point())).to_int_point()
            canvas_widget.on_mouse_position_changed(midp[1], midp[0], modifiers)
            canvas_widget.on_mouse_position_changed(p2[1], p2[0], modifiers)
        if callable(canvas_widget.on_mouse_released):
            canvas_widget.on_mouse_released(p2[1], p2[0], modifiers)

    def test_drag_inside_bounds(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = TestCanvasItem()
            canvas_widget.canvas_item.add_canvas_item(canvas_item)
            canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=100, h=100))
            self.simulate_drag(canvas_widget, (50, 50), (30, 50))
            self.assertTrue(canvas_item._mouse_released)

    def test_drag_outside_bounds(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = TestCanvasItem()
            canvas_widget.canvas_item.add_canvas_item(canvas_item)
            canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=100, h=100))
            self.simulate_drag(canvas_widget, (50, 50), (-30, 50))
            self.assertTrue(canvas_item._mouse_released)

    def test_drag_within_composition(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = TestCanvasItem()
            container = CanvasItem.CanvasItemComposition()
            container.add_canvas_item(canvas_item)
            canvas_widget.canvas_item.add_canvas_item(container)
            canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=100, h=100))
            self.simulate_drag(canvas_widget, (50, 50), (30, 50))
            self.assertTrue(canvas_item._mouse_released)

    def test_drag_within_composition_but_outside_bounds(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = TestCanvasItem()
            container = CanvasItem.CanvasItemComposition()
            container.add_canvas_item(canvas_item)
            canvas_widget.canvas_item.add_canvas_item(container)
            canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=100, h=100))
            self.simulate_drag(canvas_widget, (50, 50), (-30, 50))
            self.assertTrue(canvas_item._mouse_released)

    def test_layout_uses_minimum_aspect_ratio(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_aspect_ratio(2.0))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=80))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=320))

    def test_layout_uses_maximum_aspect_ratio(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_maximum_aspect_ratio(1.0))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=80, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=480, height=480))

    def test_composition_layout_uses_preferred_aspect_ratio(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        child_canvas = CanvasItem.CanvasItemComposition()
        child_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(child_canvas)
        child_canvas.update_sizing(child_canvas.sizing.with_preferred_aspect_ratio(1.0))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=80, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=480, height=480))

    def test_composition_layout_sizing_includes_margins_but_not_spacing(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout.margins = Geometry.Margins(top=4, bottom=6, left=8, right=10)
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(16).with_maximum_height(24))
        self.assertEqual(canvas_item.layout_sizing.minimum_width, 16 + 8 + 10)
        self.assertEqual(canvas_item.layout_sizing.maximum_height, 24 + 4 + 6)

    def test_row_layout_sizing_includes_margins_and_spacing(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout(spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(16).with_maximum_height(12))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_width(32).with_maximum_height(24))
        canvas_item.canvas_items[2].update_sizing(canvas_item.canvas_items[2].sizing.with_minimum_width(48).with_maximum_height(36))
        self.assertEqual(canvas_item.layout_sizing.minimum_width, 16 + 32 + 48 + 2 * 7 + 8 + 10)  # includes margins and spacing
        self.assertEqual(canvas_item.layout_sizing.maximum_height, 36 + 4 + 6)  # includes margins only

    def test_column_layout_sizing_includes_margins_and_spacing(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout(spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(16).with_maximum_height(12))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_width(32).with_maximum_height(24))
        canvas_item.canvas_items[2].update_sizing(canvas_item.canvas_items[2].sizing.with_minimum_width(48).with_maximum_height(36))
        self.assertEqual(canvas_item.layout_sizing.minimum_width, 48 + 8 + 10)  # includes margins only
        self.assertEqual(canvas_item.layout_sizing.maximum_height, 12 + 24 + 36 + 2 * 7 + 4 + 6)  # includes margins and spacing

    def test_grid_layout_sizing_includes_margins_and_spacing(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2), spacing=7, margins=Geometry.Margins(top=4, bottom=6, left=8, right=10))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=0, y=1))
        #canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=1, y=1))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(16).with_maximum_height(12))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_width(32).with_maximum_height(24))
        canvas_item.canvas_items[2].update_sizing(canvas_item.canvas_items[2].sizing.with_minimum_width(48).with_maximum_height(36))
        self.assertEqual(canvas_item.layout_sizing.minimum_width, 32 + 48 + 1 * 7 + 8 + 10)  # includes margins only
        self.assertEqual(canvas_item.layout_sizing.maximum_height, 24 + 36 + 1 * 7 + 4 + 6)  # includes margins and spacing

    def test_layout_splits_evening_between_two_items(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=320, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=320, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=320, height=480))
        # test column layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=240))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=240))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=240))

    def test_layout_splits_evening_between_three_items_with_spacing_and_margins(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout(spacing=10, margins=Geometry.Margins(top=3, left=5, bottom=7, right=11))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=5, y=3))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=201, height=470))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=216, y=3))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=201, height=470))
        self.assertEqual(canvas_item.canvas_items[2].canvas_origin, Geometry.IntPoint(x=427, y=3))
        self.assertEqual(canvas_item.canvas_items[2].canvas_size, Geometry.IntSize(width=202, height=470))
        # test column layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout(spacing=10, margins=Geometry.Margins(top=3, left=5, bottom=7, right=11))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=5, y=3))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=624, height=150))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=5, y=163))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=624, height=150))
        self.assertEqual(canvas_item.canvas_items[2].canvas_origin, Geometry.IntPoint(x=5, y=323))
        self.assertEqual(canvas_item.canvas_items[2].canvas_size, Geometry.IntSize(width=624, height=150))

    def test_layout_splits_two_with_first_one_minimum_size(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(500))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=500, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=500, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=140, height=480))
        # test column layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_height(300))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=300))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=300))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=180))

    def test_layout_splits_two_with_second_one_minimum_size(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_width(500))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=140, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=140, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=500, height=480))
        # test column layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_height(300))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=180))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=180))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=300))

    def test_layout_splits_two_with_first_one_maximum_size(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_maximum_width(100))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=100, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=100, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=540, height=480))

    def test_layout_splits_two_with_second_one_maximum_size(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_maximum_width(100))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=540, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=540, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=100, height=480))

    def disabled_test_layout_splits_three_with_maximum_making_room_for_minimized_item(self) -> None:
        # this should work, but the particular solver has trouble in this specific case because it reaches
        # the minimum value of 230 on the first pass before it processes the maximum value of 100 and it
        # should be able to go back and raise the 230 to 270 once it sees it has extra space.
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_width(230))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_maximum_width(100))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        for i, child_canvas_item in enumerate(canvas_item.canvas_items):
            print("{} {} {}".format(i, child_canvas_item.canvas_origin, child_canvas_item.canvas_size))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=270, height=480))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=270, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=100, height=480))
        self.assertEqual(canvas_item.canvas_items[2].canvas_origin, Geometry.IntPoint(x=370, y=0))
        self.assertEqual(canvas_item.canvas_items[2].canvas_size, Geometry.IntSize(width=270, height=480))

    def test_column_with_child_with_fixed_size_does_not_expand_child_horizontally(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_bounds, Geometry.IntRect.from_tlbr(0, 0, 20, 30))

    def test_column_with_fixed_size_child_centers_horizontally_by_default(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(230, 305, 250, 335))

    def test_column_with_fixed_size_child_aligns_start(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout(alignment="start")
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(230, 0, 250, 30))

    def test_column_with_fixed_size_child_aligns_end(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout(alignment="end")
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(230, 610, 250, 640))

    def test_row_with_fixed_size_child_centers_horizontally_by_default(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(230, 305, 250, 335))

    def test_row_with_fixed_size_child_aligns_start(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout(alignment="start")
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(0, 305, 20, 335))

    def test_row_with_fixed_size_child_aligns_end(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout(alignment="end")
        canvas_item.add_stretch()
        background_canvas_item = CanvasItem.BackgroundCanvasItem("#F00")
        background_canvas_item.update_sizing(background_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.add_canvas_item(background_canvas_item)
        canvas_item.add_stretch()
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(background_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(460, 305, 480, 335))

    def test_row_layout_with_stretch_inside_column_layout_results_in_correct_vertical_positions(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        row = CanvasItem.CanvasItemComposition()
        row.layout = CanvasItem.CanvasItemRowLayout()
        row.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        row.add_stretch()
        canvas_item.add_canvas_item(row)
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.add_stretch()
        row.canvas_items[0].update_sizing(row.canvas_items[0].sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(row.canvas_items[0].canvas_rect, Geometry.IntRect.from_tlbr(0, 0, 20, 30))
        self.assertEqual(canvas_item.canvas_items[1].canvas_rect, Geometry.IntRect.from_tlbr(20, 305, 40, 335))

    def test_row_layout_with_stretch_inside_column_layout_results_in_correct_row_height(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        row = CanvasItem.CanvasItemComposition()
        row.layout = CanvasItem.CanvasItemRowLayout()
        row.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        row.add_stretch()
        canvas_item.add_canvas_item(row)
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        row.canvas_items[0].update_sizing(row.canvas_items[0].sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(row.canvas_items[0].canvas_rect, Geometry.IntRect.from_tlbr(0, 0, 20, 30))
        self.assertEqual(canvas_item.canvas_items[1].canvas_rect, Geometry.IntRect.from_tlbr(20, 305, 40, 335))

    def test_row_layout_with_stretch_on_each_side_centers_content(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        row = CanvasItem.CanvasItemComposition()
        row.layout = CanvasItem.CanvasItemRowLayout()
        row.add_stretch()
        content_item = CanvasItem.BackgroundCanvasItem("#F00")
        content_item.update_sizing(content_item.sizing.with_fixed_size(Geometry.IntSize(height=20, width=30)))
        row.add_canvas_item(content_item)
        row.add_stretch()
        canvas_item.add_canvas_item(row)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(content_item.canvas_rect, Geometry.IntRect.from_tlbr(0, 305, 20, 335))

    def test_grid_layout_2x2_works(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=320, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(canvas_item.canvas_items[2].canvas_origin, Geometry.IntPoint(x=0, y=240))
        self.assertEqual(canvas_item.canvas_items[2].canvas_size, Geometry.IntSize(width=320, height=240))
        self.assertEqual(canvas_item.canvas_items[3].canvas_origin, Geometry.IntPoint(x=320, y=240))
        self.assertEqual(canvas_item.canvas_items[3].canvas_size, Geometry.IntSize(width=320, height=240))

    def test_grid_layout_splits_with_one_min_size_specified(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_height(300))
        canvas_item.canvas_items[1].update_sizing(canvas_item.canvas_items[1].sizing.with_minimum_width(500))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=140, height=300))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=140, y=0))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=500, height=300))
        self.assertEqual(canvas_item.canvas_items[2].canvas_origin, Geometry.IntPoint(x=0, y=300))
        self.assertEqual(canvas_item.canvas_items[2].canvas_size, Geometry.IntSize(width=140, height=180))
        self.assertEqual(canvas_item.canvas_items[3].canvas_origin, Geometry.IntPoint(x=140, y=300))
        self.assertEqual(canvas_item.canvas_items[3].canvas_size, Geometry.IntSize(width=500, height=180))

    def test_grid_layout_within_column_layout(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        grid_canvas = CanvasItem.CanvasItemComposition()
        grid_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        background = CanvasItem.BackgroundCanvasItem("#F00")
        canvas_item.add_canvas_item(background)
        canvas_item.add_canvas_item(grid_canvas)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
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

    def test_focus_changed_messages_sent_when_focus_changes(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item1.focusable = True
            canvas_item2.focusable = True
            focus_changed_set = set()

            def focus_changed1(focused: bool) -> None:
                focus_changed_set.add(canvas_item1)

            def focus_changed2(focused: bool) -> None:
                focus_changed_set.add(canvas_item2)
            canvas_item1.on_focus_changed = focus_changed1
            canvas_item2.on_focus_changed = focus_changed2
            canvas_item.add_canvas_item(canvas_item1)
            canvas_item.add_canvas_item(canvas_item2)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertIsNone(canvas_item.focused_item)
            self.assertFalse(canvas_item1.focused)
            self.assertFalse(canvas_item2.focused)
            # click in item 1 and check that focus was updated and changed
            modifiers = CanvasItem.KeyboardModifiers()
            canvas_item.canvas_widget.simulate_mouse_click(160, 240, modifiers)
            self.assertTrue(canvas_item1.focused)
            self.assertTrue(canvas_item1 in focus_changed_set)
            self.assertFalse(canvas_item2.focused)
            self.assertFalse(canvas_item2 in focus_changed_set)
            self.assertEqual(canvas_item.focused_item, canvas_item1)
            # click in item 2 and check that focus was updated and changed
            focus_changed_set.clear()
            canvas_item.canvas_widget.simulate_mouse_click(160 + 320, 240, modifiers)
            self.assertFalse(canvas_item1.focused)
            self.assertTrue(canvas_item1 in focus_changed_set)
            self.assertTrue(canvas_item2.focused)
            self.assertTrue(canvas_item2 in focus_changed_set)
            self.assertEqual(canvas_item.focused_item, canvas_item2)

    def test_root_canvas_item_loses_focus_too_when_canvas_widget_loses_focus(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.focusable = True
            canvas_item.wants_mouse_events = True
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
            # check assumptions
            modifiers = CanvasItem.KeyboardModifiers()
            self.assertIsNone(canvas_item.focused_item)
            self.assertFalse(canvas_item.focused)
            canvas_item.canvas_widget.simulate_mouse_click(320, 240, modifiers)
            self.assertTrue(canvas_item.focused)
            self.assertEqual(canvas_item.focused_item, canvas_item)  # refers to itself??
            # become unfocused
            if callable(canvas_item.canvas_widget.on_focus_changed):
                canvas_item.canvas_widget.on_focus_changed(False)
            self.assertFalse(canvas_item.focused)
            self.assertIsNone(canvas_item.focused_item)

    def test_keys_go_to_focused_item(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item1.focusable = True
            canvas_item2.focusable = True
            canvas_item.add_canvas_item(canvas_item1)
            canvas_item.add_canvas_item(canvas_item2)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # click in item 1, then 2 and check key goes to 2nd item
            modifiers = CanvasItem.KeyboardModifiers()
            canvas_item.canvas_widget.simulate_mouse_click(160, 240, modifiers)
            canvas_item.canvas_widget.simulate_mouse_click(160 + 320, 240, modifiers)
            # check assumptions
            self.assertFalse(canvas_item1.focused)
            self.assertTrue(canvas_item2.focused)
            # key should go to 2nd item
            if callable(canvas_item.canvas_widget.on_key_pressed):
                canvas_item.canvas_widget.on_key_pressed(TestUI.Key("a", "a", CanvasItem.KeyboardModifiers()))
            # check result
            self.assertIsNone(canvas_item1.key)
            self.assertEqual(canvas_item2.key.text if canvas_item2.key else None, 'a')
            # now back to first item
            canvas_item1.key = None
            canvas_item2.key = None
            canvas_item.canvas_widget.simulate_mouse_click(160, 240, modifiers)
            if callable(canvas_item.canvas_widget.on_key_pressed):
                canvas_item.canvas_widget.on_key_pressed(TestUI.Key("a", "a", CanvasItem.KeyboardModifiers()))
            self.assertEqual(typing.cast(UserInterface.Key, canvas_item1.key).text if canvas_item1.key else None, 'a')  # unknown type error, need cast
            self.assertIsNone(canvas_item2.key)

    def test_composition_layout_sizing_has_infinite_maximum_if_first_child_is_finite_and_one_is_infinite(self) -> None:
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[0].update_sizing(composition.canvas_items[0].sizing.with_maximum_height(40).with_minimum_height(40))
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_composition_layout_sizing_has_infinite_maximum_if_last_child_is_finite_and_one_is_infinite(self) -> None:
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[1].update_sizing(composition.canvas_items[1].sizing.with_maximum_height(40).with_minimum_height(40))
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_column_layout_sizing_has_infinite_maximum_if_one_child_is_finite_and_one_is_infinite(self) -> None:
        composition = CanvasItem.CanvasItemComposition()
        composition.layout = CanvasItem.CanvasItemColumnLayout()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[0].update_sizing(composition.canvas_items[0].sizing.with_maximum_height(40).with_minimum_height(40))
        composition.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(composition.layout_sizing.minimum_height, 40)
        self.assertIsNone(composition.layout_sizing.maximum_height)

    def test_grid_layout_sizing_has_infinite_maximum_if_one_child_is_finite_and_one_is_infinite(self) -> None:
        grid_canvas = CanvasItem.CanvasItemComposition()
        grid_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        grid_canvas.canvas_items[0].update_sizing(
            grid_canvas.canvas_items[0].sizing.with_maximum_height(40).with_minimum_height(40).with_maximum_width(
                40).with_minimum_width(40))
        grid_canvas.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(grid_canvas.layout_sizing.minimum_height, 40)
        self.assertIsNone(grid_canvas.layout_sizing.maximum_height)
        self.assertEqual(grid_canvas.layout_sizing.minimum_width, 40)
        self.assertIsNone(grid_canvas.layout_sizing.maximum_width)

    def test_height_constraint_inside_layout_with_another_height_constraint_results_in_proper_layout(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        canvas_item.canvas_items[0].update_sizing(canvas_item.canvas_items[0].sizing.with_minimum_height(10).with_maximum_height(10))
        composition = CanvasItem.CanvasItemComposition()
        composition.layout = CanvasItem.CanvasItemColumnLayout()
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
        composition.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
        composition.canvas_items[1].update_sizing(composition.canvas_items[1].sizing.with_minimum_height(40).with_maximum_height(40))
        canvas_item.add_canvas_item(composition)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_items[0].canvas_origin, Geometry.IntPoint(x=0, y=0))
        self.assertEqual(canvas_item.canvas_items[0].canvas_size, Geometry.IntSize(width=640, height=10))
        self.assertEqual(canvas_item.canvas_items[1].canvas_origin, Geometry.IntPoint(x=0, y=10))
        self.assertEqual(canvas_item.canvas_items[1].canvas_size, Geometry.IntSize(width=640, height=470))

    def test_grid_layout_2x2_canvas_item_at_point(self) -> None:
        # test row layout
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2), spacing=20, margins=Geometry.Margins(top=10, bottom=10, left=10, right=10))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
        canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item.canvas_item_at_point(5, 5), canvas_item)
        self.assertEqual(canvas_item.canvas_item_at_point(20, 20), canvas_item.canvas_items[0])
        self.assertEqual(canvas_item.canvas_item_at_point(320, 20), canvas_item)
        self.assertEqual(canvas_item.canvas_item_at_point(340, 20), canvas_item.canvas_items[1])
        self.assertEqual(canvas_item.canvas_item_at_point(320, 240), canvas_item)
        self.assertEqual(canvas_item.canvas_item_at_point(300, 260), canvas_item.canvas_items[2])
        self.assertEqual(canvas_item.canvas_item_at_point(340, 260), canvas_item.canvas_items[3])

    def test_grid_layout_2x2_canvas_item_scroll_area_with_content_and_scroll_bars_inside_column_lays_out_properly(self) -> None:
        # test row layout
        column = CanvasItem.CanvasItemComposition()
        column.layout = CanvasItem.CanvasItemColumnLayout()
        content = CanvasItem.BackgroundCanvasItem("#F00")
        content.update_sizing(content.sizing.with_fixed_size(Geometry.IntSize(width=250, height=60)))
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_area_canvas_item.auto_resize_contents = True
        right_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item)
        bottom_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item, CanvasItem.Orientation.Horizontal)
        bottom_canvas_item.update_sizing(bottom_canvas_item.sizing.with_fixed_height(20))
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(width=2, height=2))
        canvas_item.add_canvas_item(scroll_area_canvas_item, Geometry.IntPoint(x=0, y=0))
        canvas_item.add_canvas_item(right_canvas_item, Geometry.IntPoint(x=1, y=0))
        canvas_item.add_canvas_item(bottom_canvas_item, Geometry.IntPoint(x=0, y=1))
        column.add_canvas_item(canvas_item)
        column.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=200, height=100))
        self.assertEqual(scroll_area_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(0, 0, 80, 184))
        self.assertEqual(right_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(0, 184, 80, 200))
        self.assertEqual(bottom_canvas_item.canvas_rect, Geometry.IntRect.from_tlbr(80, 0, 100, 184))

    def test_item_in_column_layout_with_preferred_less_than_min_expands(self) -> None:
        column = CanvasItem.CanvasItemComposition()
        column.layout = CanvasItem.CanvasItemColumnLayout()
        column.add_spacing(20)
        item = CanvasItem.EmptyCanvasItem()
        item.update_sizing(item.sizing.with_preferred_height(10).with_minimum_height(20))
        column.add_canvas_item(item)
        column.add_spacing(20)
        column.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=30, height=100))
        self.assertEqual(column.canvas_items[0].canvas_rect, Geometry.IntRect.from_tlbr(0, 15, 20, 15))
        self.assertEqual(column.canvas_items[1].canvas_rect, Geometry.IntRect.from_tlbr(20, 0, 80, 30))
        self.assertEqual(column.canvas_items[2].canvas_rect, Geometry.IntRect.from_tlbr(80, 15, 100, 15))

    class TestCanvasItem(CanvasItem.CanvasItemComposition):

        def __init__(self) -> None:
            super(TestCanvasItemClass.TestCanvasItem, self).__init__()
            self.mouse_inside = False
            self.mouse_pos: typing.Optional[Geometry.IntPoint] = None
            self.mouse_pressed_pos: typing.Optional[Geometry.IntPoint] = None
            self.drag_inside = False
            self.drag_pos: typing.Optional[Geometry.IntPoint] = None
            self.repaint_count = 0
            self.repaint_delay = 0.0

        def mouse_entered(self) -> bool:
            self.mouse_inside = True
            return True

        def mouse_exited(self) -> bool:
            self.mouse_inside = False
            self.mouse_pos = None
            return True

        def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
            self.mouse_pos = Geometry.IntPoint(y=y, x=x)
            return True

        def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
            self.mouse_pressed_pos = Geometry.IntPoint(y=y, x=x)
            return True

        def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
            self.mouse_pressed_pos = None
            return True

        def drag_enter(self, mime_data: UserInterface.MimeData) -> str:
            self.drag_inside = True
            return "ignore"

        def drag_leave(self) -> str:
            self.drag_inside = False
            self.drag_pos = None
            return "ignore"

        def drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
            self.drag_pos = Geometry.IntPoint(y=y, x=x)
            return "ignore"

        def drop(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
            return "copy"

        def _repaint(self, drawing_context: DrawingContext.DrawingContext) -> None:
            self.repaint_count += 1
            time.sleep(self.repaint_delay)
            super()._repaint(drawing_context)

    def test_mouse_tracking_on_topmost_non_overlapped_canvas_item(self) -> None:
        ui = TestUI.UserInterface()
        # test row layout
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container_canvas_item = CanvasItem.CanvasItemComposition()
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item.wants_mouse_events = True
            container_canvas_item.add_canvas_item(test_canvas_item)
            canvas_item.add_canvas_item(container_canvas_item)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            modifiers = CanvasItem.KeyboardModifiers()
            # check assumptions
            self.assertFalse(test_canvas_item.mouse_inside)
            # run test
            if callable(canvas_item.canvas_widget.on_mouse_entered):
                canvas_item.canvas_widget.on_mouse_entered()
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
            self.assertTrue(test_canvas_item.mouse_inside)
            self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
            if callable(canvas_item.canvas_widget.on_mouse_exited):
                canvas_item.canvas_widget.on_mouse_exited()
            self.assertFalse(test_canvas_item.mouse_inside)

    def test_mouse_tracking_on_container_with_non_overlapped_canvas_item(self) -> None:
        ui = TestUI.UserInterface()
        # test row layout
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item.wants_mouse_events = True
            test_canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
            canvas_item.add_canvas_item(test_canvas_item)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            modifiers = CanvasItem.KeyboardModifiers()
            # check assumptions
            self.assertFalse(test_canvas_item.mouse_inside)
            # run test
            if callable(canvas_item.canvas_widget.on_mouse_entered):
                canvas_item.canvas_widget.on_mouse_entered()
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
            self.assertTrue(test_canvas_item.mouse_inside)
            self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
            if callable(canvas_item.canvas_widget.on_mouse_exited):
                canvas_item.canvas_widget.on_mouse_exited()
            self.assertFalse(test_canvas_item.mouse_inside)

    def test_mouse_tracking_on_container_with_two_overlapped_canvas_items(self) -> None:
        # tests case where container contains a mouse tracking canvas item with a non-mouse
        # tracking canvas item overlayed.
        ui = TestUI.UserInterface()
        # test row layout
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item.wants_mouse_events = True
            test_canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))
            canvas_item.add_canvas_item(test_canvas_item)
            canvas_item.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            modifiers = CanvasItem.KeyboardModifiers()
            # check assumptions
            self.assertFalse(test_canvas_item.mouse_inside)
            # run test
            if callable(canvas_item.canvas_widget.on_mouse_entered):
                canvas_item.canvas_widget.on_mouse_entered()
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(320, 240, modifiers)
            self.assertTrue(test_canvas_item.mouse_inside)
            self.assertEqual(test_canvas_item.mouse_pos, Geometry.IntPoint(x=320, y=240))
            if callable(canvas_item.canvas_widget.on_mouse_exited):
                canvas_item.canvas_widget.on_mouse_exited()
            self.assertFalse(test_canvas_item.mouse_inside)

    def test_drag_tracking_on_topmost_non_overlapped_canvas_item(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container_canvas_item = CanvasItem.CanvasItemComposition()
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item.wants_drag_events = True
            container_canvas_item.add_canvas_item(test_canvas_item)
            canvas_item.add_canvas_item(container_canvas_item)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertFalse(test_canvas_item.drag_inside)
            # run test
            if callable(canvas_item.canvas_widget.on_drag_enter):
                self.assertEqual(canvas_item.canvas_widget.on_drag_enter(TestUI.MimeData()), "accept")
            if callable(canvas_item.canvas_widget.on_drag_move):
                canvas_item.canvas_widget.on_drag_move(TestUI.MimeData(), 320, 240)
            self.assertTrue(test_canvas_item.drag_inside)
            self.assertEqual(test_canvas_item.drag_pos, Geometry.IntPoint(x=320, y=240))
            if callable(canvas_item.canvas_widget.on_drop):
                self.assertEqual(canvas_item.canvas_widget.on_drop(TestUI.MimeData(), 320, 240), "copy")
            self.assertFalse(test_canvas_item.drag_inside)

    def test_drag_tracking_from_one_item_to_another(self) -> None:
        ui = TestUI.UserInterface()
        modifiers = CanvasItem.KeyboardModifiers()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container_canvas_item = CanvasItem.CanvasItemComposition()
            container_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            test_canvas_item1 = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item1.wants_mouse_events = True
            test_canvas_item1.wants_drag_events = True
            container_canvas_item.add_canvas_item(test_canvas_item1)
            canvas_item.add_canvas_item(container_canvas_item)
            test_canvas_item2 = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item2.wants_mouse_events = True
            container_canvas_item.add_canvas_item(test_canvas_item2)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            if callable(canvas_item.canvas_widget.on_mouse_entered):
                canvas_item.canvas_widget.on_mouse_entered()
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_pressed):
                canvas_item.canvas_widget.on_mouse_pressed(160, 160, modifiers)
            self.assertEqual(test_canvas_item1.mouse_pressed_pos, (160, 160))
            if callable(canvas_item.canvas_widget.on_mouse_released):
                canvas_item.canvas_widget.on_mouse_released(160, 160, modifiers)
            self.assertIsNone(test_canvas_item1.mouse_pressed_pos)
            # now the drag. start in the right item, press mouse, move to left item
            # release mouse; press mouse again in left pane and verify it is in the left pane
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_pressed):
                canvas_item.canvas_widget.on_mouse_pressed(480, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_released):
                canvas_item.canvas_widget.on_mouse_released(160, 160, modifiers)
            # immediate mouse press after mouse release
            if callable(canvas_item.canvas_widget.on_mouse_pressed):
                canvas_item.canvas_widget.on_mouse_pressed(160, 160, modifiers)
            self.assertEqual(test_canvas_item1.mouse_pressed_pos, (160, 160))
            self.assertIsNone(test_canvas_item2.mouse_pressed_pos)
            if callable(canvas_item.canvas_widget.on_mouse_released):
                canvas_item.canvas_widget.on_mouse_released(160, 160, modifiers)

    def test_mouse_tracking_after_drag_from_one_item_to_another(self) -> None:
        ui = TestUI.UserInterface()
        modifiers = CanvasItem.KeyboardModifiers()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container_canvas_item = CanvasItem.CanvasItemComposition()
            container_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            test_canvas_item1 = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item1.wants_mouse_events = True
            test_canvas_item1.wants_drag_events = True
            container_canvas_item.add_canvas_item(test_canvas_item1)
            canvas_item.add_canvas_item(container_canvas_item)
            test_canvas_item2 = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item2.wants_mouse_events = True
            container_canvas_item.add_canvas_item(test_canvas_item2)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            if callable(canvas_item.canvas_widget.on_mouse_entered):
                canvas_item.canvas_widget.on_mouse_entered()
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
            self.assertTrue(test_canvas_item1.mouse_inside)
            self.assertFalse(test_canvas_item2.mouse_inside)
            self.assertEqual(test_canvas_item1.mouse_pos, (160, 160))
            self.assertEqual(test_canvas_item2.mouse_pos, None)
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
            self.assertFalse(test_canvas_item1.mouse_inside)
            self.assertTrue(test_canvas_item2.mouse_inside)
            self.assertEqual(test_canvas_item1.mouse_pos, None)
            self.assertEqual(test_canvas_item2.mouse_pos, (160, 160))  # relative pos
            # now the drag. start in the right item, press mouse, move to left item
            # release mouse; press mouse again in left pane and verify it is in the left pane
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(480, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_pressed):
                canvas_item.canvas_widget.on_mouse_pressed(480, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_position_changed):
                canvas_item.canvas_widget.on_mouse_position_changed(160, 160, modifiers)
            if callable(canvas_item.canvas_widget.on_mouse_released):
                canvas_item.canvas_widget.on_mouse_released(160, 160, modifiers)
            # check mouse tracking
            self.assertTrue(test_canvas_item1.mouse_inside)
            self.assertFalse(test_canvas_item2.mouse_inside)
            self.assertEqual(test_canvas_item1.mouse_pos, (160, 160))
            self.assertEqual(test_canvas_item2.mouse_pos, None)

    def test_layout_splitter_within_splitter(self) -> None:
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter_outer = CanvasItem.SplitterCanvasItem()
        splitter_inner = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item3 = TestCanvasItem()
        splitter_inner.add_canvas_item(canvas_item2)
        splitter_inner.add_canvas_item(canvas_item3)
        splitter_outer.add_canvas_item(canvas_item1)
        splitter_outer.add_canvas_item(splitter_inner)
        canvas_item.add_canvas_item(splitter_outer)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect.from_tlbr(0, 0, 480, 320))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect.from_tlbr(0, 0, 480, 160))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect.from_tlbr(0, 160, 480, 320))

    def test_dragging_splitter_resizes_children(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 0.5)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
            # drag splitter
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=320, y=240), Geometry.IntPoint(x=480, y=240))
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            self.assertAlmostEqual(splitter.splits[0], 0.75)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=480, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=480, y=0), size=Geometry.IntSize(width=160, height=480)))

    def test_setting_splitter_initial_values_results_in_correct_layout(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        splitter.splits = [0.4, 0.6]
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check layout
        self.assertAlmostEqual(splitter.splits[0], 0.4)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=256, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=256, y=0), size=Geometry.IntSize(width=640-256, height=480)))

    def test_setting_splitter_values_after_adding_item_results_in_correct_layout(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.splits = [1.0]
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        splitter.add_canvas_item(canvas_item2)
        splitter.splits = [0.4, 0.6]
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check layout
        self.assertAlmostEqual(splitter.splits[0], 0.4)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=256, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=256, y=0), size=Geometry.IntSize(width=640-256, height=480)))

    def test_resizing_splitter_in_splitter_results_in_correct_layout(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        splitter_in = CanvasItem.SplitterCanvasItem("horizontal")
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item3 = TestCanvasItem()
        splitter_in.add_canvas_item(canvas_item1)
        splitter_in.add_canvas_item(canvas_item3)
        splitter.add_canvas_item(splitter_in)
        splitter.add_canvas_item(canvas_item2)
        splitter_in.splits = [0.5, 0.5]
        splitter.splits = [0.5, 0.5]
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=240)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=240), size=Geometry.IntSize(width=320, height=240)))
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=640))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=320)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=640)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=320), size=Geometry.IntSize(width=320, height=320)))

    def test_splitters_within_splitter_result_in_correct_origins(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        splitter_l = CanvasItem.SplitterCanvasItem("horizontal")
        splitter_r = CanvasItem.SplitterCanvasItem("horizontal")
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        canvas_item3 = TestCanvasItem()
        canvas_item4 = TestCanvasItem()
        splitter_l.add_canvas_item(canvas_item1)
        splitter_l.add_canvas_item(canvas_item2)
        splitter_r.add_canvas_item(canvas_item3)
        splitter_r.add_canvas_item(canvas_item4)
        splitter.add_canvas_item(splitter_l)
        splitter.add_canvas_item(splitter_r)
        splitter_l.splits = [0.5, 0.5]
        splitter_r.splits = [0.5, 0.5]
        splitter.splits = [0.5, 0.5]
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=200, height=200))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=100)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=100), size=Geometry.IntSize(width=100, height=100)))
        self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=100)))
        self.assertEqual(canvas_item4.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=100), size=Geometry.IntSize(width=100, height=100)))

    def test_dragging_splitter_enforces_minimum_size(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 0.5)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
            # drag splitter
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=320, y=240), Geometry.IntPoint(x=0, y=240))
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=64, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=64, y=0), size=Geometry.IntSize(width=576, height=480)))

    def test_resizing_splitter_keeps_relative_sizes(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # update layout
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=720, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=360, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=360, y=0), size=Geometry.IntSize(width=360, height=480)))

    def test_resizing_splitter_slowly_keeps_relative_sizes(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        splitter = CanvasItem.SplitterCanvasItem()
        canvas_item1 = TestCanvasItem()
        canvas_item2 = TestCanvasItem()
        splitter.add_canvas_item(canvas_item1)
        splitter.add_canvas_item(canvas_item2)
        canvas_item.add_canvas_item(splitter)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480))
        # check assumptions
        self.assertAlmostEqual(splitter.splits[0], 0.5)
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
        # update layout
        for w in range(640, 801, 4):
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=w, height=480))
        self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=400, height=480)))
        self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=400, y=0), size=Geometry.IntSize(width=400, height=480)))

    def test_dragging_splitter_with_three_children_resizes_third_child(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item3 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            splitter.add_canvas_item(canvas_item3)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
            self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
            # drag splitter
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=426, y=240), Geometry.IntPoint(x=500, y=240))
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=500 - 213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=500, y=0), size=Geometry.IntSize(width=140, height=480)))

    def test_dragging_splitter_with_three_children_resizes_third_child_after_second(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item3 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            splitter.add_canvas_item(canvas_item3)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
            self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
            # drag splitters
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=213, y=240), Geometry.IntPoint(x=220, y=240), modifiers=CanvasItem.KeyboardModifiers(shift=True))
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=426, y=240), Geometry.IntPoint(x=500, y=240), modifiers=CanvasItem.KeyboardModifiers(shift=True))
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=220, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=220, y=0), size=Geometry.IntSize(width=500 - 220, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=500, y=0), size=Geometry.IntSize(width=140, height=480)))

    def test_dragging_splitter_with_three_children_should_only_resize_the_two_items_involved(self) -> None:
        # problem occurred when resizing to minimum; it pulled space from uninvolved item
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item3 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            splitter.add_canvas_item(canvas_item3)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
            self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
            # drag splitter
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=213, y=240), Geometry.IntPoint(x=0, y=240))
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=64, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=64, y=0), size=Geometry.IntSize(width=640 - 64 - 214, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=640 - 214, y=0), size=Geometry.IntSize(width=214, height=480)))

    def test_dragging_splitter_with_three_children_snaps_to_thirds(self) -> None:
        # problem occurred when resizing to minimum; it pulled space from uninvolved item
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            canvas_item3 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            splitter.add_canvas_item(canvas_item3)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
            self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))
            # drag splitter away, then back
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=213, y=240), Geometry.IntPoint(x=240, y=240), modifiers=CanvasItem.KeyboardModifiers(shift=True))
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=240, y=240), Geometry.IntPoint(x=218, y=240))
            self.assertAlmostEqual(splitter.splits[0], 213.0 / 640.0)
            self.assertAlmostEqual(splitter.splits[1], 213.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=213, y=0), size=Geometry.IntSize(width=213, height=480)))
            self.assertEqual(canvas_item3.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=426, y=0), size=Geometry.IntSize(width=214, height=480)))

    def test_dragging_splitter_snaps_to_half(self) -> None:
        # problem occurred when resizing to minimum; it pulled space from uninvolved item
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            splitter = CanvasItem.SplitterCanvasItem()
            canvas_item1 = TestCanvasItem()
            canvas_item2 = TestCanvasItem()
            splitter.add_canvas_item(canvas_item1)
            splitter.add_canvas_item(canvas_item2)
            canvas_item.add_canvas_item(splitter)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=640, height=480), immediate=True)
            # check assumptions
            self.assertAlmostEqual(splitter.splits[0], 320.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))
            # drag splitter away, then back
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=320, y=240), Geometry.IntPoint(x=300, y=240))
            self.assertAlmostEqual(splitter.splits[0], 300.0 / 640.0)
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=300, y=240), Geometry.IntPoint(x=316, y=240))
            self.assertAlmostEqual(splitter.splits[0], 320.0 / 640.0)
            self.assertEqual(canvas_item1.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=320, height=480)))
            self.assertEqual(canvas_item2.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=320, y=0), size=Geometry.IntSize(width=320, height=480)))

    def test_scroll_area_content_gets_added_at_offset_zero(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        canvas_item.add_canvas_item(scroll_area)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        self.assertEqual(content.canvas_origin, Geometry.IntPoint())

    def test_scroll_bar_thumb_rect_disappears_when_visible_larger_than_content(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=100))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        canvas_item.add_canvas_item(scroll_area)
        canvas_item.add_canvas_item(scroll_bar)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=100)))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=0)))

    def test_scroll_bar_can_adjust_full_range_of_content(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            content = TestCanvasItem()
            content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
            scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
            scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
            canvas_item.add_canvas_item(scroll_area)
            canvas_item.add_canvas_item(scroll_bar)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500), immediate=True)
            # check assumptions
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
            # drag the thumb down as far as possible
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=90, y=125), Geometry.IntPoint(x=90, y=500))
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))

    def test_scroll_bar_can_adjust_full_range_of_content_when_thumb_is_minimum_size(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            content = TestCanvasItem()
            content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=30000), immediate=True)
            scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
            scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
            canvas_item.add_canvas_item(scroll_area)
            canvas_item.add_canvas_item(scroll_bar)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500), immediate=True)
            # check assumptions
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=32)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=30000)))
            # drag the thumb down as far as possible
            self.simulate_drag(canvas_widget, Geometry.IntPoint(x=90, y=8), Geometry.IntPoint(x=90, y=500))
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=468), size=Geometry.IntSize(width=16, height=32)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-29500), size=Geometry.IntSize(width=100, height=30000)))

    def test_resizing_scroll_area_with_scroll_bar_adjusts_thumb_rect(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            content = TestCanvasItem()
            content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
            scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
            scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
            canvas_item.add_canvas_item(scroll_area)
            canvas_item.add_canvas_item(scroll_bar)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500), immediate=True)
            # check assumptions
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
            # resize the canvas item
            canvas_item.size_changed(100, 750)
            canvas_item.refresh_layout_immediate()
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=int(750 * 0.75))))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))

    def test_resizing_scroll_area_with_scroll_bar_adjusts_thumb_rect_when_canvas_is_offset_already(self) -> None:
        # setup canvas
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            content = TestCanvasItem()
            content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000), immediate=True)
            scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
            scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
            canvas_item.add_canvas_item(scroll_area)
            canvas_item.add_canvas_item(scroll_bar)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500), immediate=True)
            content._set_canvas_origin(Geometry.IntPoint(x=0, y=-500))
            # check assumptions
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))
            # resize the canvas item
            canvas_item.size_changed(100, 750)
            canvas_item.refresh_layout_immediate()
            self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=750 - int(750 * 0.75)), size=Geometry.IntSize(width=16, height=int(750 * 0.75))))
            self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-250), size=Geometry.IntSize(width=100, height=1000)))

    def test_resizing_scroll_area_content_with_adjusts_thumb_rect(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        canvas_item.add_canvas_item(scroll_area)
        canvas_item.add_canvas_item(scroll_bar)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=1000)))
        # resize the content. make sure the thumb_rect is correct.
        content.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=750))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=16, height=int(500*2.0/3))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=0), size=Geometry.IntSize(width=100, height=750)))

    def test_resizing_scroll_area_content_with_scroll_bar_adjusts_content_position(self) -> None:
        # setup canvas
        canvas_item = CanvasItem.CanvasItemComposition()
        canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        content = TestCanvasItem()
        content.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=100, height=1000))
        scroll_area = CanvasItem.ScrollAreaCanvasItem(content)
        scroll_bar = CanvasItem.ScrollBarCanvasItem(scroll_area)
        canvas_item.add_canvas_item(scroll_area)
        canvas_item.add_canvas_item(scroll_bar)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=500))
        content._set_canvas_origin(Geometry.IntPoint(x=0, y=-500))
        # check assumptions
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=250), size=Geometry.IntSize(width=16, height=250)))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-500), size=Geometry.IntSize(width=100, height=1000)))
        # resize the content. make sure that it will not let the origin be wrong.
        content.update_layout(Geometry.IntPoint(x=0, y=-500), Geometry.IntSize(width=100, height=750))
        self.assertEqual(scroll_bar.thumb_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=int(500*1.0/3+0.5)), size=Geometry.IntSize(width=16, height=int(500*2.0/3))))
        self.assertEqual(content.canvas_rect, Geometry.IntRect(origin=Geometry.IntPoint(x=0, y=-250), size=Geometry.IntSize(width=100, height=750)))

    def test_removing_item_from_layout_causes_container_to_relayout(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
            empty1 = CanvasItem.EmptyCanvasItem()
            empty2 = CanvasItem.EmptyCanvasItem()
            empty2.update_sizing(empty2.sizing.with_fixed_height(40))
            canvas_item.add_canvas_item(empty1)
            canvas_item.add_canvas_item(empty2)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100), immediate=True)
            # check assumptions
            empty1_canvas_bounds = empty1.canvas_bounds or Geometry.IntRect.empty_rect()
            empty2_canvas_bounds = empty2.canvas_bounds or Geometry.IntRect.empty_rect()
            self.assertEqual(empty1_canvas_bounds.height, 60)
            self.assertEqual(empty2_canvas_bounds.height, 40)
            # remove 2nd canvas item
            canvas_item.remove_canvas_item(empty2)
            # check that column was laid out again
            canvas_item.refresh_layout_immediate()
            empty1_canvas_bounds = empty1.canvas_bounds or Geometry.IntRect.empty_rect()
            self.assertEqual(empty1_canvas_bounds.height, 100)

    def test_removing_item_from_collapsible_layout_that_gets_resized_causes_container_to_relayout(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
            empty1 = CanvasItem.EmptyCanvasItem()
            row = CanvasItem.CanvasItemComposition()
            row.update_sizing(row.sizing.with_collapsible(True))
            row.layout = CanvasItem.CanvasItemRowLayout()
            empty2 = CanvasItem.EmptyCanvasItem()
            empty2.update_sizing(empty2.sizing.with_fixed_height(40))
            canvas_item.add_canvas_item(empty1)
            row.add_canvas_item(empty2)
            canvas_item.add_canvas_item(row)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100), immediate=True)
            # check assumptions
            empty1_canvas_bounds = empty1.canvas_bounds or Geometry.IntRect.empty_rect()
            empty2_canvas_bounds = empty2.canvas_bounds or Geometry.IntRect.empty_rect()
            row_canvas_bounds = row.canvas_bounds or Geometry.IntRect.empty_rect()
            self.assertEqual(empty1_canvas_bounds.height, 60)
            self.assertEqual(row_canvas_bounds.height, 40)
            self.assertEqual(empty2_canvas_bounds.height, 40)
            # remove 2nd canvas item
            row.remove_canvas_item(empty2)
            # check that column was laid out again
            canvas_item.refresh_layout_immediate()
            empty1_canvas_bounds = empty1.canvas_bounds or Geometry.IntRect.empty_rect()
            row_canvas_bounds = row.canvas_bounds or Geometry.IntRect.empty_rect()
            self.assertEqual(empty1_canvas_bounds.height, 100)
            self.assertEqual(row_canvas_bounds.height, 0)

    def test_preferred_size_in_overlap_does_not_limit_sibling_sizes(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container = CanvasItem.CanvasItemComposition()  # overlap layout
            item1 = CanvasItem.CanvasItemComposition()
            item2 = CanvasItem.CanvasItemComposition()
            row = CanvasItem.CanvasItemComposition()
            row.layout = CanvasItem.CanvasItemRowLayout()
            column = CanvasItem.CanvasItemComposition()
            column.layout = CanvasItem.CanvasItemColumnLayout()
            row.add_stretch()
            row.add_spacing(8)
            column.add_stretch()
            column.add_canvas_item(row)
            column.add_spacing(8)
            item1.add_canvas_item(column)
            container.add_canvas_item(item1)
            container.add_canvas_item(item2)
            canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
            canvas_item.add_canvas_item(container)
            canvas_item.add_stretch()
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100), immediate=True)
            # check that items use full container (due to item2 not having preferred size)
            self.assertIsNone(container.layout.get_sizing(container.canvas_items).preferred_height)
            canvas_size1 = item1.canvas_size or Geometry.IntSize()
            canvas_size2 = item2.canvas_size or Geometry.IntSize()
            self.assertEqual(canvas_size1.width, 100)
            self.assertEqual(canvas_size1.height, 50)  # vertical is shared evenly between item1 and stretch
            self.assertEqual(canvas_size2.width, 100)
            self.assertEqual(canvas_size2.height, 50)  # vertical is shared evenly between item2 and stretch

    def test_preferred_width_in_column_does_not_limit_sibling_sizes(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container = CanvasItem.CanvasItemComposition()  # column layout
            container.layout = CanvasItem.CanvasItemColumnLayout()
            item1 = CanvasItem.CanvasItemComposition()
            item2 = CanvasItem.CanvasItemComposition()
            row = CanvasItem.CanvasItemComposition()
            row.layout = CanvasItem.CanvasItemRowLayout()
            row.add_stretch()
            row.add_spacing(8)
            item1.add_canvas_item(row)
            container.add_canvas_item(item1)
            container.add_canvas_item(item2)
            canvas_item.layout = CanvasItem.CanvasItemRowLayout()
            canvas_item.add_canvas_item(container)
            canvas_item.add_stretch()
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100), immediate=True)
            # check that items use full container width (due to item2 not having preferred width)
            self.assertIsNone(container.layout.get_sizing(container.canvas_items).preferred_width)
            canvas_size1 = item1.canvas_size or Geometry.IntSize()
            canvas_size2 = item2.canvas_size or Geometry.IntSize()
            self.assertEqual(canvas_size1.width, 50)
            self.assertEqual(canvas_size1.height, 50)  # vertical is shared evenly between item1 and stretch
            self.assertEqual(canvas_size2.width, 50)
            self.assertEqual(canvas_size2.height, 50)  # vertical is shared evenly between item2 and stretch

    def test_preferred_height_in_row_does_not_limit_sibling_sizes(self) -> None:
        ui = TestUI.UserInterface()
        canvas_widget = ui.create_canvas_widget()
        with contextlib.closing(canvas_widget):
            canvas_item = canvas_widget.canvas_item
            container = CanvasItem.CanvasItemComposition()  # row layout
            container.layout = CanvasItem.CanvasItemRowLayout()
            item1 = CanvasItem.CanvasItemComposition()
            item2 = CanvasItem.CanvasItemComposition()
            column = CanvasItem.CanvasItemComposition()
            column.layout = CanvasItem.CanvasItemColumnLayout()
            column.add_stretch()
            column.add_spacing(8)
            item1.add_canvas_item(column)
            container.add_canvas_item(item1)
            container.add_canvas_item(item2)
            canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
            canvas_item.add_canvas_item(container)
            canvas_item.add_stretch()
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=100, height=100), immediate=True)
            # check that items use full container width (due to item2 not having preferred width)
            self.assertIsNone(container.layout.get_sizing(container.canvas_items).preferred_width)
            canvas_size1 = item1.canvas_size or Geometry.IntSize()
            canvas_size2 = item2.canvas_size or Geometry.IntSize()
            self.assertEqual(canvas_size1.width, 50)
            self.assertEqual(canvas_size1.height, 50)  # vertical is shared evenly between item1 and stretch
            self.assertEqual(canvas_size2.width, 50)
            self.assertEqual(canvas_size2.height, 50)  # vertical is shared evenly between item2 and stretch

    def test_repaint_immediate_paints_child_layers_and_their_elements_too(self) -> None:
        outer_layer = CanvasItem.LayerCanvasItem()
        with contextlib.closing(outer_layer):
            inner_composition = CanvasItem.CanvasItemComposition()
            inner_layer = CanvasItem.LayerCanvasItem()
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            outer_layer.add_canvas_item(inner_composition)
            inner_composition.add_canvas_item(inner_layer)
            inner_layer.add_canvas_item(test_canvas_item)
            outer_layer_repaint_count = outer_layer._repaint_count
            inner_layer_repaint_count = inner_layer._repaint_count
            test_canvas_item_repaint_count = test_canvas_item._repaint_count
            outer_layer.repaint_immediate(DrawingContext.DrawingContext(), Geometry.IntSize(100, 100))
            self.assertEqual(outer_layer_repaint_count + 1, outer_layer._repaint_count)
            self.assertEqual(inner_layer_repaint_count + 1, inner_layer._repaint_count)
            self.assertEqual(test_canvas_item_repaint_count + 1, test_canvas_item._repaint_count)

    def test_repaint_threaded_paints_child_layers_and_their_elements_too(self) -> None:
        CanvasItem._threaded_rendering_enabled = True
        outer_layer = CanvasItem.LayerCanvasItem()
        with contextlib.closing(outer_layer):
            inner_composition = CanvasItem.CanvasItemComposition()
            inner_layer = CanvasItem.LayerCanvasItem()
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            outer_layer.add_canvas_item(inner_composition)
            inner_composition.add_canvas_item(inner_layer)
            inner_layer.add_canvas_item(test_canvas_item)
            # update the outer layer with the initial size
            outer_layer.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=640, height=480))
            # sleep a short time to allow thread to run
            time.sleep(0.05)
            # save the repaint counts
            outer_layer_repaint_count = outer_layer._repaint_count
            inner_layer_repaint_count = inner_layer._repaint_count
            test_canvas_item_repaint_count = test_canvas_item._repaint_count
            # update the canvas item and make sure everyone repaints
            test_canvas_item.update()
            # sleep a short time to allow thread to run
            time.sleep(0.05)
            # check the repaint counts were all incremented
            self.assertEqual(outer_layer_repaint_count + 1, outer_layer._repaint_count)
            self.assertEqual(inner_layer_repaint_count + 1, inner_layer._repaint_count)
            self.assertEqual(test_canvas_item_repaint_count + 1, test_canvas_item._repaint_count)

    def test_update_during_repaint_triggers_another_repaint(self) -> None:
        CanvasItem._threaded_rendering_enabled = True
        outer_layer = CanvasItem.LayerCanvasItem()
        with contextlib.closing(outer_layer):
            test_canvas_item = TestCanvasItemClass.TestCanvasItem()
            test_canvas_item.repaint_delay = 0.05
            outer_layer.add_canvas_item(test_canvas_item)
            # update the outer layer with the initial size
            outer_layer.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=640, height=480), immediate=True)
            # sleep a short time to allow thread to run
            time.sleep(test_canvas_item.repaint_delay / 2)
            test_canvas_item.update()
            time.sleep(test_canvas_item.repaint_delay * 2)
            self.assertEqual(test_canvas_item.repaint_count, 2)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
