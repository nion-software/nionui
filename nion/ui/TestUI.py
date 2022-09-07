from __future__ import annotations

# standard libraries
import collections
import enum
import json
import pathlib
import typing

# third party libraries
import numpy

# local libraries
from . import CanvasItem
from . import DrawingContext
from . import UserInterface as UserInterfaceModule
from nion.utils import Geometry

if typing.TYPE_CHECKING:
    from . import Application
    from . import Window


focused_widget: typing.Optional[WidgetBehavior] = None  # simulate focus handling at the widget level


class TestFontMetrics:
    def __init__(self,
                 display_scaling: float,
                 font_metrics_height: int,
                 font_metrics_ascent: int,
                 font_metrics_descent: int,
                 font_metrics_leading: int,
                 font_width_and_chars: typing.Dict[int, str],
                 default_char_width: int):
        """
        :param font_width_and_chars: iterator over `(width, chars)` where `chars` is the string consisting
            of characters whose width is `width` for the font.
        :param default_char_width:
        """
        font_chars_by_width = dict(font_width_and_chars)

        font_width_by_char: typing.Dict[str, int] = dict()
        for width, chars in font_chars_by_width.items():
            font_width_by_char.update((char, width) for char in chars)

        self._display_scaling = display_scaling
        self._font_metrics_height = font_metrics_height
        self._font_metrics_ascent = font_metrics_ascent
        self._font_metrics_descent = font_metrics_descent
        self._font_metrics_leading = font_metrics_leading
        self._font_width_by_char = font_width_by_char
        self._default_char_width = default_char_width

    def get_font_metrics(self, font_str: str, text: str) -> UserInterfaceModule.FontMetrics:
        def get_char_width(c: str) -> int:
            return self._font_width_by_char.get(c, self._default_char_width)

        var_text_width = int(round(sum(map(get_char_width, text))))
        return UserInterfaceModule.FontMetrics(width=var_text_width / self._display_scaling,
                                               height=self._font_metrics_height / self._display_scaling,
                                               ascent=self._font_metrics_ascent / self._display_scaling,
                                               descent=self._font_metrics_descent / self._display_scaling,
                                               leading=self._font_metrics_leading / self._display_scaling)


def calculate_font_metric_info_for_tests(font_str: str, display_scaling: float) -> str:
    """
    For now, this is hardcoded to use Qt for the font metrics

    This is only used to make the :py:class:nion.ui.TestUI.UserInterface.get_font_metrics
    slightly more realistic in calculating text with for a var width font, so the details
    should not matter. Tests should not make assumptions about the exact text sizes returned.

    :return: a string containing the Python code to construct a :py:class:TestFontMetrics instance
        approximating the Qt font metrics for the font described by the arguments. The code
        is indented 4 spaces, so it can be copied to the body of a top-level function.
    """
    # Use local imports so Qt is not required for module to load
    from nion.ui.PyQtProxy import ParseFontString, QtGui  # type: ignore
    font = ParseFontString(font_str, display_scaling)

    font_metrics = QtGui.QFontMetrics(font)

    font_metrics_height = font_metrics.height()
    font_metrics_ascent = font_metrics.ascent()
    font_metrics_descent = font_metrics.descent()
    font_metrics_leading = font_metrics.leading()

    default_char_width = font_metrics.width('M')

    font_chars_arr_by_width = collections.defaultdict(list)

    for char_ord in range(ord(' '), ord('~')+ 1):
        char = chr(char_ord)
        width = font_metrics.width(char)
        font_chars_arr_by_width[width].append(char)

    # Sort by numbers of characters at a given width, descending
    font_chars_str_by_width = dict(
        (k, ''.join(v)) for k, v in sorted(font_chars_arr_by_width.items(),
                                           key=lambda _: (-len(_[1]), _[0])))

    font_chars_by_width_dict_entries = "\n".join(
        "            {}: {},".format(width, json.dumps(chars))
        for width, chars in font_chars_str_by_width.items()
    )

    test_font_metrics_str = f"""
    TestFontMetrics(
        display_scaling={display_scaling},
        font_metrics_height={font_metrics_height},
        font_metrics_ascent={font_metrics_ascent},
        font_metrics_descent={font_metrics_descent},
        font_metrics_leading={font_metrics_leading},
        font_width_and_chars={{\n{font_chars_by_width_dict_entries}
        }},
        default_char_width={default_char_width}
    )
    """.strip('\n')

    return test_font_metrics_str


def make_font_metrics_for_tests() -> TestFontMetrics:
    """
    The body came from running the following in a NionSwift console on a Mac:

        from nion.ui.TestUI import calculate_font_metric_info_for_tests
        print(calculate_font_metric_info_for_tests(font_str="normal 11px serif", display_scaling=1.0))

    """
    return TestFontMetrics(
        display_scaling=1.0,
        font_metrics_height=13,
        font_metrics_ascent=11,
        font_metrics_descent=2,
        font_metrics_leading=0,
        font_width_and_chars={
            7: "#$+02345689<=>ABEKPRSTVYZ^bdghopq~",
            6: "7?FJL_`aceknsuvxyz",
            3: " !',./:;I\\ijl|",
            4: "()[]frt{}",
            8: "&CDGHNUX",
            5: "\"*-1",
            10: "%@Mm",
            9: "OQw",
            11: "W",
        },
        default_char_width=10
    )


class MimeData(UserInterfaceModule.MimeData):
    def __init__(self, mime_data: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> None:
        self.mime_data = dict() if mime_data is None else dict(mime_data)

    @property
    def formats(self) -> typing.Sequence[str]:
        return list(self.mime_data.keys())

    @property
    def file_paths(self) -> typing.Sequence[str]:
        urls = self.urls
        file_paths = []
        for url in urls:
            file_paths.append(url)
        return file_paths

    def data_as_string(self, format: str) -> str:
        return str(self.mime_data.get(format))

    def set_data_as_string(self, format: str, text: str) -> None:
        self.mime_data[format] = text


class MenuItem(UserInterfaceModule.MenuAction):
    def __init__(self, title: str, action_id: str, callback: typing.Optional[typing.Callable[[], None]],
                 key_sequence: typing.Optional[str], role: typing.Optional[str],
                 menu: typing.Optional[UserInterfaceModule.Menu], is_separator: bool, checked: bool) -> None:
        super().__init__(action_id)
        self.__title = title
        self.callback = callback
        self.key_sequence = key_sequence,
        self.role = role
        self.menu = menu
        self.is_separator = is_separator
        self.__checked = checked
        self.__enabled = True

    def close(self) -> None:
        self.callback = None
        super().close()

    @property
    def title(self) -> str:
        return self.__title or str()

    @title.setter
    def title(self, value: str) -> None:
        self.__title = value

    @property
    def checked(self) -> bool:
        return self.__checked

    @checked.setter
    def checked(self, checked: bool) -> None:
        self.__checked = checked

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self.__enabled = enabled


class Menu(UserInterfaceModule.Menu):
    def __init__(self, document_window: UserInterfaceModule.Window, title: typing.Optional[str] = None,
                 menu_id: typing.Optional[str] = None) -> None:
        super().__init__(document_window, title or str(), menu_id or str())
        self.on_popup: typing.Optional[typing.Callable[[UserInterfaceModule.Menu, int, int], None]] = None

    def add_menu_item(self, title: str, callback: typing.Callable[[], None], key_sequence: typing.Optional[str] = None,
                      role: typing.Optional[str] = None,
                      action_id: typing.Optional[str] = None) -> UserInterfaceModule.MenuAction:
        menu_item = MenuItem(title, action_id or str(), callback, key_sequence, role, None, False, False)
        self._item_added(action=menu_item)
        return menu_item

    def add_sub_menu(self, title: str, menu: UserInterfaceModule.Menu) -> None:
        menu_item = MenuItem(title, str(), None, None, None, menu, False, False)
        self._item_added(sub_menu=menu_item.menu)

    def add_separator(self) -> None:
        self._item_added(is_separator=True)

    def popup(self, gx: int, gy: int) -> None:
        if self.on_popup:
            self.on_popup(self, gx, gy)


class ItemModelController:
    DRAG = 0
    DROP = 1

    class Item:
        def __init__(self, data: typing.Any = None) -> None:
            self.children: typing.List[ItemModelController.Item] = list()
            self.parent: typing.Optional[ItemModelController.Item] = None
            self.id: typing.Optional[int] = None
            self.data = data if data else {}

        def insert_child(self, before_index: int, item: ItemModelController.Item) -> None:
            item.parent = self
            self.children.insert(before_index, item)

        def remove_child(self, item: ItemModelController.Item) -> None:
            item.parent = None
            self.children.remove(item)

        def child(self, index: int) -> ItemModelController.Item:
            return self.children[index]

        @property
        def row(self) -> int:
            if self.parent:
                return self.parent.children.index(self)
            return -1

    def __init__(self) -> None:
        self.__next_id = 0
        self.root = self.create_item()

    def close(self) -> None:
        pass

    def create_item(self, data: typing.Any = None) -> ItemModelController.Item:
        item = ItemModelController.Item(data)
        item.id = self.__next_id
        self.__next_id = self.__next_id + 1
        return item

    def item_from_id(self, item_id: typing.Optional[int], parent: typing.Optional[ItemModelController.Item] = None) -> typing.Optional[ItemModelController.Item]:
        item = []  # nonlocal in Python 3.1+

        def fn(parent: typing.Optional[ItemModelController.Item], index: typing.Optional[int],
               child: ItemModelController.Item) -> bool:
            if child.id == item_id:
                item.append(child)
                return True
            return False

        self.traverse(fn)
        return item[0] if item else None

    def __item_id(self, index: int, parent_id: int) -> typing.Optional[int]:
        parent = self.item_from_id(parent_id)
        assert parent is not None
        if index >= 0 and index < len(parent.children):
            return parent.children[index].id
        return 0  # invalid id

    def item_value_for_item_id(self, role: str, index: int, item_id: typing.Optional[int]) -> typing.Any:
        child = self.item_from_id(item_id)
        if role == "index":
            return index
        if child and role in child.data:
            return child.data[role]
        return None

    def item_value(self, role: str, index: int, parent_id: int) -> typing.Any:
        return self.item_value_for_item_id(role, index, self.__item_id(index, parent_id))

    def begin_insert(self, first_row: int, last_row: int, parent_row: int, parent_id: int) -> None:
        pass

    def end_insert(self) -> None:
        pass

    def begin_remove(self, first_row: int, last_row: int, parent_row: int, parent_id: int) -> None:
        pass

    def end_remove(self) -> None:
        pass

    def data_changed(self, row: int, parent_row: int, parent_id: int) -> None:
        pass

    def traverse_depth_first(self, fn: typing.Callable[[typing.Optional[ItemModelController.Item], typing.Optional[int], ItemModelController.Item], bool],
                             parent: ItemModelController.Item) -> bool:
        real_parent = parent if parent else self.root
        for index, child in enumerate(real_parent.children):
            if self.traverse_depth_first(fn, child):
                return True
            if fn(parent, index, child):
                return True
        return False

    def traverse(self, fn: typing.Callable[[typing.Optional[ItemModelController.Item], typing.Optional[int], ItemModelController.Item], bool]) -> None:
        if not fn(None, 0, self.root):
            self.traverse_depth_first(fn, self.root)


class ListModelController:
    DRAG = 0
    DROP = 1

    def __init__(self) -> None:
        self.model: typing.List[typing.Any] = []

    def close(self) -> None:
        pass

    def begin_insert(self, first_row: int, last_row: int) -> None:
        pass

    def end_insert(self) -> None:
        pass

    def begin_remove(self, first_row: int, last_row: int) -> None:
        pass

    def end_remove(self) -> None:
        pass

    def data_changed(self) -> None:
        pass


class Key(UserInterfaceModule.Key):
    def __init__(self, text: str, key: str, modifiers: UserInterfaceModule.KeyboardModifiers) -> None:
        self.__text = text
        self.__key = key
        self.__modifiers = modifiers if modifiers else CanvasItem.KeyboardModifiers()

    @property
    def text(self) -> str:
        return self.__text

    @property
    def key(self) -> int:
        return 0

    @property
    def modifiers(self) -> UserInterfaceModule.KeyboardModifiers:
        return self.__modifiers

    @property
    def is_delete(self) -> bool:
        return self.__key == "delete"

    @property
    def is_enter_or_return(self) -> bool:
        return self.__key == "enter" or self.__key == "return"

    @property
    def is_tab(self) -> bool:
        return self.__key == "tab"

    @property
    def is_arrow(self) -> bool:
        return self.is_left_arrow or self.is_up_arrow or self.is_right_arrow or self.is_down_arrow

    @property
    def is_left_arrow(self) -> bool:
        return self.__key == "left"

    @property
    def is_up_arrow(self) -> bool:
        return self.__key == "up"

    @property
    def is_right_arrow(self) -> bool:
        return self.__key == "right"

    @property
    def is_down_arrow(self) -> bool:
        return self.__key == "down"

    @property
    def is_delete_to_end_of_line(self) -> bool:
        return self.__key == "delete_to_end_of_line"

    @property
    def is_end(self) -> bool:
        return self.__key == "end"

    @property
    def is_escape(self) -> bool:
        return self.__key == "escape"

    @property
    def is_home(self) -> bool:
        return self.__key == "home"

    @property
    def is_insert(self) -> bool:
        return self.__key == "insert"

    @property
    def is_move_to_end_of_line(self) -> bool:
        return self.__key == "end_of_line"

    @property
    def is_move_to_start_of_line(self) -> bool:
        return self.__key == "start_of_line"

    @property
    def is_page_down(self) -> bool:
        return self.__key == "page_down"

    @property
    def is_page_up(self) -> bool:
        return self.__key == "page_up"


class ButtonGroup:

    def __init__(self) -> None:
        self.on_button_clicked: typing.Optional[typing.Callable[[str], None]] = None

    def close(self) -> None:
        self.on_button_clicked = None

    def add_button(self, radio_button: UserInterfaceModule.RadioButtonWidget, button_id: str) -> None:
        pass

    def remove_button(self, radio_button: UserInterfaceModule.RadioButtonWidget) -> None:
        pass

    def clicked(self, button_id: str) -> None:
        if self.on_button_clicked:
            self.on_button_clicked(button_id)


class Widget:

    def __init__(self, widget_type: str) -> None:
        self.widget_type = widget_type
        self.children: typing.List[Widget] = list()
        self.size: typing.Optional[Geometry.IntSize] = None
        self.on_size_changed: typing.Optional[typing.Callable[[typing.Optional[Geometry.IntSize]], None]] = None

    def close(self) -> None:
        self.children = typing.cast(typing.List[Widget], None)

    def size_changed(self, size: typing.Optional[Geometry.IntSize]) -> None:
        if size != self.size:
            self.size = size
            if callable(self.on_size_changed):
                self.on_size_changed(size)
        for child in self.children:
            child.size_changed(size)


class WidgetBehavior:

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        self.widget = Widget(widget_type)
        self.widget.on_size_changed = self._size_changed
        self.does_retain_focus = False
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self._no_focus = "no_focus"
        self.__focused = False
        self.visible = True
        self.enabled = True
        self.size: Geometry.IntSize = Geometry.IntSize()
        self.tool_tip: typing.Optional[str] = None
        self.children: typing.List[Widget] = list()
        self.content: typing.Optional[UserInterfaceModule.Widget] = None
        self.canvas_item: typing.Optional[CanvasItem.AbstractCanvasItem] = None

    def close(self) -> None:
        if callable(getattr(self.widget, "close", None)):
            self.widget.close()
        self.on_ui_activity = None
        self.on_context_menu_event = None
        self.on_focus_changed = None
        self.on_size_changed = None
        self.children = list()
        self.content = None
        self.canvas_item = None

    def periodic(self) -> None:
        pass

    def _set_root_container(self, window: typing.Optional[Window.Window]) -> None:
        pass

    def _get_content_widget(self) -> typing.Optional[UserInterfaceModule.Widget]:
        return None

    def _register_ui_activity(self) -> None:
        pass

    @property
    def focused(self) -> bool:
        return self.__focused

    @focused.setter
    def focused(self, focused: bool) -> None:
        global focused_widget
        if self.__focused != focused:
            if focused and focused_widget != self:
                if focused_widget:
                    focused_widget.focused = False
                focused_widget = self
            self.__focused = focused
            if self.on_focus_changed:
                self.on_focus_changed(focused)

    def set_background_color(self, color: typing.Optional[str]) -> None:
        pass

    def set_property(self, key: str, value: typing.Any) -> None:
        pass

    def _size_changed(self, size: typing.Optional[Geometry.IntSize]) -> None:
        pass

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return p

    def drag(self, mime_data: UserInterfaceModule.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        pass


class NullBehavior:

    def __init__(self) -> None:
        self.focused = False
        self.does_retain_focus = False
        self.visible = True
        self.enabled = True
        self.size = Geometry.IntSize()
        self.tool_tip: typing.Optional[str] = None
        self.on_ui_activity: typing.Optional[typing.Callable[[], None]] = None
        self.on_context_menu_event: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_focus_changed: typing.Optional[typing.Callable[[bool], None]] = None
        self.widget = None

    def close(self) -> None:
        pass

    def periodic(self) -> None:
        pass

    def _set_root_container(self, window: typing.Optional[Window.Window]) -> None:
        pass

    def _get_content_widget(self) -> typing.Optional[UserInterfaceModule.Widget]:
        return None

    def set_property(self, key: str, value: typing.Any) -> None:
        pass

    def map_to_global(self, p: Geometry.IntPoint) -> Geometry.IntPoint:
        return Geometry.IntPoint()

    def drag(self, mime_data: UserInterfaceModule.MimeData, thumbnail: typing.Optional[DrawingContext.RGBA32Type] = None,
             hot_spot_x: typing.Optional[int] = None, hot_spot_y: typing.Optional[int] = None,
             drag_finished_fn: typing.Optional[typing.Callable[[str], None]] = None) -> None:
        pass

    def set_background_color(self, value: typing.Optional[str]) -> None:
        pass


class BoxStretch(UserInterfaceModule.Widget):

    def __init__(self) -> None:
        super().__init__(NullBehavior())


class BoxSpacing(UserInterfaceModule.Widget):

    def __init__(self, spacing: int):
        super().__init__(NullBehavior())
        self.spacing = spacing


def extract_widget(widget: typing.Optional[UserInterfaceModule.Widget]) -> typing.Optional[Widget]:
    content_widget = widget._behavior._get_content_widget() if widget else None
    if content_widget:
        return extract_widget(content_widget)
    return typing.cast(typing.Optional[Widget], widget._behavior.widget if widget else None)


class WidgetItemType(enum.Enum):
    WIDGET = 0
    STRETCH = 1
    SPACING = 2


class WidgetItem:

    def __init__(self, type: WidgetItemType, *, widget: typing.Optional[Widget] = None, fill: bool = False,
                 alignment: typing.Optional[str] = None, spacing: int = 0) -> None:
        self.type = type
        self.widget = widget
        self.fill = fill
        self.alignment = alignment
        self.spacing = spacing


class BoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.__widgets: typing.List[WidgetItem] = list()

    def insert(self, child: UserInterfaceModule.Widget, index_or_widget: typing.Optional[typing.Union[UserInterfaceModule.Widget, int]], fill: bool = False, alignment: typing.Optional[str] = None) -> None:
        # behavior must handle index of None, meaning insert at end
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = index_or_widget if isinstance(index_or_widget, int) else len(self.__widgets)
        self.__widgets.insert(index, WidgetItem(WidgetItemType.WIDGET, widget=child_widget, fill=fill, alignment=alignment))
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size)

    def add_stretch(self) -> UserInterfaceModule.Widget:
        self.__widgets.append(WidgetItem(WidgetItemType.STRETCH))
        self.widget.children.append(Widget("stretch"))
        return BoxStretch()

    def add_spacing(self, spacing: int) -> UserInterfaceModule.Widget:
        self.__widgets.append(WidgetItem(WidgetItemType.SPACING, spacing=spacing))
        self.widget.children.append(Widget("spacing"))
        return BoxSpacing(spacing)

    def remove_all(self) -> None:
        self.__widgets.clear()
        self.widget.children.clear()


class SplitterWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.__children: typing.List[UserInterfaceModule.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def add(self, child: UserInterfaceModule.Widget) -> None:
        # behavior must handle index of None, meaning insert at end
        self.__children.append(child)
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = len(self.widget.children)
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size)

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass


class TabWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.current_index = 0
        self.on_current_index_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.__children: typing.List[UserInterfaceModule.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def add(self, child: UserInterfaceModule.Widget, label: str) -> None:
        self.__children.append(child)

    def restore_state(self, tag: str) -> None:
        pass

    def save_state(self, tag: str) -> None:
        pass


class StackWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.current_index = -1
        self.__children: typing.List[UserInterfaceModule.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def insert(self, child: UserInterfaceModule.Widget, index: int) -> None:
        # behavior must handle index of None, meaning insert at end
        self.__children.insert(index, child)
        child_widget = extract_widget(child)
        assert child_widget is not None
        index = index if index is not None else len(self.widget.children)
        self.widget.children.insert(index, child_widget)
        child_widget.size_changed(self.widget.size or Geometry.IntSize())

    def add(self, child: UserInterfaceModule.Widget) -> None:
        self.__children.append(child)
        child_widget = extract_widget(child)
        assert child_widget
        self.widget.children.append(child_widget)

    def remove(self, child: UserInterfaceModule.Widget) -> None:
        self.__children.remove(child)
        child_widget = extract_widget(child)
        assert child_widget
        self.widget.children.remove(child_widget)


class GroupWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.title: typing.Optional[str] = None
        self.__children: typing.List[UserInterfaceModule.Widget] = list()

    def close(self) -> None:
        for child in self.__children:
            child.close()
        super().close()

    def add(self, child: UserInterfaceModule.Widget) -> None:
        self.__children.append(child)

    def remove(self, child: UserInterfaceModule.Widget) -> None:
        self.__children.remove(child)


class ScrollAreaWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.on_size_changed: typing.Optional[typing.Callable[[int, int], None]] = None
        self.on_viewport_changed: typing.Optional[typing.Callable[[Geometry.RectIntTuple], None]] = None

    def close(self) -> None:
        self.on_size_changed = None
        self.on_viewport_changed = None
        super().close()

    def set_content(self, content: typing.Optional[UserInterfaceModule.Widget]) -> None:
        assert not self.widget.children
        child_widget = extract_widget(content)
        assert child_widget
        self.widget.children.append(child_widget)
        child_widget.size_changed(self.widget.size or Geometry.IntSize())

    # called from widget
    def _size_changed(self, size: typing.Optional[Geometry.IntSize]) -> None:
        self._register_ui_activity()
        if callable(self.on_size_changed) and size:
            self.on_size_changed(size.width, size.height)

    def scroll_to(self, x: int, y: int) -> None:
        pass

    def set_scrollbar_policies(self, horizontal_policy: str, vertical_policy: str) -> None:
        pass

    def info(self) -> None:
        pass


class ComboBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.on_current_text_changed: typing.Optional[typing.Callable[[str], None]] = None
        self.current_index = 0
        self.item_strings: typing.List[str] = list()

    def close(self) -> None:
        self.on_current_text_changed = None
        super().close()

    @property
    def current_text(self) -> str:
        return self.item_strings[self.current_index] if 0 <= self.current_index < len(self.item_strings) else str()

    @current_text.setter
    def current_text(self, value: str) -> None:
        if 0 <= self.current_index < len(self.item_strings):
            self.item_strings[self.current_index] = value

    def set_item_strings(self, item_strings: typing.Sequence[str]) -> None:
        self.item_strings = list(item_strings)


class PushButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.text: typing.Optional[str] = None
        self.icon: typing.Optional[DrawingContext.RGBA32Type] = None
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None


class RadioButtonWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.text: typing.Optional[str] = None
        self.icon: typing.Optional[DrawingContext.RGBA32Type] = None
        self.checked = False
        self.on_clicked: typing.Optional[typing.Callable[[], None]] = None


class CheckBoxWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.text: typing.Optional[str] = None
        self.check_state = "checked"
        self.tristate = False
        self.on_check_state_changed: typing.Optional[typing.Callable[[str], None]] = None


class LabelWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.text: typing.Optional[str] = None
        self.word_wrap = False

    def set_text_color(self, color: typing.Optional[str]) -> None:
        pass

    def set_text_font(self, font_str: typing.Optional[str]) -> None:
        pass


class SliderWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.value = 0
        self.minimum = 0
        self.maximum = 100
        self.on_value_changed: typing.Optional[typing.Callable[[int], None]] = None
        self.on_slider_pressed: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_released: typing.Optional[typing.Callable[[], None]] = None
        self.on_slider_moved: typing.Optional[typing.Callable[[int], None]] = None

    @property
    def pressed(self) -> bool:
        return False


class CanvasWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.on_mouse_entered: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_exited: typing.Optional[typing.Callable[[], None]] = None
        self.on_mouse_clicked: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], bool]] = None
        self.on_mouse_double_clicked: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], bool]] = None
        self.on_mouse_pressed: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], bool]] = None
        self.on_mouse_released: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], bool]] = None
        self.on_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], None]] = None
        self.on_grabbed_mouse_position_changed: typing.Optional[typing.Callable[[int, int, UserInterfaceModule.KeyboardModifiers], None]] = None
        self.on_wheel_changed: typing.Optional[typing.Callable[[int, int, int, int, bool], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterfaceModule.Key], bool]] = None
        self.on_key_released: typing.Optional[typing.Callable[[UserInterfaceModule.Key], bool]] = None
        self.on_drag_enter: typing.Optional[typing.Callable[[UserInterfaceModule.MimeData], str]] = None
        self.on_drag_leave: typing.Optional[typing.Callable[[], str]] = None
        self.on_drag_move: typing.Optional[typing.Callable[[UserInterfaceModule.MimeData, int, int], str]] = None
        self.on_drop: typing.Optional[typing.Callable[[UserInterfaceModule.MimeData, int, int], str]] = None
        self.on_tool_tip: typing.Optional[typing.Callable[[int, int, int, int], bool]] = None
        self.on_pan_gesture: typing.Optional[typing.Callable[[int, int], bool]] = None
        self.__focusable = False

    def close(self) -> None:
        self.on_mouse_entered = None
        self.on_mouse_exited = None
        self.on_mouse_clicked = None
        self.on_mouse_double_clicked = None
        self.on_mouse_pressed = None
        self.on_mouse_released = None
        self.on_mouse_position_changed = None
        self.on_grabbed_mouse_position_changed = None
        self.on_wheel_changed = None
        self.on_key_pressed = None
        self.on_key_released = None
        self.on_size_changed = None
        self.on_drag_enter = None
        self.on_drag_leave = None
        self.on_drag_move = None
        self.on_drop = None
        self.on_tool_tip = None
        self.on_pan_gesture = None
        super().close()

    def _set_canvas_item(self, canvas_item: CanvasItem.AbstractCanvasItem) -> None:
        pass

    def periodic(self) -> None:
        pass

    @property
    def focusable(self) -> bool:
        return self.__focusable

    @focusable.setter
    def focusable(self, focusable: bool) -> None:
        self.__focusable = focusable

    def draw(self, drawing_context: DrawingContext.DrawingContext) -> None:
        pass

    def draw_section(self, section_id: int, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect) -> None:
        pass

    def remove_section(self, section_id: int) -> None:
        pass

    def set_cursor_shape(self, cursor_shape: typing.Optional[str]) -> None:
        cursor_shape = cursor_shape or "arrow"

    def grab_gesture(self, gesture_type: str) -> None:
        pass

    def release_gesture(self, gesture_type: str) -> None:
        pass

    def grab_mouse(self, gx: int, gy: int) -> None:
        pass

    def release_mouse(self) -> None:
        pass

    def show_tool_tip_text(self, text: str, gx: int, gy: int) -> None:
        pass


class LineEditWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.on_editing_finished: typing.Optional[typing.Callable[[str], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterfaceModule.Key], bool]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[str], None]] = None
        self.__clear_button_enabled = False
        self._no_focus = "click_focus"
        self.text: typing.Optional[str] = str()
        self.placeholder_text: typing.Optional[str] = str()
        self.editable = True
        self.clear_button_enabled = False

    def close(self) -> None:
        self.on_editing_finished = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_text_edited = None
        super().close()

    @property
    def selected_text(self) -> typing.Optional[str]:
        return self.text

    def select_all(self) -> None:
        pass

    def editing_finished(self, text: str) -> None:
        self.text = text
        if self.on_editing_finished:
            self.on_editing_finished(text)


class TextEditWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.on_cursor_position_changed: typing.Optional[typing.Callable[[UserInterfaceModule.CursorPosition], None]] = None
        self.on_selection_changed: typing.Optional[typing.Callable[[UserInterfaceModule.Selection], None]] = None
        self.on_text_changed: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_text_edited: typing.Optional[typing.Callable[[typing.Optional[str]], None]] = None
        self.on_escape_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_return_pressed: typing.Optional[typing.Callable[[], bool]] = None
        self.on_key_pressed: typing.Optional[typing.Callable[[UserInterfaceModule.Key], bool]] = None
        self.on_insert_mime_data: typing.Optional[typing.Callable[[UserInterfaceModule.MimeData], None]] = None
        self._no_focus = "click_focus"
        self.text: typing.Optional[str] = str()
        self.selected_text: typing.Optional[str] = str()
        self.placeholder: typing.Optional[str] = str()
        self.editable = True
        self.word_wrap_mode = "optimal"

    def close(self) -> None:
        self.on_cursor_position_changed = None
        self.on_selection_changed = None
        self.on_text_changed = None
        self.on_escape_pressed = None
        self.on_return_pressed = None
        self.on_key_pressed = None
        self.on_insert_mime_data = None
        super().close()

    @property
    def cursor_position(self) -> UserInterfaceModule.CursorPosition:
        return UserInterfaceModule.CursorPosition(0, 0, 0)

    @property
    def selection(self) -> UserInterfaceModule.Selection:
        return UserInterfaceModule.Selection(0, 0)

    def append_text(self, value: str) -> None:
        if self.text:
            self.text += value
        else:
            self.text = value

    def insert_text(self, value: str) -> None:
        if self.text:
            self.text += value
        else:
            self.text = value

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


class TreeWidgetBehavior(WidgetBehavior):

    def __init__(self, widget_type: str, properties: typing.Optional[typing.Mapping[str, typing.Any]]) -> None:
        super().__init__(widget_type, properties)
        self.selection_mode = str()
        self.item_model_controller: typing.Any = None
        self.on_key_pressed: typing.Optional[typing.Callable[[typing.Sequence[int], UserInterfaceModule.Key], bool]] = None
        self.on_tree_selection_changed: typing.Optional[typing.Callable[[typing.Sequence[typing.Tuple[int, int, int]]], None]] = None
        self.on_tree_item_changed: typing.Optional[typing.Callable[[int, int, int], None]] = None
        self.on_tree_item_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_tree_item_double_clicked: typing.Optional[typing.Callable[[int, int, int], bool]] = None
        self.on_tree_item_key_pressed: typing.Optional[typing.Callable[[int, int, int, UserInterfaceModule.Key], bool]] = None

    def set_current_row(self, index: int, parent_row: int, parent_id: int) -> None:
        pass

    def clear_current_row(self) -> None:
        pass

    def size_to_content(self) -> None:
        pass


class DocumentWindow(UserInterfaceModule.Window):

    def __init__(self, size: typing.Optional[Geometry.IntSize] = None):
        super().__init__(None, "title")
        self.__size = size if size is not None else Geometry.IntSize(height=720, width=960)
        self.__title: typing.Optional[str] = None

    def request_close(self) -> None:
        if self.on_about_to_close:
            self.on_about_to_close(str(), str())

    def _attach_root_widget(self, root_widget: typing.Optional[UserInterfaceModule.Widget]) -> None:
        widget = extract_widget(root_widget)
        if widget:
            widget.size_changed(self.__size)

    def _set_title(self, value: str) -> None:
        self.__title = value

    def _set_window_file_path(self, value: typing.Optional[pathlib.Path]) -> None:
        self.__window_file_path = value

    def set_palette_color(self, role: str, r: int, g: int, b: int, a: int) -> None:
        pass

    def set_window_style(self, styles: typing.Sequence[str]) -> None:
        pass

    def set_attributes(self, attributes: typing.Sequence[str]) -> None:
        pass

    @property
    def position(self) -> Geometry.IntPoint:
        return Geometry.IntPoint(x=0, y=0)

    @property
    def size(self) -> Geometry.IntSize:
        return Geometry.IntSize(w=640, h=480)

    def create_dock_widget(self, widget: UserInterfaceModule.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> UserInterfaceModule.DockWidget:
        dock_widget = DockWidget(self, widget, panel_id, title, positions, position)
        dock_widget.size_changed(Geometry.IntSize(height=320, width=480))
        return dock_widget

    def tabify_dock_widgets(self, dock_widget1: UserInterfaceModule.DockWidget, dock_widget2: UserInterfaceModule.DockWidget) -> None:
        pass

    def insert_menu(self, title: str, before_menu: UserInterfaceModule.Menu, menu_id: typing.Optional[str] = None) -> UserInterfaceModule.Menu:
        menu = Menu(self)
        self._menu_inserted(menu, before_menu)
        return menu

    def add_menu(self, title: str, menu_id: typing.Optional[str] = None) -> UserInterfaceModule.Menu:
        menu = Menu(self, menu_id)
        self._menu_added(menu)
        return menu

    def show(self, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        pass

    def restore(self, geometry: str, state: str) -> None:
        pass

    def _get_focus_widget(self) -> typing.Optional[UserInterfaceModule.Widget]:
        return None
        # wrong type. disabling.
        # global focused_widget
        # return focused_widget


class DockWidget(UserInterfaceModule.DockWidget):

    def __init__(self, window: DocumentWindow, widget: UserInterfaceModule.Widget, panel_id: str, title: str, positions: typing.Sequence[str], position: str) -> None:
        super().__init__(window, widget, panel_id, title, positions, position)
        self.visible = False
        self.__focus_policy = "no_focus"
        self.does_retain_focus = False

    @property
    def toggle_action(self) -> UserInterfaceModule.MenuAction:
        action = UserInterfaceModule.MenuAction("toggle_dock_widget_" + self.panel_id)
        action.on_ui_activity = self._register_ui_activity
        return action

    def show(self) -> None:
        self.visible = True
        self._register_ui_activity()

    def hide(self) -> None:
        self.visible = False
        self._register_ui_activity()

    def size_changed(self, size: Geometry.IntSize) -> None:
        self._handle_size_changed(size)


class UserInterface(UserInterfaceModule.UserInterface):

    def __init__(self) -> None:
        CanvasItem._threaded_rendering_enabled = False
        self.clipboard: UserInterfaceModule.MimeData = MimeData()
        self.popup: typing.Optional[UserInterfaceModule.Menu] = None
        self.popup_pos: typing.Optional[typing.Tuple[int, int]] = None
        self._font_metrics = make_font_metrics_for_tests()

    def close(self) -> None:
        pass

    def run(self, app: Application.BaseApplication) -> None:
        pass

    def request_quit(self) -> None:
        pass

    def set_application_info(self, name: str, organization: str, domain: str) -> None:
        pass

    # data objects

    def create_mime_data(self) -> MimeData:
        return MimeData()

    def create_item_model_controller(self) -> typing.Any:
        return ItemModelController()

    def create_button_group(self) -> ButtonGroup:
        return ButtonGroup()

    # window elements

    def create_document_window(self, title: typing.Optional[str] = None, parent_window: typing.Optional[UserInterfaceModule.Window] = None) -> UserInterfaceModule.Window:
        return DocumentWindow()

    def destroy_document_window(self, document_window: UserInterfaceModule.Window) -> None:
        document_window.close()

    def create_row_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.BoxWidget:
        return UserInterfaceModule.BoxWidget(BoxWidgetBehavior("row", properties), alignment)

    def create_column_widget(self, alignment: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.BoxWidget:
        return UserInterfaceModule.BoxWidget(BoxWidgetBehavior("column", properties), alignment)

    def create_splitter_widget(self, orientation: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.SplitterWidget:
        return UserInterfaceModule.SplitterWidget(SplitterWidgetBehavior("splitter", properties), orientation)

    def create_tab_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.TabWidget:
        return UserInterfaceModule.TabWidget(TabWidgetBehavior("tab", properties))

    def create_stack_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.StackWidget:
        return UserInterfaceModule.StackWidget(StackWidgetBehavior("stack", properties))

    def create_group_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.GroupWidget:
        return UserInterfaceModule.GroupWidget(GroupWidgetBehavior("group", properties))

    def create_scroll_area_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.ScrollAreaWidget:
        return UserInterfaceModule.ScrollAreaWidget(ScrollAreaWidgetBehavior("scrollarea", properties))

    def create_combo_box_widget(self, items: typing.Optional[typing.Sequence[typing.Any]] = None, item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.ComboBoxWidget:
        return UserInterfaceModule.ComboBoxWidget(ComboBoxWidgetBehavior("combobox", properties), items or list(), item_getter or (lambda x: str(x)))

    def create_push_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.PushButtonWidget:
        return UserInterfaceModule.PushButtonWidget(PushButtonWidgetBehavior("pushbutton", properties), text)

    def create_radio_button_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.RadioButtonWidget:
        return UserInterfaceModule.RadioButtonWidget(RadioButtonWidgetBehavior("radiobutton", properties), text)

    def create_check_box_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.CheckBoxWidget:
        return UserInterfaceModule.CheckBoxWidget(CheckBoxWidgetBehavior("checkbox", properties), text)

    def create_label_widget(self, text: typing.Optional[str] = None, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.LabelWidget:
        return UserInterfaceModule.LabelWidget(LabelWidgetBehavior("label", properties), text)

    def create_slider_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.SliderWidget:
        return UserInterfaceModule.SliderWidget(SliderWidgetBehavior("slider", properties))

    def create_progress_bar_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.ProgressBarWidget:
        return UserInterfaceModule.ProgressBarWidget(CanvasWidgetBehavior("canvas", properties))

    def create_line_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.LineEditWidget:
        return UserInterfaceModule.LineEditWidget(LineEditWidgetBehavior("lineedit", properties))

    def create_text_edit_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.TextEditWidget:
        return UserInterfaceModule.TextEditWidget(TextEditWidgetBehavior("textedit", properties))

    def create_canvas_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None, *, layout_render: typing.Optional[str] = None) -> UserInterfaceModule.CanvasWidget:
        return UserInterfaceModule.CanvasWidget(CanvasWidgetBehavior("canvas", properties), layout_render=layout_render)

    def create_tree_widget(self, properties: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> UserInterfaceModule.TreeWidget:
        return UserInterfaceModule.TreeWidget(TreeWidgetBehavior("pytree", properties))

    # file i/o

    def load_rgba_data_from_file(self, filename: str) -> typing.Optional[DrawingContext.RGBA32Type]:
        return numpy.zeros((20,20), numpy.uint32)

    def save_rgba_data_to_file(self, data: DrawingContext.RGBA32Type, filename: str, format: typing.Optional[str]) -> None:
        pass

    def get_existing_directory_dialog(self, title: str, directory: str) -> typing.Tuple[str, str]:
        return directory, directory

    def get_file_paths_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        raise NotImplementedError()

    def get_file_path_dialog(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], str, str]:
        raise NotImplementedError()

    def get_save_file_path(self, title: str, directory: str, filter: str, selected_filter: typing.Optional[str] = None) -> typing.Tuple[str, str, str]:
        raise NotImplementedError()

    # persistence (associated with application)

    def get_data_location(self) -> str:
        return str()

    def get_document_location(self) -> str:
        return str()

    def get_temporary_location(self) -> str:
        return str()

    def get_configuration_location(self) -> str:
        return str()

    def set_persistence_handler(self, handler: UserInterfaceModule.PersistenceHandler) -> None:
        pass

    def get_persistent_string(self, key: str, default_value: typing.Optional[str] = None) -> str:
        return default_value or str()

    def set_persistent_string(self, key: str, value: str) -> None:
        pass

    def get_persistent_object(self, key: str, default_value: typing.Optional[typing.Any] = None) -> typing.Any:
        return default_value

    def set_persistent_object(self, key: str, value: typing.Optional[typing.Any]) -> None:
        pass

    def remove_persistent_key(self, key: str) -> None:
        pass

    # clipboard

    def clipboard_clear(self) -> None:
        self.clipboard = MimeData()

    def clipboard_mime_data(self) -> UserInterfaceModule.MimeData:
        return self.clipboard

    def clipboard_set_mime_data(self, mime_data: UserInterfaceModule.MimeData) -> None:
        self.clipboard = mime_data

    def clipboard_set_text(self, text: str) -> None:
        self.clipboard = MimeData()
        self.clipboard.set_data_as_string('text', text)

    def clipboard_text(self) -> str:
        return self.clipboard.data_as_string('text')

    # misc

    def create_rgba_image(self, drawing_context: DrawingContext.DrawingContext, width: int, height: int) -> typing.Optional[DrawingContext.RGBA32Type]:
        return numpy.zeros((height, width), dtype=numpy.uint32)

    def get_font_metrics(self, font_str: str, text: str) -> UserInterfaceModule.FontMetrics:
        return self._font_metrics.get_font_metrics(font_str, text)

    def truncate_string_to_width(self, font_str: str, text: str, pixel_width: int, mode: UserInterfaceModule.TruncateModeType) -> str:
        return text

    def get_qt_version(self) -> str:
        return "TEST"

    def get_tolerance(self, tolerance_type: UserInterfaceModule.ToleranceType) -> float:
        return 5

    def create_context_menu(self, document_window: UserInterfaceModule.Window) -> UserInterfaceModule.Menu:
        menu = Menu(document_window)
        def handle_popup(menu: UserInterfaceModule.Menu, gx: int, gy: int) -> None:
            self.popup = menu
            self.popup_pos = gx, gy
        menu.on_popup = handle_popup
        return menu

    def create_sub_menu(self, document_window: UserInterfaceModule.Window, title: typing.Optional[str] = None, menu_id: typing.Optional[str] = None) -> UserInterfaceModule.Menu:
        return Menu(document_window, title)

    def get_color_dialog(self, title: str, color: typing.Optional[str], show_alpha: bool) -> typing.Optional[str]:
        return color

    def get_keyboard_modifiers(self, query: bool = False) -> UserInterfaceModule.KeyboardModifiers:
        return CanvasItem.KeyboardModifiers()

    # testing

    def create_key_by_id(self, key_id: str, modifiers: typing.Optional[CanvasItem.KeyboardModifiers] = None) -> UserInterfaceModule.Key:
        return Key(str(), key_id, modifiers or CanvasItem.KeyboardModifiers())

    def create_modifiers_by_id_list(self, modifiers_id_list: typing.Sequence[str]) -> CanvasItem.KeyboardModifiers:
        shift = False
        control = False
        alt = False
        meta = False
        keypad = False
        for modifiers_id in modifiers_id_list:
            if modifiers_id == "shift":
                shift = True
            elif modifiers_id == "control":
                control = True
            elif modifiers_id == "alt":
                alt = True
            elif modifiers_id == "meta":
                meta = True
            elif modifiers_id == "keypad":
                keypad = True
        return CanvasItem.KeyboardModifiers(shift, control, alt, meta, keypad)
