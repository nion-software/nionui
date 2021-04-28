"""
A library of custom widgets.
"""

from __future__ import annotations

# standard libraries
import copy
import gettext
import typing

# third party libraries
import numpy

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import Selection

if typing.TYPE_CHECKING:
    from nion.utils import Binding


_ = gettext.gettext


class CompositeWidgetBehavior:

    def __init__(self, content_widget):
        self.content_widget = content_widget
        self.on_context_menu_event = None
        self.on_focus_changed = None

    # subclasses should override to clear their variables.
    # subclasses should NOT call Qt code to delete anything here... that is done by the Qt code
    def close(self):
        self.content_widget.close()
        self.content_widget = None

    def _set_root_container(self, root_container):
        pass

    @property
    def focused(self):
        return self.content_widget.focused

    @focused.setter
    def focused(self, focused):
        self.content_widget.focused = focused

    @property
    def does_retain_focus(self) -> bool:
        return self.content_widget.does_retain_focus

    @does_retain_focus.setter
    def does_retain_focus(self, value: bool) -> None:
        self.content_widget.does_retain_focus = value

    @property
    def visible(self):
        return self.content_widget.visible

    @visible.setter
    def visible(self, visible):
        self.content_widget.visible = visible

    @property
    def enabled(self):
        return self.content_widget.enabled

    @enabled.setter
    def enabled(self, enabled):
        self.content_widget.enabled = enabled

    @property
    def size(self):
        return self.content_widget.size

    @size.setter
    def size(self, size):
        self.content_widget.size = size

    @property
    def tool_tip(self):
        return self.content_widget.tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip):
        self.content_widget.tool_tip = tool_tip

    def drag(self, mime_data: UserInterface.MimeData, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn) -> None:
        self.content_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def map_to_global(self, p):
        return self.content_widget.map_to_global(p)


class CompositeWidgetBase(UserInterface.Widget):

    def __init__(self, content_widget):
        assert content_widget is not None
        super().__init__(CompositeWidgetBehavior(content_widget))

    @property
    def content_widget(self):
        return self._behavior.content_widget

    @property
    def _contained_widgets(self):
        return [self.content_widget]

    def _set_root_container(self, root_container):
        super()._set_root_container(root_container)
        self.content_widget._set_root_container(root_container)

    # not thread safe
    def periodic(self):
        super().periodic()
        self.content_widget.periodic()

    def size_changed(self, size):
        self.content_widget.size_changed(size)


class SectionWidget(CompositeWidgetBase):
    """A widget representing a twist down section.

    The section is composed of a title in bold and then content.
    """

    def __init__(self, ui: UserInterface.UserInterface, section_title: str, section, section_id: str=None):
        super().__init__(ui.create_column_widget())

        section_widget = self.content_widget

        section_title_row = ui.create_row_widget()

        twist_down_canvas_item = CanvasItem.TwistDownCanvasItem()

        twist_down_canvas_widget = ui.create_canvas_widget(properties={"height": 20, "width": 20})
        twist_down_canvas_widget.canvas_item.add_canvas_item(twist_down_canvas_item)

        section_title_label = ui.create_label_widget(section_title)
        section_title_label.text_font = "bold"

        section_title_row.add(twist_down_canvas_widget)
        section_title_row.add(section_title_label)
        section_title_row.add_stretch()
        section_widget.add(section_title_row)
        section_content_row = ui.create_row_widget()
        section_content_column = ui.create_column_widget()
        section_content_column.add_spacing(4)
        section_content_column.add(section)
        section_content_row.add_spacing(20)
        section_content_row.add(section_content_column)
        section_widget.add(section_content_row)
        section_widget.add_spacing(4)

        def toggle():
            twist_down_canvas_item.checked = not twist_down_canvas_item.checked
            section_content_column.visible = twist_down_canvas_item.checked
            if section_id:
                ui.set_persistent_string(section_id, "true" if twist_down_canvas_item.checked else "false")

        section_open = ui.get_persistent_string(section_id, "true") == "true" if section_id else True
        twist_down_canvas_item.checked = section_open
        section_content_column.visible = section_open
        twist_down_canvas_item.on_button_clicked = toggle

        self.section_title_row = section_title_row
        self.__twist_down_canvas_item = twist_down_canvas_item

    @property
    def expanded(self) -> bool:
        return self.__twist_down_canvas_item.checked

    @expanded.setter
    def expanded(self, value: bool) -> None:
        if value != self.expanded:
            self.__twist_down_canvas_item.on_button_clicked()


class ListCanvasItemDelegate:

    def __init__(self):
        self.__items = list()
        self.on_item_selected = None
        self.on_cancel = None

    @property
    def items(self):
        return self.__items

    @items.setter
    def items(self, value):
        self.__items = value

    @property
    def item_count(self):
        return len(self.__items)

    def key_pressed(self, key: UserInterface.Key) -> bool:
        if key.is_escape:
            if callable(self.on_cancel):
                self.on_cancel()
                # returning False here will allow window to handle the escape key.
                return False
        return False

    def item_selected(self, index):
        if callable(self.on_item_selected):
            return self.on_item_selected(index)
        return False

    def paint_item(self, drawing_context, display_item, rect, is_selected):
        raise NotImplementedError()


class ListWidget(CompositeWidgetBase):
    """A widget with a list in a scroll bar."""

    def __init__(self, ui, list_item_delegate, *, items=None, selection_style=None, properties=None, selection=None, border_color=None, v_scroll_enabled: bool=True, v_auto_resize: bool=False):
        super().__init__(ui.create_column_widget())
        self.property_changed_event = Event.Event()
        items = items or list()
        self.__items: typing.List = list()
        self.on_selection_changed: typing.Optional[typing.Callable[[typing.AbstractSet[int]], None]] = None
        self.on_item_selected: typing.Optional[typing.Callable[[int], bool]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None
        self.on_item_handle_context_menu = None  # used for declarative
        self.__items_binding = None
        self.__current_index_binding = None
        self.__on_current_index_changed = None
        self.__v_auto_resize = v_auto_resize
        self.on_escape_pressed : typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed : typing.Optional[typing.Callable[[], bool]] = None

        self.__selection = selection if selection else Selection.IndexedSelection(selection_style)

        def selection_changed():
            on_selection_changed = self.on_selection_changed
            if callable(on_selection_changed):
                on_selection_changed(self.__selection.indexes)
            if callable(self.__on_current_index_changed):
                self.__on_current_index_changed(self.current_index)

        def handle_delegate_cancel():
            if callable(self.on_cancel):
                self.on_cancel()
            if callable(self.on_escape_pressed):
                self.on_escape_pressed()

        def handle_delegate_item_selected(index):
            if callable(self.on_item_selected):
                self.on_item_selected(index)
            if callable(self.on_return_pressed):
                self.on_return_pressed()

        self.__selection_changed_event_listener = self.__selection.changed_event.listen(selection_changed)
        self.__list_canvas_item_delegate = list_item_delegate
        self.__list_canvas_item_delegate.on_cancel = handle_delegate_cancel
        self.__list_canvas_item_delegate.on_item_selected = handle_delegate_item_selected
        self.__list_canvas_item = ListCanvasItem.ListCanvasItem(self.__list_canvas_item_delegate, self.__selection, 20)

        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(self.__list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_group_canvas_item = CanvasItem.CanvasItemComposition()
        if border_color is not None:
            scroll_group_canvas_item.border_color = border_color
        scroll_group_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        scroll_group_canvas_item.add_canvas_item(scroll_area_canvas_item)
        if v_scroll_enabled:
            scroll_bar_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item)
            scroll_group_canvas_item.add_canvas_item(scroll_bar_canvas_item)

        canvas_widget = ui.create_canvas_widget(properties=properties)
        canvas_widget.canvas_item.add_canvas_item(scroll_group_canvas_item)

        self.content_widget.add(canvas_widget)

        self.__canvas_widget = canvas_widget

        self.items = items

    def close(self) -> None:
        self.__selection_changed_event_listener.close()
        self.__selection_changed_event_listener = None
        self.on_selection_changed = None
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.clear_task("update_items")
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        self.__on_current_index_changed = None
        self.clear_task("update_current_index")
        self.__items = typing.cast(typing.List, None)
        super().close()

    @property
    def focused(self) -> bool:
        return self.__canvas_widget.focused and self.__list_canvas_item.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self.__list_canvas_item.request_focus()

    @property
    def wants_drag_events(self) -> bool:
        return self.__list_canvas_item.wants_drag_events

    @wants_drag_events.setter
    def wants_drag_events(self, value: bool) -> None:
        self.__list_canvas_item.wants_drag_events = value

    @property
    def items(self) -> typing.List:
        return self.__items if self.__items is not None else list()

    @items.setter
    def items(self, items: typing.List) -> None:
        self.__items = copy.copy(items)

        self.__list_canvas_item_delegate.items = self.__items
        self.__list_canvas_item.size_to_content()  # this will only configure the sizing, not actual size (until next layout)
        self.__list_canvas_item.update()

        if self.__v_auto_resize:
            # if v_auto_resize is True, ensure the canvas item resizes vertically to its content and the canvas widget
            # resizes vertically to the height of the canvas item content.

            new_sizing = self.__canvas_widget.canvas_item.copy_sizing()
            content_height = self.__list_canvas_item.sizing.maximum_height
            new_sizing._minimum_height = content_height
            new_sizing._preferred_height = content_height
            new_sizing._maximum_height = content_height
            self.__canvas_widget.canvas_item.update_sizing(new_sizing)

            self.__canvas_widget.set_property("min-height", content_height)
            self.__canvas_widget.set_property("max-height", content_height)
            self.__canvas_widget.set_property("size-policy-vertical", "fixed")

        # setting items on the widget will not update items on the bound items since the list widget is merely a view

    def bind_items(self, binding) -> None:
        self.clear_task("update_items")
        if self.__items_binding:
            self.__items_binding.close()
            self.__items_binding = None
        self.items = binding.get_target_value()
        self.__items_binding = binding

        def update_items(items):
            def update_items_():
                if self._behavior:
                    self.items = items

            self.add_task("update_items", update_items_)

        self.__items_binding.target_setter = update_items

    @property
    def selected_items(self) -> typing.AbstractSet[int]:
        return self.__selection.indexes

    def set_selected_index(self, index: int) -> None:
        self.__selection.set(index)
        self.__list_canvas_item.make_selection_visible()

    def update(self) -> None:
        self.__list_canvas_item.update()

    @property
    def current_index(self) -> int:
        return self.__selection.current_index

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__selection.set(index)

    def bind_current_index(self, binding):
        self.clear_task("update_current_index")
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        current_index = binding.get_target_value()
        if current_index is not None and 0 <= current_index < len(self.items):
            self.current_index = current_index
        self.__current_index_binding = binding
        def update_current_index(current_index):
            if current_index is not None and 0 <= current_index < len(self.items):
                def update_current_index_():
                    if self._behavior:
                        self.current_index = current_index
                self.add_task("update_current_index", update_current_index_)
        self.__current_index_binding.target_setter = update_current_index
        self.__on_current_index_changed = lambda index: self.__current_index_binding.update_source(index)

    def unbind_current_index(self):
        if self.__current_index_binding:
            self.__current_index_binding.close()
            self.__current_index_binding = None
        self.__on_current_index_changed = None


class StringListCanvasItemDelegate(ListCanvasItemDelegate):

    def __init__(self, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None):
        super().__init__()
        self.__item_getter = item_getter or (lambda x: x)

    def close(self):
        self.__item_getter = None

    def paint_item(self, drawing_context, display_item, rect, is_selected):

        def notnone(s) -> str:
            return str(s) if s is not None else str()

        item_string = notnone(self.__item_getter(display_item) if self.__item_getter else display_item)

        with drawing_context.saver():
            drawing_context.fill_style = "#000"
            drawing_context.font = "12px"
            drawing_context.text_align = 'left'
            drawing_context.text_baseline = 'bottom'
            drawing_context.fill_text(item_string, rect[0][1] + 4, rect[0][0] + 20 - 4)


class StringListWidget(ListWidget):
    """A widget with a list in a scroll bar."""

    # TODO: arguments after ui should be keyword required. current arguments are for backwards compatibility.
    def __init__(self, ui, items=None, selection_style=None, item_getter=None, *, properties=None, selection=None, border_color=None, v_scroll_enabled: bool=True, v_auto_resize: bool=False):
        super().__init__(ui, StringListCanvasItemDelegate(item_getter), items=items, selection_style=selection_style, properties=properties, selection=selection, border_color=border_color, v_scroll_enabled=v_scroll_enabled, v_auto_resize=v_auto_resize)


class TableWidget(CompositeWidgetBase):
    """A widget representing a table (column only)."""

    def __init__(self, ui, create_list_item_widget, header_widget=None, header_for_empty_list_widget=None):
        super().__init__(ui.create_column_widget())
        self.__binding = None
        self.content_section = ui.create_column_widget()
        self.content_section.widget_id = "content_section"
        header_column = ui.create_column_widget()
        self.header_widget = header_widget
        self.header_for_empty_list_widget = header_for_empty_list_widget
        if self.header_widget:
            header_column.add(self.header_widget)
        if self.header_for_empty_list_widget:
            header_column.add(self.header_for_empty_list_widget)
        self.content_widget.add(header_column)
        content_column = ui.create_column_widget()
        content_column.add(self.content_section)
        content_column.add_stretch()
        self.content_widget.add(content_column)
        self.content_widget.add_stretch()
        self.create_list_item_widget = create_list_item_widget

    def close(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_queued_tasks()
        self.content_section = None
        self.header_widget = None
        self.header_for_empty_list_widget = None
        self.create_list_item_widget = None
        super().close()

    @property
    def list_items(self):
        return self.content_section.children

    @property
    def list_item_count(self):
        return self.content_section.child_count

    def insert_item(self, item, before_index):
        if self.create_list_item_widget:  # item may be closed while this call is pending on main thread.
            item_row = self.create_list_item_widget(item)
            if self.content_section:
                self.content_section.insert(item_row, before_index)
                self.__sync_header()
            else:
                item_row.close()

    def remove_item(self, index):
        if self.content_section:
            self.content_section.remove(index)
            self.__sync_header()

    def remove_all_items(self):
        self.content_section.remove_all()
        self.__sync_header()

    def __sync_header(self):
        # select the right header item
        has_content = self.content_section.child_count > 0
        if self.header_widget:
            self.header_widget.visible = has_content
        if self.header_for_empty_list_widget:
            self.header_for_empty_list_widget.visible = not has_content

    def bind_items(self, binding):
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.__binding = binding
        def insert_item(item, before_index):
            self.queue_task(lambda: self.insert_item(item, before_index))
        def remove_item(index):
            self.queue_task(lambda: self.remove_item(index))
        self.__binding.inserter = insert_item
        self.__binding.remover = remove_item
        for index, item in enumerate(binding.items):
            self.insert_item(item, index)
        self.__sync_header()

    def unbind_items(self):
        if self.__binding:
            self.__binding.close()
            self.__binding = None


class TextButtonCell:

    def __init__(self, text: str):
        super().__init__()
        self.update_event = Event.Event()
        self.__text = text

    def paint_cell(self, drawing_context, rect, style):

        # disabled (default is enabled)
        # checked, partial (default is unchecked)
        # hover, active (default is none)

        drawing_context.text_baseline = "middle"
        drawing_context.text_align = "center"
        drawing_context.fill_style = "#000"
        drawing_context.fill_text(self.__text, rect.center.x, rect.center.y)

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


class TextButtonCanvasItem(CanvasItem.CellCanvasItem):

    def __init__(self, text: str):
        super().__init__()
        self.cell = TextButtonCell(text)
        self.wants_mouse_events = True
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None

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


class TextPushButtonWidget(CompositeWidgetBase):
    def __init__(self, ui, text: str):
        super().__init__(ui.create_column_widget())
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None
        font = "normal 11px serif"
        font_metrics = ui.get_font_metrics(font, text)
        text_button_canvas_item = TextButtonCanvasItem(text)
        text_button_canvas_item.update_sizing(text_button_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=font_metrics.height + 6, width=font_metrics.width + 6)))

        def button_clicked():
            if callable(self.on_button_clicked):
                self.on_button_clicked()

        text_button_canvas_item.on_button_clicked = button_clicked

        text_button_canvas_widget = ui.create_canvas_widget(properties={"height": 20, "width": 20})
        text_button_canvas_widget.canvas_item.add_canvas_item(text_button_canvas_item)
        # ugh. this is a partially working stop-gap when a canvas item is in a widget it will not get mouse exited reliably
        text_button_canvas_widget.on_mouse_exited = text_button_canvas_item.root_container.canvas_widget.on_mouse_exited

        self.content_widget.add(text_button_canvas_widget)


class ImageWidget(CompositeWidgetBase):
    def __init__(self, ui, rgba_bitmap_data: typing.Optional[numpy.ndarray] = None, properties = None):
        super().__init__(ui.create_column_widget(properties=properties))
        self.ui = ui
        self.on_clicked = None

        def button_clicked():
            if callable(self.on_clicked):
                self.on_clicked()

        self.__bitmap_canvas_item = CanvasItem.BitmapButtonCanvasItem(rgba_bitmap_data)
        self.__bitmap_canvas_item.on_button_clicked = button_clicked
        bitmap_canvas_widget = self.ui.create_canvas_widget()
        bitmap_canvas_widget.canvas_item.add_canvas_item(self.__bitmap_canvas_item)
        self.content_widget.add(bitmap_canvas_widget)

        self.image = rgba_bitmap_data

    @property
    def image(self) -> typing.Optional[numpy.ndarray]:
        return self.__rgba_bitmap_data

    @image.setter
    def image(self, rgba_bitmap_data: typing.Optional[numpy.ndarray]) -> None:
        self.__bitmap_canvas_item.rgba_bitmap_data = rgba_bitmap_data
        self.__rgba_bitmap_data = rgba_bitmap_data

    @property
    def background_color(self) -> typing.Optional[str]:
        return self.__bitmap_canvas_item.background_color

    @background_color.setter
    def background_color(self, background_color: typing.Optional[str]) -> None:
        self.__bitmap_canvas_item.background_color = background_color

    @property
    def border_color(self) -> typing.Optional[str]:
        return self.__bitmap_canvas_item.border_color

    @border_color.setter
    def border_color(self, border_color: typing.Optional[str]) -> None:
        self.__bitmap_canvas_item.border_color = border_color


class ColorButtonCell:

    def __init__(self, color: typing.Optional[str]):
        super().__init__()
        self.update_event = Event.Event()
        self.__color = color

    @property
    def color(self) -> typing.Optional[str]:
        return self.__color

    @color.setter
    def color(self, value: typing.Optional[str]) -> None:
        self.__color = value

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.FloatRect, style: str) -> None:
        # style: "disabled" (default is enabled)

        margin_rect = rect.inset(4, 4)

        drawing_context.begin_path()
        drawing_context.rect(margin_rect.left, margin_rect.top, margin_rect.width, margin_rect.height)
        drawing_context.fill_style = "#BBB"
        drawing_context.fill()

        inset_rect = margin_rect.inset(4, 4)

        drawing_context.begin_path()
        drawing_context.rect(inset_rect.left, inset_rect.top, inset_rect.width, inset_rect.height)
        drawing_context.close_path()
        drawing_context.fill_style = self.__color
        drawing_context.fill()

        drawing_context.begin_path()
        drawing_context.move_to(inset_rect.right, inset_rect.top)
        drawing_context.line_to(inset_rect.right, inset_rect.bottom)
        drawing_context.line_to(inset_rect.left, inset_rect.bottom)
        drawing_context.close_path()
        drawing_context.fill_style = DrawingContext.color_without_alpha(self.__color)
        drawing_context.fill()

        drawing_context.begin_path()
        drawing_context.rect(inset_rect.left, inset_rect.top, inset_rect.width, inset_rect.height)
        drawing_context.stroke_style = "#454545"
        drawing_context.stroke()

        if "disabled" in style:
            drawing_context.begin_path()
            drawing_context.rect(margin_rect.left, margin_rect.top, margin_rect.width, margin_rect.height)
            drawing_context.fill_style = "rgba(255, 255, 255, 0.5)"
            drawing_context.fill()


class ColorButtonCanvasItem(CanvasItem.CellCanvasItem):

    def __init__(self, color: typing.Optional[str]):
        super().__init__()
        self.cell = ColorButtonCell(color)
        self.wants_mouse_events = True
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_button_clicked = None
        super().close()

    def mouse_entered(self) -> None:
        self._mouse_inside = True

    def mouse_exited(self) -> None:
        self._mouse_inside = False

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        self._mouse_pressed = True

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        self._mouse_pressed = False

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True


class ColorPushButtonWidget(CompositeWidgetBase):
    def __init__(self, ui, color: typing.Optional[str] = None):
        super().__init__(ui.create_column_widget())

        self.on_color_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None

        color_button_canvas_item = ColorButtonCanvasItem(color)
        color_button_canvas_item.update_sizing(color_button_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=30, width=44)))

        def button_clicked():
            start_color = self.color or "rgba(255, 255, 255, 0.0)"
            color = ui.get_color_dialog(_("Select Color"), start_color, True)
            if color != start_color:
                self.color = color
                if callable(self.on_color_changed):
                    self.on_color_changed(self.color)

        color_button_canvas_item.on_button_clicked = button_clicked

        color_button_canvas_widget = ui.create_canvas_widget(properties={"height": 30, "width": 44})
        color_button_canvas_widget.canvas_item.add_canvas_item(color_button_canvas_item)
        # ugh. this is a partially working stop-gap when a canvas item is in a widget it will not get mouse exited reliably
        color_button_canvas_widget.on_mouse_exited = color_button_canvas_item.root_container.canvas_widget.on_mouse_exited

        self.__color_button_canvas_item = color_button_canvas_item

        self.content_widget.add(color_button_canvas_widget)

        self.__color_binding: typing.Optional[Binding.Binding] = None

    def close(self):
        if self.__color_binding:
            self.__color_binding.close()
            self.__color_binding = None
        self.clear_task("update_color")
        super().close()

    @property
    def color(self) -> typing.Optional[str]:
        return self.__color_button_canvas_item.cell.color

    @color.setter
    def color(self, color: typing.Optional[str]) -> None:
        if color != self.color:
            self.__color_button_canvas_item.cell.color = color
            self.__color_button_canvas_item.update()

    def bind_color(self, binding: Binding.Binding) -> None:
        if self.__color_binding:
            self.__color_binding.close()
            self.__color_binding = None
        self.color = binding.get_target_value()
        self.__color_binding = binding

        def update_color(color):
            def update_color_():
                if self._behavior:
                    self.color = color

            self.add_task("update_color", update_color_)

        self.__color_binding.target_setter = update_color

    def unbind_color(self) -> None:
        if self.__color_binding:
            self.__color_binding.close()
            self.__color_binding = None


class IconRadioButtonWidget(CompositeWidgetBase):

    def __init__(self, ui: UserInterface.UserInterface, properties: typing.Dict = None):
        super().__init__(ui.create_column_widget(properties=properties))
        self.ui = ui
        self.on_clicked = None
        self.__bitmap_canvas_item = CanvasItem.BitmapButtonCanvasItem(None, border_color="#CCC")
        self.__bitmap_canvas_item.on_button_clicked = self.__handle_clicked
        self.__value = None
        self.__group_value = None
        self.__on_group_value_changed = None
        self.__group_value_binding = None
        self.__icon_binding = None
        self.__enabled = True
        self.__checked = False
        bitmap_canvas_widget = self.ui.create_canvas_widget()
        bitmap_canvas_widget.canvas_item.add_canvas_item(self.__bitmap_canvas_item)
        self.content_widget.add(bitmap_canvas_widget)

    def close(self):
        if self.__group_value_binding:
            self.__group_value_binding.close()
            self.__group_value_binding = None
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None
        self.clear_task("update_icon")
        self.clear_task("update_group_value")
        super().close()

    def __handle_clicked(self) -> None:
        if self.__value is not None:
            self.group_value = self.__value
        if callable(self.on_clicked):
            self.on_clicked()

    @property
    def enabled(self) -> bool:
        return self.__bitmap_canvas_item.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        print(f"set enabled {self.__value} {self.__group_value}")
        self.__bitmap_canvas_item.enabled = value

    @property
    def checked(self) -> bool:
        return self.__bitmap_canvas_item.checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self.__bitmap_canvas_item.checked = value

    @property
    def icon(self) -> typing.Optional[numpy.ndarray]:
        return self.__bitmap_canvas_item.rgba_bitmap_data

    @icon.setter
    def icon(self, rgba_bitmap_data: typing.Optional[numpy.ndarray]) -> None:
        self.__bitmap_canvas_item.rgba_bitmap_data = rgba_bitmap_data

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = value
        self.checked = self.__group_value == self.__value

    @property
    def group_value(self):
        return self.__group_value

    @group_value.setter
    def group_value(self, group_value):
        self.__group_value = group_value
        self.checked = self.__group_value == self.__value
        if callable(self.__on_group_value_changed):
            self.__on_group_value_changed(group_value)

    # bind to value. takes ownership of binding.
    def bind_group_value(self, binding):
        if self.__group_value_binding:
            self.__group_value_binding.close()
            self.__group_value_binding = None
            self.__on_group_value_changed = None
        self.group_value = binding.get_target_value()
        self.__group_value_binding = binding
        def update_group_value(group_value):
            def update_group_value_():
                self.group_value = group_value
            self.add_task("update_group_value", update_group_value_)
        self.__group_value_binding.target_setter = update_group_value
        self.__on_group_value_changed = lambda group_value: self.__group_value_binding.update_source(group_value)

    def unbind_group_value(self):
        if self.__group_value_binding:
            self.__group_value_binding.close()
            self.__group_value_binding = None
        self.__on_group_value_changed = None

    def bind_icon(self, binding):
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None
        self.icon = binding.get_target_value()
        self.__icon_binding = binding

        def update_icon(icon):
            def update_icon_():
                self.icon = icon

            self.add_task("update_icon", update_icon_)

        self.__icon_binding.target_setter = update_icon

    def unbind_icon(self):
        if self.__icon_binding:
            self.__icon_binding.close()
            self.__icon_binding = None
