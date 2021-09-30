# standard libraries
import unittest

# third party libraries
# None

# local libraries
from nion.ui import TestUI
from nion.ui import UserInterface as UserInterfaceModule


class TestTestUIUserInterface(unittest.TestCase):

    def setUp(self) -> None:
        self.ui = TestUI.UserInterface()

    def tearDown(self) -> None:
        pass

    def test_get_font_metrics_sanity_check(self) -> None:
        # Test that TestUI.UserInterface.get_font_metrics returns a reasonable size
        # This test will need to be updated if 'make_font_metrics_for_tests' is modified
        self.assertEqual(self.ui.get_font_metrics("ignored", "This is a string"),
                         UserInterfaceModule.FontMetrics(77, 13, 11, 2, 0))

    def test_default_font_metrics_is_var_width(self) -> None:
        self.assertNotEqual(self.ui.get_font_metrics("ignored", "111"),
                            self.ui.get_font_metrics("ignored", "999"))
