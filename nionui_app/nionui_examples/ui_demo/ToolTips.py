import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import ListModel
from nion.utils import Model


class NamedItem:
    """An item displayed by its name, carrying the tool tip shown while the mouse rests on it.

    A list displays an item by its string conversion and takes its tool tip from its `tool_tip` attribute, so any
    object with the two will do.
    """

    def __init__(self, name: str, tool_tip: str) -> None:
        self.name = name
        self.tool_tip = tool_tip

    def __str__(self) -> str:
        return self.name


class ItemHandler(Declarative.Handler):
    """Display one item of the list view: its name, and its tool tip alongside so both are visible at once."""

    def __init__(self, item: NamedItem) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.name = item.name
        self.tool_tip_text = item.tool_tip
        self.is_selected_model = Model.PropertyModel(False)
        self.ui_view = u.create_row(
            u.create_label(text="@binding(name)", width=80),
            u.create_label(text="@binding(tool_tip_text)", color="#888"),
            u.create_stretch(),
            spacing=8, margin=4)


class Handler(Declarative.Handler):
    """Show the tool tip of the item under the mouse, which each row of a list carries for itself.

    A widget tool tip belongs to the whole widget, so it says the same thing wherever the mouse rests on it. An item
    tool tip belongs to one row, so it changes as the mouse moves from row to row without leaving the list.
    """

    def __init__(self) -> None:
        super().__init__()
        items = [NamedItem("Alpha", "the first letter"),
                 NamedItem("Beta", "the second letter"),
                 NamedItem("Gamma", "the third letter"),
                 NamedItem("Delta", "the fourth letter")]
        # the list box takes its items as a sequence; the list view follows an observable list.
        self.list_box_items_model = Model.PropertyModel[typing.List[typing.Any]](list(items))
        self.list_view_items_model = ListModel.ListModel[NamedItem]("items", items=list(items))
        self.current_index_model = Model.PropertyModel(0)
        self.list_view_current_index_model = Model.PropertyModel(0)

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[ItemHandler]:
        return ItemHandler(item) if component_id == "item" else None


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # rest the mouse on a row of either list: the tool tip which appears is the one that row carries, and it changes
    # as the mouse moves to the next row.
    list_box = u.create_list_box(items_ref="@binding(list_box_items_model.value)",
                                 current_index="@binding(current_index_model.value)",
                                 width=200, height=120)

    list_view = u.create_list_view(items="list_view_items_model.items", item_component_id="item", item_height=24,
                                   current_index="@binding(list_view_current_index_model.value)",
                                   width=260, height=120)

    lists_row = u.create_row(u.create_column(u.create_label(text="List box"), list_box, spacing=4),
                             u.create_column(u.create_label(text="List view"), list_view, spacing=4),
                             u.create_stretch(), spacing=16)

    # a widget tool tip, for contrast: it belongs to the button rather than to anything within it, so it says the
    # same thing wherever the mouse rests on the button.
    widget_tool_tip_row = u.create_row(u.create_push_button(text="Widget tool tip", tool_tip="the whole button"),
                                       u.create_check_box(text="Also a widget tool tip", tool_tip="the whole check box"),
                                       u.create_stretch(), spacing=8)

    return u.create_column(lists_row, widget_tool_tip_row, spacing=12)
