"""
A library of custom widgets.
"""

# standard libraries
import copy
import typing

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import Selection


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

    def __init__(self, ui, section_title: str, section, section_id: str=None):
        super().__init__(ui.create_column_widget())

        section_widget = self.content_widget

        section_title_row = ui.create_row_widget()

        twist_down_canvas_item = CanvasItem.TwistDownCanvasItem()

        twist_down_canvas_widget = ui.create_canvas_widget(properties={"height": 20, "width": 20})
        twist_down_canvas_widget.canvas_item.add_canvas_item(twist_down_canvas_item)

        section_title_row.add(twist_down_canvas_widget)
        section_title_row.add(ui.create_label_widget(section_title, properties={"stylesheet": "font-weight: bold"}))
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

    def key_pressed(self, key):
        if key.is_escape:
            if callable(self.on_cancel):
                self.on_cancel()
                return True
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
        items = items or list()
        self.__items = list()
        self.on_selection_changed = None
        self.on_item_selected = None
        self.on_cancel = None
        self.__items_binding = None
        self.__v_auto_resize = v_auto_resize

        self.__selection = selection if selection else Selection.IndexedSelection(selection_style)

        def selection_changed():
            on_selection_changed = self.on_selection_changed
            if callable(on_selection_changed):
                on_selection_changed(self.__selection.indexes)

        def handle_delegate_cancel():
            if callable(self.on_cancel):
                self.on_cancel()

        def handle_delegate_item_selected(index):
            if callable(self.on_item_selected):
                self.on_item_selected(index)

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
        self.__items = None
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
            new_sizing.minimum_height = content_height
            new_sizing.preferred_height = content_height
            new_sizing.maximum_height = content_height
            self.__canvas_widget.canvas_item.update_sizing(new_sizing)

            self.__canvas_widget.set_property("min-height", content_height)
            self.__canvas_widget.set_property("max-height", content_height)
            self.__canvas_widget.set_property("size-policy-vertical", "fixed")

        # setting items on the widget will not update items on the bound items since the list widget is merely a view

    def bind_items(self, binding) -> None:
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


class StringListCanvasItemDelegate(ListCanvasItemDelegate):

    def __init__(self, item_getter):
        super().__init__()
        self.__item_getter = item_getter

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


class TextPushButtonWidget(CompositeWidgetBase):
    def __init__(self, ui, text: str):
        super().__init__(ui.create_column_widget())
        self.on_button_clicked = None
        font = "normal 11px serif"
        font_metrics = ui.get_font_metrics(font, text)
        text_button_canvas_item = TextButtonCanvasItem(text)
        text_button_canvas_item.sizing.set_fixed_size(Geometry.IntSize(height=font_metrics.height + 6, width=font_metrics.width + 6))

        def button_clicked():
            if callable(self.on_button_clicked):
                self.on_button_clicked()

        text_button_canvas_item.on_button_clicked = button_clicked

        text_button_canvas_widget = ui.create_canvas_widget(properties={"height": 20, "width": 20})
        text_button_canvas_widget.canvas_item.add_canvas_item(text_button_canvas_item)
        # ugh. this is a partially working stop-gap when a canvas item is in a widget it will not get mouse exited reliably
        text_button_canvas_widget.on_mouse_exited = text_button_canvas_item.root_container.canvas_widget.on_mouse_exited

        self.content_widget.add(text_button_canvas_widget)
