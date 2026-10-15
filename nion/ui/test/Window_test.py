# standard libraries
import unittest

# local libraries
from nion.ui import Window


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
