# standard libraries
import unittest

# third party libraries
# None

# local libraries
from nion.ui import TestUI
from nion.ui import UserInterface as UserInterfaceModule


class TestTestUIUserInterface(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = TestUI.UserInterface()

    def tearDown(self) -> None:
        pass

    def test_get_font_metrics_sanity_check(self) -> None:
        # Test that TestUI.UserInterface.get_font_metrics returns a reasonable size
        # This test will need to be updated if 'make_font_metrics_for_tests' is modified
        self.assertEqual(self.ui.get_font_metrics("ignored", "This is a string"),
                         UserInterfaceModule.FontMetrics(77, 13, 11, 2, 0))

    def test_default_font_metrics_is_var_width(self) -> None:
        self.assertNotEqual(self.ui.get_font_metrics("ignored", "111"),
                            self.ui.get_font_metrics("ignored", "999"))

    def test_get_text_offsets_last_value_matches_font_metrics_width(self) -> None:
        text = "This is a string"
        offsets = self.ui.get_text_offsets("ignored", text)
        self.assertEqual(len(offsets), len(text) + 1)
        self.assertEqual(offsets[0], 0.0)
        self.assertAlmostEqual(offsets[-1], self.ui.get_font_metrics("ignored", text).width)

    def test_get_text_offsets_empty_string(self) -> None:
        self.assertEqual(self.ui.get_text_offsets("ignored", ""), [0.0])

    def test_get_line_break_opportunities_sanity_check(self) -> None:
        # TestUI has no real text segmentation implementation; ensure it returns a
        # sequence without raising for representative inputs (hyphenation, punctuation, spaces).
        for text in ("", "word", "The quick-brown fox jumps over the lazy dog."):
            result = self.ui.get_line_break_opportunities(text)
            self.assertIsInstance(result, list)
