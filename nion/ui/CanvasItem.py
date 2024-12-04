"""
CanvasItem module contains classes related to canvas items.

OVERVIEW

User interface consists of high-level widgets, usually provided by the host application, and low-level canvas items. 
The canvas items are designed to be lightweight and efficient, and they are used for graphics and other visual 
elements not provided by widgets.

Canvas items are typically created and put into a container to form a tree of canvas items. Canvas items fall into 
two main categories: composite and non-composite. Composite canvas items are containers for other canvas items, 
while non-composite canvas items are the leaf nodes of the canvas item tree. Both are derived from the 
AbstractCanvasItem base class.

The root canvas item in the tree is usually attached to a high level CanvasWidget and receives mouse and keyboard
events via that widget and passes them down through the tree. The root canvas item is also used for sending rendering
drawing commands to the host via the canvas widget.

The root canvas item is a subclass of a special type of canvas item called a layer, which executes layout and 
painting on a thread. The canvas item tree can be configured so that the root canvas item is composed of layers that
draw directly to the canvas widget from their thread; or it can be configured so that the root canvas draws to the 
canvas widget. When comprised of layers, the root canvas item can be split into drawing disjoint areas,
called sections, each in its own thread for performance.

Each layer canvas item also manages a thread for rendering and is responsible for sending drawing commands to the 
CanvasWidget. Layers acting as sections use the CanvasWidget.draw_section method; whereas root canvas item uses the 
CanvasWidget.draw method.

Each canvas item is responsible for maintaining its state, including visibility, sizing preferences, visual properties,
and contents. Each canvas item is also responsible for supplying a composer object representing the canvas item for
layout and drawing.

The composer object represents a snapshot of its canvas item and handles layout and rendering. It is immutable and 
safe to use in threads. Like the canvas items, the composers will be organized into a composer tree that will match 
the hierarchy of the canvas item tree.

When a canvas item needs an update, it will mark itself as needing a new composer and then request a repaint from its 
container. When it moves up the tree to a layer container, it will trigger a repaint on the layer's thread. The 
thread will ask for its layer's composer, layout the composer, and paint the composer. When the painting is finished, 
the thread will send the drawing commands to the CanvasWidget.

An update can be triggered by layout changes, sizing preference changes, property changes, content changes, and more.

Layout occurs on a thread using composers. However, sometimes the canvas item needs to know about its layout,
such as for hit testing. So whenever the layout is painted, the painting thread will inform the canvas item of its
latest position and size via the _update_layout_from_composer method.

CANVAS ITEMS

- AbstractCanvasItem
- CanvasItemComposition (see COMPOSITE CANVAS ITEMS and LAYOUTS below)
- DrawingContextCanvasItem
- SliderCanvasItem
- ScrollBarCanvasItem
- BackgroundCanvasItem
- CellCanvasItem (see CELL STYLE CANVAS ITEMS below)
- CheckBoxCanvasItem
- EmptyCanvasItem
- DrawCanvasItem
- DividerCanvasItem
- ProgressBarCanvasItem
- TimestampCanvasItem

COMPOSITE CANVAS ITEMS

- LayerCanvasItem
- RootCanvasItem (special type of LayerCanvasItem)
- ScrollAreaCanvasItem
- SplitterCanvasItem

LAYOUTS

- CanvasItemAbstractLayout
- CanvasItemLayout (overlapping)
- CanvasItemColumnLayout, CanvasItemRowLayout
- CanvasItemGridLayout
- CanvasItemScrollAreaLayout (used only for ScrollAreaCanvasItem)
- CanvasItemSplitterLayout (used only for SplitterCanvasItem)

CELL STYLE CANVAS ITEMS

- TextCanvasItem
- TwistDownCanvasItem
- BitmapCanvasItem
- StaticTextCanvasItem

GLOSSARY

"widget" is a high level UI element supplied by the host application.

"canvas item" is a low level UI element supplied by the UI library.

"composer" is an immutable object representing a canvas item for layout and drawing.

"layout" is the process of determining the size and position of each canvas item in the tree.

"painting" is the process of creating a list of drawing commands representing the canvas items.

"rendering" is the process of turning the drawing commands into a bitmap.

"blitting" is the process of copying the bitmap to the screen.

"""
from __future__ import annotations

# standard libraries
import abc
import concurrent.futures
import contextlib
import copy
import dataclasses
import datetime
import enum
import functools
import imageio.v3 as imageio
import logging
import operator
import random
import sys
import threading
import time
import types
import typing
import warnings
import weakref

# third party libraries
import numpy

# local libraries
from nion.ui import Bitmap
from nion.ui import DrawingContext
from nion.utils import Color
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import Observable
from nion.utils import Process
from nion.utils import ReferenceCounting
from nion.utils import Stream

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface
    from nion.ui import MouseTrackingCanvasItem


MAX_VALUE = sys.maxsize

class Orientation(enum.Enum):
    Vertical = 0
    Horizontal = 1


class Constraint:

    """ A constraint on an item in a layout. Preferred is only used when free sizing. """

    def __init__(self) -> None:
        self.minimum: typing.Optional[int] = None
        self.maximum: typing.Optional[int] = None
        self.preferred: typing.Optional[int] = None

    def __repr__(self) -> str:
        return "Constraint (min={0}, max={1}, pref={2})".format(self.minimum, self.maximum, self.preferred)


class SolverItem:
    def __init__(self, constraint: Constraint) -> None:
        self.constraint = constraint
        self.size: typing.Optional[int] = None
        self.is_constrained = False


@dataclasses.dataclass
class ConstraintResultType:
    origins: typing.List[int]
    sizes: typing.List[int]


def constraint_solve(canvas_origin: int, canvas_size: int, canvas_item_constraints: typing.Sequence[Constraint], spacing: int = 0) -> ConstraintResultType:
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
            assert solver_item.constraint.minimum is not None
            assert solver_item.constraint.maximum is not None
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
                assert solver_item.constraint.minimum is not None
                assert solver_item.constraint.maximum is not None
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
        actual_canvas_size = sum([(solver_item.size or 0) for solver_item in solver_items])
        assert actual_canvas_size is not None
        if actual_canvas_size > canvas_size:
            remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
            remaining_canvas_size = actual_canvas_size - canvas_size
            if remaining_count > 0:
                for solver_item in solver_items:
                    if not solver_item.is_constrained:
                        assert solver_item.size is not None
                        assert solver_item.constraint.minimum is not None
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
        actual_canvas_size = sum([(solver_item.size or 0) for solver_item in solver_items])
        assert actual_canvas_size is not None
        if actual_canvas_size < canvas_size:
            remaining_count = sum([not solver_item.is_constrained for solver_item in solver_items])
            remaining_canvas_size = canvas_size - actual_canvas_size
            if remaining_count > 0:
                for solver_item in solver_items:
                    if not solver_item.is_constrained:
                        assert solver_item.size is not None
                        assert solver_item.constraint.maximum is not None
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
    sizes = [(solver_item.size or 0) for solver_item in solver_items]
    origins = list()
    for index in range(len(canvas_item_constraints)):
        origins.append(canvas_origin)
        canvas_origin += sizes[index] + spacing

    return ConstraintResultType(origins, sizes)


class SizingEnum(enum.Enum):
    UNRESTRAINED = 0


SizingSpecifierType = int | float | SizingEnum | None


@dataclasses.dataclass
class SizingData:
    preferred_width: SizingSpecifierType = None
    preferred_height: SizingSpecifierType = None
    preferred_aspect_ratio: typing.Optional[float] = None
    minimum_width: SizingSpecifierType = None
    minimum_height: SizingSpecifierType = None
    minimum_aspect_ratio: typing.Optional[float] = None
    maximum_width: SizingSpecifierType = None
    maximum_height: SizingSpecifierType = None
    maximum_aspect_ratio: typing.Optional[float] = None
    collapsible: bool = False


class Sizing:

    """
        Describes the sizing for a particular canvas item.

        Aspect ratio, width, and height can each specify minimums, maximums, and preferred values.

        Width and height can be integer or floats. If floats, they specify a percentage of their
        respective maximum.

        Preferred values are only used when free sizing.

        Collapsible items collapse to fixed size of 0 if they don't have children.
    """

    def __init__(self, sizing_data: SizingData) -> None:
        self.__sizing_data = sizing_data

    def __repr__(self) -> str:
        format_str = "Sizing (min_w={0}, max_w={1}, pref_w={2}, min_h={3}, max_h={4}, pref_h={5}, min_a={6}, max_a={7}, pref_a={8}, collapsible={9})"
        return format_str.format(self.minimum_width, self.maximum_width, self.preferred_width,
                                 self.minimum_height, self.maximum_height, self.preferred_height,
                                 self.minimum_aspect_ratio, self.maximum_aspect_ratio, self.preferred_aspect_ratio,
                                 self.collapsible)

    def __eq__(self, other: typing.Any) -> bool:
        return isinstance(other, Sizing) and other.sizing_data == self.sizing_data

    def __deepcopy__(self, memo: typing.Dict[typing.Any, typing.Any]) -> Sizing:
        deepcopy = Sizing(self.sizing_data)
        memo[id(self)] = deepcopy
        return deepcopy

    @property
    def sizing_data(self) -> SizingData:
        return copy.copy(self.__sizing_data)

    @property
    def preferred_width(self) -> SizingSpecifierType:
        return self.__sizing_data.preferred_width

    @property
    def preferred_width_int(self) -> int:
        return round(self.__sizing_data.preferred_width) if isinstance(self.__sizing_data.preferred_width, (int, float)) else 0

    @property
    def preferred_height(self) -> SizingSpecifierType:
        return self.__sizing_data.preferred_height

    @property
    def preferred_height_int(self) -> int:
        return round(self.__sizing_data.preferred_height) if isinstance(self.__sizing_data.preferred_height, (int, float)) else 0

    @property
    def preferred_aspect_ratio(self) -> typing.Optional[float]:
        return self.__sizing_data.preferred_aspect_ratio

    @property
    def minimum_width(self) -> SizingSpecifierType:
        return self.__sizing_data.minimum_width

    @property
    def minimum_height(self) -> SizingSpecifierType:
        return self.__sizing_data.minimum_height

    @property
    def minimum_aspect_ratio(self) -> typing.Optional[float]:
        return self.__sizing_data.minimum_aspect_ratio

    @property
    def maximum_width(self) -> SizingSpecifierType:
        return self.__sizing_data.maximum_width

    @property
    def maximum_height(self) -> SizingSpecifierType:
        return self.__sizing_data.maximum_height

    @property
    def maximum_aspect_ratio(self) -> typing.Optional[float]:
        return self.__sizing_data.maximum_aspect_ratio

    @property
    def collapsible(self) -> bool:
        return self.__sizing_data.collapsible

    def with_preferred_width(self, width: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_width = width
        return Sizing(sizing_data)

    def with_preferred_height(self, height: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_height = height
        return Sizing(sizing_data)

    def with_preferred_aspect_ratio(self, aspect_ratio: typing.Optional[float]) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_aspect_ratio = aspect_ratio
        return Sizing(sizing_data)

    def with_minimum_width(self, width: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.minimum_width = width
        return Sizing(sizing_data)

    def with_minimum_height(self, height: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.minimum_height = height
        return Sizing(sizing_data)

    def with_minimum_aspect_ratio(self, aspect_ratio: typing.Optional[float]) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.minimum_aspect_ratio = aspect_ratio
        return Sizing(sizing_data)

    def with_maximum_width(self, width: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.maximum_width = width
        return Sizing(sizing_data)

    def with_maximum_height(self, height: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.maximum_height = height
        return Sizing(sizing_data)

    def with_maximum_aspect_ratio(self, aspect_ratio: typing.Optional[float]) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.maximum_aspect_ratio = aspect_ratio
        return Sizing(sizing_data)

    def with_collapsible(self, collapsible: bool) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.collapsible = collapsible
        return Sizing(sizing_data)

    def with_unconstrained_height(self) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_height = None
        sizing_data.minimum_height = None
        sizing_data.maximum_height = None
        return Sizing(sizing_data)

    def with_unconstrained_width(self) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_width = None
        sizing_data.minimum_width = None
        sizing_data.maximum_width = None
        return Sizing(sizing_data)

    def with_fixed_height(self, height: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_height = height
        sizing_data.minimum_height = height
        sizing_data.maximum_height = height
        return Sizing(sizing_data)

    def with_fixed_width(self, width: SizingSpecifierType) -> Sizing:
        sizing_data = self.sizing_data
        sizing_data.preferred_width = width
        sizing_data.minimum_width = width
        sizing_data.maximum_width = width
        return Sizing(sizing_data)

    def with_fixed_size(self, size: Geometry.IntSizeTuple) -> Sizing:
        size_ = Geometry.IntSize.make(size)
        sizing_data = self.sizing_data
        sizing_data.preferred_width = size_.width
        sizing_data.minimum_width = size_.width
        sizing_data.maximum_width = size_.width
        sizing_data.preferred_height = size_.height
        sizing_data.minimum_height = size_.height
        sizing_data.maximum_height = size_.height
        return Sizing(sizing_data)

    def get_width_constraint(self, width: typing.Union[int, float]) -> Constraint:
        """ Create and return a new width Constraint object made from this sizing object. """
        constraint = Constraint()
        if self.minimum_width is not None and not isinstance(self.minimum_width, SizingEnum):
            if isinstance(self.minimum_width, float) and self.minimum_width <= 1.0:
                constraint.minimum = int(width * self.minimum_width)
            else:
                constraint.minimum = int(self.minimum_width)
        else:
            constraint.minimum = 0
        if self.maximum_width is not None and not isinstance(self.maximum_width, SizingEnum):
            if isinstance(self.maximum_width, float) and self.maximum_width <= 1.0:
                constraint.maximum = int(width * self.maximum_width)
            else:
                constraint.maximum = int(self.maximum_width)
        else:
            constraint.maximum = MAX_VALUE
        if self.preferred_width is not None and not isinstance(self.preferred_width, SizingEnum):
            if isinstance(self.preferred_width, float) and self.preferred_width <= 1.0:
                constraint.preferred = int(width * self.preferred_width)
            else:
                constraint.preferred = int(self.preferred_width)
        else:
            constraint.preferred = None
        return constraint

    def get_height_constraint(self, height: typing.Union[int, float]) -> Constraint:
        """ Create and return a new height Constraint object made from this sizing object. """
        constraint = Constraint()
        if self.minimum_height is not None and not isinstance(self.minimum_height, SizingEnum):
            if isinstance(self.minimum_height, float) and self.minimum_height <= 1.0:
                constraint.minimum = int(height * self.minimum_height)
            else:
                constraint.minimum = int(self.minimum_height)
        else:
            constraint.minimum = 0
        if self.maximum_height is not None and not isinstance(self.maximum_height, SizingEnum):
            if isinstance(self.maximum_height, float) and self.maximum_height <= 1.0:
                constraint.maximum = int(height * self.maximum_height)
            else:
                constraint.maximum = int(self.maximum_height)
        else:
            constraint.maximum = MAX_VALUE
        if self.preferred_height is not None and not isinstance(self.preferred_height, SizingEnum):
            if isinstance(self.preferred_height, float) and self.preferred_height <= 1.0:
                constraint.preferred = int(height * self.preferred_height)
            else:
                constraint.preferred = int(self.preferred_height)
        else:
            constraint.preferred = None
        return constraint

    def get_unrestrained_width(self, maximum_width: typing.Union[int, float]) -> int:
        if self.maximum_width is not None and not isinstance(self.maximum_width, SizingEnum):
            if isinstance(self.maximum_width, float) and self.maximum_width < 1.0:
                return int(self.maximum_width * maximum_width)
            return int(min(self.maximum_width, maximum_width))
        return int(maximum_width)

    def get_unrestrained_height(self, maximum_height: typing.Union[int, float]) -> int:
        if self.maximum_height is not None and not isinstance(self.maximum_height, SizingEnum):
            if isinstance(self.maximum_height, float) and self.maximum_height < 1.0:
                return int(self.maximum_height * maximum_height)
            return int(min(self.maximum_height, maximum_height))
        return int(maximum_height)

    def get_preferred_width(self) -> typing.Union[int, float]:
        if self.preferred_width:
            return self.preferred_width if not isinstance(self.preferred_width, SizingEnum) else 0
        if self.maximum_width:
            return self.maximum_width if not isinstance(self.maximum_width, SizingEnum) else 0
        if self.minimum_width:
            return self.minimum_width if not isinstance(self.minimum_width, SizingEnum) else 0
        return 0

    def get_preferred_height(self) -> typing.Union[int, float]:
        if self.preferred_height:
            return self.preferred_height if not isinstance(self.preferred_height, SizingEnum) else 0
        if self.maximum_height:
            return self.maximum_height if not isinstance(self.maximum_height, SizingEnum) else 0
        if self.minimum_height:
            return self.minimum_height if not isinstance(self.minimum_height, SizingEnum) else 0
        return 0

    def get_preferred_size(self) -> Geometry.IntSize:
        return Geometry.IntSize(int(self.get_preferred_height()), int(self.get_preferred_width()))


class KeyboardModifiers:
    def __init__(self, shift: bool = False, control: bool = False, alt: bool = False, meta: bool = False, keypad: bool = False) -> None:
        self.__shift = shift
        self.__control = control
        self.__alt = alt
        self.__meta = meta
        self.__keypad = keypad

    @property
    def any_modifier(self) -> bool:
        return self.shift or self.control or self.alt or self.meta

    # shift
    @property
    def shift(self) -> bool:
        return self.__shift

    @property
    def only_shift(self) -> bool:
        return self.__shift and not self.__control and not self.__alt and not self.__meta

    # control (command key on mac)
    @property
    def control(self) -> bool:
        return self.__control

    @property
    def only_control(self) -> bool:
        return self.__control and not self.__shift and not self.__alt and not self.__meta

    # alt (option key on mac)
    @property
    def alt(self) -> bool:
        return self.__alt

    @property
    def only_alt(self) -> bool:
        return self.__alt and not self.__control and not self.__shift and not self.__meta

    # option (alt key on windows)
    @property
    def option(self) -> bool:
        return self.__alt

    @property
    def only_option(self) -> bool:
        return self.__alt and not self.__control and not self.__shift and not self.__meta

    # meta (control key on mac)
    @property
    def meta(self) -> bool:
        return self.__meta

    @property
    def only_meta(self) -> bool:
        return self.__meta and not self.__control and not self.__shift and not self.__alt

    # keypad
    @property
    def keypad(self) -> bool:
        return self.__keypad

    @property
    def only_keypad(self) -> bool:
        return self.__keypad

    @property
    def native_control(self) -> bool:
        return self.control


def visible_layout_sizing_item(canvas_item: typing.Optional[LayoutSizingItem]) -> typing.Optional[LayoutSizingItem]:
    return canvas_item if canvas_item and canvas_item.is_visible else None


def visible_layout_item(canvas_item: typing.Optional[LayoutItem]) -> typing.Optional[LayoutItem]:
    return canvas_item if canvas_item and canvas_item.is_visible else None


class ComposerCacheItem(typing.Protocol):
    def key(self) -> typing.Any: ...
    def calculate(self) -> typing.Any: ...


@dataclasses.dataclass(frozen=True)
class CacheValue:
    value: typing.Any


class ComposerCache:
    def __init__(self) -> None:
        self.__cache = dict[typing.Any, weakref.ReferenceType[CacheValue]]()

    def get_cache_value(self, cache_item: ComposerCacheItem) -> CacheValue:
        cache_item_key = cache_item.key()
        cache_value_ref = self.__cache.get(cache_item_key)
        cache_value = cache_value_ref() if cache_value_ref else None
        if cache_value is None:
            value = cache_item.calculate()
            cache_value = CacheValue(value)
            self.__cache[cache_item_key] = weakref.ref(cache_value)

            def finalize(cache: dict[typing.Any, weakref.ReferenceType[CacheValue]], cache_item_key: typing.Any) -> None:
                cache.pop(cache_item_key, None)

            weakref.finalize(cache_value, finalize, self.__cache, cache_item_key)
        return cache_value


class BaseComposer:
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache) -> None:
        self.__canvas_item_ref = weakref.ref(canvas_item)
        self.__layout_sizing = layout_sizing
        self.__drawing_context: typing.Optional[DrawingContext.DrawingContext] = None
        self.__actual_visible_rect: typing.Optional[Geometry.IntRect] = None
        self.__canvas_bounds: typing.Optional[Geometry.IntRect] = None
        self.__cache = cache

    def repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect) -> None:
        # if layout is changed, update it. it may clear the drawing context.
        self.update_layout(canvas_rect.origin, canvas_rect.size)
        actual_visible_rect = visible_rect.intersect(canvas_rect)
        existing_draw_context = self.__drawing_context
        if not existing_draw_context or self.__actual_visible_rect != actual_visible_rect:
            existing_draw_context = DrawingContext.DrawingContext()
            try:
                self._repaint_visible(existing_draw_context, canvas_rect, visible_rect, self.__cache)
                self._draw_unique_marker(existing_draw_context, canvas_rect)
            except Exception as e:
                logging.exception(f"Error in composer repaint {type(self)} {e}")
            self._update_repaint_count()
        drawing_context.add(existing_draw_context)
        self.__drawing_context = existing_draw_context
        self.__actual_visible_rect = actual_visible_rect

    def _update_repaint_count(self) -> None:
        # this is overridable to allow class DrawingContextCanvasItemComposer to accurately update the repaint count.
        canvas_item = self.__canvas_item_ref()
        if canvas_item:
            canvas_item._update_repaint_count_from_composer()

    # used for debugging
    def _draw_unique_marker(self, drawing_context: DrawingContext.DrawingContext, canvas_bounds: Geometry.IntRect) -> None:
        MARKER_SIZE: typing.Final[int] = 3
        canvas_item = self.__canvas_item_ref()
        draw_unique_marker = (canvas_item and canvas_item._draw_unique_marker) or _g_draw_unique_marker
        if draw_unique_marker and canvas_bounds.width > MARKER_SIZE * 2 and canvas_bounds.height > MARKER_SIZE * 2:
            colors = list(Color.svg_color_map.values())
            for oy in (0, MARKER_SIZE):
                for ox in (0, MARKER_SIZE):
                    with drawing_context.saver():
                        drawing_context.begin_path()
                        drawing_context.rect(ox, oy, MARKER_SIZE, MARKER_SIZE)
                        drawing_context.fill_style = random.choice(colors)
                        drawing_context.fill()

    @property
    def _canvas_item(self) -> AbstractCanvasItem:
        canvas_item = self.__canvas_item_ref()
        assert canvas_item
        return canvas_item

    @property
    def _canvas_bounds(self) -> Geometry.IntRect:
        assert self.__canvas_bounds
        return self.__canvas_bounds

    def _repaint_visible(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        self._repaint(drawing_context, canvas_rect, composer_cache)

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        raise NotImplementedError()

    @property
    def is_visible(self) -> bool:
        return True

    @property
    def layout_sizing(self) -> Sizing:
        return self.__layout_sizing

    @property
    def _has_layout(self) -> bool:
        return self.__canvas_bounds is not None

    def update_layout(self, canvas_origin: typing.Optional[Geometry.IntPoint], canvas_size: typing.Optional[Geometry.IntSize]) -> None:
        canvas_bounds = Geometry.IntRect(canvas_origin or (0, 0), canvas_size or (0, 0))
        canvas_bounds = self._adjust_canvas_bounds(canvas_bounds)
        if self.__canvas_bounds != canvas_bounds:
            self.__canvas_bounds = canvas_bounds
            self.__drawing_context = None
            self._update_layout(canvas_bounds)
        canvas_item = self.__canvas_item_ref()
        if canvas_item:
            canvas_item._update_layout_from_composer(canvas_bounds)

    def _adjust_canvas_bounds(self, canvas_bounds: Geometry.IntRect) -> Geometry.IntRect:
        return canvas_bounds

    def _update_layout(self, canvas_bounds: Geometry.IntRect) -> None:
        pass


_g_draw_unique_marker = False


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
    """

    def __init__(self, cache: typing.Optional[ComposerCache] = None) -> None:
        super().__init__()
        self.__composer_lock = threading.RLock()
        self.__composer: typing.Optional[BaseComposer] = None
        self.__cache = cache or ComposerCache()
        self.__container: typing.Optional[CanvasItemComposition] = None
        self._canvas_size_stream = Stream.ValueStream[Geometry.IntSize]()
        self._canvas_origin_stream = Stream.ValueStream[Geometry.IntPoint]()
        self.__sizing = Sizing(SizingData())
        self.__layout_count = 0
        self.__focused = False
        self.__focusable = False
        self.wants_mouse_events = False
        self.wants_drag_events = False
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.__cursor_shape: typing.Optional[str] = None
        self.__tool_tip: typing.Optional[str] = None
        self.__background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None
        self.__border_color: typing.Optional[str] = None
        self.__visible = True
        self.__enabled = True
        self.__thread = threading.current_thread()
        self.__update_lock = threading.RLock()
        self.__update_level = 0  # used for deferred updating
        # stats for testing
        self._update_count = 0
        self._repaint_count = 0
        self._layout_count = 0
        self.is_root_opaque = False
        self._draw_unique_marker = False

    def close(self) -> None:
        """ Close the canvas object. """
        if threading.current_thread() != self.__thread:
            warnings.warn('CanvasItem closed on different thread')
            import traceback
            traceback.print_stack()
        self.__container = None
        self.on_focus_changed = None

    def _description(self) -> str:
        return self.__class__.__name__

    def _summary(self, indent: typing.Optional[str] = None) -> str:
        indent = indent or str()
        return indent + self._description() + f"+0x{id(self):x}" + " [" + str(self.canvas_rect) + "]" + " (" + str(self.sizing) + ")"

    def __repr__(self) -> str:
        return self._summary()

    def _set_owner_thread(self, thread: threading.Thread) -> None:
        self.__thread = thread
        for canvas_item in self.canvas_items:
            canvas_item._set_owner_thread(thread)

    @property
    def canvas_items(self) -> typing.List[AbstractCanvasItem]:
        """ Returns a list of all canvas items in the hierarchy. """
        return list()

    @property
    def is_ui_interaction_active(self) -> bool:
        root_container = self.root_container
        if root_container:
            return root_container.is_ui_interaction_active
        return False

    @property
    def canvas_size(self) -> typing.Optional[Geometry.IntSize]:
        """ Returns size of canvas_rect (external coordinates). """
        return self._canvas_size_stream.value

    def _set_canvas_size(self, canvas_size: typing.Optional[Geometry.IntSizeTuple]) -> None:
        old_canvas_size_ = self._canvas_size_stream.value
        canvas_size_ = Geometry.IntSize.make(canvas_size) if canvas_size is not None else None
        if ((old_canvas_size_ is None) != (canvas_size_ is None)) or (old_canvas_size_ != canvas_size_):
            self._canvas_size_stream.value = canvas_size_
            self.update()

    @property
    def canvas_origin(self) -> typing.Optional[Geometry.IntPoint]:
        """ Returns origin of canvas_rect (external coordinates). """
        return self._canvas_origin_stream.value

    def _set_canvas_origin(self, canvas_origin: typing.Optional[Geometry.IntPointTuple]) -> None:
        old_canvas_origin_ = self._canvas_origin_stream.value
        canvas_origin_ = Geometry.IntPoint.make(canvas_origin) if canvas_origin is not None else None
        if ((old_canvas_origin_ is None) != (canvas_origin_ is None)) or (old_canvas_origin_ != canvas_origin_):
            self._canvas_origin_stream.value = canvas_origin_
            self.update()

    @property
    def _has_layout(self) -> bool:
        return self.canvas_origin is not None and self.canvas_size is not None

    @property
    def canvas_widget(self) -> typing.Optional[UserInterface.CanvasWidget]:
        return self.container.canvas_widget if self.container else None

    @property
    def canvas_bounds(self) -> typing.Optional[Geometry.IntRect]:
        """ Returns a rect of the internal coordinates. """
        if self.canvas_size is not None:
            return Geometry.IntRect((0, 0), self.canvas_size)
        return None

    @property
    def canvas_rect(self) -> typing.Optional[Geometry.IntRect]:
        """ Returns a rect of the external coordinates. """
        if self.canvas_origin is not None and self.canvas_size is not None:
            return Geometry.IntRect(self.canvas_origin, self.canvas_size)
        return None

    @property
    def container(self) -> typing.Optional[CanvasItemComposition]:
        """ Return the container, if any. """
        return self.__container

    @container.setter
    def container(self, container: typing.Optional[CanvasItemComposition]) -> None:
        """ Set container. """
        assert self.__container is None or container is None
        self.__container = container

    @property
    def root_container(self) -> typing.Optional[RootCanvasItem]:
        """ Return the root container, if any. """
        return self.__container.root_container if self.__container else None

    @property
    def background_color(self) -> typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]:
        return self.__background_color

    @background_color.setter
    def background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.__background_color = background_color
        self.update()

    @property
    def border_color(self) -> typing.Optional[str]:
        return self.__border_color

    @border_color.setter
    def border_color(self, border_color: typing.Optional[str]) -> None:
        self.__border_color = border_color
        self.update()

    @property
    def focusable(self) -> bool:
        """ Return whether the canvas item is focusable. """
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        """
            Set whether the canvas item is focusable.

            If this canvas item is focusable and contains other canvas items, they should
            not be focusable.
        """
        self.__focusable = focusable

    @property
    def focused(self) -> bool:
        """ Return whether the canvas item is focused. """
        return self.__focused

    def _set_focused(self, focused: bool) -> None:
        """ Set whether the canvas item is focused. Only called from container. """
        if focused != self.__focused:
            self.__focused = focused
            self.update()
            if callable(self.on_focus_changed):
                self.on_focus_changed(focused)

    def _request_focus(self, p: typing.Optional[Geometry.IntPoint] = None,
                       modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        # protected method
        if not self.focused:
            root_container = self.root_container
            if root_container:
                root_container._request_root_focus(self, p, modifiers)

    def request_focus(self) -> None:
        """Request focus.

        Subclasses should not override. Override _request_focus instead."""
        self._request_focus()

    def adjust_secondary_focus(self, p: Geometry.IntPoint, modifiers: UserInterface.KeyboardModifiers) -> None:
        """Adjust secondary focus. Default does nothing."""
        pass

    def clear_focus(self) -> None:
        """ Relinquish focus. """
        if self.focused:
            root_container = self.root_container
            if root_container:
                root_container._set_focused_item(None)

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[Bitmap.BitmapOrArray] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        root_container = self.root_container
        if root_container:
            root_container.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        root_container = self.root_container
        if root_container:
            root_container.show_tool_tip_text(text, gx, gy)

    @property
    def tool_tip(self) -> typing.Optional[str]:
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, value: typing.Optional[str]) -> None:
        self.__tool_tip = value
        # clear the tool tip when setting to None. this will happen whenever the mouse exits any item, whether it has
        # a tool tip or not. this may need refinement in the future.
        if value is None:
            root_container = self.root_container
            if root_container:
                root_container.hide_tool_tip_text()

    @property
    def cursor_shape(self) -> typing.Optional[str]:
        return self.__cursor_shape

    @cursor_shape.setter
    def cursor_shape(self, cursor_shape: typing.Optional[str]) -> None:
        self.__cursor_shape = cursor_shape
        root_container = self.root_container
        if root_container:
            root_container._cursor_shape_changed(self)

    def map_to_canvas_item(self, p: Geometry.IntPointTuple, canvas_item: AbstractCanvasItem) -> Geometry.IntPoint:
        """ Map the point to the local coordinates of canvas_item. """
        o1 = self.map_to_root_container(Geometry.IntPoint())
        o2 = canvas_item.map_to_root_container(Geometry.IntPoint())
        return Geometry.IntPoint.make(p) + o1 - o2

    def map_to_root_container(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        """ Map the point to the coordinates of the root container. """
        canvas_item: typing.Optional[AbstractCanvasItem] = self
        while canvas_item:  # handle case where last canvas item was root
            canvas_item_origin = canvas_item.canvas_origin
            if canvas_item_origin is not None:  # handle case where canvas item is not root but has no parent
                p = canvas_item.map_to_container(p)
                canvas_item = canvas_item.container
            else:
                break
        return p

    def map_to_container(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        """ Map the point to the coordinates of the container. """
        canvas_origin = self.canvas_origin
        assert canvas_origin
        return p + canvas_origin

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        root_container = self.root_container
        assert root_container
        return root_container.map_to_global(self.map_to_root_container(p))

    def _inserted(self, container: typing.Optional[AbstractCanvasItem]) -> None:
        """Subclasses may override to know when inserted into a container."""
        pass

    def _removed(self, container: typing.Optional[AbstractCanvasItem]) -> None:
        """Subclasses may override to know when removed from a container."""
        pass

    def update_layout(self, canvas_origin: typing.Optional[Geometry.IntPoint], canvas_size: typing.Optional[Geometry.IntSize]) -> None:
        """Update the layout with a new canvas_origin and canvas_size. Update child layouts, too.

        canvas_origin and canvas_size are the external bounds.

        The canvas_origin and canvas_size properties are valid after calling this method and _has_layout is True.
        """
        # TEST ONLY
        self.update_layout_using_composer(Geometry.IntRect(canvas_origin or (0, 0), canvas_size or (0, 0)))

    def update_layout_immediate(self, canvas_origin: typing.Optional[Geometry.IntPoint], canvas_size: typing.Optional[Geometry.IntSize]) -> None:
        """Update the layout with a new canvas_origin and canvas_size. Update child layouts, too.

        canvas_origin and canvas_size are the external bounds.

        The canvas_origin and canvas_size properties are valid after calling this method and _has_layout is True.
        """
        # TEST ONLY
        self.update_layout_using_composer_immediate(Geometry.IntRect(canvas_origin or (0, 0), canvas_size or (0, 0)))

    def refresh_layout_immediate(self) -> None:
        """Immediate re-layout the item. Deprecated. Use refresh_layout instead."""
        # TEST ONLY
        canvas_rect = self.canvas_rect
        assert canvas_rect
        self.update_layout_using_composer_immediate(canvas_rect)

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if self.__visible != value:
            self.__visible = value
            self.update()
            # the regular update path will only invalidate the composer and call _updated
            # if the item is visible. if we just set it to not visible, we need to call it
            # here to get things to update properly. hack. one place where this would show
            # up is in the line plot legend being set between none and top-right.
            if not self.__visible:
                self._invalidate_composer()
                self._updated()

    @property
    def is_visible(self) -> bool:
        return self.__visible

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if self.__enabled != value:
            self.__enabled = value
            self.update()

    @property
    def sizing(self) -> Sizing:
        """
            Return sizing information for this canvas item.

            The sizing property is read only, but the object itself
            can be modified.
        """
        return self.__sizing

    @property
    def layout_sizing(self) -> Sizing:
        """
            Return layout sizing information for this canvas item.

            The layout sizing is read only and cannot be modified. It is
            used from the layout engine.
        """
        return self.sizing

    def copy_sizing(self) -> Sizing:
        return self.sizing

    def update_sizing(self, new_sizing: Sizing) -> None:
        if new_sizing != self.sizing:
            self.__sizing = new_sizing
            self.update()

    def _begin_batch_update(self) -> None:
        with self.__update_lock:
            self.__update_level += 1

    def _end_batch_update(self) -> None:
        with self.__update_lock:
            self.__update_level -= 1
            if self.__update_level == 0:
                self._batch_update_ended()
                self._update()

    def _batch_update_ended(self) -> None:
        pass

    @contextlib.contextmanager
    def batch_update(self) -> typing.Iterator[typing.Any]:
        self._begin_batch_update()
        try:
            yield
        finally:
           self._end_batch_update()

    def _update(self) -> None:
        """Mark canvas item as needing a display update.

        Thread-safe.

        The canvas item will be repainted by the root canvas item.
        """
        if self.is_visible:
            self._update_count += 1
            self._invalidate_composer()
            self._updated()

    def update(self) -> None:
        with self.batch_update():
            pass

    def redraw(self) -> None:
        """Force full redraw of this item and children. Used for resolution changes."""
        for canvas_item in self.canvas_items:
            canvas_item.redraw()
        self._redraw()

    def _redraw(self) -> None:
        """Force full redraw of this item. Used for resolution changes. Subclasses may override."""
        self.update()

    def _updated(self) -> None:
        # Notify this canvas item that a child has been updated, repaint if needed at next opportunity.
        # thread-safe
        if container := self.__container:
            container.update()

    def _get_composer_cache(self) -> ComposerCache:
        return self.__cache

    def _invalidate_composer(self) -> None:
        # avoid the race condition where the composer gets set in _get_composer_inner immediately after
        # being cleared here and no further updates occur, resulting in an incorrect composer.
        with self.__composer_lock:
            self.__composer = None

    def get_composer(self, cache: ComposerCache) -> typing.Optional[BaseComposer]:
        """Return the composer for this canvas item. Subclasses should not override.

        The layer canvas item is special in that it will not have a composer when called
        from the container. This is because the layer canvas item runs its layout on a thread
        and draws itself directly in the root container. The layer canvas item uses the
        _get_composer_inner function to get its composer when it is ready to draw.
        """
        return self._get_composer_inner(cache)

    def _get_composer_inner(self, cache: ComposerCache) -> typing.Optional[BaseComposer]:
        with self.__composer_lock:
            if not self.__composer:
                self.__composer = self._get_composer(cache)
                # assert self.__composer, f"missing composer for {type(self)}"
        return self.__composer

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return None

    def get_composer_immediate(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return self.get_composer(composer_cache)

    def update_layout_using_composer(self, canvas_rect: Geometry.IntRect) -> None:
        composer = self.get_composer(self._get_composer_cache())
        if composer:
            composer.update_layout(canvas_rect.origin, canvas_rect.size)

    def update_layout_using_composer_immediate(self, canvas_rect: Geometry.IntRect) -> None:
        # TEST ONLY
        composer = self.get_composer_immediate(self._get_composer_cache())
        if composer:
            composer.update_layout(canvas_rect.origin, canvas_rect.size)

    def _repaint(self, drawing_context: DrawingContext.DrawingContext) -> None:
        """Repaint the canvas item to the drawing context.

        Subclasses should override this method to paint. Non-composite canvas items can ignore the visible_rect
        parameter. It is only being used when a composite item is repainting its children.

        This method will be called on a thread.

        The drawing should take place within the canvas_bounds.
        """
        assert self.canvas_size is not None
        composer = self.get_composer(self._get_composer_cache())
        canvas_rect = self.canvas_rect
        if composer and canvas_rect:
            composer.repaint(drawing_context, canvas_rect, canvas_rect)

    def _update_repaint_count_from_composer(self) -> None:
        self._repaint_count += 1

    def _update_layout_from_composer(self, canvas_bounds: Geometry.IntRect) -> None:
        did_layout_change = False
        old_canvas_origin_ = self._canvas_origin_stream.value
        if (old_canvas_origin_ is None) or (old_canvas_origin_ != canvas_bounds.origin):
            self._canvas_origin_stream.value = canvas_bounds.origin
            did_layout_change = True
        old_canvas_size_ = self._canvas_size_stream.value
        if (old_canvas_size_ is None) or (old_canvas_size_ != canvas_bounds.size):
            self._canvas_size_stream.value = canvas_bounds.size
            did_layout_change = True
        self._layout_count += 1 if did_layout_change else 0
        if did_layout_change:
            self._layout_changed()

    def _layout_changed(self) -> None:
        pass

    def _draw_background(self, drawing_context: DrawingContext.DrawingContext) -> None:
        """Draw the background. Subclasses can call this."""
        background_color = self.__background_color
        if background_color:
            rect = self.canvas_bounds
            if rect:
                with drawing_context.saver():
                    drawing_context.begin_path()
                    drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                    drawing_context.fill_style = background_color
                    drawing_context.fill()

    def _draw_border(self, drawing_context: DrawingContext.DrawingContext) -> None:
        """Draw the border. Subclasses can call this."""
        border_color = self.__border_color
        if border_color:
            rect = self.canvas_bounds
            if rect:
                with drawing_context.saver():
                    drawing_context.begin_path()
                    drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                    drawing_context.stroke_style = border_color
                    drawing_context.stroke()

    def canvas_item_at_point(self, x: int, y: int) -> typing.Optional[AbstractCanvasItem]:
        canvas_items = self.canvas_items_at_point(x, y)
        return canvas_items[0] if len(canvas_items) > 0 else None

    def canvas_items_at_point(self, x: int, y: int) -> typing.List[AbstractCanvasItem]:
        """ Return the canvas item at the point. May return None. """
        canvas_bounds = self.canvas_bounds
        if canvas_bounds and canvas_bounds.contains_point(Geometry.IntPoint(x=x, y=y)):
            return [self]
        return []

    def get_root_opaque_canvas_items(self) -> typing.List[AbstractCanvasItem]:
        return [self] if self.is_root_opaque else list()

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        """ Handle a mouse click within this canvas item. Return True if handled. """
        return False

    def mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        """ Handle a mouse double click within this canvas item. Return True if handled. """
        return False

    def mouse_entered(self) -> bool:
        """ Handle a mouse entering this canvas item. Return True if handled. """
        return False

    def mouse_exited(self) -> bool:
        """ Handle a mouse exiting this canvas item. Return True if handled. """
        return False

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        """ Handle a mouse press within this canvas item. Return True if handled. """
        return False

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        """ Handle a mouse release within this canvas item. Return True if handled. """
        return False

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        """ Handle a mouse move within this canvas item. Return True if handled. """
        return False

    def wheel_changed(self, x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> bool:
        """ Handle a mouse wheel changed within this canvas item. Return True if handled. """
        return False

    def context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        """ Handle a context menu event. x, y are local coordinates. gx, gy are global coordinates. """
        return False

    def key_pressed(self, key: UserInterface.Key) -> bool:
        """ Handle a key pressed while this canvas item has focus. Return True if handled. """
        return False

    def key_released(self, key: UserInterface.Key) -> bool:
        """ Handle a key released while this canvas item has focus. Return True if handled. """
        return False

    def wants_drag_event(self, mime_data: UserInterface.MimeData, x: int, y: int) -> bool:
        """ Determines if the item should handle certain mime_data at a certain point. Return True if handled."""
        return self.wants_drag_events

    def drag_enter(self, mime_data: UserInterface.MimeData) -> str:
        """ Handle a drag event entering this canvas item. Return action if handled. """
        return "ignore"

    def drag_leave(self) -> str:
        """ Handle a drag event leaving this canvas item. Return action if handled. """
        return "ignore"

    def drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        """ Handle a drag event moving within this canvas item. Return action if handled. """
        return "ignore"

    def drop(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        """ Handle a drop event in this canvas item. Return action if handled. """
        return "ignore"

    def handle_tool_tip(self, x: int, y: int, gx: int, gy: int) -> bool:
        return False

    def pan_gesture(self, dx: int, dy: int) -> bool:
        """ Handle a pan gesture in this canvas item. Return action if handled. """
        return False

    def _dispatch_any(self, method: str, *args: typing.Any, **kwargs: typing.Any) -> bool:
        if hasattr(self, method):
            return typing.cast(bool, getattr(self, method)(*args, **kwargs))
        return False

    def _can_dispatch_any(self, method: str) -> bool:
        return hasattr(self, method)

    def _get_menu_item_state(self, command_id: str) -> typing.Optional[UserInterface.MenuItemState]:
        handle_method = "handle_" + command_id
        menu_item_state_method = "get_" + command_id + "_menu_item_state"
        if hasattr(self, menu_item_state_method):
            menu_item_state = getattr(self, menu_item_state_method)()
            if menu_item_state:
                return typing.cast(UserInterface.MenuItemState, menu_item_state)
        if hasattr(self, handle_method):
            return UserInterface.MenuItemState(title=None, enabled=True, checked=False)
        return None

    def simulate_click(self, p: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers_ = modifiers or typing.cast("UserInterface.KeyboardModifiers", KeyboardModifiers())
        self.mouse_pressed(p[1], p[0], modifiers_)
        self.mouse_released(p[1], p[0], modifiers_)

    def simulate_drag(self, p1: Geometry.IntPointTuple, p2: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers_ = modifiers or typing.cast("UserInterface.KeyboardModifiers", KeyboardModifiers())
        self.mouse_pressed(p1[1], p1[0], modifiers_)
        self.mouse_position_changed(p1[1], p1[0], modifiers_)
        midpoint = Geometry.midpoint(Geometry.IntPoint.make(p1).to_float_point(), Geometry.IntPoint.make(p2).to_float_point())
        self.mouse_position_changed(round(midpoint[1]), round(midpoint[0]), modifiers_)
        self.mouse_position_changed(p2[1], p2[0], modifiers_)
        self.mouse_released(p2[1], p2[0], modifiers_)

    def simulate_press(self, p: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers_ = modifiers or typing.cast("UserInterface.KeyboardModifiers", KeyboardModifiers())
        self.mouse_pressed(p[1], p[0], modifiers_)

    def simulate_move(self, p: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers_ = modifiers or typing.cast("UserInterface.KeyboardModifiers", KeyboardModifiers())
        self.mouse_position_changed(p[1], p[0], modifiers_)

    def simulate_release(self, p: Geometry.IntPointTuple, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        modifiers_ = modifiers or typing.cast("UserInterface.KeyboardModifiers", KeyboardModifiers())
        self.mouse_released(p[1], p[0], modifiers_)


class LayoutItem(typing.Protocol):

    @property
    def is_visible(self) -> bool: raise NotImplementedError()

    @property
    def layout_sizing(self) -> Sizing: raise NotImplementedError()

    @property
    def _has_layout(self) -> bool: raise NotImplementedError()

    def update_layout(self, canvas_origin: typing.Optional[Geometry.IntPoint], canvas_size: typing.Optional[Geometry.IntSize]) -> None: ...


class LayoutSizingItem(typing.Protocol):

    @property
    def is_visible(self) -> bool: raise NotImplementedError()

    @property
    def layout_sizing(self) -> Sizing: raise NotImplementedError()


class CanvasItemAbstractLayout:

    """
        Layout canvas items within a larger space.

        Subclasses must implement layout method.

        NOTE: origin=0 is at the top
    """

    def __init__(self, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None) -> None:
        self.margins = margins if margins is not None else Geometry.Margins(0, 0, 0, 0)
        self.spacing = spacing if spacing else 0

    def copy(self) -> CanvasItemAbstractLayout:
        raise NotImplementedError()

    def calculate_row_layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize,
                             canvas_items: typing.Sequence[LayoutItem]) -> ConstraintResultType:
        """ Use constraint_solve to return the positions of canvas items as if they are in a row. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_width_constraint(content_width) for canvas_item in canvas_items]
        return constraint_solve(content_left, content_width, constraints, self.spacing)

    def calculate_column_layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize,
                                canvas_items: typing.Sequence[LayoutItem]) -> ConstraintResultType:
        """ Use constraint_solve to return the positions of canvas items as if they are in a column. """
        canvas_item_count = len(canvas_items)
        spacing_count = canvas_item_count - 1
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = [canvas_item.layout_sizing.get_height_constraint(content_height) for canvas_item in canvas_items]
        return constraint_solve(content_top, content_height, constraints, self.spacing)

    def update_canvas_item_layout(self, canvas_item_origin: Geometry.IntPoint, canvas_item_size: Geometry.IntSize, canvas_item: LayoutItem) -> None:
        """ Given a container box, adjust a single canvas item within the box according to aspect_ratio constraints. """
        # TODO: Also adjust canvas items for maximums, and positioning
        aspect_ratio = canvas_item_size.aspect_ratio
        rect = Geometry.IntRect(origin=canvas_item_origin, size=canvas_item_size)
        layout_sizing = canvas_item.layout_sizing
        if layout_sizing.minimum_aspect_ratio is not None and aspect_ratio < layout_sizing.minimum_aspect_ratio:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.minimum_aspect_ratio).to_int_rect()
        elif layout_sizing.maximum_aspect_ratio is not None and aspect_ratio > layout_sizing.maximum_aspect_ratio:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.maximum_aspect_ratio).to_int_rect()
        elif layout_sizing.preferred_aspect_ratio is not None:
            rect = Geometry.fit_to_aspect_ratio(rect, layout_sizing.preferred_aspect_ratio).to_int_rect()
        canvas_item.update_layout(rect.origin, rect.size)

    def layout_canvas_items(self, x_positions: typing.Sequence[int], y_positions: typing.Sequence[int],
                            widths: typing.Sequence[int], heights: typing.Sequence[int],
                            canvas_items: typing.Sequence[LayoutItem]) -> None:
        """ Set the container boxes for the canvas items using update_canvas_item_layout on the individual items. """
        for index, canvas_item in enumerate(canvas_items):
            if canvas_item is not None:
                canvas_item_origin = Geometry.IntPoint(x=x_positions[index], y=y_positions[index])
                canvas_item_size = Geometry.IntSize(width=widths[index], height=heights[index])
                self.update_canvas_item_layout(canvas_item_origin, canvas_item_size, canvas_item)

    def _combine_sizing_property(self, sizing_data: SizingData, canvas_item_sizing: Sizing, property: str,
                                 combiner: typing.Callable[[typing.Any, typing.Any], typing.Any],
                                 clear_if_missing: bool = False) -> None:
        """ Utility method for updating the property of the sizing object using the combiner function and the canvas_item_sizing. """
        canvas_item_value = getattr(canvas_item_sizing, property)
        value = getattr(sizing_data, property)
        if canvas_item_value is not None:
            if clear_if_missing:
                setattr(sizing_data, property, combiner(value, canvas_item_value) if value is not None else None)
            else:
                setattr(sizing_data, property, combiner(value, canvas_item_value) if value is not None else canvas_item_value)
        elif clear_if_missing:
            setattr(sizing_data, property, None)

    def _get_overlap_sizing(self, canvas_items: typing.Sequence[typing.Optional[LayoutSizingItem]]) -> Sizing:
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is stacked/overlapping.
            Does not include spacing or margins.
        """
        sizing_data = SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_width = 0
        sizing_data.preferred_height = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_width", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_height", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_width", max)  # if any minimum_width is present, take the maximum one
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_height", max)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_width", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_height", max, True)
        if sizing_data.maximum_width == 0 or len(canvas_items) == 0:
            sizing_data.maximum_width = None
        if sizing_data.maximum_height == 0 or len(canvas_items) == 0:
            sizing_data.maximum_height = None
        if sizing_data.preferred_width == 0 or len(canvas_items) == 0:
            sizing_data.preferred_width = None
        if sizing_data.preferred_height == 0 or len(canvas_items) == 0:
            sizing_data.preferred_height = None
        return Sizing(sizing_data)

    def _get_column_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem])-> Sizing:
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is a column.
            Does not include spacing or margins.
        """
        sizing_data = SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_width = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_width", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_height", operator.add)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_width", max)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_height", operator.add)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_width", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_height", operator.add, True)
        if sizing_data.maximum_width == 0 or len(canvas_items) == 0:
            sizing_data.maximum_width = None
        if sizing_data.preferred_width == 0 or len(canvas_items) == 0:
            sizing_data.preferred_width = None
        if sizing_data.maximum_height == MAX_VALUE or len(canvas_items) == 0:
            sizing_data.maximum_height = None
        return Sizing(sizing_data)

    def _get_row_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        """
            A commonly used sizing method to determine the preferred/min/max assuming everything is a column.
            Does not include spacing or margins.
        """
        sizing_data = SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_height = 0
        for canvas_item in canvas_items:
            if canvas_item is not None:
                canvas_item_sizing = canvas_item.layout_sizing
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_width", operator.add)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_height", max, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_width", operator.add)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_height", max)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_width", operator.add, True)
                self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_height", max, True)
        if sizing_data.maximum_width == MAX_VALUE or len(canvas_items) == 0:
            sizing_data.maximum_width = None
        if sizing_data.maximum_height == 0 or len(canvas_items) == 0:
            sizing_data.maximum_height = None
        if sizing_data.preferred_height == 0 or len(canvas_items) == 0:
            sizing_data.preferred_height = None
        return Sizing(sizing_data)

    def _adjust_sizing(self, sizing_data: SizingData, x_spacing: int, y_spacing: int) -> SizingData:
        """ Adjust the sizing object by adding margins and spacing. Spacing is total, not per item. """
        if sizing_data.minimum_width is not None and not isinstance(sizing_data.minimum_width, SizingEnum):
            sizing_data.minimum_width += self.margins.left + self.margins.right + x_spacing
        if sizing_data.maximum_width is not None and not isinstance(sizing_data.maximum_width, SizingEnum):
            sizing_data.maximum_width += self.margins.left + self.margins.right + x_spacing
        if sizing_data.preferred_width is not None and not isinstance(sizing_data.preferred_width, SizingEnum):
            sizing_data.preferred_width += self.margins.left + self.margins.right + x_spacing
        if sizing_data.minimum_height is not None and not isinstance(sizing_data.minimum_height, SizingEnum):
            sizing_data.minimum_height += self.margins.top + self.margins.bottom + y_spacing
        if sizing_data.maximum_height is not None and not isinstance(sizing_data.maximum_height, SizingEnum):
            sizing_data.maximum_height += self.margins.top + self.margins.bottom + y_spacing
        if sizing_data.preferred_height is not None and not isinstance(sizing_data.preferred_height, SizingEnum):
            sizing_data.preferred_height += self.margins.top + self.margins.bottom + y_spacing
        return sizing_data

    def add_canvas_item(self, canvas_item: typing.Any, pos: typing.Optional[Geometry.IntPoint]) -> None:
        """
            Subclasses may override this method to get position specific information when a canvas item is added to
            the layout.
        """
        pass

    def remove_canvas_item(self, canvas_item: typing.Any) -> None:
        """
            Subclasses may override this method to clean up position specific information when a canvas item is removed
            from the layout.
        """
        pass

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        """ Subclasses must override this method to layout canvas item. """
        raise NotImplementedError()

    def get_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        """
            Return the sizing object for this layout. Includes spacing and margins.

            Subclasses must implement.
        """
        raise NotImplementedError()

    def create_spacing_item(self, spacing: int) -> AbstractCanvasItem:
        raise NotImplementedError()

    def create_stretch_item(self) -> AbstractCanvasItem:
        raise NotImplementedError()


class CanvasItemLayout(CanvasItemAbstractLayout):

    """
        Default layout which overlays all items on one another.

        Pass margins.
    """

    def __init__(self, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None) -> None:
        super().__init__(margins, spacing)

    def copy(self) -> CanvasItemAbstractLayout:
        return CanvasItemLayout(self.margins, self.spacing)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        for canvas_item in canvas_items:
            self.update_canvas_item_layout(canvas_origin, canvas_size, canvas_item)

    def get_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        return Sizing(self._adjust_sizing(self._get_overlap_sizing(canvas_items).sizing_data, 0, 0))

    def create_spacing_item(self, spacing: int) -> AbstractCanvasItem:
        raise NotImplementedError()

    def create_stretch_item(self) -> AbstractCanvasItem:
        raise NotImplementedError()


class CanvasItemColumnLayout(CanvasItemAbstractLayout):

    """
        Layout items in a column.

        Pass margins and spacing.
    """

    def __init__(self, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None,
                 alignment: typing.Optional[str] = None) -> None:
        super().__init__(margins, spacing)
        self.alignment = alignment

    def copy(self) -> CanvasItemAbstractLayout:
        return CanvasItemColumnLayout(self.margins, self.spacing, self.alignment)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        # calculate the vertical placement
        column_layout = self.calculate_column_layout(canvas_origin, canvas_size, canvas_items)
        widths = [canvas_item.layout_sizing.get_unrestrained_width(canvas_size.width - self.margins.left - self.margins.right) for canvas_item in canvas_items]
        available_width = canvas_size.width - self.margins.left - self.margins.right
        if self.alignment == "start":
            x_positions = [canvas_origin.x + self.margins.left for width in widths]
        elif self.alignment == "end":
            x_positions = [canvas_origin.x + self.margins.left + (available_width - width) for width in widths]
        else:
            x_positions = [round(canvas_origin.x + self.margins.left + (available_width - width) * 0.5) for width in widths]
        self.layout_canvas_items(x_positions, column_layout.origins, widths, column_layout.sizes, canvas_items)

    def get_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        return Sizing(self._adjust_sizing(self._get_column_sizing(canvas_items).sizing_data, 0, self.spacing * (len(canvas_items) - 1)))

    def create_spacing_item(self, spacing: int) -> AbstractCanvasItem:
        spacing_item = EmptyCanvasItem()
        spacing_item.update_sizing(spacing_item.sizing.with_fixed_height(spacing).with_fixed_width(0))
        return spacing_item

    def create_stretch_item(self) -> AbstractCanvasItem:
        spacing_item = EmptyCanvasItem()
        spacing_item.update_sizing(spacing_item.sizing.with_fixed_width(0))
        return spacing_item


class CanvasItemRowLayout(CanvasItemAbstractLayout):

    """
        Layout items in a row.

        Pass margins and spacing.
    """

    def __init__(self, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None,
                 alignment: typing.Optional[str] = None) -> None:
        super().__init__(margins, spacing)
        self.alignment = alignment

    def copy(self) -> CanvasItemAbstractLayout:
        return CanvasItemRowLayout(self.margins, self.spacing, self.alignment)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        row_layout = self.calculate_row_layout(canvas_origin, canvas_size, canvas_items)
        heights = [canvas_item.layout_sizing.get_unrestrained_height(canvas_size.height - self.margins.top - self.margins.bottom) for canvas_item in canvas_items]
        available_height = canvas_size.height - self.margins.top - self.margins.bottom
        if self.alignment == "start":
            y_positions = [canvas_origin.y + self.margins.top for width in row_layout.sizes]
        elif self.alignment == "end":
            y_positions = [canvas_origin.y + self.margins.top + (available_height - height) for height in heights]
        else:
            y_positions = [round(canvas_origin.y + self.margins.top + (available_height - height) // 2) for height in heights]
        self.layout_canvas_items(row_layout.origins, y_positions, row_layout.sizes, heights, canvas_items)

    def get_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        return Sizing(self._adjust_sizing(self._get_row_sizing(canvas_items).sizing_data, self.spacing * (len(canvas_items) - 1), 0))

    def create_spacing_item(self, spacing: int) -> AbstractCanvasItem:
        spacing_item = EmptyCanvasItem()
        spacing_item.update_sizing(spacing_item.sizing.with_fixed_width(spacing).with_fixed_height(0))
        return spacing_item

    def create_stretch_item(self) -> AbstractCanvasItem:
        spacing_item = EmptyCanvasItem()
        spacing_item.update_sizing(spacing_item.sizing.with_fixed_height(0))
        return spacing_item


class CanvasItemGridLayout(CanvasItemAbstractLayout):

    """
        Layout items in a grid specified by size (IntSize).

        Pass margins and spacing.

        Canvas items must be added to container canvas item using
        add_canvas_item with the position (IntPoint) passed as pos
        parameter.
    """

    def __init__(self, size: Geometry.IntSize, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None, columns: typing.Optional[typing.List[typing.List[typing.Optional[typing.Any]]]] = None, canvas_items: typing.Optional[typing.List[typing.Any]] = None) -> None:
        super().__init__(margins, spacing)
        assert size.width > 0 and size.height > 0
        self.__size = size
        # columns stores the canvas items in a grid. canvas items keeps track of the order in which they're added or
        # removed. this allows for finding the associated index of a canvas item in the layout so that the layout can
        # use the list of layout items passed in to layout or get_sizing.
        self.__columns = [[None for _ in range(size.height)] for _ in range(size.width)]
        if columns is not None and canvas_items is not None:
            self.__canvas_items = list(canvas_items)
            for row in range(size.height):
                for column in range(size.width):
                    old_canvas_item = columns[column][row]
                    if old_canvas_item:
                        index = canvas_items.index(columns[column][row])
                        self.__columns[column][row] = self.__canvas_items[index]
                    else:
                        self.__columns[column][row] = None
        else:
            self.__columns = [[None for _ in range(size.height)] for _ in range(size.width)]
            self.__canvas_items = list()

    def copy(self) -> CanvasItemAbstractLayout:
        return CanvasItemGridLayout(self.__size, self.margins, self.spacing, self.__columns, self.__canvas_items)

    def add_canvas_item(self, canvas_item: typing.Any, pos: typing.Optional[Geometry.IntPoint]) -> None:
        assert pos
        assert pos.x >= 0 and pos.x < self.__size.width
        assert pos.y >= 0 and pos.y < self.__size.height
        self.__columns[pos.x][pos.y] = canvas_item
        self.__canvas_items.append(canvas_item)

    def remove_canvas_item(self, canvas_item: typing.Any) -> None:
        for x in range(self.__size.width):
            for y in range(self.__size.height):
                if self.__columns[x][y] == canvas_item:
                    self.__columns[x][y] = None
        self.__canvas_items.remove(canvas_item)

    def __layout_sizing_item_at(self, canvas_items: typing.Sequence[LayoutSizingItem], x: int, y: int) -> typing.Optional[LayoutSizingItem]:
        canvas_item = self.__columns[x][y]
        if canvas_item is not None:
            index = self.__canvas_items.index(canvas_item)
            return canvas_items[index]
        return None

    def __layout_item_at(self, canvas_items: typing.Sequence[LayoutItem], x: int, y: int) -> typing.Optional[LayoutItem]:
        canvas_item = self.__columns[x][y]
        if canvas_item is not None:
            index = self.__canvas_items.index(canvas_item)
            return canvas_items[index]
        return None

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        canvas_items = list(canvas_items)
        # calculate the horizontal placement
        # calculate the sizing (x, width) for each column
        canvas_item_count = self.__size.width
        spacing_count = canvas_item_count - 1
        content_left = canvas_origin.x + self.margins.left
        content_width = canvas_size.width - self.margins.left - self.margins.right - self.spacing * spacing_count
        constraints = list()
        for x in range(self.__size.width):
            sizing = self._get_overlap_sizing([visible_layout_sizing_item(self.__layout_item_at(canvas_items, x, y)) for y in range(self.__size.height)])
            constraints.append(sizing.get_width_constraint(content_width))
        # run the layout engine
        row_layout = constraint_solve(content_left, content_width, constraints, self.spacing)
        # calculate the vertical placement
        # calculate the sizing (y, height) for each row
        canvas_item_count = self.__size.height
        spacing_count = canvas_item_count - 1
        content_top = canvas_origin.y + self.margins.top
        content_height = canvas_size.height - self.margins.top - self.margins.bottom - self.spacing * spacing_count
        constraints = list()
        for y in range(self.__size.height):
            sizing = self._get_overlap_sizing([visible_layout_sizing_item(self.__layout_item_at(canvas_items, x, y)) for x in range(self.__size.width)])
            constraints.append(sizing.get_height_constraint(content_height))
        # run the layout engine
        column_layout = constraint_solve(content_top, content_height, constraints, self.spacing)
        # do the layout
        combined_xs = list()
        combined_ys = list()
        combined_widths = list()
        combined_heights = list()
        combined_canvas_items = list()
        for x in range(self.__size.width):
            for y in range(self.__size.height):
                canvas_item = visible_layout_item(self.__layout_item_at(canvas_items, x, y))
                if canvas_item is not None:
                    combined_xs.append(row_layout.origins[x])
                    combined_ys.append(column_layout.origins[y])
                    combined_widths.append(row_layout.sizes[x])
                    combined_heights.append(column_layout.sizes[y])
                    combined_canvas_items.append(canvas_item)
        self.layout_canvas_items(combined_xs, combined_ys, combined_widths, combined_heights, combined_canvas_items)

    def get_sizing(self, canvas_items: typing.Sequence[LayoutSizingItem]) -> Sizing:
        """
            Calculate the sizing for the grid. Treat columns and rows independently.

            Override from abstract layout.
        """
        canvas_items = list(canvas_items)
        sizing_data = SizingData()
        sizing_data.maximum_width = 0
        sizing_data.maximum_height = 0
        sizing_data.preferred_height = 0
        # the widths
        canvas_item_sizings = list()
        for x in range(self.__size.width):
            canvas_items_ = [visible_layout_sizing_item(self.__layout_sizing_item_at(canvas_items, x, y)) for y in range(self.__size.height)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items_))
        for canvas_item_sizing in canvas_item_sizings:
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_width", operator.add)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_width", operator.add)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_width", operator.add, True)
        # the heights
        canvas_item_sizings = list()
        for y in range(self.__size.height):
            canvas_items_ = [visible_layout_sizing_item(self.__layout_sizing_item_at(canvas_items, x, y)) for x in range(self.__size.width)]
            canvas_item_sizings.append(self._get_overlap_sizing(canvas_items_))
        for canvas_item_sizing in canvas_item_sizings:
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "preferred_height", operator.add)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "minimum_height", operator.add)
            self._combine_sizing_property(sizing_data, canvas_item_sizing, "maximum_height", operator.add, True)
        if sizing_data.maximum_width == MAX_VALUE or len(canvas_items_) == 0:
            sizing_data.maximum_width = None
        if sizing_data.maximum_height == MAX_VALUE or len(canvas_items_) == 0:
            sizing_data.maximum_height = None
        if sizing_data.maximum_width == 0 or len(canvas_items_) == 0:
            sizing_data.maximum_width = None
        if sizing_data.preferred_width == 0 or len(canvas_items_) == 0:
            sizing_data.preferred_width = None
        if sizing_data.maximum_height == 0 or len(canvas_items_) == 0:
            sizing_data.maximum_height = None
        if sizing_data.preferred_height == 0 or len(canvas_items_) == 0:
            sizing_data.preferred_height = None
        self._adjust_sizing(sizing_data, self.spacing * (self.__size.width - 1), self.spacing * (self.__size.height - 1))
        return Sizing(sizing_data)


class CanvasItemCompositionComposer(BaseComposer):
    def __init__(self,
                 canvas_item: AbstractCanvasItem,
                 layout_sizing: Sizing,
                 composer_cache: ComposerCache,
                 layout: CanvasItemAbstractLayout,
                 child_composers: typing.Sequence[BaseComposer],
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]],
                 border_color: typing.Optional[str]) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__layout = layout
        self.__child_composers = child_composers
        self.__background_color = background_color
        self.__border_color = border_color

    def _update_layout(self, canvas_bounds: Geometry.IntRect) -> None:
        self.__layout.layout(Geometry.IntPoint(), canvas_bounds.size, self.__child_composers)

    def _repaint_visible(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        self.__draw_background(drawing_context, canvas_rect, self.__background_color)
        self._repaint_children(drawing_context, canvas_rect, visible_rect, self.__child_composers)
        self.__draw_border(drawing_context, canvas_rect, self.__border_color)
        self._draw_unique_marker(drawing_context, canvas_rect)

    def _repaint_children(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, child_composers: typing.Sequence[BaseComposer]) -> None:
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            visible_rect -= canvas_rect.origin
            for child_composer in child_composers:
                child_canvas_rect = child_composer._canvas_bounds
                if visible_rect.intersects_rect(child_canvas_rect):
                    child_composer.repaint(drawing_context, child_canvas_rect, visible_rect)

    def __draw_background(self, drawing_context: DrawingContext.DrawingContext, canvas_bounds: Geometry.IntRect, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        if background_color:
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.rect(canvas_bounds.left, canvas_bounds.top, canvas_bounds.width, canvas_bounds.height)
                drawing_context.fill_style = background_color
                drawing_context.fill()

    def __draw_border(self, drawing_context: DrawingContext.DrawingContext, canvas_bounds: Geometry.IntRect, border_color: typing.Optional[str]) -> None:
        if border_color:
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.rect(canvas_bounds.left, canvas_bounds.top, canvas_bounds.width, canvas_bounds.height)
                drawing_context.stroke_style = border_color
                drawing_context.stroke()


class CanvasItemComposition(AbstractCanvasItem):
    """A composite canvas item comprised of other canvas items.

    Optionally includes a layout. Compositions without an explicit layout are stacked to fit this container.

    Access child canvas items using canvas_items.

    Child canvas items with higher indexes are considered to be foremost.
    """

    def __init__(self) -> None:
        super().__init__()
        self.__canvas_items: typing.List[AbstractCanvasItem] = list()
        self.layout: CanvasItemAbstractLayout = CanvasItemLayout()

    def close(self) -> None:
        canvas_items = self.canvas_items
        for canvas_item in canvas_items:
            canvas_item.close()
        # this goes after closing; if this goes before closing, threaded canvas items don't get closed properly
        # since they notify their container (to cull). to reproduce the bug, create a 1x2, then a 4x3 in the bottom.
        # then close several panels and undo. not sure if this is  the permanent fix or not. reset to a list rather
        # than None so that pending uses of canvas_items don't fail.
        while self.__canvas_items:
            self._remove_canvas_item_direct(self.__canvas_items[-1])
        super().close()

    def _description(self) -> str:
        return self.__class__.__name__ + "/" + self.layout.__class__.__name__

    def _summary(self, indent: typing.Optional[str] = None) -> str:
        indent = indent or str()
        if self.__canvas_items:
            return super()._summary(indent) + f" [{len(self.__canvas_items)}]" + "\n" + "\n".join(canvas_item._summary(indent + "  ") for canvas_item in self.__canvas_items)
        else:
            return super()._summary(indent) + f" [{len(self.__canvas_items)}]"

    @property
    def canvas_items_count(self) -> int:
        """Return count of canvas items managed by this composition."""
        return len(self.__canvas_items)

    @property
    def canvas_items(self) -> typing.List[AbstractCanvasItem]:
        """ Return a copy of the canvas items managed by this composition. """
        return copy.copy(self.__canvas_items)

    @property
    def visible_canvas_items(self) -> typing.List[AbstractCanvasItem]:
        if self.__canvas_items is not None:
            return [canvas_item for canvas_item in self.__canvas_items if canvas_item and canvas_item.visible]
        return list()

    def layout_immediate(self, canvas_size: Geometry.IntSize) -> None:
        # TEST ONLY
        self.update_layout_immediate(Geometry.IntPoint(), canvas_size)

    # override sizing information. let layout provide it.
    @property
    def layout_sizing(self) -> Sizing:
        sizing = self.sizing
        layout_sizing = self.layout.get_sizing(self.visible_canvas_items)
        layout_sizing_data = layout_sizing.sizing_data
        if sizing.minimum_width is not None:
            layout_sizing_data.minimum_width = sizing.minimum_width if isinstance(sizing.minimum_width, (int, float)) else None
        if sizing.maximum_width is not None:
            layout_sizing_data.maximum_width = sizing.maximum_width if isinstance(sizing.maximum_width, (int, float)) else None
        if sizing.preferred_width is not None:
            layout_sizing_data.preferred_width = sizing.preferred_width if isinstance(sizing.preferred_width, (int, float)) else None
        if sizing.minimum_height is not None:
            layout_sizing_data.minimum_height = sizing.minimum_height if isinstance(sizing.minimum_height, (int, float)) else None
        if sizing.maximum_height is not None:
            layout_sizing_data.maximum_height = sizing.maximum_height if isinstance(sizing.maximum_height, (int, float)) else None
        if sizing.preferred_height is not None:
            layout_sizing_data.preferred_height = sizing.preferred_height if isinstance(sizing.preferred_height, (int, float)) else None
        if sizing.minimum_aspect_ratio is not None:
            layout_sizing_data.minimum_aspect_ratio = sizing.minimum_aspect_ratio
        if sizing.maximum_aspect_ratio is not None:
            layout_sizing_data.maximum_aspect_ratio = sizing.maximum_aspect_ratio
        if sizing.preferred_aspect_ratio is not None:
            layout_sizing_data.preferred_aspect_ratio = sizing.preferred_aspect_ratio
        if len(self.visible_canvas_items) == 0 and sizing.collapsible:
            layout_sizing_data.minimum_width = 0
            layout_sizing_data.preferred_width = 0
            layout_sizing_data.maximum_width = 0
            layout_sizing_data.minimum_height = 0
            layout_sizing_data.preferred_height = 0
            layout_sizing_data.maximum_height = 0
        return Sizing(layout_sizing_data)

    def size_to_content(self) -> None:
        # I'm not sure if this is the right implementation. It works for now.
        self.update_sizing(self.layout.get_sizing(self.visible_canvas_items))

    def _insert_canvas_item_direct(self, before_index: int, canvas_item: AbstractCanvasItem,
                                   pos: typing.Optional[Geometry.IntPoint] = None) -> None:
        self.insert_canvas_item(before_index, canvas_item, pos)

    def _insert_canvas_item_x(self, before_index: int, canvas_item: AbstractCanvasItem) -> None:
        self.__canvas_items.insert(before_index, canvas_item)

    def insert_canvas_item(self, before_index: int, canvas_item: AbstractCanvasItem,
                           pos: typing.Optional[typing.Any] = None) -> AbstractCanvasItem:
        """ Insert canvas item into layout. pos parameter is layout specific. """
        self._insert_canvas_item_x(before_index, canvas_item)
        canvas_item.container = self
        canvas_item._inserted(self)
        # tell the layout about the canvas item. layout does not occur here.
        self.layout.add_canvas_item(canvas_item, pos)
        # trigger layout of both this item and the container.
        self.update()
        return canvas_item

    def insert_spacing(self, before_index: int, spacing: int) -> AbstractCanvasItem:
        spacing_item = self.layout.create_spacing_item(spacing)
        return self.insert_canvas_item(before_index, spacing_item)

    def insert_stretch(self, before_index: int) -> AbstractCanvasItem:
        stretch_item = self.layout.create_stretch_item()
        return self.insert_canvas_item(before_index, stretch_item)

    def add_canvas_item(self, canvas_item: AbstractCanvasItem, pos: typing.Optional[typing.Any] = None) -> AbstractCanvasItem:
        """ Add canvas item to layout. pos parameter is layout specific. """
        return self.insert_canvas_item(len(self.__canvas_items), canvas_item, pos)

    def add_spacing(self, spacing: int) -> AbstractCanvasItem:
        return self.insert_spacing(len(self.__canvas_items), spacing)

    def add_stretch(self) -> AbstractCanvasItem:
        return self.insert_stretch(len(self.__canvas_items))

    def _remove_canvas_item_direct(self, canvas_item: AbstractCanvasItem) -> None:
        self.__canvas_items.remove(canvas_item)

    def _remove_canvas_item(self, canvas_item: AbstractCanvasItem) -> None:
        canvas_item._removed(self)
        canvas_item.close()
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        self._remove_canvas_item_direct(canvas_item)
        # trigger layout of both this item and the container.
        self.update()

    def remove_canvas_item(self, canvas_item: AbstractCanvasItem) -> None:
        """ Remove canvas item from layout. Canvas item is closed. """
        self._remove_canvas_item(canvas_item)

    def remove_all_canvas_items(self) -> None:
        """ Remove all canvas items from layout. Canvas items are closed. """
        for canvas_item in reversed(copy.copy(self.__canvas_items)):
            self._remove_canvas_item(canvas_item)

    def replace_canvas_item(self, old_canvas_item: AbstractCanvasItem, new_canvas_item: AbstractCanvasItem) -> None:
        """ Replace the given canvas item with the new one. Canvas item is closed. """
        index = self.__canvas_items.index(old_canvas_item)
        self.remove_canvas_item(old_canvas_item)
        self.insert_canvas_item(index, new_canvas_item)

    def replace_canvas_items(self, canvas_items: typing.Sequence[AbstractCanvasItem]) -> None:
        """ Replace all canvas items with the given ones. Canvas items are closed. """
        for canvas_item in reversed(copy.copy(self.__canvas_items)):
            canvas_item._set_owner_thread(threading.current_thread())
        self.remove_all_canvas_items()
        for canvas_item in canvas_items:
            self.add_canvas_item(canvas_item)

    def _will_wrap_child_canvas_item(self) -> typing.Any:
        return None

    def _did_wrap_child_canvas_item(self, state: typing.Any) -> typing.Any:
        pass

    def _will_unwrap_child_canvas_item(self) -> typing.Any:
        return None

    def _did_unwrap_child_canvas_item(self, state: typing.Any) -> typing.Any:
        pass

    def wrap_canvas_item(self, canvas_item: AbstractCanvasItem, canvas_item_container: CanvasItemComposition) -> None:
        """ Replace the given canvas item with the container and move the canvas item into the container. """
        wrap_state = self._will_wrap_child_canvas_item()
        canvas_origin = canvas_item.canvas_origin
        canvas_size = canvas_item.canvas_size
        index = self.__canvas_items.index(canvas_item)
        # remove the existing canvas item, but without closing it.
        self.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        canvas_item._set_canvas_size(None)
        canvas_item._set_canvas_origin(None)
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
        # allow subclasses to restore state
        self._did_wrap_child_canvas_item(wrap_state)
        self.update()

    def unwrap_canvas_item(self, canvas_item: AbstractCanvasItem) -> None:
        """ Replace the canvas item container with the canvas item. """
        container = canvas_item.container
        assert container
        assert len(container.canvas_items) == 1
        assert container.canvas_items[0] == canvas_item
        self_container = self.container
        assert self_container
        wrap_state = self_container._will_unwrap_child_canvas_item()
        enclosing_container = container.container
        assert enclosing_container
        index = enclosing_container.canvas_items.index(container)
        # remove the existing canvas item from the container, but without closing it.
        container.layout.remove_canvas_item(canvas_item)
        canvas_item.container = None
        canvas_item._set_canvas_size(None)
        canvas_item._set_canvas_origin(None)
        container._remove_canvas_item_direct(canvas_item)
        # remove container from enclosing container
        enclosing_container._remove_canvas_item_direct(container)
        # insert canvas item into the enclosing container
        # enclosing_container.insert_canvas_item(index, canvas_item)  # this would adjust splitters. don't do it.
        enclosing_container._insert_canvas_item_direct(index, canvas_item)
        # allow subclasses to restore state
        self_container._did_unwrap_child_canvas_item(wrap_state)
        # update the layout if origin and size already known
        self.update()

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        child_composers = list[BaseComposer]()
        for canvas_item in self.visible_canvas_items:
            composer = canvas_item.get_composer(composer_cache)
            if composer:
                child_composers.append(composer)
            else:
                return None
        return self._get_composition_composer(child_composers, composer_cache)

    def _get_composition_composer(self, child_composers: typing.Sequence[BaseComposer], composer_cache: ComposerCache) -> BaseComposer:
        return CanvasItemCompositionComposer(self, self.layout_sizing, composer_cache, self.layout.copy(), child_composers, self.background_color, self.border_color)

    def get_composer_immediate(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        child_composers = list[BaseComposer]()
        for canvas_item in self.visible_canvas_items:
            composer = canvas_item.get_composer_immediate(composer_cache)
            if composer:
                child_composers.append(composer)
            else:
                return None
        return self._get_composition_composer(child_composers, composer_cache)

    def repaint_immediate(self, drawing_context: DrawingContext.DrawingContext, canvas_size: Geometry.IntSize) -> None:
        # repaint assumes that the canvas item being repainted already has a canvas rect.
        # to ensure it does, call _update_layout here.
        canvas_rect = Geometry.IntRect(Geometry.IntPoint(), canvas_size)
        self.update_layout_using_composer(canvas_rect)
        self._repaint(drawing_context)

    def _canvas_items_at_point(self, visible_canvas_items: typing.Sequence[AbstractCanvasItem], x: int, y: int) -> typing.List[AbstractCanvasItem]:
        """Returns list of canvas items under x, y, ordered from back to front."""
        canvas_items: typing.List[AbstractCanvasItem] = []
        point = Geometry.IntPoint(x=x, y=y)
        for canvas_item in reversed(visible_canvas_items):
            # the visible items can be changed while this method is running from the layout thread.
            # and yet we don't want to allow this to occur; maybe the layout thread should have some
            # sort of pending system, where once methods like this exit, they're allowed to update...?
            canvas_item_rect = canvas_item.canvas_rect
            if canvas_item_rect and canvas_item_rect.contains_point(point):
                canvas_origin = typing.cast(Geometry.IntPoint, canvas_item.canvas_origin)
                canvas_point = point - canvas_origin
                canvas_items.extend(canvas_item.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super().canvas_items_at_point(x, y))
        return canvas_items

    def canvas_items_at_point(self, x: int, y: int) -> typing.List[AbstractCanvasItem]:
        """Returns list of canvas items under x, y, ordered from back to front."""
        return self._canvas_items_at_point(self.visible_canvas_items, x, y)

    def get_root_opaque_canvas_items(self) -> typing.List[AbstractCanvasItem]:
        if self.is_root_opaque:
            return [self]
        canvas_items = list()
        for canvas_item in self.canvas_items:
            canvas_items.extend(canvas_item.get_root_opaque_canvas_items())
        return canvas_items

    def pan_gesture(self, dx: int, dy: int) -> bool:
        for canvas_item in reversed(self.visible_canvas_items):
            if canvas_item.pan_gesture(dx, dy):
                return True
        return False


class DrawingContextCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, drawing_context: typing.Optional[DrawingContext.DrawingContext]) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__drawing_context = drawing_context

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        if self.__drawing_context:
            with drawing_context.saver():
                # drawing_context.translate(canvas_bounds.left, canvas_bounds.top)
                drawing_context.add(self.__drawing_context)

    def _update_repaint_count(self) -> None:
        # override this to prevent the repaint count from being updated since this is a passthrough for the layer
        # and doesn't represent a real repaint.
        pass


_threaded_rendering_enabled = True


class LayerCanvasItem(CanvasItemComposition):
    """A composite canvas item that does layout and repainting in a thread."""

    _executor = concurrent.futures.ThreadPoolExecutor()

    def __init__(self) -> None:
        super().__init__()
        self.__executing = False
        self.__cancel = False
        self.__needs_repaint = False  # keep track of repaint requests that arrive during an existing repaint
        self.__layer_drawing_context: typing.Optional[DrawingContext.DrawingContext] = None
        self.__layer_thread_lock = threading.RLock()
        self.__repaint_one_future: typing.Optional[concurrent.futures.Future[typing.Any]] = None
        self.__canvas_widget_section_ref: typing.Optional[CanvasWidgetSection] = None

    def close(self) -> None:
        self._stop_render_behavior()
        if self.__canvas_widget_section_ref:
            self.__canvas_widget_section_ref = None
        super().close()

    def _stop_render_behavior(self) -> None:
        self.__cancel = True
        done_event = threading.Event()
        with self.__layer_thread_lock:
            if self.__repaint_one_future:
                def repaint_done(future: typing.Optional[concurrent.futures.Future[typing.Any]]) -> None:
                    done_event.set()

                self.__repaint_one_future.add_done_callback(repaint_done)
            else:
                done_event.set()
        done_event.wait()

    def __repaint_done(self, future: typing.Optional[concurrent.futures.Future[typing.Any]]) -> None:
        with self.__layer_thread_lock:
            self.__repaint_one_future = None
            if self.__needs_repaint:
                self.__queue_repaint()

    def __queue_repaint(self) -> None:
        with self.__layer_thread_lock:
            # this will not launch another repaint layer if one is already running. updates will stack up and
            # be processed at the end of the current update in repaint done.
            if not self.__cancel and not self.__repaint_one_future:
                self.__needs_repaint = False
                self.__repaint_one_future = LayerCanvasItem._executor.submit(self.__repaint_layer)
                self.__repaint_one_future.add_done_callback(self.__repaint_done)
            else:
                self.__needs_repaint = True

    def _repaint_finished(self, drawing_context: DrawingContext.DrawingContext) -> None:
        # when the thread finishes the repaint, this method gets called. the normal container update
        # has not been called yet since the repaint wasn't finished until now. this method performs
        # the container update. it does not call the regular update again because that would re-invalidate
        # this canvas item itself and cause another repaint.
        self.__layer_drawing_context = drawing_context
        self._invalidate_composer()
        super()._updated()

    def _updated(self) -> None:
        # thread-safe
        with self.__layer_thread_lock:
            if _threaded_rendering_enabled:
                self.__queue_repaint()
        # normally, this method would mark a pending update and forward the update to the container;
        # however with the layer, since drawing occurs on a thread, this must occur after the thread
        # is finished. if the thread is suppressed (typically during testing), use the regular flow.
        if not _threaded_rendering_enabled:
            # pass through updates in the thread is suppressed, so that updates actually occur.
            super()._updated()

    def get_composer(self, cache: ComposerCache) -> typing.Optional[BaseComposer]:
        if self.__layer_drawing_context:
            return DrawingContextCanvasItemComposer(self, self.layout_sizing, cache, self.__layer_drawing_context)
        else:
            return EmptyCanvasItemComposer(self, self.layout_sizing, cache)

    def _layout_changed(self) -> None:
        self._updated()

    def _repaint_layer_inner(self, drawing_context: DrawingContext.DrawingContext) -> None:
        assert self.canvas_size is not None
        composer = self._get_composer_inner(self._get_composer_cache())
        canvas_rect = self.canvas_rect
        if composer and canvas_rect:
            composer.repaint(drawing_context, canvas_rect, canvas_rect)

    def repaint_immediate(self, drawing_context: DrawingContext.DrawingContext, canvas_size: Geometry.IntSize) -> None:
        # repaint assumes that the canvas item being repainted already has a canvas rect.
        # to ensure it does, call _update_layout here.
        composer = self.get_composer_immediate(self._get_composer_cache())
        if composer:
            # the "immediate" composer has composer for all children, including those of any layers in the hierarchy,
            # so it can be used to repaint immediate.
            composer.update_layout(Geometry.IntPoint(), canvas_size)
            if canvas_rect := self.canvas_rect:
                composer.repaint(drawing_context, canvas_rect, canvas_rect)

    def __map_origin_to_root_container(self) -> typing.Optional[Geometry.IntPoint]:
        """ Map the point to the coordinates of the root container.

        This is different from default implementation in that it returns None if it fails.
        """
        p = Geometry.IntPoint()
        canvas_item: typing.Optional[AbstractCanvasItem] = self
        while canvas_item:  # handle case where last canvas item was root
            canvas_item_origin = canvas_item.canvas_origin
            if canvas_item_origin is not None:  # handle case where canvas item is not root but has no parent
                p = canvas_item.map_to_container(p)
                canvas_item = canvas_item.container
            else:
                return None
        return p

    def __repaint_layer(self) -> None:
        if not self.__cancel:
            if self._has_layout:
                try:
                    with Process.audit("repaint_layer"):
                        canvas_rect = self.canvas_rect
                        root_container = self.root_container
                        canvas_widget = typing.cast(CanvasWidgetCanvasItem, root_container) if isinstance(root_container, CanvasWidgetCanvasItem) else None
                        drawing_context = DrawingContext.DrawingContext()
                        is_root_opaque = self.is_root_opaque
                        if is_root_opaque and canvas_widget and canvas_rect:
                            # if direct drawing is used, configure the drawing context to draw directly to the canvas
                            # widget section at the location 0,0.
                            drawing_context.translate(-canvas_rect.left, -canvas_rect.top)
                        self._repaint_layer_inner(drawing_context)
                        if not self.__cancel:
                            if is_root_opaque and canvas_widget and canvas_rect:
                                # if direct drawing is used, draw the drawing context to the canvas widget section.
                                if not self.__canvas_widget_section_ref:
                                    # create a section ref, which allows direct drawing for top level opaque items.
                                    # the section is automatically deallocated (via finalize) when the last python
                                    # reference to the section is released.
                                    self.__canvas_widget_section_ref = canvas_widget.get_section_ref()
                                # draw top level opaque item directly. ensure the proper canvas rect.
                                assert self.__canvas_widget_section_ref
                                # get the canvas origin; but wait until the root container is ready.
                                # this layout may occur faster than the root layout.
                                canvas_origin = self.__map_origin_to_root_container()
                                while not canvas_origin:
                                    time.sleep(0.01)
                                    canvas_origin = self.__map_origin_to_root_container()
                                canvas_rect = Geometry.IntRect(origin=canvas_origin, size=canvas_rect.size)
                                self.__canvas_widget_section_ref.draw(drawing_context, canvas_rect)
                            else:
                                # if this is a normal layer that is not top level opaque, then the drawing context
                                # is saved and the container is asked to update after which it will return a composer
                                # with the drawing context. if this is a root layer, then the drawing context is
                                # directly updated to the canvas widget.
                                self._repaint_finished(drawing_context)
                except Exception as e:
                    import traceback
                    logging.debug("CanvasItem Render Error: %s", e)
                    traceback.print_exc()
                    traceback.print_stack()


class ScrollAreaLayout(CanvasItemLayout):
    def __init__(self, auto_resize_contents: bool = False) -> None:
        super().__init__()
        self.auto_resize_contents = auto_resize_contents

    def copy(self) -> CanvasItemAbstractLayout:
        return ScrollAreaLayout(self.auto_resize_contents)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        content = canvas_items[0] if canvas_items else None
        if content:
            if self.auto_resize_contents:
                self.update_canvas_item_layout(canvas_origin, canvas_size, content)
            elif not content._has_layout:
                preferred_size = content.layout_sizing.get_preferred_size()
                if not preferred_size.width:
                    preferred_size = Geometry.IntSize(width=canvas_size.width, height=preferred_size.height)
                if not preferred_size.height:
                    preferred_size = Geometry.IntSize(width=preferred_size.width, height=canvas_size.height)
                self.update_canvas_item_layout(canvas_origin, preferred_size, content)


class ScrollAreaCanvasItemComposer(CanvasItemCompositionComposer):
    def __init__(self,
                 canvas_item: AbstractCanvasItem,
                 layout_sizing: Sizing,
                 composer_cache: ComposerCache,
                 layout: CanvasItemAbstractLayout,
                 child_composers: typing.Sequence[BaseComposer],
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]],
                 border_color: typing.Optional[str],
                 content_origin: Geometry.IntPoint) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache, layout, child_composers, background_color, border_color)
        self.__content_origin = content_origin

    def _repaint_children(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, child_composers: typing.Sequence[BaseComposer]) -> None:
        with drawing_context.saver():
            content_origin = self.__content_origin
            drawing_context.clip_rect(canvas_rect.left, canvas_rect.top, canvas_rect.width, canvas_rect.height)
            super()._repaint_children(drawing_context, canvas_rect + content_origin, visible_rect, child_composers)


class ScrollAreaCanvasItem(CanvasItemComposition):
    """A scroll area canvas item with content.

    This scroll area has the content_origin property, which controls where the content will be drawn, but not the
    size. When the scroll area is resized, update_layout will be called on the content (via the ScrollAreaLayout).
    The content is free to adjust its canvas size at any time.

    The content_origin will typically be negative if the content canvas_size is larger than the scroll area canvas
    size, and zero otherwise.
    """

    def __init__(self, content: typing.Optional[AbstractCanvasItem] = None) -> None:
        super().__init__()
        self.__content_origin = Geometry.IntPoint()
        self.__scroll_area_layout = ScrollAreaLayout()
        self.layout = self.__scroll_area_layout
        # the content_updated_event is used by scroll bars to update their size and position.
        self.content_updated_event = Event.Event()
        # set up listener for canvas size changes
        self.__canvas_size_changed_action = Stream.ValueStreamAction(self._canvas_size_stream, ReferenceCounting.weak_partial(ScrollAreaCanvasItem.__handle_canvas_size_changed, self))
        # update the content if it was passed in.
        if content:
            self.content = content
        self.__handle_canvas_size_changed(self.canvas_size)

    def __handle_canvas_size_changed(self, canvas_size: typing.Optional[Geometry.IntSizeTuple]) -> None:
        # if update_content_origin returns False, the content_updated_event was not fired and update was
        # not performed. However, since the size changed, those need to be done.
        if not self.update_content_origin(self.content_origin):
            self.content_updated_event.fire()
            self.update()

    @property
    def auto_resize_contents(self) -> bool:
        """Return whether the content should be resized when the scroll area is resized."""
        return self.__scroll_area_layout.auto_resize_contents

    @auto_resize_contents.setter
    def auto_resize_contents(self, value: bool) -> None:
        """Set whether the content should be resized when the scroll area is resized."""
        self.__scroll_area_layout.auto_resize_contents = value
        self.update()

    @property
    def content(self) -> typing.Optional[AbstractCanvasItem]:
        """ Return the content of the scroll area. """
        return self.canvas_items[0] if self.canvas_items else None

    @content.setter
    def content(self, content: AbstractCanvasItem) -> None:
        """ Set the content of the scroll area. """
        self.__content_canvas_size_changed_action = Stream.ValueStreamAction(content._canvas_size_stream, ReferenceCounting.weak_partial(ScrollAreaCanvasItem.__content_layout_updated, self))
        self.replace_canvas_items([content])

    @property
    def content_origin(self) -> Geometry.IntPoint:
        """Return the content origin (i.e. the scroll position)."""
        return self.__content_origin

    @property
    def content_size(self) -> typing.Optional[Geometry.IntSize]:
        """Return the content size. This is the size of the content canvas, not the scroll area canvas."""
        content = self.content
        return content.canvas_size if content else None

    @property
    def _content_rect(self) -> Geometry.IntRect:
        # for testing.
        return Geometry.IntRect(origin=self.content_origin, size=self.content_size or Geometry.IntSize())

    def update_content_origin(self, new_content_origin: Geometry.IntPoint) -> bool:
        """Update the content origin, restricting it to a valid range."""
        content_size = self.content_size or Geometry.IntSize()
        canvas_size = self.canvas_size or Geometry.IntSize()
        cx = max(-(content_size.width - canvas_size.width), min(0, new_content_origin.x)) if content_size.width > canvas_size.width else 0
        cy = max(-(content_size.height - canvas_size.height), min(0, new_content_origin.y)) if content_size.height > canvas_size.height else 0
        content_origin = Geometry.IntPoint(x=cx, y=cy)
        if self.__content_origin != content_origin:
            self.__content_origin = content_origin
            self.content_updated_event.fire()
            self.update()
            return True
        return False

    def make_selection_visible(self, min_rect: Geometry.IntRect, max_rect: Geometry.IntRect, adjust_horizontal: bool, adjust_vertical: bool, prefer_min: bool) -> None:
        canvas_origin = self.canvas_origin
        canvas_size = self.canvas_size
        if canvas_origin and canvas_size:
            content_origin = self.content_origin
            if content_origin:
                new_content_origin = content_origin
                visible_rect = Geometry.IntRect(origin=-content_origin, size=canvas_size)
                if adjust_vertical:
                    if prefer_min:
                        if min_rect.top < visible_rect.top:
                            new_content_origin = Geometry.IntPoint(y=-min_rect.top, x=new_content_origin.x)
                        elif min_rect.bottom > visible_rect.bottom:
                            new_content_origin = Geometry.IntPoint(y=-min_rect.bottom + visible_rect.height, x=new_content_origin.x)
                    else:
                        if max_rect.bottom > visible_rect.bottom:
                            new_content_origin = Geometry.IntPoint(y=-max_rect.bottom + visible_rect.height, x=new_content_origin.x)
                        elif max_rect.top < visible_rect.top:
                            new_content_origin = Geometry.IntPoint(y=-max_rect.top, x=new_content_origin.x)
                if adjust_horizontal:
                    if prefer_min:
                        if min_rect.left < visible_rect.left:
                            new_content_origin = Geometry.IntPoint(y=new_content_origin.y, x=-min_rect.left)
                        elif min_rect.right > visible_rect.right:
                            new_content_origin = Geometry.IntPoint(y=new_content_origin.y, x=-min_rect.right + visible_rect.width)
                    else:
                        if max_rect.right > visible_rect.right:
                            new_content_origin = Geometry.IntPoint(y=new_content_origin.y, x=-max_rect.right + visible_rect.width)
                        elif max_rect.left < visible_rect.left:
                            new_content_origin = Geometry.IntPoint(y=new_content_origin.y, x=-max_rect.left)
                self.update_content_origin(new_content_origin)

    @property
    def layout_sizing(self) -> Sizing:
        return self.sizing

    def __content_layout_updated(self, canvas_size: typing.Optional[Geometry.IntSize]) -> None:
        # whenever the content layout changes, this method gets called. adjust the canvas_origin of the content if
        # necessary. pass the canvas_origin, canvas_size of the content. this method is used in the scroll bar canvas
        # item to ensure that the content stays within view and consistent with the scroll bar when the scroll area
        # gets a new layout.
        if self._has_layout:
            # when the scroll area content layout changes, this method will get called. ensure that the content
            # matches the scroll position.
            if not self.update_content_origin(self.__content_origin):
                self.content_updated_event.fire()
                self.update()

    def _get_composition_composer(self, child_composers: typing.Sequence[BaseComposer], composer_cache: ComposerCache) -> BaseComposer:
        return ScrollAreaCanvasItemComposer(self, self.layout_sizing, composer_cache, self.layout, child_composers, self.background_color, self.border_color, self.__content_origin)

    def map_to_container(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return super().map_to_container(p + self.content_origin)

    def canvas_items_at_point(self, x: int, y: int) -> typing.List[AbstractCanvasItem]:
        canvas_items: typing.List[AbstractCanvasItem] = []
        point = Geometry.IntPoint(x=x, y=y)
        canvas_point = point - self.content_origin
        content = self.content
        if content and content.canvas_rect and content.canvas_rect.contains_point(canvas_point):
            canvas_items.extend(content.canvas_items_at_point(canvas_point.x, canvas_point.y))
        canvas_items.extend(super().canvas_items_at_point(x, y))
        return canvas_items

    def wheel_changed(self, x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> bool:
        canvas_origin = self.canvas_origin
        canvas_size = self.canvas_size
        if canvas_origin and canvas_size:
            x -= canvas_origin.x
            y -= canvas_origin.y
            content = self.content
            content_size = self.content_size
            if content and content_size:
                # give the content a chance to handle the wheel changed itself.
                if content.wheel_changed(x, y, dx, dy, is_horizontal):
                    return True
                # if the content didn't handle the wheel changed, then scroll the content here.
                dx = dx if is_horizontal else 0
                dy = dy if not is_horizontal else 0
                self.update_content_origin(self.__content_origin + Geometry.IntPoint(x=dx, y=dy))
                return True
        return False

    def pan_gesture(self, dx: int, dy: int) -> bool:
        content = self.content
        if content:
            return content.pan_gesture(dx, dy)
        return False


class SplitterLayout(CanvasItemLayout):
    def __init__(self, orientation: str, margins: typing.Optional[Geometry.Margins] = None, spacing: typing.Optional[int] = None, sizings: typing.Optional[typing.Sequence[Sizing]] = None) -> None:
        super().__init__(margins, spacing)
        self.__orientation = orientation
        self.__sizings = list(sizings) if sizings else list[Sizing]()

    def copy(self) -> CanvasItemAbstractLayout:
        return SplitterLayout(self.__orientation, self.margins, self.spacing, self.__sizings)

    @property
    def sizings(self) -> typing.Sequence[Sizing]:
        return self.__sizings

    def with_sizings(self, sizings: typing.Sequence[Sizing]) -> SplitterLayout:
        return SplitterLayout(self.__orientation, self.margins, self.spacing, sizings)

    def layout(self, canvas_origin: Geometry.IntPoint, canvas_size: Geometry.IntSize, canvas_items: typing.Sequence[LayoutItem]) -> None:
        sizings = self.sizings
        assert len(canvas_items) == len(sizings)
        if canvas_size:
            layout = SplitterCanvasItem.calculate_layout(self.__orientation, canvas_size, sizings)
            if self.__orientation == "horizontal":
                for canvas_item, (origin, size) in zip(canvas_items, zip(layout.origins, layout.sizes)):
                    canvas_item_origin = Geometry.IntPoint(y=origin, x=0)  # origin within the splitter
                    canvas_item_size = Geometry.IntSize(height=size, width=canvas_size.width)
                    canvas_item.update_layout(canvas_item_origin, canvas_item_size)
                    assert canvas_item._has_layout
            else:
                for canvas_item, (origin, size) in zip(canvas_items, zip(layout.origins, layout.sizes)):
                    canvas_item_origin = Geometry.IntPoint(y=0, x=origin)  # origin within the splitter
                    canvas_item_size = Geometry.IntSize(height=canvas_size.height, width=size)
                    canvas_item.update_layout(canvas_item_origin, canvas_item_size)
                    assert canvas_item._has_layout


class SplitterCanvasItemComposer(CanvasItemCompositionComposer):
    def __init__(self,
                 canvas_item: AbstractCanvasItem,
                 layout_sizing: Sizing,
                 composer_cache: ComposerCache,
                 layout: CanvasItemAbstractLayout,
                 child_composers: typing.Sequence[BaseComposer],
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]],
                 border_color: typing.Optional[str],
                 orientation: str) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache, layout, child_composers, background_color, border_color)
        self.__child_composers = child_composers
        self.__orientation = orientation

    def _repaint_visible(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, visible_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        super()._repaint_visible(drawing_context, canvas_rect, visible_rect, composer_cache)
        # this section is only to draw the splitter lines.
        with drawing_context.saver():
            drawing_context.begin_path()
            for child_composer in self.__child_composers[1:]:
                child_canvas_origin = child_composer._canvas_bounds.origin
                if self.__orientation == "horizontal":
                    drawing_context.move_to(canvas_rect.left, child_canvas_origin.y)
                    drawing_context.line_to(canvas_rect.right, child_canvas_origin.y)
                else:
                    drawing_context.move_to(child_canvas_origin.x, canvas_rect.top)
                    drawing_context.line_to(child_canvas_origin.x, canvas_rect.bottom)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#666"
            drawing_context.stroke()


class SplitterCanvasItem(CanvasItemComposition):

    def __init__(self, orientation: typing.Optional[str] = None) -> None:
        super().__init__()
        self.orientation = orientation if orientation else "vertical"
        self.__splitter_layout = SplitterLayout(self.orientation)
        self.layout = self.__splitter_layout
        self.wants_mouse_events = True
        self.__lock = threading.RLock()
        self.__sizings: typing.List[Sizing] = []
        self.__tracking = False
        self.__tracking_start_pos = Geometry.IntPoint()
        self.__tracking_start_adjust = 0
        self.__tracking_start_index = 0
        self.__tracking_start_preferred = 0
        self.__tracking_start_preferred_next = 0
        self.on_splits_will_change: typing.Optional[typing.Callable[[], None]] = None
        self.on_splits_changed: typing.Optional[typing.Callable[[], None]] = None

    def _description(self) -> str:
        return super()._description() + f" {self.orientation} {self.splits}"

    # for debugging
    # def _summary(self, indent: typing.Optional[str] = None) -> str:
    #     indent = indent or str()
    #     return indent + self._description() + f"+0x{id(self):x}" + " [" + str(self.canvas_rect) + "]" + " (" + str(self.sizing) + ")"

    @classmethod
    def calculate_layout(self, orientation: str, canvas_size: Geometry.IntSize, sizings: typing.Sequence[Sizing]) -> ConstraintResultType:
        if orientation == "horizontal":
            content_origin = 0
            content_size = canvas_size.height
            constraints = [sizing.get_height_constraint(content_size) for sizing in sizings]
        else:
            content_origin = 0
            content_size = canvas_size.width
            constraints = [sizing.get_width_constraint(content_size) for sizing in sizings]
        return constraint_solve(content_origin, content_size, constraints)

    @property
    def splits(self) -> typing.Sequence[float]:
        """ Return the canvas item splits, which represent the relative size of each child. """
        if self.canvas_size:
            canvas_size = self.canvas_size
        else:
            canvas_size = Geometry.IntSize(w=640, h=480)

        if self.orientation == "horizontal":
            content_size = canvas_size.height
        else:
            content_size = canvas_size.width

        with self.__lock:
            sizings = copy.copy(self.__sizings)

        layout = SplitterCanvasItem.calculate_layout(self.orientation, canvas_size, sizings)

        return [float(size) / content_size for size in layout.sizes]

    @splits.setter
    def splits(self, splits: typing.Sequence[float]) -> None:
        with self.__lock:
            sizings = copy.copy(self.__sizings)
        assert len(splits) == len(sizings)
        for index, (split, sizing) in enumerate(zip(splits, sizings)):
            if self.orientation == "horizontal":
                sizings[index] = sizing.with_preferred_height(split)
            else:
                sizings[index] = sizing.with_preferred_width(split)
        with self.__lock:
            self.__sizings = sizings
            self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
            self.layout = self.__splitter_layout
        self.update()

    def _insert_canvas_item_x(self, before_index: int, canvas_item: AbstractCanvasItem) -> None:
        sizing_data = SizingData()
        if self.orientation == "horizontal":
            sizing_data.preferred_height = None
            if sizing_data.minimum_height is None:
                sizing_data.minimum_height = 0.1
        else:
            sizing_data.preferred_width = None
            if sizing_data.minimum_width is None:
                sizing_data.minimum_width = 0.1
        with self.__lock:
            self.__sizings.insert(before_index, Sizing(sizing_data))
            self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
            self.layout = self.__splitter_layout
        super()._insert_canvas_item_x(before_index, canvas_item)
        self.update()

    def _remove_canvas_item_direct(self, canvas_item: AbstractCanvasItem) -> None:
        with self.__lock:
            del self.__sizings[self.canvas_items.index(canvas_item)]
            self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
            self.layout = self.__splitter_layout
        super()._remove_canvas_item_direct(canvas_item)
        self.update()

    def canvas_items_at_point(self, x: int, y: int) -> typing.List[AbstractCanvasItem]:
        if self.orientation == "horizontal":
            for canvas_item in self.canvas_items[1:]:  # don't check the '0' origin
                if canvas_item.canvas_origin and abs(y - canvas_item.canvas_origin.y) < 6:
                    return [self]
        else:
            for canvas_item in self.canvas_items[1:]:  # don't check the '0' origin
                if canvas_item.canvas_origin and abs(x - canvas_item.canvas_origin.x) < 6:
                    return [self]
        return super().canvas_items_at_point(x, y)

    def _will_wrap_child_canvas_item(self) -> typing.Any:
        return self.splits

    def _did_wrap_child_canvas_item(self, state: typing.Any) -> typing.Any:
        self.splits = typing.cast(typing.Sequence[float], state)

    def _will_unwrap_child_canvas_item(self) -> typing.Any:
        return self.splits

    def _did_unwrap_child_canvas_item(self, state: typing.Any) -> typing.Any:
        self.splits = typing.cast(typing.Sequence[float], state)

    def _get_composition_composer(self, child_composers: typing.Sequence[BaseComposer], composer_cache: ComposerCache) -> BaseComposer:
        return SplitterCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__splitter_layout, child_composers, self.background_color, self.border_color, self.orientation)

    def __hit_test(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> typing.Tuple[str, int, int]:
        if self._has_layout:
            for index, canvas_item in enumerate(self.canvas_items[1:]):  # don't check the '0' origin
                if canvas_item.canvas_origin:
                    if self.orientation == "horizontal" and abs(y - canvas_item.canvas_origin.y) < 6:
                        return "horizontal", index + 1, y - canvas_item.canvas_origin.y
                    elif self.orientation == "vertical" and abs(x - canvas_item.canvas_origin.x) < 6:
                        return  "vertical", index + 1, x - canvas_item.canvas_origin.x
        return "horizontal", 0, 0

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        orientation, index, adjust = self.__hit_test(x, y, modifiers)
        if index > 0:
            canvas_items = self.canvas_items
            canvas_item = canvas_items[index - 1]
            next_canvas_item = canvas_items[index]
            canvas_size = canvas_item.canvas_size or Geometry.IntSize()
            next_canvas_size = next_canvas_item.canvas_size or Geometry.IntSize()
            with self.__lock:
                sizings = copy.copy(self.__sizings)
            self.__tracking = True
            self.__tracking_start_pos = Geometry.IntPoint(y=y, x=x)
            self.__tracking_start_adjust = adjust
            self.__tracking_start_index = index - 1
            self.__tracking_start_preferred = canvas_size.height if orientation == "horizontal" else canvas_size.width
            self.__tracking_start_preferred_next = next_canvas_size.height if orientation == "horizontal" else next_canvas_size.width
            if callable(self.on_splits_will_change):
                self.on_splits_will_change()
            # fix the size of all children except for the two in question
            new_sizings: typing.List[Sizing] = list()
            for index, (canvas_item, sizing) in enumerate(zip(canvas_items, sizings)):
                if index != self.__tracking_start_index and index != self.__tracking_start_index + 1:
                    canvas_size = canvas_item.canvas_size or Geometry.IntSize()
                    if self.orientation == "horizontal":
                        new_sizings.append(sizing.with_fixed_height(canvas_size.height))
                    else:
                        new_sizings.append(sizing.with_fixed_width(canvas_size.width))
                else:
                    new_sizings.append(sizing)
            # update the layout
            with self.__lock:
                self.__sizings = new_sizings
                self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
                self.layout = self.__splitter_layout
            self.update()
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__tracking = False
        # restore the freedom of the others
        with self.__lock:
            sizings = self.__sizings
        new_sizings: typing.List[Sizing] = list()
        canvas_size = self.canvas_size
        assert canvas_size
        layout = SplitterCanvasItem.calculate_layout(self.orientation, canvas_size, sizings)
        for layout_size in layout.sizes:
            sizing_data = SizingData()
            if self.orientation == "horizontal":
                sizing_data.minimum_height = 0.1
                sizing_data.preferred_height = layout_size
            else:
                sizing_data.minimum_width = 0.1
                sizing_data.preferred_width = layout_size
            new_sizings.append(Sizing(sizing_data))
        with self.__lock:
            self.__sizings = new_sizings
            self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
            self.layout = self.__splitter_layout
        self.update()
        if callable(self.on_splits_changed):
            self.on_splits_changed()
        return True

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__tracking:
            with self.__lock:
                new_sizings = copy.copy(self.__sizings)
            tracking_start_preferred_next = self.__tracking_start_preferred_next
            tracking_start_preferred = self.__tracking_start_preferred
            snaps: typing.List[int] = list()
            canvas_bounds = self.canvas_bounds
            if canvas_bounds:
                if self.orientation == "horizontal":
                    offset = y - self.__tracking_start_pos.y
                    if not modifiers.shift:
                        snaps.append((tracking_start_preferred_next - tracking_start_preferred) // 2)
                        snaps.append(canvas_bounds.height // 3 - self.__tracking_start_pos.y - self.__tracking_start_adjust)
                        snaps.append(2 * canvas_bounds.height // 3 - self.__tracking_start_pos.y - self.__tracking_start_adjust)
                        for snap in snaps:
                            if abs(offset - snap) < 12:
                                offset = snap
                                break
                    new_sizings[self.__tracking_start_index] = new_sizings[self.__tracking_start_index].with_preferred_height(tracking_start_preferred + offset)
                    new_sizings[self.__tracking_start_index + 1] = new_sizings[self.__tracking_start_index + 1].with_preferred_height(tracking_start_preferred_next - offset)
                else:
                    offset = x - self.__tracking_start_pos.x
                    if not modifiers.shift:
                        snaps.append((tracking_start_preferred_next - tracking_start_preferred) // 2)
                        snaps.append(canvas_bounds.width // 3 - self.__tracking_start_pos.x - self.__tracking_start_adjust)
                        snaps.append(2 * canvas_bounds.width // 3 - self.__tracking_start_pos.x - self.__tracking_start_adjust)
                        for snap in snaps:
                            if abs(offset - snap) < 12:
                                offset = snap
                                break
                    new_sizings[self.__tracking_start_index] = new_sizings[self.__tracking_start_index].with_preferred_width(tracking_start_preferred + offset)
                    new_sizings[self.__tracking_start_index + 1] = new_sizings[self.__tracking_start_index + 1].with_preferred_width(tracking_start_preferred_next - offset)
            with self.__lock:
                self.__sizings = new_sizings
                self.__splitter_layout = self.__splitter_layout.with_sizings(self.__sizings)
                self.layout = self.__splitter_layout
            self.update()
            return True
        else:
            control, _, _ = self.__hit_test(x, y, modifiers)
            if control == "horizontal":
                self.cursor_shape = "split_vertical"
            elif control == "vertical":
                self.cursor_shape = "split_horizontal"
            else:
                self.cursor_shape = None
            return super().mouse_position_changed(x, y, modifiers)


SLIDER_THUMB_WIDTH = 8
SLIDER_THUMB_HEIGHT = 16
SLIDER_BAR_OFFSET = 1
SLIDER_BAR_HEIGHT = 4


def get_slider_bar_rect(canvas_size: typing.Optional[Geometry.IntSize]) -> Geometry.FloatRect:
    if canvas_size:
        bar_width = canvas_size.width - SLIDER_THUMB_WIDTH - SLIDER_BAR_OFFSET * 2
        return Geometry.FloatRect.from_tlhw(canvas_size.height / 2 - SLIDER_BAR_HEIGHT / 2, SLIDER_BAR_OFFSET + SLIDER_THUMB_WIDTH / 2, SLIDER_BAR_HEIGHT, bar_width)
    return Geometry.FloatRect.empty_rect()

def get_slider_thumb_rect(canvas_size: typing.Optional[Geometry.IntSize], value: float) -> Geometry.IntRect:
    if canvas_size:
        bar_width = canvas_size.width - SLIDER_THUMB_WIDTH - SLIDER_BAR_OFFSET * 2
        # use tracking value to avoid thumb jumping around while dragging, which occurs when value gets integerized and set.
        return Geometry.FloatRect.from_tlhw(canvas_size.height / 2 - SLIDER_THUMB_HEIGHT / 2, value * bar_width + SLIDER_BAR_OFFSET, SLIDER_THUMB_HEIGHT, SLIDER_THUMB_WIDTH).to_int_rect()
    return Geometry.IntRect.empty_rect()


class SliderCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, value: float) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__value = value

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        thumb_rect = get_slider_thumb_rect(canvas_rect.size, self.__value)
        bar_rect = get_slider_bar_rect(canvas_rect.size)
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            drawing_context.begin_path()
            drawing_context.rect(bar_rect.left, bar_rect.top, bar_rect.width, bar_rect.height)
            drawing_context.fill_style = "#CCC"
            drawing_context.fill()
            drawing_context.stroke_style = "#888"
            drawing_context.stroke()
            drawing_context.begin_path()
            drawing_context.rect(thumb_rect.left, thumb_rect.top, thumb_rect.width, thumb_rect.height)
            drawing_context.fill_style = "#007AD8"
            drawing_context.fill()


class SliderCanvasItem(AbstractCanvasItem, Observable.Observable):
    """Slider."""
    def __init__(self) -> None:
        super().__init__()
        self.wants_mouse_events = True
        self.__tracking = False
        self.__tracking_start = Geometry.IntPoint()
        self.__tracking_value = 0.0
        self.update_sizing(self.sizing.with_fixed_height(20))
        self.value_stream = Stream.ValueStream[float]().add_ref()
        self.value_change_stream = Stream.ValueChangeStream(self.value_stream).add_ref()

    def close(self) -> None:
        self.value_change_stream.remove_ref()
        self.value_change_stream = typing.cast(typing.Any, None)
        self.value_stream.remove_ref()
        self.value_stream = typing.cast(typing.Any, None)
        super().close()

    @property
    def value(self) -> float:
        return self.value_stream.value or 0.0

    @value.setter
    def value(self, value: float) -> None:
        if self.value != value:
            self.value_stream.value = max(0.0, min(1.0, value))
            self.update()
            self.notify_property_changed("value")

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        value = self.value if not self.__tracking else self.__tracking_value
        return SliderCanvasItemComposer(self, self.layout_sizing, composer_cache, value)

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        thumb_rect = get_slider_thumb_rect(self.canvas_size, self.value)
        pos = Geometry.IntPoint(x=x, y=y)
        if thumb_rect.inset(-2, -2).contains_point(pos):
            self.__tracking = True
            self.__tracking_start = pos
            self.__tracking_value = self.value
            self.value_change_stream.begin()
            self.update()
            return True
        elif x < thumb_rect.left:
            self.__adjust_thumb(-1)
            return True
        elif x > thumb_rect.right:
            self.__adjust_thumb(1)
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__tracking:
            self.__tracking = False
            self.value_change_stream.end()
            self.update()
            return True
        return super().mouse_released(x, y, modifiers)

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__tracking:
            pos = Geometry.FloatPoint(x=x, y=y)
            bar_rect = get_slider_bar_rect(self.canvas_size)
            value = (pos.x - bar_rect.left) / bar_rect.width
            self.__tracking_value = max(0.0, min(1.0, value))
            self.value = value
        return super().mouse_position_changed(x, y, modifiers)

    def __adjust_thumb(self, amount: float) -> None:
        self.value_change_stream.begin()
        self.value = max(0.0, min(1.0, self.value + amount * 0.1))
        self.value_change_stream.end()


@dataclasses.dataclass
class PositionLength:
    position: int
    length: int


def get_thumb_position_and_length(canvas_length: int, visible_length: int, content_length: int, content_offset: int) -> PositionLength:
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
        # the free-range of the thumb which is the canvas_length minus the thumb_length.
        thumb_position = int((canvas_length - thumb_length) * (float(-content_offset) / scroll_range))
    else:
        thumb_length = 0
        thumb_position = 0
    return PositionLength(thumb_position, thumb_length)


def get_thumb_rect(canvas_size: Geometry.IntSize, orientation: Orientation, content_rect: Geometry.IntRect) -> Geometry.IntRect:
    # return the thumb rect for the given canvas_size
    index = 0 if orientation == Orientation.Vertical else 1
    scroll_area_content_origin = content_rect.origin
    scroll_area_content_size = content_rect.size
    if scroll_area_content_size.width and scroll_area_content_size.height:
        visible_length = canvas_size[index]
        content_length = scroll_area_content_size[index]
        content_offset = scroll_area_content_origin[index]
        thumb_position_length = get_thumb_position_and_length(canvas_size[index], visible_length, content_length, content_offset)
        if orientation == Orientation.Vertical:
            thumb_origin = Geometry.IntPoint(x=0, y=thumb_position_length.position)
            thumb_size = Geometry.IntSize(width=canvas_size.width, height=thumb_position_length.length)
        else:
            thumb_origin = Geometry.IntPoint(x=thumb_position_length.position, y=0)
            thumb_size = Geometry.IntSize(width=thumb_position_length.length, height=canvas_size.height)
        return Geometry.IntRect(origin=thumb_origin, size=thumb_size)
    return Geometry.IntRect.empty_rect()


class ScrollBarCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, orientation: Orientation, content_rect: Geometry.IntRect, is_tracking: bool) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__orientation = orientation
        self.__content_rect = content_rect
        self.__is_tracking = is_tracking

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        # canvas size, thumb rect
        orientation = self.__orientation
        is_tracking = self.__is_tracking
        thumb_rect = get_thumb_rect(canvas_rect.size, self.__orientation, self.__content_rect)
        # draw it
        with drawing_context.saver():
            # draw the border of the scroll bar
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            drawing_context.begin_path()
            drawing_context.rect(0, 0, canvas_rect.width, canvas_rect.height)
            if orientation == Orientation.Vertical:
                gradient = drawing_context.create_linear_gradient(canvas_rect.width, canvas_rect.height, 0, 0, canvas_rect.width, 0)
            else:
                gradient = drawing_context.create_linear_gradient(canvas_rect.width, canvas_rect.height, 0, 0, 0, canvas_rect.height)
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
                    if orientation == Orientation.Vertical:
                        drawing_context.move_to(thumb_rect.width - 8, thumb_rect.top + 6)
                        drawing_context.line_to(thumb_rect.width - 8, thumb_rect.bottom - 6)
                    else:
                        drawing_context.move_to(thumb_rect.left + 6, thumb_rect.height - 8)
                        drawing_context.line_to(thumb_rect.right - 6, thumb_rect.height - 8)
                    drawing_context.line_width = 8.0
                    drawing_context.line_cap = "round"
                    drawing_context.stroke_style = "#888" if is_tracking else "#CCC"
                    drawing_context.stroke()
            # draw inside edge
            drawing_context.begin_path()
            drawing_context.move_to(0, 0)
            if orientation == Orientation.Vertical:
                drawing_context.line_to(0, canvas_rect.height)
            else:
                drawing_context.line_to(canvas_rect.width, 0)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#E3E3E3"
            drawing_context.stroke()
            # draw outside
            drawing_context.begin_path()
            if orientation == Orientation.Vertical:
                drawing_context.move_to(canvas_rect.width, 0)
            else:
                drawing_context.move_to(0, canvas_rect.height)
            drawing_context.line_to(canvas_rect.width, canvas_rect.height)
            drawing_context.line_width = 0.5
            drawing_context.stroke_style = "#999999"
            drawing_context.stroke()


class ScrollBarCanvasItem(AbstractCanvasItem):
    """A scroll bar for a scroll area."""

    def __init__(self, scroll_area_canvas_item: ScrollAreaCanvasItem, orientation: typing.Optional[Orientation] = None) -> None:
        super().__init__()
        orientation = orientation if orientation is not None else Orientation.Vertical
        self.wants_mouse_events = True
        self.__scroll_area_canvas_item = scroll_area_canvas_item
        self.__scroll_area_canvas_item_content_updated_listener = self.__scroll_area_canvas_item.content_updated_event.listen(self.update)
        self.__tracking = False
        self.__orientation = orientation
        if self.__orientation == Orientation.Vertical:
            self.update_sizing(self.sizing.with_fixed_width(16))
        else:
            self.update_sizing(self.sizing.with_fixed_height(16))

    def close(self) -> None:
        self.__scroll_area_canvas_item_content_updated_listener.close()
        self.__scroll_area_canvas_item_content_updated_listener = typing.cast(typing.Any, None)
        super().close()

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return ScrollBarCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__orientation, self.__scroll_area_canvas_item._content_rect, self.__tracking)

    def __change_tracking(self, tracking: bool) -> None:
        if self.__tracking != tracking:
            self.__tracking = tracking
            self.update()

    @property
    def thumb_rect(self) -> Geometry.IntRect:
        # return the thumb rect for the given canvas_size
        canvas_size = self.canvas_size
        if canvas_size:
            return get_thumb_rect(canvas_size, self.__orientation, self.__scroll_area_canvas_item._content_rect)
        return Geometry.IntRect.empty_rect()

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        thumb_rect = self.thumb_rect
        pos = Geometry.IntPoint(x=x, y=y)
        if thumb_rect.contains_point(pos):
            self.__change_tracking(True)
            self.__tracking_start = pos
            self.__tracking_content_origin = self.__scroll_area_canvas_item.content_origin or Geometry.IntPoint()
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

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__change_tracking(False)
        return super().mouse_released(x, y, modifiers)

    def __adjust_thumb(self, amount: float) -> None:
        # adjust the position up or down one visible screen worth
        index = 0 if self.__orientation == Orientation.Vertical else 1
        scroll_area_rect = self.__scroll_area_canvas_item.canvas_rect
        if scroll_area_rect:
            visible_length = scroll_area_rect.size[index]
            content_canvas_origin = self.__scroll_area_canvas_item.content_origin
            if content_canvas_origin:
                if self.__orientation == Orientation.Vertical:
                    new_content_origin = Geometry.IntPoint(y=round(content_canvas_origin[0] - visible_length * amount), x=content_canvas_origin[1])
                else:
                    new_content_origin = Geometry.IntPoint(y=content_canvas_origin[0], x=round(content_canvas_origin[1] - visible_length * amount))
                self.__scroll_area_canvas_item.update_content_origin(new_content_origin)

    def adjust_content_origin(self, canvas_length: int, visible_length: int, content_length: int, content_origin: int, mouse_offset: int) -> int:
        """
            Return the adjusted content offset.

            The canvas_length is the size of the canvas of the scroll bar.

            The visible_length is the size of the visible area of the scroll area.

            The content_length is the size of the content of the scroll area.

            The content_origin is the position of the content within the scroll area. It
            will always be negative or zero.

            The mouse_offset is the offset of the mouse.
        """
        scroll_range = max(content_length - visible_length, 0)
        thumb_position_length = get_thumb_position_and_length(canvas_length, visible_length, content_length, content_origin)
        offset_rel = int(scroll_range * float(mouse_offset) / (canvas_length - thumb_position_length.length))
        return max(min(content_origin - offset_rel, 0), -scroll_range)

    def mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.__tracking:
            pos = Geometry.IntPoint(x=x, y=y)
            canvas_size = self.canvas_size
            scroll_area_canvas_size = self.__scroll_area_canvas_item.canvas_size
            if canvas_size and scroll_area_canvas_size:
                scroll_area_content_canvas_size = self.__scroll_area_canvas_item.content_size
                if scroll_area_content_canvas_size:
                    tracking_content_origin = self.__tracking_content_origin
                    if tracking_content_origin and scroll_area_content_canvas_size:
                        if self.__orientation == Orientation.Vertical:
                            mouse_offset_v = pos.y - self.__tracking_start.y
                            visible_height = scroll_area_canvas_size[0]
                            content_height = scroll_area_content_canvas_size[0]
                            new_content_origin_v = self.adjust_content_origin(canvas_size[0], visible_height, content_height, tracking_content_origin[0], mouse_offset_v)
                            new_content_origin = Geometry.IntPoint(x=tracking_content_origin[1], y=new_content_origin_v)
                        else:
                            mouse_offset_h = pos.x - self.__tracking_start.x
                            visible_width = scroll_area_canvas_size[1]
                            content_width = scroll_area_content_canvas_size[1]
                            new_content_origin_h = self.adjust_content_origin(canvas_size[1], visible_width, content_width, tracking_content_origin[1], mouse_offset_h)
                            new_content_origin = Geometry.IntPoint(x=new_content_origin_h, y=tracking_content_origin[0])
                        if self.__scroll_area_canvas_item.update_content_origin(new_content_origin):
                            self.update()
        return super().mouse_position_changed(x, y, modifiers)


class CanvasWidgetSection:

    def draw(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        raise NotImplementedError()


class CanvasWidgetCanvasItem(LayerCanvasItem):
    """Internal class to represent a composition with a canvas widget."""

    @property
    @abc.abstractmethod
    def canvas_widget(self) -> UserInterface.CanvasWidget: ...

    @property
    @abc.abstractmethod
    def focused_item(self) -> typing.Optional[AbstractCanvasItem]: ...

    @abc.abstractmethod
    def size_changed(self, width: int, height: int) -> None: ...

    @abc.abstractmethod
    def get_section_ref(self) -> CanvasWidgetSection: ...


RootLayoutRender = "root"


class RootCanvasItem(CanvasWidgetCanvasItem):
    """A root layer to interface to the widget world.

    The root canvas item acts as a bridge between the higher level ui widget and a canvas hierarchy. It connects size
    notifications, mouse activity, keyboard activity, focus activity, and drag and drop actions to the canvas item.

    The root canvas item provides a canvas_widget property which is the canvas widget associated with this root item.

    The root canvas may be focusable or not. There are two focus states that this root canvas item handles: the widget
    focus and the canvas item focus. The widget focus comes from the enclosing widget. If this root canvas item has a
    widget focus, then it can also have a canvas item focus to specify which specific canvas item is the focus in this
    root canvas item's hierarchy.
    """

    next_section_id = 0

    def __init__(self, canvas_widget: UserInterface.CanvasWidget, **kwargs: typing.Any) -> None:
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
        self.__canvas_widget.on_can_dispatch_any = self.__can_dispatch_any
        self.__canvas_widget.on_get_menu_item_state = self.__get_menu_item_state
        setattr(self.__canvas_widget, "_root_canvas_item", weakref.ref(self))  # for debugging
        self.__drawing_context_updated = False
        self.__interaction_count = 0
        self.__focused_item: typing.Optional[AbstractCanvasItem] = None
        self.__last_focused_item: typing.Optional[AbstractCanvasItem] = None
        self.__mouse_canvas_item: typing.Optional[AbstractCanvasItem] = None  # not None when the mouse is pressed
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item: typing.Optional[AbstractCanvasItem] = None
        self.__request_focus_canvas_item: typing.Optional[AbstractCanvasItem] = None
        self.__request_focus_modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None  # modifiers at the time of mouse press
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item: typing.Optional[AbstractCanvasItem] = None
        self.__grab_canvas_item: typing.Optional[MouseTrackingCanvasItem.TrackingCanvasItem] = None
        self._set_canvas_origin(Geometry.IntPoint())

    def close(self) -> None:
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
        super().close()
        # culling will require the canvas widget; clear it here (after close) so that it is availahle.
        self.__canvas_widget = typing.cast(typing.Any, None)

    def get_composer(self, cache: ComposerCache) -> typing.Optional[BaseComposer]:
        # layer overrides this; need to override here to implement it as it would be implemented in the parent class
        # of the layer.
        return self._get_composer_inner(cache)

    def _update_layout_from_composer(self, canvas_bounds: Geometry.IntRect) -> None:
        # for the root canvas item, the size is determined from the canvas widget. a race condition can occur when
        # the canvas widget changes size and triggers a layout and then during layout another size change occurs.
        # when the layout finishes, it will call this method and normally update the size of the canvas item,
        # overriding the second size change. to avoid this, we do not update the size from the composer.
        # for backwards compatibility with tests, also override the test-only methods below and explicitly
        # call the super method that has been bypassed here.
        pass

    def update_layout(self, canvas_origin: typing.Optional[Geometry.IntPoint], canvas_size: typing.Optional[Geometry.IntSize]) -> None:
        # TEST ONLY
        canvas_rect = Geometry.IntRect(canvas_origin or (0, 0), canvas_size or (0, 0))
        self.update_layout_using_composer(canvas_rect)
        super()._update_layout_from_composer(canvas_rect)

    def update_layout_using_composer_immediate(self, canvas_rect: Geometry.IntRect) -> None:
        # TEST ONLY
        super().update_layout_using_composer_immediate(canvas_rect)
        super()._update_layout_from_composer(canvas_rect)

    def _repaint_layer_inner(self, drawing_context: DrawingContext.DrawingContext) -> None:
        # layer introduces this; need to override here so that root items use regular repaint and not the non-root
        # layer painting. items under non-root layer have layout specific to the layer, but root children can use
        # regular layout.
        super()._repaint(drawing_context)

    def _repaint_finished(self, drawing_context: DrawingContext.DrawingContext) -> None:
        self.__canvas_widget.draw(drawing_context)

    def get_section_ref(self) -> CanvasWidgetSection:
        """Return a section ref object for direct top level drawing.

        The section can be removed for efficiency by eliminating all references to the section ref.
        """

        class RootCanvasWidgetSection(CanvasWidgetSection):
            def __init__(self, root_canvas_item: RootCanvasItem, section_id: int) -> None:
                self.__root_canvas_item_ref = weakref.ref(root_canvas_item)
                self._section_id = section_id

                def finalize(root_canvas_item_ref: weakref.ReferenceType[RootCanvasItem]) -> None:
                    root_canvas_item = root_canvas_item_ref()
                    if root_canvas_item:
                        root_canvas_item.canvas_widget.remove_section(section_id)

                weakref.finalize(self, finalize, self.__root_canvas_item_ref)

            def draw(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
                root_canvas_item = self.__root_canvas_item_ref()
                if root_canvas_item:
                    root_canvas_item.canvas_widget.draw_section(self._section_id, drawing_context, canvas_rect)

        RootCanvasItem.next_section_id += 1

        return RootCanvasWidgetSection(self, RootCanvasItem.next_section_id)

    @property
    def root_container(self) -> typing.Optional[RootCanvasItem]:
        return self

    @property
    def canvas_widget(self) -> UserInterface.CanvasWidget:
        """ Return the canvas widget. """
        return self.__canvas_widget

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return self.__canvas_widget.map_to_global(p)

    @property
    def is_ui_interaction_active(self) -> bool:
        return self.__interaction_count > 0

    def _adjust_ui_interaction(self, value: int) -> None:
        self.__interaction_count += value

    class UIInteractionContext:
        def __init__(self, root_canvas_item: RootCanvasItem) -> None:
            self.__root_canvas_item = root_canvas_item

        def close(self) -> None:
            self.__root_canvas_item._adjust_ui_interaction(-1)

        def __enter__(self) -> RootCanvasItem.UIInteractionContext:
            self.__root_canvas_item._adjust_ui_interaction(1)
            return self

        def __exit__(self, exception_type: typing.Optional[typing.Type[BaseException]],
                     value: typing.Optional[BaseException], traceback: typing.Optional[types.TracebackType]) -> typing.Optional[bool]:
            self.close()
            return None

    def _ui_interaction(self) -> contextlib.AbstractContextManager[RootCanvasItem.UIInteractionContext]:
        return RootCanvasItem.UIInteractionContext(self)

    @property
    def focusable(self) -> bool:
        """ Return whether the canvas widget is focusable. """
        return self.canvas_widget.focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        """ Set whether the canvas widget is focusable. """
        self.canvas_widget.focusable = focusable

    def size_changed(self, width: int, height: int) -> None:
        """ Called when size changes. """
        if width > 0 and height > 0:
            self._set_canvas_origin(Geometry.IntPoint())
            self._set_canvas_size(Geometry.IntSize(height=height, width=width))

    @property
    def focused_item(self) -> typing.Optional[AbstractCanvasItem]:
        """
            Return the canvas focused item. May return None.

            The focused item is either this item itself or one of its
            children.
        """
        return self.__focused_item

    def _set_focused_item(self, focused_item: typing.Optional[AbstractCanvasItem], p: typing.Optional[Geometry.IntPoint] = None, modifiers: typing.Optional[UserInterface.KeyboardModifiers] = None) -> None:
        """ Set the canvas focused item. This will also update the focused property of both old item (if any) and new item (if any). """
        if not modifiers or not modifiers.any_modifier:
            if focused_item != self.__focused_item:
                if self.__focused_item:
                    self.__focused_item._set_focused(False)
                self.__focused_item = focused_item
                if self.__focused_item:
                    self.__focused_item._set_focused(True)
            if self.__focused_item:
                self.__last_focused_item = self.__focused_item
        elif focused_item:
            focused_item.adjust_secondary_focus(p or Geometry.IntPoint(), modifiers)

    def __focus_changed(self, focused: bool) -> None:
        """ Called when widget focus changes. """
        if focused and not self.focused_item:
            self._set_focused_item(self.__last_focused_item)
        elif not focused and self.focused_item:
            self._set_focused_item(None)

    def _request_root_focus(self, focused_item: typing.Optional[AbstractCanvasItem], p: typing.Optional[Geometry.IntPoint], modifiers: typing.Optional[UserInterface.KeyboardModifiers]) -> None:
        """Requests that the root widget gets focus.

        This focused is different from the focus within the canvas system. This is
        the external focus in the widget system.

        If the canvas widget is already focused, this simply sets the focused item
        to be the requested one. Otherwise, the widget has to request focus. When
        it receives focus, a __focus_changed from the widget which will restore the
        last focused item to be the new focused canvas item.
        """
        if self.__canvas_widget.focused:
            self._set_focused_item(focused_item, p, modifiers)
        else:
            self._set_focused_item(None, p, modifiers)
            self.__last_focused_item = focused_item
            self.__canvas_widget.focused = True  # this will trigger focus changed to set the focus

    def wheel_changed(self, x: int, y: int, dx: int, dy: int, is_horizontal: bool) -> bool:
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

    def __dispatch_any(self, method: str, *args: typing.Any, **kwargs: typing.Any) -> bool:
        focused_item = self.focused_item
        if focused_item:
            return focused_item._dispatch_any(method, *args, **kwargs)
        return False

    def __can_dispatch_any(self, method: str) -> bool:
        focused_item = self.focused_item
        if focused_item:
            return focused_item._can_dispatch_any(method)
        return False

    def __get_menu_item_state(self, command_id: str) -> typing.Optional[UserInterface.MenuItemState]:
        focused_item = self.focused_item
        if focused_item:
            menu_item_state = focused_item._get_menu_item_state(command_id)
            if menu_item_state:
                return menu_item_state
        return None

    def _cursor_shape_changed(self, item: AbstractCanvasItem) -> None:
        if item == self.__mouse_tracking_canvas_item and self.__mouse_tracking_canvas_item:
            self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)

    def _restore_cursor_shape(self) -> None:
        # if self.__mouse_tracking_canvas_item:
        #     self.__canvas_widget.set_cursor_shape(self.__mouse_tracking_canvas_item.cursor_shape)
        # else:
        self.__canvas_widget.set_cursor_shape(None)

    def __mouse_entered(self) -> None:
        self.__mouse_tracking = True

    def __mouse_exited(self) -> None:
        if self.__mouse_tracking_canvas_item:
            self.__mouse_tracking_canvas_item.mouse_exited()
        self.__mouse_tracking = False
        self.__mouse_tracking_canvas_item = None
        self.__canvas_widget.set_cursor_shape(None)
        self.__canvas_widget.tool_tip = None

    def __mouse_canvas_item_at_point(self, x: int, y: int) -> typing.Optional[AbstractCanvasItem]:
        if self.__mouse_canvas_item:
            return self.__mouse_canvas_item
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            if canvas_item.wants_mouse_events:
                return canvas_item
        return None

    def __request_focus(self, canvas_item: AbstractCanvasItem, p: Geometry.IntPoint, modifiers: UserInterface.KeyboardModifiers) -> None:
        canvas_item_: typing.Optional[AbstractCanvasItem] = canvas_item
        while canvas_item_:
            if canvas_item_.focusable:
                canvas_item_._request_focus(p, modifiers)
                break
            canvas_item_ = canvas_item_.container

    def __mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        with self._ui_interaction():
            canvas_item = self.__mouse_canvas_item_at_point(x, y)
            if canvas_item:
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
                return canvas_item.mouse_clicked(canvas_item_point.x, canvas_item_point.y, modifiers)
            return False

    def __mouse_double_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        with self._ui_interaction():
            canvas_item = self.__mouse_canvas_item_at_point(x, y)
            if canvas_item:
                self.__request_focus(canvas_item, Geometry.IntPoint(x=x, y=y), modifiers)
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
                return canvas_item.mouse_double_clicked(canvas_item_point.x, canvas_item_point.y, modifiers)
            return False

    def __mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._adjust_ui_interaction(1)
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
            self.__request_focus_modifiers = modifiers
            return self.__mouse_canvas_item.mouse_pressed(canvas_item_point.x, canvas_item_point.y, modifiers)
        return False

    def __mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        result = False
        if self.__mouse_canvas_item:
            if self.__request_focus_canvas_item:
                # pass the modifiers at the time of the mouse press to request focus. this avoids issues where
                # the user clicks to start a drag operation such as creating a rectangle and then holds shift
                # to modify that drag operation, i.e. shift to make rectangle square. if this code is reached,
                # it means no tool has claimed the mouse released operation and so focus should be requested, but
                # the request focus should only utilize the modifiers down at the start of the operation.
                assert self.__request_focus_modifiers  # this is the result of a mouse click, so should always be set
                self.__request_focus(self.__request_focus_canvas_item, Geometry.IntPoint(x=x, y=y), self.__request_focus_modifiers)
                self.__request_focus_canvas_item = None
            canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__mouse_canvas_item)
            result = self.__mouse_canvas_item.mouse_released(canvas_item_point.x, canvas_item_point.y, modifiers)
            self.__mouse_canvas_item = None
            self.__mouse_position_changed(x, y, modifiers)
        self._adjust_ui_interaction(-1)
        return result

    def bypass_request_focus(self) -> None:
        self.__request_focus_canvas_item = None

    def __mouse_position_changed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
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

    def __grabbed_mouse_position_changed(self, dx: int, dy: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        if self.__grab_canvas_item:
            self.__grab_canvas_item.grabbed_mouse_position_changed(dx, dy, modifiers)

    def __context_menu_event(self, x: int, y: int, gx: int, gy: int) -> bool:
        with self._ui_interaction():
            canvas_items = self.canvas_items_at_point(x, y)
            for canvas_item in canvas_items:
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), canvas_item)
                if canvas_item.context_menu_event(canvas_item_point.x, canvas_item_point.y, gx, gy):
                    return True
            return False

    def __key_pressed(self, key: UserInterface.Key) -> bool:
        self._adjust_ui_interaction(1)
        if self.focused_item:
            return self.focused_item.key_pressed(key)
        return False

    def __key_released(self, key: UserInterface.Key) -> bool:
        result = False
        if self.focused_item:
            result = self.focused_item.key_released(key)
        self._adjust_ui_interaction(-1)
        return result

    def __drag_enter(self, mime_data: UserInterface.MimeData) -> str:
        self.__drag_tracking = True
        return "accept"

    def __drag_leave(self) -> str:
        if self.__drag_tracking_canvas_item:
            self.__drag_tracking_canvas_item.drag_leave()
        self.__drag_tracking = False
        self.__drag_tracking_canvas_item = None
        return "accept"

    def __drag_canvas_item_at_point(self, x: int, y: int, mime_data: UserInterface.MimeData) -> typing.Optional[AbstractCanvasItem]:
        canvas_items = self.canvas_items_at_point(x, y)
        for canvas_item in canvas_items:
            if canvas_item.wants_drag_event(mime_data, x, y):
                return canvas_item
        return None

    def __drag_move(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
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

    def __drop(self, mime_data: UserInterface.MimeData, x: int, y: int) -> str:
        with self._ui_interaction():
            response = "ignore"
            if self.__drag_tracking_canvas_item:
                canvas_item_point = self.map_to_canvas_item(Geometry.IntPoint(y=y, x=x), self.__drag_tracking_canvas_item)
                response = self.__drag_tracking_canvas_item.drop(mime_data, canvas_item_point.x, canvas_item_point.y)
            self.__drag_leave()
            return response

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[Bitmap.BitmapOrArray] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self.__canvas_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def grab_gesture(self, gesture_type: str) -> None:
        """ Grab gesture """
        self._adjust_ui_interaction(1)
        self.__canvas_widget.grab_gesture(gesture_type)

    def release_gesture(self, gesture_type: str) -> None:
        """ Ungrab gesture """
        self.__canvas_widget.release_gesture(gesture_type)
        self._adjust_ui_interaction(-1)

    def grab_mouse(self, grabbed_canvas_item: MouseTrackingCanvasItem.TrackingCanvasItem, gx: int, gy: int) -> None:
        self._adjust_ui_interaction(1)
        self.__canvas_widget.grab_mouse(gx, gy)
        self.__grab_canvas_item = grabbed_canvas_item

    def release_mouse(self) -> None:
        self.__canvas_widget.release_mouse()
        self._restore_cursor_shape()
        self.__grab_canvas_item = None
        self._adjust_ui_interaction(-1)

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        self.__canvas_widget.show_tool_tip_text(text, gx, gy)

    def hide_tool_tip_text(self) -> None:
        self.__canvas_widget.hide_tool_tip_text()


class BackgroundCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, composer_cache: ComposerCache, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__background_color = background_color

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        if self.__background_color:
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.rect(canvas_rect.left, canvas_rect.top, canvas_rect.width, canvas_rect.height)
                drawing_context.fill_style = self.__background_color
                drawing_context.fill()


class BackgroundCanvasItem(AbstractCanvasItem):
    """ Canvas item to draw background_color.

    The fallback color is used if the background color is None. The fallback color may also be None, in which case
    nothing is drawn. However, for backwards compatibility, the default fallback color is gray.
    """
    def __init__(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None, fallback_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = "#888") -> None:
        super().__init__()
        self.__background_color = background_color
        self.__fallback_color = fallback_color

    @property
    def background_color(self) -> typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]:
        return self.__background_color

    @background_color.setter
    def background_color(self, value: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.__background_color = value
        self.update()

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return BackgroundCanvasItemComposer(self, self.layout_sizing, composer_cache, self.background_color or self.__fallback_color)


@dataclasses.dataclass
class CellBorderProperties:
    color: Color.Color = Color.Color()
    style: str = "solid"
    width: float = 1.0


class CellBorder:
    border: typing.Optional[CellBorderProperties] = None
    border_horizontal: typing.Optional[CellBorderProperties] = None
    border_vertical: typing.Optional[CellBorderProperties] = None
    border_top: typing.Optional[CellBorderProperties] = None
    border_left: typing.Optional[CellBorderProperties] = None
    border_bottom: typing.Optional[CellBorderProperties] = None
    border_right: typing.Optional[CellBorderProperties] = None

    def clear(self) -> None:
        self.border = None
        self.border_horizontal = None
        self.border_vertical = None
        self.border_top = None
        self.border_left = None
        self.border_bottom = None
        self.border_right = None


class CellLike(typing.Protocol):
    # PRIVATE CLASS. DO NOT USE OUTSIDE NIONUI

    update_event: Event.Event

    @property
    def background_color(self) -> typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]: raise NotImplementedError()

    @background_color.setter
    def background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None: ...

    @property
    def border_color(self) -> typing.Optional[str]: raise NotImplementedError()

    @border_color.setter
    def border_color(self, border_color: typing.Optional[str]) -> None: ...

    @property
    def border(self) -> CellBorder: raise NotImplementedError()

    @border.setter
    def border(self, border: CellBorder) -> None: ...

    @property
    def padding(self) -> Geometry.IntSize: raise NotImplementedError()

    @padding.setter
    def padding(self, padding: typing.Optional[Geometry.IntSize]) -> None: ...

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize: ...

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None: ...


class Cell(CellLike):
    # PRIVATE CLASS. DO NOT USE OUTSIDE NIONUI

    def __init__(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None, border: typing.Optional[CellBorder] = None,
                 padding: typing.Optional[Geometry.IntSize] = None) -> None:
        self.__background_color = background_color
        self.__border = border or CellBorder()
        self.__padding = padding or Geometry.IntSize(4, 4)
        self.update_event = Event.Event()

    def _update(self) -> None:
        self.update_event.fire()

    @property
    def background_color(self) -> typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]:
        return self.__background_color

    @background_color.setter
    def background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.__background_color = background_color
        self._update()

    @property
    def border_color(self) -> typing.Optional[str]:
        return self.__border.border.color.color_str if self.__border.border else None

    @border_color.setter
    def border_color(self, border_color: typing.Optional[str]) -> None:
        self.__border.clear()
        if border_color:
            self.__border.border = CellBorderProperties(Color.Color(border_color))
        self._update()

    @property
    def border(self) -> CellBorder:
        return self.__border

    @border.setter
    def border(self, border: CellBorder) -> None:
        self.__border = border
        self._update()

    @property
    def padding(self) -> Geometry.IntSize:
        return self.__padding

    @padding.setter
    def padding(self, padding: typing.Optional[Geometry.IntSize]) -> None:
        self.__padding = padding or Geometry.IntSize()
        self._update()

    def _size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize:
        raise NotImplementedError()

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize:
        return self._size_to_content(get_font_metrics_fn)

    def _get_background_and_overlay_colors(self, style: typing.Set[str]) -> typing.Tuple[typing.Optional[typing.Union[str, DrawingContext.LinearGradient]], typing.Optional[str]]:
        background_color = self.__background_color
        overlay_color = None
        # configure based on style
        if "disabled" in style:
            overlay_color = Color.Color("gray").to_color_with_alpha(0.33).color_str
            if "checked" in style:
                background_color = "rgb(64, 64, 64)"
        else:
            if "checked" in style:
                background_color = "rgb(192, 192, 192)"
            if "active" in style:
                overlay_color = "rgba(128, 128, 128, 0.5)"
            elif "hover" in style:
                overlay_color = "rgba(128, 128, 128, 0.1)"
        return background_color, overlay_color

    def _paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None:
        pass

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None:
        background_color, overlay_color = self._get_background_and_overlay_colors(style)

        padding = self.__padding
        dest_rect = Geometry.FloatRect.from_tlbr(
            rect.top + padding.height,
            rect.left + padding.width,
            rect.bottom - padding.height,
            rect.right - padding.width
        )

        rect_args = rect.left, rect.top, rect.width, rect.height

        # draw the background
        if background_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = background_color
            drawing_context.fill()

        self._paint_cell(drawing_context, dest_rect, style)

        # draw the overlay style
        if overlay_color:
            drawing_context.begin_path()
            drawing_context.rect(*rect_args)
            drawing_context.fill_style = overlay_color
            drawing_context.fill()

        # draw the border
        border_rect = rect
        if self.__border.border:
            border_width = self.__border.border.width
            drawing_context.begin_path()
            drawing_context.rect(border_rect.left, border_rect.top, border_rect.width, border_rect.height)
            drawing_context.line_width = border_width
            drawing_context.stroke_style = self.__border.border.color.color_str if self.__border.border.color else None
            drawing_context.stroke()
        else:
            if self.__border.border_horizontal:
                border_width = self.__border.border_horizontal.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.left, border_rect.top)
                drawing_context.line_to(border_rect.right, border_rect.top)
                drawing_context.move_to(border_rect.left, border_rect.bottom)
                drawing_context.line_to(border_rect.right, border_rect.bottom)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_horizontal.color.color_str if self.__border.border_horizontal.color else None
                drawing_context.stroke()
            if self.__border.border_vertical:
                border_width = self.__border.border_vertical.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.left, border_rect.top)
                drawing_context.line_to(border_rect.left, border_rect.bottom)
                drawing_context.move_to(border_rect.right, border_rect.top)
                drawing_context.line_to(border_rect.right, border_rect.bottom)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_vertical.color.color_str if self.__border.border_vertical.color else None
                drawing_context.stroke()
            if self.__border.border_top:
                border_width = self.__border.border_top.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.left, border_rect.top)
                drawing_context.line_to(border_rect.right, border_rect.top)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_top.color.color_str if self.__border.border_top.color else None
                drawing_context.stroke()
            if self.__border.border_left:
                border_width = self.__border.border_left.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.left, border_rect.top)
                drawing_context.line_to(border_rect.left, border_rect.bottom)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_left.color.color_str if self.__border.border_left.color else None
                drawing_context.stroke()
            if self.__border.border_bottom:
                border_width = self.__border.border_bottom.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.left, border_rect.bottom)
                drawing_context.line_to(border_rect.right, border_rect.bottom)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_bottom.color.color_str if self.__border.border_bottom.color else None
                drawing_context.stroke()
            if self.__border.border_right:
                border_width = self.__border.border_right.width
                drawing_context.begin_path()
                drawing_context.move_to(border_rect.right, border_rect.top)
                drawing_context.line_to(border_rect.right, border_rect.bottom)
                drawing_context.line_width = border_width
                drawing_context.stroke_style = self.__border.border_right.color.color_str if self.__border.border_right.color else None
                drawing_context.stroke()

            if False:  # for debugging
                drawing_context.begin_path()
                drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                drawing_context.line_width = 1.0
                drawing_context.stroke_style = "red"
                drawing_context.stroke()


class CellCanvasItemComposer(BaseComposer):

    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, cell: CellLike, style: typing.Set[str]) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__cell = cell
        self.__style = style

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        with drawing_context.saver():
            self.__cell.paint_cell(drawing_context, canvas_rect.to_float_rect(), self.__style)


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

    def __init__(self, cell: typing.Optional[CellLike] = None) -> None:
        super().__init__()
        self.__enabled = True
        self.__check_state = "unchecked"
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.__cell: typing.Optional[CellLike] = None
        self.__cell_update_event_listener: typing.Optional[Event.EventListener] = None
        self.cell = cell
        self.style: typing.Set[str] = set()
        # on_button_clicked is deprecated; use on_clicked instead
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_button_clicked = None
        self.on_clicked = None
        self.cell = None
        super().close()

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if self.__enabled != value:
            self.__enabled = value
            self.__update_style()

    @property
    def check_state(self) -> str:
        return self.__check_state

    @check_state.setter
    def check_state(self, value: str) -> None:
        assert value in ["checked", "unchecked", "partial"]
        if self.__check_state != value:
            self.__check_state = value
            self.__update_style()

    @property
    def checked(self) -> bool:
        return self.check_state == "checked"

    @checked.setter
    def checked(self, value: bool) -> None:
        self.check_state = "checked" if value else "unchecked"

    @property
    def background_color(self) -> typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]:
        return self.__cell.background_color if self.__cell else None

    @background_color.setter
    def background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        if self.__cell:
            self.__cell.background_color = background_color

    @property
    def border_color(self) -> typing.Optional[str]:
        return self.__cell.border_color if self.__cell else None

    @border_color.setter
    def border_color(self, border_color: typing.Optional[str]) -> None:
        if self.__cell:
            self.__cell.border_color = border_color

    @property
    def border(self) -> CellBorder:
        return self.__cell.border if self.__cell else CellBorder()

    @border.setter
    def border(self, border: CellBorder) -> None:
        if self.__cell:
            self.__cell.border = copy.deepcopy(border)

    @property
    def padding(self) -> Geometry.IntSize:
        return self.__cell.padding if self.__cell else Geometry.IntSize()

    @padding.setter
    def padding(self, padding: typing.Optional[Geometry.IntSize]) -> None:
        if self.__cell:
            self.__cell.padding = padding or Geometry.IntSize()

    @property
    def _mouse_inside(self) -> bool:
        return self.__mouse_inside

    @_mouse_inside.setter
    def _mouse_inside(self, value: bool) -> None:
        self.__mouse_inside = value
        self.__update_style()

    @property
    def _mouse_pressed(self) -> bool:
        return self.__mouse_pressed

    @_mouse_pressed.setter
    def _mouse_pressed(self, value: bool) -> None:
        self.__mouse_pressed = value
        self.__update_style()

    def __update_style(self) -> None:
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
    def cell(self) -> typing.Optional[CellLike]:
        return self.__cell

    @cell.setter
    def cell(self, new_cell: typing.Optional[CellLike]) -> None:
        if self.__cell_update_event_listener:
            self.__cell_update_event_listener.close()
            self.__cell_update_event_listener = None
        self.__cell = new_cell
        if self.__cell:
            self.__cell_update_event_listener = self.__cell.update_event.listen(self.update)

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        """ Size the canvas item to the text content with padding."""
        new_size = self.cell.size_to_content(get_font_metrics_fn) if self.cell else Geometry.IntSize()
        new_sizing = self.sizing
        padding = self.padding
        # if size is 0 in either dimension, do not pad that dimension. this is a backwards compatibility issue
        # to avoid drawing dimmed disabled items with no content ("Scan/Abort" in device control panels).
        new_sizing = new_sizing.with_fixed_width(new_size.width + (padding.width * 2 if new_size.width else 0))
        new_sizing = new_sizing.with_fixed_height(new_size.height + (padding.height * 2 if new_size.height else 0))
        self.update_sizing(new_sizing)

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        if cell := self.cell:
            return CellCanvasItemComposer(self, self.layout_sizing, composer_cache, cell, self.style)
        return None

    def mouse_entered(self) -> bool:
        if self.wants_mouse_events:
            self._mouse_inside = True
            return True
        return super().mouse_entered()

    def mouse_exited(self) -> bool:
        if self.wants_mouse_events:
            self._mouse_inside = False
            return True
        return super().mouse_exited()

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.wants_mouse_events:
            self._mouse_pressed = True
            return True
        return super().mouse_pressed(x, y, modifiers)

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.wants_mouse_events:
            self._mouse_pressed = False
            return True
        return super().mouse_released(x, y, modifiers)

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.wants_mouse_events:
            if self.enabled:
                if callable(self.on_button_clicked):
                    self.on_button_clicked()
                if callable(self.on_clicked):
                    self.on_clicked()
            return True
        return super().mouse_clicked(x, y, modifiers)


class TextButtonCell(Cell):

    def __init__(self, text: typing.Optional[str] = None, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border: typing.Optional[CellBorder] = None, padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__(background_color, border, padding)
        self.__text = text if text is not None else str()
        self.__text_color: typing.Optional[str] = None
        self.__text_font: typing.Optional[str] = None

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        text = text if text is not None else str()
        if self.__text != text:
            self.__text = text
            self._update()

    @property
    def text_color(self) -> typing.Optional[str]:
        return self.__text_color

    @text_color.setter
    def text_color(self, value: typing.Optional[str]) -> None:
        if self.__text_color != value:
            self.__text_color = value
            self._update()

    @property
    def text_font(self) -> typing.Optional[str]:
        return self.__text_font

    @text_font.setter
    def text_font(self, value: typing.Optional[str]) -> None:
        if self.__text_font != value:
            self.__text_font = value
            self._update()

    def _size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize:
        """ Size the canvas item to the text content without padding."""
        text_font = self.text_font or "12px"
        font_metrics = get_font_metrics_fn(text_font, self.text)
        return Geometry.IntSize(width=font_metrics.width, height=font_metrics.height)

    def _paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None:
        if self.__text:
            text_font = self.text_font or "12px"
            text_color = self.__text_color or "black"
            drawing_context.font = text_font
            drawing_context.text_baseline = "middle"
            drawing_context.text_align = "center"
            drawing_context.fill_style = text_color
            drawing_context.fill_text(self.__text, rect.center.x, rect.center.y + 1)


class TextCanvasItem(CellCanvasItem):

    def __init__(self, text: typing.Optional[str] = None, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border_color: typing.Optional[str] = None, padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__()
        border = CellBorder()
        if border_color:
            border.border = CellBorderProperties(Color.Color(border_color))
        self.__text_cell = TextButtonCell(text, background_color, border, padding)
        self.cell = self.__text_cell

    def _description(self) -> str:
        return self.__class__.__name__ + f" '{self.text}'"

    @property
    def _text_cell(self) -> TextButtonCell:
        return self.__text_cell

    @property
    def text(self) -> str:
        return self.__text_cell.text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_cell.text = text or str()

    @property
    def text_color(self) -> typing.Optional[str]:
        return self.__text_cell.text_color

    @text_color.setter
    def text_color(self, text_color: typing.Optional[str]) -> None:
        self.__text_cell.text_color = text_color

    @property
    def text_font(self) -> typing.Optional[str]:
        return self.__text_cell.text_font

    @text_font.setter
    def text_font(self, text_font: typing.Optional[str]) -> None:
        self.__text_cell.text_font = text_font

    @property
    def border_enabled(self) -> bool:
        return self.border_color is not None

    @border_enabled.setter
    def border_enabled(self, value: bool) -> None:
        if value:
            self.border_color = self.border_color or "black"
        else:
            self.border_color = None


class TextButtonCanvasItem(TextCanvasItem):

    def __init__(self, text: typing.Optional[str] = None, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border_color: typing.Optional[str] = None, padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__(text, background_color, border_color, padding)
        self.wants_mouse_events = True


class TwistDownCell(Cell):

    def __init__(self) -> None:
        super().__init__()

    def _size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize:
        return Geometry.IntSize(height=18, width=16)

    def _get_background_and_overlay_colors(self, style: typing.Set[str]) -> typing.Tuple[typing.Optional[typing.Union[str, DrawingContext.LinearGradient]], typing.Optional[str]]:
        return None, super()._get_background_and_overlay_colors(style)[1]

    def _paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None:
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

        drawing_context.fill_style = "#444"
        drawing_context.fill()
        drawing_context.stroke_style = "#444"
        drawing_context.stroke()


class TwistDownCanvasItem(CellCanvasItem):

    def __init__(self) -> None:
        super().__init__(TwistDownCell())
        self.wants_mouse_events = True


class BitmapCell(Cell):

    def __init__(self, bitmap: typing.Optional[Bitmap.Bitmap],
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border: typing.Optional[CellBorder] = None,
                 padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__(background_color, border, padding)
        if bitmap:
            assert isinstance(bitmap, Bitmap.Bitmap)
        self.__bitmap = bitmap
        self.__data: typing.Optional[DrawingContext.GrayscaleF32Type] = None
        self.__display_limits: typing.Optional[typing.Tuple[float, float]] = None
        self.__color_map_data: typing.Optional[DrawingContext.RGBA32Type] = None

    def set_bitmap(self, bitmap: Bitmap.Bitmap, trigger_update: bool = True) -> None:
        if bitmap:
            assert isinstance(bitmap, Bitmap.Bitmap)
        self.__bitmap = bitmap
        self.__data = None
        self.__display_limits = None
        self.__color_map_data = None
        if trigger_update:
            self._update()

    def set_data(self, data: typing.Optional[DrawingContext.GrayscaleF32Type],
                 display_limits: typing.Optional[typing.Tuple[float, float]],
                 color_map_data: typing.Optional[DrawingContext.RGBA32Type], trigger_update: bool = True) -> None:
        self.__bitmap = None
        self.__data = data
        self.__display_limits = display_limits
        self.__color_map_data = color_map_data
        if trigger_update:
            self._update()

    @property
    def data(self) -> typing.Optional[DrawingContext.GrayscaleF32Type]:
        return self.__data

    @property
    def bitmap(self) -> typing.Optional[Bitmap.Bitmap]:
        return self.__bitmap

    @bitmap.setter
    def bitmap(self, bitmap: Bitmap.Bitmap) -> None:
        self.set_bitmap(bitmap)

    def _size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> Geometry.IntSize:
        """ Size the canvas item to the text content without padding."""
        if self.__bitmap:
            return self.__bitmap.computed_shape
        if self.__data is not None:
            return Geometry.IntSize.make(typing.cast(Geometry.IntSizeTuple, self.__data.shape))
        return Geometry.IntSize()

    def _get_background_and_overlay_colors(self, style: typing.Set[str]) -> typing.Tuple[typing.Optional[typing.Union[str, DrawingContext.LinearGradient]], typing.Optional[str]]:
        # bitmaps are disabled by dimming them
        background_color, overlay_color = super()._get_background_and_overlay_colors(style)
        return background_color, None if "disabled" in style and "checked" not in style else overlay_color

    def _update_bitmap_data(self, bitmap_data: DrawingContext.RGBA32Type, style: typing.Set[str]) -> DrawingContext.RGBA32Type:
        if 'disabled' in style:
            bitmap_rgba = numpy.copy(numpy.array(bitmap_data, copy=False).view(numpy.uint8).reshape(bitmap_data.shape + (4,)))
            bitmap_gray_mix = 0.66
            bitmap_gray = (1.0 - bitmap_gray_mix) * 255 + bitmap_gray_mix * (0.0722 * bitmap_rgba[..., 0] + 0.7152 * bitmap_rgba[..., 1] + 0.2126 * bitmap_rgba[..., 2])
            bitmap_rgba[..., 0] = bitmap_gray
            bitmap_rgba[..., 1] = bitmap_gray
            bitmap_rgba[..., 2] = bitmap_gray
            return numpy.array(bitmap_rgba, copy=False).view(numpy.uint32).reshape(bitmap_rgba.shape[:-1])
        return bitmap_data

    def _paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: typing.Set[str]) -> None:
        # draw the bitmap
        if self.__bitmap and self.__bitmap.rgba_bitmap_data is not None:
            image_size = self.__bitmap.computed_shape
            if image_size.height > 0 and image_size.width > 0:
                display_rect = Geometry.fit_to_size(rect, image_size)
                display_height = display_rect.height
                display_width = display_rect.width
                if display_rect and display_width > 0 and display_height > 0:
                    display_top = display_rect.top
                    display_left = display_rect.left
                    drawing_context.draw_image(self._update_bitmap_data(self.__bitmap.rgba_bitmap_data, style), display_left, display_top, display_width, display_height)
        if self.__data is not None:
            image_size = Geometry.IntSize.make(typing.cast(Geometry.IntSizeTuple, self.__data.shape))
            if image_size.height > 0 and image_size.width > 0:
                display_rect = Geometry.fit_to_size(rect, image_size)
                display_height = display_rect.height
                display_width = display_rect.width
                if display_rect and display_width > 0 and display_height > 0:
                    display_top = display_rect.top
                    display_left = display_rect.left
                    display_limits = self.__display_limits or (0.0, 0.0)
                    color_map_data = self.__color_map_data
                    drawing_context.draw_data(self.__data, display_left, display_top, display_width, display_height, display_limits[0], display_limits[1], color_map_data)


class BitmapCanvasItem(CellCanvasItem):

    """ Canvas item to draw rgba bitmap in bgra uint32 ndarray format. """

    def __init__(self, *,
                 bitmap: typing.Optional[Bitmap.Bitmap] = None,
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border_color: typing.Optional[str] = None,
                 padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__()
        padding = padding or Geometry.IntSize()  # for backwards compatibility
        border = CellBorder()
        if border_color:
            border.border = CellBorderProperties(Color.Color(border_color))
        self.__bitmap_cell = BitmapCell(bitmap, background_color, border, padding)
        self.cell = self.__bitmap_cell

    def set_rgba_bitmap_data(self, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type], rgba_bitmap_shape: typing.Optional[Geometry.IntSize] = None, trigger_update: bool = True) -> None:
        self.__bitmap_cell.set_bitmap(Bitmap.Bitmap(rgba_bitmap_data=rgba_bitmap_data), trigger_update=trigger_update)

    def set_data(self, data: typing.Optional[DrawingContext.GrayscaleF32Type],
                 display_limits: typing.Optional[typing.Tuple[float, float]],
                 color_map_data: typing.Optional[DrawingContext.RGBA32Type], trigger_update: bool = True) -> None:
        self.__bitmap_cell.set_data(data, display_limits, color_map_data, trigger_update)

    @property
    def data(self) -> typing.Optional[DrawingContext.GrayscaleF32Type]:
        return self.__bitmap_cell.data

    @property
    def bitmap(self) -> typing.Optional[Bitmap.Bitmap]:
        return self.__bitmap_cell.bitmap

    @bitmap.setter
    def bitmap(self, bitmap: typing.Optional[Bitmap.Bitmap]) -> None:
        self.__bitmap_cell.bitmap = bitmap

    @property
    def rgba_bitmap_data(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__bitmap_cell.bitmap.rgba_bitmap_data if self.__bitmap_cell.bitmap else None

    @rgba_bitmap_data.setter
    def rgba_bitmap_data(self, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__bitmap_cell.bitmap = Bitmap.Bitmap(rgba_bitmap_data=rgba_bitmap_data)


class BitmapButtonCanvasItem(BitmapCanvasItem):
    """ Canvas item button to draw rgba bitmap in bgra uint32 ndarray format. """

    def __init__(self, bitmap: typing.Optional[Bitmap.BitmapOrArray] = None, *,
                 background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border_color: typing.Optional[str] = None,
                 padding: typing.Optional[Geometry.IntSize] = None) -> None:
        bitmap = Bitmap.promote_bitmap(bitmap)
        super().__init__(bitmap=bitmap, background_color=background_color, border_color=border_color, padding=padding)
        self.wants_mouse_events = True


class StaticTextCanvasItem(TextCanvasItem):
    # for backwards compatibility

    def __init__(self, text: typing.Optional[str] = None) -> None:
        super().__init__(text, padding=Geometry.IntSize(4, 4))

    @property
    def font(self) -> typing.Optional[str]:
        return self.text_font

    @font.setter
    def font(self, value: typing.Optional[str]) -> None:
        self.text_font = value


class CheckBoxCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache,
                    check_state: str, enabled: bool, mouse_inside: bool, mouse_pressed: bool,
                    text: str, text_color: str, text_disabled_color: str, font: str) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__check_state = check_state
        self.__enabled = enabled
        self.__mouse_inside = mouse_inside
        self.__mouse_pressed = mouse_pressed
        self.__text = text
        self.__text_color = text_color
        self.__text_disabled_color = text_disabled_color
        self.__font = font

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        canvas_size = canvas_rect.size
        check_state = self.__check_state
        enabled = self.__enabled
        mouse_inside = self.__mouse_inside
        mouse_pressed = self.__mouse_pressed
        font = self.__font
        text_color = self.__text_color
        text_disabled_color = self.__text_disabled_color
        text = self.__text
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            drawing_context.begin_path()
            tx = 4 + 14 + 4
            cx = 4 + 7
            cy = canvas_size.height * 0.5
            size = 14
            size_half = 7
            drawing_context.round_rect(4, cy - size_half, size, size, 4.0)
            if check_state in ("checked", "partial"):
                drawing_context.fill_style = "#FFF"
                drawing_context.fill()
            if enabled and mouse_inside and mouse_pressed:
                drawing_context.fill_style = "rgba(128, 128, 128, 0.5)"
                drawing_context.fill()
            elif enabled and mouse_inside:
                drawing_context.fill_style = "rgba(128, 128, 128, 0.1)"
                drawing_context.fill()
            drawing_context.stroke_style = "#000"
            drawing_context.line_width = 1.0
            drawing_context.stroke()
            if check_state == "checked":
                drawing_context.begin_path()
                drawing_context.move_to(cx - 3, cy - 2)
                drawing_context.line_to(cx + 0, cy + 2)
                drawing_context.line_to(cx + 8, cy - 9)
                drawing_context.stroke_style = "#000"
                drawing_context.line_width = 2.0
                drawing_context.stroke()
            elif check_state == "partial":
                drawing_context.begin_path()
                drawing_context.move_to(cx - 5, cy)
                drawing_context.line_to(cx + 5, cy)
                drawing_context.stroke_style = "#000"
                drawing_context.line_width = 2.0
                drawing_context.stroke()
            drawing_context.font = font
            drawing_context.text_align = 'left'
            drawing_context.text_baseline = 'middle'
            drawing_context.fill_style = text_color if enabled else text_disabled_color
            drawing_context.fill_text(text, tx, cy + 1)


class CheckBoxCanvasItem(AbstractCanvasItem):

    def __init__(self, text: typing.Optional[str] = None) -> None:
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
        self.on_checked_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None

    def close(self) -> None:
        self.on_checked_changed = None
        self.on_check_state_changed = None
        super().close()

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.__enabled = value
        self.update()

    @property
    def tristate(self) -> bool:
        return self.__tristate

    @tristate.setter
    def tristate(self, value: bool) -> None:
        self.__tristate = value
        if not self.__tristate:
            self.checked = self.check_state == "checked"
        self.update()

    @property
    def check_state(self) -> str:
        return self.__check_state

    @check_state.setter
    def check_state(self, value: str) -> None:
        if self.tristate and value not in ("unchecked", "checked", "partial"):
            value = "unchecked"
        elif not self.tristate and value not in ("unchecked", "checked"):
            value = "unchecked"
        self.__check_state = value
        self.update()

    @property
    def checked(self) -> bool:
        return self.check_state == "checked"

    @checked.setter
    def checked(self, value: bool) -> None:
        self.check_state = "checked" if value else "unchecked"

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        text = text if text is not None else str()
        if self.__text != text:
            self.__text = text
            self.update()

    @property
    def text_color(self) -> str:
        return self.__text_color

    @text_color.setter
    def text_color(self, value: str) -> None:
        if self.__text_color != value:
            self.__text_color = value
            self.update()

    @property
    def text_disabled_color(self) -> str:
        return self.__text_disabled_color

    @text_disabled_color.setter
    def text_disabled_color(self, value: str) -> None:
        if self.__text_disabled_color != value:
            self.__text_disabled_color = value
            self.update()

    @property
    def font(self) -> str:
        return self.__font

    @font.setter
    def font(self, value: str) -> None:
        if self.__font != value:
            self.__font = value
            self.update()

    def mouse_entered(self) -> bool:
        self.__mouse_inside = True
        self.update()
        return True

    def mouse_exited(self) -> bool:
        self.__mouse_inside = False
        self.update()
        return True

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__mouse_pressed = True
        self.update()
        return True

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self.__mouse_pressed = False
        self.update()
        return True

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._toggle_checked()
        return True

    def _toggle_checked(self) -> None:
        if self.enabled:
            if self.check_state == "checked":
                self.check_state = "unchecked"
            else:
                self.check_state = "checked"
            if callable(self.on_checked_changed):
                self.on_checked_changed(self.check_state == "checked")
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(self.check_state)

    @property
    def _mouse_inside(self) -> bool:
        return self.__mouse_inside

    @property
    def _mouse_pressed(self) -> bool:
        return self.__mouse_pressed

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        """ Size the canvas item to the text content. """
        horizontal_padding = 4
        vertical_padding = 3
        font_metrics = get_font_metrics_fn(self.__font, self.__text)
        new_sizing = self.sizing
        new_sizing = new_sizing.with_fixed_width(font_metrics.width + 2 * horizontal_padding + 14 + 4)
        new_sizing = new_sizing.with_fixed_height(font_metrics.height + 2 * vertical_padding)
        self.update_sizing(new_sizing)

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return CheckBoxCanvasItemComposer(self, self.layout_sizing, composer_cache, self.check_state, self.enabled, self.__mouse_inside, self.__mouse_pressed, self.__text, self.__text_color, self.__text_disabled_color, self.__font)


class EmptyCanvasItemComposer(BaseComposer):
    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        pass


class EmptyCanvasItem(CellCanvasItem):
    """ Canvas item to act as a placeholder (spacer or stretch). """

    def __init__(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None, border: typing.Optional[CellBorder] = None) -> None:
        super().__init__()
        self.cell = Cell(background_color, border)


class RadioButtonGroup:

    def __init__(self, buttons: typing.Sequence[BitmapButtonCanvasItem]) -> None:
        self.__buttons = copy.copy(buttons)
        self.__current_index = 0
        self.on_current_index_changed: typing.Optional[typing.Callable[[int], None]] = None

        for index, button in enumerate(self.__buttons):
            button.checked = index == self.__current_index

        for index, button in enumerate(self.__buttons):
            def current_index_changed(index: int) -> None:
                self.__current_index = index
                for index, button in enumerate(self.__buttons):
                    button.checked = index == self.__current_index
                if callable(self.on_current_index_changed):
                    self.on_current_index_changed(self.__current_index)

            button.on_button_clicked = functools.partial(current_index_changed, index)

    def close(self) -> None:
        for button in self.__buttons:
            button.on_button_clicked = None
        self.on_current_index_changed = None

    @property
    def current_index(self) -> int:
        return self.__current_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        self.__current_index = value
        for index, button in enumerate(self.__buttons):
            button.checked = index == self.__current_index


class DrawCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, composer_cache: ComposerCache, drawing_fn: typing.Callable[[DrawingContext.DrawingContext, Geometry.IntSize], None]) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__drawing_fn = drawing_fn

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            self.__drawing_fn(drawing_context, canvas_rect.size)


class DrawCanvasItem(AbstractCanvasItem):
    def __init__(self, drawing_fn: typing.Callable[[DrawingContext.DrawingContext, Geometry.IntSize], None]) -> None:
        super().__init__()
        self.__drawing_fn = drawing_fn

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return DrawCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__drawing_fn)


class DividerCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, composer_cache: ComposerCache, orientation: str, color: str) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__orientation = orientation
        self.__color = color

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        with drawing_context.saver():
            if self.__orientation == "vertical":
                drawing_context.move_to(canvas_rect.center.x, canvas_rect.top)
                drawing_context.line_to(canvas_rect.center.x, canvas_rect.bottom)
            else:
                drawing_context.move_to(canvas_rect.left, canvas_rect.center.y)
                drawing_context.line_to(canvas_rect.right, canvas_rect.center.y)
            drawing_context.stroke_style = self.__color
            drawing_context.stroke()


class DividerCanvasItem(AbstractCanvasItem):
    def __init__(self, *, orientation: typing.Optional[str] = None, color: typing.Optional[str] = None):
        super().__init__()
        self.__orientation = orientation or "vertical"
        if self.__orientation == "vertical":
            self.update_sizing(self.sizing.with_fixed_width(2))
        else:
            self.update_sizing(self.sizing.with_fixed_height(2))
        self.__color = color or "#CCC"

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return DividerCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__orientation, self.__color)


class ProgressBarCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, progress: float) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__progress = progress

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        progress = self.__progress
        canvas_size = canvas_rect.size
        canvas_rect_center = canvas_rect.center
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            drawing_context.begin_path()
            drawing_context.rect(0, 0, canvas_size.width, canvas_size.height)
            drawing_context.close_path()
            drawing_context.stroke_style = "#CCC"
            drawing_context.fill_style = "#CCC"
            drawing_context.fill()
            drawing_context.stroke()
            if canvas_size.width * progress >= 1:
                drawing_context.begin_path()
                drawing_context.rect(0, 0, canvas_size.width * progress, canvas_size.height)
                drawing_context.close_path()
                drawing_context.stroke_style = "#6AB"
                drawing_context.fill_style = "#6AB"
                drawing_context.fill()
                drawing_context.stroke()
            if canvas_size.height >= 16 and canvas_size.width * progress >= 50:  # TODO: use font metrics to find length of text
                progress_text = str(round(progress * 100)) + "%"
                drawing_context.begin_path()
                drawing_context.font = "12px sans-serif"
                drawing_context.text_align = 'center'
                drawing_context.text_baseline = 'middle'
                drawing_context.fill_style = "#fff"
                drawing_context.line_width = 2
                drawing_context.fill_text(progress_text, (canvas_size.width - 6) * progress - 19, canvas_rect_center.y + 1)
                drawing_context.fill()
                drawing_context.close_path()


class ProgressBarCanvasItem(AbstractCanvasItem):
    def __init__(self) -> None:
        super().__init__()
        self.__enabled = True
        self.__progress = 0.0  # 0.0 to 1.0
        self.update_sizing(self.sizing.with_fixed_height(4))

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        return ProgressBarCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__progress)

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


class TimestampCanvasItemComposer(BaseComposer):
    def __init__(self, canvas_item: AbstractCanvasItem, layout_sizing: Sizing, cache: ComposerCache, timestamp_str: str) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__timestamp_str = timestamp_str

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: ComposerCache) -> None:
        timestamp_str = self.__timestamp_str
        if timestamp_str:
            with drawing_context.saver():
                drawing_context.translate(canvas_rect.left, canvas_rect.top)
                drawing_context.timestamp(timestamp_str)


class TimestampCanvasItem(AbstractCanvasItem):
    def __init__(self) -> None:
        super().__init__()
        self.timestamp: typing.Optional[datetime.datetime] = None
        self.__timestamp_ns = 0
        self.__used_timestamp_ns = 0

    @property
    def timestamp_ns(self) -> int:
        return self.__timestamp_ns

    @timestamp_ns.setter
    def timestamp_ns(self, value: int) -> None:
        if value != self.__timestamp_ns or value != self.__used_timestamp_ns:
            self.__timestamp_ns = value
            self.__used_timestamp_ns = value
            self._invalidate_composer()

    def _get_composer(self, composer_cache: ComposerCache) -> typing.Optional[BaseComposer]:
        timestamp_str = str()
        if self.__used_timestamp_ns:
            timestamp_str = str(self.__used_timestamp_ns)
            self.__used_timestamp = 0
        elif self.__timestamp_ns:
            # tell host to use last timestamp it knows about.
            timestamp_str = "last"
        return TimestampCanvasItemComposer(self, self.layout_sizing, composer_cache, timestamp_str)


def load_rgba_data_from_bytes(b: typing.ByteString, format: typing.Optional[str] = None) -> typing.Optional[DrawingContext.RGBA32Type]:
    extension = "." + format if format else None
    image_argb = imageio.imread(typing.cast(typing.BinaryIO, b), extension=typing.cast(str, extension))
    if image_argb is not None:
        image_rgba = numpy.zeros_like(image_argb)
        image_rgba[:, :, 0] = image_argb[:, :, 2]
        image_rgba[:, :, 1] = image_argb[:, :, 1]
        image_rgba[:, :, 2] = image_argb[:, :, 0]
        image_rgba[:, :, 3] = image_argb[:, :, 3]
        return image_rgba.view(numpy.uint32).reshape(image_rgba.shape[:-1])
    return None


def load_bitmap_from_bytes(b: typing.ByteString, format: typing.Optional[str] = None) -> typing.Optional[Bitmap.Bitmap]:
    return Bitmap.promote_bitmap(load_rgba_data_from_bytes(b, format))
