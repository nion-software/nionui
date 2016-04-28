"""
A basic class to serve as the document controller of a typical one window application.
"""

# futures
from __future__ import absolute_import

# standard libraries
# None

# local libraries
from nion.utils import Process


class DocumentController(object):

    def __init__(self, ui, app=None):
        self.ui = ui
        self.app = app
        self.document_window = self.ui.create_document_window()
        self.document_window.on_periodic = self.periodic
        self.document_window.on_queue_task = self.queue_task
        self.document_window.on_add_task = self.add_task
        self.document_window.on_clear_task = self.clear_task
        self.document_window.on_about_to_show = self.about_to_show
        self.document_window.on_about_to_close = self.about_to_close
        self.document_window.title = "Hello World"
        self.__periodic_queue = Process.TaskQueue()
        self.__periodic_set = Process.TaskSet()

    def close(self):
        self.ui.destroy_document_window(self.document_window)
        self.document_window = None

    def about_to_show(self):
        pass

    def about_to_close(self, geometry, state):
        self.close()

    def add_task(self, key, task):
        self.__periodic_set.add_task(key + str(id(self)), task)

    def clear_task(self, key):
        self.__periodic_set.clear_task(key + str(id(self)))

    def queue_task(self, task):
        self.__periodic_queue.put(task)

    def periodic(self):
        self.__periodic_queue.perform_tasks()
        self.__periodic_set.perform_tasks()

    def handle_quit(self):
        self.app.exit()