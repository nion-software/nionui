"""
    CanvasItem module contains classes related to canvas items.
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
import collections
import copy
import functools
import logging
import operator
import sys
import threading
import time
import types
import weakref

# third party libraries
# None

# local libraries
from . import Geometry
from . import ThreadPool
from . import Observable
from . import Test


DEFAULT_MAX_FRAME_RATE = 40

if sys.version < '3':
    MAX_VALUE = sys.maxint
else:
    MAX_VALUE = sys.maxsize

class Constraint(object):

    """ A constraint on an item in a layout. Preferred is only used when free sizing. """

    def __init__(self):
        self.minimum = None
        self.maximum = None
        self.preferred = None

    def __str__(self):
        return "{0} (min={1}, max={2}, pref={3})".format(super(Constraint, self).__str__(), self.minimum, self.maximum, self.preferred)


class SolverItem(object):
    def __init__(self, constraint):
        self.constraint = constraint
        self.size = None
        self.is_constrained = False


class Solver(object):

    """
        A helper object to solve a layout of items.

        Caller must pass in the canvas origin as an IntPoint, the canvas size
        as an IntSize, the canvas item constraints as a list of Constraint objects,
        and the spacing as an int.

        After calling the solve method, the sizes and origins fields will be set
        and can be used to position the items.
    """

    def __init__(self, canvas_origin, canvas_size, canvas_item_constraints, spacing=0):
        self.canvas_origin = canvas_origin
        self.canvas_size = canvas_size
        self.canvas_item_constraints = canvas_item_constraints
        self.spacing = spacing
        self.sizes = None
        self.origins = None

    def solve(self):
        """
            Solve the layout by assigning space and enforcing constraints.
        """
        # setup information from each item
        solver_items = [SolverItem(constraint) for constraint in self.canvas_item_constraints]

        # assign preferred size, if any, to each item. items with preferred size are still
        # free to change as long as they don't become constrained.
        for solver_item in solver_items:
            if not solver_item.is_constrained and solver_item.constraint.preferred is not None:
                solver_item.size = solver_item.constraint.preferred
                if solver_item.size < solver_item.constraint.minimum:
                    solver_item.size = solver_item.constraint.minimum
                    solver_item.is_constrained = True
                if solver_item.size > solver_item.constraint.maximum:
                    solver_item.size = solver_item.constraint.maximum
                    solver_item.is_constrained = True

        # assign the free space to the remaining items. first figure out how much space is left
        # and how many items remain. then divide the space up.
        finished = False
        while not finished:
            finished = True
            remaining_canvas_size = self.canvas_size
            remaining_count = len(solver_items)
            # reset the items that we can
            for solver_item in solver_items:
                if not solver_item.is_constrained and solver_item.constraint.preferred is None:
                    solver_item.size = None
            # figure out how many free range items there are
            for solver_item in solver_items:
                if solver_item.size is not None:
                    remaining_canvas_size -= solver_item.size
                    remaining_count -= 1
            # again attempt to assign sizes
            for solver_item in solver_items:
                if solver_item.size is None:
                    size = remaining_canvas_size // remaining_count
                    if size < solver_item.constraint.minimum:
                        size = solver_item.constraint.minimum
                        solver_item.is_constrained = True
                        finished = False
                    if size > solver_item.constraint.maximum:
                        size = solver_item.constraint.maximum
                        solver_item.is_constrained = True
                        finished = False
                    solver_item.size = size
                    remaining_canvas_size -= size
                    remaining_count -= 1
                if not finished:
                    break

        # go through again and assign any remaining space
        for solver_item in solver_items:
            if solver_item.size is None:
                solver_item.size = remaining_canvas_size // remaining_count

        # check if we're oversized. if so divide among unconstrained items, but honor minimum size.
        finished = False
        while not finished:
            finished = True
            actual_canvas_size = sum([solver_item.size for solver_item in solver_items])
            if actual_canvas_size > self.canvas_size:
                remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
                remaining_canvas_size = actual_canvas_size - self.canvas_size
                if remaining_count > 0:
                    for solver_item in solver_items:
                        if not solver_item.is_constrained:
                            size = solver_item.size - remaining_canvas_size // remaining_count
                            if size < solver_item.constraint.minimum:
                                size = solver_item.constraint.minimum
                                solver_item.is_constrained = True
                                finished = False
                            adjustment = solver_item.size - size
                            solver_item.size = size
                            remaining_canvas_size -= adjustment
                            remaining_count -= 1
                        if not finished:
                            break

        # check if we're undersized. if so add among unconstrained items, but honor maximum size.
        finished = False
        while not finished:
            finished = True
            actual_canvas_size = sum([solver_item.size for solver_item in solver_items])
            if actual_canvas_size < self.canvas_size:
                remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
                remaining_canvas_size = self.canvas_size - actual_canvas_size
                if remaining_count > 0:
                    for solver_item in solver_items:
                        if not solver_item.is_constrained:
                            size = solver_item.size + remaining_canvas_size // remaining_count
                            if size > solver_item.constraint.maximum:
                                size = solver_item.constraint.maximum
                                solver_item.is_constrained = True
                                finished = False
                            adjustment = size - solver_item.size
                            solver_item.size = size
                            remaining_canvas_size -= adjustment
                            remaining_count -= 1
                        if not finished:
                            break

        #logging.debug([solver_item.size for solver_item in solver_items])
        #logging.debug([solver_item.is_constrained for solver_item in solver_items])

        # assign layouts
        self.sizes = [solver_item.size for solver_item in solver_items]
        canvas_origin = self.canvas_origin
        self.origins = list()
        for index in range(len(self.canvas_item_constraints)):
            self.origins.append(canvas_origin)
            canvas_origin += self.sizes[index] + self.spacing


class Sizing(object):

    """
        Describes the sizing for a particular canvas item.

        Aspect ratio, width, and height can each specify minimums, maximums, and preferred values.

        Width and height can be integer or floats. If floats, they specify a percentage of their
        respective maximum.

        Preferred values are only used when free sizing.
    """

    def __init__(self):
        self.preferred_width = None
        self.preferred_height = None
        self.preferred_aspect_ratio = None
        self.minimum_width = None
        self.minimum_height = None
        self.minimum_aspect_ratio = None
        self.maximum_width = None
        self.maximum_height = None
        self.maximum_aspect_ratio = None
        self.collapsible = False

    def __str__(self):
        format_str = "{0} (min_w={1}, max_w={2}, pref_w={3}, min_h={4}, max_h={5}, pref_h={6}, min_a={7}, max_a={8}, pref_a={9}, collapsible={10})"
        return format_str.format(super(Sizing, self).__str__(),
                                 self.minimum_width, self.maximum_width, self.preferred_width,
                                 self.minimum_height, self.maximum_height, self.preferred_height,
                                 self.minimum_aspect_ratio, self.maximum_aspect_ratio, self.preferred_aspect_ratio,
                                 self.collapsible)

    def copy_from(self, other):
        self.preferred_width = other.preferred_width
        self.preferred_height = other.preferred_height
        self.preferred_aspect_ratio = other.preferred_aspect_ratio
        self.minimum_width = other.minimum_width
        self.minimum_height = other.minimum_height
        self.minimum_aspect_ratio = other.minimum_aspect_ratio
        self.maximum_width = other.maximum_width
        self.maximum_height = other.maximum_height
        self.maximum_aspect_ratio = other.maximum_aspect_ratio
        self.collapsible = other.collapsible

    def set_fixed_height(self, height):
        self.preferred_height = height
        self.minimum_height = height
        self.maximum_height = height

    def set_fixed_width(self, width):
        self.preferred_width = width
        self.minimum_width = width
        self.maximum_width = width

    def set_fixed_size(self, size):
        size = Geometry.IntSize.make(size)
        self.set_fixed_height(size.height)
        self.set_fixed_width(size.width)

    def get_width_constraint(self, width):
        """ Create and return a new width Constraint object made from this sizing object. """
        constraint = Constraint()
        if self.minimum_width is not None:
            if isinstance(self.minimum_width, float) and self.minimum_width <= 1.0:
                constraint.minimum = int(width * self.minimum_width)
            else:
                constraint.minimum = self.minimum_width
        else:
            constraint.minimum = 0
        if self.maximum_width is not None:
            if isinstance(self.maximum_width, float) and self.maximum_width <= 1.0:
                constraint.maximum = int(width * self.maximum_width)
            else:
                constraint.maximum = self.maximum_width
        else:
            constraint.maximum = MAX_VALUE
        if self.preferred_width is not None:
            if isinstance(self.preferred_width, float) and self.preferred_width <= 1.0:
                constraint.preferred = int(width * self.preferred_width)
            else:
                constraint.preferred = self.preferred_width
        else:
            constraint.preferred = None
        return constraint

    def get_height_constraint(self, height):
        """ Create and return a new height Constraint object made from this sizing object. """
        constraint = Constraint()
        if self.minimum_height is not None:
            if isinstance(self.minimum_height, float) and self.minimum_height <= 1.0:
                constraint.minimum = height * self.minimum_height
            else:
                constraint.minimum = self.minimum_height
        else:
            constraint.minimum = 0
        if self.maximum_height is not None:
            if isinstance(self.maximum_height, float) and self.maximum_height <= 1.0:
                constraint.maximum = height * self.maximum_height
            else:
                constraint.maximum = self.maximum_height
        else:
            constraint.maximum = MAX_VALUE
        if self.preferred_height is not None:
            if isinstance(self.preferred_height, float) and self.preferred_height <= 1.0:
                constraint.preferred = int(height * self.preferred_height)
            else:
                constraint.preferred = self.preferred_height
        else:
            constraint.preferred = None
        return constraint


class AbstractCanvasItem(object):

    """
        Represents an object to be drawn on a canvas.

        The canvas object is responsible for drawing its content after which it tells its container that it has updated
        content. The container will send the updated content to the ui canvas which will schedule it to be drawn by the
        ui.

        This is an abstract class and must be subclassed to be used properly.

        Canvas items are only meant to be placed within a single container and the caller has access to that container
        if this item is so placed.

        Canvas items keep track of the canvas widget in which they are placed. The canvas widget is used for drawing.

        Canvas items will take up their maximum allowed space unless otherwise configured. There are typically two ways
        that sizing is managed. One in which the top level container determines the overall space available and one
        where the content determines the size of the top level container. Combinations of the two methods might be used,
        for example a fixed container size but  an area inside the container that is sized to its contents.
    """

    def __init__(self):
        self.__container = None
        self.__canvas_size = None
        self.__canvas_origin = None
        self.__sizing = Sizing()
        self.__focused = False
        self.__focusable = False
        self.wants_mouse_events = False
        self.wants_drag_events = False
        self.on_focus_changed = None
        self.on_layout_updated = None
        self.__cursor_shape = None

    def close(self):
        """ Close the canvas object. """
        self.__container = None
        self.on_focus_changed = None
        self.on_layout_updated = None

    @property
    def canvas_size(self):
        """ Returns size of canvas_rect (external coordinates). """
        return self.__canvas_size

    def _set_canvas_size(self, canvas_size):
        self.__canvas_size = Geometry.IntSize.make(canvas_size)

    @property
    def canvas_origin(self):
        """ Returns origin of canvas_rect (external coordinates). """
        return self.__canvas_origin

    def _set_canvas_origin(self, canvas_origin):
        self.__canvas_origin = Geometry.IntPoint.make(canvas_origin)

    @property
    def canvas_widget(self):
        return self.container.canvas_widget if self.container else None

    @property
    def canvas_bounds(self):
        """ Returns a rect of the internal coordinates. """
        if self.canvas_size is not None:
            return Geometry.IntRect((0, 0), self.canvas_size)
        return None

    @property
    def canvas_rect(self):
        """ Returns a rect of the external coordinates. """
        if self.canvas_origin is not None and self.canvas_size is not None:
            return Geometry.IntRect(self.canvas_origin, self.canvas_size)
        return None

    @property
    def container(self):
        """ Return the container, if any. """
        return self.__container

    @container.setter
    def container(self, container):
        """ Set container. """
        self.__container = container

    @property
    def root_container(self):
        """ Return the root container, if any. """
        return self.__container.root_container if self.__container else None

    @property
    def focusable(self):
        """ Return whether the canvas item is focusable. """
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable):
        """
            Set whether the canvas item is focusable.

            If this canvas item is focusable and contains other canvas items, they should
            not be focusable.
        """
        self.__focusable = focusable

    @property
    def focused(self):
        """ Return whether the canvas item is focused. """
        return self.__focused

    def _set_focused(self, focused):
        """ Set whether the canvas item is focused. Only called from container. """
        if focused != self.__focused:
            self.__focused = focused
            if self.on_focus_changed:
                self.on_focus_changed(focused)

    def request_focus(self):
        """ Request focus. """
        if not self.focused:
            root_container = self.root_container
            if root_container:
                root_container._request_root_focus(self)

    def clear_focus(self):
        """ Relinquish focus. """
        if self.focused:
            root_container = self.root_container
            if root_container:
                root_container.focused_item = None

    @property
    def cursor_shape(self):
        return self.__cursor_shape

    @cursor_shape.setter
    def cursor_shape(self, cursor_shape):
        self.__cursor_shape = cursor_shape
        root_container = self.root_container
        if root_container:
            root_container._cursor_shape_changed(self)

    def map_to_canvas_item(self, p, canvas_item):
        """ Map the point to the local coordinates of canvas_item. """
        p = Geometry.IntPoint.make(p)
        o1 = self.map_to_global(Geometry.IntPoint())
        o2 = canvas_item.map_to_global(Geometry.IntPoint())
        return p + o1 - o2

    def map_to_global(self, p):
        """ Map the point to the coordinates of the enclosing canvas widget. """
        canvas_item = self
        while canvas_item:  # handle case where last canvas item was root
            canvas_item_origin = canvas_item.canvas_origin
            if canvas_item_origin is not None:  # handle case where canvas item is not root but has no parent
                p = p + Geometry.IntPoint.make(canvas_item_origin)
                canvas_item = canvas_item.container
            else:
                break
        return p

    def map_to_container(self, p):
        """ Map the point to the coordinates of the container. """
        return p + Geometry.IntPoint.make(self.canvas_origin)

    def update_layout(self, canvas_origin, canvas_size, trigger_update=True):
        """
            Update the layout with a new canvas_origin and canvas_size.

            canvas_origin and canvas_size are the external bounds.

            Set trigger_update to false to avoid triggering updates for efficiency.

            Subclasses can override this method to take action when the
            size of the canvas item changes.

            The on_layout_updated callable will be called with the new canvas_origin,
            canvas_size, and trigger_update flag.

            The canvas_origin and canvas_size properties are set after calling this method.
        """
        self._set_canvas_origin(canvas_origin)
        self._set_canvas_size(canvas_size)
        if self.on_layout_updated:
            self.on_layout_updated(self.canvas_origin, self.canvas_size, trigger_update)

    def refresh_layout(self, trigger_update=True):
        """ Update the layout with the same origin and size.

            Set trigger_update to false to avoid triggering updates for efficiency.

            Call this method on containers if child items have changed size or constraints.
        """
        if self.canvas_origin is not None and self.canvas_size is not None:
            self.update_layout(self.canvas_origin, self.canvas_size, trigger_update)
            if trigger_update:
                self.update()

    @property
    def sizing(self):
        """
            Return sizing information for this canvas item.

            The sizing property is read only, but the object itself
            can be modified.
        """
        return self.__sizing

    @property
    def layout_sizing(self):
        """
            Return layout sizing information for this canvas item.

            The layout sizing is read only and cannot be modified. It is
            used from the layout engine.
        """
        return self.sizing

    def update(self):
        """
            Mark this canvas item as needing a display update.

            The canvas item will be repainted by the root canvas item.
        """
        container = self.__container
        if container:
            container._child_updated(self)

    def _child_updated(self, child):
        """
            Notify this canvas item that a child has been updated, repaint if needed at next opportunity.

            Default implementation calls child_updated on the container, if not None.

            Subclasses can override to handle specially.
        """
        container = self.__container
        if container:
            container._child_updated(self)

    def _repaint(self, drawing_context):
        """
            Repaint the canvas item to the drawing context.

            Subclasses should override this method to paint.

            This method will be called on a thread.

            The drawing should take place within the canvas_bounds.
        """
        assert self.canvas_size is not None

    def _repaint_visible(self, drawing_context, visible_rect):
        """
            Repaint the canvas item to the drawing context within the visible area.

            Subclasses can override this method to paint.

            This method will be called on a thread.

            The drawing should take place within the canvas_bounds.

            The default implementation calls _repaint(drawing_context)
        """
        self._repaint(drawing_context)

    def canvas_item_at_point(self, x, y):
        canvas_items = self.canvas_items_at_point(x, y)
        return canvas_items[0] if len(canvas_items) > 0 else None

    def canvas_items_at_point(self, x, y):
        """ Return the canvas item at the point. May return None. """
        canvas_bounds = self.canvas_bounds
        if canvas_bounds and canvas_bounds.contains_point(Geometry.IntPoint(x=x, y=y)):
            return [self]
        return []

    def mouse_clicked(self, x, y, modifiers):
        """ Handle a mouse click within this canvas item. Return True if handled. """
        return False

    def mouse_double_clicked(self, x, y, modifiers):
        """ Handle a mouse double click within this canvas item. Return True if handled. """
        return False

    def mouse_entered(self):
        """ Handle a mouse entering this canvas item. Return True if handled. """
        return False

    def mouse_exited(self):
        """ Handle a mouse exiting this canvas item. Return True if handled. """
        return False

    def mouse_pressed(self, x, y, modifiers):
        """ Handle a mouse press within this canvas item. Return True if handled. """
        return False

    def mouse_released(self, x, y, modifiers):
        """ Handle a mouse release within this canvas item. Return True if handled. """
        return False

    def mouse_position_changed(self, x, y, modifiers):
        """ Handle a mouse move within this canvas item. Return True if handled. """
        return False

    def wheel_changed(self, dx, dy, is_horizontal):
        """ Handle a mouse wheel changed within this canvas item. Return True if handled. """
        return False

    def context_menu_event(self, x, y, gx, gy):
        """ Handle a context menu event. x, y are local coordinates. gx, gy are global coordinates. """
        return False

    def key_pressed(self, key):
        """ Handle a key pressed while this canvas item has focus. Return True if handled. """
        return False

    def drag_enter(self, mime_data):
        """ Handle a drag event entering this canvas item. Return action if handled. """
        return "ignore"

    def drag_leave(self):
        """ Handle a drag event leaving this canvas item. Return action if handled. """
        return "ignore"

    def drag_move(self, mime_data, x, y):
        """ Handle a drag event moving within this canvas item. Return action if handled. """
        return "ignore"

    def drop(self, mime_data, x, y):
        """ Handle a drop event in this canvas item. Return action if handled. """
        return "ignore"

    def pan_gesture(self, dx, dy):
        """ Handle a pan gesture in this canvas item. Return action if handled. """
        return False

    def simulate_click(self, p, modifiers=None):
        modifiers = Test.KeyboardModifiers() if not modifiers else modifiers
        self.mouse_pressed(p[1], p[0], modifiers)
        self.mouse_released(p[1], p[0], modifiers)

    def simulate_drag(self, p1, p2, modifiers=None):
        modifiers = Test.KeyboardModifiers() if not modifiers else modifiers
        self.mouse_pressed(p1[1], p1[0], modifiers)
        self.mouse_position_changed(p1[1], p1[0], modifiers)
        midpoint = Geometry.midpoint(p1, p2)
        self.mouse_position_changed(midpoint[1], midpoint[0], modifiers)
        self.mouse_position_changed(p2[1], p2[0], modifiers)
        self.mouse_released(p2[1], p2[0], modifiers)


class CanvasItemAbstractLayout(object):

    """
        Layout canvas items within a larger space.

        Subclasses must implement layout method.

        NOTE: origin=0 is at the top
    """

    def __init__(self, margins=None, spacing=None):
        self.margins = margins if margins is not None else Geometry.Margins(0, 0, 0, 0)
        self.spacing = spacing if spacing else 0

    @classmethod
    def calculate_layout(cls, canvas_origin, canvas_size, canvas_item_constraints, spacing):
        """
            Calculate the layout within the canvas for the given item constraints and spacing.

            Returns the origins and sizes for each item.
        """
        solver = Solver(canvas_origin, canvas_size, canvas_item_constraints, spacing)
        solver.solve()
        return solver.origins, solver.sizes

    def calculate_row_layout(self, canvas_origin, canvas_size, canvas_items):
        """ Use calculate_layout to return the positions of canvas items as if they are in a row. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_width_constraint(content_width) for canvas_item in canvas_items]
        return CanvasItemAbstractLayout.calculate_layout(content_left, content_width, constraints, self.spacing)

    def calculate_column_layout(self, canvas_origin, canvas_size, canvas_items):
        """ Use calculate_layout to return the positions of canvas items as if they are in a column. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_height_constraint(content_height) for canvas_item in canvas_items]
        return CanvasItemAbstractLayout.calculate_layout(content_top, content_height, constraints, self.spacing)

    def update_canvas_item_layout(self, canvas_item_origin, canvas_item_size, canvas_item, trigger_update=True):
        """ Given a container box, adjust a single canvas item within the box according to aspect_ratio constraints. """
        # TODO: Also adjust canvas items for maximums, and positioning
        aspect_ratio = canvas_item_size.aspect_ratio
        rect = (canvas_item_origin, canvas_item_size)
        layout_sizing = canvas_item.layout_sizing
        if layout_sizing.minimum_aspect_ratio is not None and aspect_ratio < layout_sizing.minimum_aspect_ratio:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.minimum_aspect_ratio)
        elif layout_sizing.maximum_aspect_ratio is not None and aspect_ratio > layout_sizing.maximum_aspect_ratio:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.maximum_aspect_ratio)
        elif layout_sizing.preferred_aspect_ratio is not None:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.preferred_aspect_ratio)
        canvas_item_origin = Geometry.IntPoint.make(rect[0])
        canvas_item_size = Geometry.IntSize.make(rect[1])
        canvas_item.update_layout(canvas_item_origin, canvas_item_size, trigger_update)
        if trigger_update:
            canvas_item.update()

    def layout_canvas_items(self, x_positions, y_positions, widths, heights, canvas_items, trigger_update):
        """ Set the container boxes for the canvas items using update_canvas_item_layout on the individual items. """
        for index, canvas_item in enumerate(canvas_items):
            if canvas_item is not None:
                canvas_item_origin = Geometry.IntPoint(x=x_positions[index], y=y_positions[index])
                canvas_item_size = Geometry.IntSize(width=widths[index], height=heights[index])
                self.update_canvas_item_layout(canvas_item_origin, canvas_item_size, canvas_item, trigger_update)

    def _update_sizing_property(self, sizing, canvas_item_sizing, property, combiner, clear_if_missing=False):
        """ Utility method for updating the property of the sizing object using the combiner function and the canvas_item_sizing. """
        canvas_item_value = getattr(canvas_item_sizing, property)
        value = getattr(sizing, property)
        if canvas_item_value is not None:
            if clear_if_missing:
                setattr(sizing, property, combiner(value, canvas_item_value) if value is not None else None)
            else:
                setattr(sizing, property, combiner(value, canvas_item_value) if value is not None else canvas_item_value)
        elif clear_if_missing:
            setattr(sizing, property, None)

    def _get_overlap_sizing(self, canvas_items):
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is stacked/overlapping.
            Does not include spacing or margins.
        """
        sizing = Sizing()
        sizing.maximum_width = MAX_VALUE
        sizing.maximum_height = MAX_VALUE
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_width", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_height", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_width", max)  # if any minimum_width is present, take the maximum one
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_height", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_width", min, True)  # if all maximum_widths are present, take the minimum one
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_height", min, True)
        if sizing.maximum_width == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.maximum_height == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_height = None
        return sizing

    def _get_column_sizing(self, canvas_items):
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is a column.
            Does not include spacing or margins.
        """
        sizing = Sizing()
        sizing.maximum_width = MAX_VALUE
        sizing.maximum_height = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_width", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_height", operator.add)
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_width", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_height", operator.add)
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_width", min, True)
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_height", operator.add, True)
        if sizing.maximum_width == MAX_VALUE:
            sizing.maximum_width = None
        if sizing.maximum_height == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_height = None
        return sizing

    def _get_row_sizing(self, canvas_items):
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is a column.
            Does not include spacing or margins.
        """
        sizing = Sizing()
        sizing.maximum_width = 0
        sizing.maximum_height = MAX_VALUE
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_width", operator.add)
                self._update_sizing_property(sizing, canvas_item_sizing, "preferred_height", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_width", operator.add)
                self._update_sizing_property(sizing, canvas_item_sizing, "minimum_height", max)
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_width", operator.add, True)
                self._update_sizing_property(sizing, canvas_item_sizing, "maximum_height", min, True)
        if sizing.maximum_width == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.maximum_height == MAX_VALUE:
            sizing.maximum_height = None
        return sizing

    def _adjust_sizing(self, sizing, x_spacing, y_spacing):
        """ Adjust the sizing object by adding margins and spacing. Spacing is total, not per item. """
        if sizing.minimum_width is not None:
            sizing.minimum_width += self.margins.left + self.margins.right + x_spacing
        if sizing.maximum_width is not None:
            sizing.maximum_width += self.margins.left + self.margins.right + x_spacing
        if sizing.preferred_width is not None:
            sizing.preferred_width += self.margins.left + self.margins.right + x_spacing
        if sizing.minimum_height is not None:
            sizing.minimum_height += self.margins.top + self.margins.bottom + y_spacing
        if sizing.maximum_height is not None:
            sizing.maximum_height += self.margins.top + self.margins.bottom + y_spacing
        if sizing.preferred_height is not None:
            sizing.preferred_height += self.margins.top + self.margins.bottom + y_spacing

    def insert_canvas_item(self, before_index, canvas_item, pos):
        """
            Subclasses may override this method to get position specific information when a canvas item is added to
            the layout.
        """
        pass

    def add_canvas_item(self, canvas_item, pos):
        """
            Subclasses may override this method to get position specific information when a canvas item is added to
            the layout.
        """
        pass

    def remove_canvas_item(self, canvas_item):
        """
            Subclasses may override this method to clean up position specific information when a canvas item is removed
            from the layout.
        """
        pass

    def replace_canvas_item(self, old_canvas_item, new_canvas_item):
        """
            Subclasses may override this method to replace an existing canvas item.
        """
        pass

    def layout(self, canvas_origin, canvas_size, canvas_items, trigger_update=True):
        """ Subclasses must override this method to layout canvas item. """
        raise NotImplementedError()

    def get_sizing(self, canvas_items):
        """
            Return the sizing object for this layout. Includes spacing and margins.

            Subclasses must implement.
        """
        raise NotImplementedError()


class CanvasItemLayout(CanvasItemAbstractLayout):

    """
        Default layout which overlays all items on one another.

        Pass margins.
    """

    def __init__(self, margins=None, spacing=None):
        super(CanvasItemLayout, self).__init__(margins, spacing)

    def layout(self, canvas_origin, canvas_size, canvas_items, trigger_update=True):
        for canvas_item in canvas_items:
            self.update_canvas_item_layout(canvas_origin, canvas_size, canvas_item, trigger_update)

    def get_sizing(self, canvas_items):
        sizing = self._get_overlap_sizing(canvas_items)
        self._adjust_sizing(sizing, 0, 0)
        return sizing

    def create_spacing_item(self, spacing):
        raise NotImplementedError()

    def create_stretch_item(self):
        raise NotImplementedError()


class CanvasItemColumnLayout(CanvasItemAbstractLayout):

    """
        Layout items in a column.

        Pass margins and spacing.
    """

    def __init__(self, margins=None, spacing=None):
        super(CanvasItemColumnLayout, self).__init__(margins, spacing)

    def layout(self, canvas_origin, canvas_size, canvas_items, trigger_update=True):
        # calculate the vertical placement
        y_positions, heights = self.calculate_column_layout(canvas_origin, canvas_size, canvas_items)
        x_positions = [canvas_origin.x + self.margins.left] * len(canvas_items)
        widths = [canvas_size.width - self.margins.left - self.margins.right] * len(canvas_items)
        self.layout_canvas_items(x_positions, y_positions, widths, heights, canvas_items, trigger_update)

    def get_sizing(self, canvas_items):
        sizing = self._get_column_sizing(canvas_items)
        self._adjust_sizing(sizing, 0, self.spacing * (len(canvas_items) - 1))
        return sizing

    def create_spacing_item(self, spacing):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.minimum_height = spacing
        spacing_item.sizing.maximum_height = spacing
        return spacing_item

    def create_stretch_item(self):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.minimum_width = 0.0
        spacing_item.sizing.minimum_width = 0.0
        return spacing_item


class CanvasItemRowLayout(CanvasItemAbstractLayout):

    """
        Layout items in a row.

        Pass margins and spacing.
    """

    def __init__(self, margins=None, spacing=None):
        super(CanvasItemRowLayout, self).__init__(margins, spacing)

    def layout(self, canvas_origin, canvas_size, canvas_items, trigger_update=True):
        # calculate the vertical placement
        x_positions, widths = self.calculate_row_layout(canvas_origin, canvas_size, canvas_items)
        y_positions = [canvas_origin.y + self.margins.top] * len(canvas_items)
        heights = [canvas_size.height - self.margins.top - self.margins.bottom] * len(canvas_items)
        self.layout_canvas_items(x_positions, y_positions, widths, heights, canvas_items, trigger_update)

    def get_sizing(self, canvas_items):
        sizing = self._get_row_sizing(canvas_items)
        self._adjust_sizing(sizing, self.spacing * (len(canvas_items) - 1), 0)
        return sizing

    def create_spacing_item(self, spacing):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.minimum_width = spacing
        spacing_item.sizing.maximum_width = spacing
        return spacing_item

    def create_stretch_item(self):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.minimum_height = 0.0
        spacing_item.sizing.maximum_height = 0.0
        return spacing_item


class CanvasItemGridLayout(CanvasItemAbstractLayout):

    """
        Layout items in a grid specified by size (IntSize).

        Pass margins and spacing.

        Canvas items must be added to container canvas item using
        add_canvas_item with the position (IntPoint) passed as pos
        parameter.
    """

    def __init__(self, size, margins=None, spacing=None):
        super(CanvasItemGridLayout, self).__init__(margins, spacing)
        assert size.width > 0 and size.height > 0
        self.__size = size
        self.__columns = [[None for _ in range(self.__size.height)] for _ in range(self.__size.width)]

    def add_canvas_item(self, canvas_item, pos):
        assert pos.x >= 0 and pos.x < self.__size.width
        assert pos.y >= 0 and pos.y < self.__size.height
        self.__columns[pos.x][pos.y] = canvas_item

    def remove_canvas_item(self, canvas_item):
        canvas_item.close()
        for x in range(self.__size.width):
            for y in range(self.__size.height):
                if self.__columns[x][y] == canvas_item:
                    self.__columns[x][y] = None

    def layout(self, canvas_origin, canvas_size, canvas_items, trigger_update=True):
        # calculate the horizontal placement
        # calculate the sizing (x, width) for each column
        canvas_item_count = self.__size.width
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = list()
        for x in range(self.__size.width):
            sizing = self._get_overlap_sizing([self.__columns[x][y] for y in range(self.__size.height)])
            constraints.append(sizing.get_width_constraint(content_width))
        # run the layout engine
        x_positions, widths = CanvasItemAbstractLayout.calculate_layout(content_left, content_width, constraints, self.spacing)
        # calculate the vertical placement
        # calculate the sizing (y, height) for each row
        canvas_item_count = self.__size.height
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = list()
        for y in range(self.__size.height):
            sizing = self._get_overlap_sizing([self.__columns[x][y] for x in range(self.__size.width)])
            constraints.append(sizing.get_height_constraint(content_height))
        # run the layout engine
        y_positions, heights = CanvasItemAbstractLayout.calculate_layout(content_top, content_height, constraints, self.spacing)
        # do the layout
        combined_xs = list()
        combined_ys = list()
        combined_widths = list()
        combined_heights = list()
        combined_canvas_items = list()
        for x in range(self.__size.width):
            for y in range(self.__size.height):
                if self.__columns[x][y] is not None:
                    combined_xs.append(x_positions[x])
                    combined_ys.append(y_positions[y])
                    combined_widths.append(widths[x])
                    combined_heights.append(heights[y])
                    combined_canvas_items.append(self.__columns[x][y])
        self.layout_canvas_items(combined_xs, combined_ys, combined_widths, combined_heights, combined_canvas_items, trigger_update)

    def get_sizing(self, canvas_items):
        """
            Calculate the sizing for the grid. Treat columns and rows independently.

            Override from abstract layout.
        """
        sizing = Sizing()
        # the widths
        canvas_item_sizings = list()
        for x in range(self.__size.width):
            canvas_items = [self.__columns[x][y] for y in range(self.__size.height)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items))
        for canvas_item_sizing in canvas_item_sizings:
            self._update_sizing_property(sizing, canvas_item_sizing, "preferred_width", operator.add)
            self._update_sizing_property(sizing, canvas_item_sizing, "minimum_width", operator.add)
            self._update_sizing_property(sizing, canvas_item_sizing, "maximum_width", operator.add)
        # the heights
        canvas_item_sizings = list()
        for y in range(self.__size.height):
            canvas_items = [self.__columns[x][y] for x in range(self.__size.width)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items))
        for canvas_item_sizing in canvas_item_sizings:
            self._update_sizing_property(sizing, canvas_item_sizing, "preferred_height", operator.add)
            self._update_sizing_property(sizing, canvas_item_sizing, "minimum_height", operator.add)
            self._update_sizing_property(sizing, canvas_item_sizing, "maximum_height", operator.add)
        self._adjust_sizing(sizing, self.spacing * (self.__size.width - 1), self.spacing * (self.__size.height - 1))
        return sizing


class CanvasItemComposition(AbstractCanvasItem):

    """
        A composite canvas item comprised of other canvas items.

        Optionally includes a layout.

        All canvas messages are passed to children appropriately.

        Access child canvas items using canvas_items.
    """

    def __init__(self):
        super(CanvasItemComposition, self).__init__()
        self.__canvas_items = []
        self.layout = CanvasItemLayout()

    def close(self):
        canvas_items_copy = copy.copy(self.__canvas_items)
        for canvas_item in canvas_items_copy:
            canvas_item.close()
            canvas_item.container = None
            self.__canvas_items.remove(canvas_item)
        self.__canvas_items = None
        super(CanvasItemComposition, self).close()

    @property
    def canvas_items(self):
        """ Return a copy of the canvas items managed by this composition. """
        return copy.copy(self.__canvas_items)

    def update_layout(self, canvas_origin, canvas_size, trigger_update=True):
        """Override from abstract canvas item.

        After calling the super class, ask the layout object to layout the list of canvas items in this object.
        """
        super(CanvasItemComposition, self).update_layout(canvas_origin, canvas_size, trigger_update)
        # make sure arguments are point, size
        canvas_size = Geometry.IntSize.make(canvas_size)
        self.layout.layout(Geometry.IntPoint(), canvas_size, self.__canvas_items, trigger_update)

    # override sizing information. let layout provide it.
    @property
    def layout_sizing(self):
        sizing = super(CanvasItemComposition, self).sizing
        layout_sizing = self.layout.get_sizing(self.__canvas_items)
        if sizing.minimum_width is not None:
            layout_sizing.minimum_width = sizing.minimum_width
        if sizing.maximum_width is not None:
            layout_sizing.maximum_width = sizing.maximum_width
        if sizing.preferred_width is not None:
            layout_sizing.preferred_width = sizing.preferred_width
        if sizing.minimum_height is not None:
            layout_sizing.minimum_height = sizing.minimum_height
        if sizing.maximum_height is not None:
            layout_sizing.maximum_height = sizing.maximum_height
        if sizing.preferred_height is not None:
            layout_sizing.preferred_height = sizing.preferred_height
        if sizing.minimum_aspect_ratio is not None:
            layout_sizing.minimum_aspect_ratio = sizing.minimum_aspect_ratio
        if sizing.maximum_aspect_ratio is not None:
            layout_sizing.maximum_aspect_ratio = sizing.maximum_aspect_ratio
        if sizing.preferred_aspect_ratio is not None:
            layout_sizing.preferred_aspect_ratio = sizing.preferred_aspect_ratio
        if len(self.__canvas_items) == 0 and sizing.collapsible:
            layout_sizing.minimum_width = 0
            layout_sizing.preferred_width = 0
            layout_sizing.maximum_width = 0
            layout_sizing.minimum_height = 0
            layout_sizing.preferred_height = 0
            layout_sizing.maximum_height = 0
        return layout_sizing

    def canvas_item_layout_sizing_changed(self, canvas_item):
        """ Contained canvas items call this when their layout_sizing changes. """
        self.refresh_layout()

    def _insert_canvas_item_direct(self, before_index, canvas_item, pos=None):
        self.insert_canvas_item(before_index, canvas_item, pos)

    def insert_canvas_item(self, before_index, canvas_item, pos=None):
        """ Insert canvas item into layout. pos parameter is layout specific. """
        self.__canvas_items.insert(before_index, canvas_item)
        canvas_item.container = self
        self.layout.add_canvas_item(canvas_item, pos)
        root_container = self.root_container
        if root_container:
            # TODO: refresh layout during add canvas item only as necessary
            # This is a hammer approach: the entire layout up to the root
            # container gets refreshed. Alternatively, one could walk up
            # the container hierarchy and see where the layout_sizing changed
            # and stop when the layout_sizing does not change.
            root_container.refresh_layout()
        return canvas_item

    def insert_spacing(self, before_index, spacing):
        spacing_item = self.layout.create_spacing_item(spacing)
        return self.insert_canvas_item(before_index, spacing_item)

    def insert_stretch(self, before_index):
        stretch_item = self.layout.create_stretch_item()
        return self.insert_canvas_item(before_index, stretch_item)

    def add_canvas_item(self, canvas_item, pos=None):
        """ Add canvas item to layout. pos parameter is layout specific. """
        return self.insert_canvas_item(len(self.__canvas_items), canvas_item, pos)

    def add_spacing(self, spacing):
        return self.insert_spacing(len(self.__canvas_items), spacing)

    def add_stretch(self):
        return self.insert_stretch(len(self.__canvas_items))

    def _remove_canvas_item_direct(self, canvas_item):
        self.__canvas_items.remove(canvas_item)

    def remove_canvas_item(self, canvas_item):
        """ Remove canvas item from layout. Canvas item is closed. """
        canvas_item.close()
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        self.__canvas_items.remove(canvas_item)
        root_container = self.root_container
        if root_container:
            # TODO: refresh layout during remove canvas item only as necessary
            # This is a hammer approach: the entire layout up to the root
            # container gets refreshed. Alternatively, one could walk up
            # the container hierarchy and see where the layout_sizing changed
            # and stop when the layout_sizing does not change.
            root_container.refresh_layout()

    def replace_canvas_item(self, old_canvas_item, new_canvas_item, container=None):
        """ Replace the given canvas item with the new one. Canvas item is closed. """
        index = self.canvas_items.index(old_canvas_item)
        self.remove_canvas_item(old_canvas_item)
        self.insert_canvas_item(index, new_canvas_item)

    def wrap_canvas_item(self, canvas_item, canvas_item_container):
        """ Replace the given canvas item with the container and move the canvas item into the container. """
        index = self.canvas_items.index(canvas_item)
        # remove the existing canvas item, but without closing it.
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        self._remove_canvas_item_direct(canvas_item)
        # insert the canvas item container
        # self.insert_canvas_item(index, canvas_item_container)  # this would adjust splitters. don't do it.
        self._insert_canvas_item_direct(index, canvas_item_container)
        # insert the canvas item into the container
        canvas_item_container.add_canvas_item(canvas_item)
        # update the layout if origin and size already known
        self.refresh_layout()

    def unwrap_canvas_item(self, canvas_item):
        """ Replace the canvas item container with the canvas item. """
        assert len(canvas_item.container.canvas_items) == 1
        assert canvas_item.container.canvas_items[0] == canvas_item
        container = canvas_item.container
        enclosing_container = container.container
        index = enclosing_container.canvas_items.index(container)
        # remove the existing canvas item from the container, but without closing it.
        container.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        container._remove_canvas_item_direct(canvas_item)
        # remove container from enclosing container
        enclosing_container._remove_canvas_item_direct(container)
        # insert canvas item into the enclosing container
        # enclosing_container.insert_canvas_item(index, canvas_item)  # this would adjust splitters. don't do it.
        enclosing_container._insert_canvas_item_direct(index, canvas_item)
        # update the layout if origin and size already known
        self.refresh_layout()

    def _repaint(self, drawing_context):
        super(CanvasItemComposition, self)._repaint(drawing_context)
        for canvas_item in self.__canvas_items:
            drawing_context.save()
            try:
                canvas_item_rect = canvas_item.canvas_rect
                drawing_context.translate(canvas_item_rect.left, canvas_item_rect.top)
                canvas_item._repaint(drawing_context)
            finally:
                drawing_context.restore()

    def canvas_items_at_point(self, x, y):
        canvas_items = []
        point = Geometry.IntPoint(x=x, y=y)
        for canvas_item in reversed(self.__canvas_items):
            if canvas_item.canvas_rect.contains_point(point):
                canvas_point = point - Geometry.IntPoint.make(canvas_item.canvas_origin)
                canvas_items.extend(canvas_item.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super(CanvasItemComposition, self).canvas_items_at_point(x, y))
        return canvas_items

    def wheel_changed(self, dx, dy, is_horizontal):
        # always give the mouse canvas item priority (for tracking outside bounds)
        if False:
            pass # self.root_container.mouse_canvas_item.wheel_changed(dx, dy, is_horizontal)
        # now give other canvas items a chance
        else:
            for canvas_item in reversed(self.__canvas_items):
                if canvas_item.wheel_changed(dx, dy, is_horizontal):
                    return True
        return False

    def pan_gesture(self, dx, dy):
        for canvas_item in reversed(self.__canvas_items):
            if canvas_item.pan_gesture(dx, dy):
                return True
        return False


class LayerCanvasItem(CanvasItemComposition):

    def __init__(self):
        super(LayerCanvasItem, self).__init__()
        self.__layer_id = None

    def _repaint(self, drawing_context):
        layer_id = self.__layer_id  # avoid race condition on self.__layer_id by reading just once
        if layer_id:
            drawing_context.draw_layer(layer_id)
        else:
            layer_id = drawing_context.create_layer()
            with drawing_context.layer(layer_id):
                self._repaint_layer(drawing_context)
            self.__layer_id = layer_id

    def _repaint_layer(self, drawing_context):
        super(LayerCanvasItem, self)._repaint(drawing_context)

    def update(self):
        super(LayerCanvasItem, self).update()
        self.__layer_id = None

    def _child_updated(self, child):
        super(LayerCanvasItem, self)._child_updated(child)
        self.__layer_id = None


class ScrollAreaCanvasItem(AbstractCanvasItem):

    """
        A scroll area canvas item with content.

        The content property holds the content of the scroll area.

        This scroll area controls the canvas_origin of the content, but not the
        size. When the scroll area is resized, update_layout will be called on
        the content, during which the content is free to adjust its canvas size.
        When the call to update_layout returns, this scroll area will adjust
        the canvas origin separately.

        The content canvas_rect property describes the position that the content
        is drawn within the scroll area. This means that content items must
        already have a layout when they're added to this scroll area.

        The content canvas_origin will typically be negative if the content
        canvas_size is larger than the scroll area canvas size.

        The content canvas_origin will typically be positive (or zero) if the
        content canvas_size is smaller than the scroll area canvas size.
    """

    def __init__(self, content=None):
        super(ScrollAreaCanvasItem, self).__init__()
        self.__content = None
        self._on_validate_content_origin = None
        if content:
            self.content = content
        self.auto_resize_contents = False

    def close(self):
        if self.__content:
            self.__content.close()
            self.__content.container = None
        self.__content = None
        super(ScrollAreaCanvasItem, self).close()

    @property
    def content(self):
        """ Return the content of the scroll area. """
        return self.__content

    @content.setter
    def content(self, content):
        """ Set the content of the scroll area. """
        # remove the old content
        if self.__content:
            self.__content.container = None
            self.__content.on_layout_updated = None
        # add the new content
        self.__content = content
        content.container = self
        content.on_layout_updated = self.__content_layout_updated
        self.refresh_layout()

    def update_layout(self, canvas_origin, canvas_size, trigger_update=True):
        """Override from abstract canvas item.

        After setting the canvas origin and canvas size, like the abstract canvas item,
        update the layout of the content if it has no assigned layout yet. Whether it has
        an assigned layout is determined by whether the canvas origin and canvas size are
        None or not.
        """
        self._set_canvas_origin(canvas_origin)
        self._set_canvas_size(canvas_size)
        if self.__content.canvas_origin is None or self.__content.canvas_size is None:
            # if content has no assigned layout, update its layout relative to this object.
            # it will get a 0,0 origin but the same size as this scroll area.
            self.__content.update_layout(Geometry.IntPoint(), self.canvas_size, trigger_update)
            if trigger_update:
                self.__content.update()
        elif self.auto_resize_contents:
            # if content has no assigned layout, update its layout relative to this object.
            # it will get a 0,0 origin but the same size as this scroll area.
            self.__content.update_layout(self.__content.canvas_origin, self.canvas_size, trigger_update)
            if trigger_update:
                self.__content.update()
        # validate the content origin. this is used for the scroll bar canvas item to ensure that the content is
        # consistent with the scroll bar.
        self.__content_layout_updated(self.__content.canvas_origin, self.__content.canvas_size, trigger_update)
        # NOTE: super is never called for this implementation
        # call on_layout_updated, just like the super implementation.
        if self.on_layout_updated:
            self.on_layout_updated(self.canvas_origin, self.canvas_size, trigger_update)

    def __content_layout_updated(self, canvas_origin, canvas_size, trigger_update):
        # whenever the content layout changes, this method gets called.
        # adjust the canvas_origin of the content if necessary. pass the canvas_origin, canvas_size of the content.
        # this method is used in the scroll bar canvas item to ensure that the content stays within view and
        # consistent with the scroll bar when the scroll area gets a new layout.
        if self._on_validate_content_origin and canvas_origin is not None and canvas_size is not None and self.canvas_origin is not None and self.canvas_size is not None:
            self.__content._set_canvas_origin(self._on_validate_content_origin(canvas_origin))

    def _repaint(self, drawing_context):
        super(ScrollAreaCanvasItem, self)._repaint(drawing_context)
        drawing_context.save()
        try:
            drawing_context.clip_rect(self.canvas_origin[1], self.canvas_origin[0], self.canvas_size[1], self.canvas_size[0])
            drawing_context.translate(self.__content.canvas_origin[1], self.__content.canvas_origin[0])
            visible_rect = Geometry.IntRect(origin=-Geometry.IntPoint.make(self.__content.canvas_origin), size=Geometry.IntSize.make(self.canvas_size))
            self.__content._repaint_visible(drawing_context, visible_rect)
        finally:
            drawing_context.restore()

    def canvas_items_at_point(self, x, y):
        canvas_items = []
        point = Geometry.IntPoint(x=x, y=y)
        if self.__content.canvas_rect.contains_point(point):
            canvas_point = point - Geometry.IntPoint.make(self.__content.canvas_origin)
            canvas_items.extend(self.__content.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super(ScrollAreaCanvasItem, self).canvas_items_at_point(x, y))
        return canvas_items

    def wheel_changed(self, dx, dy, is_horizontal):
        return self.__content.wheel_changed(dx, dy, is_horizontal)

    def pan_gesture(self, dx, dy):
        return self.__content.pan_gesture(dx, dy)


class SplitterCanvasItem(CanvasItemComposition):

    def __init__(self, orientation=None):
        super(SplitterCanvasItem, self).__init__()
        self.orientation = orientation if orientation else "vertical"
        self.wants_mouse_events = True
        if self.orientation == "horizontal":
            self.layout = CanvasItemColumnLayout()
        else:
            self.layout = CanvasItemRowLayout()
        self.sizings = []
        self.__tracking = False

    def __calculate_layout(self, canvas_origin, canvas_size):
        if self.orientation == "horizontal":
            content_origin = Geometry.IntPoint.make(canvas_origin).y
            content_size = Geometry.IntSize.make(canvas_size).height
            constraints = [sizing.get_height_constraint(content_size) for sizing in self.sizings]
        else:
            content_origin = Geometry.IntPoint.make(canvas_origin).x
            content_size = Geometry.IntSize.make(canvas_size).width
            constraints = [sizing.get_width_constraint(content_size) for sizing in self.sizings]
        solver = Solver(content_origin, content_size, constraints)
        solver.solve()
        return solver.origins, solver.sizes

    @property
    def splits(self):
        """ Return the canvas item splits, which represent the relative size of each child. """
        if self.canvas_origin is not None:
            if self.orientation == "horizontal":
                content_size = Geometry.IntSize.make(self.canvas_size).height
            else:
                content_size = Geometry.IntSize.make(self.canvas_size).width
            _, sizes = self.__calculate_layout(self.canvas_origin, self.canvas_size)
            return [float(size) / content_size for size in sizes]
        return None

    @splits.setter
    def splits(self, splits):
        assert len(splits) == len(self.sizings)
        for split, sizing in zip(splits, self.sizings):
            if self.orientation == "horizontal":
                sizing.preferred_height = split
            else:
                sizing.preferred_width = split
        self.refresh_layout()

    def _insert_canvas_item_direct(self, before_index, canvas_item, pos=None):
        super(SplitterCanvasItem, self).insert_canvas_item(before_index, canvas_item)

    def insert_canvas_item(self, before_index, canvas_item, sizing=None):
        sizing = copy.copy(sizing) if sizing else Sizing()
        if self.orientation == "horizontal":
            sizing.preferred_height = None
            if sizing.minimum_height is None:
                sizing.minimum_height = 0.1
        else:
            sizing.preferred_width = None
            if sizing.minimum_width is None:
                sizing.minimum_width = 0.1
        self.sizings.insert(before_index, sizing)
        super(SplitterCanvasItem, self).insert_canvas_item(before_index, canvas_item)

    def remove_canvas_item(self, canvas_item):
        del self.sizings[self.canvas_items.index(canvas_item)]
        super(SplitterCanvasItem, self).remove_canvas_item(canvas_item)

    def update_layout(self, canvas_origin, canvas_size, trigger_update=True):
        """Override from abstract canvas item.

        Attempt to use existing layout techniques for each of the canvas items, but put fixed size
        constraints on each item before allowing it to layout.
        """
        _, sizes = self.__calculate_layout(canvas_origin, canvas_size)
        if self.orientation == "horizontal":
            for canvas_item, size in zip(self.canvas_items, sizes):
                canvas_item.sizing.set_fixed_height(size)
            for sizing, size in zip(self.sizings, sizes):
                sizing.preferred_height = size
        else:
            for canvas_item, size in zip(self.canvas_items, sizes):
                canvas_item.sizing.set_fixed_width(size)
            for sizing, size in zip(self.sizings, sizes):
                sizing.preferred_width = size
        # have the abstract canvas item do its layout thing with the constraints imposed above.
        super(SplitterCanvasItem, self).update_layout(canvas_origin, canvas_size, trigger_update)

    def canvas_items_at_point(self, x, y):
        assert self.canvas_origin is not None and self.canvas_size is not None
        origins, _ = self.__calculate_layout(self.canvas_origin, self.canvas_size)
        if self.orientation == "horizontal":
            for origin in origins[1:]:  # don't check the '0' origin
                if abs(y - origin) < 6:
                    return [self]
        else:
            for origin in origins[1:]:  # don't check the '0' origin
                if abs(x - origin) < 6:
                    return [self]
        return super(SplitterCanvasItem, self).canvas_items_at_point(x, y)

    def _repaint(self, drawing_context):
        super(SplitterCanvasItem, self)._repaint(drawing_context)
        assert self.canvas_origin is not None and self.canvas_size is not None
        origins, _ = self.__calculate_layout(self.canvas_origin, self.canvas_size)
        drawing_context.save()
        try:
            drawing_context.begin_path()
            for origin in origins[1:]:  # don't paint the '0' origin
                if self.orientation == "horizontal":
                    drawing_context.move_to(self.canvas_bounds.left, origin)
                    drawing_context.line_to(self.canvas_bounds.right, origin)
                else:
                    drawing_context.move_to(origin, self.canvas_bounds.top)
                    drawing_context.line_to(origin, self.canvas_bounds.bottom)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#666"
            drawing_context.stroke()
        finally:
            drawing_context.restore()

    def __hit_test(self, x, y, modifiers):
        origins, _ = self.__calculate_layout(self.canvas_origin, self.canvas_size)
        if self.orientation == "horizontal":
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(y - origin) < 6:
                    return "horizontal"
        else:
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(x - origin) < 6:
                    return "vertical"
        return None

    def mouse_pressed(self, x, y, modifiers):
        assert self.canvas_origin is not None and self.canvas_size is not None
        origins, _ = self.__calculate_layout(self.canvas_origin, self.canvas_size)
        if self.orientation == "horizontal":
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(y - origin) < 6:
                    self.__tracking = True
                    self.__tracking_start_pos = Geometry.IntPoint(y=y, x=x)
                    self.__tracking_start_index = index
                    self.__tracking_start_preferred = self.sizings[index].preferred_height
                    self.__tracking_start_preferred_next = self.sizings[index + 1].preferred_height
                    return True
        else:
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(x - origin) < 6:
                    self.__tracking = True
                    self.__tracking_start_pos = Geometry.IntPoint(y=y, x=x)
                    self.__tracking_start_index = index
                    self.__tracking_start_preferred = self.sizings[index].preferred_width
                    self.__tracking_start_preferred_next = self.sizings[index + 1].preferred_width
                    return True
        return super(SplitterCanvasItem, self).mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        self.__tracking = False
        return True

    def mouse_position_changed(self, x, y, modifiers):
        if self.__tracking:
            if self.orientation == "horizontal":
                offset = y - self.__tracking_start_pos.y
                self.sizings[self.__tracking_start_index].preferred_height = self.__tracking_start_preferred + offset
                self.sizings[self.__tracking_start_index + 1].preferred_height = self.__tracking_start_preferred_next - offset
            else:
                offset = x - self.__tracking_start_pos.x
                self.sizings[self.__tracking_start_index].preferred_width = self.__tracking_start_preferred + offset
                self.sizings[self.__tracking_start_index + 1].preferred_width = self.__tracking_start_preferred_next - offset
            # fix the size of all children except for the two in question
            old_sizings = copy.deepcopy(self.sizings)
            for index, sizing in enumerate(self.sizings):
                if index != self.__tracking_start_index and index != self.__tracking_start_index + 1:
                    if self.orientation == "horizontal":
                        sizing.set_fixed_width(sizing.preferred_height)
                    else:
                        sizing.set_fixed_width(sizing.preferred_width)
            # update the layout
            self.refresh_layout()
            # restore the freedom of the others
            for index, pair in enumerate(zip(old_sizings, self.sizings)):
                old_sizing, sizing = pair
                if index != self.__tracking_start_index and index != self.__tracking_start_index + 1:
                    sizing.copy_from(old_sizing)
            return True
        else:
            control = self.__hit_test(x, y, modifiers)
            if control == "horizontal":
                self.cursor_shape = "split_vertical"
            elif control == "vertical":
                self.cursor_shape = "split_horizontal"
            else:
                self.cursor_shape = None
            return super(SplitterCanvasItem, self).mouse_position_changed(x, y, modifiers)


PositionLength = collections.namedtuple("PositionLength", ["position", "length"])


class ScrollBarCanvasItem(AbstractCanvasItem):

    """ A scroll bar for a scroll area. """

    def __init__(self, scroll_area_canvas_item):
        super(ScrollBarCanvasItem, self).__init__()
        self.wants_mouse_events = True
        self.sizing.set_fixed_width(16)
        self.__scroll_area_canvas_item = scroll_area_canvas_item
        # when the scroll area content layout changes, this method will get called.
        self.__scroll_area_canvas_item._on_validate_content_origin = self.__validate_content_origin
        self.__tracking = False

    def _repaint(self, drawing_context):
        # canvas size, thumb rect
        canvas_size = self.canvas_size
        thumb_rect = self.thumb_rect

        # draw it
        drawing_context.save()
        # draw the border of the scroll bar
        drawing_context.begin_path()
        drawing_context.rect(0, 0, canvas_size.width, canvas_size.height)
        gradient = drawing_context.create_linear_gradient(canvas_size.width, canvas_size.height, 0, 0, canvas_size.width, 0)
        gradient.add_color_stop(0.0, "#F2F2F2")
        gradient.add_color_stop(0.35, "#FDFDFD")
        gradient.add_color_stop(0.65, "#FDFDFD")
        gradient.add_color_stop(1.0, "#F2F2F2")
        drawing_context.fill_style = gradient
        drawing_context.fill()
        # draw the thumb, if any
        if thumb_rect.height > 0:
            drawing_context.save()
            drawing_context.begin_path()
            drawing_context.move_to(thumb_rect.width - 8, thumb_rect.top + 6)
            drawing_context.line_to(thumb_rect.width - 8, thumb_rect.bottom - 6)
            drawing_context.line_width = 8.0
            drawing_context.line_cap = "round"
            drawing_context.stroke_style = "#888" if self.__tracking else "#CCC"
            drawing_context.stroke()
            drawing_context.restore()
        # draw inside edge
        drawing_context.begin_path()
        drawing_context.move_to(0, 0)
        drawing_context.line_to(0, canvas_size.height)
        drawing_context.line_width = 0.5
        drawing_context.stroke_style = "#E3E3E3"
        drawing_context.stroke()
        # draw outside
        drawing_context.begin_path()
        drawing_context.move_to(canvas_size.width, 0)
        drawing_context.line_to(canvas_size.width, canvas_size.height)
        drawing_context.line_width = 0.5
        drawing_context.stroke_style = "#999999"
        drawing_context.stroke()
        drawing_context.restore()

    def get_thumb_position_and_length(self, canvas_length, visible_length, content_length, content_offset):
        """
            Return the thumb position and length as a tuple of ints.

            The canvas_length is the size of the canvas of the scroll bar.

            The visible_length is the size of the visible area of the scroll area.

            The content_length is the size of the content of the scroll area.

            The content_offset is the position of the content within the scroll area. It
            will always be negative or zero.
        """
        # the scroll_range defines the maximum negative value of the content_offset.
        scroll_range = max(content_length - visible_length, 0)
        # content_offset should be negative, but not more negative than the scroll_range.
        assert content_offset <= 0 and content_offset >= -scroll_range
        # the length of the thumb is the visible_length multiplied by the ratio of
        # visible_length to the content_length. however, a minimum height is enforced
        # so that the user can always grab it. if the thumb is invisible (the content_length
        # is less than or equal to the visible_length) then the thumb will have a length of zero.
        if content_length > visible_length:
            thumb_length = int(canvas_length * (float(visible_length) / content_length))
            thumb_length = max(thumb_length, 32)
            # the position of the thumb is the content_offset over the content_length multiplied by
            # the free range of the thumb which is the canvas_length minus the thumb_length.
            thumb_position = int((canvas_length - thumb_length) * (float(-content_offset) / scroll_range))
        else:
            thumb_length = 0
            thumb_position = 0
        return PositionLength(thumb_position, thumb_length)

    @property
    def thumb_rect(self):
        # return the thumb rect for the given canvas_size
        canvas_size = Geometry.IntSize.make(self.canvas_size)
        visible_height = self.__scroll_area_canvas_item.canvas_size[0]
        content_height = self.__scroll_area_canvas_item.content.canvas_size[0]
        content_offset = self.__scroll_area_canvas_item.content.canvas_origin[0]
        thumb_y, thumb_height = self.get_thumb_position_and_length(canvas_size[0], visible_height, content_height, content_offset)
        thumb_origin = Geometry.IntPoint(x=0, y=thumb_y)
        thumb_size = Geometry.IntSize(width=canvas_size.width, height=thumb_height)
        return Geometry.IntRect(origin=thumb_origin, size=thumb_size)

    def __validate_content_origin(self, content_canvas_origin):
        # when the scroll area content layout changes, this method will get called.
        # ensure that the content matches the scroll position.
        visible_height = self.__scroll_area_canvas_item.canvas_size[0]
        content_height = self.__scroll_area_canvas_item.content.canvas_size[0]
        scroll_range = max(content_height - visible_height, 0)
        return Geometry.IntPoint(x=content_canvas_origin.x, y=max(min(content_canvas_origin.y, 0), -scroll_range))

    def mouse_pressed(self, x, y, modifiers):
        thumb_rect = self.thumb_rect
        pos = Geometry.IntPoint(x=x, y=y)
        if thumb_rect.contains_point(pos):
            self.__tracking = True
            self.__tracking_start = pos
            self.__tracking_content_offset = self.__scroll_area_canvas_item.content.canvas_origin
            self.update()
            return True
        elif y < thumb_rect.top:
            self.__adjust_thumb(-1)
            return True
        elif y > thumb_rect.bottom:
            self.__adjust_thumb(1)
            return True
        return super(ScrollBarCanvasItem, self).mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        self.__tracking = False
        self.update()
        return super(ScrollBarCanvasItem, self).mouse_released(x, y, modifiers)

    def __adjust_thumb(self, amount):
        # adjust the position up or down one visible screen worth
        visible_height = self.__scroll_area_canvas_item.canvas_size[0]
        content = self.__scroll_area_canvas_item.content
        new_content_offset = Geometry.IntPoint(y=content.canvas_origin[0] - visible_height * amount, x=content.canvas_origin[1])
        content.update_layout(new_content_offset, content.canvas_size)
        content.update()

    def adjust_content_offset(self, canvas_length, visible_length, content_length, content_offset, mouse_offset):
        """
            Return the adjusted content offset.

            The canvas_length is the size of the canvas of the scroll bar.

            The visible_length is the size of the visible area of the scroll area.

            The content_length is the size of the content of the scroll area.

            The content_offset is the position of the content within the scroll area. It
            will always be negative or zero.

            The mouse_offset is the offset of the mouse.
        """
        scroll_range = max(content_length - visible_length, 0)
        _, thumb_length = self.get_thumb_position_and_length(canvas_length, visible_length, content_length, content_offset)
        offset_rel = int(scroll_range * float(mouse_offset) / (canvas_length - thumb_length))
        return max(min(content_offset - offset_rel, 0), -scroll_range)

    def mouse_position_changed(self, x, y, modifiers):
        if self.__tracking:
            pos = Geometry.IntPoint(x=x, y=y)
            mouse_offset_v = pos.y - self.__tracking_start.y
            visible_height = self.__scroll_area_canvas_item.canvas_size[0]
            content_height = self.__scroll_area_canvas_item.content.canvas_size[0]
            new_content_offset_v = self.adjust_content_offset(self.canvas_size[0], visible_height, content_height, self.__tracking_content_offset[0], mouse_offset_v)
            new_content_offset = Geometry.IntPoint(x=self.__tracking_content_offset[1], y=new_content_offset_v)
            self.__scroll_area_canvas_item.content._set_canvas_origin(new_content_offset)
            self.__scroll_area_canvas_item.refresh_layout()
            self.__scroll_area_canvas_item.content.update()
        return super(ScrollBarCanvasItem, self).mouse_position_changed(x, y, modifiers)


class RootCanvasItem(CanvasItemComposition):

    """
        The root canvas item acts as a bridge between the higher level ui widget
        and a canvas hierarchy. It connects size notifications, mouse activity,
        keyboard activity, focus activity, and drag and drop actions to the
        canvas item.

        The root canvas item provides a canvas_widget property which is the
        canvas widget associated with this root item.

        The root canvas may be focusable or not. There are two focus states that
        this root canvas item handles: the widget focus and the canvas item focus.
        The widget focus comes from the enclosing widget. If this root canvas item
        has a widget focus, then it can also have a canvas item focus to specify
        which specific canvas item is the focus in this root canvas item's hierarchy.
    """

    def __init__(self, ui, properties=None, max_frame_rate=None):
        super(RootCanvasItem, self).__init__()
        self.__canvas_widget = ui.create_canvas_widget(properties)
        self.__canvas_widget.on_size_changed = self.size_changed
        self.__canvas_widget.on_mouse_clicked = self.__mouse_clicked
        self.__canvas_widget.on_mouse_double_clicked = self.__mouse_double_clicked
        self.__canvas_widget.on_mouse_entered = self.__mouse_entered
        self.__canvas_widget.on_mouse_exited = self.__mouse_exited
        self.__canvas_widget.on_mouse_pressed = self.__mouse_pressed
        self.__canvas_widget.on_mouse_released = self.__mouse_released
        self.__canvas_widget.on_mouse_position_changed = self.__mouse_position_changed
        self.__canvas_widget.on_wheel_changed = self.wheel_changed
        self.__canvas_widget.on_context_menu_event = self.__context_menu_event
        self.__canvas_widget.on_key_pressed = self.__key_pressed
        self.__canvas_widget.on_focus_changed = self.__focus_changed
        self.__canvas_widget.on_drag_enter = self.__drag_enter
        self.__canvas_widget.on_drag_leave = self.__drag_leave
        self.__canvas_widget.on_drag_move = self.__drag_move
        self.__canvas_widget.on_drop = self.__drop
        self.__canvas_widget.on_pan_gesture = self.pan_gesture
        self.__canvas_widget.on_periodic = self.__draw_if_needed
        self.__canvas_widget._root_canvas_item = weakref.ref(self)  # for debugging
        self.__drawing_context_storage = self.__canvas_widget.create_drawing_context_storage()
        self.__max_frame_rate = float(max_frame_rate) if max_frame_rate is not None else DEFAULT_MAX_FRAME_RATE
        self.__repaint_thread = ThreadPool.ThreadDispatcher(self.__repaint_on_thread, minimum_interval=1/50.0)
        self.__repaint_thread.start()
        self.__focused_item = None
        self.__last_focused_item = None
        self.__needs_repaint = True
        self.__needs_repaint_lock = threading.RLock()
        self.__last_repaint = None
        self.__mouse_canvas_item = None  # not None when the mouse is pressed
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item = None
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item = None
        self._set_canvas_origin(Geometry.IntPoint())
        # metrics
        self._metric_update_event = Observable.Event()

    def close(self):
        if self.__drawing_context_storage:
            self.__drawing_context_storage.close()
            self.__drawing_context_storage = None
        self.__repaint_thread.close()
        self.__repaint_thread = None
        self.__canvas_widget.on_size_changed = None
        self.__canvas_widget.on_mouse_clicked = None
        self.__canvas_widget.on_mouse_double_clicked = None
        self.__canvas_widget.on_mouse_entered = None
        self.__canvas_widget.on_mouse_exited = None
        self.__canvas_widget.on_mouse_pressed = None
        self.__canvas_widget.on_mouse_released = None
        self.__canvas_widget.on_mouse_position_changed = None
        self.__canvas_widget.on_wheel_changed = None
        self.__canvas_widget.on_context_menu_event = None
        self.__canvas_widget.on_key_pressed = None
        self.__canvas_widget.on_focus_changed = None
        self.__canvas_widget.on_drag_enter = None
        self.__canvas_widget.on_drag_leave = None
        self.__canvas_widget.on_drag_move = None
        self.__canvas_widget.on_drop = None
        self.__canvas_widget.on_pan_gesture = None
        self.__canvas_widget.on_periodic = None
        self.__canvas_widget = None
        super(RootCanvasItem, self).close()

    @property
    def root_container(self):
        return self

    @property
    def canvas_widget(self):
        return self.__canvas_widget

    def __draw_if_needed(self):
        # Check to see if needs repaint has been set. trigger drawing on a thread if so.
        with self.__needs_repaint_lock:
            now = time.time()
            if self.__last_repaint is None or now - self.__last_repaint > 1 / self.__max_frame_rate:
                needs_repaint = self.__needs_repaint
                self.__needs_repaint = False
                self.__last_repaint = now
            else:
                needs_repaint = False
        if needs_repaint:
            self.__repaint_thread.trigger()

    def __repaint_on_thread(self):
        # Create a new drawing context, render to it, upload to canvas widget.
        if self.canvas_size is not None:
            drawing_context = self.__canvas_widget.create_drawing_context(self.__drawing_context_storage)
            self.__drawing_context_storage.mark()
            drawing_context.save()
            try:
                self._repaint(drawing_context)
            except Exception as e:
                import traceback
                logging.debug("CanvasItem Repaint Error: %s", e)
                traceback.print_exc()
                traceback.print_stack()
            finally:
                drawing_context.restore()
            self.__canvas_widget.draw(drawing_context, self.__drawing_context_storage)
            self.__drawing_context_storage.clean()
        else:  # this may happen if thread gets triggered before layout is called. try again.
            with self.__needs_repaint_lock:
                self.__needs_repaint = True

    @property
    def canvas_widget(self):
        """ Return the canvas widget. """
        return self.__canvas_widget

    @property
    def focusable(self):
        """ Return whether the canvas widget is focusable. """
        return self.canvas_widget.focusable

    @focusable.setter
    def focusable(self, focusable):
        """ Set whether the canvas widget is focusable. """
        self.canvas_widget.focusable = focusable

    # a child has been updated, trigger the thread to repaint
    def _child_updated(self, child):
        self._metric_update_event.fire()
        with self.__needs_repaint_lock:
            self.__needs_repaint = True

    def size_changed(self, width, height):
        """ Called when size changes. """
        # logging.debug("{} {} x {}".format(id(self), width, height))
        if width > 0 and height > 0:
            self.update_layout((0, 0), (height, width))
            self.update()

    @property
    def focused_item(self):
        """
            Return the canvas focused item. May return None.

            The focused item is either this item itself or one of its
            children.
        """
        return self.__focused_item

    @focused_item.setter
    def focused_item(self, focused_item):
        """ Set the canvas focused item. This will also update the focused property of both old item (if any) and new item (if any). """
        if focused_item != self.__focused_item:
            if self.__focused_item:
                self.__focused_item._set_focused(False)
            self.__focused_item = focused_item
            if self.__focused_item:
                self.__focused_item._set_focused(True)
        if self.__focused_item:
            self.__last_focused_item = self.__focused_item

    def __focus_changed(self, focused):
        """ Called when widget focus changes. """
        if focused and not self.focused_item:
            self.focused_item = self.__last_focused_item
        elif not focused and self.focused_item:
            self.focused_item = None

    def _request_root_focus(self, focused_item):
        """
            Requests that the root widget gets focus.

            This focused is different from the focus within the canvas system. This is
            the external focus in the widget system.

            If the canvas widget is already focused, this simply sets the focused item
            to be the requested one. Otherwise, the widget has to request focus. When
            it receives focus, a __focus_changed from the widget which will restore the
            last focused item to be the new focused canvas item.
        """
        if self.__canvas_widget.focused:
            self.focused_item = focused_item
        else:
            self.focused_item = None
            self.__last_focused_item = focused_item
            self.__canvas_widget.focused = True  # this will trigger focus changed to set the focus

    def _cursor_shape_changed(self, item):
        if item == self.__mouse_tracking_canvas_item:
            self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)

    def __mouse_entered(self):
        self.__mouse_tracking = True

    def __mouse_exited(self):
        if self.__mouse_tracking_canvas_item:
            self.__mouse_tracking_canvas_item.mouse_exited()
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item = None
        self.__canvas_widget.set_cursor_shape(None)

    def __mouse_canvas_item_at_point(self, x, y):
        if self.__mouse_canvas_item:
            return self.__mouse_canvas_item
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            if canvas_item.wants_mouse_events:
                return canvas_item
        return None

    def __request_focus(self, canvas_item):
        while canvas_item:
            if canvas_item.focusable:
                canvas_item.request_focus()
                break
            canvas_item = canvas_item.container

    def __mouse_clicked(self, x, y, modifiers):
        canvas_item = self.__mouse_canvas_item_at_point(x, y)
        if canvas_item:
            self.__request_focus(canvas_item)
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
            return canvas_item.mouse_clicked(canvas_item_point.x, canvas_item_point.y, modifiers)

    def __mouse_double_clicked(self, x, y, modifiers):
        canvas_item = self.__mouse_canvas_item_at_point(x, y)
        if canvas_item:
            self.__request_focus(canvas_item)
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
            return canvas_item.mouse_double_clicked(canvas_item_point.x, canvas_item_point.y, modifiers)

    def __mouse_pressed(self, x, y, modifiers):
        self.__mouse_position_changed(x, y, modifiers)
        if not self.__mouse_tracking_canvas_item:
            self.__mouse_tracking_canvas_item = self.__mouse_canvas_item_at_point(x, y)
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_entered()
                self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
        if self.__mouse_tracking_canvas_item:
            self.__mouse_canvas_item = self.__mouse_tracking_canvas_item
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_canvas_item)
            self.__request_focus(self.__mouse_canvas_item)
            return self.__mouse_canvas_item.mouse_pressed(canvas_item_point.x, canvas_item_point.y, modifiers)
        return False

    def __mouse_released(self, x, y, modifiers):
        if self.__mouse_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_canvas_item)
            result = self.__mouse_canvas_item.mouse_released(canvas_item_point.x, canvas_item_point.y, modifiers)
            self.__mouse_canvas_item = None
            self.__mouse_position_changed(x, y, modifiers)
            return result
        return False

    def __mouse_position_changed(self, x, y, modifiers):
        if not self.__mouse_tracking:
            self.mouse_entered()
        if self.__mouse_tracking and not self.__mouse_tracking_canvas_item:
            self.__mouse_tracking_canvas_item = self.__mouse_canvas_item_at_point(x, y)
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_entered()
                self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
        new_mouse_canvas_item = self.__mouse_canvas_item_at_point(x, y)
        if self.__mouse_tracking_canvas_item != new_mouse_canvas_item:
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_exited()
                self.__canvas_widget.set_cursor_shape(None)
            self.__mouse_tracking_canvas_item = new_mouse_canvas_item
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_entered()
                self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
        if self.__mouse_tracking_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_tracking_canvas_item)
            self.__mouse_tracking_canvas_item.mouse_position_changed(canvas_item_point.x, canvas_item_point.y, modifiers)

    def __context_menu_event(self, x, y, gx, gy):
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
            if canvas_item.context_menu_event(canvas_item_point.x, canvas_item_point.y, gx, gy):
                return True
        return False

    def __key_pressed(self, key):
        if self.focused_item:
            return self.focused_item.key_pressed(key)
        return False

    def __drag_enter(self, mime_data):
        self.__drag_tracking = True
        return "accept"

    def __drag_leave(self):
        if self.__drag_tracking_canvas_item:
            self.__drag_tracking_canvas_item.drag_leave()
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item = None
        return "accept"

    def __drag_canvas_item_at_point(self, x, y):
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            if canvas_item.wants_drag_events:
                return canvas_item
        return None

    def __drag_move(self, mime_data, x, y):
        response = "ignore"
        if self.__drag_tracking and not self.__drag_tracking_canvas_item:
            self.__drag_tracking_canvas_item = self.__drag_canvas_item_at_point(x, y)
            if self.__drag_tracking_canvas_item:
                self.__drag_tracking_canvas_item.drag_enter(mime_data)
        new_drag_canvas_item = self.__drag_canvas_item_at_point(x, y)
        if self.__drag_tracking_canvas_item != new_drag_canvas_item:
            if self.__drag_tracking_canvas_item:
                self.__drag_tracking_canvas_item.drag_leave()
            self.__drag_tracking_canvas_item = new_drag_canvas_item
            if self.__drag_tracking_canvas_item:
                self.__drag_tracking_canvas_item.drag_enter(mime_data)
        if self.__drag_tracking_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__drag_tracking_canvas_item)
            response = self.__drag_tracking_canvas_item.drag_move(mime_data, canvas_item_point.x, canvas_item_point.y)
        return response

    def __drop(self, mime_data, x, y):
        response = "ignore"
        if self.__drag_tracking_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__drag_tracking_canvas_item)
            response = self.__drag_tracking_canvas_item.drop(mime_data, canvas_item_point.x, canvas_item_point.y)
        self.__drag_leave()
        return response

    def grab_gesture(self, gesture_type):
        """ Grab gesture """
        self.__canvas_widget.grab_gesture(gesture_type)

    def ungrab_gesture(self, gesture_type):
        """ Ungrab gesture """
        self.__canvas_widget.ungrab_gesture(gesture_type)


class BackgroundCanvasItem(AbstractCanvasItem):

    """ Canvas item to draw background_color. """

    def __init__(self, background_color="#888"):
        super(BackgroundCanvasItem, self).__init__()
        self.background_color = background_color

    def _repaint(self, drawing_context):
        # canvas size
        canvas_width = self.canvas_size[1]
        canvas_height = self.canvas_size[0]
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.rect(0, 0, canvas_width, canvas_height)
        drawing_context.fill_style = self.background_color
        drawing_context.fill()
        drawing_context.restore()


class CellCanvasItem(AbstractCanvasItem):

    """ Canvas item to draw and respond to user events for a cell.

    A cell must implement the following interface:

        event: update_event() - fired when the canvas item needs an update
        method: paint_cell(drawing_context, rect, style) - called to draw the cell

    The style parameter passed to paint_cell is a list with zero or one strings from each of the aspects below:
        disabled (default is enabled)
        checked, indeterminate (default is unchecked)
        hover, active (default is none)
    """

    def __init__(self, cell=None):
        super(CellCanvasItem, self).__init__()
        self.__enabled = True
        self.__check_state = "unchecked"
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.__cell = None
        self.__cell_update_event_listener = None
        self.cell = cell
        self.style = set()

    def close(self):
        self.cell = None
        super(CellCanvasItem, self).close()

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        if self.__enabled != value:
            self.__enabled = value
            self.__update_style()

    @property
    def check_state(self):
        return self.__check_state

    @check_state.setter
    def check_state(self, value):
        assert value in ["checked", "unchecked", "partial"]
        if self.__check_state != value:
            self.__check_state = value
            self.__update_style()

    @property
    def checked(self):
        return self.check_state == "checked"

    @checked.setter
    def checked(self, value):
        self.check_state = "checked" if value else "unchecked"

    @property
    def _mouse_inside(self):
        return self.__mouse_inside

    @_mouse_inside.setter
    def _mouse_inside(self, value):
        self.__mouse_inside = value
        self.__update_style()

    @property
    def _mouse_pressed(self):
        return self.__mouse_pressed

    @_mouse_pressed.setter
    def _mouse_pressed(self, value):
        self.__mouse_pressed = value
        self.__update_style()

    def __update_style(self):
        old_style = copy.copy(self.style)
        # enabled state
        self.style.discard('disabled')
        if not self.enabled:
            self.style.add('disabled')
        # checked state
        self.style.discard('checked')
        if self.check_state == "checked":
            self.style.add('checked')
        # hover state
        self.style.discard('hover')
        self.style.discard('active')
        if self._mouse_inside and self._mouse_pressed:
            self.style.add('active')
        elif self.__mouse_inside:
            self.style.add('hover')
        if self.style != old_style:
            self.update()

    @property
    def cell(self):
        return self.__cell

    @cell.setter
    def cell(self, new_cell):
        if self.__cell:
            self.__cell_update_event_listener.close()
            self.__cell_update_event_listener = None
            self.__cell = None
        if new_cell:
            self.__cell = new_cell
            self.__cell_update_event_listener = self.__cell.update_event.listen(self.update)

    def _repaint(self, drawing_context):
        rect = self.canvas_bounds
        if self.__cell and rect is not None:
            with drawing_context.saver():
                self.__cell.paint_cell(drawing_context, rect, self.style)


class TwistDownCell(object):

    def __init__(self):
        super(TwistDownCell, self).__init__()
        self.update_event = Observable.Event()

    def paint_cell(self, drawing_context, rect, style):

        # disabled (default is enabled)
        # checked, indeterminate (default is unchecked)
        # hover, active (default is none)

        if "checked" in style:
            drawing_context.begin_path()
            drawing_context.move_to(rect.center.x, rect.center.y + 4)
            drawing_context.line_to(rect.center.x + 4.5, rect.center.y - 4)
            drawing_context.line_to(rect.center.x - 4.5, rect.center.y - 4)
            drawing_context.close_path()
        else:
            drawing_context.begin_path()
            drawing_context.move_to(rect.center.x + 4, rect.center.y)
            drawing_context.line_to(rect.center.x - 4, rect.center.y + 4.5)
            drawing_context.line_to(rect.center.x - 4, rect.center.y - 4.5)
            drawing_context.close_path()

        overlay_color = None
        if "disabled" in style:
            overlay_color = "rgba(255, 255, 255, 0.5)"
        else:
            if "active" in style:
                overlay_color = "rgba(128, 128, 128, 0.5)"
            elif "hover" in style:
                overlay_color = "rgba(128, 128, 128, 0.1)"

        drawing_context.fill_style = "#444"
        drawing_context.fill()
        drawing_context.stroke_style = "#444"
        drawing_context.stroke()

        if overlay_color:
            rect_args = rect[0][1], rect[0][0], rect[1][1], rect[1][0]
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = overlay_color
            drawing_context.fill()


class TwistDownCanvasItem(CellCanvasItem):

    def __init__(self):
        super(TwistDownCanvasItem, self).__init__()
        self.cell = TwistDownCell()
        self.wants_mouse_events = True
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super(TwistDownCanvasItem, self).close()

    def mouse_entered(self):
        self._mouse_inside = True

    def mouse_exited(self):
        self._mouse_inside = False

    def mouse_pressed(self, x, y, modifiers):
        self._mouse_pressed = True

    def mouse_released(self, x, y, modifiers):
        self._mouse_pressed = False

    def mouse_clicked(self, x, y, modifiers):
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True


class BitmapCell(object):

    def __init__(self, rgba_bitmap_data=None, background_color=None, border_color=None):
        super(BitmapCell, self).__init__()
        self.__rgba_bitmap_data = rgba_bitmap_data
        self.__background_color = background_color
        self.__border_color = border_color
        self.update_event = Observable.Event()

    def set_rgba_bitmap_data(self, rgba_bitmap_data, trigger_update=True):
        self.__rgba_bitmap_data = rgba_bitmap_data
        if trigger_update:
            self.update_event.fire()

    @property
    def rgba_bitmap_data(self):
        return self.__rgba_bitmap_data

    @rgba_bitmap_data.setter
    def rgba_bitmap_data(self, value):
        self.set_rgba_bitmap_data(value, trigger_update=True)

    @property
    def background_color(self):
        return self.__background_color

    @background_color.setter
    def background_color(self, background_color):
        self.__background_color = background_color
        self.update_event.fire()

    @property
    def border_color(self):
        return self.__border_color

    @border_color.setter
    def border_color(self, border_color):
        self.__border_color = border_color
        self.update_event.fire()

    def paint_cell(self, drawing_context, rect, style):
        # set up the defaults
        background_color = self.__background_color
        border_color = self.__border_color
        overlay_color = None

        # configure based on style
        if "disabled" in style:
            overlay_color = "rgba(255, 255, 255, 0.5)"
            if "checked" in style:
                background_color = "rgb(64, 64, 64)"
        else:
            if "checked" in style:
                background_color = "rgb(192, 192, 192)"
            if "active" in style:
                overlay_color = "rgba(128, 128, 128, 0.5)"
            elif "hover" in style:
                overlay_color = "rgba(128, 128, 128, 0.1)"

        rect_args = rect[0][1], rect[0][0], rect[1][1], rect[1][0]

        # draw the background
        if background_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = background_color
            drawing_context.fill()
        # draw the bitmap
        bitmap_data = self.rgba_bitmap_data
        image_size = bitmap_data.shape
        if image_size[0] > 0 and image_size[1] > 0:
            display_rect = Geometry.fit_to_size(rect, image_size)
            display_height = display_rect[1][1]
            display_width = display_rect[1][0]
            if display_rect and display_width > 0 and display_height > 0:
                display_top = display_rect[0][1]
                display_left = display_rect[0][0]
                drawing_context.draw_image(bitmap_data, display_top, display_left, display_height, display_width)
        # draw the overlay style
        if overlay_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = overlay_color
            drawing_context.fill()
        # draw the border
        if border_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.stroke_style = border_color
            drawing_context.stroke()


class BitmapCanvasItem(CellCanvasItem):

    """ Canvas item to draw rgba bitmap in bgra uint32 ndarray format. """

    def __init__(self, rgba_bitmap_data=None, background_color=None, border_color=None):
        super(BitmapCanvasItem, self).__init__()
        self.cell = BitmapCell(rgba_bitmap_data, background_color, border_color)

    def set_rgba_bitmap_data(self, rgba_bitmap_data, trigger_update=True):
        self.cell.set_rgba_bitmap_data(rgba_bitmap_data, trigger_update)

    @property
    def rgba_bitmap_data(self):
        return self.cell.rgba_bitmap_data

    @rgba_bitmap_data.setter
    def rgba_bitmap_data(self, rgb_bitmap_data):
        self.cell.rgba_bitmap_data = rgb_bitmap_data

    @property
    def background_color(self):
        return self.cell.background_cell

    @background_color.setter
    def background_color(self, background_color):
        self.cell.background_cell = background_color

    @property
    def border_color(self):
        return self.cell.border_cell

    @border_color.setter
    def border_color(self, border_color):
        self.cell.border_cell = border_color


class BitmapButtonCanvasItem(BitmapCanvasItem):

    """ Canvas item button to draw rgba bitmap in bgra uint32 ndarray format. """

    def __init__(self, rgba_bitmap_data, background_color=None, border_color=None):
        super(BitmapButtonCanvasItem, self).__init__(rgba_bitmap_data, background_color, border_color)
        self.wants_mouse_events = True
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super(BitmapButtonCanvasItem, self).close()

    def mouse_entered(self):
        self._mouse_inside = True

    def mouse_exited(self):
        self._mouse_inside = False

    def mouse_pressed(self, x, y, modifiers):
        self._mouse_pressed = True

    def mouse_released(self, x, y, modifiers):
        self._mouse_pressed = False

    def mouse_clicked(self, x, y, modifiers):
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True


class StaticTextCanvasItem(AbstractCanvasItem):

    def __init__(self, text=None):
        super(StaticTextCanvasItem, self).__init__()
        self.__text = text if text is not None else str()
        self.__text_color = "#000"
        self.__text_disabled_color = "#888"
        self.__enabled = True
        self.__font = "12px"

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, value):
        if self.__text != value:
            self.__text = value
            self.update()

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        if self.__enabled != value:
            self.__enabled = value
            self.update()

    @property
    def text_color(self):
        return self.__text_color

    @text_color.setter
    def text_color(self, value):
        if self.__text_color != value:
            self.__text_color = value
            self.update()

    @property
    def text_disabled_color(self):
        return self.__text_disabled_color

    @text_disabled_color.setter
    def text_disabled_color(self, value):
        if self.__text_disabled_color != value:
            self.__text_disabled_color = value
            self.update()

    @property
    def font(self):
        return self.__font

    @font.setter
    def font(self, value):
        if self.__font != value:
            self.__font = value
            self.update()

    def size_to_content(self, get_font_metrics_fn, horizontal_padding=None, vertical_padding=None):
        """ Size the canvas item to the text content. """

        if horizontal_padding is None:
            horizontal_padding = 4

        if vertical_padding is None:
            vertical_padding = 4

        font_metrics = get_font_metrics_fn(self.__font, self.__text)

        self.sizing.minimum_width = font_metrics.width + 2 * horizontal_padding
        self.sizing.maximum_width = self.sizing.minimum_width

        self.sizing.minimum_height = font_metrics.height + 2 * vertical_padding
        self.sizing.maximum_height = self.sizing.minimum_height

    def _repaint(self, drawing_context):
        canvas_bounds_center = self.canvas_bounds.center
        drawing_context.save()
        drawing_context.font = self.__font
        drawing_context.text_align = 'center'
        drawing_context.text_baseline = 'middle'
        drawing_context.fill_style = self.__text_color if self.__enabled else self.__text_disabled_color
        drawing_context.fill_text(self.__text, canvas_bounds_center.x, canvas_bounds_center.y + 1)
        drawing_context.restore()


class TextButtonCanvasItem(StaticTextCanvasItem):

    def __init__(self, text=None):
        super(TextButtonCanvasItem, self).__init__(text)
        self.wants_mouse_events = True
        self.__border_enabled = True
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super(TextButtonCanvasItem, self).close()

    @property
    def border_enabled(self):
        return self.__border_enabled

    @border_enabled.setter
    def border_enabled(self, value):
        if self.__border_enabled != value:
            self.__border_enabled = value
            self.update()

    def mouse_entered(self):
        self.__mouse_inside = True
        self.update()

    def mouse_exited(self):
        self.__mouse_inside = False
        self.update()

    def mouse_pressed(self, x, y, modifiers):
        self.__mouse_pressed = True
        self.update()

    def mouse_released(self, x, y, modifiers):
        self.__mouse_pressed = False
        self.update()

    def mouse_clicked(self, x, y, modifiers):
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True

    def _repaint(self, drawing_context):
        canvas_size = self.canvas_size
        drawing_context.save()
        drawing_context.begin_path()

        # drawing_context.rect(0, 0, canvas_size.width, canvas_size.height)
        drawing_context.round_rect(1.0, 1.0, canvas_size.width - 2.0, canvas_size.height - 2.0, 4)

        if self.enabled and self.__mouse_inside and self.__mouse_pressed:
            drawing_context.fill_style = "rgba(128, 128, 128, 0.5)"
            drawing_context.fill()
        elif self.enabled and self.__mouse_inside:
            drawing_context.fill_style = "rgba(128, 128, 128, 0.1)"
            drawing_context.fill()
        if self.border_enabled:
            drawing_context.stroke_style = "#000"
            drawing_context.line_width = 1.0
            drawing_context.stroke()
        drawing_context.restore()
        super(TextButtonCanvasItem, self)._repaint(drawing_context)


class CheckBoxCanvasItem(AbstractCanvasItem):

    def __init__(self):
        super(CheckBoxCanvasItem, self).__init__()
        self.wants_mouse_events = True
        self.__enabled = True
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.__check_state = "unchecked"
        self.on_check_state_changed = None
        self.sizing.set_fixed_width(20)
        self.sizing.set_fixed_height(20)

    def close(self):
        self.on_check_state_changed = None
        super(CheckBoxCanvasItem, self).close()

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        self.__enabled = value
        self.update()

    @property
    def check_state(self):
        return self.__check_state

    @check_state.setter
    def check_state(self, value):
        self.__check_state = value
        self.update()

    def mouse_entered(self):
        self.__mouse_inside = True
        self.update()

    def mouse_exited(self):
        self.__mouse_inside = False
        self.update()

    def mouse_pressed(self, x, y, modifiers):
        self.__mouse_pressed = True
        self.update()

    def mouse_released(self, x, y, modifiers):
        self.__mouse_pressed = False
        self.update()

    def mouse_clicked(self, x, y, modifiers):
        if self.enabled:
            if self.check_state == "unchecked":
                self.check_state = "checked"
            else:
                self.check_state = "unchecked"
            if self.on_check_state_changed:
                self.on_check_state_changed(self.check_state)
        return True

    def _repaint(self, drawing_context):
        canvas_size = self.canvas_size

        drawing_context.save()
        drawing_context.begin_path()
        cx = canvas_size.width * 0.5
        cy = canvas_size.height * 0.5
        size = 14.0
        size_half = size * 0.5
        drawing_context.round_rect(cx - size_half, cy - size_half, size, size, 4.0)

        if self.check_state == "checked":
            drawing_context.fill_style = "#FFF"
            drawing_context.fill()
        if self.enabled and self.__mouse_inside and self.__mouse_pressed:
            drawing_context.fill_style = "rgba(128, 128, 128, 0.5)"
            drawing_context.fill()
        elif self.enabled and self.__mouse_inside:
            drawing_context.fill_style = "rgba(128, 128, 128, 0.1)"
            drawing_context.fill()
        drawing_context.stroke_style = "#000"
        drawing_context.line_width = 1.0
        drawing_context.stroke()
        drawing_context.restore()
        if self.check_state == "checked":
            drawing_context.save()
            drawing_context.begin_path()
            drawing_context.move_to(cx - 3, cy - 2)
            drawing_context.line_to(cx + 0, cy + 2)
            drawing_context.line_to(cx + 8, cy - 9)
            drawing_context.stroke_style = "#000"
            drawing_context.line_width = 2.0
            drawing_context.stroke()
            drawing_context.restore()

        super(CheckBoxCanvasItem, self)._repaint(drawing_context)


class EmptyCanvasItem(AbstractCanvasItem):

    """ Canvas item to act as a placeholder (spacer or stretch). """

    def __init__(self):
        super(EmptyCanvasItem, self).__init__()


class RadioButtonGroup(object):

    def __init__(self, buttons):
        self.__buttons = copy.copy(buttons)
        self.__current_index = 0
        self.on_current_index_changed = None

        for index, button in enumerate(self.__buttons):
            button.checked = index == self.__current_index

        for index, button in enumerate(self.__buttons):
            def current_index_changed(index):
                self.__current_index = index
                for index, button in enumerate(self.__buttons):
                    button.checked = index == self.__current_index
                if self.on_current_index_changed:
                    self.on_current_index_changed(self.__current_index)
            button.on_button_clicked = functools.partial(current_index_changed, index)

    def close(self):
        for button in self.__buttons:
            button.on_button_clicked = None
        self.on_current_index_changed = None
