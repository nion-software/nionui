# standard libraries
import contextlib
import typing
import unittest

# local libraries
from nion.ui import Application
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Window


@contextlib.contextmanager
def window_context() -> typing.Iterator[Window.Window]:
    """Run a window in an application, which an action needs for its context."""
    app = Application.BaseApplication(TestUI.UserInterface())
    app.initialize()
    window = Window.Window(app.ui, app=app)
    try:
        yield window
    finally:
        window.periodic()
        window.close()
        app.deinitialize()


class TestWindowActionsClass(unittest.TestCase):

    def test_unregistered_action_is_no_longer_available(self) -> None:
        # a plug-in removes the actions it registered when it is unloaded, so that menus built afterwards leave them out.
        class UnregisterTestAction(Window.Action):
            action_id = "window_test.unregister"
            action_name = "Unregister Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        action = UnregisterTestAction()
        Window.register_action(action)
        try:
            self.assertIs(action, Window.actions.get("window_test.unregister"), "a registered action is not available")
        finally:
            Window.unregister_action("window_test.unregister")
        self.assertNotIn("window_test.unregister", Window.actions, "an unregistered action is still available")

    def test_main_menu_command_is_recorded_as_coming_from_the_menu(self) -> None:
        invoked_from_list: list[Window.ActionOrigin | None] = list()

        class MainMenuTestAction(Window.Action):
            action_id = "window_test.main_menu"
            action_name = "Main Menu Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append(context.invoked_from)
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(MainMenuTestAction())
        self.addCleanup(Window.unregister_action, "window_test.main_menu")
        with window_context() as window:
            window.build_menu(None, [{"type": "menu", "menu_id": "window_test", "title": "Test", "items": [{"type": "item", "action_id": "window_test.main_menu"}]}])
            # build_menu publishes each top level menu as an attribute named after its menu id.
            menu = typing.cast(UserInterface.Menu, getattr(window, "_window_test_menu"))
            menu_action = menu.items[0].action
            assert menu_action
            menu_action.trigger()
            self.assertEqual([Window.ActionOrigin.MENU], invoked_from_list, "a main-menu command is not recorded as coming from the main menu")

    def test_context_menu_command_is_recorded_as_coming_from_a_context_menu(self) -> None:
        invoked_from_list: list[Window.ActionOrigin | None] = list()

        class ContextMenuTestAction(Window.Action):
            action_id = "window_test.context_menu"
            action_name = "Context Menu Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append(context.invoked_from)
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(ContextMenuTestAction())
        self.addCleanup(Window.unregister_action, "window_test.context_menu")
        with window_context() as window:
            assert window.app
            context_menu = window.create_context_menu()
            window.add_action_to_menu(context_menu, "window_test.context_menu", Window.ActionContext(window.app, window, None))
            menu_action = context_menu.items[0].action
            assert menu_action
            menu_action.trigger()
            # the context menu item queues its action to run once the menu has closed.
            window.periodic()
            self.assertEqual([Window.ActionOrigin.CONTEXT_MENU], invoked_from_list, "a context-menu command is not recorded as coming from a context menu")

    def test_context_menu_command_leaves_the_menu_context_without_an_origin(self) -> None:
        class ContextMenuContextTestAction(Window.Action):
            action_id = "window_test.context_menu_context"
            action_name = "Context Menu Context Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(ContextMenuContextTestAction())
        self.addCleanup(Window.unregister_action, "window_test.context_menu_context")
        with window_context() as window:
            assert window.app
            action_context = Window.ActionContext(window.app, window, None)
            context_menu = window.create_context_menu()
            window.add_action_to_menu(context_menu, "window_test.context_menu_context", action_context)
            menu_action = context_menu.items[0].action
            assert menu_action
            menu_action.trigger()
            # the context menu item queues its action to run once the menu has closed.
            window.periodic()
            self.assertIsNone(action_context.invoked_from, "a command later run by code with the context of a context menu would be logged as coming from a context menu")

    def test_command_run_by_code_has_no_origin(self) -> None:
        invoked_from_list: list[Window.ActionOrigin | None] = list()

        class CodeTestAction(Window.Action):
            action_id = "window_test.code"
            action_name = "Code Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append(context.invoked_from)
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(CodeTestAction())
        self.addCleanup(Window.unregister_action, "window_test.code")
        with window_context() as window:
            window.perform_action("window_test.code")
            self.assertEqual([None], invoked_from_list, "a command run by a script is recorded as coming from the user interface")

    def test_command_run_from_a_panel_is_recorded_with_the_panel_id(self) -> None:
        invoked_from_list: list[tuple[Window.ActionOrigin | None, str | None]] = list()

        class PanelTestAction(Window.Action):
            action_id = "window_test.panel"
            action_name = "Panel Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append((context.invoked_from, context.invoked_from_id))
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(PanelTestAction())
        self.addCleanup(Window.unregister_action, "window_test.panel")
        with window_context() as window:
            window.perform_action("window_test.panel", invoked_from=Window.ActionOrigin.PANEL, invoked_from_id="test-panel")
            self.assertEqual([(Window.ActionOrigin.PANEL, "test-panel")], invoked_from_list, "a command run from a panel is not recorded with the panel's id")

    def test_command_run_in_a_panel_context_is_recorded_with_the_panel_id(self) -> None:
        invoked_from_list: list[tuple[Window.ActionOrigin | None, str | None]] = list()

        class PanelContextTestAction(Window.Action):
            action_id = "window_test.panel_context"
            action_name = "Panel Context Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append((context.invoked_from, context.invoked_from_id))
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(PanelContextTestAction())
        self.addCleanup(Window.unregister_action, "window_test.panel_context")
        with window_context() as window:
            assert window.app
            action_context = Window.ActionContext(window.app, window, None)
            window.perform_action_in_context("window_test.panel_context", action_context, invoked_from=Window.ActionOrigin.PANEL, invoked_from_id="test-panel")
            self.assertEqual([(Window.ActionOrigin.PANEL, "test-panel")], invoked_from_list, "a command a panel runs in its own context is not recorded with the panel's id")

    def test_command_run_in_a_panel_context_leaves_the_panel_context_without_an_origin(self) -> None:
        class PanelContextKeptTestAction(Window.Action):
            action_id = "window_test.panel_context_kept"
            action_name = "Panel Context Kept Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(PanelContextKeptTestAction())
        self.addCleanup(Window.unregister_action, "window_test.panel_context_kept")
        with window_context() as window:
            assert window.app
            action_context = Window.ActionContext(window.app, window, None)
            window.perform_action_in_context("window_test.panel_context_kept", action_context, invoked_from=Window.ActionOrigin.PANEL, invoked_from_id="test-panel")
            self.assertEqual((None, None), (action_context.invoked_from, action_context.invoked_from_id), "a command later run by code with a panel's context would be logged as coming from the panel")
