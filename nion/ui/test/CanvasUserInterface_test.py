# standard libraries
import unittest

# local libraries
from nion.ui import CanvasUserInterface
from nion.ui import TestUI


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


if __name__ == '__main__':
    unittest.main()
