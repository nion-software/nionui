"""
A library of custom widgets.
"""

from __future__ import annotations

# standard libraries
import gettext
import functools
import typing

# third party libraries
import numpy

# local libraries
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.utils import Binding
from nion.utils import Event
from nion.utils import Geometry
from nion.utils import Model
from nion.utils import Selection

if typing.TYPE_CHECKING:
    from nion.ui import Window


_ = gettext.gettext


class CompositeWidgetBehavior:  # cannot subclass UserInterface.WidgetBehavior until mypy #4125 is available

    def __init__(self, content_widget: UserInterface.Widget) -> None:
        self.content_widget = content_widget
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None

    # subclasses should override to clear their variables.
    # subclasses should NOT call Qt code to delete anything here... that is done by the Qt code
    def close(self) -> None:
        # the content will be closed automatically since content widget gets returned as a contained item.
        # self.content_widget.close()
        self.content_widget = typing.cast(typing.Any, None)

    def periodic(self) -> None:
        self.content_widget.periodic()

    @property
    def widget(self) -> UserInterface.Widget:
        return self.content_widget

    def _set_root_container(self, root_container: typing.Optional[Window.Window]) -> None:
        self.content_widget._set_root_container(root_container)

    def _get_content_widget(self) -> typing.Optional[UserInterface.Widget]:
        return self.content_widget

    @property
    def focused(self) -> bool:
        return self.content_widget.focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        self.content_widget.focused = focused

    @property
    def does_retain_focus(self) -> bool:
        return self.content_widget.does_retain_focus

    @does_retain_focus.setter
    def does_retain_focus(self, value: bool) -> None:
        self.content_widget.does_retain_focus = value

    @property
    def visible(self) -> bool:
        return self.content_widget.visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        self.content_widget.visible = visible

    @property
    def enabled(self) -> bool:
        return self.content_widget.enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self.content_widget.enabled = enabled

    @property
    def size(self) -> Geometry.IntSize:
        return self.content_widget.size

    @size.setter
    def size(self, size: Geometry.IntSize) -> None:
        self.content_widget.size = size

    @property
    def tool_tip(self) -> typing.Optional[str]:
        return self.content_widget.tool_tip

    @tool_tip.setter
    def tool_tip(self, tool_tip: typing.Optional[str]) -> None:
        self.content_widget.tool_tip = tool_tip

    def set_background_color(self, value: typing.Optional[str]) -> None:
        self.content_widget.background_color = value

    def drag(self, mime_data: UserInterface.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
            self.content_widget.drag(mime_data, thumbnail, hot_spot_x, hot_spot_y, drag_finished_fn)

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return self.content_widget.map_to_global(p)

    def set_property(self, key: str, value: typing.Any) -> None:
        pass


class TabWidgetBehavior(CompositeWidgetBehavior):  # not subclass of UserInterface.TabWidgetBehavior until mypy #4125 is available
    def __init__(self, ui: UserInterface.UserInterface) -> None:
        column_widget = ui.create_column_widget()
        super().__init__(column_widget)
        self.__current_index_model = Model.PropertyModel[int](-1)
        self.ui = ui
        self.label_row = ui.create_row_widget()
        stretched_row = ui.create_row_widget()
        stretched_row.add(self.label_row)
        stretched_row.add_stretch()
        self.stack = ui.create_stack_widget()
        self.stack.bind_current_index(Binding.PropertyBinding(self.__current_index_model, "value"))
        divider = self.ui.create_canvas_widget(properties={"height": 1, "size_policy_horizontal": "expanding"})
        divider.canvas_item.add_canvas_item(CanvasItem.DividerCanvasItem(orientation="horizontal", color="gray"))
        column_widget.add(stretched_row)
        column_widget.add(divider)
        column_widget.add_spacing(4)
        column_widget.add(self.stack)
        self.__button_canvas_items: typing.List[CanvasItem.TextButtonCanvasItem] = list()

        def value_changed(value: typing.Optional[int]) -> None:
            value_ = max(0, min(value or 0, self.stack.child_count))
            for index, button_canvas_item in enumerate(self.__button_canvas_items):
                button_canvas_item.font = "12px bold" if value == index else "12px"
            if callable(self.on_current_index_changed):
                self.on_current_index_changed(value_)

        self.__current_index_model.on_value_changed = value_changed
        self.on_current_index_changed: typing.Optional[typing.Callable[[int], None]] = None

    def close(self) -> None:
        self.__current_index_model.on_value_changed = None
        self.on_current_index_changed = None
        super().close()

    def add(self, child: UserInterface.Widget, label: str) -> None:
        button_canvas_item = CanvasItem.TextButtonCanvasItem(label)
        button_canvas_item.border_enabled = False
        button_canvas_item.size_to_content(self.ui.get_font_metrics)
        button = self.ui.create_canvas_widget(properties={"height": button_canvas_item.sizing.preferred_height, "width": button_canvas_item.sizing.preferred_width})
        button.canvas_item.add_canvas_item(button_canvas_item)
        divider = self.ui.create_canvas_widget(properties={"width": 1, "size_policy_vertical": "expanding"})
        divider.canvas_item.add_canvas_item(CanvasItem.DividerCanvasItem(orientation="vertical", color="gray"))
        divider_group = self.ui.create_row_widget(properties={"min-height": 16})
        divider_group.add_spacing(4)
        divider_group.add(divider)
        divider_group.add_spacing(4)
        group = self.ui.create_row_widget()
        group.add(button)
        group.add(divider_group)
        self.label_row.add(group)
        self.stack.add(child)
        self.__button_canvas_items.append(button_canvas_item)

        def button_clicked(index: int) -> None:
            self.__current_index_model.value = index

        button_canvas_item.on_button_clicked = functools.partial(button_clicked, len(self.__button_canvas_items) - 1)

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass

    @property
    def current_index(self) -> int:
        return self.__current_index_model.value or 0

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index_model.value = index


class SectionWidget(UserInterface.Widget):
    """A widget representing a twist down section.

    The section is composed of a title in bold and then content.
    """

    def __init__(self, ui: UserInterface.UserInterface, section_title: str, section: UserInterface.Widget, section_id: typing.Optional[str] = None) -> None:
        section_widget = ui.create_column_widget()
        super().__init__(CompositeWidgetBehavior(section_widget))

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

        def set_expanded(expanded: typing.Optional[bool]) -> None:
            twist_down_canvas_item.checked = expanded or False
            section_content_column.visible = expanded or False
            if section_id:
                ui.set_persistent_string(section_id, "true" if twist_down_canvas_item.checked else "false")

        def toggle() -> None:
            self.expanded = not twist_down_canvas_item.checked

        section_open = ui.get_persistent_string(section_id, "true") == "true" if section_id else True
        twist_down_canvas_item.checked = section_open
        section_content_column.visible = section_open
        twist_down_canvas_item.on_button_clicked = toggle

        self.section_title_row = section_title_row
        self.__twist_down_canvas_item = twist_down_canvas_item

        def set_title(value: typing.Optional[str]) -> None:
            section_title_label.text = str(value) if value is not None else str()

        self.__title_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[str]](None, set_title)
        self.__expanded_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[bool]](None, set_expanded)

        self.title = section_title
        self.expanded = True

    def close(self) -> None:
        self.__title_binding_helper.close()
        self.__title_binding_helper = typing.cast(typing.Any, None)
        self.__expanded_binding_helper.close()
        self.__expanded_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def title(self) -> str:
        return self.__title_binding_helper.value or str()

    @title.setter
    def title(self, value: str) -> None:
        self.__title_binding_helper.value = value

    @property
    def expanded(self) -> bool:
        return self.__expanded_binding_helper.value or False

    @expanded.setter
    def expanded(self, value: bool) -> None:
        self.__expanded_binding_helper.value = value or False

    def bind_title(self, binding: Binding.Binding) -> None:
        self.__title_binding_helper.bind_value(binding)

    def unbind_title(self) -> None:
        self.__title_binding_helper.unbind_value()

    def bind_expanded(self, binding: Binding.Binding) -> None:
        self.__expanded_binding_helper.bind_value(binding)

    def unbind_expanded(self) -> None:
        self.__expanded_binding_helper.unbind_value()


class ListCanvasItemDelegate(ListCanvasItem.ListCanvasItemDelegate):

    def __init__(self) -> None:
        self.__items: typing.List[typing.Any] = list()
        self.on_item_selected: typing.Optional[typing.Callable[[int], None]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return self.__items

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        self.__items = list(value)

    @property
    def item_count(self) -> int:
        return len(self.__items)

    def key_pressed(self, key: UserInterface.Key) -> bool:
        if key.is_escape:
            if callable(self.on_cancel):
                self.on_cancel()
                # returning False here will allow window to handle the escape key.
                return False
        return False

    def item_selected(self, index: int) -> bool:
        if callable(self.on_item_selected):
            self.on_item_selected(index)
            return True
        return False

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, display_item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        raise NotImplementedError()


class ListWidget(UserInterface.Widget):
    """A widget with a list in a scroll bar."""

    def __init__(self, ui: UserInterface.UserInterface, list_item_delegate: ListCanvasItem.ListCanvasItemDelegate, *,
                 items: typing.Optional[typing.Sequence[typing.Any]] = None,
                 selection_style: typing.Optional[Selection.Style] = None,
                 properties: typing.Optional[typing.Mapping[str, typing.Any]] = None,
                 selection: typing.Optional[Selection.IndexedSelection] = None,
                 border_color: typing.Optional[str] = None, v_scroll_enabled: bool = True,
                 v_auto_resize: bool = False) -> None:
        column_widget = ui.create_column_widget()
        super().__init__(CompositeWidgetBehavior(column_widget))
        self.property_changed_event = Event.Event()
        items = items or list()
        self.__items: typing.List[typing.Any] = list()
        self.on_selection_changed: typing.Optional[typing.Callable[[typing.AbstractSet[int]], None]] = None
        self.on_item_selected: typing.Optional[typing.Callable[[int], bool]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None
        self.on_item_handle_context_menu: typing.Optional[typing.Callable[..., bool]] = None  # used for declarative
        self.__items_binding: typing.Optional[Binding.Binding] = None
        self.__v_auto_resize = v_auto_resize
        self.on_escape_pressed : typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed : typing.Optional[typing.Callable[[], bool]] = None

        self.__selection = selection if selection else Selection.IndexedSelection(selection_style)

        def selection_changed() -> None:
            self.__current_index_binding_helper.value_changed(self.__selection.current_index or 0)
            on_selection_changed = self.on_selection_changed
            if callable(on_selection_changed):
                on_selection_changed(self.__selection.indexes)

        def handle_delegate_cancel() -> None:
            if callable(self.on_cancel):
                self.on_cancel()
            if callable(self.on_escape_pressed):
                self.on_escape_pressed()

        def handle_delegate_item_selected(index: int) -> None:
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

        column_widget.add(canvas_widget)

        self.__canvas_widget = canvas_widget

        def set_current_index(index: int) -> None:
            self.__selection.set(index)

        def validate_current_index(new_value: int, old_value: int) -> int:
            return new_value if new_value >= 0 and new_value < len(self.items) else 0

        def set_items(items: typing.Sequence[typing.Any]) -> None:
            self.__set_items(items)

        self.__current_index_binding_helper = UserInterface.BindablePropertyHelper[int](None, set_current_index, validate_current_index)
        self.__items_binding_helper = UserInterface.BindablePropertyHelper[typing.Sequence[typing.Any]](None, set_items)

        self.items = list(items) if items else list()
        self.current_index = 0

    def close(self) -> None:
        self.__selection_changed_event_listener.close()
        self.__selection_changed_event_listener = typing.cast(typing.Any, None)
        self.on_selection_changed = None
        self.__items_binding_helper.close()
        self.__items_binding_helper = typing.cast(typing.Any, None)
        self.__current_index_binding_helper.close()
        self.__current_index_binding_helper = typing.cast(typing.Any, None)
        self.__items = typing.cast(typing.Any, None)
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
    def items(self) -> typing.Sequence[typing.Any]:
        return self.__items_binding_helper.value

    @items.setter
    def items(self, items: typing.Sequence[typing.Any]) -> None:
        self.__items_binding_helper.value = items

    def __set_items(self, items: typing.Sequence[typing.Any]) -> None:
        self.__items = list(items)

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

    def bind_items(self, binding: Binding.Binding) -> None:
        self.__items_binding_helper.bind_value(binding)

    def unbind_items(self) -> None:
        self.__items_binding_helper.unbind_value()

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
        return self.__current_index_binding_helper.value

    @current_index.setter
    def current_index(self, index: int) -> None:
        self.__current_index_binding_helper.value = index

    def bind_current_index(self, binding: Binding.Binding) -> None:
        self.__current_index_binding_helper.bind_value(binding)

    def unbind_current_index(self) -> None:
        self.__current_index_binding_helper.unbind_value()


class StringListCanvasItemDelegate(ListCanvasItemDelegate):

    def __init__(self, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None):
        super().__init__()
        self.__item_getter = item_getter or (lambda x: str(x))

    def close(self) -> None:
        self.__item_getter = typing.cast(typing.Any, None)

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, display_item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:

        def notnone(s: typing.Any) -> str:
            return str(s) if s is not None else str()

        item_string = notnone(self.__item_getter(display_item) if self.__item_getter else display_item)

        with drawing_context.saver():
            drawing_context.fill_style = "#000"
            drawing_context.font = "12px"
            drawing_context.text_align = 'left'
            drawing_context.text_baseline = 'bottom'
            drawing_context.fill_text(item_string, rect.left + 4, rect.top + 20 - 4)


class StringListWidget(ListWidget):
    """A widget with a list in a scroll bar."""

    # TODO: arguments after ui should be keyword required. current arguments are for backwards compatibility.
    def __init__(self, ui: UserInterface.UserInterface, items: typing.Optional[typing.Sequence[typing.Any]] = None,
                 selection_style: typing.Optional[Selection.Style] = None,
                 item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None, *,
                 properties: typing.Optional[typing.Mapping[str, typing.Any]] = None,
                 selection: typing.Optional[Selection.IndexedSelection] = None,
                 border_color: typing.Optional[str] = None, v_scroll_enabled: bool = True,
                 v_auto_resize: bool = False) -> None:
        super().__init__(ui, StringListCanvasItemDelegate(item_getter), items=items, selection_style=selection_style,
                         properties=properties, selection=selection, border_color=border_color,
                         v_scroll_enabled=v_scroll_enabled, v_auto_resize=v_auto_resize)


class TableWidget(UserInterface.Widget):
    """A widget representing a table (column only)."""

    def __init__(self, ui: UserInterface.UserInterface,
                 create_list_item_widget: typing.Callable[[typing.Any], UserInterface.BoxWidget],
                 header_widget: typing.Optional[UserInterface.Widget] = None,
                 header_for_empty_list_widget: typing.Optional[UserInterface.Widget] = None) -> None:
        column_widget = ui.create_column_widget()
        super().__init__(CompositeWidgetBehavior(column_widget))
        self.__binding: typing.Optional[Binding.Binding] = None
        self.content_section = ui.create_column_widget()
        self.content_section.widget_id = "content_section"
        header_column = ui.create_column_widget()
        self.header_widget = header_widget
        self.header_for_empty_list_widget = header_for_empty_list_widget
        if self.header_widget:
            header_column.add(self.header_widget)
        if self.header_for_empty_list_widget:
            header_column.add(self.header_for_empty_list_widget)
        column_widget.add(header_column)
        content_column = ui.create_column_widget()
        content_column.add(self.content_section)
        content_column.add_stretch()
        column_widget.add(content_column)
        column_widget.add_stretch()
        self.create_list_item_widget = create_list_item_widget

    def close(self) -> None:
        if self.__binding:
            self.__binding.close()
            self.__binding = None
        self.clear_queued_tasks()
        self.content_section = typing.cast(typing.Any, None)
        self.header_widget = None
        self.header_for_empty_list_widget = None
        self.create_list_item_widget = typing.cast(typing.Any, None)
        super().close()

    @property
    def list_items(self) -> typing.Sequence[UserInterface.Widget]:
        return self.content_section.children

    @property
    def list_item_count(self) -> int:
        return self.content_section.child_count

    def insert_item(self, item: typing.Any, before_index: int) -> None:
        if callable(self.create_list_item_widget):  # item may be closed while this call is pending on main thread.
            item_row = self.create_list_item_widget(item)
            if self.content_section:
                self.content_section.insert(item_row, before_index)
                self.__sync_header()
            else:
                item_row.close()

    def remove_item(self, index: int) -> None:
        if self.content_section:
            self.content_section.remove(index)
            self.__sync_header()

    def remove_all_items(self) -> None:
        self.content_section.remove_all()
        self.__sync_header()

    def __sync_header(self) -> None:
        # select the right header item
        has_content = self.content_section.child_count > 0
        if self.header_widget:
            self.header_widget.visible = has_content
        if self.header_for_empty_list_widget:
            self.header_for_empty_list_widget.visible = not has_content


class CellLike(typing.Protocol):
    update_event: Event.Event

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.IntRect, style: typing.Set[str]) -> None: ...


class TextButtonCell(CellLike):

    def __init__(self, text: str) -> None:
        self.update_event = Event.Event()
        self.__text = text

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.IntRect, style: typing.Set[str]) -> None:

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

    def __init__(self, text: str) -> None:
        super().__init__()
        self.cell = TextButtonCell(text)
        self.wants_mouse_events = True
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_button_clicked = None
        super().close()

    def mouse_entered(self) -> bool:
        self._mouse_inside = True
        return True

    def mouse_exited(self) -> bool:
        self._mouse_inside = False
        return True

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._mouse_pressed = True
        return True

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._mouse_pressed = False
        return True

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True


class TextPushButtonWidget(UserInterface.Widget):
    def __init__(self, ui: UserInterface.UserInterface, text: str) -> None:
        column_widget = ui.create_column_widget()
        super().__init__(CompositeWidgetBehavior(column_widget))
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None
        font = "normal 11px serif"
        font_metrics = ui.get_font_metrics(font, text)
        text_button_canvas_item = TextButtonCanvasItem(text)
        text_button_canvas_item.update_sizing(text_button_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=font_metrics.height + 6, width=font_metrics.width + 6)))

        def button_clicked() -> None:
            if callable(self.on_button_clicked):
                self.on_button_clicked()

        text_button_canvas_item.on_button_clicked = button_clicked

        text_button_canvas_widget = ui.create_canvas_widget(properties={"height": 20, "width": 20})
        text_button_canvas_widget.canvas_item.add_canvas_item(text_button_canvas_item)
        # ugh. this is a partially working stop-gap when a canvas item is in a widget it will not get mouse exited reliably
        root_container = text_button_canvas_item.root_container
        if root_container:
            text_button_canvas_widget.on_mouse_exited = root_container.canvas_widget.on_mouse_exited

        column_widget.add(text_button_canvas_widget)


class ImageWidget(UserInterface.Widget):
    def __init__(self, ui: UserInterface.UserInterface, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type] = None,
                 properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> None:
        column_widget = ui.create_column_widget(properties=properties)
        super().__init__(CompositeWidgetBehavior(column_widget))
        self.ui = ui
        self.on_clicked = None

        def button_clicked() -> None:
            if callable(self.on_clicked):
                self.on_clicked()

        self.__bitmap_canvas_item = CanvasItem.BitmapButtonCanvasItem(rgba_bitmap_data)
        self.__bitmap_canvas_item.on_button_clicked = button_clicked
        bitmap_canvas_widget = self.ui.create_canvas_widget()
        bitmap_canvas_widget.canvas_item.add_canvas_item(self.__bitmap_canvas_item)
        column_widget.add(bitmap_canvas_widget)

        def set_image(value: typing.Optional[DrawingContext.RGBA32Type]) -> None:
            self.__bitmap_canvas_item.rgba_bitmap_data = value

        self.__image_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[DrawingContext.RGBA32Type]](None, set_image, None, typing.cast(typing.Any, numpy.array_equal))

        self.image = rgba_bitmap_data

    def close(self) -> None:
        self.__image_binding_helper.close()
        self.__image_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def image(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__image_binding_helper.value

    @image.setter
    def image(self, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__image_binding_helper.value = rgba_bitmap_data

    def bind_image(self, binding: Binding.Binding) -> None:
        self.__image_binding_helper.bind_value(binding)

    def unbind_image(self) -> None:
        self.__image_binding_helper.unbind_value()

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


class ColorButtonCell(CellLike):

    def __init__(self, color: typing.Optional[str]):
        self.update_event = Event.Event()
        self.__color = color

    @property
    def color(self) -> typing.Optional[str]:
        return self.__color

    @color.setter
    def color(self, value: typing.Optional[str]) -> None:
        self.__color = value

    def paint_cell(self, drawing_context: DrawingContext.DrawingContext, rect: Geometry.IntRect, style: typing.Set[str]) -> None:
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
        self.color_button_cell = ColorButtonCell(color)
        self.cell = self.color_button_cell
        self.wants_mouse_events = True
        self.on_button_clicked: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        self.on_button_clicked = None
        super().close()

    def mouse_entered(self) -> bool:
        self._mouse_inside = True
        return True

    def mouse_exited(self) -> bool:
        self._mouse_inside = False
        return True

    def mouse_pressed(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._mouse_pressed = True
        return True

    def mouse_released(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        self._mouse_pressed = False
        return True

    def mouse_clicked(self, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> bool:
        if self.enabled:
            if self.on_button_clicked:
                self.on_button_clicked()
        return True


class ColorPushButtonWidget(UserInterface.Widget):
    def __init__(self, ui: UserInterface.UserInterface, color: typing.Optional[str] = None):
        column_widget = ui.create_column_widget()
        super().__init__(CompositeWidgetBehavior(column_widget))

        self.on_color_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None

        color_button_canvas_item = ColorButtonCanvasItem(color)
        color_button_canvas_item.update_sizing(color_button_canvas_item.sizing.with_fixed_size(Geometry.IntSize(height=30, width=44)))

        def button_clicked() -> None:
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
        root_container = color_button_canvas_item.root_container
        if root_container:
            color_button_canvas_widget.on_mouse_exited = root_container.canvas_widget.on_mouse_exited

        self.__color_button_canvas_item = color_button_canvas_item

        column_widget.add(color_button_canvas_widget)

        def set_color(color: typing.Optional[str]) -> None:
            self.__color_button_canvas_item.color_button_cell.color = color
            self.__color_button_canvas_item.update()

        self.__color_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[str]](None, set_color)

        self.color = color

    def close(self) -> None:
        self.__color_binding_helper.close()
        self.__color_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def color(self) -> typing.Optional[str]:
        return self.__color_binding_helper.value

    @color.setter
    def color(self, color: typing.Optional[str]) -> None:
        self.__color_binding_helper.value = color

    def bind_color(self, binding: Binding.Binding) -> None:
        self.__color_binding_helper.bind_value(binding)

    def unbind_color(self) -> None:
        self.__color_binding_helper.unbind_value()


class IconRadioButtonWidget(UserInterface.Widget):

    def __init__(self, ui: UserInterface.UserInterface, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None):
        column_widget = ui.create_column_widget(properties=properties)
        # must be available for enabled property in super class. needs refactoring.
        self.__bitmap_canvas_item = CanvasItem.BitmapButtonCanvasItem(None, border_color="#CCC")
        super().__init__(CompositeWidgetBehavior(column_widget))
        self.ui = ui
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None
        self.__bitmap_canvas_item.on_button_clicked = self.__handle_clicked
        self.__value: typing.Optional[int] = None
        self.__enabled = True
        self.__checked = False
        bitmap_canvas_widget = self.ui.create_canvas_widget()
        bitmap_canvas_widget.canvas_item.add_canvas_item(self.__bitmap_canvas_item)
        column_widget.add(bitmap_canvas_widget)

        def set_group_value(group_value: typing.Optional[int]) -> None:
            self.checked = group_value == self.__value

        def set_icon(value: typing.Optional[DrawingContext.RGBA32Type]) -> None:
            self.__bitmap_canvas_item.rgba_bitmap_data = value

        self.__group_value_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[typing.Optional[int]]](None, set_group_value)
        self.__icon_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[DrawingContext.RGBA32Type]](None, set_icon, None, typing.cast(typing.Any, numpy.array_equal))

    def close(self) -> None:
        self.__group_value_binding_helper.close()
        self.__group_value_binding_helper = typing.cast(typing.Any, None)
        self.__icon_binding_helper.close()
        self.__icon_binding_helper = typing.cast(typing.Any, None)
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
        self.__bitmap_canvas_item.enabled = value

    @property
    def checked(self) -> bool:
        return self.__bitmap_canvas_item.checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self.__bitmap_canvas_item.checked = value

    @property
    def icon(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__icon_binding_helper.value

    @icon.setter
    def icon(self, rgba_image: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__icon_binding_helper.value = rgba_image

    @property
    def value(self) -> typing.Optional[int]:
        return self.__value

    @value.setter
    def value(self, value: typing.Optional[int]) -> None:
        self.__value = value
        self.checked = self.group_value == self.__value

    @property
    def group_value(self) -> typing.Optional[int]:
        return self.__group_value_binding_helper.value

    @group_value.setter
    def group_value(self, group_value: typing.Optional[int]) -> None:
        self.__group_value_binding_helper.value = group_value

    def bind_group_value(self, binding: Binding.Binding) -> None:
        self.__group_value_binding_helper.bind_value(binding)

    def unbind_group_value(self) -> None:
        self.__group_value_binding_helper.unbind_value()

    def bind_icon(self, binding: Binding.Binding) -> None:
        self.__icon_binding_helper.bind_value(binding)

    def unbind_icon(self) -> None:
        self.__icon_binding_helper.unbind_value()


class CompositeWidgetBase(UserInterface.Widget):
    # deprecated - no longer required - just pass the behavior directly to the widget

    def __init__(self, content_widget: UserInterface.Widget) -> None:
        super().__init__(CompositeWidgetBehavior(content_widget))
