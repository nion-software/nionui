# standard libraries
import unittest

# local libraries
from nion.ui import CanvasUserInterface
from nion.ui import DrawingContext
from nion.ui import TestUI
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


if __name__ == '__main__':
    unittest.main()
