# standard libraries
import asyncio
import contextlib
import typing
import unittest

# local libraries
from nion.ui import CanvasItem
from nion.ui import Dialog
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Geometry


@contextlib.contextmanager
def window_context() -> typing.Iterator[Window.Window]:
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    window = Window.Window(TestUI.UserInterface())
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


if __name__ == '__main__':
    unittest.main()
