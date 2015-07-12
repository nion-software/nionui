"""
A collection of observation and event classes.
"""

# futures
from __future__ import absolute_import

# standard libraries
import copy
import datetime
import logging
import re
import threading
import weakref
import uuid

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
        pass

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

    def __get_observers(self):
        return [weak_observer() for weak_observer in self.__weak_observers]
    observers = property(__get_observers)

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
    def __get_ref_count(self):
        return self.__ref_count
    ref_count = property(__get_ref_count)


class ManagedProperty(object):

    """
        Represents a managed property.

        converter converts from value to json value
    """

    def __init__(self, name, value=None, make=None, read_only=False, hidden=False, validate=None, converter=None, changed=None, key=None, reader=None, writer=None):
        super(ManagedProperty, self).__init__()
        self.name = name
        self.key = key if key else name
        self.value = value
        self.make = make
        self.read_only = read_only
        self.hidden= hidden
        self.validate = validate
        self.converter = converter
        self.reader = reader
        self.writer = writer
        self.convert_get_fn = converter.convert if converter else copy.deepcopy  # optimization
        self.convert_set_fn = converter.convert_back if converter else lambda value: value  # optimization
        self.changed = changed

    def set_value(self, value):
        if self.validate:
            value = self.validate(value)
        else:
            value = copy.deepcopy(value)
        self.value = value
        if self.changed:
            self.changed(self.name, value)

    def __get_json_value(self):
        return self.convert_get_fn(self.value)
    def __set_json_value(self, json_value):
        self.set_value(self.convert_set_fn(json_value))
    json_value = property(__get_json_value, __set_json_value)

    def read_from_dict(self, properties):
        if self.reader:
            value = self.reader(self, properties)
            if value is not None:
                self.set_value(value)
        else:
            if self.key in properties:
                if self.make:
                    value = self.make()
                    value.read_dict(properties[self.key])
                    self.set_value(value)
                else:
                    self.json_value = properties[self.key]

    def write_to_dict(self, properties):
        if self.writer:
            self.writer(self, properties, self.value)
        else:
            if self.make:
                value = self.value
                if value is not None:
                    value_dict = value.write_dict()
                    properties[self.key] = value_dict
                else:
                    properties.pop(self.key, None)  # remove key
            else:
                properties[self.key] = self.json_value


class ManagedItem(object):

    def __init__(self, name, factory, item_changed=None):
        super(ManagedItem, self).__init__()
        self.name = name
        self.factory = factory
        self.item_changed = item_changed
        self.value = None


class ManagedRelationship(object):

    def __init__(self, name, factory, insert=None, remove=None):
        super(ManagedRelationship, self).__init__()
        self.name = name
        self.factory = factory
        self.insert = insert
        self.remove = remove
        self.values = list()


class ManagedObjectContext(object):

    """
        Manages a collection of managed objects.

        All objects participating in the document model should register themselves
        with this context. Other objects can then subscribe and unsubscribe to
        know when a particular object (identified by uuid) becomes available or
        unavailable. This facilitates lazy connections between objects.
    """

    def __init__(self):
        self.__subscriptions = dict()
        self.__objects = dict()
        self.__persistent_storages = dict()

    def register(self, object):
        """
            Register an object with the managed object context.

            :param object: an object with a uuid property

            Objects will be automatically unregistered when they are garbage
            collected.
        """
        object_uuid = object.uuid
        def remove_object(weak_object):
            object = self.__objects[object_uuid]
            for registered, unregistered in self.__subscriptions.get(object_uuid, list()):
                if unregistered:
                    unregistered(object)
            del self.__objects[object_uuid]
            self.__subscriptions.pop(object_uuid, None)  # delete if it exists
        weak_object = weakref.ref(object, remove_object)
        self.__objects[object_uuid] = weak_object
        for registered, unregistered in self.__subscriptions.get(object_uuid, list()):
            if registered:
                registered(object)

    def subscribe(self, uuid_, registered, unregistered):
        """
            Subscribe to a particular object being registered or unregistered.

            :param uuid_: the uuid of the object to subscribe to
            :param registered: a function taking one parameter (the object) to be called when the object gets registered
            :param unregistered: a function taking one parameter (the object) to be called when the object gets unregistered

            If the object is already registered, registered will be invoked immediately.
        """
        self.__subscriptions.setdefault(uuid_, list()).append((registered, unregistered))
        weak_object = self.__objects.get(uuid_)
        object = weak_object and weak_object()
        if object is not None:
            registered(object)

    def set_persistent_storage_for_object(self, object, persistent_storage):
        def remove_object(weak_object):
            del self.__persistent_storages[weak_object]
        weak_object = weakref.ref(object, remove_object)
        self.__persistent_storages[weak_object] = persistent_storage

    def get_persistent_storage_for_object(self, object):
        weak_object = weakref.ref(object)
        if weak_object in self.__persistent_storages:
            return self.__persistent_storages[weak_object]
        managed_parent = object.managed_parent
        if managed_parent:
            return self.get_persistent_storage_for_object(managed_parent.parent)
        return None

    def get_properties(self, object):
        persistent_storage = self.get_persistent_storage_for_object(object)
        return copy.deepcopy(persistent_storage.properties)

    def item_inserted(self, parent, name, before_index, item):
        persistent_storage = self.get_persistent_storage_for_object(parent)
        persistent_storage.insert_item(parent, name, before_index, item)

    def item_removed(self, parent, name, item_index, item):
        persistent_storage = self.get_persistent_storage_for_object(parent)
        persistent_storage.remove_item(parent, name, item_index, item)

    def item_set(self, parent, name, item):
        persistent_storage = self.get_persistent_storage_for_object(parent)
        persistent_storage.set_item(parent, name, item)

    def property_changed(self, object, name, value):
        persistent_storage = self.get_persistent_storage_for_object(object)
        persistent_storage.set_value(object, name, value)


class ManagedParent(object):

    """ Track the parent of a managed object. """

    def __init__(self, parent, relationship_name=None, item_name=None):
        self.__weak_parent = weakref.ref(parent)
        self.relationship_name = relationship_name
        self.item_name = item_name

    def __get_parent(self):
        return self.__weak_parent()
    parent = property(__get_parent)


class ManagedObject(object):

    """
        Base class for objects participating in the document model.

        Subclasses can define properties and relationships.

        Properties can have validators, converters, change notifications, and more.
        They are created using the define_property method.

        Items have set notifications and more. They are created using the
        define_item method.

        Relationships have change notifications and more. They are created using
        the define_relationship method.

        Subclasses MUST set the writer_version, optionally, the uuid
        after init. Those values should not be changed at other times.

        The managed object context will be valid in these cases:

        When the object is read from a managed object context. It is not valid while
        reading; but only after the object has been fully read. After reading, an object
        may immediately update itself to a newer version on disk using the managed object
        context.

        When the object is inserted into another object with a managed object context.
    """

    def __init__(self):
        super(ManagedObject, self).__init__()
        self.__type = None
        self.__properties = dict()
        self.__items = dict()
        self.__relationships = dict()
        self._is_reading = False
        self.__managed_object_context = None
        # uuid as a property is too slow, so make it direct
        self.uuid = uuid.uuid4()
        self.__modified_count = 0
        self.__modified = datetime.datetime.utcnow()
        self.writer_version = 0
        self.managed_parent = None

    def __deepcopy__(self, memo):
        deepcopy = self.__class__()
        deepcopy.deepcopy_from(self, memo)
        memo[id(self)] = deepcopy
        return deepcopy

    def deepcopy_from(self, item, memo):
        for key in self.__properties.keys():
            value = item._get_managed_property(key)
            new_value = copy.deepcopy(value)
            self._set_managed_property(key, new_value)
        for key in self.__items.keys():
            self.set_item(key, copy.deepcopy(getattr(item, key)))
        for key in self.__relationships.keys():
            for child_item in getattr(item, key):
                self.append_item(key, copy.deepcopy(child_item, memo))

    def managed_object_context_changed(self):
        """ Subclasses can override this to be notified when the managed context changes. """
        pass

    def __get_managed_object_context(self):
        """ Return the managed object context. """
        return self.__managed_object_context
    def __set_managed_object_context(self, managed_object_context):
        """ Set the managed object context and propagate it to contained objects. """
        assert self.__managed_object_context is None or managed_object_context is None  # make sure managed object context is handled cleanly
        self.__managed_object_context = managed_object_context
        for item_name in self.__items.keys():
            item_value = self.__items[item_name].value
            if item_value:
                item_value.managed_object_context = managed_object_context
        for relationship_name in self.__relationships.keys():
            for item in self.__relationships[relationship_name].values:
                item.managed_object_context = managed_object_context
        if managed_object_context:
            managed_object_context.register(self)
        self.managed_object_context_changed()
    managed_object_context = property(__get_managed_object_context, __set_managed_object_context)

    def get_accessor_in_parent(self):
        managed_parent = self.managed_parent
        assert managed_parent
        if managed_parent.item_name:
            return lambda storage_dict: storage_dict.get(managed_parent.item_name, dict())
        if managed_parent.relationship_name:
            index = getattr(managed_parent.parent, managed_parent.relationship_name).index(self)
            return lambda storage_dict: storage_dict[managed_parent.relationship_name][index]
        return None

    def define_type(self, type):
        self.__type = type

    def define_property(self, name, value=None, make=None, read_only=False, hidden=False, validate=None, converter=None, changed=None, key=None, reader=None, writer=None):
        """ key is what is stored on disk; name is what is used when accessing the property from code. """
        self.__properties[name] = ManagedProperty(name, value, make, read_only, hidden, validate, converter, changed, key, reader, writer)

    def define_item(self, name, factory, item_changed=None):
        self.__items[name] = ManagedItem(name, factory, item_changed)

    def define_relationship(self, name, factory, insert=None, remove=None):
        self.__relationships[name] = ManagedRelationship(name, factory, insert, remove)

    def undefine_properties(self):
        self.__properties.clear()

    def undefine_items(self):
        self.__items.clear()

    def undefine_relationships(self):
        self.__relationships.clear()

    def __get_property_names(self):
        return list(self.__properties.keys())
    property_names = property(__get_property_names)

    def __get_key_names(self):
        return [property.key for property in self.__properties.values()]
    key_names = property(__get_key_names)

    def __get_type(self):
        return self.__type
    type = property(__get_type)

    @property
    def modified(self):
        return self.__modified

    @property
    def modified_count(self):
        return self.__modified_count

    def _set_modified(self, modified):
        # for testing
        self.__update_modified(modified)
        self.managed_object_context.property_changed(self, "uuid", str(self.uuid))  # dummy write

    def __get_item_names(self):
        return list(self.__items.keys())
    item_names = property(__get_item_names)

    def __get_relationship_names(self):
        return list(self.__relationships.keys())
    relationship_names = property(__get_relationship_names)

    def begin_reading(self):
        self._is_reading = True

    def read_from_dict(self, properties):
        """ Read from a dict. """
        # uuid is handled specially for performance reasons
        if "uuid" in properties:
            self.uuid = uuid.UUID(properties["uuid"])
            if self.managed_object_context:
                self.managed_object_context.register(self)
        if "modified" in properties:
            self.__modified = datetime.datetime(*list(map(int, re.split('[^\d]', properties["modified"]))))
        # iterate the defined properties
        for key in self.__properties.keys():
            property = self.__properties[key]
            property.read_from_dict(properties)
        for key in self.__items.keys():
            item_dict = properties.get(key)
            if item_dict:
                factory = self.__items[key].factory
                # the object has not been constructed yet, but we needs its
                # type or id to construct it. so we need to look it up by key/index/name.
                # to minimize the interface to the factory methods, just pass a closure
                # which looks up by name.
                def lookup_id(name):
                    return item_dict[name]
                item = factory(lookup_id)  # the uuid is random at this point
                if item is None:
                    logging.debug("Unable to read %s", key)
                assert item is not None
                # read the item from the dict
                item.begin_reading()
                item.read_from_dict(item_dict)
                self.__set_item(key, item)
        for key in self.__relationships.keys():
            for item_dict in properties.get(key, list()):
                factory = self.__relationships[key].factory
                # the object has not been constructed yet, but we needs its
                # type or id to construct it. so we need to look it up by key/index/name.
                # to minimize the interface to the factory methods, just pass a closure
                # which looks up by name.
                def lookup_id(name):
                    return item_dict[name]
                item = factory(lookup_id)  # the uuid is random at this point
                if item is None:
                    logging.debug("Unable to read %s", key)
                assert item is not None
                # read the item from the dict
                item.begin_reading()
                item.read_from_dict(item_dict)
                # insert it into the relationship dict
                self.__insert_item(key, len(self.__relationships[key].values), item)

    def finish_reading(self):
        for key in self.__items.keys():
            item = self.__items[key].value
            if item:
                item.finish_reading()
        for key in self.__relationships.keys():
            for item in self.__relationships[key].values:
                item.finish_reading()
        self._is_reading = False

    def write_to_dict(self):
        """ Write the object to a dict and return it. """
        properties = dict()
        if self.__type:
            properties["type"] = self.__type
        properties["uuid"] = str(self.uuid)
        for key in self.__properties.keys():
            property = self.__properties[key]
            property.write_to_dict(properties)
        for key in self.__items.keys():
            item = self.__items[key].value
            if item:
                properties[key] = item.write_to_dict()
        for key in self.__relationships.keys():
            items_list = properties.setdefault(key, list())
            for item in self.__relationships[key].values:
                items_list.append(item.write_to_dict())
        return properties

    def _update_managed_object_context_property(self, name):
        """
            Update the property given by name in the managed object context.

            Subclasses can override this to provide custom writing behavior, such
            as delaying write until an appropriate time for performance reasons.
        """
        property = self.__properties[name]
        if self.managed_object_context:
            properties = dict()
            property.write_to_dict(properties)
            for property_key in properties:
                self.managed_object_context.property_changed(self, property_key, properties[property_key])

    def __update_modified(self, modified):
        self.__modified_count += 1
        self.__modified = modified
        parent = self.managed_parent.parent if self.managed_parent else None
        if parent:
            parent.__update_modified(modified)

    def _get_managed_property(self, name):
        """ Subclasses can call this to get a hidden property. """
        return self.__properties[name].value

    def _set_managed_property(self, name, value):
        """ Subclasses can call this to set a hidden property. """
        property = self.__properties[name]
        property.set_value(value)
        self.__update_modified(datetime.datetime.utcnow())
        self._update_managed_object_context_property(name)

    def __getattr__(self, name):
        # Handle property objects that are not hidden.
        property = self.__properties.get(name)
        if property and not property.hidden:
            return property.value
        if name in self.__items:
            return self.__items[name].value
        if name in self.__relationships:
            return copy.copy(self.__relationships[name].values)
        raise AttributeError("%r object has no attribute %r" % (self.__class__, name))

    def __setattr__(self, name, value):
        # Check for private properties of this class
        if name.startswith("_ManagedObject__"):
            super(ManagedObject, self).__setattr__(name, value)
        # Otherwise check for defined properties.
        else:
            property = self.__properties.get(name)
            # if the property is hidden, fall through and give regular style property a chance to handle it
            if property and not property.hidden:
                # if the property is not hidden and it is read only, throw an exception
                if not property.read_only:
                    property.set_value(value)
                    self.__update_modified(datetime.datetime.utcnow())
                    self._update_managed_object_context_property(name)
                else:
                    raise AttributeError()
            else:
                super(ManagedObject, self).__setattr__(name, value)

    def __set_item(self, name, value):
        """ Set item into item storage and notify. Does not set into persistent storage or update modified. Item can be None. """
        item = self.__items[name]
        old_value = item.value
        item.value = value
        if value:
            value.managed_parent = ManagedParent(self, item_name=name)
            value.managed_object_context = self.managed_object_context
        if item.item_changed:
            item.item_changed(name, old_value, value)

    def set_item(self, name, value):
        """ Set item into persistent storage and then into item storage and notify. """
        item = self.__items[name]
        old_value = item.value
        item.value = value
        self.__update_modified(datetime.datetime.utcnow())
        if value:
            value.managed_parent = ManagedParent(self, item_name=name)
        # the managed_parent and item need to be established before
        # calling item_changed.
        if self.managed_object_context:
            self.managed_object_context.item_set(self, name, value)  # this will also update item's managed_object_context
        if item.item_changed:
            item.item_changed(name, old_value, value)

    def __insert_item(self, name, before_index, item):
        """ Insert item into relationship storage and notify. Does not insert in persistent storage or update modified. """
        relationship = self.__relationships[name]
        relationship.values.insert(before_index, item)
        item.managed_parent = ManagedParent(self, relationship_name=name)
        item.managed_object_context = self.managed_object_context
        if relationship.insert:
            relationship.insert(name, before_index, item)

    def insert_item(self, name, before_index, item):
        """ Insert item in persistent storage and then into relationship storage and notify. """
        relationship = self.__relationships[name]
        relationship.values.insert(before_index, item)
        self.__update_modified(datetime.datetime.utcnow())
        item.managed_parent = ManagedParent(self, relationship_name=name)
        # the managed_parent and relationship need to be established before
        # calling item_inserted.
        if self.managed_object_context:
            self.managed_object_context.item_inserted(self, name, before_index, item)  # this will also update item's managed_object_context
        if relationship.insert:
            relationship.insert(name, before_index, item)

    def append_item(self, name, item):
        """ Append item and append to persistent storage. """
        self.insert_item(name, len(self.__relationships[name].values), item)

    def remove_item(self, name, item):
        """ Remove item and remove from persistent storage. """
        relationship = self.__relationships[name]
        item_index = relationship.values.index(item)
        relationship.values.remove(item)
        self.__update_modified(datetime.datetime.utcnow())
        if relationship.remove:
            relationship.remove(name, item_index, item)
        item.managed_object_context = None
        if self.managed_object_context:
            self.managed_object_context.item_removed(self, name, item_index, item)  # this will also update item's managed_object_context
        item.managed_parent = None

    def extend_items(self, name, items):
        """ Append multiple items and add to persistent storage. """
        for item in items:
            self.append_item(name, item)


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

    def __init__(self):
        self.__weak_listeners = []
        self.__weak_listeners_mutex = threading.RLock()

    def listen(self, listener_fn):
        listener = EventListener(listener_fn)
        def remove_listener(weak_listener):
            with self.__weak_listeners_mutex:
                self.__weak_listeners.remove(weak_listener)
        weak_listener = weakref.ref(listener, remove_listener)
        with self.__weak_listeners_mutex:
            self.__weak_listeners.append(weak_listener)
        return listener

    def fire(self, *args, **keywords):
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
