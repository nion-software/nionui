"""
A basic class to serve as the basis of a typical one window application.
"""
from __future__ import annotations

# standard libraries
import asyncio
import contextlib
import copy
import gettext
import logging
import os
import sys
import types
import typing
import weakref

# local libraries
from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Process

if typing.TYPE_CHECKING:
    from nion.ui import Dialog
    from nion.utils import Event

_ = gettext.gettext


class LoggingHandler(logging.StreamHandler):  # type: ignore

    def __init__(self) -> None:
        super().__init__()
        self.__records: typing.List[logging.LogRecord] = list()

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        if self.__records is not None:
            self.__records.append(record)

    def take_records(self) -> typing.List[logging.LogRecord]:
        records = self.__records
        self.__records = list()
        return records


logging_handler = LoggingHandler()


class BaseApplication:
    """A basic application class.

    Subclass this class and implement the start method. The start method should create a document window that will be
    the focus of the UI.

    Pass the desired user interface to the init method. Then call initialize and start.
    """

    def __init__(self, ui: UserInterface.UserInterface, *,
                 on_start: typing.Optional[typing.Callable[[], bool]] = None) -> None:
        self.ui = ui

        # handle last window closing in Python; but use this variable so tool can continue to
        # close on last window for backwards compatibility. setting this flag will tell the
        # tool to not close on last window closing. it is handled when items are removed from
        # __windows instead.
        self._should_close_on_last_window = False
        self.__prevent_close_count = 0

        self.__on_start = on_start
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(logging_handler)

        class ContextFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                if record.exc_info and record.exc_info[0] == ConnectionResetError:
                    return False
                return True

        # work around bug 39010 here
        logger = logging.getLogger('asyncio')
        logger.addFilter(ContextFilter())

        self.__windows : typing.List[Window.Window] = list()
        self.__window_close_event_listeners: typing.Dict[Window.Window, Event.EventListener] = dict()
        self.__event_loop: asyncio.AbstractEventLoop = typing.cast(asyncio.AbstractEventLoop, None)
        # Python 3.9+: typing.List[weakref.ReferenceType[Dialog]]
        self.__dialogs : typing.List[typing.Any] = list()

    def initialize(self) -> None:
        """Initialize. Separate from __init__ so that overridden methods can be called."""
        # configure the event loop, which can be used for non-window clients. for backwards compatibility only.
        self.__event_loop = asyncio.get_event_loop()

    def deinitialize(self) -> None:
        self._close_dialogs()
        Process.sync_event_loop(self.__event_loop)
        self.__event_loop = typing.cast(asyncio.AbstractEventLoop, None)
        with open(os.path.join(self.ui.get_data_location(), "PythonConfig.ini"), 'w') as f:
            f.write(sys.prefix + '\n')
        self.ui.close()

    def run(self) -> None:
        """Run the application. Called from PyQt."""
        self.ui.run(self)

    def start(self) -> bool:
        """The start method should create a window that will be the focus of the UI."""
        if callable(self.__on_start):
            return self.__on_start()
        return True

    def stop(self) -> None:
        # program is really stopping, clean up.
        self.deinitialize()

    @property
    def windows(self) -> typing.List[Window.Window]:
        return copy.copy(self.__windows)

    def _window_created(self, window: Window.Window) -> None:
        self.__window_close_event_listeners[window] = window._window_close_event.listen(self._window_did_close)
        assert window not in self.__windows
        self.__windows.append(window)

    def _window_did_close(self, window: Window.Window) -> None:
        self.__window_close_event_listeners[window].close()
        del self.__window_close_event_listeners[window]
        self.__windows.remove(window)
        with self.prevent_close():
            pass  # trigger close if all windows closed.

    class _PreventCloseContext:
        def __init__(self, application: BaseApplication) -> None:
            self.__application = application

        def __enter__(self) -> BaseApplication._PreventCloseContext:
            self.__application._enter_prevent_close_state()
            return self

        def __exit__(self, exception_type: typing.Optional[typing.Type[BaseException]],
                     value: typing.Optional[BaseException], traceback: typing.Optional[types.TracebackType]) -> typing.Optional[bool]:
            self.__application._exit_prevent_close_state()
            return None

    def prevent_close(self) -> contextlib.AbstractContextManager[BaseApplication._PreventCloseContext]:
        return BaseApplication._PreventCloseContext(self)

    def _enter_prevent_close_state(self) -> None:
        self.__prevent_close_count += 1

    def _exit_prevent_close_state(self) -> None:
        self.__prevent_close_count -= 1
        if not self.__prevent_close_count and not self.__windows and not self.__dialogs:
            self.ui.request_quit()

    def exit(self) -> None:
        """The exit method should request to close or close the window."""
        for window in copy.copy(self.__windows):
            # closing the window will trigger the about_to_close event to be called which
            # will then call window close which will fire its _window_close_event which will
            # remove the window from the list of window in _window_did_close.
            window.request_close()

    def periodic(self) -> None:
        """The periodic method can be overridden to implement periodic behavior."""
        if self.__event_loop:  # special for shutdown
            self.__event_loop.stop()
            self.__event_loop.run_forever()

    def _close_dialogs(self) -> None:
        for weak_dialog in self.__dialogs:
            dialog = typing.cast(Window.Window, weak_dialog())
            if dialog:
                try:
                    dialog.request_close()
                except Exception as e:
                    pass
        self.__dialogs = list()

    def is_dialog_type_open(self, dialog_class: typing.Type[Dialog.ActionDialog]) -> bool:
        for dialog_weakref in self.__dialogs:
            if isinstance(dialog_weakref(), dialog_class):
                return True
        return False

    def register_dialog(self, dialog: Window.Window) -> None:
        def close_dialog() -> None:
            self.__dialogs.remove(weakref.ref(dialog))

        dialog.on_close = close_dialog
        self.__dialogs.append(weakref.ref(dialog))

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self.__event_loop

    def _menu_about_to_show(self, window: Window.Window, menu: UserInterface.Menu) -> bool:
        return False

    def show_ok_dialog(self, title: str, message: str, *, completion_fn: typing.Optional[typing.Callable[[], None]] = None) -> None:
        u = Declarative.DeclarativeUI()
        error_message = u.create_label(text=message)
        button_row = u.create_row(u.create_stretch(), u.create_push_button(text=_("OK"), on_clicked="close_window"))
        main_column = u.create_column(error_message, button_row, spacing=8, width=300)
        window = u.create_window(main_column, title=title, margin=12, window_style="tool")
        Declarative.WindowHandler(completion_fn=completion_fn).run(window, app=self)

    def show_ok_cancel_dialog(self, title: str, message: str, *, ok_text: typing.Optional[str] = None,
                              cancel_text: typing.Optional[str] = None,
                              completion_fn: typing.Optional[typing.Callable[[bool], None]] = None) -> None:
        u = Declarative.DeclarativeUI()
        error_message = u.create_label(text=message)
        button_row = u.create_row(u.create_stretch(),
                                  u.create_push_button(text=cancel_text or _("Cancel"), on_clicked="handle_reject"),
                                  u.create_push_button(text=ok_text or _("OK"), on_clicked="handle_accept"),
                                  spacing=12)
        main_column = u.create_column(error_message, button_row, spacing=8, width=380)
        window = u.create_window(main_column, title=title, margin=12, window_style="tool")

        class OkCancelHandler(Declarative.WindowHandler):
            def __init__(self) -> None:
                super().__init__(completion_fn=self.handle_close)
                self.__result = False

            def handle_close(self) -> None:
                if callable(completion_fn):
                    completion_fn(self.__result)

            def handle_accept(self, widget: typing.Optional[Declarative.UIWidget]) -> None:
                self.__result = True
                self.close_window(widget)

            def handle_reject(self, widget: typing.Optional[Declarative.UIWidget]) -> None:
                self.__result = False
                self.close_window(widget)

        OkCancelHandler().run(window, app=self)


def make_ui(bootstrap_args: typing.Mapping[str, typing.Any]) -> UserInterface.UserInterface:
    if "proxy" in bootstrap_args:
        from nion.ui import QtUserInterface
        proxy = bootstrap_args["proxy"]
        return QtUserInterface.QtUserInterface(proxy)
    elif "pyqt" in bootstrap_args:
        from nion.ui import QtUserInterface
        from nion.ui import PyQtProxy
        return QtUserInterface.QtUserInterface(PyQtProxy.PyQtProxy())  # type: ignore
    raise Exception("Unable to create user interface object.")


def run_window(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any], d: Declarative.UIDescription, handler: Declarative.HandlerLike) -> BaseApplication:
    """Make base application and run it with the declarative d and handler."""

    def start() -> bool:
        Declarative.run_window(d, handler, app=app)
        return True

    app = BaseApplication(make_ui(bootstrap_args), on_start=start)
    app.initialize()

    return app
