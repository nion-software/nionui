"""
    Binding classes.
"""

# futures
from __future__ import absolute_import

# standard libraries
# none

# third party libraries
# none

# local libraries
from nion.ui import Observable


class Binding(Observable.Observable):

    """
        Binds two objects, a source and target, together. Typically,
        the model object would be the source and the UI object would be
        the target. Also facilitates a converter object between the
        source and target to convert between value types. Observes the
        source object for changes.

        The source object must be Observable.

        Bindings can be one way (from source to target) or two way (from
        source to target and back). The converter object, if used, must
        always supply a convert method. If this binding is two way, then
        it must also supply a convert_back method.

        This class is not intended to be used directly. Instead, subclasses
        will implement specific source bindings by configuring the
        source_setter and source_getter methods and by using update_target
        appropriately.

        Clients of this class will set target_setter to directly connect
        the target, typically a UI element.

        The owner should call close on this object.

        Bindings are not sharable. They are meant to be used to bind
        one ui element to one value. However, conversions and binding
        sources can be shared between bindings in most cases.
    """

    def __init__(self, source, converter=None, fallback=None):
        super(Binding, self).__init__()
        self.__source = None
        self.__converter = converter
        self.fallback = fallback
        self.source_getter = None
        self.source_setter = None
        self.target_setter = None
        self.source = source

    # not thread safe
    def close(self):
        """
            Closes the binding. Subclasses can use this to perform any shutdown
            related actions. Not thread safe.
        """
        self.source = None

    @property
    def source(self):
        """ Return the source of the binding. Thread safe. """
        return self.__source

    @source.setter
    def source(self, source):
        """ Set the source of the binding. Source must be Observable. Thread safe. """
        if self.__source is not None:
            self.__source.remove_observer(self)
        self.__source = source
        if self.__source is not None:
            self.__source.add_observer(self)
        self.notify_set_property("source", self.__source)

    @property
    def converter(self):
        """ Return the converter (from source to target). Thread safe. """
        return self.__converter

    # thread safe
    def __back_converted_value(self, target_value):
        """ Return the back converted value (from target to source). Thread safe. """
        return self.__converter.convert_back(target_value) if self.__converter else target_value

    # thread safe
    def __converted_value(self, source_value):
        """ Return the converted value (from source to target). Thread safe. """
        return self.__converter.convert(source_value) if self.__converter else source_value

    # public methods. subclasses must make sure these methods work as expected.

    # thread safe
    def update_source(self, target_value):
        """
            Update the source from the target value. The target value will be back converted.
            This is typically called by a target (UI element) to update the source (model).

            This method is required for two-way binding.

            Thread safe.
        """
        if self.source_setter:
            converted_value = self.__back_converted_value(target_value)
            self.source_setter(converted_value)

    # not thread safe
    def update_target(self, source_value):
        """
            Call the target setter with the unconverted value from the source.
            This is typically called by subclasses to update the target (UI element)
            when the source (model) changes.

            Required for both one-way and two-way bindings. It uses update_target_direct
            to call the target setter.

            Not thread safe.
        """
        self.update_target_direct(self.__converted_value(source_value))

    # not thread safe
    def update_target_direct(self, converted_value):
        """
            Call the target setter with the already converted value.
            This is typically called by subclasses to handle target setting
            when the conversion is already done, for instance for implementing
            a fallback, default, or placeholder value.

            Required for both one-way and two-way bindings.

            Not thread safe.
        """
        if self.target_setter:
            self.target_setter(converted_value)

    # thread safe
    def get_target_value(self):
        """
            Get the value from the source that will be set on the target.
            This is typically used by the target object to initialize its value.

            Required for both one-way and two-way bindings.

            Thread safe.
        """
        if self.source_getter:
            source = self.source_getter()
            if source is not None:
                return self.__converted_value(source)
        return self.fallback


class ObjectBinding(Binding):

    """
        Bind one way from a source object to target.

        The owner should call close on this object.
    """

    def __init__(self, source, converter=None):
        super(ObjectBinding, self).__init__(source, converter)
        self.source_getter = lambda: self.source


class ListBinding(Binding):

    """
        Binds to a source object which is a list. One way from source to target.

        Client should configure the inserter and remover functions.

        inserter function has the signature inserter(item, before_index).
        remover function has the signature remover(index).

        The owner should call close on this object.
    """

    def __init__(self, source, key_name):
        super(ListBinding, self).__init__(source)
        self.__key_name = key_name
        self.inserter = None
        self.remover = None

    # not thread safe. private method.
    def __insert_item(self, item, before_index):
        """
            This method gets called on the main thread and then
            calls the inserter function, typically on the target.
        """
        if self.inserter:
            self.inserter(item, before_index)

    # not thread safe. private method.
    def __remove_item(self, index):
        """
            This method gets called on the main thread and then
            calls the remover function, typically on the target.
        """
        if self.remover:
            self.remover(index)

    # thread safe
    def item_inserted(self, sender, key, item, before_index):
        """ This message comes from the source since this object is an observer. Handled by calling __insert_item. """
        if sender == self.source and key == self.__key_name:
            self.__insert_item(item, before_index)

    # thread safe
    def item_removed(self, sender, key, item, index):
        """ This message comes from the source since this object is an observer. Handled by calling __remove_item. """
        if sender == self.source and key == self.__key_name:
            self.__remove_item(index)

    @property
    def items(self):
        """ Return the items of the list. Thread safe. """
        return getattr(self.source, self.__key_name)


class PropertyBinding(Binding):

    """
        Binds to a property of a source object. This is a two way binding.

        When target (UI element) calls update_source to update the source (model), this binding will
        set property on source object via the setattr function and the property_name.

        When a property change occurs on the source (model) object that matches the property name, the
        target will be updated using update_target.

        The owner should call close on this object.
    """

    def __init__(self, source, property_name, converter=None, fallback=None):
        super(PropertyBinding, self).__init__(source, converter)
        self.__property_name = property_name
        self.source_setter = lambda value: setattr(self.source, self.__property_name, value)
        self.source_getter = lambda: getattr(self.source, self.__property_name)

    # thread safe
    def property_changed(self, sender, property_name, value):
        """
            This message comes from the source since this object is an observer.
            Updates the target using update_target or update_target_direct with
            the fallback value if value is None.
        """
        if sender == self.source and property_name == self.__property_name:
            if value is not None:
                self.update_target(value)
            else:
                self.update_target_direct(self.fallback)


class TuplePropertyBinding(Binding):

    """
        Binds to an element of a tuple property of a source object. This is a two way binding.

        When target (UI element) calls update_source to update the source (model), this binding will
        set property on source object via the setattr function and the property_name.

        When a property change occurs on the source (model) object that matches the property name, the
        target will be updated using update_target.

        The owner should call close on this object.
    """

    def __init__(self, source, property_name, tuple_index, converter=None, fallback=None):
        super(TuplePropertyBinding, self).__init__(source, converter=converter, fallback=fallback)
        self.__property_name = property_name
        self.__tuple_index = tuple_index
        def source_setter(value):  # pylint: disable=missing-docstring
            tuple_as_list = list(getattr(self.source, self.__property_name))
            tuple_as_list[self.__tuple_index] = value
            setattr(self.source, self.__property_name, tuple(tuple_as_list))
        def source_getter():  # pylint: disable=missing-docstring
            tuple_value = getattr(self.source, self.__property_name)
            return tuple_value[self.__tuple_index] if tuple_value else None
        self.source_setter = source_setter
        self.source_getter = source_getter

    # thread safe
    def property_changed(self, sender, property_name, value):
        """
            This message comes from the source since this object is an observer.
            Updates the target using update_target or update_target_direct with the
            fallback value if value is None.
        """
        if sender == self.source and property_name == self.__property_name:
            # perform on the main thread
            if value is not None:
                self.update_target(value[self.__tuple_index])
            else:
                self.update_target_direct(self.fallback)
