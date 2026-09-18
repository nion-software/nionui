# standard libraries
import asyncio
import contextlib
import typing
import unittest

# local libraries
from nion.ui import Application
from nion.ui import CanvasItem
from nion.ui import CanvasUserInterface
from nion.ui import Declarative
from nion.ui import Dialog
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Geometry


@contextlib.contextmanager
def window_context(*, canvas: bool = False) -> typing.Iterator[Window.Window]:
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    ui: UserInterface.UserInterface = TestUI.UserInterface()
    if canvas:
        # the canvas user interface is used when the test measures what was laid out.
        ui = CanvasUserInterface.CanvasUserInterface(ui)
    window = Window.Window(ui)
    yield window
    window._close_dialogs()
    window.periodic()
    window.close()
    event_loop.stop()
    event_loop.run_forever()
    event_loop.close()


def find_widget(widget: typing.Optional[UserInterface.Widget], widget_class: typing.Type[typing.Any]) -> typing.Any:
    """Return the first widget of the given class in the widget hierarchy."""
    if isinstance(widget, widget_class):
        return widget
    for child in getattr(widget, "_contained_widgets", list()) or list():
        found_widget = find_widget(child, widget_class)
        if found_widget:
            return found_widget
    return None


def click(button: UserInterface.PushButtonWidget) -> None:
    """Click a push button by way of its callback."""
    on_clicked = button.on_clicked
    assert on_clicked
    on_clicked()


def find_buttons(widget: typing.Optional[UserInterface.Widget]) -> typing.List[UserInterface.PushButtonWidget]:
    """Return the push buttons in the widget hierarchy, in order."""
    buttons: typing.List[UserInterface.PushButtonWidget] = list()
    if isinstance(widget, UserInterface.PushButtonWidget):
        buttons.append(widget)
    for child in getattr(widget, "_contained_widgets", list()) or list():
        buttons.extend(find_buttons(child))
    return buttons


class TestSelectItemPopupClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def __pose_popup(self, window: Window.Window, items: typing.Sequence[typing.Any],
                     selected_items: typing.List[typing.Any], **kwargs: typing.Any) -> typing.Tuple[typing.Any, typing.Any]:
        Dialog.pose_select_item_popup(items, selected_items.append, window=window, **kwargs)
        popup = window._dialogs[0]
        return popup, find_widget(getattr(popup, "widget", None), Widgets.StringListViewWidget)

    def test_select_item_popup_displays_an_item_per_row(self) -> None:
        # the popup shows the items as rows of text, using the item getter when one is given.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, [("a", 1), ("b", 2)], selected_items,
                                                 item_getter=lambda item: typing.cast(str, item[0]).upper())
            self.assertEqual(["A", "B"], [typing.cast(CanvasItem.TextCanvasItem, row._canvas_item).text
                                          for row in item_list._list_canvas_item._grid_flow_item_canvas_items])

    def test_select_item_popup_completes_with_the_chosen_item(self) -> None:
        # choosing a row and pressing the select button completes with that item.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b", "c"], selected_items)
            list_canvas_item = item_list._list_canvas_item
            list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=120))
            list_canvas_item.simulate_click(Geometry.IntPoint(y=30, x=10))
            click(find_buttons(getattr(popup, "widget", None))[-1])
            window.periodic()
            self.assertEqual(["b"], selected_items)

    def test_select_item_popup_completes_with_the_item_chosen_by_return(self) -> None:
        # pressing return in the list chooses the current item, without touching the buttons.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b", "c"], selected_items, current_item=2)
            list_canvas_item = item_list._list_canvas_item
            list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=120))
            list_canvas_item.key_pressed(typing.cast(TestUI.UserInterface, window.ui).create_key_by_id("return"))
            window.periodic()
            self.assertEqual(["c"], selected_items)

    def test_select_item_popup_completes_with_nothing_when_cancelled(self) -> None:
        # cancelling completes with nothing, so that the caller can tell the difference.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b", "c"], selected_items)
            click(find_buttons(getattr(popup, "widget", None))[0])
            window.periodic()
            self.assertEqual([None], selected_items)

    def test_select_item_popup_with_no_items(self) -> None:
        # a popup with nothing to choose from opens, and choosing completes with nothing.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, list(), selected_items)
            self.assertEqual(0, len(item_list._list_canvas_item._grid_flow_item_canvas_items))
            click(find_buttons(getattr(popup, "widget", None))[-1])
            window.periodic()
            self.assertEqual([None], selected_items)

    def test_select_item_popup_with_a_current_item_past_the_end(self) -> None:
        # a current item outside the items is no selection, and choosing completes with nothing rather than failing.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b"], selected_items, current_item=5)
            self.assertEqual(set(), item_list.selection.indexes)
            click(find_buttons(getattr(popup, "widget", None))[-1])
            window.periodic()
            self.assertEqual([None], selected_items)

    def test_select_item_popup_with_a_negative_current_item(self) -> None:
        # a negative current item is outside the items too; it does not choose from the end of the list.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b"], selected_items, current_item=-1)
            self.assertEqual(set(), item_list.selection.indexes)
            click(find_buttons(getattr(popup, "widget", None))[-1])
            window.periodic()
            self.assertEqual([None], selected_items)

    def test_select_item_popup_list_spans_the_width_of_the_popup(self) -> None:
        # the list and the buttons beneath it line up on the right. the list is given a width for its items, which
        # must not leave it narrower than the popup with the buttons stretched across the full width beside it.
        with window_context(canvas=True) as window:
            selected_items: typing.List[typing.Any] = list()
            popup, item_list = self.__pose_popup(window, ["a", "b", "c"], selected_items)
            content_widget = typing.cast(UserInterface.Widget, getattr(popup, "widget", None))
            content_canvas_item = CanvasUserInterface.extract_canvas_item(content_widget)
            assert content_canvas_item
            content_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=220))

            def right_edge(widget: typing.Any) -> int:
                canvas_item = CanvasUserInterface.extract_canvas_item(typing.cast(UserInterface.Widget, widget))
                assert canvas_item and canvas_item.canvas_rect
                return canvas_item.map_to_base_container(Geometry.IntPoint(x=canvas_item.canvas_rect.width, y=0)).x

            self.assertEqual(right_edge(find_buttons(getattr(popup, "widget", None))[-1]), right_edge(item_list))

    def test_select_item_popup_is_as_wide_as_its_items(self) -> None:
        # the popup is sized to its content rather than to a fixed width, within the limits the item width is clamped
        # to. a caller which asks for a size gets that size.
        with window_context() as window:
            selected_items: typing.List[typing.Any] = list()
            self.__pose_popup(window, ["a", "b"], selected_items)
            narrow_width = window._dialogs[0]._document_window.size.width
            self.__pose_popup(window, ["a considerably longer item string for this popup"], selected_items)
            wide_width = window._dialogs[1]._document_window.size.width
            self.assertLess(narrow_width, wide_width)
            # a popup of short items is narrower than the fixed width it used to have.
            self.assertLess(narrow_width, 400)
            Dialog.pose_select_item_popup(["a"], selected_items.append, window=window,
                                          size=Geometry.IntSize(width=333, height=222))
            self.assertEqual(333, window._dialogs[2]._document_window.size.width)


    def test_edit_string_popup_field_spans_the_popup_and_takes_key_strokes(self) -> None:
        # the field fills the popup rather than sitting at its own width, and it has the keyboard focus when the
        # popup opens, so that typing goes into it.
        with window_context(canvas=True) as window:
            edited: typing.List[typing.Optional[str]] = list()
            Dialog.pose_edit_string_popup("hello", edited.append, window=window, title="Edit")
            popup = window._dialogs[0]
            content_widget = typing.cast(UserInterface.Widget, getattr(popup, "widget", None))
            line_edit = find_widget(content_widget, UserInterface.LineEditWidget)
            content_canvas_item = CanvasUserInterface.extract_canvas_item(content_widget)
            line_edit_canvas_item = CanvasUserInterface.extract_canvas_item(line_edit)
            assert content_canvas_item and line_edit_canvas_item
            content_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=120))
            content_size = content_canvas_item.canvas_size
            line_edit_rect = line_edit_canvas_item.canvas_rect
            assert content_size and line_edit_rect
            # the field spans the popup apart from the margins on either side of it.
            self.assertGreater(line_edit_rect.width, content_size.width - 32)

            # the text is selected and the field is focused, so typing replaces it.
            root_canvas_item = typing.cast(CanvasItem.CanvasWidgetCanvasItem, line_edit_canvas_item._base_container)
            assert root_canvas_item
            self.assertTrue(line_edit_canvas_item.focused)
            on_key_pressed = root_canvas_item.canvas_widget.on_key_pressed
            assert on_key_pressed
            on_key_pressed(TestUI.Key("X", "X", CanvasItem.KeyboardModifiers()))
            self.assertEqual("X", line_edit.text)


class QuitCountingUserInterface(TestUI.UserInterface):
    """A user interface which counts the requests to quit rather than quitting."""

    def __init__(self) -> None:
        super().__init__()
        self.quit_count = 0

    def request_quit(self) -> None:
        self.quit_count += 1


@contextlib.contextmanager
def application_context() -> typing.Iterator[typing.Tuple[Application.BaseApplication, Declarative.WindowHandler]]:
    """Run an application with a single declarative window, the way an application is usually started."""
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    u = Declarative.DeclarativeUI()
    app = Application.BaseApplication(QuitCountingUserInterface())
    app.initialize()
    handler = Declarative.WindowHandler()
    handler.run(u.create_window(u.create_column(u.create_label(text="main")), title="Main"), app=app)
    yield app, handler
    app.deinitialize()
    event_loop.stop()
    event_loop.run_forever()
    event_loop.close()


class TestApplicationWindowsClass(unittest.TestCase):

    def test_closing_a_dialog_does_not_quit_the_application(self) -> None:
        # the window the dialog is posed on keeps the application running, so closing the dialog leaves it running.
        with application_context() as (app, handler):
            Dialog.pose_confirmation_popup(lambda confirmed: None, window=handler.window, title="Confirm")
            handler.window._dialogs[0].request_close()
            handler.window.periodic()
            self.assertEqual(0, typing.cast(QuitCountingUserInterface, app.ui).quit_count)

    def test_closing_the_last_window_quits_the_application(self) -> None:
        # with no windows left, the application is asked to quit.
        with application_context() as (app, handler):
            handler.window.request_close()
            self.assertEqual(1, typing.cast(QuitCountingUserInterface, app.ui).quit_count)


if __name__ == '__main__':
    unittest.main()
