# standard libraries
import logging
import unittest

# third party libraries
# None

# local libraries
from nion.ui import Persistence


class Archivable(Persistence.PersistentObject):
    def __init__(self):
        super(Archivable, self).__init__()
        self.define_property("abc")


class TestObservableClass(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_archivable_can_read_when_missing_property_keys(self):
        Archivable().read_from_dict(dict())


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
