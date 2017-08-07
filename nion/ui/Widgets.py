"""
A library of custom widgets.
"""

# standard libraries
# None

# types
from typing import AbstractSet

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
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

    def drag(self, mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn):
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
        section_content_column.add_stretch()
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


class StringListWidget(CompositeWidgetBase):
    """A widget with a list in a scroll bar."""

    def __init__(self, ui, items, selection_style=None, stringify_item=None, properties=None):
        super().__init__(ui.create_column_widget())
        self.__items = items
        content_widget = self.content_widget
        self.on_selection_changed = None
        self.on_item_selected = None
        self.on_cancel = None
        stringify_item = str if stringify_item is None else stringify_item

        class ListCanvasItemDelegate:
            def __init__(self, string_list_widget, items, selection):
                self.__string_list_widget = string_list_widget
                self.__items = items
                self.__selection = selection

            @property
            def items(self):
                return self.__items

            @items.setter
            def items(self, value):
                self.__items = value

            @property
            def item_count(self):
                return len(self.__items)

            def on_context_menu_event(self, index, x, y, gx, gy):
                return False

            def on_delete_pressed(self):
                pass

            def on_key_pressed(self, key):
                if key.is_escape:
                    if callable(self.__string_list_widget.on_cancel):
                        self.__string_list_widget.on_cancel()
                        return True
                return False

            def on_drag_started(self, index, x, y, modifiers):
                pass

            def on_item_selected(self, index):
                if callable(self.__string_list_widget.on_item_selected):
                    return self.__string_list_widget.on_item_selected(index)
                return False

            def paint_item(self, drawing_context, display_item, rect, is_selected):
                item = stringify_item(display_item)
                with drawing_context.saver():
                    drawing_context.fill_style = "#000"
                    drawing_context.font = "12px"
                    drawing_context.text_align = 'left'
                    drawing_context.text_baseline = 'bottom'
                    drawing_context.fill_text(item, rect[0][1] + 4, rect[0][0] + 20 - 4)

        self.__selection = Selection.IndexedSelection(selection_style)

        def selection_changed():
            on_selection_changed = self.on_selection_changed
            if callable(on_selection_changed):
                on_selection_changed(self.__selection.indexes)

        self.__selection_changed_event_listener = self.__selection.changed_event.listen(selection_changed)
        self.__list_canvas_item_delegate = ListCanvasItemDelegate(self, items, self.__selection)
        self.__list_canvas_item = ListCanvasItem.ListCanvasItem(self.__list_canvas_item_delegate, self.__selection, 20)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(self.__list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_bar_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item)
        scroll_group_canvas_item = CanvasItem.CanvasItemComposition()
        scroll_group_canvas_item.border_color = "#888"
        scroll_group_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        scroll_group_canvas_item.add_canvas_item(scroll_area_canvas_item)
        scroll_group_canvas_item.add_canvas_item(scroll_bar_canvas_item)

        canvas_widget = ui.create_canvas_widget(properties=properties)
        canvas_widget.canvas_item.add_canvas_item(scroll_group_canvas_item)

        content_widget.add(canvas_widget)

        self.__canvas_widget = canvas_widget

    @property
    def focused(self) -> bool:
        return self.__canvas_widget.focused and self.__list_canvas_item.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self.__list_canvas_item.request_focus()

    @property
    def items(self):
        return self.__items

    @items.setter
    def items(self, value):
        self.__items = value
        self.__list_canvas_item_delegate.items = value
        self.__list_canvas_item.refresh_layout()
        self.__list_canvas_item.update()

    @property
    def selected_items(self) -> AbstractSet[int]:
        return self.__selection.indexes

    def set_selected_index(self, index: int) -> None:
        self.__selection.set(index)
        self.__list_canvas_item.make_selection_visible()

    def close(self) -> None:
        self.__selection_changed_event_listener.close()
        self.__selection_changed_event_listener = None
        self.on_selection_changed = None
        super().close()


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
            self.content_section.insert(item_row, before_index)
            self.__sync_header()

    def remove_item(self, index):
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
