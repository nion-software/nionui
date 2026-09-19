# standard libraries
import asyncio
import contextlib
import typing
import unittest

# local libraries
from nion.ui import CanvasItem
from nion.ui import CanvasUserInterface
from nion.ui import Dialog
from nion.ui import DrawingContext
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Binding
from nion.utils import Geometry
from nion.utils import Model


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

    def test_label_is_centered_against_a_taller_widget_in_the_same_row(self) -> None:
        # a label is only as tall as its text, so in a row with a taller widget (here a combo box) it
        # has to be centered: both draw their text centered within their own box, so sharing a center
        # is what puts their text on the same line. top-aligning the label would raise its text above
        # the combo box text by half the difference in their heights.
        row = self.ui.create_row_widget()
        row.add(self.ui.create_label_widget(text="Color:"))
        row.add_spacing(8)
        row.add(self.ui.create_combo_box_widget(items=["Red", "Green", "Blue"]))

        canvas_item = row._behavior.canvas_item  # type: ignore[attr-defined]
        canvas_size = Geometry.IntSize(width=200, height=40)
        canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), canvas_size)
        canvas_item.layout_immediate(canvas_size)

        label_canvas_rect = canvas_item.canvas_items[0].canvas_rect
        combo_box_canvas_rect = canvas_item.canvas_items[2].canvas_rect
        assert label_canvas_rect and combo_box_canvas_rect

        self.assertLess(label_canvas_rect.height, combo_box_canvas_rect.height)  # otherwise nothing is being tested
        self.assertEqual(label_canvas_rect.center.y, combo_box_canvas_rect.center.y)


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


class TestScrollAreaWidgetSizing(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())

    def tearDown(self) -> None:
        pass

    def test_hidden_scroll_bar_does_not_impose_minimum_width(self) -> None:
        # regression test: the scroll bar's fixed width should not count toward the scroll area's own
        # minimum width when the scroll bar is hidden (vertical_policy == "off"), only when it is shown.
        scroll_area = self.ui.create_scroll_area_widget()
        scroll_area.set_scrollbar_policies("off", "needed")
        width_with_scroll_bar = scroll_area._behavior.canvas_item.layout_sizing.minimum_width  # type: ignore[attr-defined]

        scroll_area.set_scrollbar_policies("off", "off")
        width_without_scroll_bar = scroll_area._behavior.canvas_item.layout_sizing.minimum_width  # type: ignore[attr-defined]

        self.assertIsNotNone(width_with_scroll_bar)
        self.assertGreaterEqual(width_with_scroll_bar, 16)
        self.assertTrue(width_without_scroll_bar is None or width_without_scroll_bar < width_with_scroll_bar)


class TestLineEditCanvasIntegration(unittest.TestCase):
    """Integration tests exercising the LineEditWidget/LineEditWidgetBehavior/LineEditCanvasItem
    wiring end-to-end (mouse/key/focus events flowing through to TextEditing.LineEditCore and back
    out via the on_text_edited/on_editing_finished/on_return_pressed/on_escape_pressed callbacks)."""

    def setUp(self) -> None:
        self.test_ui = TestUI.UserInterface()
        self.ui = CanvasUserInterface.CanvasUserInterface(self.test_ui)

    def _key(self, text: str = str(), key: str = str(), *, shift: bool = False, control: bool = False,
              alt: bool = False) -> UserInterface.Key:
        modifiers = CanvasItem.KeyboardModifiers(shift=shift, control=control, alt=alt)
        return TestUI.Key(text, key, modifiers)

    def _make_line_edit(self) -> typing.Tuple[UserInterface.LineEditWidget, typing.Any]:
        widget = self.ui.create_line_edit_widget()
        canvas_item = widget._behavior._canvas_item  # type: ignore[attr-defined]
        # give the item a real canvas_rect (needed for hit-testing coordinates) by laying it out
        # inside a composition, matching how it would be positioned inside a real window.
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(canvas_item)
        composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=200, h=24))
        return widget, canvas_item

    def test_text_property_round_trips_through_behavior(self) -> None:
        widget, canvas_item = self._make_line_edit()
        widget.text = "hello"
        self.assertEqual(widget.text, "hello")
        self.assertEqual(canvas_item.line_edit_core.buffer.text, "hello")

    def test_placeholder_text_round_trips(self) -> None:
        widget, canvas_item = self._make_line_edit()
        widget.placeholder_text = "enter value"
        self.assertEqual(widget.placeholder_text, "enter value")
        self.assertEqual(canvas_item.placeholder_text, "enter value")

    def test_typing_updates_text_and_fires_on_text_edited(self) -> None:
        widget, canvas_item = self._make_line_edit()
        edited_values: typing.List[str] = list()
        widget.on_text_edited = edited_values.append
        canvas_item._set_focused(True)
        for ch in "hi":
            canvas_item.key_pressed(self._key(text=ch))
        self.assertEqual(widget.text, "hi")
        self.assertEqual(edited_values, ["h", "hi"])

    def test_focus_lost_fires_editing_finished(self) -> None:
        widget, canvas_item = self._make_line_edit()
        finished_values: typing.List[str] = list()
        widget.on_editing_finished = finished_values.append
        canvas_item._set_focused(True)
        canvas_item.key_pressed(self._key(text="x"))
        canvas_item._set_focused(False)
        self.assertEqual(finished_values, ["x"])

    def test_widget_reports_focus_changes(self) -> None:
        widget, canvas_item = self._make_line_edit()
        focus_states: typing.List[bool] = list()
        widget.on_focus_changed = focus_states.append
        canvas_item._set_focused(True)
        canvas_item._set_focused(False)
        self.assertEqual(focus_states, [True, False])

    def test_return_pressed_fires_editing_finished_and_return_callback(self) -> None:
        widget, canvas_item = self._make_line_edit()
        finished_values: typing.List[str] = list()
        return_calls: typing.List[bool] = list()
        widget.on_editing_finished = finished_values.append

        def _on_return_pressed() -> bool:
            return_calls.append(True)
            return True

        widget.on_return_pressed = _on_return_pressed
        canvas_item._set_focused(True)
        canvas_item.key_pressed(self._key(text="a"))
        self.assertTrue(canvas_item.key_pressed(self._key(key="enter")))
        self.assertEqual(finished_values, ["a"])
        self.assertEqual(return_calls, [True])

    def test_escape_pressed_fires_escape_callback(self) -> None:
        widget, canvas_item = self._make_line_edit()
        escape_calls: typing.List[bool] = list()

        def _on_escape_pressed() -> bool:
            escape_calls.append(True)
            return True

        widget.on_escape_pressed = _on_escape_pressed
        canvas_item._set_focused(True)
        self.assertTrue(canvas_item.key_pressed(self._key(key="escape")))
        self.assertEqual(escape_calls, [True])

    def test_select_all_and_selected_text(self) -> None:
        widget, canvas_item = self._make_line_edit()
        widget.text = "hello"
        widget.select_all()
        self.assertEqual(widget.selected_text, "hello")

    def test_caret_not_drawn_while_there_is_a_selection(self) -> None:
        # the caret should be hidden whenever there is an active (non-empty) selection, matching
        # standard text-field UX (e.g. QLineEdit does not draw a caret over selected text).
        widget = self.ui.create_line_edit_widget()
        canvas_item = widget._behavior._canvas_item  # type: ignore[attr-defined]
        widget.text = "hello"
        canvas_item._set_focused(True)
        canvas_item.line_edit_core.caret_visible = True

        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(canvas_item)
        composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=200, h=24))

        # no selection: caret should be drawn (an extra "stroke" command beyond the cell's own
        # border stroke).
        drawing_context = DrawingContext.DrawingContext()
        composition.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=24))
        stroke_commands_without_selection = [command for command in drawing_context.commands if command[0] == "stroke"]

        # with a selection: caret should be suppressed even though caret_visible is still True --
        # only the cell's own border stroke should remain.
        widget.select_all()
        self.assertTrue(canvas_item.line_edit_core.caret_visible)
        drawing_context = DrawingContext.DrawingContext()
        composition.repaint_immediate(drawing_context, Geometry.IntSize(width=200, height=24))
        stroke_commands_with_selection = [command for command in drawing_context.commands if command[0] == "stroke"]
        self.assertEqual(len(stroke_commands_with_selection), len(stroke_commands_without_selection) - 1)

    def test_mouse_click_places_cursor_and_double_click_selects_word(self) -> None:
        widget, canvas_item = self._make_line_edit()
        widget.text = "the quick fox"
        canvas_item._set_focused(True)
        # click near the start of "quick" - since TestUI's font metrics are deterministic (not all
        # characters the same width), just verify a click moves the cursor away from its initial
        # end-of-text position, and a double click selects a non-empty word.
        initial_cursor = canvas_item.line_edit_core.buffer.cursor_position
        canvas_item.mouse_pressed(canvas_item.padding.width + 5, 5, CanvasItem.KeyboardModifiers())
        canvas_item.mouse_released(0, 0, CanvasItem.KeyboardModifiers())
        self.assertNotEqual(canvas_item.line_edit_core.buffer.cursor_position, initial_cursor)
        canvas_item.mouse_double_clicked(canvas_item.padding.width + 25, 5, CanvasItem.KeyboardModifiers())
        self.assertTrue(len(canvas_item.line_edit_core.buffer.selected_text) > 0)

    def test_double_click_then_drag_selects_whole_words(self) -> None:
        widget, canvas_item = self._make_line_edit()
        widget.text = "the quick brown fox"
        canvas_item._set_focused(True)
        padding = canvas_item.padding.width
        # double-click somewhere inside "quick", then drag into "brown" - the selection should
        # extend by whole words, not character-by-character.
        canvas_item.mouse_double_clicked(padding + 25, 5, CanvasItem.KeyboardModifiers())
        first_word = canvas_item.line_edit_core.buffer.selected_text
        canvas_item.mouse_position_changed(padding + 65, 5, CanvasItem.KeyboardModifiers())
        dragged_selection = canvas_item.line_edit_core.buffer.selected_text
        self.assertTrue(dragged_selection.startswith(first_word))
        self.assertGreater(len(dragged_selection), len(first_word))
        # a space-joined multi-word selection should not end mid-word.
        self.assertFalse(dragged_selection.endswith(" "))
        canvas_item.mouse_released(0, 0, CanvasItem.KeyboardModifiers())
        # after release, a plain drag should go back to character-wise selection.
        canvas_item.mouse_pressed(padding, 5, CanvasItem.KeyboardModifiers())
        canvas_item.mouse_position_changed(padding + 5, 5, CanvasItem.KeyboardModifiers())
        self.assertLessEqual(len(canvas_item.line_edit_core.buffer.selected_text), 2)

    def test_double_click_drag_stops_after_mouse_released_at_container_level(self) -> None:
        # regression test: this reproduces the real event path (container-level double-click
        # dispatch, not calling canvas_item.mouse_double_clicked/mouse_released directly) since a
        # double click's mouse_released has no matching mouse_pressed of its own and is only
        # delivered here because mouse_double_clicked calls grab_mouse() -- without that, the
        # word-wise drag-selection state would be left stuck active forever, even after the mouse
        # button was released.
        canvas_widget = self.test_ui.create_canvas_widget()
        self.addCleanup(canvas_widget.close)
        widget = self.ui.create_line_edit_widget()
        canvas_item = widget._behavior._canvas_item  # type: ignore[attr-defined]
        canvas_widget.canvas_item.add_canvas_item(canvas_item)
        canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=200, h=24))
        widget.text = "the quick brown fox"
        canvas_item._set_focused(True)
        padding = canvas_item.padding.width
        modifiers = CanvasItem.KeyboardModifiers()

        assert callable(canvas_widget.on_mouse_double_clicked)
        canvas_widget.on_mouse_double_clicked(padding + 25, 5, modifiers)
        first_word = canvas_item.line_edit_core.buffer.selected_text
        self.assertTrue(first_word)

        assert callable(canvas_widget.on_mouse_released)
        canvas_widget.on_mouse_released(padding + 25, 5, modifiers)

        # after the release that follows the double click, further mouse moves (with no button
        # held) must not keep extending the word-wise selection.
        assert callable(canvas_widget.on_mouse_position_changed)
        canvas_widget.on_mouse_position_changed(padding + 65, 5, modifiers)
        self.assertEqual(canvas_item.line_edit_core.buffer.selected_text, first_word)

    def test_caret_blinks_via_periodic(self) -> None:
        widget, canvas_item = self._make_line_edit()
        behavior = typing.cast(typing.Any, widget._behavior)
        canvas_item._set_focused(True)
        self.assertTrue(canvas_item.line_edit_core.caret_visible)
        behavior._LineEditWidgetBehavior__last_periodic_time -= CanvasUserInterface.TextEditing.CARET_BLINK_INTERVAL + 0.01  # type: ignore[attr-defined]
        behavior.periodic()
        self.assertFalse(canvas_item.line_edit_core.caret_visible)

    def test_not_focused_does_not_blink(self) -> None:
        widget, canvas_item = self._make_line_edit()
        behavior = typing.cast(typing.Any, widget._behavior)
        self.assertFalse(canvas_item.focused)
        behavior._LineEditWidgetBehavior__last_periodic_time -= CanvasUserInterface.TextEditing.CARET_BLINK_INTERVAL + 0.01  # type: ignore[attr-defined]
        behavior.periodic()
        # blink state should not have changed since the item never gained focus.
        self.assertTrue(canvas_item.line_edit_core.caret_visible)

    def test_line_edit_scrolls_to_keep_caret_visible_when_text_overflows_the_field(self) -> None:
        # regression test: previously LineEditCore/LineEditCell had no horizontal scroll concept
        # at all, so once typed text exceeded the field's width, the caret (and anything typed
        # after it) simply kept being positioned past the visible area with nothing bringing it
        # back into view, matching how QLineEdit scrolls its content to keep the caret visible.
        widget = self.ui.create_line_edit_widget()
        canvas_item = widget._behavior._canvas_item  # type: ignore[attr-defined]
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(canvas_item)
        width = 60
        composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=width, h=24))
        widget.text = "a very long line of text that overflows the field"
        canvas_item._set_focused(True)
        canvas_item.line_edit_core.buffer.move_to_end(False)

        drawing_context = DrawingContext.DrawingContext()
        composition.repaint_immediate(drawing_context, Geometry.IntSize(width=width, height=24))

        fill_text_commands = [command for command in drawing_context.commands if command[0] == "fillText"]
        self.assertEqual(len(fill_text_commands), 1)
        # the text must now draw scrolled left (negative x), not flush against the field's left edge.
        self.assertLess(fill_text_commands[0][2], 0.0)

        # the caret itself, however, must stay within the field's visible (padded) width.
        move_to_commands = [command for command in drawing_context.commands if command[0] == "moveTo"]
        self.assertTrue(move_to_commands)
        caret_x = move_to_commands[-1][1]
        padding = canvas_item.padding.width
        self.assertGreaterEqual(caret_x, padding - 0.01)
        self.assertLessEqual(caret_x, width - padding + 0.01)

    def test_line_edit_unfocused_shows_start_of_text_not_scrolled_position(self) -> None:
        # an unfocused field should always display from the start of its text (like QLineEdit),
        # even if it was previously scrolled while focused.
        widget = self.ui.create_line_edit_widget()
        canvas_item = widget._behavior._canvas_item  # type: ignore[attr-defined]
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(canvas_item)
        width = 60
        composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=width, h=24))
        widget.text = "a very long line of text that overflows the field"
        canvas_item._set_focused(True)
        canvas_item.line_edit_core.buffer.move_to_end(False)
        composition.repaint_immediate(DrawingContext.DrawingContext(), Geometry.IntSize(width=width, height=24))
        self.assertGreater(canvas_item.line_edit_core.scroll_x, 0.0)

        canvas_item._set_focused(False)
        drawing_context = DrawingContext.DrawingContext()
        composition.repaint_immediate(drawing_context, Geometry.IntSize(width=width, height=24))
        self.assertEqual(canvas_item.line_edit_core.scroll_x, 0.0)
        fill_text_commands = [command for command in drawing_context.commands if command[0] == "fillText"]
        self.assertEqual(len(fill_text_commands), 1)
        self.assertGreaterEqual(fill_text_commands[0][2], 0.0)


class TestTextEditCanvasIntegration(unittest.TestCase):
    """Integration tests exercising the TextEditWidget/TextEditWidgetBehavior/MultiLineEditCanvasItem
    wiring end-to-end (mouse/key/focus events flowing through to TextEditing.TextEditCore and back
    out via the on_text_changed/on_cursor_position_changed/on_selection_changed/on_escape_pressed/
    on_return_pressed callbacks), mirroring TestLineEditCanvasIntegration's structure."""

    def setUp(self) -> None:
        self.test_ui = TestUI.UserInterface()
        self.ui = CanvasUserInterface.CanvasUserInterface(self.test_ui)

    def _key(self, text: str = str(), key: str = str(), *, shift: bool = False, control: bool = False,
             alt: bool = False) -> UserInterface.Key:
        modifiers = CanvasItem.KeyboardModifiers(shift=shift, control=control, alt=alt)
        return TestUI.Key(text, key, modifiers)

    def _make_text_edit(self, width: int = 200, height: int = 100) -> typing.Tuple[UserInterface.TextEditWidget, typing.Any]:
        widget = self.ui.create_text_edit_widget()
        top_canvas_item = widget._behavior.canvas_item  # type: ignore[attr-defined]
        canvas_item = widget._behavior._content_canvas_item  # type: ignore[attr-defined]
        # give the item a real canvas_rect (needed for hit-testing coordinates) by laying it out
        # inside a composition, matching how it would be positioned inside a real window.
        composition = CanvasItem.CanvasItemComposition()
        composition.add_canvas_item(top_canvas_item)
        composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=width, h=height))
        self.__composition = composition
        return widget, canvas_item

    def _relayout(self, width: int = 200, height: int = 100) -> None:
        # word wrap/content-height sizing changes require an explicit fresh layout pass to actually
        # take effect on canvas_size (matching how a real window's next layout pass would pick up a
        # sizing change -- update_sizing() alone only marks the item for repaint, not re-layout).
        self.__composition.update_layout(Geometry.IntPoint(), Geometry.IntSize(w=width, h=height))

    def test_text_property_round_trips_through_behavior(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        self.assertEqual(widget.text, "hello world")
        self.assertEqual(canvas_item.text_edit_core.buffer.text, "hello world")

    def test_placeholder_text_round_trips(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.placeholder = "enter value"
        self.assertEqual(widget.placeholder, "enter value")
        self.assertEqual(canvas_item.placeholder_text, "enter value")

    def test_typing_incl_newlines_updates_text_and_fires_on_text_changed(self) -> None:
        widget, canvas_item = self._make_text_edit()
        changed_values: typing.List[typing.Optional[str]] = list()
        widget.on_text_changed = changed_values.append
        canvas_item._set_focused(True)
        canvas_item.key_pressed(self._key("a", "a"))
        canvas_item.key_pressed(self._key(str(), "enter"))
        canvas_item.key_pressed(self._key("b", "b"))
        self.assertEqual(canvas_item.text, "a\nb")
        self.assertEqual(changed_values, ["a", "a\n", "a\nb"])

    def test_enter_inserts_newline_rather_than_finishing_editing(self) -> None:
        # unlike LineEditCanvasItem, Enter is not intercepted here -- it's ordinary text insertion.
        widget, canvas_item = self._make_text_edit()
        canvas_item._set_focused(True)
        consumed = canvas_item.key_pressed(self._key(str(), "enter"))
        self.assertTrue(consumed)
        self.assertEqual(canvas_item.text, "\n")

    def test_select_all_and_selected_text(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        widget.select_all()
        self.assertEqual(widget.selected_text, "hello world")

    def test_cursor_position_and_selection_properties(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        widget.select_all()
        self.assertEqual(widget.cursor_position.position, len("hello world"))
        self.assertEqual(widget.selection, UserInterface.Selection(0, len("hello world")))

    def test_cursor_position_changed_and_selection_changed_callbacks_fire(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        cursor_positions: typing.List[UserInterface.CursorPosition] = list()
        selections: typing.List[UserInterface.Selection] = list()
        widget.on_cursor_position_changed = cursor_positions.append
        widget.on_selection_changed = selections.append
        canvas_item._set_focused(True)
        canvas_item.key_pressed(self._key(key="left", shift=True))
        self.assertTrue(cursor_positions)
        self.assertTrue(selections)

    def test_escape_pressed_fires_escape_callback(self) -> None:
        widget, canvas_item = self._make_text_edit()
        escape_calls = list()

        def on_escape_pressed() -> bool:
            escape_calls.append(True)
            return True

        widget.on_escape_pressed = on_escape_pressed
        canvas_item._set_focused(True)
        consumed = canvas_item.key_pressed(self._key(str(), "escape"))
        self.assertTrue(consumed)
        self.assertEqual(escape_calls, [True])

    def test_move_cursor_position(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        widget.move_cursor_position("start")
        self.assertEqual(canvas_item.text_edit_core.buffer.cursor_position, 0)
        widget.move_cursor_position("end")
        self.assertEqual(canvas_item.text_edit_core.buffer.cursor_position, len("hello world"))

    def test_append_text_and_insert_text(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello"
        widget.append_text(" world")
        self.assertEqual(widget.text, "hello world")
        widget.move_cursor_position("start")
        widget.insert_text("X")
        self.assertEqual(widget.text, "Xhello world")

    def test_remove_selected_text_and_clear_selection(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "hello world"
        widget.select_all()
        widget.remove_selected_text()
        self.assertEqual(widget.text, str())
        widget.text = "hello world"
        widget.select_all()
        widget.clear_selection()
        self.assertEqual(widget.selection.start, widget.selection.end)

    def test_word_wrap_mode_wraps_text_across_multiple_rows(self) -> None:
        widget, canvas_item = self._make_text_edit(width=100, height=100)
        widget.word_wrap_mode = "word"
        widget.text = "a long line of text that should wrap across several visual rows"
        self._relayout(width=100, height=100)
        self.assertGreater(canvas_item.text_edit_core.layout().row_count, 1)

    def test_scrolling_via_wrapped_scroll_area(self) -> None:
        widget, canvas_item = self._make_text_edit(width=200, height=40)
        widget.word_wrap_mode = "word"
        widget.text = "\n".join(f"line {i}" for i in range(20))
        # re-layout after the text change so the fixed content-height sizing takes effect.
        self._relayout(width=200, height=40)
        # content is much taller than the 40px viewport -- real scrolling should be available.
        self.assertGreater(canvas_item.canvas_size.height, 40)

    def test_mouse_click_places_cursor_and_double_click_selects_word(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "the quick brown fox"
        modifiers = CanvasItem.KeyboardModifiers()
        padding = canvas_item.padding.width
        canvas_item.mouse_pressed(padding + 5, 5, modifiers)
        self.assertGreaterEqual(canvas_item.text_edit_core.buffer.cursor_position, 0)
        canvas_item.mouse_double_clicked(padding + 25, 5, modifiers)
        self.assertTrue(canvas_item.text_edit_core.buffer.selected_text)

    def test_double_click_then_drag_selects_whole_words(self) -> None:
        widget, canvas_item = self._make_text_edit()
        widget.text = "the quick brown fox"
        modifiers = CanvasItem.KeyboardModifiers()
        padding = canvas_item.padding.width
        canvas_item.mouse_double_clicked(padding + 25, 5, modifiers)
        first_word = canvas_item.text_edit_core.buffer.selected_text
        self.assertTrue(first_word)
        canvas_item.mouse_position_changed(padding + 65, 5, modifiers)
        dragged = canvas_item.text_edit_core.buffer.selected_text
        self.assertNotEqual(dragged, first_word)
        canvas_item.mouse_released(padding + 65, 5, modifiers)

    def test_double_click_drag_stops_after_mouse_released_at_container_level(self) -> None:
        # regression test mirroring TestLineEditCanvasIntegration's equivalent: reproduces the real
        # event path (container-level double-click dispatch) since the earlier fix (recording the
        # double-clicked canvas item as "mouse grabbed" in RootCanvasItem/ThreadedCanvasItem) is
        # shared infrastructure that a fresh canvas item type should still exercise directly.
        canvas_widget = self.test_ui.create_canvas_widget()
        self.addCleanup(canvas_widget.close)
        widget = self.ui.create_text_edit_widget()
        top_canvas_item = widget._behavior.canvas_item  # type: ignore[attr-defined]
        canvas_item = widget._behavior._content_canvas_item  # type: ignore[attr-defined]
        canvas_widget.canvas_item.add_canvas_item(top_canvas_item)
        canvas_widget.canvas_item.layout_immediate(Geometry.IntSize(w=200, h=60))
        widget.text = "the quick brown fox"
        canvas_item._set_focused(True)
        padding = canvas_item.padding.width
        modifiers = CanvasItem.KeyboardModifiers()

        assert callable(canvas_widget.on_mouse_double_clicked)
        canvas_widget.on_mouse_double_clicked(padding + 25, 5, modifiers)
        first_word = canvas_item.text_edit_core.buffer.selected_text
        self.assertTrue(first_word)

        assert callable(canvas_widget.on_mouse_released)
        canvas_widget.on_mouse_released(padding + 25, 5, modifiers)

        assert callable(canvas_widget.on_mouse_position_changed)
        canvas_widget.on_mouse_position_changed(padding + 65, 5, modifiers)
        self.assertEqual(canvas_item.text_edit_core.buffer.selected_text, first_word)

    def test_caret_blinks_via_periodic(self) -> None:
        widget, canvas_item = self._make_text_edit()
        behavior = typing.cast(typing.Any, widget._behavior)
        canvas_item._set_focused(True)
        self.assertTrue(canvas_item.text_edit_core.caret_visible)
        behavior._TextEditWidgetBehavior__last_periodic_time -= CanvasUserInterface.TextEditing.CARET_BLINK_INTERVAL + 0.01  # type: ignore[attr-defined]
        behavior.periodic()
        self.assertFalse(canvas_item.text_edit_core.caret_visible)

    def test_not_focused_does_not_blink(self) -> None:
        widget, canvas_item = self._make_text_edit()
        behavior = typing.cast(typing.Any, widget._behavior)
        self.assertFalse(canvas_item.focused)
        behavior._TextEditWidgetBehavior__last_periodic_time -= CanvasUserInterface.TextEditing.CARET_BLINK_INTERVAL + 0.01  # type: ignore[attr-defined]
        behavior.periodic()
        self.assertTrue(canvas_item.text_edit_core.caret_visible)


class TestSplitterWidgetCanvas(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())

    def tearDown(self) -> None:
        pass

    def __make_splitter(self, orientation: typing.Optional[str]) -> typing.Tuple[UserInterface.SplitterWidget, CanvasItem.SplitterCanvasItem]:
        widget = self.ui.create_splitter_widget(orientation)
        widget.add(self.ui.create_label_widget("A"))
        widget.add(self.ui.create_label_widget("B"))
        canvas_item = typing.cast(CanvasItem.SplitterCanvasItem, CanvasUserInterface.extract_canvas_item(widget))
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=200))
        return widget, canvas_item

    def test_horizontal_splitter_arranges_children_side_by_side(self) -> None:
        # at the user interface level "horizontal" means the children are arranged left to right. the canvas item
        # uses the opposite convention, so this also covers the translation between them.
        widget, canvas_item = self.__make_splitter("horizontal")
        rects = [child.canvas_rect or Geometry.IntRect.empty_rect() for child in canvas_item.canvas_items]
        self.assertEqual(2, len(rects))
        self.assertEqual(Geometry.IntPoint(x=0, y=0), rects[0].origin)
        self.assertEqual(Geometry.IntPoint(x=200, y=0), rects[1].origin)
        self.assertEqual(200, rects[0].height)

    def test_vertical_splitter_arranges_children_top_to_bottom(self) -> None:
        widget, canvas_item = self.__make_splitter("vertical")
        rects = [child.canvas_rect or Geometry.IntRect.empty_rect() for child in canvas_item.canvas_items]
        self.assertEqual(Geometry.IntPoint(x=0, y=0), rects[0].origin)
        self.assertEqual(Geometry.IntPoint(x=0, y=100), rects[1].origin)
        self.assertEqual(400, rects[0].width)

    def test_default_splitter_orientation_stacks_children(self) -> None:
        # the user interface splitter defaults to "vertical", so an unspecified orientation stacks the children.
        widget, canvas_item = self.__make_splitter(None)
        rects = [child.canvas_rect or Geometry.IntRect.empty_rect() for child in canvas_item.canvas_items]
        self.assertEqual(Geometry.IntPoint(x=0, y=100), rects[1].origin)

    def test_changing_splitter_orientation_is_rejected(self) -> None:
        widget, canvas_item = self.__make_splitter("horizontal")
        # setting the same orientation is allowed, since SplitterWidget does this during construction.
        widget.orientation = "horizontal"
        with self.assertRaises(NotImplementedError):
            widget.orientation = "vertical"

    def test_set_sizes_converts_pixel_sizes_to_splits(self) -> None:
        widget, canvas_item = self.__make_splitter("horizontal")
        widget.set_sizes([300, 100])
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=200))
        rects = [child.canvas_rect or Geometry.IntRect.empty_rect() for child in canvas_item.canvas_items]
        self.assertEqual(300, rects[0].width)
        self.assertEqual(100, rects[1].width)


class RecordingUserInterface(TestUI.UserInterface):
    """A user interface which records the parent it is asked to create each window under."""

    def __init__(self) -> None:
        super().__init__()
        self.window_parents: typing.List[typing.Optional[UserInterface.Window]] = list()

    def create_document_window(self, title: typing.Optional[str] = None,
                               parent_window: typing.Optional[UserInterface.Window] = None) -> UserInterface.Window:
        self.window_parents.append(parent_window)
        return super().create_document_window(title, parent_window)


class TestCanvasWindowClass(unittest.TestCase):

    def setUp(self) -> None:
        # a window takes the current event loop when it is created.
        self.__event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.__event_loop)

    def tearDown(self) -> None:
        self.__event_loop.stop()
        self.__event_loop.run_forever()
        self.__event_loop.close()

    def test_closing_a_child_window_runs_its_close_handling(self) -> None:
        # the host closes the window a canvas window wraps; the canvas window has to pass that along, or the window
        # displaying it is never told that it closed and its completion never runs.
        ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
        window = Window.Window(ui)
        with contextlib.closing(window):
            results: typing.List[bool] = list()
            Dialog.pose_confirmation_popup(results.append, window=window, title="Confirm")
            window._dialogs[0].request_close()
            window.periodic()
            self.assertEqual([False], results)
            self.assertEqual(0, len(window._dialogs))

    def test_widget_reports_where_it_is_on_the_screen(self) -> None:
        # a menu popped up beside a widget has to know where the widget is. the content of a canvas window is drawn
        # within a single widget of the host, so a widget maps its position through the canvas item displaying it.
        ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
        window = Window.Window(ui)
        with contextlib.closing(window):
            column = ui.create_column_widget()
            column.add_spacing(40)
            row = ui.create_row_widget()
            row.add_spacing(30)
            button = ui.create_push_button_widget("Push")
            row.add(button)
            row.add_stretch()
            column.add(row)
            column.add_stretch()
            window.attach_widget(column)
            canvas_item = CanvasUserInterface.extract_canvas_item(column)
            assert canvas_item
            canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=300, height=120))
            self.assertEqual(Geometry.IntPoint(x=30, y=40), button.map_to_global(Geometry.IntPoint()))

    def test_context_menu_is_created_for_the_window_of_the_host(self) -> None:
        # a canvas window wraps a window of the host user interface, which knows nothing about canvas windows, so a
        # context menu, like a child window, must be made for the wrapped window rather than for the canvas window.
        ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
        window = Window.Window(ui)
        with contextlib.closing(window):
            menu = window.create_context_menu()
            document_window = typing.cast(CanvasUserInterface.CanvasWindow, window._document_window)
            self.assertEqual(document_window._root_window, menu.document_window)

    def test_child_window_is_created_under_the_window_of_the_host(self) -> None:
        # a canvas window wraps a window of the host user interface, which knows nothing about canvas windows, so a
        # child window must be created under the wrapped window rather than under the canvas window itself.
        host_ui = RecordingUserInterface()
        ui = CanvasUserInterface.CanvasUserInterface(host_ui)
        parent_window = Window.Window(ui)
        with contextlib.closing(parent_window):
            child_window = Window.Window(ui, parent_window=parent_window)
            with contextlib.closing(child_window):
                parent_document_window = typing.cast(CanvasUserInterface.CanvasWindow, parent_window._document_window)
                self.assertEqual([None, parent_document_window._root_window], host_ui.window_parents)


class TestCanvasWidgetFocus(unittest.TestCase):
    """The canvas backend draws a whole window in one hierarchy of canvas items, so a widget in it is one or more
    canvas items rather than something with a focus of its own. These tests cover which of them takes the focus:
    the boundary a canvas widget draws around its content, and the item a widget of several of them is focused by."""

    def setUp(self) -> None:
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.host_ui = TestUI.UserInterface()
        self.ui = CanvasUserInterface.CanvasUserInterface(self.host_ui)

    def tearDown(self) -> None:
        self.event_loop.stop()
        self.event_loop.run_forever()
        self.event_loop.close()

    def _make_window(self, content: UserInterface.Widget) -> typing.Tuple[CanvasUserInterface.CanvasWindow, UserInterface.CanvasWidget]:
        # the canvas window wraps a window of the host user interface, so it is built on the host ui; rooting it in
        # a canvas widget of the canvas ui would nest the content in a second hierarchy which nothing drives.
        window = CanvasUserInterface.CanvasWindow(self.host_ui, "test")
        window._attach_root_widget(content)
        window.show()
        host_canvas_widget = typing.cast(UserInterface.CanvasWidget, window._CanvasWindow__canvas_widget)  # type: ignore[attr-defined]
        host_canvas_widget.focused = True
        return window, host_canvas_widget

    def _send_key(self, host_canvas_widget: UserInterface.CanvasWidget, key_name: str, *, text: str = str()) -> bool:
        on_key_pressed = host_canvas_widget.on_key_pressed
        assert callable(on_key_pressed)
        shift = key_name == "backtab"
        return on_key_pressed(TestUI.Key(text, key_name, CanvasItem.KeyboardModifiers(shift=shift)))

    def _make_canvas_widget(self, focusable: bool) -> typing.Tuple[UserInterface.CanvasWidget, CanvasItem.AbstractCanvasItem]:
        canvas_widget = self.ui.create_canvas_widget()
        canvas_widget.focusable = focusable
        content_item = CanvasItem.CanvasItemComposition()
        content_item.focusable = True
        canvas_widget.canvas_item.add_canvas_item(content_item)
        return canvas_widget, content_item

    def test_tab_walks_the_widgets_of_a_window_in_order_and_comes_back_around(self) -> None:
        # the whole window is drawn in one widget of the host, so the focus has nothing outside to move on to when
        # it reaches the last widget: it returns to the first one.
        column = self.ui.create_column_widget()
        first_line_edit = self.ui.create_line_edit_widget()
        second_line_edit = self.ui.create_line_edit_widget()
        column.add(first_line_edit)
        column.add(second_line_edit)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(first_line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(second_line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(first_line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "backtab"))
            self.assertTrue(second_line_edit.focused)

    def test_tab_stops_at_a_canvas_widget_which_can_take_the_focus(self) -> None:
        # the canvas items drawn in a canvas widget are reached through that widget, so a widget which can take the
        # focus puts its content into the walk.
        column = self.ui.create_column_widget()
        line_edit = self.ui.create_line_edit_widget()
        canvas_widget, content_item = self._make_canvas_widget(focusable=True)
        column.add(line_edit)
        column.add(canvas_widget)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(content_item.focused)
            self.assertTrue(canvas_widget.focused)

    def test_tab_skips_the_content_of_a_canvas_widget_which_cannot_take_the_focus(self) -> None:
        # a widget which cannot take the focus cannot hold it on behalf of its content either, so the walk passes
        # over everything drawn in it rather than focusing an item the user could never tab to.
        column = self.ui.create_column_widget()
        line_edit = self.ui.create_line_edit_widget()
        canvas_widget, content_item = self._make_canvas_widget(focusable=False)
        column.add(line_edit)
        column.add(canvas_widget)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertFalse(content_item.focused)
            self.assertTrue(line_edit.focused)
            # and it cannot be given the focus by asking for it either.
            canvas_widget.focused = True
            self.assertFalse(content_item.focused)

    def test_a_canvas_widget_gives_up_the_focus_of_the_item_holding_it(self) -> None:
        # the widget holds the focus on behalf of the item drawn in it, so giving up the widget's focus has to take
        # the focus off that item; leaving it focused would send the keys to an item nothing has the focus for.
        column = self.ui.create_column_widget()
        canvas_widget, content_item = self._make_canvas_widget(focusable=True)
        column.add(canvas_widget)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(content_item.focused)
            self.assertTrue(canvas_widget.focused)
            canvas_widget.focused = False
            self.assertFalse(content_item.focused)
            self.assertFalse(canvas_widget.focused)

    def test_a_push_button_takes_the_focus_and_reports_it(self) -> None:
        # a push button is drawn by several canvas items -- an icon and a text -- but takes the focus as one, so
        # that it can be reached by the keyboard and say so.
        column = self.ui.create_column_widget()
        line_edit = self.ui.create_line_edit_widget()
        push_button = self.ui.create_push_button_widget("Press")
        focus_changes: typing.List[bool] = list()
        push_button.on_focus_changed = focus_changes.append
        column.add(line_edit)
        column.add(push_button)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(push_button.focused)
            self.assertEqual([True], focus_changes)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertFalse(push_button.focused)
            self.assertEqual([True, False], focus_changes)

    def test_the_space_bar_and_return_press_the_focused_push_button(self) -> None:
        # a button which has the focus is pressed by the keyboard, the way clicking it presses it.
        column = self.ui.create_column_widget()
        push_button = self.ui.create_push_button_widget("Press")
        clicked_count = 0

        def handle_clicked() -> None:
            nonlocal clicked_count
            clicked_count += 1

        push_button.on_clicked = handle_clicked
        column.add(push_button)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(push_button.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "space", text=" "))
            self.assertEqual(1, clicked_count)
            self.assertTrue(self._send_key(host_canvas_widget, "return"))
            self.assertEqual(2, clicked_count)

    def test_the_space_bar_toggles_the_focused_check_box(self) -> None:
        # a check box which has the focus is toggled by the keyboard, the way clicking it toggles it.
        column = self.ui.create_column_widget()
        check_box = self.ui.create_check_box_widget("Check")
        check_states: typing.List[str] = list()
        check_box.on_check_state_changed = check_states.append
        column.add(check_box)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(check_box.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "space", text=" "))
            self.assertEqual("checked", check_box.check_state)
            self.assertTrue(self._send_key(host_canvas_widget, "space", text=" "))
            self.assertEqual("unchecked", check_box.check_state)
            self.assertEqual(["checked", "unchecked"], check_states)

    def test_the_space_bar_chooses_the_focused_radio_button(self) -> None:
        # a radio button which has the focus is chosen by the keyboard, and choosing one drops the other.
        column = self.ui.create_column_widget()
        first_radio_button = self.ui.create_radio_button_widget("First")
        second_radio_button = self.ui.create_radio_button_widget("Second")
        first_radio_button.value = 1
        second_radio_button.value = 2
        binding_model = Model.PropertyModel(1)
        first_radio_button.bind_group_value(Binding.PropertyBinding(binding_model, "value"))
        second_radio_button.bind_group_value(Binding.PropertyBinding(binding_model, "value"))
        column.add(first_radio_button)
        column.add(second_radio_button)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(first_radio_button.checked)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(second_radio_button.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "space", text=" "))
            self.assertEqual(2, binding_model.value)
            self.assertTrue(second_radio_button.checked)
            self.assertFalse(first_radio_button.checked)

    def test_the_list_view_takes_its_place_in_the_walk_and_gives_up_the_focus(self) -> None:
        # the list view draws its rows in a canvas widget of its own, which is the case the boundary exists for.
        column = self.ui.create_column_widget()
        line_edit = self.ui.create_line_edit_widget()
        list_widget = Widgets.StringListViewWidget(self.ui, items=["a", "b"], item_height=20)
        column.add(line_edit)
        column.add(list_widget)
        window, host_canvas_widget = self._make_window(column)
        with contextlib.closing(window):
            self.assertTrue(line_edit.focused)
            self.assertTrue(self._send_key(host_canvas_widget, "tab"))
            self.assertTrue(list_widget.focused)
            self.assertFalse(line_edit.focused)
            list_widget.focused = False
            self.assertFalse(list_widget.focused)


if __name__ == '__main__':
    unittest.main()
