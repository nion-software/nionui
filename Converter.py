"""
    Converter classes. Useful for bindings.
"""

# futures
from __future__ import absolute_import

# standard libraries
import re
import locale

# third party libraries
# none

# local libraries
# none


class IntegerToStringConverter(object):
    """ Convert between int value and formatted string. """

    def __init__(self, format=None):
        """ format specifies int to string conversion """
        self.__format = format if format else "{:d}"

    def convert(self, value):
        """ Convert value to string using format string """
        return self.__format.format(int(value))

    def convert_back(self, formatted_value):
        """ Convert string to value using standard int conversion """
        return int(formatted_value)


class FloatToStringConverter(object):
    """ Convert between float value and formatted string. """

    def __init__(self, format=None, pass_none=False, fuzzy=True):
        self.__format = format if format else "{:g}"
        self.__pass_none = pass_none
        self.__fuzzy = fuzzy

    def convert(self, value):
        """ Convert value to string using format string """
        if self.__pass_none and value is None:
            return None
        return self.__format.format(value)

    def convert_back(self, formatted_value):
        """ Convert string to value using standard float conversion """
        if self.__pass_none and (formatted_value is None or len(formatted_value) == 0):
            return None
        if self.__fuzzy:
            _parser = re.compile(r"""        # A numeric string consists of:
                (?P<sign>[-+])?              # an optional sign, followed by either...
                (
                    (?=\d|[\.,]\d)              # ...a number (with at least one digit)
                    (?P<int>\d*)             # having a (possibly empty) integer part
                    ([\.,](?P<frac>\d*))?       # followed by an optional fractional part
                    (E(?P<exp>[-+]?\d+))?    # followed by an optional exponent, or...
                )
            """, re.VERBOSE | re.IGNORECASE).match
            m = _parser(formatted_value.strip())
            if m is not None:
                return locale.atof(m.group(0))
            return 0.0
        else:
            return locale.atof(formatted_value)


class FloatTo100Converter(object):
    """ Convert between float value and int (float * 100). """

    def convert(self, value):
        """ Convert float between 0, 1 to percentage int """
        return int(value * 100)

    def convert_back(self, value100):
        """ Convert int percentage value to float """
        return value100 / 100.0


class FloatToPercentStringConverter(object):
    """ Convert between float value and percentage string. """

    def convert(self, value):
        """ Convert float between 0, 1 to percentage string """
        return str(int(value * 100)) + "%"

    def convert_back(self, formatted_value):
        """ Convert percentage string to float between 0, 1 """
        return float(formatted_value.strip('%'))/100.0


class CheckedToCheckStateConverter(object):
    """ Convert between bool and checked/unchecked strings. """

    def convert(self, value):
        """ Convert bool to checked or unchecked string """
        return "checked" if value else "unchecked"

    def convert_back(self, value):
        """ Convert checked or unchecked string to bool """
        return value == "checked"
