# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import TestUI
from nion.ui import TextEditing
from nion.ui import UserInterface


class FakeMeasurements:
    """A tiny deterministic TextMeasurements fake: every character is 10 pixels wide."""

    CHAR_WIDTH = 10.0

    def get_font_metrics(self, font_str: str, text: str) -> UserInterface.FontMetrics:
        width = len(text) * self.CHAR_WIDTH
        return UserInterface.FontMetrics(width=width, height=16.0, ascent=12.0, descent=4.0, leading=0.0)

    def get_text_offsets(self, font_str: str, text: str) -> typing.Sequence[float]:
        return [i * self.CHAR_WIDTH for i in range(len(text) + 1)]


def make_key(text: str = str(), key: str = str(), *, shift: bool = False, control: bool = False,
             alt: bool = False) -> UserInterface.Key:
    modifiers = CanvasItem.KeyboardModifiers(shift=shift, control=control, alt=alt)
    return TestUI.Key(text, key, modifiers)


class TestTextBuffer(unittest.TestCase):

    def test_initial_state(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        self.assertEqual(buffer.text, "hello")
        self.assertEqual(buffer.cursor_position, 5)
        self.assertIsNone(buffer.selection)

    def test_sanitizes_newlines(self) -> None:
        buffer = TextEditing.TextBuffer("hi\nthere\r\nworld\r")
        self.assertEqual(buffer.text, "hithereworld")

    def test_insert_text_at_cursor(self) -> None:
        buffer = TextEditing.TextBuffer("ac")
        buffer.set_cursor(1, False)
        self.assertTrue(buffer.insert_text("b"))
        self.assertEqual(buffer.text, "abc")
        self.assertEqual(buffer.cursor_position, 2)

    def test_insert_text_replaces_selection(self) -> None:
        buffer = TextEditing.TextBuffer("hello world")
        buffer.set_cursor(0, False)
        buffer.set_cursor(5, True)  # select "hello"
        self.assertTrue(buffer.insert_text("goodbye"))
        self.assertEqual(buffer.text, "goodbye world")
        self.assertIsNone(buffer.selection)

    def test_backspace(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        self.assertTrue(buffer.backspace())
        self.assertEqual(buffer.text, "hell")
        self.assertEqual(buffer.cursor_position, 4)

    def test_backspace_at_start_does_nothing(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(0, False)
        self.assertFalse(buffer.backspace())
        self.assertEqual(buffer.text, "hello")

    def test_delete_forward(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(0, False)
        self.assertTrue(buffer.delete_forward())
        self.assertEqual(buffer.text, "ello")
        self.assertEqual(buffer.cursor_position, 0)

    def test_delete_forward_at_end_does_nothing(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        self.assertFalse(buffer.delete_forward())

    def test_backspace_deletes_selection_instead(self) -> None:
        buffer = TextEditing.TextBuffer("hello world")
        buffer.set_cursor(0, False)
        buffer.set_cursor(5, True)
        self.assertTrue(buffer.backspace())
        self.assertEqual(buffer.text, " world")

    def test_move_cursor_and_select_with_shift(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(0, False)
        buffer.move_cursor(3, True)
        self.assertEqual(buffer.selection, UserInterface.Selection(0, 3))
        self.assertEqual(buffer.selected_text, "hel")

    def test_move_to_start_and_end(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.move_to_start(False)
        self.assertEqual(buffer.cursor_position, 0)
        buffer.move_to_end(False)
        self.assertEqual(buffer.cursor_position, 5)

    def test_select_all(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        self.assertTrue(buffer.select_all())
        self.assertEqual(buffer.selection, UserInterface.Selection(0, 5))

    def test_select_all_empty_text_does_nothing(self) -> None:
        buffer = TextEditing.TextBuffer("")
        self.assertFalse(buffer.select_all())

    def test_select_word_at(self) -> None:
        buffer = TextEditing.TextBuffer("the quick fox")
        self.assertTrue(buffer.select_word_at(5))  # inside "quick"
        self.assertEqual(buffer.selected_text, "quick")

    def test_move_word_left_and_right(self) -> None:
        buffer = TextEditing.TextBuffer("the quick fox")
        buffer.move_to_end(False)
        buffer.move_word(-1, False)
        self.assertEqual(buffer.cursor_position, 10)  # start of "fox"
        buffer.move_word(-1, False)
        self.assertEqual(buffer.cursor_position, 4)  # start of "quick"
        buffer.move_word(1, False)
        self.assertEqual(buffer.cursor_position, 9)  # end of "quick"

    def test_delete_word_backward(self) -> None:
        buffer = TextEditing.TextBuffer("the quick fox")
        buffer.move_to_end(False)
        self.assertTrue(buffer.delete_word_backward())
        self.assertEqual(buffer.text, "the quick ")

    def test_delete_word_forward(self) -> None:
        buffer = TextEditing.TextBuffer("the quick fox")
        buffer.move_to_start(False)
        self.assertTrue(buffer.delete_word_forward())
        self.assertEqual(buffer.text, " quick fox")

    def test_delete_to_end_of_line(self) -> None:
        buffer = TextEditing.TextBuffer("hello world")
        buffer.set_cursor(5, False)
        self.assertTrue(buffer.delete_to_end_of_line())
        self.assertEqual(buffer.text, "hello")

    def test_set_text_resets_state(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(0, True)
        buffer.set_text("goodbye")
        self.assertEqual(buffer.text, "goodbye")
        self.assertEqual(buffer.cursor_position, 7)
        self.assertIsNone(buffer.selection)


class TestTextLayout(unittest.TestCase):

    def setUp(self) -> None:
        self.measurements = FakeMeasurements()

    def test_offsets_last_value_matches_width(self) -> None:
        layout = TextEditing.TextLayout(self.measurements, "ignored", "hello")
        metrics = self.measurements.get_font_metrics("ignored", "hello")
        self.assertAlmostEqual(layout.width, metrics.width)

    def test_x_for_column_round_trips_with_column_for_x(self) -> None:
        layout = TextEditing.TextLayout(self.measurements, "ignored", "hello world")
        for column in range(len("hello world") + 1):
            x = layout.x_for_column(column)
            self.assertEqual(layout.column_for_x(x), column)

    def test_column_for_x_clamps_to_bounds(self) -> None:
        layout = TextEditing.TextLayout(self.measurements, "ignored", "hello")
        self.assertEqual(layout.column_for_x(-100), 0)
        self.assertEqual(layout.column_for_x(1e6), 5)

    def test_column_for_x_picks_nearest_boundary(self) -> None:
        layout = TextEditing.TextLayout(self.measurements, "ignored", "hello")
        # each character is 10px wide; x=4 is closer to column 0 (x=0) than column 1 (x=10).
        self.assertEqual(layout.column_for_x(4), 0)
        # x=6 is closer to column 1 (x=10) than column 0 (x=0).
        self.assertEqual(layout.column_for_x(6), 1)

    def test_selection_x_span(self) -> None:
        layout = TextEditing.TextLayout(self.measurements, "ignored", "hello world")
        self.assertEqual(layout.selection_x_span(UserInterface.Selection(0, 5)), (0.0, 50.0))


class TestLineEditCore(unittest.TestCase):

    def setUp(self) -> None:
        self.clipboard = str()

        def clipboard_get_text() -> str:
            return self.clipboard

        def clipboard_set_text(text: str) -> None:
            self.clipboard = text

        self.core = TextEditing.LineEditCore(FakeMeasurements(), "ignored", clipboard_get_text, clipboard_set_text)

    def test_typing_inserts_text(self) -> None:
        self.assertTrue(self.core.handle_key(make_key(text="h")))
        self.assertTrue(self.core.handle_key(make_key(text="i")))
        self.assertEqual(self.core.buffer.text, "hi")

    def test_backspace_key(self) -> None:
        self.core.buffer.set_text("hello")
        self.assertTrue(self.core.handle_key(make_key(key="backspace")))
        self.assertEqual(self.core.buffer.text, "hell")

    def test_forward_delete_key_is_distinct_from_backspace(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.buffer.move_to_start(False)
        self.assertTrue(self.core.handle_key(make_key(key="delete")))
        self.assertEqual(self.core.buffer.text, "ello")

    def test_home_and_end_keys(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.handle_key(make_key(key="home"))
        self.assertEqual(self.core.buffer.cursor_position, 0)
        self.core.handle_key(make_key(key="end"))
        self.assertEqual(self.core.buffer.cursor_position, 5)

    def test_shift_arrow_extends_selection(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.handle_key(make_key(key="home"))
        self.core.handle_key(make_key(key="right", shift=True))
        self.core.handle_key(make_key(key="right", shift=True))
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(0, 2))

    def test_select_all_shortcut(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.handle_key(make_key(text="a", control=True))
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(0, 5))

    def test_copy_and_paste_shortcuts(self) -> None:
        self.core.buffer.set_text("hello world")
        self.core.buffer.set_cursor(0, False)
        self.core.buffer.set_cursor(5, True)  # select "hello"
        self.core.handle_key(make_key(text="c", control=True))
        self.assertEqual(self.clipboard, "hello")
        self.core.buffer.move_to_end(False)
        self.core.handle_key(make_key(text="v", control=True))
        self.assertEqual(self.core.buffer.text, "hello worldhello")

    def test_cut_shortcut(self) -> None:
        self.core.buffer.set_text("hello world")
        self.core.buffer.set_cursor(0, False)
        self.core.buffer.set_cursor(5, True)  # select "hello"
        self.core.handle_key(make_key(text="x", control=True))
        self.assertEqual(self.clipboard, "hello")
        self.assertEqual(self.core.buffer.text, " world")

    def test_double_click_selects_word(self) -> None:
        self.core.buffer.set_text("the quick fox")
        # "quick" spans columns 4-9 (0-indexed, char width 10px -> pixel 50 lands mid-word).
        self.core.handle_double_click(50.0)
        self.assertEqual(self.core.buffer.selected_text, "quick")

    def test_double_click_then_drag_right_extends_by_whole_words(self) -> None:
        self.core.buffer.set_text("the quick brown fox")
        # double-click "quick" (columns 4-9), then drag into "brown" (columns 10-15, pixel 120).
        self.core.handle_double_click(50.0)
        self.core.handle_mouse_position_changed(120.0)
        self.assertEqual(self.core.buffer.selected_text, "quick brown")

    def test_double_click_then_drag_left_extends_by_whole_words(self) -> None:
        self.core.buffer.set_text("the quick brown fox")
        # double-click "brown" (columns 10-15, pixel 120), then drag back into "the" (pixel 5).
        self.core.handle_double_click(120.0)
        self.core.handle_mouse_position_changed(5.0)
        self.assertEqual(self.core.buffer.selected_text, "the quick brown")

    def test_double_click_then_drag_back_to_same_word_selects_just_that_word(self) -> None:
        self.core.buffer.set_text("the quick brown fox")
        self.core.handle_double_click(120.0)  # "brown"
        self.core.handle_mouse_position_changed(200.0)  # drag into "fox"
        self.core.handle_mouse_position_changed(120.0)  # drag back to "brown" itself
        self.assertEqual(self.core.buffer.selected_text, "brown")

    def test_double_click_drag_ends_on_mouse_released(self) -> None:
        self.core.buffer.set_text("the quick brown fox")
        self.core.handle_double_click(50.0)  # "quick"
        self.core.handle_mouse_released()
        self.core.handle_mouse_position_changed(120.0)  # should no longer extend the selection
        self.assertEqual(self.core.buffer.selected_text, "quick")

    def test_plain_click_and_drag_after_double_click_is_character_wise(self) -> None:
        self.core.buffer.set_text("the quick brown fox")
        self.core.handle_double_click(50.0)  # arms word-wise drag mode
        self.core.handle_mouse_released()
        # a fresh, ordinary click-and-drag afterward should go back to character-wise extension.
        self.core.handle_mouse_pressed(0.0, CanvasItem.KeyboardModifiers())
        self.core.handle_mouse_position_changed(25.0)
        self.assertEqual(self.core.buffer.selected_text, "th")

    def test_mouse_press_places_cursor(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.handle_mouse_pressed(25.0, CanvasItem.KeyboardModifiers())
        # x=25 is equidistant between columns 2 (x=20) and 3 (x=30); ties favor the earlier column.
        self.assertEqual(self.core.buffer.cursor_position, 2)
        self.assertIsNone(self.core.buffer.selection)

    def test_mouse_drag_extends_selection(self) -> None:
        self.core.buffer.set_text("hello world")
        self.core.handle_mouse_pressed(0.0, CanvasItem.KeyboardModifiers())
        self.core.handle_mouse_position_changed(50.0)
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(0, 5))
        self.core.handle_mouse_released()
        # after release, further position changes should not extend the selection.
        self.core.handle_mouse_position_changed(0.0)
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(0, 5))

    def test_caret_blink_tick(self) -> None:
        self.assertTrue(self.core.caret_visible)
        self.assertFalse(self.core.tick(0.1))
        self.assertTrue(self.core.caret_visible)
        self.assertTrue(self.core.tick(TextEditing.CARET_BLINK_INTERVAL))
        self.assertFalse(self.core.caret_visible)

    def test_reset_blink_on_keystroke(self) -> None:
        self.core.tick(TextEditing.CARET_BLINK_INTERVAL)
        self.assertFalse(self.core.caret_visible)
        self.core.handle_key(make_key(text="a"))
        self.assertTrue(self.core.caret_visible)

    def test_enter_and_escape_are_not_consumed(self) -> None:
        self.assertFalse(self.core.handle_key(make_key(key="enter")))
        self.assertFalse(self.core.handle_key(make_key(key="escape")))


if __name__ == "__main__":
    unittest.main()
