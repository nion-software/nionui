import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Model


class Item:
    """An item of the list, with a title and a tool tip describing it."""

    def __init__(self, title: str, tool_tip: str) -> None:
        self.title = title
        self.tool_tip = tool_tip

    def __str__(self) -> str:
        return self.title


class RowHandler(Declarative.Handler):
    """Display one item of the list. Hovering a row shows the tool tip of its item."""

    def __init__(self, item: Item) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.title = item.title
        self.ui_view = u.create_row(u.create_label(text="@binding(title)"), u.create_stretch(), margin=4)


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it when a menu needs to be popped up.
        self.container_handler: typing.Any = None
        self.status_model = Model.PropertyModel("")
        self.items_model = ListModel.ListModel[Item]("items", items=[
            Item("Alpha", "the first item"),
            Item("Beta", "the second item"),
            Item("Gamma", "the third item"),
        ])
        self.current_index_model = Model.PropertyModel(0)
        self.menu_button: typing.Optional[UserInterface.PushButtonWidget] = None
        self.__next_item_index = 4

    @property
    def __window(self) -> Window.Window:
        return typing.cast(Window.Window, getattr(self.container_handler, "window"))

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[RowHandler]:
        return RowHandler(item) if component_id == "row" else None

    def show_menu(self, widget: UserInterface.PushButtonWidget) -> None:
        # a menu popped up from a button appears below it; the button reports where it is on the screen.
        menu = self.__window.create_context_menu()
        for count in (1, 2, 3):
            menu.add_menu_item(f"Choose {count}", lambda count=count: self.__chose(f"menu item {count}"))  # type: ignore
        menu.add_separator()
        menu.add_menu_item("Choose Nothing", lambda: self.__chose("nothing"))
        position = widget.map_to_global(Geometry.IntPoint(y=widget.size.height, x=0))
        menu.popup(position.x, position.y)

    def item_context_menu(self, widget: UserInterface.Widget, index: typing.Optional[int], x: int, y: int,
                          gx: int, gy: int) -> bool:
        # a menu popped up for an item appears where the pointer is, and acts on that item.
        items = self.items_model.items
        if index is None or not (0 <= index < len(items)):
            return False
        item = items[index]
        menu = self.__window.create_context_menu()
        menu.add_menu_item(f"Duplicate \"{item.title}\"", lambda: self.__duplicate(item))
        menu.add_menu_item(f"Remove \"{item.title}\"", lambda: self.__remove(item))
        menu.add_separator()
        menu.add_menu_item("Add an Item", self.__add)
        menu.popup(gx, gy)
        return True

    def __chose(self, what: str) -> None:
        self.status_model.value = f"Chose {what}"

    def __duplicate(self, item: Item) -> None:
        index = list(self.items_model.items).index(item)
        self.items_model.insert_item(index + 1, Item(f"{item.title} copy", f"a copy of {item.title.lower()}"))
        self.status_model.value = f"Duplicated {item.title}"

    def __remove(self, item: Item) -> None:
        self.items_model.remove_item(list(self.items_model.items).index(item))
        self.status_model.value = f"Removed {item.title}"

    def __add(self) -> None:
        index = self.__next_item_index
        self.__next_item_index += 1
        self.items_model.append_item(Item(f"Item {index}", f"item number {index}"))
        self.status_model.value = f"Added Item {index}"


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # a menu popped up from a button, which is how a control offers a list of choices.
    menu_row = u.create_row(u.create_push_button(text="Show Menu...", on_clicked="show_menu", name="menu_button",
                                                 tool_tip="Pops up a menu below this button."),
                            u.create_stretch(), spacing=8)

    # a menu popped up for an item of a list, which acts on the item it was popped up for. hovering a row shows the
    # tool tip of its item.
    item_list = u.create_list_view(items="items_model.items", item_component_id="row", item_height=24,
                                   current_index="@binding(current_index_model.value)",
                                   on_item_handle_context_menu="item_context_menu",
                                   width=200, height=140)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(u.create_label(text="Right click an item for a menu; hover one for its tool tip."),
                           menu_row, item_list, status_label, spacing=8)
