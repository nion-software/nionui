"""
A basic class to serve as the basis of a typical one window application.
"""
# standard libraries
import asyncio
import copy
import logging
import os
import sys

# local libraries
from nion.utils import Process


class LoggingHandler(logging.StreamHandler):

    def __init__(self):
        super().__init__()
        self.__records = list()

    def emit(self, record):
        super().emit(record)
        if self.__records is not None:
            self.__records.append(record)

    def take_records(self):
        records = self.__records
        self.__records = None
        return records


logging_handler = LoggingHandler()


class Application:
    """A basic application class.

    Subclass this class and implement the start method. The start method should create a document window that will be
    the focus of the UI.

    Pass the desired user interface to the init method. Then call initialize and start.
    """

    def __init__(self, ui, *, on_start=None):
        self.ui = ui
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(logging_handler)
        self.window = None
        self.on_start = on_start
        self.__windows = list()
        self.__window_close_event_listeners = dict()
        self.__event_loop = None

    def initialize(self):
        """Initialize. Separate from __init__ so that overridden methods can be called."""
        # configure the event loop, which can be used for non-window clients.
        logger = logging.getLogger()
        old_level = logger.level
        logger.setLevel(logging.INFO)
        self.__event_loop = asyncio.new_event_loop()  # outputs a debugger message!
        logger.setLevel(old_level)

    def deinitialize(self):
        Process.close_event_loop(self.__event_loop)
        self.__event_loop = None
        with open(os.path.join(self.ui.get_data_location(), "PythonConfig.ini"), 'w') as f:
            f.write(sys.prefix + '\n')
        self.ui.close()

    def run(self):
        """Alternate start which allows ui to control event loop."""
        self.ui.run(self)

    def start(self):
        """The start method should create a window that will be the focus of the UI."""
        if self.on_start:
            return self.on_start()
        raise NotImplemented()

    def _window_created(self, window):
        self.__window_close_event_listeners[window] = window._window_close_event.listen(self.__window_did_close)
        assert window not in self.__windows
        self.__windows.append(window)

    def __window_did_close(self, window):
        self.__window_close_event_listeners[window].close()
        del self.__window_close_event_listeners[window]
        self.__windows.remove(window)

    def exit(self):
        """The exit method should request to close or close the window."""
        for window in copy.copy(self.__windows):
            # closing the window will trigger the about_to_close event to be called which
            # will then call window close which will fire its did_close_event which will
            # remove the window from the list of window.
            window.request_close()

    def periodic(self):
        """The periodic method can be overridden to implement periodic behavior."""
        if self.__event_loop:  # special for shutdown
            self.__event_loop.stop()
            self.__event_loop.run_forever()

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self.__event_loop


def make_ui(bootstrap_args):
    if "proxy" in bootstrap_args:
        from nion.ui import QtUserInterface
        proxy = bootstrap_args["proxy"]
        return QtUserInterface.QtUserInterface(proxy)
    elif "pyqt" in bootstrap_args:
        from nion.ui import QtUserInterface
        from nion.ui import PyQtProxy
        return QtUserInterface.QtUserInterface(PyQtProxy.PyQtProxy())
    elif "server" in bootstrap_args:
        from nion.ui import CanvasUI
        server = bootstrap_args["server"]
        return CanvasUI.CanvasUserInterface(server.draw, server.get_font_metrics)
    else:
        return None
