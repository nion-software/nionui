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
from nion.utils import Geometry

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
    """Holds the text content and cursor/selection state for a document.

    Uses UserInterface.CursorPosition/Selection (rather than inventing new line-edit-only types) so
    that this same class serves both the single-paragraph (LineEdit) and multi-paragraph (TextEdit)
    cases. By default (allow_newlines=False) this behaves exactly as it did for the line-edit phase
    (embedded newlines are stripped on insert, matching QLineEdit, block_number stays 0). When
    constructed with allow_newlines=True (multi-line phase), "\\n" is preserved as an ordinary
    character -- all of the character-index-based operations below (backspace/delete/move/selection)
    work unchanged either way, since a newline is just another character as far as they're concerned;
    only paragraph_bounds()/cursor_position_info() need to actually look for them.
    """

    def __init__(self, text: str = str(), allow_newlines: bool = False) -> None:
        self.__allow_newlines = allow_newlines
        self.__text = self.__sanitize(text)
        self.__cursor_position = len(self.__text)
        self.__selection_anchor: typing.Optional[int] = None

    def __sanitize(self, text: str) -> str:
        # normalize line endings to "\n" first so callers never have to deal with "\r"/"\r\n"; then,
        # for the single-paragraph (line-edit) case, drop newlines entirely -- matching QLineEdit,
        # which silently drops them (Enter/Return is handled separately as an editing-finished
        # signal, not inserted text).
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not self.__allow_newlines:
            text = text.replace("\n", "")
        return text

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

    def paragraph_bounds(self) -> typing.Sequence[typing.Tuple[int, int]]:
        """Return the (start, end) character indexes of each "\\n"-delimited paragraph.

        For a single-paragraph buffer (allow_newlines=False, or simply no "\\n" present) this
        returns exactly one entry spanning the whole text.
        """
        bounds = list()
        start = 0
        for index, ch in enumerate(self.__text):
            if ch == "\n":
                bounds.append((start, index))
                start = index + 1
        bounds.append((start, len(self.__text)))
        return bounds

    def cursor_position_info(self) -> UserInterface.CursorPosition:
        position = self.__cursor_position
        for block_number, (start, end) in enumerate(self.paragraph_bounds()):
            if position <= end:
                return UserInterface.CursorPosition(position, block_number, position - start)
        # unreachable in practice (paragraph_bounds always covers the full text), but keep a safe
        # fallback consistent with the pre-multi-paragraph behavior.
        return UserInterface.CursorPosition(position, 0, position)

    def insert_newline(self) -> bool:
        """Insert a paragraph break at the cursor (replacing any selection). Only meaningful when
        this buffer was constructed with allow_newlines=True -- otherwise insert_text's sanitizing
        will drop the newline, matching a single-paragraph buffer's existing "Enter does nothing to
        the text" behavior."""
        return self.insert_text("\n")

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


def _paragraph_bounds(text: str) -> typing.Sequence[typing.Tuple[int, int]]:
    """Return (start, end) character indexes of each "\\n"-delimited paragraph in text.

    The "\\n" character itself belongs to neither paragraph -- it sits at index `end` of the
    paragraph before it and `start - 1` of the paragraph after it. Mirrors
    `TextBuffer.paragraph_bounds` exactly (duplicated here rather than shared because
    `TextEditLayout` deliberately only depends on a plain `str`, not a `TextBuffer` instance).
    """
    bounds = []
    start = 0
    for index, ch in enumerate(text):
        if ch == "\n":
            bounds.append((start, index))
            start = index + 1
    bounds.append((start, len(text)))
    return bounds


def _wrap_paragraph_into_rows(text: str, wrap_width: float, font_str: str, measurements: TextMeasurements) -> typing.List[typing.Tuple[int, int]]:
    """Greedily word-wrap a single paragraph (no embedded "\\n") into a list of (start, end) row ranges.

    A pure-Python greedy line-breaking algorithm (not full UAX #14): a "token" is a run of
    non-whitespace characters plus any whitespace immediately following it, so that trailing
    whitespace on a row does not itself force a wrap (matching common editor behavior of allowing
    trailing spaces to overflow past the wrap column). A single token wider than wrap_width on its
    own (a very long "word") is hard-broken at the widest prefix that still fits, so that wrapping
    always makes forward progress.
    """
    if not text:
        return [(0, 0)]
    tokens = [(match.start(), match.end()) for match in re.finditer(r"\S+\s*|\s+", text)]
    rows: typing.List[typing.Tuple[int, int]] = []
    row_start = 0
    token_index = 0
    while token_index < len(tokens):
        token_start, token_end = tokens[token_index]
        candidate_width = measurements.get_text_offsets(font_str, text[row_start:token_end])[-1]
        if candidate_width <= wrap_width:
            token_index += 1
            continue
        if token_start > row_start:
            # this token doesn't fit and the row already has content -- end the row before it.
            rows.append((row_start, token_start))
            row_start = token_start
            continue
        # the token itself is the first thing on this row and is still too wide on its own --
        # hard-break it at the widest prefix that fits (guarantees at least one character of
        # progress so wrapping cannot loop forever on a single overlong "word").
        offsets = measurements.get_text_offsets(font_str, text[row_start:token_end])
        k = 1
        for i in range(1, len(offsets)):
            if offsets[i] <= wrap_width:
                k = i
            else:
                break
        rows.append((row_start, row_start + k))
        row_start += k
    rows.append((row_start, len(text)))
    return rows


class _Row(typing.NamedTuple):
    paragraph_index: int
    position_start: int  # absolute character index (into the full buffer text) where the row begins
    position_end: int  # absolute character index where the row ends (exclusive of a paragraph-separating "\n")
    offsets: typing.Sequence[float]  # cumulative x offsets within the row; length == (position_end - position_start) + 1
    y: float
    height: float


class TextEditLayout:
    """Word-wrapped, multi-row layout for TextEditCore (parallel to TextLayout, not a modification of it).

    Stateless computation, no painting: given the full buffer text, produces visual rows and the
    2D position <-> (row, column)/point conversions a multi-line text widget needs. TextLayout is
    unaffected by this class and continues to be used unchanged by LineEditCore.

    word_wrap_mode "none" (or a missing wrap_width) puts exactly one row per paragraph, at natural
    width. word_wrap_mode "word" greedily word-wraps each paragraph to wrap_width. Other
    UserInterface.TextEditWidgetBehavior wrap modes ("manual"/"anywhere"/"optional") are
    approximated onto "word" by the caller (this class only ever sees "none" or "word").
    """

    def __init__(self, measurements: TextMeasurements, font_str: str, text: str,
                 wrap_width: typing.Optional[float], word_wrap_mode: str) -> None:
        row_height: float = measurements.get_font_metrics(font_str, "x").height
        rows: typing.List[_Row] = []
        y = 0.0
        for paragraph_index, (p_start, p_end) in enumerate(_paragraph_bounds(text)):
            paragraph_text = text[p_start:p_end]
            if word_wrap_mode == "word" and wrap_width is not None:
                sub_ranges = _wrap_paragraph_into_rows(paragraph_text, wrap_width, font_str, measurements)
            else:
                sub_ranges = [(0, len(paragraph_text))]
            for r_start, r_end in sub_ranges:
                row_text = paragraph_text[r_start:r_end]
                offsets = measurements.get_text_offsets(font_str, row_text) if row_text else [0.0]
                rows.append(_Row(paragraph_index, p_start + r_start, p_start + r_end, offsets, y, row_height))
                y += row_height
        self.__rows = rows
        self.__row_height = row_height
        self.__row_starts = [row.position_start for row in rows]
        self.__row_tops = [row.y for row in rows]

    @property
    def row_count(self) -> int:
        return len(self.__rows)

    @property
    def total_height(self) -> float:
        return len(self.__rows) * self.__row_height

    @property
    def content_width(self) -> float:
        return max((row.offsets[-1] for row in self.__rows), default=0.0)

    def row_height(self, row: int) -> float:
        return self.__rows[row].height if 0 <= row < len(self.__rows) else self.__row_height

    def row_top(self, row: int) -> float:
        return self.__rows[row].y if 0 <= row < len(self.__rows) else 0.0

    def row_range(self, row: int) -> typing.Tuple[int, int]:
        r = self.__rows[row]
        return r.position_start, r.position_end

    def row_for_position(self, position: int) -> int:
        """Return the index of the row that owns character index position.

        A position exactly at a wrap boundary (no separating "\\n") is considered to belong to the
        row that starts there (i.e. the row after the wrap), matching the usual editor convention
        that the caret appears at the start of the row you just wrapped into. A position exactly at
        a paragraph-separating "\\n" belongs to the row before it (the "\\n" itself is never part of
        any row's own text), so end-of-line/click behavior lands at the visual end of that row.
        """
        if not self.__row_starts:
            return 0
        index = bisect.bisect_right(self.__row_starts, position) - 1
        return max(0, min(len(self.__rows) - 1, index))

    def row_for_y(self, y: float) -> int:
        if not self.__row_tops:
            return 0
        index = bisect.bisect_right(self.__row_tops, y) - 1
        return max(0, min(len(self.__rows) - 1, index))

    def position_for_row_column(self, row: int, column: int) -> int:
        r = self.__rows[max(0, min(len(self.__rows) - 1, row))]
        column = max(0, min(len(r.offsets) - 1, column))
        return r.position_start + column

    def point_for_position(self, position: int) -> Geometry.FloatPoint:
        row_index = self.row_for_position(position)
        row = self.__rows[row_index]
        column = max(0, min(len(row.offsets) - 1, position - row.position_start))
        return Geometry.FloatPoint(x=row.offsets[column], y=row.y)

    def position_for_point(self, x: float, y: float) -> int:
        row_index = self.row_for_y(y)
        row = self.__rows[row_index]
        offsets = row.offsets
        if x <= offsets[0]:
            column = 0
        elif x >= offsets[-1]:
            column = len(offsets) - 1
        else:
            index = bisect.bisect_left(offsets, x)
            before, after = offsets[index - 1], offsets[index]
            column = index - 1 if (x - before) <= (after - x) else index
        return row.position_start + column

    def selection_rects(self, selection: UserInterface.Selection) -> typing.Sequence[Geometry.FloatRect]:
        rects: typing.List[Geometry.FloatRect] = []
        if selection.start == selection.end:
            return rects
        for row in self.__rows:
            if row.position_end <= selection.start or row.position_start >= selection.end:
                continue
            col_start = max(0, selection.start - row.position_start)
            col_end = min(len(row.offsets) - 1, selection.end - row.position_start)
            col_end = max(col_end, col_start)
            x0, x1 = row.offsets[col_start], row.offsets[col_end]
            rects.append(Geometry.FloatRect(origin=Geometry.FloatPoint(x=x0, y=row.y),
                                             size=Geometry.FloatSize(width=max(0.0, x1 - x0), height=row.height)))
        return rects


# minimum interval (seconds) the caret stays in one blink state (visible or hidden).
CARET_BLINK_INTERVAL = 0.530


class _WordDragSelection:
    """Shared word-wise drag-selection state machine, used by both LineEditCore and TextEditCore.

    After a double-click, dragging extends the selection in whole-word increments anchored to the
    word that was double-clicked, rather than the usual per-character extension of an ordinary
    click-and-drag. This holds only that bit of state/logic and operates purely on character
    positions (via _word_bounds_at) -- hit-testing (pixel position(s) -> character position) stays
    with each caller, since that differs between LineEditCore's single-line x-only lookup and
    TextEditCore's 2D (x, y) lookup.
    """

    def __init__(self, buffer: TextBuffer) -> None:
        self.__buffer = buffer
        self.__word_anchor: typing.Optional[typing.Tuple[int, int]] = None

    @property
    def active(self) -> bool:
        return self.__word_anchor is not None

    def arm(self, position: int) -> None:
        """Call on double-click: arm word-wise drag anchored to the word at position."""
        self.__word_anchor = _word_bounds_at(self.__buffer.text, position)

    def clear(self) -> None:
        self.__word_anchor = None

    def extend(self, position: int) -> bool:
        assert self.__word_anchor is not None
        anchor_start, anchor_end = self.__word_anchor
        start, end = _word_bounds_at(self.__buffer.text, position)
        if start <= anchor_start:
            # dragged to or before the anchor word: selection grows leftward from the anchor's end.
            new_anchor, new_cursor = anchor_end, start
        else:
            # dragged past the anchor word to the right: selection grows rightward from its start.
            new_anchor, new_cursor = anchor_start, end
        changed = self.__buffer.set_cursor(new_anchor, False)
        changed = self.__buffer.set_cursor(new_cursor, True) or changed
        return changed


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
        self.__word_drag = _WordDragSelection(self.__buffer)
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
        self.__word_drag.clear()
        self.reset_blink()
        return changed

    def handle_mouse_position_changed(self, x: float) -> bool:
        if not self.__drag_active:
            return False
        column = self.layout().column_for_x(x)
        if self.__word_drag.active:
            return self.__word_drag.extend(column)
        return self.__buffer.set_cursor(column, True)

    def handle_mouse_released(self) -> None:
        self.__drag_active = False
        self.__word_drag.clear()

    def handle_double_click(self, x: float) -> bool:
        column = self.layout().column_for_x(x)
        changed = self.__buffer.select_word_at(column)
        # arm word-wise drag selection: any drag from here on (until mouse released) extends the
        # selection by whole words, anchored to the word that was just double-clicked.
        self.__word_drag.arm(column)
        self.__drag_active = True
        self.reset_blink()
        return changed


class TextEditCore:
    """Orchestrates a TextBuffer(allow_newlines=True) + TextEditLayout for a multi-line edit.

    Parallel to LineEditCore, which stays unchanged and is still used by LineEditCanvasItem.
    CanvasUserInterface.py's TextEditWidgetBehavior owns an instance of this and delegates to it.
    """

    def __init__(self, measurements: TextMeasurements, font_str: str = "12px",
                 clipboard_get_text: typing.Optional[typing.Callable[[], str]] = None,
                 clipboard_set_text: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self.__measurements = measurements
        self.__font_str = font_str
        self.__buffer = TextBuffer(allow_newlines=True)
        self.__clipboard_get_text = clipboard_get_text or (lambda: str())
        self.__clipboard_set_text = clipboard_set_text or (lambda text: None)
        self.__word_wrap_mode = "none"
        self.__wrap_width: typing.Optional[float] = None
        self.__viewport_height = 0.0
        self.__drag_active = False
        self.__word_drag = _WordDragSelection(self.__buffer)
        # tracks the horizontal pixel position Up/Down/PageUp/PageDown should aim for across
        # consecutive presses (so repeatedly pressing Down through a ragged-right paragraph keeps
        # you near the same horizontal position rather than snapping to each row's actual last
        # character); reset to None (recompute from the cursor) on any non-vertical-move action.
        self.__preferred_x: typing.Optional[float] = None
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

    @property
    def word_wrap_mode(self) -> str:
        return self.__word_wrap_mode

    @word_wrap_mode.setter
    def word_wrap_mode(self, word_wrap_mode: str) -> None:
        # only "none" and "word" are implemented for real; the other UserInterface.TextEditWidgetBehavior
        # wrap modes ("manual"/"anywhere"/"optional") are approximated onto "word" -- a documented
        # MVP simplification, consistent with the earlier word/grapheme segmentation simplifications.
        self.__word_wrap_mode = "none" if word_wrap_mode == "none" else "word"

    def set_wrap_width(self, wrap_width: typing.Optional[float]) -> None:
        self.__wrap_width = wrap_width

    def set_viewport_height(self, height: float) -> None:
        self.__viewport_height = height

    def layout(self) -> TextEditLayout:
        return TextEditLayout(self.__measurements, self.__font_str, self.__buffer.text, self.__wrap_width, self.__word_wrap_mode)

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
        keep_preferred_x = False

        if key.is_up_arrow:
            changed = self.__move_vertical(-1, modifiers.shift)
            keep_preferred_x = True
        elif key.is_down_arrow:
            changed = self.__move_vertical(1, modifiers.shift)
            keep_preferred_x = True
        elif key.is_page_up:
            changed = self.__move_page(-1, modifiers.shift)
            keep_preferred_x = True
        elif key.is_page_down:
            changed = self.__move_page(1, modifiers.shift)
            keep_preferred_x = True
        elif key.is_move_to_start_of_line or key.is_home:
            changed = self.__move_to_row_start(modifiers.shift)
        elif key.is_move_to_end_of_line or key.is_end:
            changed = self.__move_to_row_end(modifiers.shift)
        elif key.is_delete_to_end_of_line:
            changed = buffer.delete_to_end_of_line()
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
        elif key.is_enter_or_return:
            # unlike LineEditCore (which excludes Enter here and fires on_return_pressed instead),
            # Enter always inserts a newline for a multi-line edit, matching QTextEdit. The owning
            # canvas item's on_key_pressed callback still gets first right of refusal before this is
            # ever reached, mirroring LineEditCanvasItem's existing callback-ordering pattern, so
            # app-level conventions like "Enter submits, Shift+Enter inserts a newline" can still be
            # layered on top without changing this engine.
            changed = buffer.insert_newline()
        elif key.is_escape:
            # not handled here - TextEditWidgetBehavior handles on_escape_pressed.
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
            if not keep_preferred_x:
                self.__preferred_x = None
        return consumed

    def __move_to_row_start(self, extend: bool) -> bool:
        layout = self.layout()
        row = layout.row_for_position(self.__buffer.cursor_position)
        start, _ = layout.row_range(row)
        return self.__buffer.set_cursor(start, extend)

    def __move_to_row_end(self, extend: bool) -> bool:
        layout = self.layout()
        row = layout.row_for_position(self.__buffer.cursor_position)
        _, end = layout.row_range(row)
        return self.__buffer.set_cursor(end, extend)

    def __move_to_paragraph_start(self, extend: bool) -> bool:
        position = self.__buffer.cursor_position
        for start, end in self.__buffer.paragraph_bounds():
            if position <= end:
                return self.__buffer.set_cursor(start, extend)
        return False

    def __move_to_paragraph_end(self, extend: bool) -> bool:
        position = self.__buffer.cursor_position
        for start, end in self.__buffer.paragraph_bounds():
            if position <= end:
                return self.__buffer.set_cursor(end, extend)
        return False

    def __row_top_y(self, layout: TextEditLayout, row: int) -> float:
        return layout.point_for_position(layout.position_for_row_column(row, 0)).y

    def __move_vertical(self, direction: int, extend: bool) -> bool:
        layout = self.layout()
        row = layout.row_for_position(self.__buffer.cursor_position)
        target_row = max(0, min(layout.row_count - 1, row + direction))
        if target_row == row:
            # already at the first/last row -- stop, matching native editors (no wrap to document
            # start/end on Up/Down at the edge).
            return False
        x = self.__preferred_x if self.__preferred_x is not None else layout.point_for_position(self.__buffer.cursor_position).x
        position = layout.position_for_point(x, self.__row_top_y(layout, target_row))
        changed = self.__buffer.set_cursor(position, extend)
        self.__preferred_x = x
        return changed

    def __move_page(self, direction: int, extend: bool) -> bool:
        layout = self.layout()
        row_height = layout.row_height(0)
        rows_per_page = max(1, int(self.__viewport_height // row_height)) if row_height else 1
        row = layout.row_for_position(self.__buffer.cursor_position)
        target_row = max(0, min(layout.row_count - 1, row + direction * rows_per_page))
        x = self.__preferred_x if self.__preferred_x is not None else layout.point_for_position(self.__buffer.cursor_position).x
        position = layout.position_for_point(x, self.__row_top_y(layout, target_row))
        changed = self.__buffer.set_cursor(position, extend)
        self.__preferred_x = x
        return changed

    def move_cursor_position(self, operation: str, mode: str) -> bool:
        """Programmatic cursor movement, matching PyQtProxy.py's TextEdit_moveCursorPosition vocabulary.

        operation: "start"/"end"/"start_line"/"end_line"/"start_para"/"end_para"/"previous"/"next"/
        "up"/"down"/"left"/"right". mode: "move" or "keep" (keep extends the selection).
        """
        extend = mode == "keep"
        buffer = self.__buffer
        changed = False
        if operation == "start":
            changed = buffer.move_to_start(extend)
        elif operation == "end":
            changed = buffer.move_to_end(extend)
        elif operation == "start_line":
            changed = self.__move_to_row_start(extend)
        elif operation == "end_line":
            changed = self.__move_to_row_end(extend)
        elif operation == "start_para":
            changed = self.__move_to_paragraph_start(extend)
        elif operation == "end_para":
            changed = self.__move_to_paragraph_end(extend)
        elif operation in ("previous", "left"):
            changed = buffer.move_cursor(-1, extend)
        elif operation in ("next", "right"):
            changed = buffer.move_cursor(1, extend)
        elif operation == "up":
            changed = self.__move_vertical(-1, extend)
        elif operation == "down":
            changed = self.__move_vertical(1, extend)
        if changed:
            self.reset_blink()
            self.__preferred_x = None
        return changed

    # -- mouse --

    def handle_mouse_pressed(self, x: float, y: float, modifiers: UserInterface.KeyboardModifiers) -> bool:
        position = self.layout().position_for_point(x, y)
        changed = self.__buffer.set_cursor(position, modifiers.shift)
        self.__drag_active = True
        self.__word_drag.clear()
        self.__preferred_x = None
        self.reset_blink()
        return changed

    def handle_mouse_position_changed(self, x: float, y: float) -> bool:
        if not self.__drag_active:
            return False
        position = self.layout().position_for_point(x, y)
        if self.__word_drag.active:
            return self.__word_drag.extend(position)
        return self.__buffer.set_cursor(position, True)

    def handle_mouse_released(self) -> None:
        self.__drag_active = False
        self.__word_drag.clear()

    def handle_double_click(self, x: float, y: float) -> bool:
        position = self.layout().position_for_point(x, y)
        changed = self.__buffer.select_word_at(position)
        # arm word-wise drag selection: any drag from here on (until mouse released) extends the
        # selection by whole words, anchored to the word that was just double-clicked.
        self.__word_drag.arm(position)
        self.__drag_active = True
        self.__preferred_x = None
        self.reset_blink()
        return changed

