"""
A basic class to serve as the document controller of a typical one window application.
"""
from __future__ import annotations

# standard libraries
import asyncio
import enum
import functools
import gettext
import logging
import pathlib
import typing
import weakref

# local libraries
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import Process
from nion.ui import DrawingContext
from nion.ui import UserInterface

if typing.TYPE_CHECKING:
    from nion.ui import Application


_ = gettext.gettext


class ActionContext:
    def __init__(self, application: Application.BaseApplication, window: typing.Optional[Window], focus_widget: typing.Optional[UserInterface.Widget]):
        self._application = application
        self._window = window
        self.focus_widget = focus_widget
        self.event_type_str: typing.Optional[str] = None
        self.parameters: typing.Dict[str, typing.Any] = dict()

    @property
    def application(self) -> Application.BaseApplication:
        return self._application

    @property
    def window(self) -> typing.Optional[Window]:
        return self._window


class ActionStatus(enum.IntEnum):
    FINISHED = 0
    MODAL = 1
    CANCELLED = 2
    PASS = 3


class ActionResult:
    def __init__(self, status: ActionStatus):
        self.status = status
        self.results: typing.Dict[str, typing.Any] = dict()


class ReportType(enum.IntEnum):
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class Report:
    def __init__(self, type: ReportType, message: str):
        self.type = type
        self.message = message

    @classmethod
    def from_log_record(cls, record: logging.LogRecord) -> Report:
        return Report(ReportType(record.levelno), record.getMessage())


class ActionProperty:
    pass


class ActionStringProperty(ActionProperty):
    def __init__(self, name: str):
        self.name = name


class ActionIntegerProperty(ActionProperty):
    def __init__(self, name: str):
        self.name = name


class Action:
    action_id: str = str()
    action_name: str = str()
    action_role: typing.Optional[str] = None
    action_summary: typing.Optional[str] = None
    action_description: typing.Optional[str] = None
    action_parameters: typing.List[ActionProperty] = list()

    def __init__(self) -> None:
        self.__reports: typing.List[Report] = list()

    @property
    def reports(self) -> typing.List[Report]:
        return self.__reports

    def clear(self) -> None:
        self.__reports = list()

    def event(self, context: ActionContext) -> ActionResult:
        """Handle the event."""
        ...

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action with the context. No user interaction allowed. May be called from scripts."""
        raise NotImplementedError()

    def invoke(self, context: ActionContext) -> ActionResult:
        """Called to execute the action with the context. User interaction allowed. Typically calls `execute`."""
        return self.execute(context)

    def is_checked(self, context: ActionContext) -> bool:
        return False

    def is_enabled(self, context: ActionContext) -> bool:
        return True

    def get_action_name(self, context: ActionContext) -> str:
        return self.action_name

    def report(self, type: ReportType, message: str) -> None:
        self.__reports.append(Report(type, message))

    def log_record(self, record: logging.LogRecord) -> None:
        self.__reports.append(Report.from_log_record(record))

    def get_string_property(self, context: ActionContext, name: str) -> str:
        return str(context.parameters.get(name, str()))

    def set_string_property(self, context: ActionContext, name: str, value: str) -> None:
        context.parameters[name] = value

    def get_int_property(self, context: ActionContext, name: str) -> int:
        return int(context.parameters.get(name, 0))

    def set_int_property(self, context: ActionContext, name: str, value: int) -> None:
        context.parameters[name] = value


actions: typing.Mapping[str, Action] = dict()


def register_action(action: Action) -> None:
    assert action.action_id not in actions
    typing.cast(typing.MutableMapping[str, Action], actions)[action.action_id] = action


_ActionShortcutsType = typing.Mapping[str, typing.Mapping[str, str]]

action_shortcuts: typing.Mapping[str, typing.Mapping[str, str]] = dict()


def add_action_shortcut(action_id: str, action_context: str, key_sequence: str) -> None:
    typing.cast(typing.MutableMapping[str, typing.MutableMapping[str, str]], action_shortcuts).setdefault(action_id, dict())[action_context] = key_sequence


def register_action_shortcuts(action_shortcuts: _ActionShortcutsType) -> None:
    for action_id, action_shortcut_d in action_shortcuts.items():
        for action_context, key_sequence in action_shortcut_d.items():
            add_action_shortcut(action_id, action_context, key_sequence)


def get_action_id_for_key(context: str, key: UserInterface.Key) -> typing.Optional[str]:
    # deprecated as of 0.5.2. use get_action_for_key instead.
    action = get_action_for_key([context], key)
    return action.action_id if action else None


def get_action_for_key(action_contexts: typing.Sequence[str], key: UserInterface.Key) -> typing.Optional[Action]:
    for action_context in reversed(action_contexts):
        for action_id, action_shortcut_d in action_shortcuts.items():
            for key_action_context, key_sequence_str in action_shortcut_d.items():
                if action_context == key_action_context:
                    if isinstance(key_sequence_str, list):
                        key_sequences = [UserInterface.KeySequence(kss) for kss in key_sequence_str]
                    else:
                        key_sequences = [UserInterface.KeySequence(key_sequence_str)]
                    for key_sequence in key_sequences:
                        if key_sequence.matches(key) == UserInterface.KeySequenceMatch.EXACT:
                            return actions[action_id]
    return None


class Window:
    count = 0  # useful for detecting leaks in tests

    def __init__(self, ui: UserInterface.UserInterface, app: typing.Optional[Application.BaseApplication] = None,
                 parent_window: typing.Optional[Window] = None, window_style: typing.Optional[str] = None,
                 persistent_id: typing.Optional[str] = None):
        Window.count += 1
        self.ui = ui
        self.parent_window = parent_window
        self.app: typing.Optional[Application.BaseApplication] = app or (parent_window.app if parent_window else None)
        self.on_close: typing.Optional[typing.Callable[[], None]] = None
        parent_ui_window = parent_window._document_window if parent_window else None
        self.__document_window = self.ui.create_document_window(parent_window=parent_ui_window)
        if window_style:
            self.__document_window.window_style = window_style
        self.__persistent_id = persistent_id
        self.__shown = False
        self.__request_close = False

        # Python 3.9+: should be weakref.ReferenceType[Dialog]
        self.__dialogs: typing.List[typing.Any] = list()

        self._window_close_event = Event.Event()

        self.__document_window.on_periodic = self.periodic
        self.__document_window.on_queue_task = self.queue_task
        self.__document_window.on_clear_queued_tasks = self.clear_queued_tasks
        self.__document_window.on_add_task = self.add_task
        self.__document_window.on_clear_task = self.clear_task
        self.__document_window.on_about_to_show = self.about_to_show
        self.__document_window.on_about_to_close = self.about_to_close
        self.__document_window.on_activation_changed = self.activation_changed
        self.__document_window.on_key_pressed = self.key_pressed
        self.__document_window.on_key_released = self.key_released
        self.__document_window.on_size_changed = self.size_changed
        self.__document_window.on_position_changed = self.position_changed
        self.__document_window.on_refocus_widget = self.refocus_widget
        self.__document_window.on_ui_activity = self._register_ui_activity
        self.__periodic_queue = Process.TaskQueue()
        self.__periodic_set = Process.TaskSet()
        self.__modal_actions: typing.List[Action] = list()

        # define old-style menu actions for backwards compatibility
        self._close_action = None
        self._page_setup_action = None
        self._print_action = None
        self._quit_action = None
        self._undo_action = None
        self._redo_action = None
        self._cut_action = None
        self._copy_action = None
        self._paste_action = None
        self._delete_action = None
        self._select_all_action = None
        self._minimize_action = None
        self._zoom_action = None
        self._bring_to_front_action = None

        # configure the event loop object. for backwards compatibility only.
        self.__event_loop = asyncio.get_event_loop_policy().get_event_loop()

        if app:
            app._window_created(self)

    def close(self) -> None:
        self.__request_close = False
        self._finish_periodic()  # required to finish periodic operations during tests
        self._close_dialogs()
        self._window_close_event.fire(self)
        self._window_close_event = typing.cast(Event.Event, None)
        self.on_close = None
        self.__event_loop = typing.cast(asyncio.AbstractEventLoop, None)
        self.ui.destroy_document_window(self.__document_window)  # close the ui window
        self.__document_window = typing.cast(UserInterface.Window, None)
        self.__periodic_queue = typing.cast(Process.TaskQueue, None)
        self.__periodic_set = typing.cast(Process.TaskSet, None)
        self.__modal_actions = typing.cast(typing.List[Action], None)
        self._close_action = None
        self._page_setup_action = None
        self._print_action = None
        self._quit_action = None
        self._undo_action = None
        self._redo_action = None
        self._cut_action = None
        self._copy_action = None
        self._paste_action = None
        self._delete_action = None
        self._select_all_action = None
        self._minimize_action = None
        self._zoom_action = None
        self._bring_to_front_action = None
        self.parent_window = None
        self.app = None
        Window.count -= 1

    @property
    def _document_window(self) -> UserInterface.Window:
        # for testing only
        return self.__document_window

    def _create_menus(self) -> None:
        menu_descriptions = [
            {"type": "menu", "menu_id": "file", "title": _("File"), "items":
                [
                    {"type": "item", "action_id": "window.close"},
                    {"type": "separator"},
                    {"type": "item", "action_id": "window.page_setup"},
                    {"type": "item", "action_id": "window.print"},
                    {"type": "separator"},
                    {"type": "item", "action_id": "application.exit"},
                ]
             },
            {"type": "menu", "menu_id": "edit", "title": _("Edit"), "items":
                [
                    {"type": "item", "action_id": "window.undo"},
                    {"type": "item", "action_id": "window.redo"},
                    {"type": "separator"},
                    {"type": "item", "action_id": "window.cut"},
                    {"type": "item", "action_id": "window.copy"},
                    {"type": "item", "action_id": "window.paste"},
                    {"type": "item", "action_id": "window.delete"},
                    {"type": "item", "action_id": "window.select_all"},
                ]
             },
            {"type": "menu", "menu_id": "window", "title": _("Window"), "items":
                [
                    {"type": "item", "action_id": "window.minimize"},
                    {"type": "separator"},
                    {"type": "item", "action_id": "window.zoom"},
                    {"type": "item", "action_id": "window.bring_to_front"},
                ]
             },
            {"type": "menu", "menu_id": "help", "title": _("Help"), "items":
                [
                ]
             },
        ]

        self.build_menu(None, typing.cast(typing.List[typing.Dict[str, typing.Any]], menu_descriptions))

    def _adjust_menus(self) -> None:
        # called when key may be shortcut. does not work for sub-menus.
        for menu in self.__document_window.menus:
            self._menu_about_to_show(menu)

    def _request_exit(self) -> None:
        if self.app:
            self.app.exit()

    @property
    def window_file_path(self) -> typing.Optional[pathlib.Path]:
        return self.__document_window.window_file_path

    @window_file_path.setter
    def window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        self.__document_window.window_file_path = value

    def request_close(self) -> None:
        self.__document_window.request_close()

    def queue_request_close(self) -> None:
        # used to request a close from inside an event loop task.
        # sets the flag and the request close will be executed during the next periodic.
        self.__request_close = True

    def _register_ui_activity(self) -> None:
        pass

    def _finish_periodic(self) -> None:
        # recognize when we're running as test and finish out periodic operations
        if not self.__document_window.has_event_loop:
            self.periodic()

    def periodic(self) -> None:
        self.__periodic_queue.perform_tasks()
        self.__periodic_set.perform_tasks()
        self.__event_loop.stop()
        self.__event_loop.run_forever()
        if self.app:
            self.app.periodic()
        # if the request close flag is set, request the close.
        # this must be at the end of periodic since it will result in the window
        # close method being called.
        if self.__request_close:
            self.request_close()

    def exec_action_events(self, event_type_str: str, **kwargs: typing.Any) -> bool:
        action_context = None
        for action in self.__modal_actions:
            if not action_context:
                action_context = self._get_action_context()
                action_context.event_type_str = event_type_str
                for k, v in kwargs.items():
                    setattr(action_context, k, v)
            action_result = action.event(action_context)
            # finished or cancelled will remove the action
            if action_result.status not in {ActionStatus.MODAL, ActionStatus.PASS}:
                self.__modal_actions.remove(action)
            # modal, finished, or cancelled will stop iterating and return True
            if action_result.status != ActionStatus.PASS:
                for report in action.reports:
                    self.display_report(report)
                return True
        # pass will return False
        return False

    def _close_dialogs(self) -> None:
        # each window may have its own dialogs, but for the most part, this is used for the top level
        # windows. request close will trigger close which will remove items from __dialogs, so be sure
        # to copy the list so that it doesn't get modified while iterating.
        for weak_dialog in list(self.__dialogs):
            dialog = typing.cast("Window", weak_dialog())
            if dialog:
                try:
                    dialog.request_close()
                except Exception:
                    pass
        self.__dialogs = list()

    def is_dialog_type_open(self, dialog_class: typing.Type[Window]) -> bool:
        for dialog_weakref in self.__dialogs:
            if isinstance(dialog_weakref(), dialog_class):
                return True
        return False

    def register_dialog(self, dialog: Window) -> None:
        old_on_close = dialog.on_close

        def close_dialog() -> None:
            self.__dialogs.remove(weakref.ref(dialog))
            if callable(old_on_close):
                old_on_close()

        dialog.on_close = close_dialog
        self.__dialogs.append(weakref.ref(dialog))

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self.__event_loop

    def attach_widget(self, widget: UserInterface.Widget) -> None:
        self.__document_window.attach(widget)

    def detach_widget(self) -> None:
        self.__document_window.detach()

    def about_to_show(self) -> None:
        if self.__persistent_id:
            geometry = self.ui.get_persistent_string("{}/Geometry".format(self.__persistent_id))
            state = self.ui.get_persistent_string("{}/State".format(self.__persistent_id))
            self.restore(geometry, state)
        self.__shown = True

    def about_to_close(self, geometry: str, state: str) -> None:
        # this method is invoked when the low level window is about to close.
        # subclasses can override this method to save geometry and state.
        if callable(self.on_close):
            self.on_close()
        # this call will close this object and subsequently the ui window, but not the low level window itself.
        # it will, however, delete the widget hierarchy as a consequence of closing the ui window.
        # so care must be taken to not close windows in cases where the widget triggering the close is still in use.
        self.close()

    def refocus_widget(self, widget: UserInterface.Widget) -> None:
        widget.refocus()

    def __save_bounds(self) -> None:
        if self.__shown and self.__persistent_id:
            geometry, state = self.save()
            self.ui.set_persistent_string("{}/Geometry".format(self.__persistent_id), geometry)
            self.ui.set_persistent_string("{}/State".format(self.__persistent_id), state)

    def activation_changed(self, activated: bool) -> None:
        pass

    def size_changed(self, width: int, height: int) -> None:
        self.__save_bounds()

    def position_changed(self, x: int, y: int) -> None:
        self.__save_bounds()

    def key_pressed(self, key: UserInterface.Key) -> bool:
        return False

    def key_released(self, key: UserInterface.Key) -> bool:
        if key.modifiers.control and key.key:
            self._adjust_menus()
        return False

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type], hot_spot_x: int, hot_spot_y: int) -> None:
        root_widget = self.__document_window.root_widget
        if root_widget:
            root_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y)

    @property
    def title(self) -> str:
        return self.__document_window.title

    @title.setter
    def title(self, value: str) -> None:
        self.__document_window.title = value

    def get_file_paths_dialog(self, title: str, directory: str, filter: str,
                              selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__document_window.get_file_paths_dialog(title, directory, filter, selected_filter)

    def get_file_path_dialog(self, title: str, directory: str, filter: str,
                             selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__document_window.get_file_path_dialog(title, directory, filter, selected_filter)

    def get_save_file_path(self, title: str, directory: str, filter: str,
                           selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        return self.__document_window.get_save_file_path(title, directory, filter, selected_filter)

    def create_dock_widget(self, widget: UserInterface.Widget, panel_id: str, title: str,
                           positions: typing.Sequence[str], position: str) -> UserInterface.DockWidget:
        return self.__document_window.create_dock_widget(widget, panel_id, title, positions, position)

    def tabify_dock_widgets(self, dock_widget1: UserInterface.DockWidget, dock_widget2: UserInterface.DockWidget) -> None:
        self.__document_window.tabify_dock_widgets(dock_widget1, dock_widget2)

    @property
    def screen_size(self) -> Geometry.IntSize:
        return self.__document_window.screen_size

    @property
    def screen_logical_dpi(self) -> float:
        return self.__document_window.screen_logical_dpi

    @property
    def screen_physical_dpi(self) -> float:
        return self.__document_window.screen_physical_dpi

    @property
    def display_scaling(self) -> float:
        return self.__document_window.display_scaling

    def get_font_metrics(self, font: str, text: str) -> UserInterface.FontMetrics:
        return self.ui.get_font_metrics(font, text)

    @property
    def focus_widget(self) -> typing.Optional[UserInterface.Widget]:
        focus_widget = self.__document_window.focus_widget
        if focus_widget:
            return focus_widget
        for dock_widget in self.dock_widgets:
            focus_widget = dock_widget.focus_widget
            if focus_widget:
                return focus_widget
        return None

    @property
    def dock_widgets(self) -> typing.Sequence[UserInterface.DockWidget]:
        return self.__document_window.dock_widgets

    def show(self, *, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        self.__document_window.show(size=size, position=position)

    def activate(self) -> None:
        self.__document_window.activate()

    def add_menu(self, title: str, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        return self.__document_window.add_menu(title, menu_id)

    def insert_menu(self, title: str, before_menu: UserInterface.Menu, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        return self.__document_window.insert_menu(title, before_menu, menu_id)

    def create_sub_menu(self, title: typing.Optional[str] = None, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        return self.ui.create_sub_menu(self.__document_window, title, menu_id)

    def create_context_menu(self) -> UserInterface.Menu:
        return self.ui.create_context_menu(self.__document_window)

    def restore(self, geometry: str, state: str) -> None:
        self.__document_window.restore(geometry, state)

    def save(self) -> typing.Tuple[str, str]:
        return self.__document_window.save()

    # tasks can be added in two ways, queued or added
    # queued tasks are guaranteed to be executed in the order queued.
    # added tasks are only executed if not replaced before execution.
    # added tasks do not guarantee execution order or execution at all.

    def add_task(self, key: str, task: typing.Callable[[], None]) -> None:
        assert task
        self.__periodic_set.add_task(key + str(id(self)), task)

    def clear_task(self, key: str) -> None:
        self.__periodic_set.clear_task(key + str(id(self)))

    def queue_task(self, task: typing.Callable[[], None]) -> None:
        assert task
        self.__periodic_queue.put(task)

    def clear_queued_tasks(self) -> None:
        self.__periodic_queue.clear_tasks()

    def handle_quit(self) -> None:
        assert self.app
        self.app.exit()

    def _dispatch_any_to_focus_widget(self, method: str, *args: typing.Any, **kwargs: typing.Any) -> bool:
        focus_widget = self.focus_widget
        if focus_widget and focus_widget._dispatch_any(method, *args, **kwargs):
            return True
        if hasattr(self, method) and getattr(self, method)(*args, **kwargs):
            return True
        return False

    def _can_dispatch_to_focus_widget(self, method: str) -> bool:
        focus_widget = self.focus_widget
        if focus_widget and focus_widget._can_dispatch_any(method):
            return True
        if hasattr(self, method):
            return True
        return False

    def build_menu(self, menu: typing.Optional[UserInterface.Menu], menu_descriptions: typing.Sequence[typing.Mapping[str, typing.Any]]) -> None:
        for item_d in menu_descriptions:
            item_type = item_d["type"]
            if item_type == "menu":
                assert menu is None
                menu_id = item_d["menu_id"]
                menu_title = item_d["title"]
                menu_items = item_d["items"]
                new_menu = self.__document_window.get_menu(menu_id)
                if not new_menu:
                    new_menu = self.add_menu(menu_title, menu_id)
                    new_menu.on_about_to_show = functools.partial(self._menu_about_to_show, new_menu)
                setattr(self, "_" + menu_id + "_menu", new_menu)
                self.build_menu(new_menu, menu_items)
            elif item_type == "item":
                action_id = item_d["action_id"]
                action = actions.get(action_id)
                if action:
                    key_sequence = action_shortcuts.get(action_id, dict()).get("window")
                    role = getattr(action, "about_role", None)
                    assert menu is not None
                    menu.add_menu_item(action.action_name, functools.partial(self.perform_action, action_id),
                                       key_sequence=key_sequence, role=role, action_id=action_id)
                else:
                    logging.debug("Unregistered action {action_id}")
            elif item_type == "separator":
                assert menu is not None
                menu.add_separator()
            elif item_type == "sub_menu":
                assert menu is not None
                menu_id = item_d["menu_id"]
                menu_title = item_d["title"]
                menu_items = item_d["items"]
                new_menu = self.create_sub_menu(menu_title, menu_id)
                menu.add_sub_menu(menu_title, new_menu)
                new_menu.on_about_to_show = functools.partial(self._menu_about_to_show, new_menu)
                # setattr(self, "_" + menu_id + "_menu", new_menu)
                self.build_menu(new_menu, menu_items)

    def _get_action_context(self) -> ActionContext:
        assert self.app
        focus_widget = self.focus_widget
        return ActionContext(self.app, self, focus_widget)

    def _apply_menu_state(self, action_id: str, action_context: ActionContext) -> None:
        menu_action = self.__document_window.get_menu_action(action_id)
        if menu_action and menu_action.action_id:
            action = actions.get(menu_action.action_id)
            if action:
                title = action.get_action_name(action_context)
                enabled = action and action.is_enabled(action_context)
                checked = action and action.is_checked(action_context)
                menu_action.apply_state(UserInterface.MenuItemState(title=title, enabled=enabled, checked=checked))

    def is_action_enabled(self, action_id: str, action_context: ActionContext) -> bool:
        action = actions.get(action_id)
        if action and action.is_enabled(action_context):
            return True
        return False

    def add_action_to_menu_if_enabled(self, menu: UserInterface.Menu, action_id: str, action_context: ActionContext) -> typing.Optional[Action]:
        action = actions.get(action_id)
        if action and action.is_enabled(action_context):
            self.add_action_to_menu(menu, action_id, action_context)
        return action

    def add_action_to_menu(self, menu: UserInterface.Menu, action_id: str, action_context: ActionContext) -> typing.Optional[Action]:
        action = actions.get(action_id)
        if action:
            key_sequence = action_shortcuts.get(action_id, dict()).get("window")
            assert menu is not None

            def perform_action() -> None:
                self.perform_action_in_context(action_id, action_context)

            def queue_perform_action() -> None:
                # delay execution to ensure menu closes properly
                # this would manifest itself by export dialog crashes in nionswift.
                self.queue_task(perform_action)

            menu_action = menu.add_menu_item(action.action_name,
                                             queue_perform_action,
                                             key_sequence=key_sequence, action_id=action_id)
            title = action.get_action_name(action_context)
            enabled = action and action.is_enabled(action_context)
            checked = action and action.is_checked(action_context)
            menu_action.apply_state(UserInterface.MenuItemState(title=title, enabled=enabled, checked=checked))
        return action

    def execute_action(self, action_id: str, action_context: typing.Optional[ActionContext] = None,
                       parameters: typing.Optional[typing.Dict[str, typing.Any]] = None) -> ActionResult:
        context = action_context or self._get_action_context()
        if parameters:
            context.parameters.update(parameters)
        action = actions[action_id]
        return action.execute(context)

    def perform_action(self, action: typing.Union[Action, str]) -> None:
        self.perform_action_in_context(action, self._get_action_context())

    def perform_action_in_context(self, action_or_action_id: typing.Union[Action, str], action_context: ActionContext) -> None:
        action: typing.Optional[Action]
        if isinstance(action_or_action_id, Action):
            action = action_or_action_id
        else:
            action = actions.get(str(action_or_action_id))
        if action and action not in self.__modal_actions:
            action.clear()
            if action.invoke(action_context).status == ActionStatus.MODAL:
                self.__modal_actions.append(action)
            for report in action.reports:
                self.display_report(report)

    def display_report(self, report: Report) -> None:
        from nion.ui import Dialog  # avoid circular reference
        if report.type == ReportType.DEBUG:
            logging.debug(report.message)
        elif report.type == ReportType.INFO:
            logging.info(report.message)
        elif report.type == ReportType.WARNING:
            logging.warning(report.message)
            Dialog.NotificationDialog(self.ui, message=f"WARNING: {report.message}", parent_window=self).show()
        elif report.type == ReportType.ERROR:
            logging.error(report.message)
            Dialog.NotificationDialog(self.ui, message=f"ERROR: {report.message}", parent_window=self).show()

    def display_log_record(self, record: logging.LogRecord) -> None:
        self.display_report(Report.from_log_record(record))

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[UserInterface.MenuItemState]:
        # if there is a specific menu item state for the command_id, use it
        # otherwise, if the handle method exists, return an enabled menu item
        # otherwise, don't handle
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = getattr(self, menu_item_state_method)()
            if menu_item_state:
                return typing.cast(UserInterface.MenuItemState, menu_item_state)
        if hasattr(self, handle_method):
            return UserInterface.MenuItemState(title=None, enabled=True, checked=False)
        return None

    def _get_focus_widget_menu_item_state(self, command_id: str) -> typing.Optional[UserInterface.MenuItemState]:
        focus_widget = self.focus_widget
        if focus_widget:
            menu_item_state = focus_widget._get_menu_item_state(command_id)
            if menu_item_state:
                return menu_item_state
        return self._get_menu_item_state(command_id)

    # standard menu items

    def _menu_about_to_show(self, menu: UserInterface.Menu) -> None:
        if self.app and self.app._menu_about_to_show(self, menu):
            pass
        elif menu.menu_id == "file":
            self._file_menu_about_to_show()
        elif menu.menu_id == "edit":
            self._edit_menu_about_to_show()
        elif menu.menu_id == "window":
            self._window_menu_about_to_show()
        # perform enable/disable/title for all menus
        action_context = self._get_action_context()
        for menu_action in menu.get_menu_actions():
            if menu_action.action_id:
                action = actions.get(menu_action.action_id)
                if action:
                    title = action.get_action_name(action_context)
                    enabled = action and action.is_enabled(action_context)
                    checked = action and action.is_checked(action_context)
                    menu_action.apply_state(UserInterface.MenuItemState(title=title, enabled=enabled, checked=checked))

    def _file_menu_about_to_show(self) -> None:
        action_context = self._get_action_context()
        self._apply_menu_state("window.close", action_context)
        self._apply_menu_state("window.page_setup", action_context)
        self._apply_menu_state("window.print", action_context)
        self._apply_menu_state("application.exit", action_context)
        # handle old style for backwards compatibility
        if self._close_action:
            self._close_action.enabled = True
        if self._page_setup_action:
            self._page_setup_action.apply_state(self._get_focus_widget_menu_item_state("page_setup"))
        if self._print_action:
            self._print_action.apply_state(self._get_focus_widget_menu_item_state("print"))
        if self._quit_action:
            self._quit_action.enabled = True

    def _edit_menu_about_to_show(self) -> None:
        action_context = self._get_action_context()
        self._apply_menu_state("window.undo", action_context)
        self._apply_menu_state("window.redo", action_context)
        self._apply_menu_state("window.cut", action_context)
        self._apply_menu_state("window.copy", action_context)
        self._apply_menu_state("window.paste", action_context)
        self._apply_menu_state("window.delete", action_context)
        self._apply_menu_state("window.select_all", action_context)
        # handle old style for backwards compatibility
        if self._undo_action:
            self._undo_action.apply_state(self._get_focus_widget_menu_item_state("undo"))
        if self._redo_action:
            self._redo_action.apply_state(self._get_focus_widget_menu_item_state("redo"))
        if self._cut_action:
            self._cut_action.apply_state(self._get_focus_widget_menu_item_state("cut"))
        if self._copy_action:
            self._copy_action.apply_state(self._get_focus_widget_menu_item_state("copy"))
        if self._paste_action:
            self._paste_action.apply_state(self._get_focus_widget_menu_item_state("paste"))
        if self._delete_action:
            self._delete_action.apply_state(self._get_focus_widget_menu_item_state("delete"))
        if self._select_all_action:
            self._select_all_action.apply_state(self._get_focus_widget_menu_item_state("select_all"))

    def _window_menu_about_to_show(self) -> None:
        action_context = self._get_action_context()
        self._apply_menu_state("window.minimize", action_context)
        self._apply_menu_state("window.zoom", action_context)
        self._apply_menu_state("window.bring_to_front", action_context)
        # handle old style for backwards compatibility
        if self._minimize_action:
            self._minimize_action.apply_state(self._get_focus_widget_menu_item_state("minimize"))
        if self._zoom_action:
            self._zoom_action.apply_state(self._get_focus_widget_menu_item_state("zoom"))
        if self._bring_to_front_action:
            self._bring_to_front_action.apply_state(self._get_focus_widget_menu_item_state("bring_to_front"))

    def _page_setup(self) -> None:
        self.perform_action("window.page_setup")

    def _print(self) -> None:
        self.perform_action("window.print")

    def _cut(self) -> None:
        self._dispatch_any_to_focus_widget("handle_cut")

    def _copy(self) -> None:
        self._dispatch_any_to_focus_widget("handle_copy")

    def _paste(self) -> None:
        self._dispatch_any_to_focus_widget("handle_paste")

    def _delete(self) -> None:
        self._dispatch_any_to_focus_widget("handle_delete")

    def _select_all(self) -> None:
        self._dispatch_any_to_focus_widget("handle_select_all")

    def _undo(self) -> None:
        self._dispatch_any_to_focus_widget("handle_undo")

    def _redo(self) -> None:
        self._dispatch_any_to_focus_widget("handle_redo")

    def _minimize(self) -> None:
        self._dispatch_any_to_focus_widget("handle_minimize")

    def _zoom(self) -> None:
        self._dispatch_any_to_focus_widget("handle_zoom")

    def _bring_to_front(self) -> None:
        self._dispatch_any_to_focus_widget("bring_to_front")


class AboutBoxAction(Action):
    action_id = "application.about"
    action_name = _("About...")
    action_role = "about"

    def execute(self, context: ActionContext) -> ActionResult:
        raise NotImplementedError()

    def invoke(self, context: ActionContext) -> ActionResult:
        show_about_box = getattr(context.window, "show_about_box", None)
        show_about_box = show_about_box or getattr(context.application, "show_about_box", None)
        if callable(show_about_box):
            show_about_box()
        return ActionResult(ActionStatus.FINISHED)


class BringToFrontAction(Action):
    action_id = "window.bring_to_front"
    action_name = _("Bring to Front")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("bring_to_front")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "bring_to_front")


class CloseWindowAction(Action):
    action_id = "window.close"
    action_name = _("Close Window")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window.request_close()
        return ActionResult(ActionStatus.FINISHED)


class CopyAction(Action):
    action_id = "window.copy"
    action_name = _("Copy")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_copy")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_copy")


class CutAction(Action):
    action_id = "window.cut"
    action_name = _("Cut")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_cut")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_cut")


class DeleteAction(Action):
    action_id = "window.delete"
    action_name = _("Delete")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_delete")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_delete")


class ExitAction(Action):
    action_id = "application.exit"
    action_name = _("Exit")
    action_role = "quit"

    def execute(self, context: ActionContext) -> ActionResult:
        context.application.exit()
        return ActionResult(ActionStatus.FINISHED)


class MinimizeAction(Action):
    action_id = "window.minimize"
    action_name = _("Minimize")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_minimize")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_minimize")


class PageSetupAction(Action):
    action_id = "window.page_setup"
    action_name = _("Page Setup")

    def execute(self, context: ActionContext) -> ActionResult:
        raise NotImplementedError()

    def invoke(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_page_setup")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_page_setup")


class PasteAction(Action):
    action_id = "window.paste"
    action_name = _("Paste")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_paste")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_paste")


class PreferencesAction(Action):
    action_id = "application.preferences"
    action_name = _("Preferences...")
    action_role = "preferences"

    def execute(self, context: ActionContext) -> ActionResult:
        raise NotImplementedError()

    def invoke(self, context: ActionContext) -> ActionResult:
        open_preferences = getattr(context.window, "open_preferences", None)
        open_preferences = open_preferences or getattr(context.application, "open_preferences", None)
        if callable(open_preferences):
            open_preferences()
        return ActionResult(ActionStatus.FINISHED)


class PrintAction(Action):
    action_id = "window.print"
    action_name = _("Print...")

    def execute(self, context: ActionContext) -> ActionResult:
        raise NotImplementedError()

    def invoke(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_print")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_print")


class RedoAction(Action):
    action_id = "window.redo"
    action_name = _("Redo")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_redo")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_redo")


class SelectAllAction(Action):
    action_id = "window.select_all"
    action_name = _("Select All")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_select_all")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        if context.window:
            return context.window._can_dispatch_to_focus_widget("handle_select_all") or hasattr(context.window, "handle_select_all")
        return False


class UndoAction(Action):
    action_id = "window.undo"
    action_name = _("Undo")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_undo")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_undo")


class ZoomAction(Action):
    action_id = "window.zoom"
    action_name = _("Zoom")

    def execute(self, context: ActionContext) -> ActionResult:
        if context.window:
            context.window._dispatch_any_to_focus_widget("handle_zoom")
        return ActionResult(ActionStatus.FINISHED)

    def is_enabled(self, context: ActionContext) -> bool:
        return hasattr(context.window, "handle_zoom")


register_action(AboutBoxAction())
register_action(BringToFrontAction())
register_action(CloseWindowAction())
register_action(CopyAction())
register_action(CutAction())
register_action(DeleteAction())
register_action(ExitAction())
register_action(MinimizeAction())
register_action(PageSetupAction())
register_action(PasteAction())
register_action(PreferencesAction())
register_action(PrintAction())
register_action(SelectAllAction())
register_action(UndoAction())
register_action(RedoAction())
register_action(ZoomAction())

action_shortcuts_dict = {
    "application.exit": {"window": "quit"},
    "window.close": {"window": "close"},
    "window.print": {"window": "Ctrl+P"},
    "window.undo": {"window": "undo"},
    "window.redo": {"window": "redo"},
    "window.cut": {"window": "cut"},
    "window.copy": {"window": "copy"},
    "window.paste": {"window": "paste"},
    "window.delete": {"window": "delete"},
    "window.select_all": {"window": "select-all"},
}

register_action_shortcuts(action_shortcuts_dict)
