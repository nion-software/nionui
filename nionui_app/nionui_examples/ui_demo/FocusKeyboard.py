"""A page exercising the keyboard focus: which widget has it, how it moves, and where the keys go.

The goals of this page are:

1. Report which widget has the keyboard focus, as announced by the widget itself. Every focusable widget on the
   page reports gaining and losing the focus, and the "Focused" label names whichever one currently claims it.
2. Report which widget answers that it is focused when it is asked, rather than waiting to be told. The "Poll
   Focus" button asks each widget in turn and the "Polled" label lists the answers. The two labels are meant to
   agree; where they disagree, a widget is announcing one thing and answering another.
3. Move the focus from outside the widget receiving it. The "Focus Name" and "Focus List" buttons set the focus
   the way a command or a validation failure would, rather than the user clicking the widget.
4. Give up the focus. "Clear Focus" unfocuses whatever holds the focus, leaving nothing focused.
5. Show the tab order. Tab should visit the two fields, the two buttons, and the list, in the order they appear
   on the page, and shift-tab should walk back.
6. Show where the keys go. Each key reaches only the widget which has the focus, and the "Last key" label names
   the key just pressed and the widget it arrived at. Only a key press appears there: choosing an item of the list
   by double clicking it is reported as a choice, on the status line, because it is not a key. The keys are passed
   on afterwards, so typing still fills in the field it was typed into.

   A field reports every key it receives. The list reports only the keys it does not act on itself, which is why
   return appears on the "Last key" label but the arrow keys do not: the list consumes those to move its selection,
   which the status line reports instead.

The widgets are chosen to cover the three ways a widget takes the focus: a line edit, which takes it and keeps it
while editing; a push button, which takes it to be pressed by the keyboard; and a list view, which takes it on
behalf of the canvas items displaying its rows.
"""
from __future__ import annotations

import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.utils import ListModel
from nion.utils import Model


class Item:
    """An item of the list, displayed as one row of the list view."""

    def __init__(self, title: str) -> None:
        self.title = title

    def __str__(self) -> str:
        return self.title


class RowHandler(Declarative.Handler):
    """Display one item of the list."""

    def __init__(self, item: Item) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.title = item.title
        self.ui_view = u.create_row(u.create_label(text="@binding(title)"), u.create_stretch(), margin=4)


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it.
        self.container_handler: typing.Any = None
        self.name_line_edit: typing.Optional[UserInterface.LineEditWidget] = None
        self.color_line_edit: typing.Optional[UserInterface.LineEditWidget] = None
        self.first_button: typing.Optional[UserInterface.PushButtonWidget] = None
        self.second_button: typing.Optional[UserInterface.PushButtonWidget] = None
        self.list_view: typing.Optional[Widgets.ListViewWidget] = None
        self.items_model = ListModel.ListModel[Item]("items", items=[Item("Alpha"), Item("Beta"), Item("Gamma")])
        self.current_index_model = Model.PropertyModel(0)
        self.focus_model = Model.PropertyModel("Focused: nothing")
        self.polled_model = Model.PropertyModel("Polled: (not yet polled)")
        self.last_key_model = Model.PropertyModel("Last key: (none yet)")
        self.status_model = Model.PropertyModel("")
        self.__focused_title: typing.Optional[str] = None

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[RowHandler]:
        return RowHandler(item) if component_id == "row" else None

    @property
    def __focusable_widgets(self) -> typing.Sequence[typing.Tuple[str, typing.Optional[UserInterface.Widget]]]:
        # the widgets which can take the focus, in the order they appear on the page, which is the order tab is
        # expected to visit them in.
        return (("Name", self.name_line_edit), ("Color", self.color_line_edit), ("First", self.first_button),
                ("Second", self.second_button), ("List", self.list_view))

    def __title_of(self, widget: UserInterface.Widget) -> str:
        for title, focusable_widget in self.__focusable_widgets:
            if focusable_widget is widget:
                return title
        return "an unnamed widget"

    def __widget_titled(self, title: str) -> typing.Optional[UserInterface.Widget]:
        for focusable_title, focusable_widget in self.__focusable_widgets:
            if focusable_title == title:
                return focusable_widget
        return None

    def __report_key(self, title: str, key_name: str) -> None:
        # the last key only: a running log of keys says nothing the last one does not, and reads as noise next to
        # the focus labels it is meant to be compared against.
        self.last_key_model.value = f"Last key: {key_name} → {title}"

    # goals 1 and 6: the widget announces the focus arriving and leaving.

    def focus_changed(self, widget: UserInterface.Widget, focused: bool) -> None:
        # a widget losing the focus reports separately from the next one gaining it, and in no guaranteed order, so
        # only the widget which claimed the focus may report giving it up.
        title = self.__title_of(widget)
        if focused:
            self.__focused_title = title
        elif self.__focused_title == title:
            self.__focused_title = None
        self.focus_model.value = f"Focused: {self.__focused_title or 'nothing'}"

    # goal 2: the widget answers whether it is focused when asked.

    def poll_focus(self, widget: UserInterface.PushButtonWidget) -> None:
        titles = [title for title, w in self.__focusable_widgets if w and w.focused]
        self.polled_model.value = "Polled: " + (", ".join(titles) if titles else "nothing")

    # goals 3 and 4: the focus is moved and cleared from outside the widget holding it.

    def focus_name(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__request_focus("Name")

    def focus_list(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__request_focus("List")

    def clear_focus(self, widget: UserInterface.PushButtonWidget) -> None:
        for title, focusable_widget in self.__focusable_widgets:
            if focusable_widget and focusable_widget.focused:
                focusable_widget.focused = False
        self.status_model.value = "Cleared the focus"

    def __request_focus(self, title: str) -> None:
        widget = self.__widget_titled(title)
        if widget:
            widget.focused = True
            self.status_model.value = f"Asked {title} for the focus"

    # goal 5: the keys arrive at the widget holding the focus.

    def key_pressed(self, widget: UserInterface.Widget, key: UserInterface.Key) -> bool:
        # returning False passes the key on to the widget itself, so a character still ends up in the field it was
        # typed into and tab still moves the focus.
        self.__report_key(self.__title_of(widget), describe_key(key))
        return False

    def return_pressed(self, widget: UserInterface.Widget) -> bool:
        # the list view reports return on its own rather than through a key handler.
        self.__report_key(self.__title_of(widget), "Return")
        return False

    def item_selected(self, widget: UserInterface.Widget, current_index: int) -> bool:
        # an item chosen by double clicking it, which is not a key press and so is not reported as one.
        items = self.items_model.items
        title = items[current_index].title if 0 <= current_index < len(items) else None
        self.status_model.value = f"Chose {title}"
        return False

    def item_changed(self, widget: UserInterface.Widget, current_index: typing.Optional[int]) -> None:
        # the arrow keys reaching the focused list show up as its selection changing.
        items = self.items_model.items
        title = items[current_index].title if current_index is not None and 0 <= current_index < len(items) else None
        self.status_model.value = f"List selection: {title}"

    def button_clicked(self, widget: UserInterface.PushButtonWidget) -> None:
        self.status_model.value = f"Clicked {self.__title_of(widget)}"


def describe_key(key: UserInterface.Key) -> str:
    """Name a key the way a menu would, so that the key log reads as what was typed."""
    named_keys = (("Tab", key.is_tab), ("Backtab", key.is_backtab), ("Return", key.is_enter_or_return),
                  ("Escape", key.is_escape), ("Backspace", key.is_backspace), ("Delete", key.is_delete),
                  ("Up", key.is_up_arrow), ("Down", key.is_down_arrow), ("Left", key.is_left_arrow),
                  ("Right", key.is_right_arrow))
    name = next((named_key for named_key, is_key in named_keys if is_key), None)
    if name is None:
        if key.text == " ":
            name = "Space"
        elif key.text and key.text.isprintable():
            name = key.text
        else:
            name = f"#{key.key}"
    modifiers = key.modifiers
    prefixes = [prefix for prefix, is_down in (("shift", modifiers.shift), ("control", modifiers.control),
                                               ("alt", modifiers.alt), ("meta", modifiers.meta)) if is_down]
    return "+".join(prefixes + [name])


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # the focusable widgets appear in the order tab should visit them in.

    # a line edit takes the focus and keeps it while the text is edited.
    name_line_edit = u.create_line_edit(placeholder_text="Name", name="name_line_edit", width=120,
                                        on_focus_changed="focus_changed", on_key_pressed="key_pressed")
    color_line_edit = u.create_line_edit(placeholder_text="Color", name="color_line_edit", width=120,
                                         on_focus_changed="focus_changed", on_key_pressed="key_pressed")
    field_row = u.create_row(name_line_edit, color_line_edit, u.create_stretch(), spacing=8)

    # a push button takes the focus so that it can be pressed by the keyboard.
    first_button = u.create_push_button(text="First", name="first_button", on_clicked="button_clicked",
                                        on_focus_changed="focus_changed")
    second_button = u.create_push_button(text="Second", name="second_button", on_clicked="button_clicked",
                                         on_focus_changed="focus_changed")
    button_row = u.create_row(first_button, second_button, u.create_stretch(), spacing=8)

    # a list view takes the focus on behalf of the canvas items displaying its rows; the arrow keys then move its
    # selection and return chooses an item.
    list_view = u.create_list_view(items="items_model.items", item_component_id="row", item_height=24,
                                   name="list_view", current_index="@binding(current_index_model.value)",
                                   on_item_changed="item_changed", on_item_selected="item_selected",
                                   on_return_pressed="return_pressed",
                                   on_focus_changed="focus_changed", width=200, height=90)

    # the buttons which move the focus are deliberately not focusable targets themselves in the list above: they
    # stand in for a command moving the focus somewhere the user is not currently working.
    focus_row = u.create_row(u.create_push_button(text="Focus Name", on_clicked="focus_name"),
                             u.create_push_button(text="Focus List", on_clicked="focus_list"),
                             u.create_push_button(text="Clear Focus", on_clicked="clear_focus"),
                             u.create_push_button(text="Poll Focus", on_clicked="poll_focus"),
                             u.create_stretch(), spacing=8)

    return u.create_column(
        u.create_label(text="Press tab to move the focus; type to see where the keys go."),
        field_row,
        button_row,
        list_view,
        focus_row,
        u.create_label(text="@binding(focus_model.value)"),
        u.create_label(text="@binding(polled_model.value)"),
        u.create_label(text="@binding(last_key_model.value)"),
        u.create_label(text="@binding(status_model.value)"),
        spacing=8)
