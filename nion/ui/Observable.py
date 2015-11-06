"""
A collection of observation and event classes.
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


class Broadcaster(object):

    def __init__(self):
        super(Broadcaster, self).__init__()
        self.__weak_listeners = []
        self.__weak_listeners_mutex = threading.RLock()

    # Add a listener.
    def add_listener(self, listener):
        with self.__weak_listeners_mutex:
            assert listener is not None
            def remove_listener(weak_listener):
                with self.__weak_listeners_mutex:
                    self.__weak_listeners.remove(weak_listener)
            self.__weak_listeners.append(weakref.ref(listener, remove_listener))

    # Remove a listener.
    def remove_listener(self, listener):
        with self.__weak_listeners_mutex:
            assert listener is not None
            self.__weak_listeners.remove(weakref.ref(listener))

    # Send a message to the listeners
    def notify_listeners(self, fn, *args, **keywords):
        try:
            with self.__weak_listeners_mutex:
                listeners = [weak_listener() for weak_listener in self.__weak_listeners]
            for listener in listeners:
                if hasattr(listener, fn):
                    getattr(listener, fn)(*args, **keywords)
        except Exception as e:
            import traceback
            logging.debug("Notify Error: %s", e)
            traceback.print_exc()
            traceback.print_stack()


class Subscription(object):

    def __init__(self, publisher, subscriber, closer):
        self.__publisher = publisher
        self.subscriber = subscriber
        self.__closer = closer

    def close(self):
        if self.__closer:
            self.__closer(weakref.ref(self))
            self.__publisher = None
            self.subscriber = None
            self.__closer = None


class Publisher(object):

    def __init__(self):
        super(Publisher, self).__init__()
        self.__weak_subscriptions = []
        self.__weak_subscriptions_mutex = threading.RLock()
        self.on_subscribe = None

    def close(self):
        self.on_subscribe = None

    @property
    def _subscriptions(self):
        """Return the subscriptions list. Useful for debugging."""
        with self.__weak_subscriptions_mutex:
            return [weak_subscription() for weak_subscription in self.__weak_subscriptions]

    # Add a listener.
    def subscribex(self, subscriber):
        with self.__weak_subscriptions_mutex:
            assert subscriber is not None
            assert isinstance(subscriber, Subscriber)
            subscription = Subscription(self, subscriber, self.__unsubscribe)
            self.__weak_subscriptions.append(weakref.ref(subscription, self.__unsubscribe))
        if self.on_subscribe:  # outside of lock
            self.on_subscribe(subscriber)
        return subscription

    def __unsubscribe(self, weak_subscription):
        with self.__weak_subscriptions_mutex:
            if weak_subscription in self.__weak_subscriptions:
                self.__weak_subscriptions.remove(weak_subscription)

    # Send a message to the listeners
    def __notify_subscribers(self, fn, subscriber1, *args, **keywords):
        try:
            with self.__weak_subscriptions_mutex:
                subscriptions = [weak_subscription() for weak_subscription in self.__weak_subscriptions]
            for subscription in subscriptions:
                subscriber = subscription.subscriber
                if hasattr(subscriber, fn) and (subscriber1 is None or subscriber == subscriber1):
                    getattr(subscriber, fn)(*args, **keywords)
        except Exception as e:
            import traceback
            logging.debug("Notify Subscription Error: %s", e)
            traceback.print_exc()
            traceback.print_stack()

    def notify_next_value(self, value, subscriber=None):
        self.__notify_subscribers("publisher_next_value", subscriber, value)

    def notify_error(self, exception, subscriber=None):
        self.__notify_subscribers("publisher_error", subscriber, exception)

    def notify_complete(self, subscriber=None):
        self.__notify_subscribers("publisher_complete", subscriber)

    def select(self, select_fn):
        return PublisherSelect(self, select_fn)

    def cache(self):
        return PublisherCache(self)


class PublisherSelect(Publisher):

    def __init__(self, publisher, select_fn):
        super(PublisherSelect, self).__init__()
        self.__select_fn = select_fn
        self.__last_value = None
        def next_value(value):
            self.__last_value = self.__select_fn(value)
            self.notify_next_value(self.__last_value)
        self.__subscription = publisher.subscribex(Subscriber(next_value))

    def close(self):
        self.__subscription.close()
        self.__subscription = None
        self.__select_fn = None
        self.__last_value = None
        super(PublisherSelect, self).close()

    def subscribex(self, subscriber):
        subscription = super(PublisherSelect, self).subscribex(subscriber)
        if self.__last_value:
            self.notify_next_value(self.__last_value)
        return  subscription


class PublisherCache(Publisher):

    def __init__(self, publisher):
        super(PublisherCache, self).__init__()
        self.__cached_value = None
        def next_value(value):
            if value != self.__cached_value:
                self.notify_next_value(value)
                self.__cached_value = value
        self.__subscription = publisher.subscribex(Subscriber(next_value))

    def close(self):
        self.__subscription.close()
        self.__subscription = None
        self.__cached_value = None
        super(PublisherCache, self).close()

    def subscribex(self, subscriber):
        subscription = super(PublisherCache, self).subscribex(subscriber)
        if self.__cached_value:
            self.notify_next_value(self.__cached_value)
        return subscription


class Subscriber(object):

    def __init__(self, next_fn=None, error_fn=None, complete_fn=None):
        self.__next_fn = next_fn
        self.__error_fn = error_fn
        self.__complete_fn = complete_fn

    def publisher_next_value(self, value):
        if self.__next_fn:
            self.__next_fn(value)

    def publisher_error(self, exception):
        if self.__error_fn:
            self.__error_fn(exception)

    def publisher_complete(self):
        if self.__complete_fn:
            self.__complete_fn()


class Observable(object):

    """
        Provide basic observable object. Sub classes should implement properties,
        items, and collections and call appropriate notifications when necessary.
    """

    def __init__(self):
        super(Observable, self).__init__()
        self.__weak_observers = list()

    def add_observer(self, observer):
        def remove_observer(weak_observer):
            self.__weak_observers.remove(weak_observer)
        weak_observer = weakref.ref(observer, remove_observer)
        # an observer can be added more than once
        self.__weak_observers.append(weak_observer)

    def remove_observer(self, observer):
        weak_observer = weakref.ref(observer)
        # when removing an observer, it should already be in the list
        assert weak_observer in self.__weak_observers
        self.__weak_observers.remove(weak_observer)

    def get_observer_count(self, observer):
        return self.__weak_observers.count(weakref.ref(observer))

    @property
    def observers(self):
        return [weak_observer() for weak_observer in self.__weak_observers]

    def notify_set_property(self, key, value):
        for weak_observer in set(self.__weak_observers):  # call each observer only once
            observer = weak_observer()
            if observer and getattr(observer, "property_changed", None):
                observer.property_changed(self, key, value)

    def notify_set_item(self, key, item):
        for weak_observer in set(self.__weak_observers):  # call each observer only once
            observer = weak_observer()
            if observer and getattr(observer, "item_set", None):
                observer.item_set(self, key, item)

    def notify_clear_item(self, key):
        for weak_observer in set(self.__weak_observers):  # call each observer only once
            observer = weak_observer()
            if observer and getattr(observer, "item_cleared", None):
                observer.item_cleared(self, key)

    def notify_insert_item(self, key, value, before_index):
        for weak_observer in set(self.__weak_observers):  # call each observer only once
            observer = weak_observer()
            if observer and getattr(observer, "item_inserted", None):
                observer.item_inserted(self, key, value, before_index)

    def notify_remove_item(self, key, value, index):
        for weak_observer in set(self.__weak_observers):  # call each observer only once
            observer = weak_observer()
            if observer and getattr(observer, "item_removed", None):
                observer.item_removed(self, key, value, index)


class ReferenceCounted(object):

    def __init__(self):
        super(ReferenceCounted, self).__init__()
        self.__ref_count = 0
        self.__ref_count_mutex = threading.RLock()  # access to the image
        self.__active = True

    # Give subclasses a chance to clean up. This gets called when reference
    # count goes to 0, but before deletion.
    def about_to_delete(self):
        pass

    def ref(self):
        class RefContextManager(object):
            def __init__(self, item):
                self.__item = item
            def __enter__(self):
                self.__item.add_ref()
                return self
            def __exit__(self, type, value, traceback):
                self.__item.remove_ref()
        return RefContextManager(self)

    # Anytime you store a reference to this item, call add_ref.
    # This allows the class to disconnect from its own sources
    # automatically when the reference count goes to zero.
    def add_ref(self):
        with self.__ref_count_mutex:
            self.__ref_count += 1

    # Anytime you give up a reference to this item, call remove_ref.
    def remove_ref(self, check=True):
        with self.__ref_count_mutex:
            assert self.__ref_count > 0, 'DataItem has no references'
            self.__ref_count -= 1
            if self.__active and self.__ref_count == 0 and check:
                self.__active = False
                self.about_to_delete()

    # Return the reference count, which should represent the number
    # of places that this DataItem is stored by a caller.
    @property
    def ref_count(self):
        return self.__ref_count
