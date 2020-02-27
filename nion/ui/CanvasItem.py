"""
    CanvasItem module contains classes related to canvas items.
"""

# standard libraries
import collections
import contextlib
import copy
import enum
import functools
import imageio
import logging
import operator
import sys
import threading
import typing
import warnings
import weakref

# third party libraries
import numpy

# local libraries
from nion.ui import DrawingContext
from nion.utils import Event
from nion.utils import Geometry

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


DEFAULT_MAX_FRAME_RATE = 25

MAX_VALUE = sys.maxsize

class Orientation(enum.Enum):
    Vertical = 0
    Horizontal = 1

MenuItemState = collections.namedtuple("MenuItemState", ["title", "enabled", "checked"])


class Constraint:

    """ A constraint on an item in a layout. Preferred is only used when free sizing. """

    def __init__(self):
        self.minimum = None
        self.maximum = None
        self.preferred = None

    def __repr__(self):
        return "Constraint (min={0}, max={1}, pref={2})".format(self.minimum, self.maximum, self.preferred)


class SolverItem:
    def __init__(self, constraint):
        self.constraint = constraint
        self.size = None
        self.is_constrained = False


def constraint_solve(canvas_origin, canvas_size, canvas_item_constraints, spacing=0):
    """
        Solve the layout by assigning space and enforcing constraints.

        Returns origins, sizes tuple.
    """

    # setup information from each item
    solver_items = [SolverItem(constraint) for constraint in canvas_item_constraints]

    # assign preferred size, if any, to each item. items with preferred size are still
    # free to change as long as they don't become constrained.
    for solver_item in solver_items:
        if solver_item.constraint.preferred is not None:
            solver_item.size = solver_item.constraint.preferred
            if solver_item.size < solver_item.constraint.minimum:
                solver_item.size = solver_item.constraint.minimum
                if solver_item.size > solver_item.constraint.maximum:
                    solver_item.size = solver_item.constraint.maximum
                    solver_item.is_constrained = True
            if solver_item.size > solver_item.constraint.maximum:
                solver_item.size = solver_item.constraint.maximum
                if solver_item.size < solver_item.constraint.minimum:
                    solver_item.size = solver_item.constraint.minimum
                    solver_item.is_constrained = True

    # put these here to avoid linter warnings
    remaining_canvas_size = canvas_size
    remaining_count = len(solver_items)

    # assign the free space to the remaining items. first figure out how much space is left
    # and how many items remain. then divide the space up.
    finished = False
    while not finished:
        finished = True
        remaining_canvas_size = canvas_size
        remaining_count = len(solver_items)
        # reset the items that we can, i.e. those that aren't already constrained and don't have a preferred size
        for solver_item in solver_items:
            if not solver_item.is_constrained and solver_item.constraint.preferred is None:
                solver_item.size = None
        # figure out how many free range items there are, i.e. those that don't already have a size assigned
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
        if actual_canvas_size > canvas_size:
            remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
            remaining_canvas_size = actual_canvas_size - canvas_size
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
        if actual_canvas_size < canvas_size:
            remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
            remaining_canvas_size = canvas_size - actual_canvas_size
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

    # assign layouts
    # TODO: allow for various justification options (start - default, end, center, space-between, space-around)
    # see https://css-tricks.com/snippets/css/a-guide-to-flexbox/
    sizes = [solver_item.size for solver_item in solver_items]
    origins = list()
    for index in range(len(canvas_item_constraints)):
        origins.append(canvas_origin)
        canvas_origin += sizes[index] + spacing

    return origins, sizes


class Sizing:

    """
        Describes the sizing for a particular canvas item.

        Aspect ratio, width, and height can each specify minimums, maximums, and preferred values.

        Width and height can be integer or floats. If floats, they specify a percentage of their
        respective maximum.

        Preferred values are only used when free sizing.

        Collapsible items collapse to fixed size of 0 if they don't have children.
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

    def __repr__(self):
        format_str = "Sizing (min_w={0}, max_w={1}, pref_w={2}, min_h={3}, max_h={4}, pref_h={5}, min_a={6}, max_a={7}, pref_a={8}, collapsible={9})"
        return format_str.format(self.minimum_width, self.maximum_width, self.preferred_width,
                                 self.minimum_height, self.maximum_height, self.preferred_height,
                                 self.minimum_aspect_ratio, self.maximum_aspect_ratio, self.preferred_aspect_ratio,
                                 self.collapsible)

    def __eq__(self, other):
        if self.preferred_width != other.preferred_width:
            return False
        if self.preferred_height != other.preferred_height:
            return False
        if self.preferred_aspect_ratio != other.preferred_aspect_ratio:
            return False
        if self.minimum_width != other.minimum_width:
            return False
        if self.minimum_height != other.minimum_height:
            return False
        if self.minimum_aspect_ratio != other.minimum_aspect_ratio:
            return False
        if self.maximum_width != other.maximum_width:
            return False
        if self.maximum_height != other.maximum_height:
            return False
        if self.maximum_aspect_ratio != other.maximum_aspect_ratio:
            return False
        if self.collapsible != other.collapsible:
            return False
        return True

    def __deepcopy__(self, memo):
        deepcopy = Sizing()
        deepcopy.copy_from(self)
        memo[id(self)] = deepcopy
        return deepcopy

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

    def clear_height_constraint(self):
        self.preferred_height = None
        self.minimum_height = None
        self.maximum_height = None

    def clear_width_constraint(self):
        self.preferred_width = None
        self.minimum_width = None
        self.maximum_width = None

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

    def get_unrestrained_width(self, maximum_width):
        if self.maximum_width is not None:
            if isinstance(self.maximum_width, float) and self.maximum_width < 1.0:
                return self.maximum_width * maximum_width
            return min(self.maximum_width, maximum_width)
        return maximum_width

    def get_unrestrained_height(self, maximum_height):
        if self.maximum_height is not None:
            if isinstance(self.maximum_height, float) and self.maximum_height < 1.0:
                return self.maximum_height * maximum_height
            return min(self.maximum_height, maximum_height)
        return maximum_height


class KeyboardModifiers:
    def __init__(self, shift=False, control=False, alt=False, meta=False, keypad=False):
        self.__shift = shift
        self.__control = control
        self.__alt = alt
        self.__meta = meta
        self.__keypad = keypad

    # shift
    @property
    def shift(self):
        return self.__shift

    @property
    def only_shift(self):
        return self.__shift and not self.__control and not self.__alt and not self.__meta

    # control (command key on mac)
    @property
    def control(self):
        return self.__control

    @property
    def only_control(self):
        return self.__control and not self.__shift and not self.__alt and not self.__meta

    # alt (option key on mac)
    @property
    def alt(self):
        return self.__alt

    @property
    def only_alt(self):
        return self.__alt and not self.__control and not self.__shift and not self.__meta

    # option (alt key on windows)
    @property
    def option(self):
        return self.__alt

    @property
    def only_option(self):
        return self.__alt and not self.__control and not self.__shift and not self.__meta

    # meta (control key on mac)
    @property
    def meta(self):
        return self.__meta

    @property
    def only_meta(self):
        return self.__meta and not self.__control and not self.__shift and not self.__alt

    # keypad
    @property
    def keypad(self):
        return self.__keypad

    @property
    def only_keypad(self):
        return self.__keypad


def visible_canvas_item(canvas_item: "AbstractCanvasItem") -> "AbstractCanvasItem":
    return canvas_item if canvas_item and canvas_item.visible else None


class AbstractCanvasItem:
    """An item drawn on a canvas supporting mouse and keyboard actions.

    CONTAINERS

    A canvas item should be added to a container. It is an error to add a particular canvas item to more than one
    container. The container in which the canvas item resides is accessible via the ``container`` property.

    LAYOUT

    The container is responsible for layout and will set the canvas bounds of this canvas item as a function of the
    container layout algorithm and this canvas item's sizing information.

    The ``sizing`` property is the intrinsic sizing constraints of this canvas item.

    The ``layout_sizing`` property is a the sizing information used by the container layout algorithm.

    If this canvas item is non-composite, then ``layout_sizing`` will be identical to this canvas item's ``sizing``.

    However, if this canvas item is composite, then ``layout_sizing`` is determined by the layout algorithm and then
    additionally constrained by this canvas item's ``sizing``. In this way, by leaving ``sizing`` unconstrained, the
    layout can determine the sizing of this canvas item. Alternatively, by adding a constraint to ``sizing``, the layout
    can be constrained. This corresponds to the contents determining the size of the container vs. the container
    determining the size of the layout.

    Unpredictable layout may occur if an unconstrained item is placed into an unrestrained container. Be sure to
    either restrain (implicitly or explicitly) the content or the container.

    Layout occurs when the structure of the item hierarchy changes, such as when a new canvas item is added to a
    container. Clients can also call ``refresh_layout`` explicitly as needed.

    UPDATES AND DRAWING

    Update is the mechanism by which the container is notified that one of its child canvas items needs updating.
    The update message will ultimately end up at the root container at which point the root container will trigger a
    repaint on a thread.

    Subclasses should override _repaint or _repaint_visible to implement drawing. Drawing should take place within the
    canvas bounds.
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
        self.__tool_tip = None
        self.__background_color = None
        self.__border_color = None
        self.__visible = True
        self._has_layout = False
        self.__thread = threading.current_thread()
        self.__update_level_lock = threading.RLock()
        self.__update_level = 0
        self.__pending_update = True
        self.__repaint_drawing_context = None
        # stats for testing
        self._update_count = 0
        self._repaint_count = 0

    def close(self):
        """ Close the canvas object. """
        if threading.current_thread() != self.__thread:
            warnings.warn('CanvasItem closed on different thread')
            import traceback
            traceback.print_stack()
        self.__container = None
        self.on_focus_changed = None
        self.on_layout_updated = None

    @property
    def canvas_size(self):
        """ Returns size of canvas_rect (external coordinates). """
        return self.__canvas_size

    def _set_canvas_size(self, canvas_size):
        canvas_size = Geometry.IntSize.make(canvas_size) if canvas_size is not None else None
        if ((self.__canvas_size is None) != (canvas_size is None)) or (self.__canvas_size != canvas_size):
            self.__canvas_size = canvas_size
            self.update()

    @property
    def canvas_origin(self):
        """ Returns origin of canvas_rect (external coordinates). """
        return self.__canvas_origin

    def _set_canvas_origin(self, canvas_origin):
        canvas_origin = Geometry.IntPoint.make(canvas_origin) if canvas_origin is not None else None
        if ((self.__canvas_origin is None) != (canvas_origin is None)) or (self.__canvas_origin != canvas_origin):
            self.__canvas_origin = canvas_origin
            self.update()

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
        assert self.__container is None or container is None
        self.__container = container

    @property
    def layer_container(self) -> "LayerCanvasItem":
        """ Return the root container, if any. """
        return self.__container.layer_container if self.__container else None

    @property
    def root_container(self):
        """ Return the root container, if any. """
        return self.__container.root_container if self.__container else None

    @property
    def background_color(self):
        return self.__background_color

    @background_color.setter
    def background_color(self, background_color):
        self.__background_color = background_color
        self.update()

    @property
    def border_color(self):
        return self.__border_color

    @border_color.setter
    def border_color(self, border_color):
        self.__border_color = border_color
        self.update()

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
            self.update()
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

    def drag(self, mime_data: "UserInterface.MimeData", thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None) -> None:
        root_container = self.root_container
        if root_container:
            self.root_container.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        root_container = self.root_container
        if root_container:
            root_container.show_tool_tip_text(text, gx, gy)

    @property
    def tool_tip(self):
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, value):
        self.__tool_tip = value

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
        o1 = self.map_to_root_container(Geometry.IntPoint())
        o2 = canvas_item.map_to_root_container(Geometry.IntPoint())
        return p + o1 - o2

    def map_to_root_container(self, p):
        """ Map the point to the coordinates of the root container. """
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

    def map_to_global(self, p):
        return self.root_container.map_to_global(self.map_to_root_container(p))

    def _inserted(self, container):
        """Subclasses may override to know when inserted into a container."""
        pass

    def _removed(self, container):
        """Subclasses may override to know when removed from a container."""
        pass

    def prepare_render(self):
        """Subclasses may override to prepare for layout and repaint."""
        pass

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Update the layout with a new canvas_origin and canvas_size.

        canvas_origin and canvas_size are the external bounds.

        This method will be called on the render thread.

        Subclasses can override this method to take action when the size of the canvas item changes, but they should
        typically call super to do the actual layout.

        The on_layout_updated callable will be called with the new canvas_origin and canvas_size.

        The canvas_origin and canvas_size properties are valid after calling this method and _has_layout is True.
        """
        self._update_self_layout(canvas_origin, canvas_size, immediate=immediate)
        self._has_layout = self.canvas_origin is not None and self.canvas_size is not None

    def _update_self_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Update the canvas origin and size and call notification methods."""
        self._set_canvas_origin(canvas_origin)
        self._set_canvas_size(canvas_size)
        if self.on_layout_updated:
            self.on_layout_updated(self.canvas_origin, self.canvas_size, immediate=immediate)
        self._has_layout = self.canvas_origin is not None and self.canvas_size is not None

    def refresh_layout_immediate(self):
        """Immediate re-layout the item."""
        self.refresh_layout()
        self.update_layout(self.canvas_origin, self.canvas_size, immediate=True)

    def refresh_layout(self):
        """Invalidate the layout and trigger layout.

        Items get layout from their container, so the default implementation asks the container to layout.
        """
        if self.__container:
            self.__container._needs_layout(self)

    def _needs_layout(self, canvas_item):
        # pass the needs layout up the chain.
        if self.__container:
            self.__container._needs_layout(canvas_item)

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self.__visible = value
        if self.__container:
            self.__container.refresh_layout()

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

    def copy_sizing(self):
        new_sizing = Sizing()
        new_sizing.copy_from(self.sizing)
        return new_sizing

    def update_sizing(self, new_sizing):
        if new_sizing != self.sizing:
            self.sizing.copy_from(new_sizing)
            self.refresh_layout()

    def update(self):
        """
            Mark this canvas item as needing a display update.

            The canvas item will be repainted by the root canvas item.
        """
        self._begin_update()
        self._end_update()

    def _begin_update(self):
        with self.__update_level_lock:
            self.__update_level += 1

    def _end_update(self):
        with self.__update_level_lock:
            self.__update_level -= 1
            update_level = self.__update_level
        if update_level == 0:
            self._update_count += 1
            self._updated()
            self._handle_end_update()

    def _handle_end_update(self):
        container = self.__container
        if container and self._has_layout:
            container.update()

    def _update_container(self):
        with self.__update_level_lock:
            update_level = self.__update_level
        if update_level == 0:
            container = self.__container
            if container and self._has_layout:
                container.update()

    def _updated(self):
        """
            Notify this canvas item that a child has been updated, repaint if needed at next opportunity.

            Default implementation calls child_updated on the container, if not None.

            Subclasses can override to handle specially.
        """
        self.__pending_update = True

    @contextlib.contextmanager
    def update_context(self):
        self._begin_update()
        yield
        self._end_update()

    def _repaint(self, drawing_context):
        """Repaint the canvas item to the drawing context.

        Subclasses should override this method to paint.

        This method will be called on a thread.

        The drawing should take place within the canvas_bounds.
        """
        assert self.canvas_size is not None
        self._repaint_count += 1

    def _repaint_template(self, drawing_context: DrawingContext.DrawingContext, immediate: bool) -> None:
        """A wrapper method for _repaint.

        Callers should always call this method instead of _repaint directly. This helps keep the _repaint
        implementations simple and easy to understand.
        """
        self._repaint(drawing_context)

    @property
    def _pending_update(self):
        return self.__pending_update

    def _repaint_if_needed(self, drawing_context, *, immediate=False) -> None:
        """Repaint if no cached version of the last paint is available.

        If no cached drawing context is available, regular _repaint is used to make a new one which is then cached.

        The cached drawing context is typically cleared during the update method.

        Subclasses will typically not need to override this method, except in special cases.
        """
        pending_update, self.__pending_update = self.__pending_update, False
        if pending_update:
            repaint_drawing_context = DrawingContext.DrawingContext()
            self._repaint_template(repaint_drawing_context, immediate)
            self.__repaint_drawing_context = repaint_drawing_context
        drawing_context.add(self.__repaint_drawing_context)

    def repaint_immediate(self, drawing_context: DrawingContext.DrawingContext, canvas_size: Geometry.IntSize) -> None:
        self.update_layout(Geometry.IntPoint(), canvas_size)
        self._repaint_template(drawing_context, immediate=True)

    def _draw_background(self, drawing_context):
        """Draw the background. Subclasses can call this."""
        background_color = self.__background_color
        if background_color:
            rect = self.canvas_bounds
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.rect(rect[0][1], rect[0][0], rect[1][1], rect[1][0])
                drawing_context.fill_style = background_color
                drawing_context.fill()

    def _draw_border(self, drawing_context):
        """Draw the border. Subclasses can call this."""
        border_color = self.__border_color
        if border_color:
            rect = self.canvas_bounds
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.rect(rect[0][1], rect[0][0], rect[1][1], rect[1][0])
                drawing_context.stroke_style = border_color
                drawing_context.stroke()

    def _repaint_visible(self, drawing_context, visible_rect):
        """
            Repaint the canvas item to the drawing context within the visible area.

            Subclasses can override this method to paint.

            This method will be called on a thread.

            The drawing should take place within the canvas_bounds.

            The default implementation calls _repaint(drawing_context)
        """
        self._repaint_if_needed(drawing_context)

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

    def wheel_changed(self, x, y, dx, dy, is_horizontal):
        """ Handle a mouse wheel changed within this canvas item. Return True if handled. """
        return False

    def context_menu_event(self, x, y, gx, gy):
        """ Handle a context menu event. x, y are local coordinates. gx, gy are global coordinates. """
        return False

    def key_pressed(self, key):
        """ Handle a key pressed while this canvas item has focus. Return True if handled. """
        return False

    def key_released(self, key):
        """ Handle a key released while this canvas item has focus. Return True if handled. """
        return False

    def wants_drag_event(self, mime_data: "UserInterface.MimeData", x: int, y: int) -> bool:
        """ Determines if the item should handle certain mime_data at a certain point. Return True if handled."""
        return self.wants_drag_events

    def drag_enter(self, mime_data: "UserInterface.MimeData") -> str:
        """ Handle a drag event entering this canvas item. Return action if handled. """
        return "ignore"

    def drag_leave(self):
        """ Handle a drag event leaving this canvas item. Return action if handled. """
        return "ignore"

    def drag_move(self, mime_data: "UserInterface.MimeData", x: int, y: int) -> str:
        """ Handle a drag event moving within this canvas item. Return action if handled. """
        return "ignore"

    def drop(self, mime_data: "UserInterface.MimeData", x: int, y: int) -> str:
        """ Handle a drop event in this canvas item. Return action if handled. """
        return "ignore"

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        return False

    def pan_gesture(self, dx, dy):
        """ Handle a pan gesture in this canvas item. Return action if handled. """
        return False

    def _dispatch_any(self, method: str, *args, **kwargs) -> bool:
        if hasattr(self, method):
            return getattr(self, method)(*args, **kwargs)
        return False

    def _get_menu_item_state(self, command_id: str):
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = getattr(self, menu_item_state_method)()
            if menu_item_state:
                return menu_item_state
        if hasattr(self, handle_method):
            return MenuItemState(title=None, enabled=True, checked=False)
        return None

    def simulate_click(self, p, modifiers=None):
        modifiers = KeyboardModifiers() if not modifiers else modifiers
        self.mouse_pressed(p[1], p[0], modifiers)
        self.mouse_released(p[1], p[0], modifiers)

    def simulate_drag(self, p1, p2, modifiers=None):
        modifiers = KeyboardModifiers() if not modifiers else modifiers
        self.mouse_pressed(p1[1], p1[0], modifiers)
        self.mouse_position_changed(p1[1], p1[0], modifiers)
        midpoint = Geometry.midpoint(p1, p2)
        self.mouse_position_changed(midpoint[1], midpoint[0], modifiers)
        self.mouse_position_changed(p2[1], p2[0], modifiers)
        self.mouse_released(p2[1], p2[0], modifiers)

    def simulate_press(self, p, modifiers=None):
        modifiers = KeyboardModifiers() if not modifiers else modifiers
        self.mouse_pressed(p[1], p[0], modifiers)

    def simulate_move(self, p, modifiers=None):
        modifiers = KeyboardModifiers() if not modifiers else modifiers
        self.mouse_position_changed(p[1], p[0], modifiers)

    def simulate_release(self, p, modifiers=None):
        modifiers = KeyboardModifiers() if not modifiers else modifiers
        self.mouse_released(p[1], p[0], modifiers)


class CanvasItemAbstractLayout:

    """
        Layout canvas items within a larger space.

        Subclasses must implement layout method.

        NOTE: origin=0 is at the top
    """

    def __init__(self, margins=None, spacing=None):
        self.margins = margins if margins is not None else Geometry.Margins(0, 0, 0, 0)
        self.spacing = spacing if spacing else 0

    def calculate_row_layout(self, canvas_origin, canvas_size, canvas_items):
        """ Use constraint_solve to return the positions of canvas items as if they are in a row. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_width_constraint(content_width) for canvas_item in canvas_items]
        return constraint_solve(content_left, content_width, constraints, self.spacing)

    def calculate_column_layout(self, canvas_origin, canvas_size, canvas_items):
        """ Use constraint_solve to return the positions of canvas items as if they are in a column. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_height_constraint(content_height) for canvas_item in canvas_items]
        return constraint_solve(content_top, content_height, constraints, self.spacing)

    def update_canvas_item_layout(self, canvas_item_origin, canvas_item_size, canvas_item, *, immediate=False):
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
        canvas_item.update_layout(canvas_item_origin, canvas_item_size, immediate=immediate)

    def layout_canvas_items(self, x_positions, y_positions, widths, heights, canvas_items, *, immediate=False):
        """ Set the container boxes for the canvas items using update_canvas_item_layout on the individual items. """
        for index, canvas_item in enumerate(canvas_items):
            if canvas_item is not None:
                canvas_item_origin = Geometry.IntPoint(x=x_positions[index], y=y_positions[index])
                canvas_item_size = Geometry.IntSize(width=widths[index], height=heights[index])
                self.update_canvas_item_layout(canvas_item_origin, canvas_item_size, canvas_item, immediate=immediate)

    def _combine_sizing_property(self, sizing, canvas_item_sizing, property, combiner, clear_if_missing=False):
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
        sizing.maximum_width = 0
        sizing.maximum_height = 0
        sizing.preferred_width = 0
        sizing.preferred_height = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_width", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_height", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_width", max)  # if any minimum_width is present, take the maximum one
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_height", max)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_width", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_height", max, True)
        if sizing.maximum_width == 0 or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.maximum_height == 0 or len(canvas_items) == 0:
            sizing.maximum_height = None
        if sizing.preferred_width == 0 or len(canvas_items) == 0:
            sizing.preferred_width = None
        if sizing.preferred_height == 0 or len(canvas_items) == 0:
            sizing.preferred_height = None
        return sizing

    def _get_column_sizing(self, canvas_items):
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is a column.
            Does not include spacing or margins.
        """
        sizing = Sizing()
        sizing.maximum_width = 0
        sizing.maximum_height = 0
        sizing.preferred_width = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_width", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_height", operator.add)
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_width", max)
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_height", operator.add)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_width", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_height", operator.add, True)
        if sizing.maximum_width == 0 or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.preferred_width == 0 or len(canvas_items) == 0:
            sizing.preferred_width = None
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
        sizing.maximum_height = 0
        sizing.preferred_height = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_width", operator.add)
                self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_height", max, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_width", operator.add)
                self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_height", max)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_width", operator.add, True)
                self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_height", max, True)
        if sizing.maximum_width == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.maximum_height == 0 or len(canvas_items) == 0:
            sizing.maximum_height = None
        if sizing.preferred_height == 0 or len(canvas_items) == 0:
            sizing.preferred_height = None
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

    def layout(self, canvas_origin, canvas_size, canvas_items, *, immediate=False):
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
        super().__init__(margins, spacing)

    def layout(self, canvas_origin, canvas_size, canvas_items, *, immediate=False):
        for canvas_item in canvas_items:
            self.update_canvas_item_layout(canvas_origin, canvas_size, canvas_item, immediate=immediate)

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

    def __init__(self, margins=None, spacing=None, alignment=None):
        super().__init__(margins, spacing)
        self.alignment = alignment

    def layout(self, canvas_origin, canvas_size, canvas_items, *, immediate=False):
        # calculate the vertical placement
        y_positions, heights = self.calculate_column_layout(canvas_origin, canvas_size, canvas_items)
        widths = [canvas_item.layout_sizing.get_unrestrained_width(canvas_size.width - self.margins.left - self.margins.right) for canvas_item in canvas_items]
        available_width = canvas_size.width - self.margins.left - self.margins.right
        if self.alignment == "start":
            x_positions = [canvas_origin.x + self.margins.left for width in widths]
        elif self.alignment == "end":
            x_positions = [canvas_origin.x + self.margins.left + (available_width - width) for width in widths]
        else:
            x_positions = [canvas_origin.x + self.margins.left + (available_width - width) * 0.5 for width in widths]
        self.layout_canvas_items(x_positions, y_positions, widths, heights, canvas_items, immediate=immediate)

    def get_sizing(self, canvas_items):
        sizing = self._get_column_sizing(canvas_items)
        self._adjust_sizing(sizing, 0, self.spacing * (len(canvas_items) - 1))
        return sizing

    def create_spacing_item(self, spacing):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.set_fixed_height(spacing)
        spacing_item.sizing.set_fixed_width(0)
        return spacing_item

    def create_stretch_item(self):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.set_fixed_width(0)
        return spacing_item


class CanvasItemRowLayout(CanvasItemAbstractLayout):

    """
        Layout items in a row.

        Pass margins and spacing.
    """

    def __init__(self, margins=None, spacing=None, alignment=None):
        super().__init__(margins, spacing)
        self.alignment = alignment

    def layout(self, canvas_origin, canvas_size, canvas_items, *, immediate=False):
        # calculate the vertical placement
        x_positions, widths = self.calculate_row_layout(canvas_origin, canvas_size, canvas_items)
        heights = [canvas_item.layout_sizing.get_unrestrained_height(canvas_size.height - self.margins.top - self.margins.bottom) for canvas_item in canvas_items]
        available_height = canvas_size.height - self.margins.top - self.margins.bottom
        if self.alignment == "start":
            y_positions = [canvas_origin.y + self.margins.top for width in widths]
        elif self.alignment == "end":
            y_positions = [canvas_origin.y + self.margins.top + (available_height - height) for height in heights]
        else:
            y_positions = [canvas_origin.y + self.margins.top + (available_height - height) * 0.5 for height in heights]
        self.layout_canvas_items(x_positions, y_positions, widths, heights, canvas_items, immediate=immediate)

    def get_sizing(self, canvas_items):
        sizing = self._get_row_sizing(canvas_items)
        self._adjust_sizing(sizing, self.spacing * (len(canvas_items) - 1), 0)
        return sizing

    def create_spacing_item(self, spacing):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.set_fixed_width(spacing)
        spacing_item.sizing.set_fixed_height(0)
        return spacing_item

    def create_stretch_item(self):
        spacing_item = EmptyCanvasItem()
        spacing_item.sizing.set_fixed_height(0)
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
        super().__init__(margins, spacing)
        assert size.width > 0 and size.height > 0
        self.__size = size
        self.__columns = [[None for _ in range(self.__size.height)] for _ in range(self.__size.width)]  # type: typing.List[typing.List[AbstractCanvasItem]]

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

    def layout(self, canvas_origin, canvas_size, canvas_items, *, immediate=False):
        # calculate the horizontal placement
        # calculate the sizing (x, width) for each column
        canvas_item_count = self.__size.width
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = list()
        for x in range(self.__size.width):
            sizing = self._get_overlap_sizing([visible_canvas_item(self.__columns[x][y]) for y in range(self.__size.height)])
            constraints.append(sizing.get_width_constraint(content_width))
        # run the layout engine
        x_positions, widths = constraint_solve(content_left, content_width, constraints, self.spacing)
        # calculate the vertical placement
        # calculate the sizing (y, height) for each row
        canvas_item_count = self.__size.height
        spacing_count = canvas_item_count - 1
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = list()
        for y in range(self.__size.height):
            sizing = self._get_overlap_sizing([visible_canvas_item(self.__columns[x][y]) for x in range(self.__size.width)])
            constraints.append(sizing.get_height_constraint(content_height))
        # run the layout engine
        y_positions, heights = constraint_solve(content_top, content_height, constraints, self.spacing)
        # do the layout
        combined_xs = list()
        combined_ys = list()
        combined_widths = list()
        combined_heights = list()
        combined_canvas_items = list()
        for x in range(self.__size.width):
            for y in range(self.__size.height):
                canvas_item = visible_canvas_item(self.__columns[x][y])
                if canvas_item is not None:
                    combined_xs.append(x_positions[x])
                    combined_ys.append(y_positions[y])
                    combined_widths.append(widths[x])
                    combined_heights.append(heights[y])
                    combined_canvas_items.append(canvas_item)
        self.layout_canvas_items(combined_xs, combined_ys, combined_widths, combined_heights, combined_canvas_items, immediate=immediate)

    def get_sizing(self, canvas_items):
        """
            Calculate the sizing for the grid. Treat columns and rows independently.

            Override from abstract layout.
        """
        sizing = Sizing()
        sizing.maximum_width = 0
        sizing.maximum_height = 0
        sizing.preferred_height = 0
        # the widths
        canvas_item_sizings = list()
        for x in range(self.__size.width):
            canvas_items = [visible_canvas_item(self.__columns[x][y]) for y in range(self.__size.height)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items))
        for canvas_item_sizing in canvas_item_sizings:
            self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_width", operator.add)
            self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_width", operator.add)
            self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_width", operator.add, True)
        # the heights
        canvas_item_sizings = list()
        for y in range(self.__size.height):
            canvas_items = [visible_canvas_item(self.__columns[x][y]) for x in range(self.__size.width)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items))
        for canvas_item_sizing in canvas_item_sizings:
            self._combine_sizing_property(sizing, canvas_item_sizing, "preferred_height", operator.add)
            self._combine_sizing_property(sizing, canvas_item_sizing, "minimum_height", operator.add)
            self._combine_sizing_property(sizing, canvas_item_sizing, "maximum_height", operator.add, True)
        if sizing.maximum_width == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.maximum_height == MAX_VALUE or len(canvas_items) == 0:
            sizing.maximum_height = None
        if sizing.maximum_width == 0 or len(canvas_items) == 0:
            sizing.maximum_width = None
        if sizing.preferred_width == 0 or len(canvas_items) == 0:
            sizing.preferred_width = None
        if sizing.maximum_height == 0 or len(canvas_items) == 0:
            sizing.maximum_height = None
        if sizing.preferred_height == 0 or len(canvas_items) == 0:
            sizing.preferred_height = None
        self._adjust_sizing(sizing, self.spacing * (self.__size.width - 1), self.spacing * (self.__size.height - 1))
        return sizing


class CanvasItemComposition(AbstractCanvasItem):
    """A composite canvas item comprised of other canvas items.

    Optionally includes a layout. Compositions without an explicit layout are stacked to fit this container.

    Access child canvas items using canvas_items.

    Child canvas items with higher indexes are considered to be foremost.
    """

    def __init__(self):
        super().__init__()
        self.__canvas_items = []
        self.layout = CanvasItemLayout()
        self.__layout_lock = threading.RLock()

    def close(self):
        self._close()
        with self.__layout_lock:
            canvas_items = self.canvas_items
            self.__canvas_items = None
            for canvas_item in canvas_items:
                canvas_item.close()
        super().close()

    def _close(self):
        pass

    @property
    def canvas_items_count(self) -> int:
        """Return count of canvas items managed by this composition."""
        return len(self.__canvas_items)

    @property
    def canvas_items(self):
        """ Return a copy of the canvas items managed by this composition. """
        return copy.copy(self.__canvas_items)

    @property
    def visible_canvas_items(self):
        with self.__layout_lock:
            if self.__canvas_items is not None:
                return [canvas_item for canvas_item in self.__canvas_items if canvas_item and canvas_item.visible]
        return list()

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Override from abstract canvas item."""
        self._update_layout(canvas_origin, canvas_size, immediate=immediate)

    def _update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        """Private method, but available to tests."""
        with self.__layout_lock:
            if self.__canvas_items is not None:
                assert canvas_origin is not None
                assert canvas_size is not None
                canvas_origin = Geometry.IntSize.make(canvas_origin)
                canvas_size = Geometry.IntSize.make(canvas_size)
                self._update_self_layout(canvas_origin, canvas_size, immediate=immediate)
                self._update_child_layouts(canvas_size, immediate=immediate)

    def _update_child_layouts(self, canvas_size, *, immediate=False):
        with self.__layout_lock:
            if self.__canvas_items is not None:
                assert canvas_size is not None
                canvas_size = Geometry.IntSize.make(canvas_size)
                self.layout.layout(Geometry.IntPoint(), canvas_size, self.visible_canvas_items, immediate=immediate)

    # override sizing information. let layout provide it.
    @property
    def layout_sizing(self):
        sizing = self.sizing
        layout_sizing = self.layout.get_sizing(self.visible_canvas_items)
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
        if len(self.visible_canvas_items) == 0 and sizing.collapsible:
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
        canvas_item._inserted(self)
        self.layout.add_canvas_item(canvas_item, pos)
        self.refresh_layout()
        self.update()
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

    def _remove_canvas_item(self, canvas_item):
        canvas_item._removed(self)
        canvas_item.close()
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        self.__canvas_items.remove(canvas_item)
        self.refresh_layout()
        self.update()

    def remove_canvas_item(self, canvas_item):
        """ Remove canvas item from layout. Canvas item is closed. """
        self._remove_canvas_item(canvas_item)

    def remove_all_canvas_items(self):
        """ Remove all canvas items from layout. Canvas items are closed. """
        for canvas_item in reversed(copy.copy(self.__canvas_items)):
            self._remove_canvas_item(canvas_item)

    def replace_canvas_item(self, old_canvas_item, new_canvas_item, container=None):
        """ Replace the given canvas item with the new one. Canvas item is closed. """
        index = self.__canvas_items.index(old_canvas_item)
        self.remove_canvas_item(old_canvas_item)
        self.insert_canvas_item(index, new_canvas_item)

    def wrap_canvas_item(self, canvas_item, canvas_item_container):
        """ Replace the given canvas item with the container and move the canvas item into the container. """
        canvas_origin = canvas_item.canvas_origin
        canvas_size = canvas_item.canvas_size
        index = self.__canvas_items.index(canvas_item)
        # remove the existing canvas item, but without closing it.
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        self._remove_canvas_item_direct(canvas_item)
        # insert the canvas item container
        # self.insert_canvas_item(index, canvas_item_container)  # this would adjust splitters. don't do it.
        self._insert_canvas_item_direct(index, canvas_item_container)
        # insert the canvas item into the container
        canvas_item_container.add_canvas_item(canvas_item)
        # perform the layout using existing origin/size.
        if canvas_origin is not None and canvas_size is not None:
            canvas_item_container._set_canvas_origin(canvas_origin)
            canvas_item_container._set_canvas_size(canvas_size)
            canvas_item._set_canvas_origin(Geometry.IntPoint())
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

    def _repaint_template(self, drawing_context: DrawingContext.DrawingContext, immediate: bool) -> None:
        self._repaint_children(drawing_context, immediate=immediate)
        self._repaint(drawing_context)

    def _repaint_children(self, drawing_context, *, immediate=False):
        """Paint items from back to front."""
        self._draw_background(drawing_context)
        for canvas_item in self.visible_canvas_items:
            if canvas_item._has_layout:
                with drawing_context.saver():
                    canvas_item_rect = canvas_item.canvas_rect
                    drawing_context.translate(canvas_item_rect.left, canvas_item_rect.top)
                    canvas_item._repaint_if_needed(drawing_context, immediate=immediate)
        self._draw_border(drawing_context)

    def _canvas_items_at_point(self, visible_canvas_items, x, y):
        """Returns list of canvas items under x, y, ordered from back to front."""
        canvas_items = []
        point = Geometry.IntPoint(x=x, y=y)
        for canvas_item in reversed(visible_canvas_items):
            # the visible items can be changed while this method is running from the layout thread.
            # and yet we don't want to allow this to occur; maybe the layout thread should have some
            # sort of pending system, where once methods like this exit, they're allowed to update...?
            if canvas_item.canvas_rect.contains_point(point):
                canvas_point = point - Geometry.IntPoint.make(canvas_item.canvas_origin)
                canvas_items.extend(canvas_item.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super().canvas_items_at_point(x, y))
        return canvas_items

    def canvas_items_at_point(self, x, y):
        """Returns list of canvas items under x, y, ordered from back to front."""
        return self._canvas_items_at_point(self.visible_canvas_items, x, y)

    def pan_gesture(self, dx, dy):
        for canvas_item in reversed(self.visible_canvas_items):
            if canvas_item.pan_gesture(dx, dy):
                return True
        return False


_threaded_rendering_enabled = True
_layer_id = 0


class LayerCanvasItem(CanvasItemComposition):
    """A composite canvas item that does layout and repainting in a thread."""

    def __init__(self):
        super().__init__()
        global _layer_id
        _layer_id += 1
        self.__layer_id = _layer_id
        self.__layer_lock = threading.RLock()
        self.__layer_drawing_context = None
        self.__layer_seed = 0
        self.__cancel = False
        self.__needs_layout = False
        self.__needs_repaint = False
        self.__prepare_canvas_items = list()
        global _threaded_rendering_enabled
        self._layer_thread_suppress = not _threaded_rendering_enabled  # for testing
        self.__layer_thread_condition = threading.Condition()
        self.__layer_thread = threading.Thread(target=self.__repaint_loop, daemon=True)
        self.__layer_thread.start()

    def _close(self):
        self._stop_render_behavior()

    def _stop_render_behavior(self):
        if self.__layer_thread:
            self.__cancel = True
            with self.__layer_thread_condition:
                self.__layer_thread_condition.notify()
            self.__layer_thread.join()
            self.__layer_thread = None
            self.__layer_drawing_context = None

    @property
    def _needs_layout_for_testing(self):
        return self.__needs_layout

    @property
    def layer_container(self) -> "CanvasItemComposition":
        return self

    def register_prepare_canvas_item(self, canvas_item: AbstractCanvasItem) -> None:
        assert canvas_item not in self.__prepare_canvas_items
        self.__prepare_canvas_items.append(canvas_item)

    def unregister_prepare_canvas_item(self, canvas_item: AbstractCanvasItem) -> None:
        assert canvas_item in self.__prepare_canvas_items
        self.__prepare_canvas_items.remove(canvas_item)

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        if immediate:
            self._update_layout(canvas_origin, canvas_size, immediate=True)
        else:
            # layout self, but not the children. layout for children goes to thread.
            self._update_self_layout(canvas_origin, canvas_size)
            self.__trigger_layout()

    def _needs_layout(self, canvas_item):
        self.__trigger_layout()

    def _updated(self):
        with self.__layer_thread_condition:
            self.__needs_repaint = True
            if not self._layer_thread_suppress:
                self.__layer_thread_condition.notify()
        super()._updated()

    def _handle_end_update(self):
        if self._layer_thread_suppress:
            # pass through updates in the thread is suppressed, so that updates actually occur.
            super()._handle_end_update()

    def _repaint_template(self, drawing_context: DrawingContext.DrawingContext, immediate: bool) -> None:
        if immediate:
            self.repaint_immediate(drawing_context, self.canvas_size)
        else:
            with self.__layer_lock:
                layer_drawing_context = self.__layer_drawing_context
                layer_seed = self.__layer_seed
            canvas_rect = self.canvas_rect
            canvas_rect = canvas_rect or (0, 0, 0, 0)
            drawing_context.begin_layer(self.__layer_id, layer_seed, *tuple(canvas_rect.origin), *tuple(canvas_rect.size))
            if layer_drawing_context:
                drawing_context.add(layer_drawing_context)
            drawing_context.end_layer(self.__layer_id, layer_seed, *tuple(canvas_rect.origin), *tuple(canvas_rect.size))

    def _repaint_if_needed(self, drawing_context, *, immediate=False) -> None:
        # If the render behavior is a layer, it will have its own cached drawing context. Use it.
        self._repaint_template(drawing_context, immediate)

    def layout_immediate(self, canvas_size: Geometry.IntSize, force: bool=True) -> None:
        orphan = len(self.__prepare_canvas_items) == 0
        if orphan:
            self._inserted(None)
        if force or self.__needs_layout:
            self.__needs_layout = False
            layer_thread_suppress, self._layer_thread_suppress = self._layer_thread_suppress, True
            for canvas_item in copy.copy(self.__prepare_canvas_items):
                canvas_item.prepare_render()
            self._update_self_layout(Geometry.IntPoint(), canvas_size, immediate=True)
            self._update_child_layouts(canvas_size, immediate=True)
            self._layer_thread_suppress = layer_thread_suppress
        if orphan:
            self._removed(None)

    def repaint_immediate(self, drawing_context: DrawingContext.DrawingContext, canvas_size: Geometry.IntSize) -> None:
        orphan = len(self.__prepare_canvas_items) == 0
        if orphan:
            self._inserted(None)
        layer_thread_suppress, self._layer_thread_suppress = self._layer_thread_suppress, True
        self._layer_thread_suppress = True
        for canvas_item in copy.copy(self.__prepare_canvas_items):
            canvas_item.prepare_render()
        self._update_self_layout(Geometry.IntPoint(), canvas_size, immediate=True)
        self._update_child_layouts(canvas_size, immediate=True)
        self._repaint_children(drawing_context, immediate=True)
        self._repaint(drawing_context)
        self._layer_thread_suppress = layer_thread_suppress
        if orphan:
            self._removed(None)

    def __repaint_loop(self):
        while not self.__cancel:
            with self.__layer_thread_condition:
                self.__layer_thread_condition.wait()
            while True:
                with self.__layer_thread_condition:
                    needs_layout = self.__needs_layout
                    needs_repaint = self.__needs_repaint
                    self.__needs_layout = False
                    self.__needs_repaint = False
                if not self.__cancel and not self._layer_thread_suppress and (needs_repaint or needs_layout):
                    if self._has_layout:
                        try:
                            for canvas_item in copy.copy(self.__prepare_canvas_items):
                                canvas_item.prepare_render()
                                # layout or repaint that occurs during prepare render should be handled
                                # but not trigger another repaint after this one.
                                with self.__layer_thread_condition:
                                    needs_layout = needs_layout or self.__needs_layout
                                    needs_repaint = needs_repaint or self.__needs_repaint
                                    self.__needs_layout = False
                                    self.__needs_repaint = False
                            if needs_layout:
                                assert self.canvas_size is not None
                                self._update_child_layouts(self.canvas_size)
                            drawing_context = DrawingContext.DrawingContext()
                            self._repaint_children(drawing_context)
                            self._repaint(drawing_context)
                            with self.__layer_lock:
                                self.__layer_seed += 1
                                self.__layer_drawing_context = drawing_context
                            self._repaint_finished(self.__layer_drawing_context)
                        except Exception as e:
                            import traceback
                            logging.debug("CanvasItem Render Error: %s", e)
                            traceback.print_exc()
                            traceback.print_stack()
                else:
                    break

    def __trigger_layout(self):
        with self.__layer_thread_condition:
            self.__needs_layout = True
            if not self._layer_thread_suppress:
                self.__layer_thread_condition.notify()

    def _repaint_finished(self, drawing_context):
        self._update_container()


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
        super().__init__()
        self.__content = None
        if content:
            self.content = content
        self.auto_resize_contents = False
        self._constrain_position = True
        self.content_updated_event = Event.Event()

    def close(self):
        content = self.__content
        self.__content = None
        if content:
            content.close()
        super().close()

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
        self.update()

    @property
    def visible_rect(self) -> Geometry.IntRect:
        return Geometry.IntRect(origin=-Geometry.IntPoint.make(self.__content.canvas_origin), size=Geometry.IntSize.make(self.canvas_size))

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
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
            self.__content.update_layout(Geometry.IntPoint(), self.canvas_size, immediate=immediate)
        elif self.auto_resize_contents:
            # if content has no assigned layout, update its layout relative to this object.
            # it will get a 0,0 origin but the same size as this scroll area.
            self.__content.update_layout(self.__content.canvas_origin, self.canvas_size, immediate=immediate)
        # validate the content origin. this is used for the scroll bar canvas item to ensure that the content is
        # consistent with the scroll bar.
        self.__content_layout_updated(self.__content.canvas_origin, self.__content.canvas_size, immediate=immediate)
        # NOTE: super is never called for this implementation
        # call on_layout_updated, just like the super implementation.
        if self.on_layout_updated:
            self.on_layout_updated(self.canvas_origin, self.canvas_size, immediate=immediate)
        self._has_layout = self.canvas_origin is not None and self.canvas_size is not None

    def __content_layout_updated(self, canvas_origin, canvas_size, *, immediate=False):
        # whenever the content layout changes, this method gets called.
        # adjust the canvas_origin of the content if necessary. pass the canvas_origin, canvas_size of the content.
        # this method is used in the scroll bar canvas item to ensure that the content stays within view and
        # consistent with the scroll bar when the scroll area gets a new layout.
        if self._constrain_position and canvas_origin is not None and canvas_size is not None and self.canvas_origin is not None and self.canvas_size is not None:
            # when the scroll area content layout changes, this method will get called.
            # ensure that the content matches the scroll position.
            visible_size = self.canvas_size
            content_size = self.content.canvas_size
            scroll_range_h = max(content_size.width - visible_size.width, 0)
            scroll_range_v = max(content_size.height - visible_size.height, 0)
            canvas_origin = Geometry.IntPoint(x=canvas_origin.x, y=max(min(canvas_origin.y, 0), -scroll_range_v))
            canvas_origin = Geometry.IntPoint(x=max(min(canvas_origin.x, 0), -scroll_range_h), y=canvas_origin.y)
            self.__content._set_canvas_origin(canvas_origin)
            self.content_updated_event.fire()

    def _repaint(self, drawing_context):
        super()._repaint(drawing_context)
        with drawing_context.saver():
            drawing_context.clip_rect(self.canvas_origin[1], self.canvas_origin[0], self.canvas_size[1], self.canvas_size[0])
            drawing_context.translate(self.__content.canvas_origin[1], self.__content.canvas_origin[0])
            visible_rect = Geometry.IntRect(origin=-Geometry.IntPoint.make(self.__content.canvas_origin), size=Geometry.IntSize.make(self.canvas_size))
            self.__content._repaint_visible(drawing_context, visible_rect)

    def canvas_items_at_point(self, x, y):
        canvas_items = []
        point = Geometry.IntPoint(x=x, y=y)
        if self.__content.canvas_rect.contains_point(point):
            canvas_point = point - Geometry.IntPoint.make(self.__content.canvas_origin)
            canvas_items.extend(self.__content.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super().canvas_items_at_point(x, y))
        return canvas_items

    def wheel_changed(self, x, y, dx, dy, is_horizontal):
        x -= self.canvas_origin.x
        y -= self.canvas_origin.y
        return self.__content.wheel_changed(x, y, dx, dy, is_horizontal)

    def pan_gesture(self, dx, dy):
        return self.__content.pan_gesture(dx, dy)


class SplitterCanvasItem(CanvasItemComposition):

    def __init__(self, orientation=None):
        super().__init__()
        self.orientation = orientation if orientation else "vertical"
        self.wants_mouse_events = True
        self.__lock = threading.RLock()
        self.__sizings = []
        self.__canvas_items = []
        self.__actual_sizings = []
        self.__tracking = False
        self.on_splits_will_change = None
        self.on_splits_changed = None

    def __calculate_layout(self, canvas_size, sizings):
        if self.orientation == "horizontal":
            content_origin = 0
            content_size = Geometry.IntSize.make(canvas_size).height
            constraints = [sizing.get_height_constraint(content_size) for sizing in sizings]
        else:
            content_origin = 0
            content_size = Geometry.IntSize.make(canvas_size).width
            constraints = [sizing.get_width_constraint(content_size) for sizing in sizings]
        return constraint_solve(content_origin, content_size, constraints)

    @property
    def splits(self):
        """ Return the canvas item splits, which represent the relative size of each child. """
        if self.canvas_origin is not None:
            if self.orientation == "horizontal":
                content_size = Geometry.IntSize.make(self.canvas_size).height
            else:
                content_size = Geometry.IntSize.make(self.canvas_size).width
            with self.__lock:
                sizings = copy.deepcopy(self.__sizings)
            _, sizes = self.__calculate_layout(self.canvas_size, sizings)
            return [float(size) / content_size for size in sizes]
        return None

    @splits.setter
    def splits(self, splits):
        with self.__lock:
            sizings = copy.deepcopy(self.__sizings)
        assert len(splits) == len(sizings)
        for split, sizing in zip(splits, sizings):
            if self.orientation == "horizontal":
                sizing.preferred_height = split
            else:
                sizing.preferred_width = split
        with self.__lock:
            self.__sizings = sizings
        self.refresh_layout()

    def _insert_canvas_item_direct(self, before_index, canvas_item, pos=None):
        super().insert_canvas_item(before_index, canvas_item)

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
        with self.__lock:
            self.__sizings.insert(before_index, sizing)
        super().insert_canvas_item(before_index, canvas_item)

    def remove_canvas_item(self, canvas_item):
        with self.__lock:
            del self.__sizings[self.canvas_items.index(canvas_item)]
        super().remove_canvas_item(canvas_item)

    def update_layout(self, canvas_origin, canvas_size, *, immediate=False):
        with self.__lock:
            canvas_items = copy.copy(self.canvas_items)
            sizings = copy.deepcopy(self.__sizings)
        assert len(canvas_items) == len(sizings)
        origins, sizes = self.__calculate_layout(canvas_size, sizings)
        if self.orientation == "horizontal":
            for canvas_item, (origin, size) in zip(canvas_items, zip(origins, sizes)):
                canvas_item_origin = Geometry.IntPoint(y=origin, x=0)  # origin within the splitter
                canvas_item_size = Geometry.IntSize(height=size, width=canvas_size.width)
                canvas_item.update_layout(canvas_item_origin, canvas_item_size, immediate=immediate)
                assert canvas_item._has_layout
            for sizing, size in zip(sizings, sizes):
                sizing.preferred_height = size
        else:
            for canvas_item, (origin, size) in zip(canvas_items, zip(origins, sizes)):
                canvas_item_origin = Geometry.IntPoint(y=0, x=origin)  # origin within the splitter
                canvas_item_size = Geometry.IntSize(height=canvas_size.height, width=size)
                canvas_item.update_layout(canvas_item_origin, canvas_item_size, immediate=immediate)
                assert canvas_item._has_layout
            for sizing, size in zip(sizings, sizes):
                sizing.preferred_width = size
        for canvas_item in canvas_items:
            assert canvas_item._has_layout
        with self.__lock:
            self.__actual_sizings = sizings
            self.__canvas_items = canvas_items
        # instead of calling the canvas item composition, call the one for abstract canvas item.
        self._update_self_layout(canvas_origin, canvas_size, immediate=immediate)
        self._has_layout = self.canvas_origin is not None and self.canvas_size is not None
        # the next update is required because the children will trigger updates; but the updates
        # might not go all the way up the chain if this splitter has no layout. by now, it will
        # have a layout, so force an update.
        self.update()

    def canvas_items_at_point(self, x, y):
        assert self.canvas_origin is not None and self.canvas_size is not None
        with self.__lock:
            canvas_items = copy.copy(self.__canvas_items)
            sizings = copy.deepcopy(self.__actual_sizings)
        origins, _ = self.__calculate_layout(self.canvas_size, sizings)
        if self.orientation == "horizontal":
            for origin in origins[1:]:  # don't check the '0' origin
                if abs(y - origin) < 6:
                    return [self]
        else:
            for origin in origins[1:]:  # don't check the '0' origin
                if abs(x - origin) < 6:
                    return [self]
        return self._canvas_items_at_point(canvas_items, x, y)

    def _repaint(self, drawing_context):
        super()._repaint(drawing_context)
        assert self.canvas_origin is not None and self.canvas_size is not None
        with self.__lock:
            sizings = copy.deepcopy(self.__actual_sizings)
        origins, _ = self.__calculate_layout(self.canvas_size, sizings)
        with drawing_context.saver():
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

    def __hit_test(self, x, y, modifiers):
        with self.__lock:
            sizings = copy.deepcopy(self.__actual_sizings)
        origins, _ = self.__calculate_layout(self.canvas_size, sizings)
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
        with self.__lock:
            sizings = copy.deepcopy(self.__actual_sizings)
        origins, _ = self.__calculate_layout(self.canvas_size, sizings)
        if self.orientation == "horizontal":
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(y - origin) < 6:
                    self.__tracking = True
                    self.__tracking_start_pos = Geometry.IntPoint(y=y, x=x)
                    self.__tracking_start_adjust = y - origin
                    self.__tracking_start_index = index
                    self.__tracking_start_preferred = sizings[index].preferred_height
                    self.__tracking_start_preferred_next = sizings[index + 1].preferred_height
                    if callable(self.on_splits_will_change):
                        self.on_splits_will_change()
                    return True
        else:
            for index, origin in enumerate(origins[1:]):  # don't check the '0' origin
                if abs(x - origin) < 6:
                    self.__tracking = True
                    self.__tracking_start_pos = Geometry.IntPoint(y=y, x=x)
                    self.__tracking_start_adjust = x - origin
                    self.__tracking_start_index = index
                    self.__tracking_start_preferred = sizings[index].preferred_width
                    self.__tracking_start_preferred_next = sizings[index + 1].preferred_width
                    if callable(self.on_splits_will_change):
                        self.on_splits_will_change()
                    return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        self.__tracking = False
        if callable(self.on_splits_changed):
            self.on_splits_changed()
        return True

    def mouse_position_changed(self, x, y, modifiers):
        if self.__tracking:
            with self.__lock:
                old_sizings = copy.deepcopy(self.__sizings)
                temp_sizings = copy.deepcopy(self.__actual_sizings)
            if self.orientation == "horizontal":
                offset = y - self.__tracking_start_pos.y
                if not modifiers.shift:
                    snaps = list()
                    snaps.append((self.__tracking_start_preferred_next - self.__tracking_start_preferred) // 2)
                    snaps.append(self.canvas_bounds.height // 3 - self.__tracking_start_pos.y - self.__tracking_start_adjust)
                    snaps.append(2 * self.canvas_bounds.height // 3 - self.__tracking_start_pos.y - self.__tracking_start_adjust)
                    for snap in snaps:
                        if abs(offset - snap) < 12:
                            offset = snap
                            break
                temp_sizings[self.__tracking_start_index].preferred_height = self.__tracking_start_preferred + offset
                temp_sizings[self.__tracking_start_index + 1].preferred_height = self.__tracking_start_preferred_next - offset
            else:
                offset = x - self.__tracking_start_pos.x
                if not modifiers.shift:
                    snaps = list()
                    snaps.append((self.__tracking_start_preferred_next - self.__tracking_start_preferred) // 2)
                    snaps.append(self.canvas_bounds.width // 3 - self.__tracking_start_pos.x - self.__tracking_start_adjust)
                    snaps.append(2 * self.canvas_bounds.width // 3 - self.__tracking_start_pos.x - self.__tracking_start_adjust)
                    for snap in snaps:
                        if abs(offset - snap) < 12:
                            offset = snap
                            break
                temp_sizings[self.__tracking_start_index].preferred_width = self.__tracking_start_preferred + offset
                temp_sizings[self.__tracking_start_index + 1].preferred_width = self.__tracking_start_preferred_next - offset
            # fix the size of all children except for the two in question
            for index, sizing in enumerate(temp_sizings):
                if index != self.__tracking_start_index and index != self.__tracking_start_index + 1:
                    if self.orientation == "horizontal":
                        sizing.set_fixed_height(sizing.preferred_height)
                    else:
                        sizing.set_fixed_width(sizing.preferred_width)
            # update the layout
            with self.__lock:
                self.__sizings = temp_sizings
            self.refresh_layout()
            self.update_layout(self.canvas_origin, self.canvas_size, immediate=True)
            # restore the freedom of the others
            new_sizings = list()
            for index, (old_sizing, temp_sizing) in enumerate(zip(old_sizings, temp_sizings)):
                sizing = Sizing()
                sizing.copy_from(old_sizing)
                if index == self.__tracking_start_index or index == self.__tracking_start_index + 1:
                    if self.orientation == "horizontal":
                        sizing.preferred_height = temp_sizing.preferred_height
                    else:
                        sizing.preferred_width = temp_sizing.preferred_width
                new_sizings.append(sizing)
            with self.__lock:
                self.__sizings = new_sizings
            return True
        else:
            control = self.__hit_test(x, y, modifiers)
            if control == "horizontal":
                self.cursor_shape = "split_vertical"
            elif control == "vertical":
                self.cursor_shape = "split_horizontal"
            else:
                self.cursor_shape = None
            return super().mouse_position_changed(x, y, modifiers)


PositionLength = collections.namedtuple("PositionLength", ["position", "length"])


class ScrollBarCanvasItem(AbstractCanvasItem):

    """ A scroll bar for a scroll area. """

    def __init__(self, scroll_area_canvas_item, orientation:Orientation = None):
        super().__init__()
        orientation = orientation if orientation is not None else Orientation.Vertical
        self.wants_mouse_events = True
        self.__scroll_area_canvas_item = scroll_area_canvas_item
        self.__scroll_area_canvas_item_content_updated_listener = self.__scroll_area_canvas_item.content_updated_event.listen(self.update)
        self.__tracking = False
        self.__orientation = orientation
        if self.__orientation == Orientation.Vertical:
            self.sizing.set_fixed_width(16)
        else:
            self.sizing.set_fixed_height(16)

    def close(self):
        self.__scroll_area_canvas_item_content_updated_listener.close()
        self.__scroll_area_canvas_item_content_updated_listener = None
        super().close()

    def _repaint(self, drawing_context):
        # canvas size, thumb rect
        canvas_size = self.canvas_size
        thumb_rect = self.thumb_rect

        # draw it
        with drawing_context.saver():
            # draw the border of the scroll bar
            drawing_context.begin_path()
            drawing_context.rect(0, 0, canvas_size.width, canvas_size.height)
            if self.__orientation == Orientation.Vertical:
                gradient = drawing_context.create_linear_gradient(canvas_size.width, canvas_size.height, 0, 0, canvas_size.width, 0)
            else:
                gradient = drawing_context.create_linear_gradient(canvas_size.width, canvas_size.height, 0, 0, 0, canvas_size.height)
            gradient.add_color_stop(0.0, "#F2F2F2")
            gradient.add_color_stop(0.35, "#FDFDFD")
            gradient.add_color_stop(0.65, "#FDFDFD")
            gradient.add_color_stop(1.0, "#F2F2F2")
            drawing_context.fill_style = gradient
            drawing_context.fill()
            # draw the thumb, if any
            if thumb_rect.height > 0 and thumb_rect.width > 0:
                with drawing_context.saver():
                    drawing_context.begin_path()
                    if self.__orientation == Orientation.Vertical:
                        drawing_context.move_to(thumb_rect.width - 8, thumb_rect.top + 6)
                        drawing_context.line_to(thumb_rect.width - 8, thumb_rect.bottom - 6)
                    else:
                        drawing_context.move_to(thumb_rect.left + 6, thumb_rect.height - 8)
                        drawing_context.line_to(thumb_rect.right - 6, thumb_rect.height - 8)
                    drawing_context.line_width = 8.0
                    drawing_context.line_cap = "round"
                    drawing_context.stroke_style = "#888" if self.__tracking else "#CCC"
                    drawing_context.stroke()
            # draw inside edge
            drawing_context.begin_path()
            drawing_context.move_to(0, 0)
            if self.__orientation == Orientation.Vertical:
                drawing_context.line_to(0, canvas_size.height)
            else:
                drawing_context.line_to(canvas_size.width, 0)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#E3E3E3"
            drawing_context.stroke()
            # draw outside
            drawing_context.begin_path()
            if self.__orientation == Orientation.Vertical:
                drawing_context.move_to(canvas_size.width, 0)
            else:
                drawing_context.move_to(0, canvas_size.height)
            drawing_context.line_to(canvas_size.width, canvas_size.height)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#999999"
            drawing_context.stroke()

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
        content_offset = max(-scroll_range, min(0, content_offset))
        # assert content_offset <= 0 and content_offset >= -scroll_range
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
        index = 0 if self.__orientation == Orientation.Vertical else 1
        visible_length = self.__scroll_area_canvas_item.canvas_size[index]
        content_length = self.__scroll_area_canvas_item.content.canvas_size[index]
        content_offset = self.__scroll_area_canvas_item.content.canvas_origin[index]
        thumb_position, thumb_length = self.get_thumb_position_and_length(canvas_size[index], visible_length, content_length, content_offset)
        if self.__orientation == Orientation.Vertical:
            thumb_origin = Geometry.IntPoint(x=0, y=thumb_position)
            thumb_size = Geometry.IntSize(width=canvas_size.width, height=thumb_length)
        else:
            thumb_origin = Geometry.IntPoint(x=thumb_position, y=0)
            thumb_size = Geometry.IntSize(width=thumb_length, height=canvas_size.height)
        return Geometry.IntRect(origin=thumb_origin, size=thumb_size)

    def mouse_pressed(self, x, y, modifiers):
        thumb_rect = self.thumb_rect
        pos = Geometry.IntPoint(x=x, y=y)
        if thumb_rect.contains_point(pos):
            self.__tracking = True
            self.__tracking_start = pos
            self.__tracking_content_offset = self.__scroll_area_canvas_item.content.canvas_origin
            self.update()
            return True
        elif self.__orientation == Orientation.Vertical and y < thumb_rect.top:
            self.__adjust_thumb(-1)
            return True
        elif self.__orientation == Orientation.Vertical and y > thumb_rect.bottom:
            self.__adjust_thumb(1)
            return True
        elif self.__orientation != Orientation.Vertical and x < thumb_rect.left:
            self.__adjust_thumb(-1)
            return True
        elif self.__orientation != Orientation.Vertical and x > thumb_rect.right:
            self.__adjust_thumb(1)
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x, y, modifiers):
        self.__tracking = False
        self.update()
        return super().mouse_released(x, y, modifiers)

    def __adjust_thumb(self, amount):
        # adjust the position up or down one visible screen worth
        index = 0 if self.__orientation == Orientation.Vertical else 1
        visible_length = self.__scroll_area_canvas_item.canvas_size[index]
        content = self.__scroll_area_canvas_item.content
        if self.__orientation == Orientation.Vertical:
            new_content_offset = Geometry.IntPoint(y=content.canvas_origin[0] - visible_length * amount, x=content.canvas_origin[1])
        else:
            new_content_offset = Geometry.IntPoint(y=content.canvas_origin[0], x=content.canvas_origin[1] - visible_length * amount)
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
            if self.__orientation == Orientation.Vertical:
                mouse_offset_v = pos.y - self.__tracking_start.y
                visible_height = self.__scroll_area_canvas_item.canvas_size[0]
                content_height = self.__scroll_area_canvas_item.content.canvas_size[0]
                new_content_offset_v = self.adjust_content_offset(self.canvas_size[0], visible_height, content_height, self.__tracking_content_offset[0], mouse_offset_v)
                new_content_offset = Geometry.IntPoint(x=self.__tracking_content_offset[1], y=new_content_offset_v)
            else:
                mouse_offset_h = pos.x - self.__tracking_start.x
                visible_width = self.__scroll_area_canvas_item.canvas_size[1]
                content_width = self.__scroll_area_canvas_item.content.canvas_size[1]
                new_content_offset_h = self.adjust_content_offset(self.canvas_size[1], visible_width, content_width, self.__tracking_content_offset[1], mouse_offset_h)
                new_content_offset = Geometry.IntPoint(x=new_content_offset_h, y=self.__tracking_content_offset[0])
            self.__scroll_area_canvas_item.content._set_canvas_origin(new_content_offset)
            self.__scroll_area_canvas_item.content.update()
            self.update()
        return super().mouse_position_changed(x, y, modifiers)


class RootCanvasItem(LayerCanvasItem):
    """A root layer to interface to the widget world.

    The root canvas item acts as a bridge between the higher level ui widget and a canvas hierarchy. It connects size
    notifications, mouse activity, keyboard activity, focus activity, and drag and drop actions to the canvas item.

    The root canvas item provides a canvas_widget property which is the canvas widget associated with this root item.

    The root canvas may be focusable or not. There are two focus states that this root canvas item handles: the widget
    focus and the canvas item focus. The widget focus comes from the enclosing widget. If this root canvas item has a
    widget focus, then it can also have a canvas item focus to specify which specific canvas item is the focus in this
    root canvas item's hierarchy.
    """

    def __init__(self, canvas_widget, max_frame_rate=None):
        super().__init__()
        self.__canvas_widget = canvas_widget
        self.__canvas_widget.on_size_changed = self.size_changed
        self.__canvas_widget.on_mouse_clicked = self.__mouse_clicked
        self.__canvas_widget.on_mouse_double_clicked = self.__mouse_double_clicked
        self.__canvas_widget.on_mouse_entered = self.__mouse_entered
        self.__canvas_widget.on_mouse_exited = self.__mouse_exited
        self.__canvas_widget.on_mouse_pressed = self.__mouse_pressed
        self.__canvas_widget.on_mouse_released = self.__mouse_released
        self.__canvas_widget.on_mouse_position_changed = self.__mouse_position_changed
        self.__canvas_widget.on_grabbed_mouse_position_changed = self.__grabbed_mouse_position_changed
        self.__canvas_widget.on_wheel_changed = self.wheel_changed
        self.__canvas_widget.on_context_menu_event = self.__context_menu_event
        self.__canvas_widget.on_key_pressed = self.__key_pressed
        self.__canvas_widget.on_key_released = self.__key_released
        self.__canvas_widget.on_focus_changed = self.__focus_changed
        self.__canvas_widget.on_drag_enter = self.__drag_enter
        self.__canvas_widget.on_drag_leave = self.__drag_leave
        self.__canvas_widget.on_drag_move = self.__drag_move
        self.__canvas_widget.on_drop = self.__drop
        self.__canvas_widget.on_tool_tip = self.handle_tool_tip
        self.__canvas_widget.on_pan_gesture = self.pan_gesture
        self.__canvas_widget.on_dispatch_any = self.__dispatch_any
        self.__canvas_widget.on_get_menu_item_state = self.__get_menu_item_state
        self.__canvas_widget._root_canvas_item = weakref.ref(self)  # for debugging
        self.__max_frame_rate = float(max_frame_rate) if max_frame_rate is not None else DEFAULT_MAX_FRAME_RATE
        self.__drawing_context_updated = False
        self.__focused_item = None
        self.__last_focused_item = None
        self.__mouse_canvas_item = None  # not None when the mouse is pressed
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item = None
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item = None
        self.__grab_canvas_item = None
        self._set_canvas_origin(Geometry.IntPoint())

    def close(self):
        # shut down the repaint thread first
        self._stop_render_behavior()  # call first so that it doesn't use canvas widget
        self.__mouse_tracking_canvas_item = None
        self.__drag_tracking_canvas_item = None
        self.__grab_canvas_item = None
        self.__focused_item = None
        self.__last_focused_item = None
        self.__canvas_widget.on_size_changed = None
        self.__canvas_widget.on_mouse_clicked = None
        self.__canvas_widget.on_mouse_double_clicked = None
        self.__canvas_widget.on_mouse_entered = None
        self.__canvas_widget.on_mouse_exited = None
        self.__canvas_widget.on_mouse_pressed = None
        self.__canvas_widget.on_mouse_released = None
        self.__canvas_widget.on_mouse_position_changed = None
        self.__canvas_widget.on_grabbed_mouse_position_changed = None
        self.__canvas_widget.on_wheel_changed = None
        self.__canvas_widget.on_context_menu_event = None
        self.__canvas_widget.on_key_pressed = None
        self.__canvas_widget.on_key_released = None
        self.__canvas_widget.on_focus_changed = None
        self.__canvas_widget.on_drag_enter = None
        self.__canvas_widget.on_drag_leave = None
        self.__canvas_widget.on_drag_move = None
        self.__canvas_widget.on_drop = None
        self.__canvas_widget.on_tool_tip = None
        self.__canvas_widget.on_pan_gesture = None
        self.__canvas_widget = None
        super().close()

    def _repaint_finished(self, drawing_context):
        self.__canvas_widget.draw(drawing_context)

    def refresh_layout(self):
        self._needs_layout(self)

    @property
    def root_container(self):
        return self

    @property
    def canvas_widget(self):
        """ Return the canvas widget. """
        return self.__canvas_widget

    def map_to_global(self, p):
        return self.__canvas_widget.map_to_global(p)

    @property
    def focusable(self):
        """ Return whether the canvas widget is focusable. """
        return self.canvas_widget.focusable

    @focusable.setter
    def focusable(self, focusable):
        """ Set whether the canvas widget is focusable. """
        self.canvas_widget.focusable = focusable

    def size_changed(self, width, height):
        """ Called when size changes. """
        # logging.debug("{} {} x {}".format(id(self), width, height))
        if width > 0 and height > 0:
            self._set_canvas_origin(Geometry.IntPoint())
            self._set_canvas_size(Geometry.IntSize(height=height, width=width))
            self._has_layout = self.canvas_origin is not None and self.canvas_size is not None
            self.refresh_layout()

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

    def wheel_changed(self, x, y, dx, dy, is_horizontal):
        # always give the mouse canvas item priority (for tracking outside bounds)
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in reversed(canvas_items):
            if canvas_item != self:
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
                if canvas_item.wheel_changed(canvas_item_point.x, canvas_item_point.y, dx, dy, is_horizontal):
                    return True
        return False

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in reversed(canvas_items):
            if canvas_item != self:
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
                if canvas_item.handle_tool_tip(canvas_item_point.x, canvas_item_point.y, gx, gy):
                    return True
        return False

    def __dispatch_any(self, method: str, *args, **kwargs) -> bool:
        focused_item = self.focused_item
        if focused_item:
            return focused_item._dispatch_any(method, *args, **kwargs)
        return False

    def __get_menu_item_state(self, command_id: str):
        focused_item = self.focused_item
        if focused_item:
            menu_item_state = focused_item._get_menu_item_state(command_id)
            if menu_item_state:
                return menu_item_state
        return None

    def _cursor_shape_changed(self, item):
        if item == self.__mouse_tracking_canvas_item:
            self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)

    def _restore_cursor_shape(self):
        # if self.__mouse_tracking_canvas_item:
        #     self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
        # else:
        self.__canvas_widget.set_cursor_shape(None)

    def __mouse_entered(self):
        self.__mouse_tracking = True

    def __mouse_exited(self):
        if self.__mouse_tracking_canvas_item:
            self.__mouse_tracking_canvas_item.mouse_exited()
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item = None
        self.__canvas_widget.set_cursor_shape(None)
        self.__canvas_widget.tool_tip = None

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
                self.__canvas_widget.tool_tip = self.__mouse_tracking_canvas_item.tool_tip
        if self.__mouse_tracking_canvas_item:
            self.__mouse_canvas_item = self.__mouse_tracking_canvas_item
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_canvas_item)
            self.__request_focus_canvas_item = self.__mouse_canvas_item
            return self.__mouse_canvas_item.mouse_pressed(canvas_item_point.x, canvas_item_point.y, modifiers)
        return False

    def __mouse_released(self, x, y, modifiers):
        if self.__mouse_canvas_item:
            if self.__request_focus_canvas_item:
                self.__request_focus(self.__request_focus_canvas_item)
                self.__request_focus_canvas_item = None
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_canvas_item)
            result = self.__mouse_canvas_item.mouse_released(canvas_item_point.x, canvas_item_point.y, modifiers)
            self.__mouse_canvas_item = None
            self.__mouse_position_changed(x, y, modifiers)
            return result
        return False

    def bypass_request_focus(self):
        self.__request_focus_canvas_item = None

    def __mouse_position_changed(self, x, y, modifiers):
        if not self.__mouse_tracking:
            # handle case where mouse is suddenly within this canvas item but it never entered. this can happen when
            # the user activates the application.
            self.mouse_entered()
        if self.__mouse_tracking and not self.__mouse_tracking_canvas_item:
            # find the existing canvas item that is or wants to track the mouse. if it's new, call entered and update
            # the cursor.
            self.__mouse_tracking_canvas_item = self.__mouse_canvas_item_at_point(x, y)
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_entered()
                self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
                self.__canvas_widget.tool_tip = self.__mouse_tracking_canvas_item.tool_tip
        new_mouse_canvas_item = self.__mouse_canvas_item_at_point(x, y)
        if self.__mouse_tracking_canvas_item != new_mouse_canvas_item:
            # if the mouse tracking canvas item changes, exit the old one and enter the new one.
            if self.__mouse_tracking_canvas_item:
                # there may be a case where the mouse has moved outside the canvas item and the canvas
                # item has also been closed. for instance, context menu item which closes the canvas item.
                # so double check whether the mouse tracking canvas item is still in the hierarchy by checking
                # its container. only call mouse existed if the item is still in the hierarchy.
                if self.__mouse_tracking_canvas_item.container:
                    self.__mouse_tracking_canvas_item.mouse_exited()
                self.__canvas_widget.set_cursor_shape(None)
                self.__canvas_widget.tool_tip = None
            self.__mouse_tracking_canvas_item = new_mouse_canvas_item
            if self.__mouse_tracking_canvas_item:
                self.__mouse_tracking_canvas_item.mouse_entered()
                self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
                self.__canvas_widget.tool_tip = self.__mouse_tracking_canvas_item.tool_tip
        # finally, send out the actual position changed message to the (possibly new) current mouse tracking canvas
        # item. also make note of the last time the cursor changed for tool tip tracking.
        if self.__mouse_tracking_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_tracking_canvas_item)
            self.__mouse_tracking_canvas_item.mouse_position_changed(canvas_item_point.x, canvas_item_point.y, modifiers)

    def __grabbed_mouse_position_changed(self, dx, dy, modifiers):
        if self.__grab_canvas_item:
            self.__grab_canvas_item.grabbed_mouse_position_changed(dx, dy, modifiers)

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

    def __key_released(self, key):
        if self.focused_item:
            return self.focused_item.key_released(key)
        return False

    def __drag_enter(self, mime_data: "UserInterface.MimeData") -> str:
        self.__drag_tracking = True
        return "accept"

    def __drag_leave(self):
        if self.__drag_tracking_canvas_item:
            self.__drag_tracking_canvas_item.drag_leave()
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item = None
        return "accept"

    def __drag_canvas_item_at_point(self, x: int, y: int, mime_data: "UserInterface.MimeData") -> typing.Optional["CanvasItem"]:
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            if canvas_item.wants_drag_event(mime_data, x, y):
                return canvas_item
        return None

    def __drag_move(self, mime_data: "UserInterface.MimeData", x: int, y: int) -> str:
        response = "ignore"
        if self.__drag_tracking and not self.__drag_tracking_canvas_item:
            self.__drag_tracking_canvas_item = self.__drag_canvas_item_at_point(x, y, mime_data)
            if self.__drag_tracking_canvas_item:
                self.__drag_tracking_canvas_item.drag_enter(mime_data)
        new_drag_canvas_item = self.__drag_canvas_item_at_point(x, y, mime_data)
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

    def __drop(self, mime_data: "UserInterface.MimeData", x: int, y: int) -> str:
        response = "ignore"
        if self.__drag_tracking_canvas_item:
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__drag_tracking_canvas_item)
            response = self.__drag_tracking_canvas_item.drop(mime_data, canvas_item_point.x, canvas_item_point.y)
        self.__drag_leave()
        return response

    def drag(self, mime_data: "UserInterface.MimeData", thumbnail=None, hot_spot_x=None, hot_spot_y=None, drag_finished_fn=None) -> None:
        self.__canvas_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def grab_gesture(self, gesture_type):
        """ Grab gesture """
        self.__canvas_widget.grab_gesture(gesture_type)

    def ungrab_gesture(self, gesture_type):
        """ Ungrab gesture """
        self.__canvas_widget.ungrab_gesture(gesture_type)

    def grab_mouse(self, grabbed_canvas_item, gx, gy):
        self.__canvas_widget.grab_mouse(gx, gy)
        self.__grab_canvas_item = grabbed_canvas_item

    def release_mouse(self):
        self.__canvas_widget.release_mouse()
        self._restore_cursor_shape()
        self.__grab_canvas_item = None

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        self.__canvas_widget.show_tool_tip_text(text, gx, gy)


class BackgroundCanvasItem(AbstractCanvasItem):

    """ Canvas item to draw background_color. """

    def __init__(self, background_color="#888"):
        super().__init__()
        self.background_color = background_color

    def _repaint(self, drawing_context):
        # canvas size
        canvas_width = self.canvas_size[1]
        canvas_height = self.canvas_size[0]
        with drawing_context.saver():
            drawing_context.begin_path()
            drawing_context.rect(0, 0, canvas_width, canvas_height)
            drawing_context.fill_style = self.background_color
            drawing_context.fill()


class CellCanvasItem(AbstractCanvasItem):

    """ Canvas item to draw and respond to user events for a cell.

    A cell must implement the following interface:

        event: update_event() - fired when the canvas item needs an update
        method: paint_cell(drawing_context, rect, style) - called to draw the cell

    The style parameter passed to paint_cell is a list with zero or one strings from each of the aspects below:
        disabled (default is enabled)
        checked, partial (default is unchecked)
        hover, active (default is none)
    """

    def __init__(self, cell=None):
        super().__init__()
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
        super().close()

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


class TwistDownCell:

    def __init__(self):
        super().__init__()
        self.update_event = Event.Event()

    def paint_cell(self, drawing_context, rect, style):

        # disabled (default is enabled)
        # checked, partial (default is unchecked)
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
        super().__init__()
        self.cell = TwistDownCell()
        self.wants_mouse_events = True
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super().close()

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


class BitmapCell:

    def __init__(self, rgba_bitmap_data=None, background_color=None, border_color=None):
        super().__init__()
        self.__rgba_bitmap_data = rgba_bitmap_data
        self.__data = None
        self.__display_limits = None
        self.__color_map_data = None
        self.__background_color = background_color
        self.__border_color = border_color
        self.update_event = Event.Event()

    def set_rgba_bitmap_data(self, rgba_bitmap_data, trigger_update=True):
        self.__rgba_bitmap_data = rgba_bitmap_data
        self.__data = None
        self.__display_limits = None
        self.__color_map_data = None
        if trigger_update:
            self.update_event.fire()

    def set_data(self, data, display_limits, color_map_data, trigger_update=True):
        self.__rgba_bitmap_data = None
        self.__data = data
        self.__display_limits = display_limits
        self.__color_map_data = color_map_data
        if trigger_update:
            self.update_event.fire()

    @property
    def data(self):
        return self.__data

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

        bitmap_data = self.rgba_bitmap_data
        raw_data = self.__data

        # draw the background
        if background_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = background_color
            drawing_context.fill()
        # draw the bitmap
        if bitmap_data is not None:
            image_size = bitmap_data.shape
            if image_size[0] > 0 and image_size[1] > 0:
                display_rect = Geometry.fit_to_size(rect, image_size)
                display_height = display_rect.height
                display_width = display_rect.width
                if display_rect and display_width > 0 and display_height > 0:
                    display_top = display_rect.top
                    display_left = display_rect.left
                    drawing_context.draw_image(bitmap_data, display_left, display_top, display_width, display_height)
        if raw_data is not None:
            image_size = raw_data.shape
            if image_size[0] > 0 and image_size[1] > 0:
                display_rect = Geometry.fit_to_size(rect, image_size)
                display_height = display_rect.height
                display_width = display_rect.width
                if display_rect and display_width > 0 and display_height > 0:
                    display_top = display_rect.top
                    display_left = display_rect.left
                    drawing_context.draw_data(raw_data, display_left, display_top, display_width, display_height, self.__display_limits[0], self.__display_limits[1], self.__color_map_data)
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
        super().__init__()
        self.cell = BitmapCell(rgba_bitmap_data, background_color, border_color)

    def set_rgba_bitmap_data(self, rgba_bitmap_data, trigger_update=True):
        self.cell.set_rgba_bitmap_data(rgba_bitmap_data, trigger_update)

    def set_data(self, data, display_limits, color_map_data, trigger_update=True):
        self.cell.set_data(data, display_limits, color_map_data, trigger_update)

    @property
    def data(self):
        return self.cell.data

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
        super().__init__(rgba_bitmap_data, background_color, border_color)
        self.wants_mouse_events = True
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super().close()

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
        super().__init__()
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
        new_sizing = self.copy_sizing()
        new_sizing.set_fixed_width(font_metrics.width + 2 * horizontal_padding)
        new_sizing.set_fixed_height(font_metrics.height + 2 * vertical_padding)
        self.update_sizing(new_sizing)

    def _repaint(self, drawing_context):
        canvas_bounds_center = self.canvas_bounds.center
        with drawing_context.saver():
            drawing_context.font = self.__font
            drawing_context.text_align = 'center'
            drawing_context.text_baseline = 'middle'
            drawing_context.fill_style = self.__text_color if self.__enabled else self.__text_disabled_color
            drawing_context.fill_text(self.__text, canvas_bounds_center.x, canvas_bounds_center.y + 1)


class TextButtonCanvasItem(StaticTextCanvasItem):

    def __init__(self, text=None):
        super().__init__(text)
        self.wants_mouse_events = True
        self.__border_enabled = True
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.on_button_clicked = None

    def close(self):
        self.on_button_clicked = None
        super().close()

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
        with drawing_context.saver():
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
        super()._repaint(drawing_context)


class CheckBoxCanvasItem(AbstractCanvasItem):

    def __init__(self, text=None):
        super().__init__()
        self.wants_mouse_events = True
        self.__enabled = True
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.__check_state = "unchecked"
        self.__tristate = False
        self.__text = text if text is not None else str()
        self.__text_color = "#000"
        self.__text_disabled_color = "#888"
        self.__font = "12px"
        self.on_checked_changed = None
        self.on_check_state_changed = None

    def close(self):
        self.on_checked_changed = None
        self.on_check_state_changed = None
        super().close()

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        self.__enabled = value
        self.update()

    @property
    def tristate(self):
        return self.__tristate

    @tristate.setter
    def tristate(self, value):
        self.__tristate = value
        if not self.__tristate:
            self.checked = self.check_state == "checked"
        self.update()

    @property
    def check_state(self):
        return self.__check_state

    @check_state.setter
    def check_state(self, value):
        if self.tristate and value not in ("unchecked", "checked", "partial"):
            value = "unchecked"
        elif not self.tristate and value not in ("unchecked", "checked"):
            value = "unchecked"
        self.__check_state = value
        self.update()

    @property
    def checked(self):
        return self.check_state == "checked"

    @checked.setter
    def checked(self, value):
        self.check_state = "checked" if value else "unchecked"

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, value):
        if self.__text != value:
            self.__text = value
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
        self._toggle_checked()
        return True

    def _toggle_checked(self):
        if self.enabled:
            if self.check_state == "checked":
                self.check_state = "unchecked"
            else:
                self.check_state = "checked"
            if self.on_checked_changed:
                self.on_checked_changed(self.check_state == "checked")
            if self.on_check_state_changed:
                self.on_check_state_changed(self.check_state)

    @property
    def _mouse_inside(self):
        return self.__mouse_inside

    @property
    def _mouse_pressed(self):
        return self.__mouse_pressed

    def size_to_content(self, get_font_metrics_fn):
        """ Size the canvas item to the text content. """
        horizontal_padding = 4
        vertical_padding = 3
        font_metrics = get_font_metrics_fn(self.__font, self.__text)
        new_sizing = self.copy_sizing()
        new_sizing.set_fixed_width(font_metrics.width + 2 * horizontal_padding + 14 + 4)
        new_sizing.set_fixed_height(font_metrics.height + 2 * vertical_padding)
        self.update_sizing(new_sizing)

    def _repaint(self, drawing_context):
        canvas_size = self.canvas_size
        with drawing_context.saver():
            drawing_context.begin_path()
            tx = 4 + 14 + 4
            cx = 4 + 7
            cy = canvas_size.height * 0.5
            size = 14
            size_half = 7
            drawing_context.round_rect(4, cy - size_half, size, size, 4.0)
            if self.check_state in ("checked", "partial"):
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
            if self.check_state == "checked":
                drawing_context.begin_path()
                drawing_context.move_to(cx - 3, cy - 2)
                drawing_context.line_to(cx + 0, cy + 2)
                drawing_context.line_to(cx + 8, cy - 9)
                drawing_context.stroke_style = "#000"
                drawing_context.line_width = 2.0
                drawing_context.stroke()
            elif self.check_state == "partial":
                drawing_context.begin_path()
                drawing_context.move_to(cx - 5, cy)
                drawing_context.line_to(cx + 5, cy)
                drawing_context.stroke_style = "#000"
                drawing_context.line_width = 2.0
                drawing_context.stroke()
            drawing_context.font = self.__font
            drawing_context.text_align = 'left'
            drawing_context.text_baseline = 'middle'
            drawing_context.fill_style = self.__text_color if self.__enabled else self.__text_disabled_color
            drawing_context.fill_text(self.__text, tx, cy + 1)

        super()._repaint(drawing_context)


class EmptyCanvasItem(AbstractCanvasItem):

    """ Canvas item to act as a placeholder (spacer or stretch). """

    def __init__(self):
        super().__init__()


class RadioButtonGroup:

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

    @property
    def current_index(self):
        return self.__current_index

    @current_index.setter
    def current_index(self, value):
        self.__current_index = value
        for index, button in enumerate(self.__buttons):
            button.checked = index == self.__current_index


class ProgressBarCanvasItem(AbstractCanvasItem):
    def __init__(self):
        super().__init__()
        self.__enabled = True
        self.__progress = 0.0  # 0.0 to 1.0
        self.sizing.set_fixed_height(4)

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.__enabled = value
        self.update()

    @property
    def progress(self) -> float:
        return self.__progress

    @progress.setter
    def progress(self, value: float) -> None:
        self.__progress = min(max(value, 0.0), 1.0)
        self.update()

    def _repaint(self, drawing_context):
        canvas_size = self.canvas_size
        canvas_bounds_center = self.canvas_bounds.center

        with drawing_context.saver():
            drawing_context.begin_path()
            drawing_context.rect(0, 0, canvas_size.width, canvas_size.height)
            drawing_context.close_path()
            drawing_context.stroke_style = "#CCC"
            drawing_context.fill_style = "#CCC"
            drawing_context.fill()
            drawing_context.stroke()

            if canvas_size.width * self.progress >= 1:
                drawing_context.begin_path()
                drawing_context.rect(0, 0, canvas_size.width * self.progress, canvas_size.height)
                drawing_context.close_path()
                drawing_context.stroke_style = "#6AB"
                drawing_context.fill_style = "#6AB"
                drawing_context.fill()
                drawing_context.stroke()

            if canvas_size.height >= 16 and canvas_size.width * self.progress >= 50: # TODO: use font metrics to find length of text
                progress_text = str(round(self.progress * 100)) + "%"
                drawing_context.begin_path()
                drawing_context.font = "12px sans-serif"
                drawing_context.text_align = 'center'
                drawing_context.text_baseline = 'middle'
                drawing_context.fill_style = "#fff"
                drawing_context.line_width = 2
                drawing_context.fill_text(progress_text, (canvas_size.width - 6) * self.progress - 19, canvas_bounds_center.y + 1)
                drawing_context.fill()
                drawing_context.close_path()

        super()._repaint(drawing_context)


class TimestampCanvasItem(AbstractCanvasItem):
    def __init__(self):
        super().__init__()
        self.__timestamp = None

    @property
    def timestamp(self):
        return self.__timestamp

    @timestamp.setter
    def timestamp(self, value):
        self.__timestamp = value
        # self.update()

    def _repaint_if_needed(self, drawing_context, *, immediate=False):
        if self.__timestamp:
            drawing_context.timestamp(self.__timestamp.isoformat())
        super()._repaint(drawing_context)


def load_rgba_data_from_bytes(b: typing.ByteString, format: str = None) -> numpy.ndarray:
    old_level = logging.getLogger().level
    image_rgba = None
    image_argb = imageio.imread(b, format)
    if image_argb is not None:
        image_rgba = numpy.zeros_like(image_argb)
        image_rgba[:, :, 0] = image_argb[:, :, 2]
        image_rgba[:, :, 1] = image_argb[:, :, 1]
        image_rgba[:, :, 2] = image_argb[:, :, 0]
        image_rgba[:, :, 3] = image_argb[:, :, 3]
        image_rgba = image_rgba.view(numpy.uint32).reshape(image_rgba.shape[:-1])
    return image_rgba
