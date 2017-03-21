"""
A basic class to serve as the basis of a typical one window application.
"""
# futures
from __future__ import absolute_import

# standard libraries
import logging

# local libraries
# None

class Application(object):
    """A basic application class.

    Subclass this class and implement the start method. The start method should create a document window that will be
    the focus of the UI.

    Pass the desired user interface to the init method. Then call initialize and start.
    """

    def __init__(self, ui):
        self.ui = ui
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())
        self.window = None

    def initialize(self):
        """Initialize. Separate from __init__ so that overridden methods can be called."""
        pass

    def deinitialize(self):
        self.ui.close()

    def start(self):
        """The start method should create a document window that will be the focus of the UI."""
        raise NotImplemented()


def make_ui(bootstrap_args):
    if "proxy" in bootstrap_args:
        from nion.ui import QtUserInterface
        proxy = bootstrap_args["proxy"]
        return QtUserInterface.QtUserInterface(proxy)
    elif "server" in bootstrap_args:
        from nion.ui import CanvasUI
        server = bootstrap_args["server"]
        return CanvasUI.CanvasUserInterface(server.draw, server.get_font_metrics)
    else:
        return None
