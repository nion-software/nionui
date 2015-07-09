"""
    Model classes. Useful for bindings.
"""

# futures
from __future__ import absolute_import

# standard libraries
import collections
import copy
import weakref

# third party libraries
# none

# local libraries
from nion.ui import Observable


class ListModel(collections.MutableSequence, Observable.Observable):

    """
        Observable list.

        Items added to this list are NOT recursively observed.
    """

    def __init__(self, parent, relationship_name):
        super(ListModel, self).__init__()
        self.__list = list()
        self.__weak_parent = weakref.ref(parent)
        self.__relationship_name = relationship_name

    def __copy__(self):
        return copy.copy(self.__list)

    def __len__(self):
        return len(self.__list)

    def __getitem__(self, index):
        return self.__list[index]

    def __setitem__(self, index, value):
        raise IndexError()

    def __delitem__(self, index):
        # get value
        value = self.__list[index]
        # do actual removal
        del self.__list[index]
        # keep storage up-to-date
        self.__weak_parent().notify_remove_item(self.__relationship_name, value, index)

    def __iter__(self):
        return iter(self.__list)

    def insert(self, index, value):
        assert value not in self.__list
        assert index <= len(self.__list) and index >= 0
        # insert in internal list
        self.__list.insert(index, value)
        # keep storage up-to-date
        self.__weak_parent().notify_insert_item(self.__relationship_name, value, index)


class PropertyModel(Observable.Observable):

    """
        Holds a value which can be observed for changes. The value can be any type that supports equality test.

        An optional on_value_changed method gets called when the value changes.
    """

    def __init__(self, value=None):
        super(PropertyModel, self).__init__()
        self.__value = value
        self.on_value_changed = None

    def close(self):
        self.on_value_changed = None

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        if self.__value is None:
            not_equal = value is not None
        elif value is None:
            not_equal = self.__value is not None
        else:
            not_equal = value != self.__value
        if not_equal:
            self.__value = value
            self.notify_set_property("value", value)
            if self.on_value_changed:
                self.on_value_changed(value)
