"""
Backend-independent text-editing engine.

This module holds the reusable "core" logic for canvas-drawn text widgets: the document/cursor/
selection model (`TextBuffer`), the pixel-position <-> character-index math (`TextLayout`), and the
keyboard/mouse command interpretation for a single-line edit (`LineEditCore`).

It is deliberately independent of `CanvasItem`/`DrawingContext` (no painting here) so that it can be
unit tested without a canvas, and so that the same classes can be extended to a multi-line `TextEdit`
engine later without a rewrite. `nion/ui/CanvasUserInterface.py` owns the actual canvas item that
paints using the data this module computes, and adapts mouse/key/focus events from the canvas item
into calls on this module's classes.

Explicitly deferred for the first (single-line) version - see TEXT_EDIT_PLAN.md for details:
    - grapheme-cluster-aware caret movement/deletion (operates per Python string index for now)
    - full UAX #29 word-boundary segmentation (uses a simple regex word/whitespace rule for now)
    - IME/dead-key composition
    - undo/redo
    - context menu
"""

from __future__ import annotations

import bisect
import re
import typing

from nion.ui import UserInterface

if typing.TYPE_CHECKING:
    pass


class TextMeasurements(typing.Protocol):
    """Minimal set of backend calls this module needs, independent of the full UserInterface class."""

    def get_font_metrics(self, font_str: str, text: str) -> UserInterface.FontMetrics: ...

    def get_text_offsets(self, font_str: str, text: str) -> typing.Sequence[float]: ...


# a run of word characters, or a run of non-word/non-whitespace characters, or a run of whitespace.
# used for the MVP word-boundary approximation (double-click word select, word-wise movement/delete).
_WORD_PATTERN = re.compile(r"\w+|[^\w\s]+|\s+")


def _word_bounds_at(text: str, column: int) -> typing.Tuple[int, int]:
    """Return the (start, end) character indexes of the "word" run containing column.

    If column is at a boundary between two runs, the run to the left is used (matching the usual
    convention for double-click word selection landing exactly between words) -- except at column
    0 (the very start of text), where there is no run to the left, so the first run is used
    instead. If text is empty, returns (0, 0).
    """
    if not text:
        return 0, 0
    for match in _WORD_PATTERN.finditer(text):
        start, end = match.start(), match.end()
        if start < column <= end or (column == 0 and start == 0):
            return start, end
    # column is before the first run (shouldn't normally happen) or text has no runs.
    return 0, 0


def _next_word_boundary(text: str, column: int) -> int:
    """Return the character index of the next word-run boundary at or after column (for ctrl/alt+Right).

    Whitespace-only runs are skipped over (not landed on) so that word-wise movement matches the
    usual editor convention of jumping past intervening whitespace straight to the end of the next
    word, rather than stopping partway there.
    """
    if column >= len(text):
        return len(text)
    for match in _WORD_PATTERN.finditer(text):
        if match.end() > column and not match.group().isspace():
            return match.end()
    return len(text)


def _previous_word_boundary(text: str, column: int) -> int:
    """Return the character index of the previous word-run boundary at or before column (for ctrl/alt+Left).

    Whitespace-only runs are skipped over (not landed on), matching the usual editor convention of
    jumping past intervening whitespace straight to the start of the previous word.
    """
    if column <= 0:
        return 0
    previous_start = 0
    for match in _WORD_PATTERN.finditer(text):
        if match.start() >= column:
            break
        if not match.group().isspace():
            previous_start = match.start()
    return previous_start


class TextBuffer:
    """Holds the text content and cursor/selection state for a single paragraph (line-edit phase).

    Uses UserInterface.CursorPosition/Selection (rather than inventing new line-edit-only types) so
    that this same class can be extended to multi-line documents later without changing its contract
    for the single-paragraph case (block_number stays 0 throughout the line-edit phase).
    """

    def __init__(self, text: str = str()) -> None:
        self.__text = self.__sanitize(text)
        self.__cursor_position = len(self.__text)
        self.__selection_anchor: typing.Optional[int] = None

    def __sanitize(self, text: str) -> str:
        # a line edit has no embedded newlines; matches QLineEdit, which silently drops them
        # (Enter/Return is handled separately as an editing-finished signal, not inserted text).
        return text.replace("\r\n", "").replace("\n", "").replace("\r", "")

    @property
    def text(self) -> str:
        return self.__text

    def set_text(self, text: str) -> None:
        """Programmatic set (e.g. from LineEditWidget.text setter). Resets cursor/selection."""
        self.__text = self.__sanitize(text)
        self.__cursor_position = len(self.__text)
        self.__selection_anchor = None

    @property
    def cursor_position(self) -> int:
        return self.__cursor_position

    @property
    def selection(self) -> typing.Optional[UserInterface.Selection]:
        if self.__selection_anchor is None or self.__selection_anchor == self.__cursor_position:
            return None
        start = min(self.__selection_anchor, self.__cursor_position)
        end = max(self.__selection_anchor, self.__cursor_position)
        return UserInterface.Selection(start, end)

    @property
    def selected_text(self) -> str:
        selection = self.selection
        return self.__text[selection.start:selection.end] if selection else str()

    def cursor_position_info(self) -> UserInterface.CursorPosition:
        return UserInterface.CursorPosition(self.__cursor_position, 0, self.__cursor_position)

    def set_cursor(self, column: int, extend_selection: bool) -> bool:
        column = max(0, min(len(self.__text), column))
        old_cursor_position = self.__cursor_position
        old_selection_anchor = self.__selection_anchor
        if extend_selection:
            if self.__selection_anchor is None:
                self.__selection_anchor = old_cursor_position
        else:
            self.__selection_anchor = None
        self.__cursor_position = column
        return self.__cursor_position != old_cursor_position or self.__selection_anchor != old_selection_anchor

    def move_cursor(self, delta_columns: int, extend_selection: bool) -> bool:
        return self.set_cursor(self.__cursor_position + delta_columns, extend_selection)

    def move_to_start(self, extend_selection: bool) -> bool:
        return self.set_cursor(0, extend_selection)

    def move_to_end(self, extend_selection: bool) -> bool:
        return self.set_cursor(len(self.__text), extend_selection)

    def move_word(self, direction: int, extend_selection: bool) -> bool:
        # direction is -1 (word left) or +1 (word right).
        if direction < 0:
            column = _previous_word_boundary(self.__text, self.__cursor_position)
        else:
            column = _next_word_boundary(self.__text, self.__cursor_position)
        return self.set_cursor(column, extend_selection)

    def select_all(self) -> bool:
        if len(self.__text) == 0:
            return False
        old_selection = self.selection
        self.__selection_anchor = 0
        self.__cursor_position = len(self.__text)
        return self.selection != old_selection

    def select_word_at(self, column: int) -> bool:
        start, end = _word_bounds_at(self.__text, max(0, min(len(self.__text), column)))
        old_selection = self.selection
        self.__selection_anchor = start
        self.__cursor_position = end
        return self.selection != old_selection

    def insert_text(self, text: str) -> bool:
        text = self.__sanitize(text)
        if not text:
            return False
        selection = self.selection
        if selection is not None:
            start, end = selection.start, selection.end
        else:
            start = end = self.__cursor_position
        self.__text = self.__text[:start] + text + self.__text[end:]
        self.__cursor_position = start + len(text)
        self.__selection_anchor = None
        return True

    def delete_selection(self) -> bool:
        selection = self.selection
        if selection is None:
            return False
        self.__text = self.__text[:selection.start] + self.__text[selection.end:]
        self.__cursor_position = selection.start
        self.__selection_anchor = None
        return True

    def backspace(self) -> bool:
        if self.selection is not None:
            return self.delete_selection()
        if self.__cursor_position == 0:
            return False
        self.__text = self.__text[:self.__cursor_position - 1] + self.__text[self.__cursor_position:]
        self.__cursor_position -= 1
        return True

    def delete_forward(self) -> bool:
        if self.selection is not None:
            return self.delete_selection()
        if self.__cursor_position >= len(self.__text):
            return False
        self.__text = self.__text[:self.__cursor_position] + self.__text[self.__cursor_position + 1:]
        return True

    def delete_word_backward(self) -> bool:
        if self.selection is not None:
            return self.delete_selection()
        start = _previous_word_boundary(self.__text, self.__cursor_position)
        if start == self.__cursor_position:
            return False
        self.__text = self.__text[:start] + self.__text[self.__cursor_position:]
        self.__cursor_position = start
        return True

    def delete_word_forward(self) -> bool:
        if self.selection is not None:
            return self.delete_selection()
        end = _next_word_boundary(self.__text, self.__cursor_position)
        if end == self.__cursor_position:
            return False
        self.__text = self.__text[:self.__cursor_position] + self.__text[end:]
        return True

    def delete_to_end_of_line(self) -> bool:
        if self.__cursor_position >= len(self.__text):
            return False
        self.__text = self.__text[:self.__cursor_position]
        self.__selection_anchor = None
        return True


class TextLayout:
    """Stateless pixel-position <-> character-index math for a single line of text.

    No DrawingContext dependency, so the same contract can be reused once multi-line layout (line-
    wrapping into multiple offsets arrays, one per visual row) is added later - only the caller
    changes, not this class.
    """

    def __init__(self, measurements: TextMeasurements, font_str: str, text: str) -> None:
        self.__offsets = measurements.get_text_offsets(font_str, text) if text else [0.0]

    @property
    def offsets(self) -> typing.Sequence[float]:
        return self.__offsets

    @property
    def width(self) -> float:
        return self.__offsets[-1] if self.__offsets else 0.0

    def x_for_column(self, column: int) -> float:
        column = max(0, min(len(self.__offsets) - 1, column))
        return self.__offsets[column]

    def column_for_x(self, x: float) -> int:
        """Return the character index whose boundary is closest to pixel position x."""
        if x <= self.__offsets[0]:
            return 0
        if x >= self.__offsets[-1]:
            return len(self.__offsets) - 1
        # bisect_left finds the insertion point; compare against the neighboring offset to choose
        # whichever boundary x is actually closer to (nearest-boundary hit testing, matching how
        # native text widgets place the caret on the near side of the character under the pointer).
        index = bisect.bisect_left(self.__offsets, x)
        if index == 0:
            return 0
        before, after = self.__offsets[index - 1], self.__offsets[index]
        return index - 1 if (x - before) <= (after - x) else index

    def selection_x_span(self, selection: UserInterface.Selection) -> typing.Tuple[float, float]:
        return self.x_for_column(selection.start), self.x_for_column(selection.end)


# minimum interval (seconds) the caret stays in one blink state (visible or hidden).
CARET_BLINK_INTERVAL = 0.530


class LineEditCore:
    """Orchestrates a TextBuffer + TextLayout for a single-line edit, given key/mouse events.

    This is what CanvasUserInterface.py's LineEditWidgetBehavior owns an instance of and delegates
    to, rather than reimplementing key-handling logic itself.
    """

    def __init__(self, measurements: TextMeasurements, font_str: str = "12px",
                 clipboard_get_text: typing.Optional[typing.Callable[[], str]] = None,
                 clipboard_set_text: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self.__measurements = measurements
        self.__font_str = font_str
        self.__buffer = TextBuffer()
        self.__clipboard_get_text = clipboard_get_text or (lambda: str())
        self.__clipboard_set_text = clipboard_set_text or (lambda text: None)
        self.__drag_active = False
        # when a drag follows a double-click (word selection), the drag extends the selection in
        # whole-word increments, anchored to the word that was originally double-clicked, rather
        # than the usual per-character extension used for an ordinary click-and-drag.
        self.__drag_word_anchor: typing.Optional[typing.Tuple[int, int]] = None
        self.caret_visible = True
        self.__blink_accumulator = 0.0

    @property
    def buffer(self) -> TextBuffer:
        return self.__buffer

    @property
    def font_str(self) -> str:
        return self.__font_str

    @font_str.setter
    def font_str(self, font_str: str) -> None:
        self.__font_str = font_str

    def layout(self) -> TextLayout:
        return TextLayout(self.__measurements, self.__font_str, self.__buffer.text)

    def reset_blink(self) -> None:
        self.caret_visible = True
        self.__blink_accumulator = 0.0

    def tick(self, dt: float) -> bool:
        """Advance the caret blink state. Returns True if the visible state changed (repaint needed)."""
        self.__blink_accumulator += dt
        if self.__blink_accumulator >= CARET_BLINK_INTERVAL:
            self.__blink_accumulator -= CARET_BLINK_INTERVAL
            self.caret_visible = not self.caret_visible
            return True
        return False

    # -- keyboard --

    def handle_key(self, key: UserInterface.Key) -> bool:
        buffer = self.__buffer
        modifiers = key.modifiers
        changed = False
        consumed = True

        if key.is_move_to_start_of_line:
            changed = buffer.move_to_start(modifiers.shift)
        elif key.is_move_to_end_of_line:
            changed = buffer.move_to_end(modifiers.shift)
        elif key.is_delete_to_end_of_line:
            changed = buffer.delete_to_end_of_line()
        elif key.is_home:
            changed = buffer.move_to_start(modifiers.shift)
        elif key.is_end:
            changed = buffer.move_to_end(modifiers.shift)
        elif key.is_left_arrow:
            changed = buffer.move_word(-1, modifiers.shift) if modifiers.alt else buffer.move_cursor(-1, modifiers.shift)
        elif key.is_right_arrow:
            changed = buffer.move_word(1, modifiers.shift) if modifiers.alt else buffer.move_cursor(1, modifiers.shift)
        elif key.is_backspace:
            changed = buffer.delete_word_backward() if modifiers.alt else buffer.backspace()
        elif key.is_delete:
            # is_delete is True for either backspace or forward-delete; is_backspace (checked above)
            # already claimed the backspace case, so reaching here means forward-delete.
            changed = buffer.delete_word_forward() if modifiers.alt else buffer.delete_forward()
        elif key.is_enter_or_return or key.is_escape:
            # not handled here - LineEditWidgetBehavior handles on_return_pressed/on_escape_pressed.
            consumed = False
        elif modifiers.control and key.text.lower() == "a":
            changed = buffer.select_all()
        elif modifiers.control and key.text.lower() == "c":
            self.__clipboard_set_text(buffer.selected_text)
        elif modifiers.control and key.text.lower() == "x":
            selected_text = buffer.selected_text
            if selected_text:
                self.__clipboard_set_text(selected_text)
                changed = buffer.delete_selection()
        elif modifiers.control and key.text.lower() == "v":
            changed = buffer.insert_text(self.__clipboard_get_text())
        elif key.text and not modifiers.control and not modifiers.alt and ord(key.text[0]) >= 0x20:
            # printable text (ordinary typing); excludes control characters (e.g. tab, escape,
            # backspace/delete already handled above) and characters typed with control/alt/cmd held.
            changed = buffer.insert_text(key.text)
        else:
            consumed = False

        if consumed:
            self.reset_blink()
        return consumed

    # -- mouse --

    def handle_mouse_pressed(self, x: float, modifiers: UserInterface.KeyboardModifiers) -> bool:
        column = self.layout().column_for_x(x)
        changed = self.__buffer.set_cursor(column, modifiers.shift)
        self.__drag_active = True
        self.__drag_word_anchor = None
        self.reset_blink()
        return changed

    def handle_mouse_position_changed(self, x: float) -> bool:
        if not self.__drag_active:
            return False
        column = self.layout().column_for_x(x)
        if self.__drag_word_anchor is not None:
            return self.__extend_word_selection(column)
        return self.__buffer.set_cursor(column, True)

    def handle_mouse_released(self) -> None:
        self.__drag_active = False
        self.__drag_word_anchor = None

    def handle_double_click(self, x: float) -> bool:
        column = self.layout().column_for_x(x)
        changed = self.__buffer.select_word_at(column)
        # arm word-wise drag selection: any drag from here on (until mouse released) extends the
        # selection by whole words, anchored to the word that was just double-clicked.
        self.__drag_word_anchor = _word_bounds_at(self.__buffer.text, column)
        self.__drag_active = True
        self.reset_blink()
        return changed

    def __extend_word_selection(self, column: int) -> bool:
        assert self.__drag_word_anchor is not None
        anchor_start, anchor_end = self.__drag_word_anchor
        start, end = _word_bounds_at(self.__buffer.text, column)
        if start <= anchor_start:
            # dragged to or before the anchor word: selection grows leftward from the anchor's end.
            new_anchor, new_cursor = anchor_end, start
        else:
            # dragged past the anchor word to the right: selection grows rightward from its start.
            new_anchor, new_cursor = anchor_start, end
        changed = self.__buffer.set_cursor(new_anchor, False)
        changed = self.__buffer.set_cursor(new_cursor, True) or changed
        return changed
