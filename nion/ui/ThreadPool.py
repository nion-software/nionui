"""
Useful classes for handling threads.
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
import copy
import logging
import threading
import time

# conditional imports
import sys
if sys.version < '3':
    import Queue as queue
else:
    import queue

# third party libraries
# None

# local libraries
# None


class ThreadDispatcher(object):

    """
        Invoke fn when trigger is called. Minimum interval
        limits how often the fn will be invoked.
    """

    def __init__(self, fn, minimum_interval=0.001):
        self.__fn = fn
        self.__thread_break = False
        self.__thread_ended_event = threading.Event()
        self.__thread_event = threading.Event()
        self.__triggered_event = threading.Event()
        self.__thread_lock = threading.Lock()
        self.__thread = threading.Thread(target=self.__process)
        self.__thread.daemon = True
        self.__minimum_interval = minimum_interval
        self.__last_time = 0

    def start(self):
        self.__thread.start()

    def close(self):
        with self.__thread_lock:
            self.__thread_break = True
            self.__thread_event.set()
        self.__thread_ended_event.wait()
        self.__thread.join()
        self.__thread = None
        self.__fn = None

    def trigger(self, wait=False):
        if wait:
            with self.__thread_lock:
                self.__triggered_event.clear()
                self.__thread_event.set()
            self.__triggered_event.wait()
        else:
            self.__thread_event.set()

    def __process(self):
        while True:
            self.__thread_event.wait()
            with self.__thread_lock:
                self.__thread_event.clear()  # put this inside lock to avoid race condition
            if self.__thread_break:
                break
            thread_event_set = False
            while not self.__thread_break:
                elapsed = time.time() - self.__last_time
                if self.__minimum_interval and elapsed < self.__minimum_interval:
                    if self.__thread_event.wait(self.__minimum_interval - elapsed):
                        thread_event_set = True  # set this so that we know to set it after this loop
                    self.__thread_event.clear()  # clear this so that it doesn't immediately trigger again
                else:
                    break
            if thread_event_set:
                self.__thread_event.set()
            if self.__thread_break:
                break
            try:
                self.__fn()
                self.__triggered_event.set()
            except Exception as e:
                import traceback
                logging.debug("Processing thread exception %s", e)
                traceback.print_exc()
                traceback.print_stack()
            self.__last_time = time.time()
        self.__thread_ended_event.set()


class ThreadPoolTask(object):
    """
        Execute a task once. The task may be canceled but if it is already
        in progress, canceling will wait until it finishes.
    """

    def __init__(self, fn, finished_fn, description):
        self.__description = description if description else str()
        self.__fn = fn
        self.__finished_fn = finished_fn
        self.__lock = threading.RLock()

    def cancel(self):
        #logging.debug("Task cancel - %s", self)
        with self.__lock:
            #logging.debug("Task cancel + %s", self)
            if self.__fn:
                self.__fn = None
                self.__finished_fn(self)

    def execute(self):
        # logging.debug("Task execute - %s %s", self, self.__description)
        with self.__lock:
            # logging.debug("Task execute + %s", self)
            if self.__fn:
                try:
                    self.__fn()
                except Exception as e:
                    import traceback
                    logging.debug("Task thread exception %s", e)
                    traceback.print_exc()
                    traceback.print_stack()
                self.__fn = None
                self.__finished_fn(self)
            # logging.debug("Task execute ++ %s", self)


class ThreadPool(object):

    def __init__(self):
        self.__closed = False
        self.__queue = queue.Queue()
        self.__threads = list()
        self.__lock = threading.RLock()
        self.__tasks = list()

    def close(self):
        with self.__lock:
            self.__closed = True
            tasks = copy.copy(self.__tasks)
        for task in tasks:
            task.cancel()
        for _ in self.__threads:
            self.__queue.put(None)
        if len(self.__threads) > 0:
            self.__queue.join()

    def start(self, thread_count=16):
        for _ in range(thread_count):
            thread = threading.Thread(target=self.__run)
            thread.daemon = True
            thread.start()
            self.__threads.append(thread)

    def queue_fn(self, fn, description=None):
        with self.__lock:
            if not self.__closed:
                def remove_task(task):
                    with self.__lock:
                        self.__tasks.remove(task)
                task = ThreadPoolTask(fn, remove_task, description)
                self.__tasks.append(task)
                self.__queue.put(task)

    def __run(self):
        while True:
            task = self.__queue.get()
            if task and not self.__closed:
                task.execute()
            self.__queue.task_done()
            if not task:
                break

    def run_all(self):
        while not self.__queue.empty():
            task = self.__queue.get()
            if task and not self.__closed:
                task.execute()
            self.__queue.task_done()
            if not task:
                break
