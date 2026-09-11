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

    def test_delete_to_deletes_only_up_to_given_end(self) -> None:
        buffer = TextEditing.TextBuffer("hello world", allow_newlines=True)
        buffer.set_cursor(5, False)
        self.assertTrue(buffer.delete_to(8))
        self.assertEqual(buffer.text, "hellorld")
        self.assertEqual(buffer.cursor_position, 5)

    def test_delete_to_at_or_before_cursor_does_nothing(self) -> None:
        buffer = TextEditing.TextBuffer("hello world")
        buffer.set_cursor(5, False)
        self.assertFalse(buffer.delete_to(5))
        self.assertEqual(buffer.text, "hello world")
        self.assertFalse(buffer.delete_to(2))
        self.assertEqual(buffer.text, "hello world")

    def test_set_text_resets_state(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(0, True)
        buffer.set_text("goodbye")
        self.assertEqual(buffer.text, "goodbye")
        self.assertEqual(buffer.cursor_position, 7)
        self.assertIsNone(buffer.selection)


class TestTextBufferMultiParagraph(unittest.TestCase):
    """Covers TextBuffer(allow_newlines=True), the multi-line (TextEdit) mode."""

    def test_newlines_are_dropped_by_default(self) -> None:
        buffer = TextEditing.TextBuffer("a\nb")
        self.assertEqual(buffer.text, "ab")

    def test_newlines_preserved_when_allowed(self) -> None:
        buffer = TextEditing.TextBuffer("a\nb", allow_newlines=True)
        self.assertEqual(buffer.text, "a\nb")

    def test_carriage_returns_normalized_to_newline(self) -> None:
        buffer = TextEditing.TextBuffer("a\r\nb\rc", allow_newlines=True)
        self.assertEqual(buffer.text, "a\nb\nc")

    def test_insert_newline_splits_paragraph(self) -> None:
        buffer = TextEditing.TextBuffer("hello", allow_newlines=True)
        buffer.set_cursor(2, False)
        self.assertTrue(buffer.insert_newline())
        self.assertEqual(buffer.text, "he\nllo")
        self.assertEqual(buffer.cursor_position, 3)

    def test_insert_newline_is_a_no_op_without_allow_newlines(self) -> None:
        buffer = TextEditing.TextBuffer("hello")
        buffer.set_cursor(2, False)
        self.assertFalse(buffer.insert_newline())
        self.assertEqual(buffer.text, "hello")

    def test_paragraph_bounds_single_paragraph(self) -> None:
        buffer = TextEditing.TextBuffer("hello", allow_newlines=True)
        self.assertEqual(buffer.paragraph_bounds(), [(0, 5)])

    def test_paragraph_bounds_multiple_paragraphs(self) -> None:
        buffer = TextEditing.TextBuffer("ab\ncd\ne", allow_newlines=True)
        self.assertEqual(buffer.paragraph_bounds(), [(0, 2), (3, 5), (6, 7)])

    def test_paragraph_bounds_trailing_newline_yields_empty_final_paragraph(self) -> None:
        buffer = TextEditing.TextBuffer("ab\n", allow_newlines=True)
        self.assertEqual(buffer.paragraph_bounds(), [(0, 2), (3, 3)])

    def test_cursor_position_info_reports_correct_block_and_column(self) -> None:
        buffer = TextEditing.TextBuffer("ab\ncd\ne", allow_newlines=True)
        buffer.set_cursor(0, False)
        self.assertEqual(buffer.cursor_position_info(), UserInterface.CursorPosition(0, 0, 0))
        buffer.set_cursor(4, False)  # 'd' in second paragraph ("cd", starting at index 3)
        self.assertEqual(buffer.cursor_position_info(), UserInterface.CursorPosition(4, 1, 1))
        buffer.set_cursor(7, False)  # end of text, third paragraph ("e", starting at index 6)
        self.assertEqual(buffer.cursor_position_info(), UserInterface.CursorPosition(7, 2, 1))

    def test_cursor_position_info_at_paragraph_boundary_belongs_to_earlier_paragraph(self) -> None:
        # cursor position 2 is the newline boundary between "ab" (0-2) and "cd" (3-5); it should be
        # reported as the end of the first paragraph, not the start of the second (matches the
        # convention that a position exactly at a paragraph's end belongs to that paragraph).
        buffer = TextEditing.TextBuffer("ab\ncd", allow_newlines=True)
        buffer.set_cursor(2, False)
        self.assertEqual(buffer.cursor_position_info(), UserInterface.CursorPosition(2, 0, 2))

    def test_backspace_across_paragraph_boundary_joins_paragraphs(self) -> None:
        buffer = TextEditing.TextBuffer("ab\ncd", allow_newlines=True)
        buffer.set_cursor(3, False)
        self.assertTrue(buffer.backspace())
        self.assertEqual(buffer.text, "abcd")

    def test_word_left_right_selection_and_delete_all_work_across_newlines(self) -> None:
        # backspace/delete/move/selection are unmodified by allow_newlines -- a "\n" is just another
        # character to those operations.
        buffer = TextEditing.TextBuffer("ab\ncd", allow_newlines=True)
        buffer.select_all()
        self.assertEqual(buffer.selected_text, "ab\ncd")
        self.assertTrue(buffer.delete_selection())
        self.assertEqual(buffer.text, "")


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


class TestTextEditLayout(unittest.TestCase):
    """Covers TextEditLayout, the word-wrapped multi-row layout used by TextEditCore."""

    def setUp(self) -> None:
        self.measurements = FakeMeasurements()  # 10px/char, 16px row height

    def test_no_wrap_mode_puts_one_row_per_paragraph(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd\ne", None, "none")
        self.assertEqual(layout.row_count, 3)
        self.assertEqual(layout.row_range(0), (0, 2))
        self.assertEqual(layout.row_range(1), (3, 5))
        self.assertEqual(layout.row_range(2), (6, 7))

    def test_no_wrap_mode_ignores_wrap_width(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "hello world", 30.0, "none")
        self.assertEqual(layout.row_count, 1)

    def test_empty_text_has_a_single_empty_row(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "", None, "none")
        self.assertEqual(layout.row_count, 1)
        self.assertEqual(layout.row_range(0), (0, 0))

    def test_word_wrap_splits_at_word_boundaries(self) -> None:
        # "the quick fox", 10px/char: "the " = 40px, "quick " = 60px, "fox" = 30px; wrap at 60px.
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "the quick fox", 60.0, "word")
        self.assertEqual(layout.row_count, 3)
        self.assertEqual(layout.row_range(0), (0, 4))  # "the "
        self.assertEqual(layout.row_range(1), (4, 10))  # "quick "
        self.assertEqual(layout.row_range(2), (10, 13))  # "fox"

    def test_word_wrap_hard_breaks_a_single_overlong_word(self) -> None:
        # "abcdefghij" (10 chars, 100px) with wrap_width=35px (3.5 chars) must hard-break every 3
        # characters (offsets [0,10,20,30,40,...]; largest k with offsets[k] <= 35 is k=3).
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "abcdefghij", 35.0, "word")
        self.assertEqual([layout.row_range(i) for i in range(layout.row_count)],
                          [(0, 3), (3, 6), (6, 9), (9, 10)])

    def test_word_wrap_paragraph_boundaries_still_apply(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab cd\nef", 100.0, "word")
        self.assertEqual(layout.row_count, 2)
        self.assertEqual(layout.row_range(0), (0, 5))
        self.assertEqual(layout.row_range(1), (6, 8))

    def test_total_height_and_row_height(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd", None, "none")
        self.assertEqual(layout.row_count, 2)
        self.assertEqual(layout.row_height(0), 16.0)
        self.assertEqual(layout.total_height, 32.0)

    def test_row_top(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd\nef", None, "none")
        self.assertEqual([layout.row_top(i) for i in range(layout.row_count)], [0.0, 16.0, 32.0])

    def test_content_width_is_widest_row(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "a\nabc", None, "none")
        self.assertEqual(layout.content_width, 30.0)

    def test_row_for_position_lands_before_newline_in_earlier_row(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd", None, "none")
        self.assertEqual(layout.row_for_position(2), 0)  # right at the "\n" -> end of row 0
        self.assertEqual(layout.row_for_position(3), 1)  # right after the "\n" -> start of row 1

    def test_row_for_position_at_wrap_boundary_lands_in_next_row(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "the quick fox", 60.0, "word")
        self.assertEqual(layout.row_for_position(4), 1)  # boundary between "the " and "quick "

    def test_point_for_position_and_position_for_point_round_trip(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncdef", None, "none")
        for position in range(len("ab\ncdef") + 1):
            point = layout.point_for_position(position)
            self.assertEqual(layout.position_for_point(point.x, point.y), position)

    def test_position_for_point_clamps_out_of_range_y(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd", None, "none")
        self.assertEqual(layout.position_for_point(0.0, -100.0), 0)
        self.assertEqual(layout.position_for_point(1e6, 1e6), 5)

    def test_position_for_row_column(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncdef", None, "none")
        self.assertEqual(layout.position_for_row_column(1, 2), 5)

    def test_selection_rects_within_one_row(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "hello", None, "none")
        rects = layout.selection_rects(UserInterface.Selection(1, 3))
        self.assertEqual(len(rects), 1)
        self.assertEqual((rects[0].left, rects[0].width), (10.0, 20.0))

    def test_selection_rects_span_multiple_rows(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "ab\ncd\nef", None, "none")
        rects = layout.selection_rects(UserInterface.Selection(1, 7))
        self.assertEqual(len(rects), 3)
        # first row: from column 1 to end of "ab" (full remaining width).
        self.assertEqual((rects[0].left, rects[0].width), (10.0, 10.0))
        # middle row "cd": selection fully covers it.
        self.assertEqual((rects[1].left, rects[1].width), (0.0, 20.0))
        # last row "ef": selection covers only the first column.
        self.assertEqual((rects[2].left, rects[2].width), (0.0, 10.0))

    def test_selection_rects_empty_for_collapsed_selection(self) -> None:
        layout = TextEditing.TextEditLayout(self.measurements, "ignored", "hello", None, "none")
        self.assertEqual(layout.selection_rects(UserInterface.Selection(2, 2)), [])


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


class TestTextEditCore(unittest.TestCase):

    def setUp(self) -> None:
        self.clipboard = str()

        def clipboard_get_text() -> str:
            return self.clipboard

        def clipboard_set_text(text: str) -> None:
            self.clipboard = text

        self.core = TextEditing.TextEditCore(FakeMeasurements(), "ignored", clipboard_get_text, clipboard_set_text)

    def test_enter_inserts_newline_rather_than_being_swallowed(self) -> None:
        self.core.buffer.set_text("hello")
        self.core.buffer.move_to_end(False)
        self.assertTrue(self.core.handle_key(make_key(key="enter")))
        self.assertEqual(self.core.buffer.text, "hello\n")

    def test_typing_and_backspace_work_as_in_line_edit(self) -> None:
        self.assertTrue(self.core.handle_key(make_key(text="h")))
        self.assertTrue(self.core.handle_key(make_key(text="i")))
        self.assertEqual(self.core.buffer.text, "hi")
        self.assertTrue(self.core.handle_key(make_key(key="backspace")))
        self.assertEqual(self.core.buffer.text, "h")

    def test_word_wrap_mode_setter_approximates_unimplemented_modes_onto_word(self) -> None:
        self.core.word_wrap_mode = "none"
        self.assertEqual(self.core.word_wrap_mode, "none")
        for mode in ("word", "manual", "anywhere", "optional"):
            self.core.word_wrap_mode = mode
            self.assertEqual(self.core.word_wrap_mode, "word")

    def test_down_then_up_round_trips_using_preferred_x(self) -> None:
        # "ab" (row 0, y=0) / "cdef" (row 1, y=16); place cursor after "ab" (x=20), press Down: it
        # should land at the column nearest x=20 in "cdef" (column 2 -> position 5), then Up should
        # return to position 2 (reusing the preferred x, not recomputing from the new column).
        self.core.buffer.set_text("ab\ncdef")
        self.core.buffer.set_cursor(2, False)
        self.assertTrue(self.core.handle_key(make_key(key="down")))
        self.assertEqual(self.core.buffer.cursor_position, 5)
        self.assertTrue(self.core.handle_key(make_key(key="up")))
        self.assertEqual(self.core.buffer.cursor_position, 2)

    def test_down_at_last_row_does_not_move(self) -> None:
        self.core.buffer.set_text("ab\ncd")
        self.core.buffer.move_to_end(False)
        self.core.handle_key(make_key(key="down"))
        self.assertEqual(self.core.buffer.cursor_position, 5)

    def test_up_at_first_row_does_not_move(self) -> None:
        self.core.buffer.set_text("ab\ncd")
        self.core.buffer.move_to_start(False)
        self.core.handle_key(make_key(key="up"))
        self.assertEqual(self.core.buffer.cursor_position, 0)

    def test_shift_down_extends_selection(self) -> None:
        self.core.buffer.set_text("ab\ncd")
        self.core.buffer.move_to_start(False)
        self.core.handle_key(make_key(key="down", shift=True))
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(0, 3))

    def test_page_down_and_page_up(self) -> None:
        self.core.buffer.set_text("a\nb\nc\nd\ne")  # 5 single-char paragraphs, rows at y=0,16,32,48,64
        self.core.set_viewport_height(32.0)  # 2 rows per page
        self.core.buffer.move_to_start(False)
        self.assertTrue(self.core.handle_key(make_key(key="page_down")))
        self.assertEqual(self.core.buffer.cursor_position, 4)  # row 2 ("c")
        self.assertTrue(self.core.handle_key(make_key(key="page_down")))
        self.assertEqual(self.core.buffer.cursor_position, 8)  # row 4 ("e")
        self.core.handle_key(make_key(key="page_down"))
        self.assertEqual(self.core.buffer.cursor_position, 8)  # clamped to last row ("e")
        self.assertTrue(self.core.handle_key(make_key(key="page_up")))
        self.assertEqual(self.core.buffer.cursor_position, 4)  # back to row 2

    def test_home_end_are_row_aware_when_wrapped(self) -> None:
        # "the quick fox" wraps (at 60px = 6 chars) into "the "/"quick "/"fox"; Home/End on a
        # position inside the wrapped second row should go to that row's bounds, not the document's.
        self.core.word_wrap_mode = "word"
        self.core.set_wrap_width(60.0)
        self.core.buffer.set_text("the quick fox")
        self.core.buffer.set_cursor(7, False)  # inside "quick " (row 1, spanning [4, 10))
        self.core.handle_key(make_key(key="home"))
        self.assertEqual(self.core.buffer.cursor_position, 4)
        self.core.handle_key(make_key(key="end"))
        self.assertEqual(self.core.buffer.cursor_position, 10)

    def test_delete_to_end_of_line_only_deletes_current_line_not_whole_document(self) -> None:
        # regression test: TextEditCore.handle_key used to delegate delete-to-end-of-line
        # (Ctrl/Cmd+K) straight to TextBuffer.delete_to_end_of_line(), which truncates to the end
        # of the *entire* buffer -- silently destroying every subsequent paragraph in a multi-line
        # document. It must instead behave like Home/End (row-aware), stopping at the end of the
        # current line.
        self.core.buffer.set_text("line one\nline two\nline three")
        self.core.buffer.set_cursor(4, False)  # after "line" in "line one"
        self.assertTrue(self.core.handle_key(make_key(key="delete_to_end_of_line")))
        self.assertEqual(self.core.buffer.text, "line\nline two\nline three")
        self.assertEqual(self.core.buffer.cursor_position, 4)

    def test_delete_to_end_of_line_is_wrap_row_aware(self) -> None:
        # when word-wrapped, "end of line" means the end of the current visual row, consistent
        # with the existing (already row-aware) Home/End handling above.
        self.core.word_wrap_mode = "word"
        self.core.set_wrap_width(60.0)
        self.core.buffer.set_text("the quick fox")
        self.core.buffer.set_cursor(7, False)  # inside "quick " (row 1, spanning [4, 10))
        self.assertTrue(self.core.handle_key(make_key(key="delete_to_end_of_line")))
        self.assertEqual(self.core.buffer.text, "the quifox")

    def test_delete_to_end_of_line_at_row_end_does_nothing(self) -> None:
        self.core.buffer.set_text("line one\nline two")
        self.core.buffer.set_cursor(8, False)  # end of "line one", right before the "\n"
        self.core.handle_key(make_key(key="delete_to_end_of_line"))
        self.assertEqual(self.core.buffer.text, "line one\nline two")

    def test_mouse_pressed_hit_tests_in_two_dimensions(self) -> None:
        self.core.buffer.set_text("ab\ncd")
        self.assertTrue(self.core.handle_mouse_pressed(10.0, 16.0, CanvasItem.KeyboardModifiers()))
        self.assertEqual(self.core.buffer.cursor_position, 4)  # row 1 ("cd"), column 1

    def test_double_click_then_drag_selects_whole_words_in_two_dimensions(self) -> None:
        self.core.buffer.set_text("the quick fox")
        self.assertTrue(self.core.handle_double_click(65.0, 0.0))  # inside "quick"
        self.assertEqual(self.core.buffer.selected_text, "quick")
        self.core.handle_mouse_position_changed(115.0, 0.0)  # drag onto "fox"
        self.assertEqual(self.core.buffer.selected_text, "quick fox")
        self.core.handle_mouse_released()
        # a fresh plain click-drag afterward is character-wise again.
        self.core.handle_mouse_pressed(0.0, 0.0, CanvasItem.KeyboardModifiers())
        self.core.handle_mouse_position_changed(20.0, 0.0)
        self.assertEqual(self.core.buffer.selected_text, "th")

    def test_move_cursor_position_operations(self) -> None:
        self.core.buffer.set_text("ab\ncd\nef")
        self.core.buffer.set_cursor(4, False)  # 'd' in second paragraph
        self.assertTrue(self.core.move_cursor_position("start_para", "move"))
        self.assertEqual(self.core.buffer.cursor_position, 3)
        self.assertTrue(self.core.move_cursor_position("end_para", "move"))
        self.assertEqual(self.core.buffer.cursor_position, 5)
        self.assertTrue(self.core.move_cursor_position("start", "move"))
        self.assertEqual(self.core.buffer.cursor_position, 0)
        self.assertTrue(self.core.move_cursor_position("end", "move"))
        self.assertEqual(self.core.buffer.cursor_position, 8)
        self.assertTrue(self.core.move_cursor_position("previous", "move"))
        self.assertEqual(self.core.buffer.cursor_position, 7)
        self.assertTrue(self.core.move_cursor_position("next", "keep"))
        self.assertEqual(self.core.buffer.selection, UserInterface.Selection(7, 8))

    def test_caret_blink(self) -> None:
        self.assertTrue(self.core.tick(TextEditing.CARET_BLINK_INTERVAL))
        self.assertFalse(self.core.caret_visible)

    def test_enter_key_still_reaches_handle_key_unlike_line_edit(self) -> None:
        # LineEditCore excludes Enter (returns consumed=False); TextEditCore always consumes it.
        self.assertTrue(self.core.handle_key(make_key(key="enter")))


if __name__ == "__main__":
    unittest.main()
