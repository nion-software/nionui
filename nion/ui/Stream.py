"""
Classes related to streams of values, used for reactive style programming.
"""

# standard libraries
import concurrent.futures
import functools
import threading
import time

# third party libraries
# None

# local libraries
from nion.ui import Event


class FutureValue:
    """A future value that gets evaluated in a thread."""

    def __init__(self, evaluation_fn, *args):
        self.__evaluation_fn = functools.partial(evaluation_fn, *args)
        self.__is_evaluated = False
        self.__value = dict()
        self.__executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def close(self):
        self.__executor.shutdown()
        self.__executor = None
        self.__evaluation_fn = None

    def __evaluate(self):
        if not self.__is_evaluated:
            self.__value = self.__evaluation_fn()
            self.__is_evaluated = True

    @property
    def value(self):
        self.__evaluate()
        return self.__value

    def evaluate(self, done_fn):
        def call_done(future):
            done_fn(self.value)
        future = self.__executor.submit(self.__evaluate)
        future.add_done_callback(call_done)


class CombineLatestStream:
    """A stream that produces a tuple of values when input streams change."""

    def __init__(self, stream_list, value_fn):
        # outgoing messages
        self.value_stream = Event.Event()
        # references
        self.__stream_list = stream_list
        self.__value_fn = value_fn
        # initialize values
        self.__values = [None] * len(stream_list)
        self.__value = None
        # listen for display changes
        self.__listeners = dict()  # index
        for index, stream in enumerate(self.__stream_list):
            self.__listeners[index] = stream.value_stream.listen(functools.partial(self.__handle_stream_value, index))
            self.__values[index] = stream.value
        self.__values_changed()

    def __del__(self):
        self.close()

    def close(self):
        self.value_stream.fire(self.value)
        for index, stream in enumerate(self.__stream_list):
            self.__listeners[index].close()
            self.__values[index] = None
        self.__stream_list = None
        self.__values = None
        self.__value = None

    def __handle_stream_value(self, index, value):
        self.__values[index] = value
        self.__values_changed()

    def __values_changed(self):
        self.__value = self.__value_fn(*self.__values)
        self.value_stream.fire(self.__value)

    @property
    def value(self):
        return self.__value


class DebounceStream:
    """A stream that produces latest value after a specified interval has elapsed."""

    def __init__(self, input_stream, period):
        self.value_stream = Event.Event()
        self.__input_stream = input_stream
        self.__period = period
        self.__last_time = 0
        self.__value = None
        self.__executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.__listener = input_stream.value_stream.listen(self.__value_changed)
        self.__value_changed(input_stream.value)

    def __del__(self):
        self.close()

    def close(self):
        self.__listener.close()
        self.__listener = None
        self.__input_stream = None
        self.__executor.shutdown()
        self.__executor = None

    def __value_changed(self, value):
        self.__value = value
        current_time = time.time()
        if current_time - self.__last_time > self.__period:
            def do_sleep():
                time.sleep(self.__period)
            def call_done(future):
                self.value_stream.fire(self.__value)
            self.__last_time = current_time
            future = self.__executor.submit(do_sleep)
            future.add_done_callback(call_done)

    @property
    def value(self):
        return self.__value


class SampleStream:
    """A stream that produces new values at a specified interval."""

    def __init__(self, input_stream, period):
        self.value_stream = Event.Event()
        self.__input_stream = input_stream
        self.__period = period
        self.__last_time = 0
        self.__pending_value = None
        self.__value = None
        self.__executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.__executor_lock = threading.RLock()
        self.__listener = input_stream.value_stream.listen(self.__value_changed)
        self.__value = input_stream.value
        self.__value_dirty = True
        self.__value_dirty_lock = threading.RLock()
        self.__queue_executor()

    def __del__(self):
        self.close()

    def close(self):
        self.__listener.close()
        self.__listener = None
        self.__input_stream = None
        with self.__executor_lock:  # deadlock?
            self.__executor.shutdown()
            self.__executor = None

    def __do_sleep(self):
        time.sleep(self.__period)

    def __call_done(self, future):
        with self.__value_dirty_lock:
            value_dirty = self.__value_dirty
            self.__value_dirty = False
        if value_dirty:
            self.__value = self.__pending_value
            self.value_stream.fire(self.__pending_value)
        self.__queue_executor()

    def __queue_executor(self):
        with self.__executor_lock:
            future = self.__executor.submit(self.__do_sleep)
            future.add_done_callback(self.__call_done)

    def __value_changed(self, value):
        with self.__value_dirty_lock:
            self.__value_dirty = True
        self.__pending_value = value

    @property
    def value(self):
        return self.__value
