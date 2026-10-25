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
        # main-thread only (the Qt hosts assert this before acting on request_quit).
        self.__is_exiting = False  # set while exit() is closing windows one by one
        self.__is_quit_pending = False  # a quit was requested while exit() was closing windows
        self.__is_requesting_quit = False  # guards against the host re-entering its own quit

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
        self.__event_loop: asyncio.AbstractEventLoop | None = None
        # Python 3.9+: typing.List[weakref.ReferenceType[Dialog]]
        self.__dialogs : typing.List[typing.Any] = list()

    def initialize(self) -> None:
        self._initialize_event_loop()

    def deinitialize(self) -> None:
        self._close_dialogs()
        self._deinitialize_event_loop()
        # a data location is only available for a real (non-test) ui; skip writing the config
        # file otherwise so tests do not leave a stray "PythonConfig.ini" in the working directory.
        data_location = self.ui.get_data_location()
        if data_location:
            with open(os.path.join(data_location, "PythonConfig.ini"), 'w') as f:
                f.write(sys.prefix + '\n')
        self.ui.close()

    def _get_event_loop(self) -> asyncio.AbstractEventLoop | None:
        return self.__event_loop

    def _initialize_event_loop(self) -> None:
        """Initialize. Separate from __init__ so that overridden methods can be called."""
        if sys.platform == "win32":
            # the selector event loop is needed on Windows to interoperate network I/O like requests or zmq
            event_loop = asyncio.SelectorEventLoop()
        else:
            event_loop = asyncio.new_event_loop()
        self.__event_loop = event_loop
        asyncio.set_event_loop(event_loop)

    def _deinitialize_event_loop(self) -> None:
        if self.__event_loop:
            Process.sync_event_loop(self.__event_loop)
            self.__event_loop.close()
            self.__event_loop = None

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        event_loop = self._get_event_loop()
        assert event_loop
        return event_loop

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

    def _get_action_context(self) -> Window.ActionContext:
        return Window.ActionContext(self, None, None)

    def execute_action(self, action_id: str, action_context: typing.Optional[Window.ActionContext] = None,
                       parameters: typing.Optional[typing.Dict[str, typing.Any]] = None) -> Window.ActionResult:
        context = action_context or self._get_action_context()
        if parameters:
            context.parameters.update(parameters)
        action = Window.actions[action_id]
        return self._run_action(action, context, user_interaction=False)

    def perform_action_in_context(self, action_or_action_id: Window.Action | str, action_context: Window.ActionContext, *,
                                  invoked_from: Window.ActionOrigin | None = None, invoked_from_id: str | None = None) -> None:
        """Run the action, given by the action or its id, in the context, as an action a person invoked.

        Use this instead of the window's perform_action_in_context when the window the person used has closed, such as a
        dialog which closes itself before running the action, or when there is no window.

        An action a person invokes passes invoked_from, naming the kind of user interface element they used, and optionally
        invoked_from_id, naming which panel or dialog it was. When either is given, the action runs in a copy of the context
        with both set, so the caller's context is not changed. When neither is given, the action runs in the context itself
        and keeps any origin it already carries.

        An unknown action id, or an action which is not enabled in the context, does nothing. An action which runs modally
        needs a window to track it, so run it with the window's perform_action_in_context. The action's reports are logged
        at their level, but a warning or an error is not shown in a dialog, since there is no window to show it over.
        """
        action_context = Window._action_context_with_origin(action_context, invoked_from, invoked_from_id)
        action = action_or_action_id if isinstance(action_or_action_id, Window.Action) else Window.actions.get(action_or_action_id)
        if action and action.is_enabled(action_context):
            action.clear()
            self._run_action(action, action_context, user_interaction=True)
            for report in action.reports:
                Window._log_report(report)

    def _run_action(self, action: Window.Action, action_context: Window.ActionContext, *, user_interaction: bool) -> Window.ActionResult:
        """Run the action in the context and return its result.

        Every action run through one of the application's windows or through execute_action is run by this method. A subclass
        overrides it to observe or record each action, and calls the base method to run it.

        user_interaction says whether the action may interact with the user, as Action.invoke may and Action.execute may not.
        """
        if user_interaction:
            return action.invoke(action_context)
        return action.execute(action_context)

    def _run_edit_command(self, window: Window.Window, edit_command: Window.EditCommand, dispatch: typing.Callable[[], None], *,
                          invoked_from: Window.ActionOrigin | None, invoked_from_id: str | None) -> None:
        """Run the dispatch of an edit command, such as Cut, to the focus widget of the window.

        Every edit command a window dispatches runs through this method. A subclass overrides it to observe or record each
        edit command, and calls the base method to run the dispatch.

        invoked_from and invoked_from_id say where a person invoked the edit command, as for an action. Both are None when
        code ran it.
        """
        dispatch()

    @property
    def windows(self) -> typing.List[Window.Window]:
        return copy.copy(self.__windows)

    def _window_created(self, window: Window.Window) -> None:
        self.__window_close_event_listeners[window] = window.window_close_event.listen(self._window_did_close)
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
        # hack to detect when last document window is closed. this is a hack because this
        # assumes dialogs do not prevent closing, whereas windows that are not dialog do.
        # this shows up in issue #1411, close using close box with notification dialog open.
        open_windows = set(self.__windows)
        open_dialogs = set([dialog() for dialog in self.__dialogs if dialog()])
        if not self.__prevent_close_count and not (open_windows - open_dialogs):
            # the quit can't wait for a periodic to request it: periodic is only ever driven by a
            # window-owned timer, and the last window (and its timer) is gone. ask the host to quit
            # now. if exit() is in the middle of closing windows itself, defer to exit()'s end instead,
            # since asking here would nest inside exit()'s own window-closing loop.
            if self.__is_exiting:
                self.__is_quit_pending = True
            else:
                self.__ask_host_to_quit()

    def __ask_host_to_quit(self) -> None:
        # asking the host to quit (e.g. Application_close) may itself close the remaining windows,
        # which can re-enter this method via _exit_prevent_close_state; guard against that nesting.
        if self.__is_requesting_quit:
            return
        self.__is_requesting_quit = True
        try:
            self.ui.request_quit()
        finally:
            self.__is_requesting_quit = False

    def exit(self) -> None:
        """The exit method should request to close or close the window."""
        # save/restore rather than assuming False: a window's close handler could call exit() again
        # while this call is still closing windows below, and that nested call must not mark us as
        # done exiting while the outer call is still in progress.
        was_exiting = self.__is_exiting
        self.__is_exiting = True
        try:
            while self.__windows:
                # remove the windows one by one. closing one window may close other windows, so recheck the
                # list each time through the loop.
                window = self.__windows[0]
                # closing the window will trigger the about_to_close event to be called which
                # will then call window close which will fire its window_close_event which will
                # remove the window from the list of window in _window_did_close.
                window.request_close()
                # if the window is still in the list, then the window did not close, so we need to
                # manually remove it from the list.
                if window in self.__windows:
                    self.__windows.remove(window)
        finally:
            self.__is_exiting = was_exiting
        # the application is quitting of its own accord here, rather than from within a close which the host started,
        # so ask the host to quit now, picking up any request deferred while the windows above were closing.
        # only the outermost call does this; a nested call lets the outer one pick up the pending request.
        if not was_exiting and self.__is_quit_pending:
            self.__is_quit_pending = False
            self.__ask_host_to_quit()


    def periodic(self) -> None:
        """The periodic method can be overridden to implement periodic behavior."""
        if event_loop := self._get_event_loop():  # special for shutdown
            event_loop.stop()
            event_loop.run_forever()

    def _close_dialogs(self) -> None:
        for weak_dialog in self.__dialogs:
            dialog = typing.cast(Window.Window | None, weak_dialog())
            if dialog:
                try:
                    dialog.request_close()
                except Exception as e:
                    pass

    def is_dialog_type_open(self, dialog_class: typing.Type[Window.Window]) -> bool:
        for dialog_weakref in self.__dialogs:
            if isinstance(dialog_weakref(), dialog_class):
                return True
        return False

    def register_dialog(self, dialog: Window.Window) -> None:
        old_on_close = dialog.on_close

        def close_dialog() -> None:
            if callable(old_on_close):
                old_on_close()
            self.__dialogs.remove(weakref.ref(dialog))

        dialog.on_close = close_dialog
        self.__dialogs.append(weakref.ref(dialog))

    def _menu_about_to_show(self, window: Window.Window, menu: UserInterface.Menu) -> bool:
        return False

    def show_ok_dialog(self, title: str, message: str, *, completion_fn: typing.Optional[typing.Callable[[], None]] = None) -> None:
        u = Declarative.DeclarativeUI()
        error_message = u.create_label(text=message, word_wrap=True)
        button_row = u.create_row(u.create_stretch(), u.create_push_button(text=_("OK"), on_clicked="close_window"))
        main_column = u.create_column(error_message, button_row, spacing=8, width=300)
        window = u.create_window(main_column, title=title, margin=12, window_style="tool")
        Declarative.WindowHandler(completion_fn=completion_fn).run(window, app=self)

    def show_ok_cancel_dialog(self, title: str, message: str, *, ok_text: typing.Optional[str] = None,
                              cancel_text: typing.Optional[str] = None,
                              completion_fn: typing.Optional[typing.Callable[[bool], None]] = None) -> None:
        u = Declarative.DeclarativeUI()
        error_message = u.create_label(text=message, word_wrap=True)
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
        ui: UserInterface.UserInterface = QtUserInterface.QtUserInterface(proxy)
        if "canvas" in bootstrap_args:
            from nion.ui import CanvasUserInterface
            ui = CanvasUserInterface.CanvasUserInterface(ui)
        return ui
    elif "qt" in bootstrap_args:
        from nion.ui import QtUserInterface
        from nion.ui import PyQtProxy
        ui: UserInterface.UserInterface = QtUserInterface.QtUserInterface(PyQtProxy.PyQtProxy())  # type: ignore
        if "canvas" in bootstrap_args:
            from nion.ui import CanvasUserInterface
            ui = CanvasUserInterface.CanvasUserInterface(ui)
        return ui
    raise Exception("Unable to create user interface object.")


def run_window(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any], d: Declarative.UIDescription, handler: Declarative.HandlerLike) -> BaseApplication:
    """Make base application and run it with the declarative d and handler."""

    def start() -> bool:
        Declarative.run_window(d, handler, app=app)
        return True

    app = BaseApplication(make_ui(bootstrap_args), on_start=start)
    app.initialize()

    return app
