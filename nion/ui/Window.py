"""
A basic class to serve as the document controller of a typical one window application.
"""

# standard libraries
import asyncio
import gettext
import logging
import typing

# local libraries
from nion.utils import Geometry
from nion.utils import Process
from nion.ui import UserInterface


_ = gettext.gettext


class Window:

    def __init__(self, ui: UserInterface.UserInterface, app=None, parent_window=None, window_style=None, persistent_id=None):
        self.ui = ui
        self.app = app
        self.on_close = None
        parent_window = parent_window._document_window if parent_window else None
        self.__document_window = self.ui.create_document_window(parent_window=parent_window)
        if window_style:
            self.__document_window.window_style = window_style
        self.__persistent_id = persistent_id
        self.__shown = False
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
        # configure the event loop object
        logger = logging.getLogger()
        old_level = logger.level
        logger.setLevel(logging.INFO)
        self.__event_loop = asyncio.new_event_loop()  # outputs a debugger message!
        logger.setLevel(old_level)

    def close(self):
        self.on_close = None
        Process.close_event_loop(self.__event_loop)
        self.__event_loop = None
        self.ui.destroy_document_window(self.__document_window)  # close the ui window
        self.__document_window = None
        self.__periodic_queue = None
        self.__periodic_set = None

    @property
    def _document_window(self):
        # for testing only
        return self.__document_window

    def _create_menus(self):
        self._file_menu = self.add_menu(_("File"))
        self._edit_menu = self.add_menu(_("Edit"))
        self._window_menu = self.add_menu(_("Window"))
        self._help_menu = self.add_menu(_("Help"))

        self._close_action = self._file_menu.add_menu_item(_("Close Window"), self.request_close, key_sequence="close")
        self._file_menu.add_separator()
        self._page_setup_action = self._file_menu.add_menu_item(_("Page Setup"), self._page_setup)
        self._print_action = self._file_menu.add_menu_item(_("Print"), self._print, key_sequence="Ctrl+P")
        self._file_menu.add_separator()
        self._quit_action = self._file_menu.add_menu_item(_("Exit"), self._request_exit, key_sequence="quit", role="quit")

        self._undo_action = self._edit_menu.add_menu_item(_("Undo"), self._undo, key_sequence="undo")
        self._redo_action = self._edit_menu.add_menu_item(_("Redo"), self._redo, key_sequence="redo")
        self._edit_menu.add_separator()
        self._cut_action = self._edit_menu.add_menu_item(_("Cut"), self._cut, key_sequence="cut")
        self._copy_action = self._edit_menu.add_menu_item(_("Copy"), self._copy, key_sequence="copy")
        self._paste_action = self._edit_menu.add_menu_item(_("Paste"), self._paste, key_sequence="paste")
        self._delete_action = self._edit_menu.add_menu_item(_("Delete"), self._delete, key_sequence="delete")
        self._select_all_action = self._edit_menu.add_menu_item(_("Select All"), self._select_all, key_sequence="select-all")
        self._edit_menu.add_separator()

        self._minimize_action = self._window_menu.add_menu_item(_("Minimize"), self._minimize)
        self._zoom_action = self._window_menu.add_menu_item(_("Zoom"), self._zoom)
        self._bring_to_front_action = self._window_menu.add_menu_item(_("Bring to Front"), self._bring_to_front)

        self._file_menu.on_about_to_show = self._file_menu_about_to_show
        self._edit_menu.on_about_to_show = self._edit_menu_about_to_show
        self._window_menu.on_about_to_show = self._window_menu_about_to_show

    def _adjust_menus(self) -> None:
        # called when key may be shortcut
        self._file_menu_about_to_show()
        self._edit_menu_about_to_show()
        self._window_menu_about_to_show()

    def _request_exit(self) -> None:
        if self.app:
            self.app.exit()

    def request_close(self) -> None:
        self.__document_window.request_close()

    def _register_ui_activity(self) -> None:
        pass

    def finish_periodic(self) -> None:
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

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self.__event_loop

    def attach_widget(self, widget):
        self.__document_window.attach(widget)

    def detach_widget(self):
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

    def refocus_widget(self, widget):
        widget.refocus()

    def __save_bounds(self):
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

    def drag(self, mime_data: UserInterface.MimeData, thumbnail, hot_spot_x, hot_spot_y) -> None:
        self.__document_window.root_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y)

    @property
    def title(self) -> str:
        return self.__document_window.title

    @title.setter
    def title(self, value: str) -> None:
        self.__document_window.title = value

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: str=None) -> (typing.List[str], str, str):
        return self.__document_window.get_file_paths_dialog(title, directory, filter, selected_filter)

    def get_file_path_dialog(self, title, directory, filter, selected_filter=None):
        return self.__document_window.get_file_path_dialog(title, directory, filter, selected_filter)

    def get_save_file_path(self, title, directory, filter, selected_filter=None):
        return self.__document_window.get_save_file_path(title, directory, filter, selected_filter)

    def create_dock_widget(self, widget, panel_id, title, positions, position):
        return self.__document_window.create_dock_widget(widget, panel_id, title, positions, position)

    def tabify_dock_widgets(self, dock_widget1, dock_widget2):
        return self.__document_window.tabify_dock_widgets(dock_widget1, dock_widget2)

    @property
    def screen_size(self):
        return self.__document_window.screen_size

    @property
    def screen_logical_dpi(self):
        return self.__document_window.screen_logical_dpi

    @property
    def screen_physical_dpi(self):
        return self.__document_window.screen_physical_dpi

    @property
    def display_scaling(self):
        return self.__document_window.display_scaling

    def get_font_metrics(self, font, text):
        return self.ui.get_font_metrics(font, text)

    @property
    def focus_widget(self):
        focus_widget = self.__document_window.focus_widget
        if focus_widget:
            return focus_widget
        for dock_widget in self.dock_widgets:
            focus_widget = dock_widget.focus_widget
            if focus_widget:
                return focus_widget
        return None

    @property
    def dock_widgets(self):
        return self.__document_window.dock_widgets

    def show(self, *, size: Geometry.IntSize=None, position: Geometry.IntPoint=None) -> None:
        self.__document_window.show(size=size, position=position)

    def add_menu(self, title: str):
        return self.__document_window.add_menu(title)

    def insert_menu(self, title: str, before_menu):
        return self.__document_window.insert_menu(title, before_menu)

    def create_sub_menu(self):
        return self.ui.create_sub_menu(self.__document_window)

    def create_context_menu(self):
        return self.ui.create_context_menu(self.__document_window)

    def restore(self, geometry: str, state: str) -> None:
        self.__document_window.restore(geometry, state)

    def save(self) -> (str, str):
        return self.__document_window.save()

    # tasks can be added in two ways, queued or added
    # queued tasks are guaranteed to be executed in the order queued.
    # added tasks are only executed if not replaced before execution.
    # added tasks do not guarantee execution order or execution at all.

    def add_task(self, key, task):
        assert task
        self.__periodic_set.add_task(key + str(id(self)), task)

    def clear_task(self, key):
        self.__periodic_set.clear_task(key + str(id(self)))

    def queue_task(self, task):
        assert task
        self.__periodic_queue.put(task)

    def clear_queued_tasks(self):
        self.__periodic_queue.clear_tasks()

    def handle_quit(self):
        self.app.exit()

    def _dispatch_any_to_focus_widget(self, method: str, *args, **kwargs) -> bool:
        focus_widget = self.focus_widget
        if focus_widget and focus_widget._dispatch_any(method, *args, **kwargs):
                return True
        if hasattr(self, method) and getattr(self, method)(*args, **kwargs):
                return True
        return False

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[UserInterface.MenuItemState]:
        # if there is a specific menu item state for the command_id, use it
        # otherwise, if the handle method exists, return an enabled menu item
        # otherwise, don't handle
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = getattr(self, menu_item_state_method)()
            if menu_item_state:
                return menu_item_state
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

    def _file_menu_about_to_show(self):
        self._close_action.enabled = True
        self._page_setup_action.apply_state(self._get_focus_widget_menu_item_state("page_setup"))
        self._print_action.apply_state(self._get_focus_widget_menu_item_state("print"))
        self._quit_action.enabled = True

    def _edit_menu_about_to_show(self):
        self._undo_action.apply_state(self._get_focus_widget_menu_item_state("undo"))
        self._redo_action.apply_state(self._get_focus_widget_menu_item_state("redo"))
        self._cut_action.apply_state(self._get_focus_widget_menu_item_state("cut"))
        self._copy_action.apply_state(self._get_focus_widget_menu_item_state("copy"))
        self._paste_action.apply_state(self._get_focus_widget_menu_item_state("paste"))
        self._delete_action.apply_state(self._get_focus_widget_menu_item_state("delete"))
        self._select_all_action.apply_state(self._get_focus_widget_menu_item_state("select_all"))

    def _window_menu_about_to_show(self):
        self._minimize_action.apply_state(self._get_focus_widget_menu_item_state("minimize"))
        self._zoom_action.apply_state(self._get_focus_widget_menu_item_state("zoom"))
        self._bring_to_front_action.apply_state(self._get_focus_widget_menu_item_state("bring_to_front"))

    def _page_setup(self):
        self._dispatch_any_to_focus_widget("handle_page_setup")

    def _print(self):
        self._dispatch_any_to_focus_widget("handle_print")

    def _cut(self):
        self._dispatch_any_to_focus_widget("handle_cut")

    def _copy(self):
        self._dispatch_any_to_focus_widget("handle_copy")

    def _paste(self):
        self._dispatch_any_to_focus_widget("handle_paste")

    def _delete(self):
        self._dispatch_any_to_focus_widget("handle_delete")

    def _select_all(self):
        self._dispatch_any_to_focus_widget("handle_select_all")

    def _undo(self):
        self._dispatch_any_to_focus_widget("handle_undo")

    def _redo(self):
        self._dispatch_any_to_focus_widget("handle_redo")

    def _minimize(self):
        self._dispatch_any_to_focus_widget("handle_minimize")

    def _zoom(self):
        self._dispatch_any_to_focus_widget("handle_zoom")

    def _bring_to_front(self):
        self._dispatch_any_to_focus_widget("bring_to_front")
