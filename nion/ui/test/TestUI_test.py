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

    def test_triggering_menu_item_runs_its_callback(self) -> None:
        # a click on a menu item triggers its action, which should run the callback the item was added with.
        document_window = self.ui.create_document_window()
        self.addCleanup(document_window.close)
        menu = document_window.add_menu("File", "file")
        triggered_count = 0

        def handle_triggered() -> None:
            nonlocal triggered_count
            triggered_count += 1

        menu_action = menu.add_menu_item("Open", handle_triggered, action_id="file.open")
        menu_action.trigger()
        self.assertEqual(1, triggered_count)

    def test_document_window_finds_menu_by_the_id_it_was_added_with(self) -> None:
        # building menus looks up an existing menu by its id so that it adds to it rather than making another.
        document_window = self.ui.create_document_window()
        self.addCleanup(document_window.close)
        menu = document_window.add_menu("File", "file")
        self.assertEqual(menu, document_window.get_menu("file"))
        self.assertEqual("File", menu.title)

    def test_document_window_finds_menu_by_the_id_it_was_inserted_with(self) -> None:
        # menus a plug-in creates in Nion Swift are inserted before an existing menu rather than added.
        document_window = self.ui.create_document_window()
        self.addCleanup(document_window.close)
        edit_menu = document_window.add_menu("Edit", "edit")
        file_menu = document_window.insert_menu("File", edit_menu, "file")
        self.assertEqual(file_menu, document_window.get_menu("file"))
        self.assertEqual("File", file_menu.title)
