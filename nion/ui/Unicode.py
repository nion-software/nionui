""" Provide a u() function that works in both Python 2 and 3 for ensuring a string is unicode. """

# futures
from __future__ import absolute_import

# system
import sys

if sys.version < '3':
    def u(x=None):
        return unicode(x if x is not None else str())

    def is_bytes_type(itype):
        return itype == bytes

    def is_unicode_type(itype):
        return itype == str or itype == unicode

    def str_to_bytes(s):
        return bytes(s)
else:
    def u(x=None):
        return str(x) if x is not None else str()

    def is_bytes_type(itype):
        return itype == bytes

    def is_unicode_type(itype):
        return itype == str

    def str_to_bytes(s):
        return bytes(s, 'ISO-8859-1')
