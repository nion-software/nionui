# standard libraries
import asyncio
import typing
import unittest

# local libraries
from nion.ui import CanvasItem
from nion.ui import CanvasUserInterface
from nion.ui import DrawingContext
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.utils import Geometry


class TestComboBoxCanvasSizing(unittest.TestCase):

    def setUp(self) -> None:
        # TestUI.UserInterface provides deterministic, variable-width font metrics (wider text
        # measures wider), which is what makes these sizing assertions meaningful.
        self.ui = TestUI.UserInterface()

    def tearDown(self) -> None:
        pass

    def test_combo_box_width_matches_widest_item_regardless_of_current_selection(self) -> None:
        controller = CanvasUserInterface.BasicComboBoxWidgetCanvasItemController(self.ui)
        items = ["A", "A Considerably Longer Item", "Mid"]
        controller.set_item_strings(items)

        controller.current_text = items[0]  # shortest item
        width_with_shortest_selected = controller.widget_source.canvas_item.sizing.preferred_width_int

        controller.current_text = items[1]  # longest item
        width_with_longest_selected = controller.widget_source.canvas_item.sizing.preferred_width_int

        controller.current_text = items[2]  # mid-length item
        width_with_mid_selected = controller.widget_source.canvas_item.sizing.preferred_width_int

        # the combo box should not resize as the selection changes.
        self.assertEqual(width_with_shortest_selected, width_with_longest_selected)
        self.assertEqual(width_with_shortest_selected, width_with_mid_selected)

        # and that stable width should actually accommodate the widest item, not just the shortest.
        self.assertGreater(width_with_shortest_selected, self.ui.get_font_metrics("12px", items[0]).width)

    def test_combo_box_width_grows_when_a_wider_item_is_added(self) -> None:
        controller = CanvasUserInterface.BasicComboBoxWidgetCanvasItemController(self.ui)
        controller.set_item_strings(["Short"])
        controller.current_text = "Short"
        narrow_width = controller.widget_source.canvas_item.sizing.preferred_width_int

        controller.set_item_strings(["Short", "A Much, Much Longer Item Than Short"])
        controller.current_text = "Short"
        wide_width = controller.widget_source.canvas_item.sizing.preferred_width_int

        self.assertGreater(wide_width, narrow_width)


class TestLabelCanvasAlignment(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())

    def tearDown(self) -> None:
        pass

    def test_label_text_draws_left_aligned_within_its_box(self) -> None:
        # a label that is wider than its text content (e.g. an explicit fixed width) should draw its
        # text flush against the left edge of its box, matching Qt's default QLabel alignment, rather
        # than centered (which visually looks like extra space between it and a preceding widget).
        row = self.ui.create_row_widget()
        label1 = self.ui.create_label_widget(text="L")
        label2 = self.ui.create_label_widget(text="M", properties={"width": 30})
        row.add(label1)
        row.add(label2)

        canvas_item = row._behavior.canvas_item  # type: ignore[attr-defined]
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=200, height=30))
        canvas_item.layout_immediate(Geometry.IntSize(width=200, height=30))

        drawing_context = DrawingContext.DrawingContext()
        canvas_item.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=30))

        fill_text_commands = [command for command in drawing_context.commands if command[0] == "fillText"]
        self.assertEqual(len(fill_text_commands), 2)

        label2_canvas_rect = canvas_item.canvas_items[1].canvas_rect
        assert label2_canvas_rect

        # the "M" label's text should be drawn at the left edge of its (wider) box, not its center.
        self.assertEqual(fill_text_commands[1][2], float(label2_canvas_rect.left))


class TestCheckBoxAndRadioButtonCanvasSizing(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = TestUI.UserInterface()

    def tearDown(self) -> None:
        pass

    def test_check_box_height_is_not_padded_beyond_the_check_box_glyph_size(self) -> None:
        # the check box row height should be governed by the larger of the text height or the
        # check box glyph (14px) plus a small fixed padding, not by an oversized vertical padding
        # applied on top of the text height. an overly large padding here causes checked rows in
        # a column to appear more spaced out in canvas UI than in Qt UI, even with identical
        # explicit column spacing.
        controller = CanvasUserInterface.BasicCheckBoxWidgetCanvasItemController(self.ui)
        controller.text = "Enable All"
        height = controller.widget_source.canvas_item.sizing.preferred_height_int
        self.assertEqual(height, 16)

    def test_radio_button_height_is_not_padded_beyond_the_radio_button_glyph_size(self) -> None:
        controller = CanvasUserInterface.RadioButtonCanvasItem(text="Option")
        controller.size_to_content(self.ui.get_font_metrics)
        height = controller.sizing.preferred_height_int
        self.assertEqual(height, 16)


class TestGroupBoxCanvas(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())

    def tearDown(self) -> None:
        pass

    def _layout(self, canvas_item: CanvasItem.CanvasItemComposition, width: int = 200, height: int = 100) -> None:
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=width, height=height))
        canvas_item.layout_immediate(Geometry.IntSize(width=width, height=height))

    def test_group_box_draws_a_distinct_background_and_border(self) -> None:
        # a group box should read visually as a group (background fill + border), matching Qt's
        # native QGroupBox frame, rather than being visually indistinguishable from its surroundings.
        group = self.ui.create_group_widget()
        group.add(self.ui.create_label_widget(text="Hi"))
        canvas_item = group._behavior.canvas_item  # type: ignore[attr-defined]
        self._layout(canvas_item)

        drawing_context = DrawingContext.DrawingContext()
        canvas_item.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=100))

        self.assertTrue(any(command[0] == "fill" for command in drawing_context.commands))
        self.assertTrue(any(command[0] == "stroke" for command in drawing_context.commands))

    def test_group_box_border_uses_expected_color_and_half_width(self) -> None:
        group = self.ui.create_group_widget()
        group.add(self.ui.create_label_widget(text="Hi"))
        canvas_item = group._behavior.canvas_item  # type: ignore[attr-defined]
        self._layout(canvas_item)

        drawing_context = DrawingContext.DrawingContext()
        canvas_item.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=100))

        stroke_style_commands = [command for command in drawing_context.commands if command[0] == "strokeStyle"]
        line_width_commands = [command for command in drawing_context.commands if command[0] == "lineWidth"]
        self.assertIn(("strokeStyle", "#dadada"), stroke_style_commands)
        self.assertIn(("lineWidth", 0.5), line_width_commands)

    def test_group_box_draws_its_title_left_aligned(self) -> None:
        group = self.ui.create_group_widget()
        group.add(self.ui.create_label_widget(text="Hi"))
        group.title = "My Group"
        canvas_item = group._behavior.canvas_item  # type: ignore[attr-defined]
        self._layout(canvas_item)

        drawing_context = DrawingContext.DrawingContext()
        canvas_item.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=100))

        fill_text_commands = [command for command in drawing_context.commands if command[0] == "fillText"]
        title_commands = [command for command in fill_text_commands if command[1] == "My Group"]
        self.assertEqual(len(title_commands), 1)
        # the title should be indented from the left edge, not centered across the group's width.
        self.assertLess(title_commands[0][2], 20)

    def test_group_box_height_does_not_change_when_title_is_cleared_after_being_set(self) -> None:
        # the group's sizing must be recomputed whenever content is added/removed, not only when
        # the title changes; otherwise a group created without ever setting a title starts out with
        # stale/incorrect sizing.
        group = self.ui.create_group_widget()
        group.add(self.ui.create_label_widget(text="Hi"))
        canvas_item = group._behavior.canvas_item  # type: ignore[attr-defined]
        self._layout(canvas_item)
        height_without_title = canvas_item.layout_sizing.preferred_height_int

        group.title = "My Group"
        self._layout(canvas_item)
        height_with_title = canvas_item.layout_sizing.preferred_height_int

        group.title = None
        self._layout(canvas_item)
        height_after_clearing_title = canvas_item.layout_sizing.preferred_height_int

        self.assertGreater(height_with_title, height_without_title)
        self.assertEqual(height_without_title, height_after_clearing_title)


class TestLineEditCanvasSizingAndAppearance(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())

    def tearDown(self) -> None:
        pass

    def _layout(self, canvas_item: CanvasItem.AbstractCanvasItem, width: int = 200, height: int = 100) -> None:
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=width, height=height))
        canvas_item.update_layout_immediate(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=width, height=height))

    def test_line_edit_has_a_non_zero_height_when_empty(self) -> None:
        # a line edit with no text and no placeholder should still have a sensible line-height, not
        # collapse to zero height (which would make it invisible/unusable as a placeholder widget).
        line_edit = self.ui.create_line_edit_widget()
        height = line_edit._behavior.canvas_item.sizing.preferred_height_int  # type: ignore[attr-defined]
        self.assertGreater(height, 0)

    def test_line_edit_width_grows_to_fit_placeholder_text(self) -> None:
        line_edit = self.ui.create_line_edit_widget()
        narrow_width = line_edit._behavior.canvas_item.sizing.preferred_width_int  # type: ignore[attr-defined]

        line_edit.placeholder_text = "A Considerably Longer Placeholder"
        wide_width = line_edit._behavior.canvas_item.sizing.preferred_width_int  # type: ignore[attr-defined]

        self.assertGreater(wide_width, narrow_width)

    def test_line_edit_draws_a_white_background(self) -> None:
        # a line edit should draw a white background so it reads as an editable field, rather than
        # being transparent and blending into whatever is drawn behind it.
        line_edit = self.ui.create_line_edit_widget()
        canvas_item = line_edit._behavior.canvas_item  # type: ignore[attr-defined]
        container = CanvasItem.CanvasItemComposition()
        container.add_canvas_item(canvas_item)
        self._layout(container)

        drawing_context = DrawingContext.DrawingContext()
        container.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=100))

        fill_style_commands = [command for command in drawing_context.commands if command[0] == "fillStyle"]
        self.assertIn(("fillStyle", "white"), fill_style_commands)

    def test_line_edit_text_draws_left_aligned_like_a_label(self) -> None:
        # the line edit's text should draw flush against the (padding-inset) left edge of its box,
        # the same way a label draws its text, rather than centered; the border and white background
        # occupy the full (padded) box, effectively surrounding the label-like content area.
        line_edit = self.ui.create_line_edit_widget()
        line_edit.text = "Hello"
        canvas_item = line_edit._behavior.canvas_item  # type: ignore[attr-defined]
        container = CanvasItem.CanvasItemComposition()
        container.add_canvas_item(canvas_item)
        self._layout(container, width=300)

        drawing_context = DrawingContext.DrawingContext()
        container.repaint_immediate(drawing_context, Geometry.IntSize(width=300, height=100))

        fill_text_commands = [command for command in drawing_context.commands if command[0] == "fillText"]
        self.assertEqual(len(fill_text_commands), 1)
        # the text should draw near the left edge (inset only by the cell's own small padding), not
        # centered across the (much wider) box.
        self.assertLess(fill_text_commands[0][2], 10)

        fill_style_commands = [command for command in drawing_context.commands if command[0] == "fillStyle"]
        self.assertIn(("fillStyle", "white"), fill_style_commands)


class TestCanvasWindowSizing(unittest.TestCase):
    # verifies the window auto-grows (but never auto-shrinks) to keep its live content minimum
    # visible, and that the live minimum is pushed down as a native minimum window size so manual
    # user shrinking is clamped to it but not below it.

    def setUp(self) -> None:
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)

    def tearDown(self) -> None:
        self.event_loop.stop()
        self.event_loop.run_forever()
        self.event_loop.close()

    def _make_window(self) -> typing.Tuple[CanvasUserInterface.CanvasWindow, UserInterface.BoxWidget, typing.List[Geometry.IntSize], typing.List[Geometry.IntSize]]:
        ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
        window = CanvasUserInterface.CanvasWindow(ui, "test")
        resize_calls: typing.List[Geometry.IntSize] = []
        minimum_size_calls: typing.List[Geometry.IntSize] = []
        root_window = window._root_window
        # CanvasWindow calls the public resize()/set_minimum_size() dispatch methods on the window.
        root_window.resize = resize_calls.append  # type: ignore[assignment]
        root_window.set_minimum_size = minimum_size_calls.append  # type: ignore[assignment]

        # a column with a single collapsible row so toggling its child's visibility changes the
        # column's own live minimum height, similar to a twist-down section collapsing.
        column = ui.create_column_widget()
        row = ui.create_row_widget(properties={"collapsible": True})
        self.spacer_widget = ui.create_row_widget(properties={"height": 200})
        row.add(self.spacer_widget)
        column.add(row)
        window._attach_root_widget(column)
        window.show()
        return window, column, resize_calls, minimum_size_calls

    def test_window_grows_when_live_content_minimum_exceeds_current_size(self) -> None:
        window, column, resize_calls, minimum_size_calls = self._make_window()
        self.assertEqual(len(resize_calls), 0)

        # simulate adding more content by growing the collapsible row's child.
        self.spacer_widget._behavior.canvas_item.update_sizing(  # type: ignore[attr-defined]
            self.spacer_widget._behavior.canvas_item.sizing.with_fixed_height(400))  # type: ignore[attr-defined]
        window.periodic()

        self.assertEqual(len(resize_calls), 1)
        self.assertGreaterEqual(resize_calls[-1].height, 400)
        self.assertEqual(minimum_size_calls[-1].height, resize_calls[-1].height)

    def test_window_does_not_shrink_when_live_content_minimum_decreases(self) -> None:
        window, column, resize_calls, minimum_size_calls = self._make_window()
        self.spacer_widget._behavior.canvas_item.update_sizing(  # type: ignore[attr-defined]
            self.spacer_widget._behavior.canvas_item.sizing.with_fixed_height(400))  # type: ignore[attr-defined]
        window.periodic()
        grown_size = resize_calls[-1]

        # now hide the content; the live minimum drops, but the window must not shrink itself.
        self.spacer_widget.visible = False
        window.periodic()

        self.assertEqual(len(resize_calls), 1)  # no additional (shrinking) resize call
        self.assertEqual(window._CanvasWindow__current_size, grown_size)  # type: ignore[attr-defined]
        # but the enforced minimum should have dropped, allowing the user to manually shrink later.
        self.assertLess(minimum_size_calls[-1].height, grown_size.height)


if __name__ == '__main__':
    unittest.main()
