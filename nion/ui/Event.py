"""
An event object to which to attach listeners.
"""

# futures
from __future__ import absolute_import

# standard libraries
import logging
import threading
import weakref

# third party libraries
# None

# local libraries
# None


class EventListener(object):

    def __init__(self, listener_fn):
        self.__listener_fn = listener_fn
        # the call function is very performance critical; make it fast by using a property
        # instead of a method lookup.
        if listener_fn:
            self.call = self.__listener_fn
        else:
            def void(*args, **kwargs):
                pass
            self.call = void

    def close(self):
        self.__listener_fn = None
        def void(*args, **kwargs):
            pass
        self.call = void


class Event(object):
    """An event object that to which listeners can be attached."""

    # TODO: add events to this object itself to indicate a listener being added or removed
    # this would facilitate the ability to only listen to _another_ object if the object embedding
    # this event had listeners.

    def __init__(self):
        self.__weak_listeners = []
        self.__weak_listeners_mutex = threading.RLock()

    def listen(self, listener_fn):
        """Add a listener function and return listener token. Token can be closed or deleted to unlisten."""
        listener = EventListener(listener_fn)
        def remove_listener(weak_listener):
            with self.__weak_listeners_mutex:
                self.__weak_listeners.remove(weak_listener)
        weak_listener = weakref.ref(listener, remove_listener)
        with self.__weak_listeners_mutex:
            self.__weak_listeners.append(weak_listener)
        return listener

    def fire(self, *args, **keywords):
        """Calls listeners (in order added) unconditionally."""
        try:
            with self.__weak_listeners_mutex:
                listeners = [weak_listener() for weak_listener in self.__weak_listeners]
            for listener in listeners:
                if listener:
                    listener.call(*args, **keywords)
        except Exception as e:
            import traceback
            logging.debug("Event Error: %s", e)
            traceback.print_exc()
            traceback.print_stack()

    def fire_any(self, *args, **keywords):
        """Calls listeners (in order added) until one returns True or else return False."""
        try:
            with self.__weak_listeners_mutex:
                listeners = [weak_listener() for weak_listener in self.__weak_listeners]
            for listener in listeners:
                if listener:
                    if listener.call(*args, **keywords):
                        return True
            return False
        except Exception as e:
            import traceback
            logging.debug("Event Error: %s", e)
            traceback.print_exc()
            traceback.print_stack()

    def fire_all(self, *args, **keywords):
        """Calls listeners (in order added) until one returns False or else return True."""
        try:
            with self.__weak_listeners_mutex:
                listeners = [weak_listener() for weak_listener in self.__weak_listeners]
            for listener in listeners:
                if listener:
                    if not listener.call(*args, **keywords):
                        return False
            return True
        except Exception as e:
            import traceback
            logging.debug("Event Error: %s", e)
            traceback.print_exc()
            traceback.print_stack()
