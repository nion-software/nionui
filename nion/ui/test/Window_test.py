# standard libraries
import contextlib
import typing
import unittest

# local libraries
from nion.ui import Application
from nion.ui import CanvasItem
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


class _ActionProvidingCanvasItem(CanvasItem.EmptyCanvasItem):
    """A focusable canvas item which provides the bound action, if any, for the delete command."""

    def __init__(self, bound_action: Window.BoundAction | None) -> None:
        super().__init__()
        self.focusable = True
        self.__bound_action = bound_action

    def get_delete_action(self) -> Window.BoundAction | None:
        return self.__bound_action


def focus_canvas_item(window: Window.Window, canvas_item: CanvasItem.AbstractCanvasItem) -> None:
    """Attach the canvas item to the window in a canvas widget and give it the focus."""
    canvas_widget = window.ui.create_canvas_widget()
    canvas_widget.canvas_item.add_canvas_item(canvas_item)
    window.attach_widget(canvas_widget)
    canvas_item.request_focus()


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

    def test_main_menu_item_with_its_own_title_and_parameters_runs_its_action_with_them_from_the_menu(self) -> None:
        contexts: list[tuple[typing.Mapping[str, str], Window.ActionOrigin | None]] = list()

        class MainMenuParametersTestAction(Window.Action):
            action_id = "window_test.main_menu_parameters"
            action_name = "Main Menu Parameters Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                contexts.append((dict(context.parameters), context.invoked_from))
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(MainMenuParametersTestAction())
        self.addCleanup(Window.unregister_action, "window_test.main_menu_parameters")
        with window_context() as window:
            window.build_menu(None, [{"type": "menu", "menu_id": "window_test", "title": "Test", "items": []}])
            # build_menu publishes each top level menu as an attribute named after its menu id.
            menu = typing.cast(UserInterface.Menu, getattr(window, "_window_test_menu"))
            window.add_action_to_main_menu(menu, "window_test.main_menu_parameters", title="Item Title", parameters={"item": "one"})
            # showing the menu updates the items which stand for an action, which this item does not.
            menu.about_to_show()
            menu_action = menu.items[0].action
            assert menu_action
            self.assertEqual("Item Title", menu_action.title, "a main-menu item with its own title shows the action's name instead")
            menu_action.trigger()
            self.assertEqual([({"item": "one"}, Window.ActionOrigin.MENU)], contexts, "a main-menu item does not run its action once, with its parameters, from the menu")

    def test_main_menu_item_added_by_action_id_follows_its_action_when_its_menu_is_shown(self) -> None:
        class MainMenuDisabledTestAction(Window.Action):
            action_id = "window_test.main_menu_disabled"
            action_name = "Main Menu Disabled Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

            def is_enabled(self, context: Window.ActionContext) -> bool:
                return False

        Window.register_action(MainMenuDisabledTestAction())
        self.addCleanup(Window.unregister_action, "window_test.main_menu_disabled")
        with window_context() as window:
            window.build_menu(None, [{"type": "menu", "menu_id": "window_test", "title": "Test", "items": []}])
            # build_menu publishes each top level menu as an attribute named after its menu id.
            menu = typing.cast(UserInterface.Menu, getattr(window, "_window_test_menu"))
            window.add_action_to_main_menu(menu, "window_test.main_menu_disabled")
            menu.about_to_show()
            menu_action = menu.items[0].action
            assert menu_action
            self.assertFalse(menu_action.enabled, "a main-menu item added by action id stays enabled when its action is disabled")

    def test_main_menu_item_in_an_inserted_menu_follows_its_action_when_its_menu_is_shown(self) -> None:
        # an application may insert menus among its built ones, for plug-ins to fill with action items.
        class InsertedMenuDisabledTestAction(Window.Action):
            action_id = "window_test.inserted_menu_disabled"
            action_name = "Inserted Menu Disabled Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

            def is_enabled(self, context: Window.ActionContext) -> bool:
                return False

        Window.register_action(InsertedMenuDisabledTestAction())
        self.addCleanup(Window.unregister_action, "window_test.inserted_menu_disabled")
        with window_context() as window:
            before_menu = window.add_menu("Test")
            menu = window.insert_menu("Inserted", before_menu)
            window.add_action_to_main_menu(menu, "window_test.inserted_menu_disabled")
            menu.about_to_show()
            menu_action = menu.items[0].action
            assert menu_action
            self.assertFalse(menu_action.enabled, "an item in an inserted main menu stays enabled when its action is disabled")

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

    def test_command_run_by_the_application_after_its_dialog_closed_is_recorded_with_the_dialog_id(self) -> None:
        invoked_from_list: list[tuple[Window.ActionOrigin | None, str | None]] = list()

        class ClosedDialogTestAction(Window.Action):
            action_id = "window_test.closed_dialog"
            action_name = "Closed Dialog Test"

            # a person's action runs through invoke, which may interact with them.
            def invoke(self, context: Window.ActionContext) -> Window.ActionResult:
                invoked_from_list.append((context.invoked_from, context.invoked_from_id))
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        Window.register_action(ClosedDialogTestAction())
        self.addCleanup(Window.unregister_action, "window_test.closed_dialog")
        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        action_context = Window.ActionContext(app, None, None)
        window.close()
        app.perform_action_in_context("window_test.closed_dialog", action_context, invoked_from=Window.ActionOrigin.DIALOG, invoked_from_id="test-dialog")
        self.assertEqual([(Window.ActionOrigin.DIALOG, "test-dialog")], invoked_from_list, "a command a dialog runs after closing itself is not run as a person's or not recorded with the dialog's id")

    def test_edit_commands_run_the_handler_of_the_focused_canvas_item(self) -> None:
        handled_commands: list[str] = list()

        class EditingCanvasItem(CanvasItem.EmptyCanvasItem):
            def __init__(self) -> None:
                super().__init__()
                self.focusable = True

            def handle_undo(self) -> bool:
                handled_commands.append("undo")
                return True

            def handle_redo(self) -> bool:
                handled_commands.append("redo")
                return True

            def handle_cut(self) -> bool:
                handled_commands.append("cut")
                return True

            def handle_copy(self) -> bool:
                handled_commands.append("copy")
                return True

            def handle_paste(self) -> bool:
                handled_commands.append("paste")
                return True

            def handle_delete(self) -> bool:
                handled_commands.append("delete")
                return True

            def handle_select_all(self) -> bool:
                handled_commands.append("select_all")
                return True

        class EditingWindow(Window.Window):
            # the window's edit commands are enabled only for a window which handles them, and the window handles them
            # itself only when the focused item doesn't.
            def handle_undo(self) -> bool:
                handled_commands.append("window undo")
                return True

            def handle_redo(self) -> bool:
                handled_commands.append("window redo")
                return True

            def handle_cut(self) -> bool:
                handled_commands.append("window cut")
                return True

            def handle_copy(self) -> bool:
                handled_commands.append("window copy")
                return True

            def handle_paste(self) -> bool:
                handled_commands.append("window paste")
                return True

            def handle_delete(self) -> bool:
                handled_commands.append("window delete")
                return True

            def handle_select_all(self) -> bool:
                handled_commands.append("window select_all")
                return True

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = EditingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window._create_menus()
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, EditingCanvasItem())
        for menu_action in menu.get_menu_actions():
            menu_action.trigger()
        self.assertEqual(["undo", "redo", "cut", "copy", "paste", "delete", "select_all"], handled_commands, "an edit command does not run the focused item's handler, once")

    def test_select_all_is_enabled_for_a_focused_canvas_item_which_handles_it_in_a_window_which_does_not(self) -> None:
        # select all is enabled whenever something in the focus chain handles it.
        class SelectingCanvasItem(CanvasItem.EmptyCanvasItem):
            def __init__(self) -> None:
                super().__init__()
                self.focusable = True

            def handle_select_all(self) -> bool:
                return True

        with window_context() as window:
            window._create_menus()
            # build_menu publishes each top level menu as an attribute named after its menu id.
            menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
            focus_canvas_item(window, SelectingCanvasItem())
            menu.about_to_show()
            select_all_menu_action = menu.get_menu_actions()[-1]
            self.assertEqual(("Select All", True), (select_all_menu_action.title, select_all_menu_action.enabled), "Select All is disabled although the focused item handles it")

    def test_edit_command_chosen_from_the_menu_is_run_by_the_application_once_from_the_menu(self) -> None:
        # the command log records each edit command the application runs.
        run_edit_commands: list[tuple[str, Window.ActionOrigin | None]] = list()

        class RecordingApplication(Application.BaseApplication):
            def _run_edit_command(self, window: Window.Window, edit_command: Window.EditCommand, dispatch: typing.Callable[[], None], *,
                                  invoked_from: Window.ActionOrigin | None, invoked_from_id: str | None) -> None:
                run_edit_commands.append((edit_command.edit_command_id, invoked_from))
                super()._run_edit_command(window, edit_command, dispatch, invoked_from=invoked_from, invoked_from_id=invoked_from_id)

        class CopyingWindow(Window.Window):
            # the window's Copy is enabled only for a window which handles copy.
            def handle_copy(self) -> bool:
                return True

        app = RecordingApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = CopyingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "copy"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        menu_action = menu.items[0].action
        assert menu_action
        menu_action.trigger()
        self.assertEqual([("copy", Window.ActionOrigin.MENU)], run_edit_commands, "Copy chosen from the menu is not run by the application once, from the menu")

    def test_delete_runs_the_action_the_focused_canvas_item_provides_once_from_the_menu(self) -> None:
        # the command log records each action and edit command the application runs, so the delete edit command must not run as well.
        run_commands: list[tuple[str, Window.ActionOrigin | None]] = list()

        class RecordingApplication(Application.BaseApplication):
            def _run_action(self, action: Window.Action, action_context: Window.ActionContext, *, user_interaction: bool) -> Window.ActionResult:
                run_commands.append((action.action_id, action_context.invoked_from))
                return super()._run_action(action, action_context, user_interaction=user_interaction)

            def _run_edit_command(self, window: Window.Window, edit_command: Window.EditCommand, dispatch: typing.Callable[[], None], *,
                                  invoked_from: Window.ActionOrigin | None, invoked_from_id: str | None) -> None:
                run_commands.append((edit_command.edit_command_id, invoked_from))
                super()._run_edit_command(window, edit_command, dispatch, invoked_from=invoked_from, invoked_from_id=invoked_from_id)

        class ProvidedDeleteTestAction(Window.Action):
            action_id = "window_test.provided_delete"
            action_name = "Provided Delete Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        app = RecordingApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "delete"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, _ActionProvidingCanvasItem(Window.BoundAction(ProvidedDeleteTestAction(), window._get_action_context())))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        menu_action.trigger()
        self.assertEqual([("window_test.provided_delete", Window.ActionOrigin.MENU)], run_commands, "Delete does not run only the action the focused item provides, once, from the menu")

    def test_delete_dispatches_delete_to_a_focused_canvas_item_which_handles_it_before_an_action_the_window_provides(self) -> None:
        # an action the window provides never takes Delete away from a focused item that handles it itself.
        handle_delete_count = 0
        window_actions_run: list[str] = list()

        class DeletingCanvasItem(CanvasItem.EmptyCanvasItem):
            def __init__(self) -> None:
                super().__init__()
                self.focusable = True

            def handle_delete(self) -> bool:
                nonlocal handle_delete_count
                handle_delete_count += 1
                return True

        class WindowDeleteTestAction(Window.Action):
            action_id = "window_test.window_delete"
            action_name = "Window Delete Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                window_actions_run.append(self.action_id)
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        class DeletingWindow(Window.Window):
            # the delete edit command is enabled only for a window which handles delete.
            def handle_delete(self) -> bool:
                return True

            def get_delete_action(self) -> Window.BoundAction | None:
                return Window.BoundAction(WindowDeleteTestAction(), self._get_action_context())

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = DeletingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "delete"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, DeletingCanvasItem())
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        menu_action.trigger()
        self.assertEqual((1, []), (handle_delete_count, window_actions_run), "Delete runs an action the window provides in place of the focused item which handles delete")

    def test_delete_runs_nothing_when_the_action_the_focused_canvas_item_provides_is_disabled(self) -> None:
        handle_delete_count = 0
        provided_actions_run: list[str] = list()

        class DisabledProvidedDeleteTestAction(Window.Action):
            action_id = "window_test.disabled_provided_delete"
            action_name = "Disabled Provided Delete Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                provided_actions_run.append(self.action_id)
                return Window.ActionResult(Window.ActionStatus.FINISHED)

            def is_enabled(self, context: Window.ActionContext) -> bool:
                return False

        class DeletingCanvasItem(_ActionProvidingCanvasItem):
            def handle_delete(self) -> bool:
                nonlocal handle_delete_count
                handle_delete_count += 1
                return True

        class DeletingWindow(Window.Window):
            # the delete edit command is enabled only for a window which handles delete.
            def handle_delete(self) -> bool:
                return True

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = DeletingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "delete"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, DeletingCanvasItem(Window.BoundAction(DisabledProvidedDeleteTestAction(), window._get_action_context())))
        # the item is triggered without showing the menu first, as its key shortcut triggers it.
        menu_action = menu.items[0].action
        assert menu_action
        menu_action.trigger()
        self.assertEqual((0, []), (handle_delete_count, provided_actions_run), "Delete runs something when the action the focused item provides is disabled")

    def test_delete_menu_item_shows_the_title_and_enabled_state_of_the_action_the_focused_canvas_item_provides(self) -> None:
        class DisabledProvidedDeleteTestAction(Window.Action):
            action_id = "window_test.disabled_provided_delete"
            action_name = "Provided Delete Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                return Window.ActionResult(Window.ActionStatus.FINISHED)

            def get_action_name(self, context: Window.ActionContext) -> str:
                return "Delete Provided Items"

            def is_enabled(self, context: Window.ActionContext) -> bool:
                return False

        class DeletingWindow(Window.Window):
            # the window handles delete, so the edit command alone would show Delete enabled.
            def handle_delete(self) -> bool:
                return True

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = DeletingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "delete"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, _ActionProvidingCanvasItem(Window.BoundAction(DisabledProvidedDeleteTestAction(), window._get_action_context())))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        self.assertEqual(("Delete Provided Items", False), (menu_action.title, menu_action.enabled), "the Delete menu item does not show the title and enabled state of the action it runs")

    def test_delete_menu_item_without_a_provided_action_shows_the_delete_command(self) -> None:
        class DeletingWindow(Window.Window):
            # the delete edit command is enabled only for a window which handles delete.
            def handle_delete(self) -> bool:
                return True

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = DeletingWindow(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "delete"}]}])
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        focus_canvas_item(window, _ActionProvidingCanvasItem(None))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        self.assertEqual(("Delete", True), (menu_action.title, menu_action.enabled), "the Delete menu item changes its title or enabled state when nothing provides an action")

    def test_menu_item_state_of_a_focused_canvas_item_which_handles_a_command_is_enabled(self) -> None:
        class CuttingCanvasItem(CanvasItem.EmptyCanvasItem):
            def __init__(self) -> None:
                super().__init__()
                self.focusable = True

            def handle_cut(self) -> bool:
                return True

        with window_context() as window:
            focus_canvas_item(window, CuttingCanvasItem())
            menu_item_state = window._get_focus_widget_menu_item_state("cut")
            self.assertTrue(menu_item_state and menu_item_state.enabled, "the menu item state of a focused item which handles cut is not enabled")
