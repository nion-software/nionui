"""
A collection of useful classes for handling selections.
"""

# futures
from __future__ import absolute_import

# standard libraries
import numbers

# third party libraries
# None

# local libraries
from nion.ui import Observable


class IndexedSelection(object):
    def __init__(self):
        super(IndexedSelection, self).__init__()
        self.__changed_event = Observable.Event()
        self.__indexes = set()
        self.__anchor_index = None

    @property
    def changed_event(self):
        return self.__changed_event

    @property
    def has_selection(self):
        return len(self.__indexes) > 0

    def contains(self, index):
        return index in self.__indexes

    @property
    def indexes(self):
        return self.__indexes

    def clear(self):
        old_index = self.__indexes.copy()
        self.__indexes = set()
        self.__anchor_index = None
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def __update_anchor_index(self):
        for index in self.__indexes:
            if self.__anchor_index is None or index < self.__anchor_index:
                self.__anchor_index = index

    def add(self, index):
        assert isinstance(index, numbers.Integral)
        old_index = self.__indexes.copy()
        self.__indexes.add(index)
        if len(old_index) == 0:
            self.__anchor_index = index
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def remove(self, index):
        assert isinstance(index, numbers.Integral)
        old_index = self.__indexes.copy()
        self.__indexes.remove(index)
        if not self.__anchor_index in self.__indexes:
            self.__update_anchor_index()
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def set_multiple(self, indexes):
        old_index = self.__indexes.copy()
        self.__indexes = set()
        self.__indexes.update(indexes)
        self.__anchor_index = list(indexes)[0] if len(indexes) > 0 else None
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def set(self, index):
        assert isinstance(index, numbers.Integral)
        old_index = self.__indexes.copy()
        self.__indexes = set()
        self.__indexes.add(index)
        self.__anchor_index = index
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def toggle(self, index):
        assert isinstance(index, numbers.Integral)
        if index in self.__indexes:
            self.remove(index)
        else:
            self.add(index)

    def extend(self, index):
        assert isinstance(index, numbers.Integral)
        old_index = self.__indexes.copy()
        if index > self.__anchor_index:
            for new_index in range(self.__anchor_index, index + 1):
                self.__indexes.add(new_index)
        elif index < self.__anchor_index:
            for new_index in range(index, self.__anchor_index + 1):
                self.__indexes.add(new_index)
        if old_index != self.__indexes:
            self.__changed_event.fire()

    def insert_index(self, new_index):
        new_indexes = set()
        for index in self.__indexes:
            if index < new_index:
                new_indexes.add(index)
            else:
                new_indexes.add(index + 1)
        if self.__anchor_index is not None:
            if new_index <= self.__anchor_index:
                self.__anchor_index += 1
        if self.__indexes != new_indexes:
            self.__indexes = new_indexes

    def remove_index(self, remove_index):
        new_indexes = set()
        for index in self.__indexes:
            if index != remove_index:
                if index > remove_index:
                    new_indexes.add(index - 1)
                else:
                    new_indexes.add(index)
        if self.__anchor_index is not None:
            if remove_index == self.__anchor_index:
                self.__update_anchor_index()
            elif remove_index < self.__anchor_index:
                self.__anchor_index -= 1
        if self.__indexes != new_indexes:
            self.__indexes = new_indexes
