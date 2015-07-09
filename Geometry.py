"""
    Geometry related functions and classes.

    Includes functions for making pretty axis labels.

    Includes IntPoint, IntSize, and IntRect classes.
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
import collections
import math
import numpy

# third party libraries
# None


def make_pretty(val, round_up=False):
    """ Make a pretty number from the value. """
    positive = val > 0.0
    if not positive and not val < 0.0:
        return 0.0  # make sense of values that are neither greater or less than 0.0
    factor10 = math.pow(10, int(math.log10(abs(val))))
    val_norm = abs(val)/factor10
    if val_norm < 1.0:
        val_norm = val_norm * 10
        factor10 = factor10 // 10
    if round_up:
        #print "val_norm " + str(val_norm)
        if val_norm < 1.5:
            val_norm = math.ceil(val_norm * 5) // 5  # move up to next 0.2
        elif val_norm < 3.0:
            val_norm = math.ceil(val_norm * 2) // 2  # move up to next 0.5
        else:
            val_norm = math.ceil(val_norm)  # movie up to next 1.0
        #print "val_norm+ " + str(val_norm)
        return math.copysign(val_norm * factor10, val)
    else:
        # val_norm is now between 1 and 10
        if val_norm < 5.0:
            return math.copysign(0.5 * round(val_norm/0.5) * factor10, val)
        else:
            return math.copysign(round(val_norm) * factor10, val)


def make_pretty2(val, rounding):
    """ Make a pretty number, using algorithm from Paul Heckbert, extended to handle negative numbers. """
    val = float(val)
    if not val > 0.0 and not val < 0.0:
        return 0.0  # make sense of values that are neither greater or less than 0.0
    factor10 = math.pow(10.0, math.floor(math.log10(abs(val))))
    val_norm = abs(val) / factor10  # between 1 and 10
    if val_norm < 1.0:
        val_norm = val_norm * 10
        factor10 = factor10 // 10
    if rounding:
        if val_norm < 1.5:
            val_norm = 1.0
        elif val_norm < 3.0:
            val_norm = 2.0
        elif val_norm < 7.0:
            val_norm = 5.0
        else:
            val_norm = 10.0
    else:
        if val_norm <= 1.0:
            val_norm = 1.0
        elif val_norm <= 2.0:
            val_norm = 2.0
        elif val_norm <= 5.0:
            val_norm = 5.0
        else:
            val_norm = 10.0
    return math.copysign(val_norm * factor10, val)


def make_pretty_range(value_low, value_high, tight=False, ticks=5):
    """
        Returns minimum, maximum, list of tick values, and precision.

        Value high and value low specify the data range.

        Tight indicates whether the pretty range should extend to the data (tight)
            or beyond the data (loose).

        Ticks is the approximate number of ticks desired, including the ends (if loose).

        Useful links:
            http://tog.acm.org/resources/GraphicsGems/gems/Label.c
            https://svn.r-project.org/R/trunk/src/appl/pretty.c
            http://www.mathworks.com/help/matlab/ref/axes_props.html
    """

    # adjust value_low, value_high to be floats in increasing order
    value_low = float(value_low)
    value_high = float(value_high)
    value_low, value_high = min(value_low, value_high), max(value_low, value_high)

    # check for small range
    if value_high == value_low:
        return value_low, value_low, [value_low], 0, 0

    # make the value range a pretty range
    value_range = make_pretty2(value_high - value_low, False)

    # make the tick range a pretty range
    division = make_pretty2(value_range/(ticks-1), True)

    # calculate the graph minimum and maximum
    graph_minimum = math.floor(value_low / division) * division
    graph_maximum = math.ceil(value_high / division) * division

    # calculate the precision
    precision = int(max(-math.floor(math.log10(division)), 0))

    # make the tick marks
    tick_values = []
    for x in numpy.arange(graph_minimum, graph_maximum + 0.5 * division, division):
        tick_values.append(x)

    return graph_minimum, graph_maximum, tick_values, division, precision


def fit_to_aspect_ratio(rect, aspect_ratio):
    """ Return rectangle fit to aspect ratio. Returned rectangle will have float coordinates. """
    rect = FloatRect.make(rect)
    aspect_ratio = float(aspect_ratio)
    if rect.aspect_ratio > aspect_ratio:
        # height will fill entire frame
        new_size = FloatSize(height=rect.height, width=rect.height * aspect_ratio)
        new_origin = FloatPoint(y=rect.top, x=rect.left + 0.5 * (rect.width - new_size.width))
        return FloatRect(origin=new_origin, size=new_size)
    else:
        new_size = FloatSize(height=rect.width / aspect_ratio, width=rect.width)
        new_origin = FloatPoint(y=rect.top + 0.5*(rect.height - new_size.height), x=rect.left)
        return FloatRect(origin=new_origin, size=new_size)


def fit_to_size(rect, fit_size):
    """ Return rectangle fit to size (aspect ratio). """
    return fit_to_aspect_ratio(rect, float(fit_size[1])/float(fit_size[0]))


def inset_rect(rect, amount):
    """ Return rectangle inset by given amount. """
    return ((rect[0][0] + amount, rect[0][1] + amount), (rect[1][0] - 2*amount, rect[1][1] - 2*amount))


def distance(pt1, pt2):
    """ Return distance between points as float. """
    return math.sqrt(pow(pt2[0] - pt1[0], 2) + pow(pt2[1] - pt1[1], 2))


def midpoint(pt1, pt2):
    """ Return midpoint between points. """
    return (0.5 * (pt1[0] + pt2[0]), 0.5 * (pt1[1] + pt2[1]))


Margins = collections.namedtuple("Margins", ["top", "left", "bottom", "right"])
"""
    Margins for a canvas item, specified by top, left, bottom, and right.
"""


class IntPoint(object):

    """ A class representing an integer point (x, y). """

    def __init__(self, y=0, x=0):
        self.__y = int(y)
        self.__x = int(x)

    @classmethod
    def make(cls, value):
        """ Make an IntPoint from a y, x tuple. """
        return IntPoint(value[0], value[1])

    def __str__(self):
        return "({}, {})".format(self.__x, self.__y)

    def __repr__(self):
        return "{2} (x={0}, y={1})".format(self.__x, self.__y, super(IntPoint, self).__repr__())

    def __get_x(self):
        """ Return the x coordinate. """
        return self.__x
    x = property(__get_x)

    def __get_y(self):
        """ Return the y coordinate. """
        return self.__y
    y = property(__get_y)

    def __eq__(self, other):
        other = IntPoint.make(other)
        return self.__x == other.x and self.__y == other.y

    def __ne__(self, other):
        other = IntPoint.make(other)
        return self.__x != other.x or self.__y != other.y

    def __neg__(self):
        return IntPoint(-self.__y, -self.__x)

    def __abs__(self):
        return math.sqrt(pow(self.__x, 2) + pow(self.__y, 2))

    def __add__(self, other):
        if isinstance(other, IntPoint):
            return IntPoint(self.__y + other.y, self.__x + other.x)
        elif isinstance(other, IntSize):
            return IntPoint(self.__y + other.height, self.__x + other.width)
        else:
            raise NotImplementedError()

    def __sub__(self, other):
        if isinstance(other, IntPoint):
            return IntPoint(self.__y - other.y, self.__x - other.x)
        elif isinstance(other, IntSize):
            return IntPoint(self.__y - other.height, self.__x - other.width)
        else:
            raise NotImplementedError()

    def __getitem__(self, index):
        return (self.__y, self.__x)[index]


class IntSize(object):

    """ A class representing an integer size (width, height). """

    def __init__(self, height=None, width=None, h=None, w=None):
        if height is not None:
            self.__height = int(height)
        elif h is not None:
            self.__height = int(h)
        else:
            self.__height = 0.0
        if width is not None:
            self.__width = int(width)
        elif w is not None:
            self.__width = int(w)
        else:
            self.__width = None

    @classmethod
    def make(cls, value):
        """ Make an IntSize from a height, width tuple. """
        return IntSize(value[0], value[1])

    def __str__(self):
        return "({}, {})".format(self.__width, self.__height)

    def __repr__(self):
        return "{2} (w={0}, h={1})".format(self.__width, self.__height, super(IntSize, self).__repr__())

    def __get_width(self):
        """ Return the width. """
        return self.__width
    width = property(__get_width)

    def __get_height(self):
        """ Return the height. """
        return self.__height
    height = property(__get_height)

    def __eq__(self, other):
        other = IntSize.make(other)
        return self.__width == other.width and self.__height == other.height

    def __ne__(self, other):
        other = IntSize.make(other)
        return self.__width != other.width or self.__height != other.height

    def __neg__(self):
        return IntSize(-self.__height, -self.__width)

    def __abs__(self):
        return math.sqrt(pow(self.__width, 2) + pow(self.__height, 2))

    def __add__(self, other):
        other = IntSize.make(other)
        return IntSize(self.__height + other.height, self.__width + other.width)

    def __sub__(self, other):
        other = IntSize.make(other)
        return IntSize(self.__height - other.height, self.__width - other.width)

    def __getitem__(self, index):
        return (self.__height, self.__width)[index]

    def __get_aspect_ratio(self):
        """ Return the aspect ratio as a float. """
        return float(self.__width) / float(self.__height) if self.__height != 0 else 1.0
    aspect_ratio = property(__get_aspect_ratio)


class IntRect(object):

    """
        A class representing an integer rect (origin, size).

        Increasing size goes down and to the right from origin.
    """

    def __init__(self, origin, size):
        self.__origin = IntPoint.make(origin)
        self.__size = IntSize.make(size)

    @classmethod
    def make(cls, value):
        """ Make an IntRect from a origin, size tuple. """
        return IntRect(value[0], value[1])

    @classmethod
    def from_center_and_size(cls, center, size):
        """ Make an IntRect from a center, size. """
        center = IntPoint.make(center)
        size = IntSize.make(size)
        origin = center - IntSize(height=size.height * 0.5, width=size.width * 0.5)
        return IntRect(origin, size)

    def __str__(self):
        return "({}, {})".format(self.__origin, self.__size)

    def __repr__(self):
        return "{2} (o={0}, s={1})".format(self.__origin, self.__size, super(IntRect, self).__repr__())

    def __get_origin(self):
        """ Return the origin as IntPoint. """
        return self.__origin
    origin = property(__get_origin)

    def __get_size(self):
        """ Return the size as IntSize. """
        return self.__size
    size = property(__get_size)

    def __get_width(self):
        """ Return the width. """
        return self.__size.width
    width = property(__get_width)

    def __get_height(self):
        """ Return the height. """
        return self.__size.height
    height = property(__get_height)

    def __get_left(self):
        """ Return the left coordinate. """
        return self.__origin.x
    left = property(__get_left)

    def __get_top(self):
        """ Return the top coordinate. """
        return self.__origin.y
    top = property(__get_top)

    def __get_right(self):
        """ Return the right coordinate. """
        return self.__origin.x + self.__size.width
    right = property(__get_right)

    def __get_bottom(self):
        """ Return the bottom coordinate. """
        return self.__origin.y + self.__size.height
    bottom = property(__get_bottom)

    def __get_top_left(self):
        """ Return the top left point. """
        return IntPoint(y=self.top, x=self.left)
    top_left = property(__get_top_left)

    def __get_top_right(self):
        """ Return the top right point. """
        return IntPoint(y=self.top, x=self.right)
    top_right = property(__get_top_right)

    def __get_bottom_left(self):
        """ Return the bottom left point. """
        return IntPoint(y=self.bottom, x=self.left)
    bottom_left = property(__get_bottom_left)

    def __get_bottom_right(self):
        """ Return the bottom right point. """
        return IntPoint(y=self.bottom, x=self.right)
    bottom_right = property(__get_bottom_right)

    def __get_center(self):
        """ Return the center point. """
        return IntPoint(y=(self.top + self.bottom) * 0.5, x=(self.left + self.right) * 0.5)
    center = property(__get_center)

    def __eq__(self, other):
        other = IntRect.make(other)
        return self.__origin == other.origin and self.__size == other.size

    def __ne__(self, other):
        other = IntRect.make(other)
        return self.__origin != other.origin or self.__size != other.size

    def __getitem__(self, index):
        return (self.__origin, self.__size)[index]

    def __get_aspect_ratio(self):
        """ Return the aspect ratio as a float. """
        return float(self.width) / float(self.height) if self.height != 0 else 1.0
    aspect_ratio = property(__get_aspect_ratio)

    def contains_point(self, point):
        """
            Return whether the point is contained in this rectangle.

            Left/top sides are inclusive, right/bottom sides are not.
        """
        point = IntPoint.make(point)
        return point.x >= self.left and point.x < self.right and point.y >= self.top and point.y < self.bottom

    def intersects_rect(self, rect):
        """ Return whether the rectangle intersects this rectangle. """
        if self.contains_point(rect.top_left) or self.contains_point(rect.top_right) or self.contains_point(rect.bottom_left) or self.contains_point(rect.bottom_right):
            return True
        if rect.contains_point(self.top_left) or rect.contains_point(self.top_right) or rect.contains_point(self.bottom_left) or rect.contains_point(self.bottom_right):
            return True
        return False

    def translated(self, point):
        """ Return the rectangle translated by the point or size. """
        return IntRect(self.origin + IntPoint.make(point), self.size)

    def inset(self, dx, dy=None):
        """ Returns the rectangle inset by the specified amount. """
        dy = dy if dy is not None else dx
        origin = IntPoint(y=self.top + dy, x=self.left + dx)
        size = IntSize(height=self.height - dy * 2, width=self.width - dx * 2)
        return IntRect(origin, size)


class FloatPoint(object):

    """ A class representing an float point (x, y). """

    def __init__(self, y=0.0, x=0.0):
        self.__y = float(y)
        self.__x = float(x)

    @classmethod
    def make(cls, value):
        """ Make an FloatPoint from a y, x tuple. """
        return FloatPoint(value[0], value[1])

    def __str__(self):
        return "({}, {})".format(self.__x, self.__y)

    def __repr__(self):
        return "{2} (x={0}, y={1})".format(self.__x, self.__y, super(FloatPoint, self).__repr__())

    def __get_x(self):
        """ Return the x coordinate. """
        return self.__x
    x = property(__get_x)

    def __get_y(self):
        """ Return the y coordinate. """
        return self.__y
    y = property(__get_y)

    def __eq__(self, other):
        other = FloatPoint.make(other)
        return self.__x == other.x and self.__y == other.y

    def __ne__(self, other):
        other = FloatPoint.make(other)
        return self.__x != other.x or self.__y != other.y

    def __neg__(self):
        return FloatPoint(-self.__y, -self.__x)

    def __abs__(self):
        return math.sqrt(pow(self.__x, 2) + pow(self.__y, 2))

    def __add__(self, other):
        if isinstance(other, FloatPoint):
            return FloatPoint(self.__y + other.y, self.__x + other.x)
        elif isinstance(other, FloatSize):
            return FloatPoint(self.__y + other.height, self.__x + other.width)
        else:
            raise NotImplementedError()

    def __sub__(self, other):
        if isinstance(other, FloatPoint):
            return FloatPoint(self.__y - other.y, self.__x - other.x)
        elif isinstance(other, FloatSize):
            return FloatPoint(self.__y - other.height, self.__x - other.width)
        else:
            raise NotImplementedError()

    def __getitem__(self, index):
        return (self.__y, self.__x)[index]


class FloatSize(object):

    """ A class representing an float size (width, height). """

    def __init__(self, height=None, width=None, h=None, w=None):
        if height is not None:
            self.__height = float(height)
        elif h is not None:
            self.__height = float(h)
        else:
            self.__height = 0.0
        if width is not None:
            self.__width = float(width)
        elif w is not None:
            self.__width = float(w)
        else:
            self.__width = None

    @classmethod
    def make(cls, value):
        """ Make an FloatSize from a height, width tuple. """
        return FloatSize(value[0], value[1])

    def __str__(self):
        return "({}, {})".format(self.__width, self.__height)

    def __repr__(self):
        return "{2} (w={0}, h={1})".format(self.__width, self.__height, super(FloatSize, self).__repr__())

    def __get_width(self):
        """ Return the width. """
        return self.__width
    width = property(__get_width)

    def __get_height(self):
        """ Return the height. """
        return self.__height
    height = property(__get_height)

    def __eq__(self, other):
        other = FloatSize.make(other)
        return self.__width == other.width and self.__height == other.height

    def __ne__(self, other):
        other = FloatSize.make(other)
        return self.__width != other.width or self.__height != other.height

    def __neg__(self):
        return FloatSize(-self.__height, -self.__width)

    def __abs__(self):
        return math.sqrt(pow(self.__width, 2) + pow(self.__height, 2))

    def __add__(self, other):
        other = FloatSize.make(other)
        return FloatSize(self.__height + other.height, self.__width + other.width)

    def __sub__(self, other):
        other = FloatSize.make(other)
        return FloatSize(self.__height - other.height, self.__width - other.width)

    def __getitem__(self, index):
        return (self.__height, self.__width)[index]

    def __get_aspect_ratio(self):
        """ Return the aspect ratio as a float. """
        return float(self.__width) / float(self.__height) if self.__height != 0 else 1.0
    aspect_ratio = property(__get_aspect_ratio)


class FloatRect(object):

    """
        A class representing an float rect (origin, size).

        Increasing size goes down and to the right from origin.
    """

    def __init__(self, origin, size):
        self.__origin = FloatPoint.make(origin)
        self.__size = FloatSize.make(size)

    @classmethod
    def make(cls, value):
        """ Make a FloatRect from a origin, size tuple. """
        return FloatRect(value[0], value[1])

    @classmethod
    def from_center_and_size(cls, center, size):
        """ Make a FloatRect from a center, size. """
        center = FloatPoint.make(center)
        size = FloatSize.make(size)
        origin = center - FloatSize(height=size.height * 0.5, width=size.width * 0.5)
        return FloatRect(origin, size)

    def __str__(self):
        return "({}, {})".format(self.__origin, self.__size)

    def __repr__(self):
        return "{2} (o={0}, s={1})".format(self.__origin, self.__size, super(FloatRect, self).__repr__())

    def __get_origin(self):
        """ Return the origin as FloatPoint. """
        return self.__origin
    origin = property(__get_origin)

    def __get_size(self):
        """ Return the size as FloatSize. """
        return self.__size
    size = property(__get_size)

    def __get_width(self):
        """ Return the width. """
        return self.__size.width
    width = property(__get_width)

    def __get_height(self):
        """ Return the height. """
        return self.__size.height
    height = property(__get_height)

    def __get_left(self):
        """ Return the left coordinate. """
        return self.__origin.x
    left = property(__get_left)

    def __get_top(self):
        """ Return the top coordinate. """
        return self.__origin.y
    top = property(__get_top)

    def __get_right(self):
        """ Return the right coordinate. """
        return self.__origin.x + self.__size.width
    right = property(__get_right)

    def __get_bottom(self):
        """ Return the bottom coordinate. """
        return self.__origin.y + self.__size.height
    bottom = property(__get_bottom)

    def __get_top_left(self):
        """ Return the top left point. """
        return FloatPoint(y=self.top, x=self.left)
    top_left = property(__get_top_left)

    def __get_top_right(self):
        """ Return the top right point. """
        return FloatPoint(y=self.top, x=self.right)
    top_right = property(__get_top_right)

    def __get_bottom_left(self):
        """ Return the bottom left point. """
        return FloatPoint(y=self.bottom, x=self.left)
    bottom_left = property(__get_bottom_left)

    def __get_bottom_right(self):
        """ Return the bottom right point. """
        return FloatPoint(y=self.bottom, x=self.right)
    bottom_right = property(__get_bottom_right)

    def __get_center(self):
        """ Return the center point. """
        return FloatPoint(y=(self.top + self.bottom) * 0.5, x=(self.left + self.right) * 0.5)
    center = property(__get_center)

    def __eq__(self, other):
        other = FloatRect.make(other)
        return self.__origin == other.origin and self.__size == other.size

    def __ne__(self, other):
        other = FloatRect.make(other)
        return self.__origin != other.origin or self.__size != other.size

    def __getitem__(self, index):
        return (self.__origin, self.__size)[index]

    def __get_aspect_ratio(self):
        """ Return the aspect ratio as a float. """
        return float(self.width) / float(self.height) if self.height != 0 else 1.0
    aspect_ratio = property(__get_aspect_ratio)

    def contains_point(self, point):
        """
            Return whether the point is contained in this rectangle.

            Left/top sides are inclusive, right/bottom sides are not.
        """
        point = FloatPoint.make(point)
        return point.x >= self.left and point.x < self.right and point.y >= self.top and point.y < self.bottom

    def translated(self, point):
        """ Return the rectangle translated by the point or size. """
        return IntRect(self.origin + IntPoint.make(point), self.size)

    def inset(self, dx, dy=None):
        """ Returns the rectangle inset by the specified amount. """
        dy = dy if dy is not None else dx
        origin = FloatPoint(y=self.top + dy, x=self.left + dx)
        size = FloatSize(height=self.height - dy * 2, width=self.width - dx * 2)
        return FloatRect(origin, size)
