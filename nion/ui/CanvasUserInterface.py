# TODO: merge WidgetBehavior and subclasses with counterparts in Widgets.py

from __future__ import annotations

import abc
import asyncio
import functools
import math
import pathlib
import typing

from nion.ui import Application
from nion.ui import Bitmap
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.utils import Color
from nion.utils import Geometry
from nion.utils import Model
from nion.utils import Stream


def extract_canvas_item(widget: UserInterface.Widget) -> typing.Optional[CanvasItem.AbstractCanvasItem]:
    # extracts the canvas widget from the user interface widget
    widget_behavior = typing.cast(WidgetBehavior, widget._behavior)
    content_widget = widget_behavior._get_content_widget() if widget else None
    if content_widget:
        return extract_canvas_item(content_widget)
    return widget_behavior._canvas_item if widget else None


class CheckBoxWidgetCanvasItemController(Widgets.BaseWidgetCanvasItemController):
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.on_size_changed: typing.Optional[typing.Callable[[Geometry.IntSize], None]] = None
        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None

    @property
    @abc.abstractmethod
    def text(self) -> typing.Optional[str]: raise NotImplementedError()

    @text.setter
    @abc.abstractmethod
    def text(self, text: typing.Optional[str]) -> None: ...

    @property
    @abc.abstractmethod
    def check_state(self) -> str: raise NotImplementedError()

    @check_state.setter
    @abc.abstractmethod
    def check_state(self, check_state: str) -> None: ...

    @property
    @abc.abstractmethod
    def tristate(self) -> bool: raise NotImplementedError()

    @tristate.setter
    @abc.abstractmethod
    def tristate(self, tristate: bool) -> None: ...


class BasicCheckBoxWidgetCanvasItemController(CheckBoxWidgetCanvasItemController):
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.__row = CanvasItem.CanvasItemComposition()
        self.__row.layout = CanvasItem.CanvasItemRowLayout()
        self.__check_box_canvas_item = CanvasItem.CheckBoxCanvasItem()
        self.__row.add_canvas_item(self.__check_box_canvas_item)

        def handle_check_state_changed(check_state: str) -> None:
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        self.__check_box_canvas_item.on_check_state_changed = handle_check_state_changed

    @property
    def widget_source(self) -> Widgets.WidgetSource:
        return Widgets.WidgetSource(self.ui, None, self.__row)

    @property
    def text(self) -> typing.Optional[str]:
        return self.__check_box_canvas_item.text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__check_box_canvas_item.text = text or str()
        self.__check_box_canvas_item.size_to_content(self.ui.get_font_metrics)
        self.__row.size_to_content()
        # TODO: revisit on size changed is handled
        if callable(self.on_size_changed):
            size = Geometry.IntSize(width=self.__row.sizing.preferred_width_int,
                                    height=self.__row.sizing.preferred_height_int)
            self.on_size_changed(size)

    @property
    def check_state(self) -> str:
        return self.__check_box_canvas_item.check_state

    @check_state.setter
    def check_state(self, check_state: str) -> None:
        self.__check_box_canvas_item.check_state = check_state

    @property
    def tristate(self) -> bool:
        return self.__check_box_canvas_item.tristate

    @tristate.setter
    def tristate(self, tristate: bool) -> None:
        self.__check_box_canvas_item.tristate = tristate


class RadioButtonWidgetCanvasItemController(Widgets.BaseWidgetCanvasItemController):
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.on_size_changed: typing.Optional[typing.Callable[[Geometry.IntSize], None]] = None
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

    @abc.abstractmethod
    def set_text(self, value: typing.Optional[str]) -> None: ...

    @abc.abstractmethod
    def set_icon(self, bitmap: typing.Optional[Bitmap.BitmapOrArray]) -> None: ...

    @property
    @abc.abstractmethod
    def checked(self) -> bool: raise NotImplementedError()

    @checked.setter
    @abc.abstractmethod
    def checked(self, value: bool) -> None: ...


class RadioButtonCanvasItemComposer(CanvasItem.BaseComposer):
    def __init__(self, canvas_item: CanvasItem.AbstractCanvasItem, layout_sizing: CanvasItem.Sizing, cache: CanvasItem.ComposerCache,
                 checked: bool, enabled: bool, mouse_inside: bool, mouse_pressed: bool,
                 text: str, text_color: str, text_disabled_color: str, font: str) -> None:
        super().__init__(canvas_item, layout_sizing, cache)
        self.__checked = checked
        self.__enabled = enabled
        self.__mouse_inside = mouse_inside
        self.__mouse_pressed = mouse_pressed
        self.__text = text
        self.__text_color = text_color
        self.__text_disabled_color = text_disabled_color
        self.__font = font

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: CanvasItem.ComposerCache) -> None:
        canvas_size = canvas_rect.size
        checked = self.__checked
        enabled = self.__enabled
        mouse_inside = self.__mouse_inside
        mouse_pressed = self.__mouse_pressed
        font = self.__font
        text_color = self.__text_color
        text_disabled_color = self.__text_disabled_color
        text = self.__text
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            tx = 4 + 14 + 4
            cx = 4 + 7
            cy = canvas_size.height * 0.5
            size = 14
            size_half = 7
            drawing_context.begin_path()
            drawing_context.move_to(4 + size, cy)
            drawing_context.arc(4 + size_half, cy, size_half, 0, math.pi * 2)
            drawing_context.close_path()
            if checked:
                drawing_context.fill_style = "#FFF"
                drawing_context.fill()
            if enabled and mouse_inside and mouse_pressed:
                drawing_context.fill_style = "rgba(128, 128, 128, 0.5)"
                drawing_context.fill()
            elif enabled and mouse_inside:
                drawing_context.fill_style = "rgba(128, 128, 128, 0.1)"
                drawing_context.fill()
            drawing_context.stroke_style = "#888"
            drawing_context.line_width = 1.5
            drawing_context.stroke()
            if checked:
                drawing_context.begin_path()
                drawing_context.move_to(4 + size - 3.5, cy)
                drawing_context.arc(4 + size_half, cy, size_half - 3.5, 0, math.pi * 2)
                drawing_context.close_path()
                drawing_context.stroke_style = "#000"
                drawing_context.fill_style = "#000"
                drawing_context.line_width = 1.0
                drawing_context.stroke()
                drawing_context.fill()
            drawing_context.font = font
            drawing_context.text_align = 'left'
            drawing_context.text_baseline = 'middle'
            drawing_context.fill_style = text_color if enabled else text_disabled_color
            drawing_context.fill_text(text, tx, cy + 1)


class RadioButtonCanvasItem(CanvasItem.AbstractCanvasItem):

    def __init__(self, text: typing.Optional[str] = None) -> None:
        super().__init__()
        self.wants_mouse_events = True
        self.__enabled = True
        self.__mouse_inside = False
        self.__mouse_pressed = False
        self.__checked = False
        self.__text = text if text is not None else str()
        self.__text_color = "#000"
        self.__text_disabled_color = "#888"
        self.__font = "12px"
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_clicked = None
        super().close()

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.__enabled = value
        self.update()

    @property
    def checked(self) -> bool:
        return self.__checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self.__checked = value
        self.update()

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
        if callable(self.on_clicked):
            self.on_clicked()
        return True

    @property
    def _mouse_inside(self) -> bool:
        return self.__mouse_inside

    @property
    def _mouse_pressed(self) -> bool:
        return self.__mouse_pressed

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        """ Size the canvas item to the text content. """
        horizontal_padding = 4
        vertical_padding = 1
        radio_button_size = 14
        font_metrics = get_font_metrics_fn(self.__font, self.__text)
        new_sizing = self.copy_sizing()
        new_sizing = new_sizing.with_fixed_width(font_metrics.width + 2 * horizontal_padding + 14 + 4)
        new_sizing = new_sizing.with_fixed_height(max(font_metrics.height, radio_button_size) + 2 * vertical_padding)
        self.update_sizing(new_sizing)

    def _repaint(self, drawing_context: DrawingContext.DrawingContext) -> None:
        canvas_size = self.canvas_size
        if canvas_size:
            with drawing_context.saver():
                tx = 4 + 14 + 4
                cx = 4 + 7
                cy = canvas_size.height * 0.5
                size = 14
                size_half = 7
                drawing_context.begin_path()
                drawing_context.move_to(4 + size, cy)
                drawing_context.arc(4 + size_half, cy, size_half, 0, math.pi * 2)
                drawing_context.close_path()
                if self.checked:
                    drawing_context.fill_style = "#FFF"
                    drawing_context.fill()
                if self.enabled and self.__mouse_inside and self.__mouse_pressed:
                    drawing_context.fill_style = "rgba(128, 128, 128, 0.5)"
                    drawing_context.fill()
                elif self.enabled and self.__mouse_inside:
                    drawing_context.fill_style = "rgba(128, 128, 128, 0.1)"
                    drawing_context.fill()
                drawing_context.stroke_style = "#888"
                drawing_context.line_width = 1.5
                drawing_context.stroke()
                if self.checked:
                    drawing_context.begin_path()
                    drawing_context.move_to(4 + size - 3.5, cy)
                    drawing_context.arc(4 + size_half, cy, size_half - 3.5, 0, math.pi * 2)
                    drawing_context.close_path()
                    drawing_context.stroke_style = "#000"
                    drawing_context.fill_style = "#000"
                    drawing_context.line_width = 1.0
                    drawing_context.stroke()
                    drawing_context.fill()
    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> typing.Optional[CanvasItem.BaseComposer]:
        return RadioButtonCanvasItemComposer(self, self.layout_sizing, composer_cache, self.checked, self.enabled,
                                              self.__mouse_inside, self.__mouse_pressed, self.__text,
                                              self.__text_color, self.__text_disabled_color, self.__font)


class BasicRadioButtonWidgetCanvasItemController(RadioButtonWidgetCanvasItemController):
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)

        self.__radio_button_canvas_item = RadioButtonCanvasItem()
        self.__icon_button_canvas_item = CanvasItem.BitmapButtonCanvasItem(padding=Geometry.IntSize(4, 4))
        self.__icon_button_canvas_item.background_color = "#f0f0f0"
        self.__icon_button_canvas_item.border_color = "gray"
        self.__stack = CanvasItem.CanvasItemComposition()
        self.__stack.layout = CanvasItem.CanvasItemLayout()
        self.__stack.add_canvas_item(self.__radio_button_canvas_item)
        self.__stack.add_canvas_item(self.__icon_button_canvas_item)

        def handle_clicked() -> None:
            if callable(self.on_clicked):
                self.on_clicked()

        self.__radio_button_canvas_item.on_clicked = handle_clicked
        self.__icon_button_canvas_item.on_button_clicked = handle_clicked

    @property
    def widget_source(self) -> Widgets.WidgetSource:
        return Widgets.WidgetSource(self.ui, None, self.__stack)

    def set_text(self, value: typing.Optional[str]) -> None:
        self.__radio_button_canvas_item.visible = True
        self.__icon_button_canvas_item.visible = False
        self.__radio_button_canvas_item.text = value or str()
        self.__radio_button_canvas_item.size_to_content(self.ui.get_font_metrics)
        self.__icon_button_canvas_item.bitmap = None
        self.__icon_button_canvas_item.size_to_content(self.ui.get_font_metrics)

        if callable(self.on_size_changed):
            self.on_size_changed(Geometry.IntSize(width=self.__radio_button_canvas_item.sizing.preferred_width_int,
                                                  height=self.__radio_button_canvas_item.sizing.preferred_height_int))

    def set_icon(self, bitmap: typing.Optional[Bitmap.BitmapOrArray]) -> None:
        self.__radio_button_canvas_item.visible = False
        self.__icon_button_canvas_item.visible = True
        self.__icon_button_canvas_item.bitmap = Bitmap.promote_bitmap(bitmap)
        self.__icon_button_canvas_item.size_to_content(self.ui.get_font_metrics)
        self.__radio_button_canvas_item.text = str()
        self.__radio_button_canvas_item.size_to_content(self.ui.get_font_metrics)

        if callable(self.on_size_changed):
            self.on_size_changed(Geometry.IntSize(width=self.__icon_button_canvas_item.sizing.preferred_width_int,
                                                  height=self.__icon_button_canvas_item.sizing.preferred_height_int))

    def set_enabled(self, enabled: bool) -> None:
        self.__radio_button_canvas_item.enabled = enabled
        self.__icon_button_canvas_item.enabled = enabled

    def set_tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.__radio_button_canvas_item.tool_tip = tool_tip
        self.__icon_button_canvas_item.tool_tip = tool_tip

    def set_background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.__radio_button_canvas_item.background_color = background_color
        self.__icon_button_canvas_item.background_color = background_color

    @property
    def checked(self) -> bool:
        return self.__radio_button_canvas_item.checked

    @checked.setter
    def checked(self, checked: bool) -> None:
        self.__radio_button_canvas_item.checked = checked


class ComboBoxWidgetCanvasItemController(Widgets.BaseWidgetCanvasItemController):
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.on_size_changed: typing.Optional[typing.Callable[[Geometry.IntSize], None]] = None
        self.on_current_text_changed: typing.Optional[typing.Callable[[str], None]] = None

    @property
    @abc.abstractmethod
    def window(self) -> typing.Optional[UserInterface.Window]: raise NotImplementedError()

    @window.setter
    @abc.abstractmethod
    def window(self, value: typing.Optional[UserInterface.Window]) -> None: ...

    @property
    @abc.abstractmethod
    def current_text(self) -> str: raise NotImplementedError()

    @current_text.setter
    @abc.abstractmethod
    def current_text(self, value: str) -> None: ...

    @abc.abstractmethod
    def set_item_strings(self, strings: typing.Sequence[str]) -> None: ...

    @abc.abstractmethod
    def set_enabled(self, enabled: bool) -> None: ...

    @abc.abstractmethod
    def set_tool_tip(self, tool_tip: typing.Optional[str]) -> None: ...

    @abc.abstractmethod
    def set_background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None: ...


class BasicComboBoxWidgetCanvasItemController(ComboBoxWidgetCanvasItemController):

    # extra horizontal space (on each side) reserved around the text so it does not draw flush
    # against the box border when left-aligned.
    __horizontal_text_padding = 4

    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.__row = CanvasItem.CanvasItemComposition()
        self.__row.layout = CanvasItem.CanvasItemRowLayout()
        self.__text_button_canvas_item = CanvasItem.TextButtonCanvasItem(padding=Geometry.IntSize(width=self.__horizontal_text_padding, height=0))
        self.__text_button_canvas_item.text_align = "left"
        self.__text_button_canvas_item.text_measure = typing.cast(CanvasItem.TextMeasure, ui)
        self.__row.background_color = "white"
        self.__row.border_color = "#c0c0c0"
        self.__row.border_width = 0.5
        self.__triangle = CanvasItem.StaticTextCanvasItem("\N{BLACK DOWN-POINTING TRIANGLE}")
        self.__triangle.wants_mouse_events = True
        self.__row.add_canvas_item(self.__text_button_canvas_item)
        self.__row.add_canvas_item(self.__triangle)
        self.__items: typing.List[str] = list()
        self.__item_text_size = Geometry.IntSize()
        self.__window: typing.Optional[CanvasWindow] = None

        def handle_clicked() -> None:
            if self.__window:
                menu = self.__window.create_context_menu()
                # menu = ui.create_context_menu(self.__window._root_window)
                for item_str in self.__items:
                    def handle_menu_item(text: str) -> None:
                        self.current_text = text  # updates the button
                        if callable(self.on_current_text_changed):
                            self.on_current_text_changed(text)

                    menu.add_menu_item(item_str, functools.partial(handle_menu_item, item_str))
                window_pos = self.__window._root_window.position
                y_pos = self.__row.canvas_size.height if self.__row.canvas_size else 0
                pos = window_pos + self.__row.map_to_base_container(Geometry.IntPoint(y=y_pos))
                menu.popup(pos.x, pos.y)

        self.__text_button_canvas_item.on_clicked = handle_clicked
        self.__triangle.on_clicked = handle_clicked

    @property
    def widget_source(self) -> Widgets.WidgetSource:
        return Widgets.WidgetSource(self.ui, None, self.__row)

    @property
    def window(self) -> typing.Optional[UserInterface.Window]:
        return self.__window

    @window.setter
    def window(self, window: typing.Optional[UserInterface.Window]) -> None:
        if window:
            assert isinstance(window, CanvasWindow)
            self.__window = window
        else:
            self.__window = None

    def __compute_item_text_size(self) -> Geometry.IntSize:
        # measure every item (not just the current one) so the combo box has a stable width that
        # does not change as the user picks different items, matching Qt's behavior where the
        # combo box is sized to accommodate the widest item.
        font = self.__text_button_canvas_item.text_font or "12px"
        widths = [self.ui.get_font_metrics(font, item).width for item in self.__items]
        heights = [self.ui.get_font_metrics(font, item).height for item in self.__items]
        max_width = max(widths, default=0)
        max_height = max(heights, default=0)
        # account for the text button's own padding, which is not included in the raw font metrics.
        if max_width:
            max_width += 2 * self.__horizontal_text_padding
        return Geometry.IntSize(width=max_width, height=max_height)

    @property
    def current_text(self) -> str:
        return self.__text_button_canvas_item.text

    @current_text.setter
    def current_text(self, value: str) -> None:
        if value:  # only update if value, matches Qt behavior
            self.__text_button_canvas_item.text = value
            self.__text_button_canvas_item.intrinsic_size = self.__item_text_size
            self.__triangle.size_to_content(self.ui.get_font_metrics)
            self.__row.size_to_content()
            if callable(self.on_size_changed):
                size = Geometry.IntSize(width=self.__row.sizing.preferred_width_int, height=self.__row.sizing.preferred_height_int)
                self.on_size_changed(size)

    def set_item_strings(self, strings: typing.Sequence[str]) -> None:
        index = self.__items.index(self.current_text) if self.current_text else 0
        self.__items = list(strings)
        self.__item_text_size = self.__compute_item_text_size()
        self.current_text = self.__items[index] if 0 <= index < len(self.__items) else str()

    def set_enabled(self, enabled: bool) -> None:
        self.__text_button_canvas_item.enabled = enabled

    def set_tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.__text_button_canvas_item.tool_tip = tool_tip

    def set_background_color(self, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.__text_button_canvas_item.background_color = background_color


class BasicSliderWidgetCanvasItemController(Widgets.BaseWidgetCanvasItemController):

    def __init__(self, ui: UserInterface.UserInterface) -> None:
        super().__init__(ui)
        self.__row = CanvasItem.CanvasItemComposition()
        self.__row.layout = CanvasItem.CanvasItemRowLayout()
        self.__slider_canvas_item = CanvasItem.SliderCanvasItem()
        self.__row.add_canvas_item(self.__slider_canvas_item)

        self.__minimum = 0
        self.__maximum = 0
        self.__is_pressed = False

        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.on_slider_pressed: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_released: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_moved: typing.Optional[typing.Callable[[int], None]] = None

        def handle_value(value: float) -> None:
            range = (self.maximum - self.minimum) or 1
            value_int = int(value * range + self.minimum)
            if self.__is_pressed and callable(self.on_slider_moved):
                self.on_slider_moved(value_int)
            if callable(self.on_value_changed):
                self.on_value_changed(value_int)

        def handle_value_change(value_change: Stream.ValueChange[float]) -> None:
            if value_change.is_begin:
                self.__is_pressed = True
                if callable(self.on_slider_pressed):
                    self.on_slider_pressed()
            if value_change.is_end:
                self.__is_pressed = False
                if callable(self.on_slider_released):
                    self.on_slider_released()

        self.__value_stream_listener = self.__slider_canvas_item.value_stream.value_stream.listen(handle_value)
        self.__value_change_stream_listener = self.__slider_canvas_item.value_change_stream.value_stream.listen(handle_value_change)

    def close(self) -> None:
        # TODO: this is not called
        self.__value_stream_listener = typing.cast(typing.Any, None)
        self.__value_change_stream_listener = typing.cast(typing.Any, None)

    @property
    def widget_source(self) -> Widgets.WidgetSource:
        return Widgets.WidgetSource(self.ui, None, self.__row)

    @property
    def value(self) -> int:
        range = (self.maximum - self.minimum) or 1
        return int(self.__slider_canvas_item.value * range + self.minimum)

    @value.setter
    def value(self, value: int) -> None:
        range = (self.maximum - self.minimum) or 1
        self.__slider_canvas_item.value = (value - self.minimum) / range

    @property
    def minimum(self) -> int:
        return self.__minimum

    @minimum.setter
    def minimum(self, minimum: int) -> None:
        self.__minimum = minimum

    @property
    def maximum(self) -> int:
        return self.__maximum

    @maximum.setter
    def maximum(self, maximum: int) -> None:
        self.__maximum = maximum

    @property
    def pressed(self) -> bool:
        return self.__is_pressed


class CanvasUserInterfaceWidgetCanvasItemControllerFactory(Widgets.WidgetCanvasItemControllerFactory):
    # adds methods from the subclass that are specific (for now) to the canvas UI

    def __init__(self, ui: UserInterface.UserInterface) -> None:
        self.__ui = ui

    def create_push_button_widget_canvas_item_controller(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> Widgets.PushButtonWidgetCanvasItemController:
        return Widgets.BasicPushButtonWidgetCanvasItemController(self.__ui)

    def create_tab_widget_canvas_item_controller(self) -> Widgets.TabWidgetCanvasItemController:
        return Widgets.BasicTabWidgetCanvasItemController(self.__ui)

    # additional methods

    def create_check_box_widget_canvas_item_controller(self) -> CheckBoxWidgetCanvasItemController:
        return BasicCheckBoxWidgetCanvasItemController(self.__ui)

    def create_radio_button_widget_canvas_item_controller(self) -> RadioButtonWidgetCanvasItemController:
        return BasicRadioButtonWidgetCanvasItemController(self.__ui)

    def create_combo_box_widget_canvas_item_controller(self) -> ComboBoxWidgetCanvasItemController:
        return BasicComboBoxWidgetCanvasItemController(self.__ui)

    def create_slider_widget_canvas_item_controller(self) -> BasicSliderWidgetCanvasItemController:
        return BasicSliderWidgetCanvasItemController(self.__ui)


class WidgetBehavior(UserInterface.WidgetBehavior):
    def __init__(self, canvas_item: CanvasItem.AbstractCanvasItem, does_retain_focus: bool, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.properties = dict(properties) if properties else {}
        self.canvas_item = canvas_item
        self.update_properties()
        self.__visible = True
        self.__enabled = True
        self.__tool_tip: typing.Optional[str] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed : typing.Optional[typing.Callable[[bool], None]] = None
        self.__does_retain_focus = does_retain_focus
        self._no_focus = "no_focus"
        self.__window: typing.Optional[UserInterface.Window] = None

    def close(self) -> None:
        # close the canvas item?
        self.on_ui_activity = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.canvas_item = typing.cast(typing.Any, None)

    @property
    def _canvas_item(self) -> CanvasItem.AbstractCanvasItem:
        return self.canvas_item

    @property
    def widget(self) -> typing.Any:
        return self.canvas_item

    def update_properties(self) -> None:
        # TODO
        properties = self.properties
        for key, value in properties.items():
            if key == "width":
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_fixed_width(value))
            if key == "height":
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_fixed_height(value))
            if key == "min-width":
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_minimum_width(value).with_preferred_width(value))
            if key == "min-height":
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_minimum_height(value).with_preferred_height(value))
            if key == "collapsible":
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_collapsible(bool(value)))
            if key == "size-policy-horizontal" and str(value).lower() in ("expanding", "minimum-expanding"):
                # allow this item to grow beyond its natural (children-derived) preferred width to fill
                # available leftover space in its container, while leaving its minimum/maximum untouched.
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_preferred_width(CanvasItem.SizingEnum.UNRESTRAINED))
            if key == "size-policy-vertical" and str(value).lower() in ("expanding", "minimum-expanding"):
                # same as above, but for height (e.g. a group box that should fill remaining vertical
                # space in a column but never shrink below what its current content requires).
                self.canvas_item.update_sizing(self.canvas_item.sizing.with_preferred_height(CanvasItem.SizingEnum.UNRESTRAINED))

    def set_property(self, key: str, value: typing.Any) -> None:
        # TODO
        pass

    def periodic(self) -> None:
        # TODO
        pass

    def _set_root_container(self, window: typing.Optional[UserInterface.Window]) -> None:
        self.__window = window

    def _window(self) -> typing.Optional[UserInterface.Window]:
        return self.__window

    def _get_content_widget(self) -> typing.Optional[UserInterface.Widget]:
        # TODO
        return None

    def _register_ui_activity(self) -> None:
        if callable(self.on_ui_activity):
            self.on_ui_activity()

    @property
    def focused(self) -> bool:
        return self.canvas_item.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self.canvas_item._set_focused(focused)

    @property
    def does_retain_focus(self) -> bool:
        return self.__does_retain_focus

    @does_retain_focus.setter
    def does_retain_focus(self, value: bool) -> None:
        self.__does_retain_focus = value

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        if visible != self.__visible:
            self.canvas_item.visible = visible
            self.__visible = visible

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        if enabled != self.__enabled:
            self.canvas_item.enabled = enabled
            self.__enabled = enabled

    @property
    def size(self) -> Geometry.IntSize:
        return self.canvas_item.canvas_size or Geometry.IntSize()

    @size.setter
    def size(self, size: Geometry.IntSize) -> None:
        self.canvas_item._set_canvas_size(size)

    @property
    def tool_tip(self) -> typing.Optional[str]:
        return self.__tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        if tool_tip != self.__tool_tip:
            self.canvas_item.tool_tip = tool_tip
            self.__tool_tip = tool_tip

    def set_background_color(self, color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]]) -> None:
        self.canvas_item.background_color = color

    def set_border_color(self, color: typing.Optional[str]) -> None:
        self.canvas_item.border_color = color

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[Bitmap.BitmapOrArray] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        self._register_ui_activity()

        def drag_finished(action: str) -> None:
            self._register_ui_activity()
            if drag_finished_fn:
                drag_finished_fn(action)

        # TODO
        # drag = QtDrag(self.proxy, self.widget, typing.cast(QtMimeData, mime_data), thumbnail, hot_spot_x, hot_spot_y, drag_finished)
        # drag.execute()

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return Geometry.IntPoint()
        # TODO
        # gx, gy = self.proxy.Widget_mapToGlobal(self.widget, p.x, p.y)
        # return Geometry.IntPoint(x=gx, y=gy)


class BoxWidgetBehavior(WidgetBehavior):

    def __init__(self, is_row: bool, properties: typing.Mapping[str, typing.Any] | None, alignment: str | None) -> None:
        self.__is_row = is_row
        self.__box_canvas_item = CanvasItem.CanvasItemComposition()
        self.__box_canvas_item.layout = CanvasItem.CanvasItemRowLayout() if is_row else CanvasItem.CanvasItemColumnLayout()
        self.__box_canvas_item.layout.alignment = alignment if alignment else "start"
        super().__init__(self.__box_canvas_item, False, properties)

    def insert(self, child: UserInterface.Widget, index_or_widget: typing.Optional[typing.Union[UserInterface.Widget, int]],
               fill: bool = False, alignment: typing.Optional[str] = None) -> None:
        # TODO: fill, alignment
        child_canvas_item = extract_canvas_item(child)
        assert self.widget is not None
        assert child_canvas_item is not None
        if index_or_widget is not None and isinstance(index_or_widget, UserInterface.Widget):
            index_canvas_item = extract_canvas_item(index_or_widget)
            assert index_canvas_item is not None
            index = self.__box_canvas_item.canvas_items.index(index_canvas_item)
        else:
            index = index_or_widget if index_or_widget is not None else len(self.__box_canvas_item.canvas_items)
        self.__box_canvas_item.insert_canvas_item(index, child_canvas_item)

    def remove(self, child: UserInterface.Widget) -> None:
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        if child_canvas_item in self.__box_canvas_item.canvas_items:
            self.__box_canvas_item.remove_canvas_item(child_canvas_item)
            return
        for alignment_canvas_item in self.__box_canvas_item.canvas_items:
            if child_canvas_item in alignment_canvas_item.canvas_items:
                self.__box_canvas_item.remove_canvas_item(alignment_canvas_item)
                return

    def add_stretch(self) -> UserInterface.Widget:
        return UserInterface.Widget(WidgetBehavior(self.__box_canvas_item.add_stretch(), False, None))

    def add_spacing(self, spacing: int) -> UserInterface.Widget:
        return UserInterface.Widget(WidgetBehavior(self.__box_canvas_item.add_spacing(spacing), False, None))

    def remove_all(self) -> None:
        self.__box_canvas_item.remove_all_canvas_items()


class StackWidgetBehavior(WidgetBehavior):

    def __init__(self, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)
        self.__current_index = 0

    @property
    def current_index(self) -> int | None:
        return self.__current_index

    @current_index.setter
    def current_index(self, value: int | None) -> None:
        self.__current_index = value or 0
        self.__update()

    def insert(self, child: UserInterface.Widget, before: int) -> None:
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        self.__canvas_item.insert_canvas_item(before, child_canvas_item)
        self.__update()

    def remove(self, child: UserInterface.Widget) -> None:
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        self.__canvas_item.remove_canvas_item(child_canvas_item)
        self.__update()

    def __update(self) -> None:
        for index, canvas_item in enumerate(self.__canvas_item.canvas_items):
            canvas_item.visible = self.current_index == index
        # TODO: changing the visibility of a child should auto-update the container
        self.__canvas_item.update()


class GroupWidgetBehavior(WidgetBehavior):

    def __init__(self, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics], text_measure: typing.Optional[CanvasItem.TextMeasure] = None) -> None:
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__title_item = CanvasItem.TextCanvasItem(str(), padding=Geometry.IntSize(width=4, height=2))
        self.__title_item.text_align = "left"
        self.__title_item.text_measure = text_measure
        self.__title_item.visible = False
        # indent the title a bit from the left edge of the frame, matching the typical inset of a
        # native group box's title/legend.
        self.__title_row = CanvasItem.CanvasItemComposition()
        self.__title_row.layout = CanvasItem.CanvasItemColumnLayout(margins=Geometry.Margins(top=0, left=4, bottom=0, right=0), alignment="start")
        self.__title_row.add_canvas_item(self.__title_item)
        self.__title_row.visible = False
        self.__content_composition = CanvasItem.CanvasItemComposition()
        # wrap the content in its own box so the background/border only cover the content area, not the
        # title row -- matching Qt's QGroupBox, where the title is drawn above/outside the frame rather
        # than on top of its filled background. pad the content away from the frame's edges.
        self.__content_box = CanvasItem.CanvasItemComposition()
        self.__content_box.layout = CanvasItem.CanvasItemColumnLayout(margins=Geometry.Margins(top=8, left=8, bottom=8, right=8))
        self.__content_box.add_canvas_item(self.__content_composition)
        # give the group box a distinct background and a border so it reads visually as a group,
        # matching Qt's native QGroupBox frame.
        self.__content_box.background_color = "rgba(0, 0, 0, 0.04)"
        self.__content_box.border_color = "#dadada"  # sRGB(0.855, 0.855, 0.855)
        self.__content_box.border_width = 0.5
        self.__column = CanvasItem.CanvasItemComposition()
        self.__column.layout = CanvasItem.CanvasItemColumnLayout(spacing=0, alignment="start")
        self.__column.add_canvas_item(self.__title_row)
        self.__column.add_canvas_item(self.__content_box)
        # collapsible so that this composition's own (live) sizing excludes the title row when it is
        # hidden (no title set), instead of needing to freeze/re-snapshot sizing on every content change.
        self.__column.update_sizing(self.__column.sizing.with_collapsible(True))
        super().__init__(self.__column, False, properties)
        self.__title: typing.Optional[str] = None

    @property
    def title(self) -> typing.Optional[str]:
        return self.__title

    @title.setter
    def title(self, title: typing.Optional[str]) -> None:
        self.__title = title
        self.__title_item.text = title or str()
        self.__title_item.visible = bool(title)
        self.__title_row.visible = bool(title)
        if title:
            self.__title_item.size_to_content(self.__get_font_metrics_fn)
        # trigger a re-layout without freezing this composition's own sizing (layout_sizing already
        # derives live from its children; calling size_to_content() here would bake a static size and
        # prevent it from tracking later content changes, e.g. an expanding size policy or content
        # that grows/shrinks after being added).
        self.__column.update()

    def add(self, child: UserInterface.Widget) -> None:
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        self.__content_composition.add_canvas_item(child_canvas_item)
        self.__content_composition.update()
        self.__column.update()

    def remove(self, child: UserInterface.Widget) -> None:
        child_canvas_item = extract_canvas_item(child)
        assert child_canvas_item is not None
        self.__content_composition.remove_canvas_item(child_canvas_item)
        self.__content_composition.update()
        self.__column.update()


class LabelWidgetBehavior(WidgetBehavior):

    def __init__(self, text: str, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics], text_measure: typing.Optional[CanvasItem.TextMeasure] = None) -> None:
        self.__canvas_item = CanvasItem.TextCanvasItem(text, padding=Geometry.IntSize())
        # match the default (left) alignment of Qt's QLabel; without a text_measure, text_align has no
        # effect and the text always draws centered (see TextButtonCell._paint_cell).
        self.__canvas_item.text_align = "left"
        self.__canvas_item.text_measure = text_measure
        super().__init__(self.__canvas_item, False, properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.word_wrap = False  # TODO

    @property
    def _canvas_item(self) -> CanvasItem.TextCanvasItem:
        return self.__canvas_item

    @property
    def text(self) -> typing.Optional[str]:
        return self.__canvas_item.text

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.__canvas_item.text = value or str()
        self.__canvas_item.size_to_content(self.__get_font_metrics_fn)

    def set_text_color(self, color: typing.Optional[str]) -> None:
        self.__canvas_item.text_color = color

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        self.__canvas_item.text_font = font_str
        self.__canvas_item.size_to_content(self.__get_font_metrics_fn)

    def set_text_alignment_horizontal(self, alignment: typing.Optional[str]) -> None:
        self.__canvas_item.text_align = alignment or "left"

    def set_text_alignment_vertical(self, alignment: typing.Optional[str]) -> None:
        pass

    @property
    def word_wrap(self) -> bool:
        return self.__word_wrap

    @word_wrap.setter
    def word_wrap(self, value: bool) -> None:
        self.__word_wrap = value


class TextEditCell(CanvasItem.Cell):

    def __init__(self, text: typing.Optional[str] = None, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border: typing.Optional[CanvasItem.CellBorder] = None, padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__(background_color, border, padding)
        self.__text = text if text is not None else str()
        self.__placeholder_text = str()
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
    def placeholder_text(self) -> str:
        return self.__placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, placeholder_text: typing.Optional[str]) -> None:
        placeholder_text = placeholder_text if placeholder_text is not None else str()
        if self.__placeholder_text != placeholder_text:
            self.__placeholder_text = placeholder_text
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
            # draw left-aligned, flush against the left edge of the cell, matching the way a label
            # draws its text; the border/background occupy the (padded) cell but do not shift where
            # the text itself is drawn.
            drawing_context.text_align = "left"
            drawing_context.fill_style = text_color
            drawing_context.fill_text(self.__text, rect.left, rect.center.y + 1)


class TextEditCanvasItem(CanvasItem.CellCanvasItem):

    def __init__(self, text: typing.Optional[str] = None, background_color: typing.Optional[typing.Union[str, DrawingContext.LinearGradient]] = None,
                 border_color: typing.Optional[str] = None, padding: typing.Optional[Geometry.IntSize] = None) -> None:
        super().__init__()
        border = CanvasItem.CellBorder()
        if border_color:
            border.border = CanvasItem.CellBorderProperties(Color.Color(border_color))
        self.__text_edit_cell = TextEditCell(text, background_color, border, padding)
        self.cell = self.__text_edit_cell

    def _description(self) -> str:
        return self.__class__.__name__ + f" '{self.text}'"

    @property
    def _text_cell(self) -> TextEditCell:
        return self.__text_edit_cell

    @property
    def text(self) -> str:
        return self.__text_edit_cell.text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__text_edit_cell.text = text or str()

    @property
    def placeholder_text(self) -> str:
        return self.__text_edit_cell.placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, placeholder_text: typing.Optional[str]) -> None:
        self.__text_edit_cell.placeholder_text = placeholder_text or str()

    @property
    def text_color(self) -> typing.Optional[str]:
        return self.__text_edit_cell.text_color

    @text_color.setter
    def text_color(self, text_color: typing.Optional[str]) -> None:
        self.__text_edit_cell.text_color = text_color

    @property
    def text_font(self) -> typing.Optional[str]:
        return self.__text_edit_cell.text_font

    @text_font.setter
    def text_font(self, text_font: typing.Optional[str]) -> None:
        self.__text_edit_cell.text_font = text_font

    @property
    def border_enabled(self) -> bool:
        return self.border_color is not None

    @border_enabled.setter
    def border_enabled(self, value: bool) -> None:
        if value:
            self.border_color = self.border_color or "black"
        else:
            self.border_color = None

    def size_to_content(self, get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        # size the line edit to fit its text (or placeholder, if text is empty) content height, plus
        # a small horizontal/vertical padding for the border and caret; use a minimum width so the
        # field is usable even when empty, matching Qt's QLineEdit sizeHint behavior.
        horizontal_padding = 4
        vertical_padding = 4
        minimum_width = 40
        text_font = self.text_font or "12px"
        content_text = self.text or self.placeholder_text
        font_metrics = get_font_metrics_fn(text_font, content_text)
        new_width = max(minimum_width, font_metrics.width + 2 * horizontal_padding)
        new_height = font_metrics.height + 2 * vertical_padding
        new_sizing = self.copy_sizing()
        new_sizing = new_sizing.with_minimum_width(minimum_width).with_preferred_width(new_width)
        new_sizing = new_sizing.with_fixed_height(new_height)
        self.update_sizing(new_sizing)


class LineEditWidgetBehavior(WidgetBehavior):

    def __init__(self, text: str, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        self.__canvas_item = TextEditCanvasItem(text, background_color="white", border_color="gray")
        super().__init__(self.__canvas_item, False, properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.word_wrap = False  # TODO
        self.__canvas_item.size_to_content(get_font_metrics_fn)
        self.on_editing_finished: typing.Optional[typing.Callable[[str], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[str], None]] = None

    @property
    def _canvas_item(self) -> TextEditCanvasItem:
        return self.__canvas_item

    @property
    def text(self) -> typing.Optional[str]:
        return self.__canvas_item.text

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.__canvas_item.text = value or str()
        self.__canvas_item.size_to_content(self.__get_font_metrics_fn)

    @property
    def placeholder_text(self) -> typing.Optional[str]:
        return self.__canvas_item.placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, value: typing.Optional[str]) -> None:
        self.__canvas_item.placeholder_text = value or str()
        self.__canvas_item.size_to_content(self.__get_font_metrics_fn)

    @property
    def editable(self) -> bool:
        # TODO: editable
        return True

    @editable.setter
    def editable(self, value: bool) -> None:
        # TODO: editable
        pass

    @property
    def clear_button_enabled(self) -> bool:
        # TODO: clear_button_enabled
        return True

    @clear_button_enabled.setter
    def clear_button_enabled(self, value: bool) -> None:
        # TODO: clear_button_enabled
        pass

    def editing_finished(self, text: str) -> None:
        # TODO: editing_finished
        pass

    @property
    def selected_text(self) -> typing.Optional[str]:
        # TODO: selected_text
        return str()

    def select_all(self) -> None:
        # TODO: select_all
        pass


class TextEditWidgetBehavior(WidgetBehavior, UserInterface.TextEditWidgetBehavior):
    def __init__(self, text: str, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        text_edit_canvas_item = TextEditCanvasItem(text, background_color="white", border_color="gray")
        font_metrics = get_font_metrics_fn(str(), "x")
        text_edit_canvas_item.update_sizing(text_edit_canvas_item.sizing.with_minimum_width(font_metrics.width * 32).with_minimum_height(font_metrics.height * 4))
        super().__init__(text_edit_canvas_item, False, properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__canvas_item = text_edit_canvas_item
        self.text: typing.Optional[str]
        self.placeholder: typing.Optional[str]
        self.editable: bool
        self.word_wrap_mode: str

        self.on_cursor_position_changed: typing.Optional[typing.Callable[[UserInterface.CursorPosition], None]] = None
        self.on_selection_changed: typing.Optional[typing.Callable[[UserInterface.Selection], None]] = None
        self.on_text_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_insert_mime_data: typing.Optional[typing.Callable[[UserInterface.MimeData], None]] = None

    @property
    def selected_text(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @property
    def cursor_position(self) -> UserInterface.CursorPosition:
        raise NotImplementedError()

    @property
    def selection(self) -> UserInterface.Selection:
        raise NotImplementedError()

    def append_text(self, value: str) -> None:
        pass

    def insert_text(self, value: str) -> None:
        pass

    def clear_selection(self) -> None:
        pass

    def remove_selected_text(self) -> None:
        pass

    def select_all(self) -> None:
        pass

    def move_cursor_position(self, operation: str, mode: typing.Optional[str] = None, n: int = 1) -> None:
        pass

    def set_line_height_proportional(self, proportional_line_height: float) -> None:
        pass

    def set_text_background_color(self, color: typing.Optional[str]) -> None:
        pass

    def set_text_color(self, color: typing.Optional[str]) -> None:
        pass

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        pass


class PushButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, ui: CanvasUserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)
        self.__get_font_metrics_fn = get_font_metrics_fn

        widget_canvas_item_factory = Widgets.BasicWidgetCanvasItemControllerFactory(ui)

        self.__canvas_item_controller = widget_canvas_item_factory.create_push_button_widget_canvas_item_controller()

        self.__canvas_item.add_canvas_item(self.__canvas_item_controller.widget_source.canvas_item)

        self.__text: typing.Optional[str] = None
        self.__icon: typing.Optional[Bitmap.Bitmap] = None
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

        def handle_clicked() -> None:
            if callable(self.on_clicked):
                self.on_clicked()

        def handle_size_changed(size: Geometry.IntSize) -> None:
            if size.width > 0 and size.height > 0:
                self.__canvas_item.update_sizing(self.__canvas_item.sizing.with_fixed_size(size))

        self.__canvas_item_controller.on_clicked = handle_clicked
        self.__canvas_item_controller.on_size_changed = handle_size_changed

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.__text = value
        self.__canvas_item_controller.set_text(value)
        self.__canvas_item_controller.size_to_content(self.__get_font_metrics_fn)

    @property
    def icon(self) -> typing.Optional[Bitmap.Bitmap]:
        return self.__icon

    @icon.setter
    def icon(self, value: typing.Optional[Bitmap.Bitmap]) -> None:
        self.__icon = value
        self.__canvas_item_controller.set_icon(value)
        self.__canvas_item_controller.size_to_content(self.__get_font_metrics_fn)

    def _set_enabled(self, enabled: bool) -> None:
        self.__canvas_item_controller.set_enabled(enabled)

    def _set_tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.__canvas_item_controller.set_tool_tip(tool_tip)

    def _set_background_color(self, background_color: typing.Optional[str]) -> None:
        self.__canvas_item_controller.set_background_color(background_color)


class CheckBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, ui: CanvasUserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)

        widget_canvas_item_factory = CanvasUserInterfaceWidgetCanvasItemControllerFactory(ui)

        self.__canvas_item_controller = widget_canvas_item_factory.create_check_box_widget_canvas_item_controller()

        self.__canvas_item.add_canvas_item(self.__canvas_item_controller.widget_source.canvas_item)

        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None

        def handle_check_state_changed(check_state: str) -> None:
            if callable(self.on_check_state_changed):
                self.on_check_state_changed(check_state)

        def handle_size_changed(size: Geometry.IntSize) -> None:
            # TODO: size to content be defined in AbstractCanvasItem
            self.__canvas_item.update_sizing(self.__canvas_item.sizing.with_fixed_size(size))

        self.__canvas_item_controller.on_check_state_changed = handle_check_state_changed
        self.__canvas_item_controller.on_size_changed = handle_size_changed

    @property
    def text(self) -> typing.Optional[str]:
        return self.__canvas_item_controller.text

    @text.setter
    def text(self, text: typing.Optional[str]) -> None:
        self.__canvas_item_controller.text = text

    @property
    def check_state(self) -> str:
        return self.__canvas_item_controller.check_state

    @check_state.setter
    def check_state(self, check_state: str) -> None:
        self.__canvas_item_controller.check_state = check_state

    @property
    def tristate(self) -> bool:
        return self.__canvas_item_controller.tristate

    @tristate.setter
    def tristate(self, tristate: bool) -> None:
        self.__canvas_item_controller.tristate = tristate


class RadioButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, ui: CanvasUserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)

        widget_canvas_item_factory = CanvasUserInterfaceWidgetCanvasItemControllerFactory(ui)

        self.__canvas_item_controller = widget_canvas_item_factory.create_radio_button_widget_canvas_item_controller()

        self.__canvas_item.add_canvas_item(self.__canvas_item_controller.widget_source.canvas_item)

        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None

        def handle_clicked() -> None:
            if callable(self.on_clicked):
                self.on_clicked()

        def handle_size_changed(size: Geometry.IntSize) -> None:
            # TODO: size to content be defined in AbstractCanvasItem
            self.__canvas_item.update_sizing(self.__canvas_item.sizing.with_fixed_size(size))

        self.__canvas_item_controller.on_clicked = handle_clicked
        self.__canvas_item_controller.on_size_changed = handle_size_changed

    @property
    def text(self) -> typing.Optional[str]:
        return self.__text

    @text.setter
    def text(self, value: typing.Optional[str]) -> None:
        self.__text = value
        self.__canvas_item_controller.set_text(value)

    @property
    def icon(self) -> typing.Optional[Bitmap.Bitmap]:
        return self.__icon

    @icon.setter
    def icon(self, value: typing.Optional[Bitmap.Bitmap]) -> None:
        self.__icon = value
        self.__canvas_item_controller.set_icon(value)

    @property
    def checked(self) -> bool:
        return self.__canvas_item_controller.checked

    @checked.setter
    def checked(self, checked: bool) -> None:
        self.__canvas_item_controller.checked = checked


class ComboBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, ui: CanvasUserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)

        widget_canvas_item_factory = CanvasUserInterfaceWidgetCanvasItemControllerFactory(ui)

        self.__canvas_item_controller = widget_canvas_item_factory.create_combo_box_widget_canvas_item_controller()

        self.__canvas_item.add_canvas_item(self.__canvas_item_controller.widget_source.canvas_item)

        self.on_current_text_changed: typing.Optional[typing.Callable[[str], None]] = None

        def handle_size_changed(size: Geometry.IntSize) -> None:
            # TODO: size to content be defined in AbstractCanvasItem
            self.__canvas_item.update_sizing(self.__canvas_item.sizing.with_fixed_size(size))

        def handle_current_text_changed(text: str) -> None:
            if callable(self.on_current_text_changed):
                self.on_current_text_changed(text)

        self.__canvas_item_controller.on_size_changed = handle_size_changed
        self.__canvas_item_controller.on_current_text_changed = handle_current_text_changed

        self.__items: typing.List[str] = list()

    def _set_root_container(self, window: typing.Optional[UserInterface.Window]) -> None:
        self.__canvas_item_controller.window = window
        super()._set_root_container(window)

    @property
    def current_text(self) -> str:
        return self.__canvas_item_controller.current_text

    @current_text.setter
    def current_text(self, value: str) -> None:
        self.__canvas_item_controller.current_text = value

    def set_item_strings(self, strings: typing.Sequence[str]) -> None:
        self.__canvas_item_controller.set_item_strings(strings)

    def _set_enabled(self, enabled: bool) -> None:
        self.__canvas_item_controller.set_enabled(enabled)

    def _set_tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.__canvas_item_controller.set_tool_tip(tool_tip)

    def _set_background_color(self, background_color: typing.Optional[str]) -> None:
        self.__canvas_item_controller.set_background_color(background_color)


class SliderWidgetBehavior(WidgetBehavior):

    def __init__(self, ui: CanvasUserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)

        widget_canvas_item_factory = CanvasUserInterfaceWidgetCanvasItemControllerFactory(ui)

        self.__canvas_item_controller = widget_canvas_item_factory.create_slider_widget_canvas_item_controller()

        self.__canvas_item.add_canvas_item(self.__canvas_item_controller.widget_source.canvas_item)

        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.on_slider_pressed: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_released: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_moved: typing.Optional[typing.Callable[[int], None]] = None

        def value_changed(value: int) -> None:
            if callable(self.on_value_changed):
                self.on_value_changed(value)

        def slider_pressed() -> None:
            if callable(self.on_slider_pressed):
                self.on_slider_pressed()

        def slider_released() -> None:
            if callable(self.on_slider_released):
                self.on_slider_released()

        def slider_moved(value: int) -> None:
            if callable(self.on_slider_moved):
                self.on_slider_moved(value)

        self.__canvas_item_controller.on_value_changed = value_changed
        self.__canvas_item_controller.on_slider_pressed = slider_pressed
        self.__canvas_item_controller.on_slider_released = slider_released
        self.__canvas_item_controller.on_slider_moved = slider_moved

    @property
    def value(self) -> int:
        return self.__canvas_item_controller.value

    @value.setter
    def value(self, value: int) -> None:
        self.__canvas_item_controller.value = value

    @property
    def minimum(self) -> int:
        return self.__canvas_item_controller.minimum

    @minimum.setter
    def minimum(self, minimum: int) -> None:
        self.__canvas_item_controller.minimum = minimum

    @property
    def maximum(self) -> int:
        return self.__canvas_item_controller.maximum

    @maximum.setter
    def maximum(self, maximum: int) -> None:
        self.__canvas_item_controller.maximum = maximum

    @property
    def pressed(self) -> bool:
        return self.__canvas_item_controller.pressed



class CanvasWidgetCanvasItem(CanvasItem.CanvasWidgetCanvasItem):

    @property
    def canvas_widget(self) -> UserInterface.CanvasWidget:
        # TODO
        raise NotImplementedError()

    @property
    def focused_item(self) -> typing.Optional[CanvasItem.AbstractCanvasItem]:
        # TODO
        return None

    def size_changed(self, width: int, height: int) -> None:
        pass  # TODO

    def get_section_ref(self) -> CanvasItem.CanvasWidgetSection:
        # TODO
        raise NotImplementedError()



class CanvasWidgetBehavior(WidgetBehavior, UserInterface.CanvasWidgetBehavior):
    # TODO

    def __init__(self, properties: typing.Optional[typing.Mapping[str, typing.Any]], get_font_metrics_fn: typing.Callable[[str, str], UserInterface.FontMetrics]) -> None:
        self.__canvas_item = CanvasItem.CanvasItemComposition()
        super().__init__(self.__canvas_item, False, properties)
        self.__get_font_metrics_fn = get_font_metrics_fn
        self.__focusable = False
        self.on_mouse_entered: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_exited: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_clicked: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_double_clicked: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_pressed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_released: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], bool]] = None
        self.on_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], None]] = None
        self.on_grabbed_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterface.KeyboardModifiers], None]] = None
        self.on_wheel_changed: typing.Optional[typing.Callable[[int, int, int, int, bool], bool]] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_key_released: typing.Optional[typing.Callable[[UserInterface.Key], bool]] = None
        self.on_drag_enter: typing.Optional[typing.Callable[[UserInterface.MimeData], str]] = None
        self.on_drag_leave: typing.Optional[typing.Callable[[], str]] = None
        self.on_drag_move: typing.Optional[typing.Callable[[UserInterface.MimeData, int, int], str]] = None
        self.on_drop: typing.Optional[typing.Callable[[UserInterface.MimeData, int, int], str]] = None
        self.on_tool_tip: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_pan_gesture: typing.Optional[typing.Callable[[int, int], bool]] = None

    def _set_canvas_item(self, canvas_item: CanvasItem.AbstractCanvasItem) -> None:
        self.__canvas_item.remove_all_canvas_items()
        self.__canvas_item.add_canvas_item(canvas_item)
        # TODO: how does sizing work?

    def _create_composition_canvas_item(self, canvas_widget: UserInterface.CanvasWidget, layout_render: typing.Optional[str]) -> CanvasItem.CanvasWidgetCanvasItem:
        return CanvasWidgetCanvasItem()

    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None:
        pass

    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        pass  # TODO: draw_section

    def remove_section(self, section_id: int) -> None:
        pass

    def set_cursor_shape(self, cursor_shape: typing.Optional[str]) -> None:
        pass

    def grab_gesture(self, gesture_type: str) -> None:
        pass  # TODO: grab_gesture

    def release_gesture(self, gesture_type: str) -> None:
        pass

    def grab_mouse(self, gx: int, gy: int) -> None:
        pass

    def release_mouse(self) -> None:
        pass

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        pass

    def hide_tool_tip_text(self) -> None:
        pass

    @property
    def focusable(self) -> bool:
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        self.__focusable = focusable


class ProgressBarWidgetBehavior(CanvasWidgetBehavior, UserInterface.ProgressBarWidgetBehavior):
    pass


class CanvasWindow(UserInterface.Window):

    def __init__(self, ui: UserInterface.UserInterface, title: typing.Optional[str] = None, parent_window: typing.Optional[UserInterface.Window] = None) -> None:
        super().__init__(parent_window, title or str())
        self.__ui = ui
        self.__window = ui.create_document_window(title, parent_window)
        self.__window.on_periodic = self.periodic
        self.__window.on_size_changed = self.__window_size_changed
        self.__canvas_widget: typing.Optional[UserInterface.CanvasWidget] = None
        self.__canvas_item: CanvasItem.AbstractCanvasItem = typing.cast(typing.Any, None)
        self.__pending_size: typing.Optional[Geometry.IntSize] = None
        self.__event_loop = asyncio.get_event_loop()
        # the current actual size of the window, as last reported by the host window system (via
        # __window_size_changed) or as last requested by us (via show()/__grow_to_fit_content). used
        # to auto-grow (never auto-shrink) the window to keep its live content minimum visible; the
        # user can still shrink it manually, but never below that live minimum.
        self.__current_size: typing.Optional[Geometry.IntSize] = None
        self.__pushed_minimum_size: typing.Optional[Geometry.IntSize] = None

    def __window_size_changed(self, width: int, height: int) -> None:
        self.__current_size = Geometry.IntSize(width=width, height=height)

    def close(self) -> None:
        self.__ui.destroy_document_window(self.__window)
        self.__window = typing.cast(typing.Any, None)

    def request_close(self) -> None:
        self.__window.request_close()

    @property
    def _root_window(self) -> UserInterface.Window:
        return self.__window

    def _attach_root_widget(self, root_widget: typing.Optional[UserInterface.Widget]) -> None:
        self.__canvas_widget = self.__ui.create_canvas_widget()
        # the canvas widget will be created/added in the base UI.
        # the root canvas item will listen to UI events on the canvas widget.
        # by adding the associated canvas item of the root widget to the
        # new root canvas item, the events will be passed into the root widget
        # hierarchy.
        root_canvas_item = CanvasItem.RootCanvasItem(self.__canvas_widget)
        assert root_widget
        canvas_item = extract_canvas_item(root_widget)
        assert canvas_item
        self.__canvas_item = canvas_item
        # size the root canvas item to the preferred size of the root widget, so that the layout system can work properly.
        layout_sizing = canvas_item.layout_sizing
        width = max(layout_sizing.preferred_width_int, round(layout_sizing.minimum_width) if isinstance(layout_sizing.minimum_width, (int, float)) else 0)
        height = max(layout_sizing.preferred_height_int, round(layout_sizing.minimum_height) if isinstance(layout_sizing.minimum_height, (int, float)) else 0)
        canvas_item.update_sizing(canvas_item.sizing.with_fixed_size(Geometry.IntSize(height, width)))
        root_canvas_item.add_canvas_item(canvas_item)
        self.__canvas_widget.canvas_item.add_canvas_item(root_canvas_item)
        self.__window._attach_root_widget(self.__canvas_widget)

    def _get_focus_widget(self) -> typing.Optional[UserInterface.Widget]:
        # TODO
        return None

    def create_context_menu(self) -> UserInterface.Menu:
        return self.__ui.create_context_menu(self.__window)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__window.get_file_paths_dialog(title, directory, filter, selected_filter)

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__window.get_file_path_dialog(title, directory, filter, selected_filter)

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        return self.__window.get_save_file_path(title, directory, filter, selected_filter)

    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        return self.__window.get_color_dialog(title, color, show_alpha)

    def create_dock_widget(self, widget: UserInterface.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> UserInterface.DockWidget:
        # TODO
        raise NotImplementedError()

    def tabify_dock_widgets(self, dock_widget1: UserInterface.DockWidget, dock_widget2: UserInterface.DockWidget) -> None:
        # TODO
        raise NotImplementedError()

    def _get_screen_size(self) -> Geometry.IntSize:
        return self.__window._get_screen_size()

    def _get_screen_logical_dpi(self) -> float:
        return self.__window._get_screen_logical_dpi()

    def _get_screen_physical_dpi(self) -> float:
        return self.__window._get_screen_physical_dpi()

    def _get_display_scaling(self) -> float:
        return self.__window._get_display_scaling()

    def __get_live_content_minimum_size(self) -> typing.Optional[Geometry.IntSize]:
        # returns the current, live (non-cached) minimum size required to display the root widget's
        # content, bypassing any explicit sizing override (e.g. the fixed-size snapshot applied in
        # _attach_root_widget) so that later content changes (e.g. expanding/collapsing a section) are
        # reflected immediately.
        canvas_item = self.__canvas_item
        layout = getattr(canvas_item, "layout", None)
        if layout is None or not hasattr(canvas_item, "visible_canvas_items"):
            return None
        live_sizing = layout.get_sizing(canvas_item.visible_canvas_items)

        def _as_int(value: typing.Any) -> int:
            return int(value) if isinstance(value, (int, float)) else 0

        return Geometry.IntSize(width=_as_int(live_sizing.minimum_width), height=_as_int(live_sizing.minimum_height))

    def __update_window_size_for_content(self) -> None:
        # enforce (and keep up to date) a native minimum window size matching the live content
        # minimum, and grow (but never shrink) the window's actual size if that live minimum now
        # exceeds it. the user can still manually shrink the window, but never below the live
        # minimum, since that is enforced natively (where supported) via set_minimum_size.
        if not self.__canvas_widget or self.__current_size is None:
            return
        minimum_size = self.__get_live_content_minimum_size()
        if minimum_size is None:
            return
        if minimum_size != self.__pushed_minimum_size:
            self.__window.set_minimum_size(minimum_size)
            self.__pushed_minimum_size = minimum_size
        current_size = self.__current_size
        if minimum_size.width > current_size.width or minimum_size.height > current_size.height:
            new_size = Geometry.IntSize(width=max(minimum_size.width, current_size.width),
                                        height=max(minimum_size.height, current_size.height))
            self.__current_size = new_size
            self.__window.resize(new_size)

    def show(self, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        layout_sizing = self.__canvas_widget.canvas_item.layout_sizing if self.__canvas_widget else None
        if not size and layout_sizing:
            size = Geometry.IntSize(width=layout_sizing.preferred_width_int or 400, height=layout_sizing.preferred_height_int or 200)
        self.__current_size = size
        minimum_size = self.__get_live_content_minimum_size()
        if minimum_size is not None:
            self.__window.set_minimum_size(minimum_size)
            self.__pushed_minimum_size = minimum_size
        self.__window.show(size, position)

    def activate(self) -> None:
        self.__window.activate()

    def fill_screen(self) -> None:
        self.__window.fill_screen()

    def _set_title(self, value: str) -> None:
        self.__window._set_title(value)

    def _set_window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        self.__window._set_window_file_path(value)

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        self.__window.set_palette_color(role, r, g, b, a)

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        self.__window.set_window_style(styles)

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        self.__window.set_attributes(attributes)

    def periodic(self) -> None:
        self._handle_periodic()
        if self.__canvas_widget:
            self.__canvas_widget.periodic()
        self.__update_window_size_for_content()

    def aboutToShow(self) -> None:
        # TODO
        self._register_ui_activity()
        self._handle_about_to_show()

    def activationChanged(self, activated: bool) -> None:
        # TODO
        self._register_ui_activity()
        self._handle_activation_changed(activated)

    def aboutToClose(self, geometry: str, state: str) -> None:
        # TODO
        self._register_ui_activity()
        self._handle_about_to_close(geometry, state)

    def keyPressed(self, text: str, key: int, raw_modifiers: int) -> bool:
        # TODO
        self._register_ui_activity()
        # return self._handle_key_pressed(QtKey(text, key, raw_modifiers))
        return False

    def keyReleased(self, text: str, key: int, raw_modifiers: int) -> bool:
        # TODO
        self._register_ui_activity()
        # return self._handle_key_released(QtKey(text, key, raw_modifiers))
        return False

    def add_menu(self, title: str, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        # TODO
        # native_menu = self.proxy.DocumentWindow_addMenu(self.native_document_window, notnone(title))
        # menu = QtMenu(self, title, menu_id or str(), self.proxy, native_menu)
        # self._menu_added(menu)
        # return menu
        raise NotImplementedError()

    def insert_menu(self, title: str, before_menu: UserInterface.Menu, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        # TODO
        # before_menu = typing.cast(QtMenu, before_menu)
        # native_menu = self.proxy.DocumentWindow_insertMenu(self.native_document_window, notnone(title), before_menu.native_menu)
        # menu = QtMenu(self, title, menu_id or str(), self.proxy, native_menu)
        # self._menu_inserted(menu, before_menu)
        # return menu
        raise NotImplementedError()

    def restore(self, geometry: str, state: str) -> None:
        pass  # TODO
        # self.proxy.DocumentWindow_restore(self.native_document_window, geometry, state)

    def save(self) -> typing.Tuple[str, str]:
        # TODO
        # geometry, state = self.proxy.DocumentWindow_save(self.native_document_window)
        # return geometry, state
        raise NotImplementedError()

    def sizeChanged(self, width: int, height: int) -> None:
        # TODO
        self._register_ui_activity()
        self._handle_size_changed(width, height)

    def positionChanged(self, x: int, y: int) -> None:
        # TODO
        self._register_ui_activity()
        self._handle_position_changed(x, y)

    @property
    def position(self) -> Geometry.IntPoint:
        return self.__window.position

    @property
    def size(self) -> Geometry.IntSize:
        return self.__window.size


class CanvasUserInterface(UserInterface.UserInterface):

    def __init__(self, ui: UserInterface.UserInterface) -> None:
        self.__ui = ui
        self.proxy = self

    def close(self) -> None:
        pass

    def run(self, app: Application.BaseApplication) -> None:
        self.__ui.run(app)

    def request_quit(self) -> None:
        self.__ui.request_quit()

    def Application_setQuitOnLastWindowClosed(self, value: bool) -> None:
        getattr(self.__ui, "proxy").Application_setQuitOnLastWindowClosed(value)

    # data objects

    def create_mime_data(self) -> UserInterface.MimeData:
        return self.__ui.create_mime_data()

    def create_item_model_controller(self) -> typing.Any:
        raise NotImplementedError()

    def create_button_group(self) -> UserInterface.ButtonGroup:
        raise NotImplementedError()

    # window elements

    def create_document_window(self, title: typing.Optional[str] = None, parent_window: typing.Optional[UserInterface.Window] = None) -> UserInterface.Window:
        return CanvasWindow(self.__ui, title, parent_window)

    def destroy_document_window(self, document_window: UserInterface.Window) -> None:
        document_window.close()

    # user interface elements

    def create_row_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.BoxWidget:
        return UserInterface.BoxWidget(BoxWidgetBehavior(True, properties, alignment), alignment)

    def create_column_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.BoxWidget:
        return UserInterface.BoxWidget(BoxWidgetBehavior(False, properties, alignment), alignment)

    def create_splitter_widget(self, orientation: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.SplitterWidget:
        # TODO
        raise NotImplementedError()

    def create_tab_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TabWidget:
        # TODO
        raise NotImplementedError()

    def create_stack_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.StackWidget:
        return UserInterface.StackWidget(StackWidgetBehavior(properties))

    def create_group_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.GroupWidget:
        return UserInterface.GroupWidget(GroupWidgetBehavior(properties, self.get_font_metrics, typing.cast(CanvasItem.TextMeasure, self)))

    def create_scroll_area_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ScrollAreaWidget:
        # TODO
        raise NotImplementedError()

    def create_combo_box_widget(self, items: typing.Optional[typing.Sequence[typing.Any]] = None, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ComboBoxWidget:
        return UserInterface.ComboBoxWidget(ComboBoxWidgetBehavior(self, properties), items or list(), item_getter or (lambda x: str(x)))

    def create_push_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.PushButtonWidget:
        behavior = PushButtonWidgetBehavior(self, properties, self.get_font_metrics)
        if text is not None:
            behavior.text = text
        return UserInterface.PushButtonWidget(behavior, text)

    def create_radio_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.RadioButtonWidget:
        return UserInterface.RadioButtonWidget(RadioButtonWidgetBehavior(self, properties), text)

    def create_check_box_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.CheckBoxWidget:
        return UserInterface.CheckBoxWidget(CheckBoxWidgetBehavior(self, properties), text)

    def create_label_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.LabelWidget:
        return UserInterface.LabelWidget(LabelWidgetBehavior(text or str(), properties, self.get_font_metrics, typing.cast(CanvasItem.TextMeasure, self)), text)

    def create_slider_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.SliderWidget:
        return UserInterface.SliderWidget(SliderWidgetBehavior(self, properties))

    def create_progress_bar_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.ProgressBarWidget:
        progress_bar_widget = UserInterface.ProgressBarWidget(ProgressBarWidgetBehavior(properties, self.get_font_metrics))
        # size hack until layout is improved.
        progress_bar_widget.canvas_item.update_sizing(progress_bar_widget.canvas_item.sizing.with_fixed_width(100))
        return progress_bar_widget

    def create_line_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.LineEditWidget:
        return UserInterface.LineEditWidget(LineEditWidgetBehavior(str(), properties, self.get_font_metrics))

    def create_text_browser_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TextBrowserWidget:
        # TODO
        raise NotImplementedError()

    def create_text_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TextEditWidget:
        return UserInterface.TextEditWidget(TextEditWidgetBehavior(str(), properties, self.get_font_metrics))

    def create_canvas_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None, *, layout_render: typing.Optional[str] = None) -> UserInterface.CanvasWidget:
        return UserInterface.CanvasWidget(CanvasWidgetBehavior(properties, self.get_font_metrics))

    def create_tree_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterface.TreeWidget:
        # TODO
        raise NotImplementedError()

    # file i/o

    def load_rgba_data_from_file(self, filename: str) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__ui.load_rgba_data_from_file(filename)

    def save_rgba_data_to_file(self, data: DrawingContext.RGBA32Type, filename: str, format: typing.Optional[str]) -> None:
        self.__ui.save_rgba_data_to_file(data, filename, format)

    def get_existing_directory_dialog(self, title: str, directory: str) -> typing.Tuple[str, str]:
        return self.__ui.get_existing_directory_dialog(title, directory)

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__ui.get_file_paths_dialog(title, directory, filter, selected_filter)

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        return self.__ui.get_file_path_dialog(title, directory, filter, selected_filter)

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        return self.__ui.get_save_file_path(title, directory, filter, selected_filter)

    # persistence (associated with application)

    def get_data_location(self) -> str:
        return self.__ui.get_data_location()

    def get_document_location(self) -> str:
        return self.__ui.get_document_location()

    def get_temporary_location(self) -> str:
        return self.__ui.get_temporary_location()

    def get_configuration_location(self) -> str:
        return self.__ui.get_configuration_location()

    def set_persistence_handler(self, handler: UserInterface.PersistenceHandler) -> None:
        self.__ui.set_persistence_handler(handler)

    def get_persistent_string(self, key: str, default_value: typing.Optional[str] = None) -> str:
        return self.__ui.get_persistent_string(key, default_value)

    def set_persistent_string(self, key: str, value: str) -> None:
        self.__ui.set_persistent_string(key, value)

    def get_persistent_object(self, key: str, default_value: typing.Any=None) -> typing.Any:
        return self.__ui.get_persistent_object(key, default_value)

    def set_persistent_object(self, key: str, value: typing.Any) -> None:
        self.__ui.set_persistent_object(key, value)

    def remove_persistent_key(self, key: str) -> None:
        self.__ui.remove_persistent_key(key)

    def create_persistent_string_model(self, key: str, default_value: typing.Optional[str] = None) -> Model.PropertyModel[str]:
        return UserInterface.StringPersistentModel(self, key, default_value)

    def create_persistent_float_model(self, key: str, default_value: typing.Optional[float] = None) -> Model.PropertyModel[float]:
        return UserInterface.FloatPersistentModel(self, key, default_value)

    # clipboard

    def clipboard_clear(self) -> None:
        self.__ui.clipboard_clear()

    def clipboard_mime_data(self) -> UserInterface.MimeData:
        return self.__ui.clipboard_mime_data()

    def clipboard_set_mime_data(self, mime_data: UserInterface.MimeData) -> None:
        self.__ui.clipboard_set_mime_data(mime_data)

    def clipboard_set_text(self, text: str) -> None:
        self.__ui.clipboard_set_text(text)

    def clipboard_text(self) -> str:
        return self.__ui.clipboard_text()

    # misc

    def set_application_info(self, application_name: str, organization_name: str, organization_domain: str) -> None:
        self.__ui.set_application_info(application_name, organization_name, organization_domain)

    def create_rgba_image(self, drawing_context: DrawingContext.DrawingContext, width: int, height: int) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__ui.create_rgba_image(drawing_context, width, height)

    def get_font_metrics(self, font: str, text: str) -> UserInterface.FontMetrics:
        return self.__ui.get_font_metrics(font, text)

    def truncate_string_to_width(self, font_str: str, text: str, pixel_width: int, mode: UserInterface.TruncateModeType) -> str:
        return self.__ui.truncate_string_to_width(font_str, text, pixel_width, mode)

    def get_qt_version(self) -> str:
        return self.__ui.get_qt_version()

    def get_build_version(self) -> str:
        return self.__ui.get_build_version()

    def get_tolerance(self, tolerance_type: UserInterface.ToleranceType) -> float:
        return self.__ui.get_tolerance(tolerance_type)

    def create_context_menu(self, document_window: UserInterface.Window) -> UserInterface.Menu:
        return self.__ui.create_context_menu(document_window)

    def create_sub_menu(self, document_window: UserInterface.Window, title: typing.Optional[str] = None, menu_id: typing.Optional[str] = None) -> UserInterface.Menu:
        return self.__ui.create_sub_menu(document_window, title, menu_id)

    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        return self.__ui.get_color_dialog(title, color, show_alpha)

    def get_keyboard_modifiers(self, query: bool = False) -> UserInterface.KeyboardModifiers:
        return self.__ui.get_keyboard_modifiers(query)
