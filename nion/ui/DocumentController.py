"""
A basic class to serve as the document controller of a typical one window application.
"""

# standard libraries
import typing

# local libraries
from nion.utils import Process


class DocumentController:

    def __init__(self, ui, app=None, window_style=None):
        self.ui = ui
        self.app = app
        self.__document_window = self.ui.create_document_window()
        if window_style:
            self.__document_window.window_style = window_style
        self.__document_window.on_periodic = self.periodic
        self.__document_window.on_queue_task = self.queue_task
        self.__document_window.on_add_task = self.add_task
        self.__document_window.on_clear_task = self.clear_task
        self.__document_window.on_about_to_show = self.about_to_show
        self.__document_window.on_about_to_close = self.about_to_close
        self.__document_window.on_activation_changed = self.activation_changed
        self.__periodic_queue = Process.TaskQueue()
        self.__periodic_set = Process.TaskSet()

    def close(self):
        self.ui.destroy_document_window(self.__document_window)
        self.__document_window = None
        self.__periodic_queue = None
        self.__periodic_set = None

    @property
    def _document_window(self):
        # for testing only
        return self.__document_window

    def request_close(self) -> None:
        self.__document_window.request_close()

    def finish_periodic(self) -> None:
        # recognize when we're running as test and finish out periodic operations
        if not self.__document_window.has_event_loop:
            self.periodic()

    def periodic(self) -> None:
        self.__periodic_queue.perform_tasks()
        self.__periodic_set.perform_tasks()

    def attach_widget(self, widget):
        self.__document_window.attach(widget)

    def detach_widget(self):
        self.__document_window.detach()

    def about_to_show(self) -> None:
        pass

    def about_to_close(self, geometry: str, state: str) -> None:
        # subclasses can override this method to save geometry and state
        # subclasses can also cancel closing by not calling super() (or close()).
        self.close()

    def activation_changed(self, activated: bool) -> None:
        pass

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

    def show(self) -> None:
        self.__document_window.show()

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

    def add_task(self, key, task):
        self.__periodic_set.add_task(key + str(id(self)), task)

    def clear_task(self, key):
        self.__periodic_set.clear_task(key + str(id(self)))

    def queue_task(self, task):
        self.__periodic_queue.put(task)

    def handle_quit(self):
        self.app.exit()
