# standard libraries
import contextlib
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets


class PeriodicCountingWidget(UserInterface.Widget):
    """A widget which counts the calls to its periodic, standing in for a subclass which overrides periodic."""

    def __init__(self, *, is_registered: bool = True) -> None:
        super().__init__(TestUI.WidgetBehavior("periodic_counting", None))
        self.periodic_count = 0
        if is_registered:
            self.register_periodic()

    def periodic(self) -> None:
        super().periodic()
        self.periodic_count += 1


class EqualPeriodicCountingWidget(PeriodicCountingWidget):
    """A periodic counting widget which compares equal to every other and so cannot be hashed."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EqualPeriodicCountingWidget)

    __hash__ = None  # type: ignore[assignment]


class TestUserInterfacePeriodicClass(unittest.TestCase):

    def test_canvas_widget_nested_within_containers_receives_window_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            row = ui.create_row_widget()
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            row.add(canvas_widget)
            column.add(row)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_added_after_attaching_receives_window_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            window.attach(column)
            row = ui.create_row_widget()
            column.add(row)
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            row.add(canvas_widget)
            window._handle_periodic()
            self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_in_dock_widget_receives_dock_widget_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            column.add(canvas_widget)
            dock_widget = window.create_dock_widget(column, "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                dock_widget.periodic()
                self.assertEqual(1, len(periodic_calls))
                # the window does not deliver periodic to what is in its dock widgets; the dock widget does.
                window._handle_periodic()
                self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_removed_from_its_container_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            stack = ui.create_stack_widget()
            canvas_widget = ui.create_canvas_widget()
            with contextlib.closing(canvas_widget):
                periodic_calls = list[bool]()
                canvas_widget.on_periodic = lambda: periodic_calls.append(True)
                stack.add(canvas_widget)
                window.attach(stack)
                window._handle_periodic()
                # removing from a stack widget does not close the removed widget, so it is closed here instead.
                stack.remove(canvas_widget)
                window._handle_periodic()
                self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_closed_by_the_periodic_of_another_is_skipped(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            first_canvas_widget = ui.create_canvas_widget()
            second_canvas_widget = ui.create_canvas_widget()
            second_periodic_calls = list[bool]()
            first_canvas_widget.on_periodic = lambda: column.remove(second_canvas_widget)
            second_canvas_widget.on_periodic = lambda: second_periodic_calls.append(True)
            column.add(first_canvas_widget)
            column.add(second_canvas_widget)
            # a dock widget does not catch exceptions, so calling periodic on the closed widget would raise here.
            dock_widget = window.create_dock_widget(column, "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                dock_widget.periodic()
                self.assertEqual(0, len(second_periodic_calls))

    def test_widget_registered_for_periodic_follows_it_to_another_window(self) -> None:
        ui = TestUI.UserInterface()
        first_window = TestUI.DocumentWindow()
        second_window = TestUI.DocumentWindow()
        with contextlib.closing(first_window), contextlib.closing(second_window):
            first_stack = ui.create_stack_widget()
            second_stack = ui.create_stack_widget()
            first_window.attach(first_stack)
            second_window.attach(second_stack)
            widget = PeriodicCountingWidget()
            first_stack.add(widget)
            first_window._handle_periodic()
            self.assertEqual(1, widget.periodic_count)
            first_stack.remove(widget)
            second_stack.add(widget)
            first_window._handle_periodic()
            self.assertEqual(1, widget.periodic_count)
            second_window._handle_periodic()
            self.assertEqual(2, widget.periodic_count)

    def test_canvas_widget_in_replaced_scroll_area_content_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            scroll_area = ui.create_scroll_area_widget()
            window.attach(scroll_area)
            old_content = ui.create_canvas_widget()
            # replacing the content of a scroll area does not close the replaced content, so it is closed here instead.
            with contextlib.closing(old_content):
                old_periodic_calls = list[bool]()
                old_content.on_periodic = lambda: old_periodic_calls.append(True)
                scroll_area.content = old_content
                window._handle_periodic()
                scroll_area.content = ui.create_canvas_widget()
                window._handle_periodic()
                self.assertEqual(1, len(old_periodic_calls))

    def test_canvas_widget_in_replaced_root_widget_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            old_root_widget = ui.create_canvas_widget()
            # attaching a new root widget does not close the replaced one, so it is closed here instead.
            with contextlib.closing(old_root_widget):
                old_periodic_calls = list[bool]()
                old_root_widget.on_periodic = lambda: old_periodic_calls.append(True)
                window.attach(old_root_widget)
                window._handle_periodic()
                window.attach(ui.create_canvas_widget())
                window._handle_periodic()
                self.assertEqual(1, len(old_periodic_calls))

    def test_widget_overriding_periodic_without_registering_is_not_called_by_window_periodic(self) -> None:
        # the window calls only what registers, rather than walking its widget tree.
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            widget = PeriodicCountingWidget(is_registered=False)
            column.add(widget)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(0, widget.periodic_count)

    def test_registered_widget_within_each_kind_of_registered_container_receives_periodic_once(self) -> None:
        # a registered container must not also deliver periodic to what it contains, or that is called twice.
        ui = TestUI.UserInterface()

        def make_box(child: UserInterface.Widget) -> UserInterface.Widget:
            box = ui.create_column_widget()
            box.add(child)
            return box

        def make_splitter(child: UserInterface.Widget) -> UserInterface.Widget:
            splitter = ui.create_splitter_widget()
            splitter.add(child)
            return splitter

        def make_tab(child: UserInterface.Widget) -> UserInterface.Widget:
            tab = ui.create_tab_widget()
            tab.add(child, "Tab")
            return tab

        def make_stack(child: UserInterface.Widget) -> UserInterface.Widget:
            stack = ui.create_stack_widget()
            stack.add(child)
            return stack

        def make_group(child: UserInterface.Widget) -> UserInterface.Widget:
            group = ui.create_group_widget()
            group.add(child)
            return group

        def make_scroll_area(child: UserInterface.Widget) -> UserInterface.Widget:
            scroll_area = ui.create_scroll_area_widget()
            scroll_area.content = child
            return scroll_area

        def make_composite(child: UserInterface.Widget) -> UserInterface.Widget:
            return Widgets.CompositeWidgetBase(child)

        container_makers: typing.Mapping[str, typing.Callable[[UserInterface.Widget], UserInterface.Widget]] = {
            "box": make_box,
            "splitter": make_splitter,
            "tab": make_tab,
            "stack": make_stack,
            "group": make_group,
            "scroll_area": make_scroll_area,
            "composite": make_composite,
        }
        for container_name, make_container in container_makers.items():
            with self.subTest(container=container_name):
                window = TestUI.DocumentWindow()
                with contextlib.closing(window):
                    widget = PeriodicCountingWidget()
                    container = make_container(widget)
                    container.register_periodic()
                    window.attach(container)
                    window._handle_periodic()
                    self.assertEqual(1, widget.periodic_count)

    def test_registered_widgets_which_compare_equal_each_receive_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            first_widget = EqualPeriodicCountingWidget()
            second_widget = EqualPeriodicCountingWidget()
            column.add(first_widget)
            column.add(second_widget)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(1, first_widget.periodic_count)
            self.assertEqual(1, second_widget.periodic_count)


if __name__ == '__main__':
    unittest.main()
