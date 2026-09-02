import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.utils import Model


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.items_model = Model.PropertyModel[typing.List[str]](["Alpha", "Beta", "Gamma", "Delta"])
        self.current_index_model = Model.PropertyModel(0)
        self.status_model = Model.PropertyModel("")
        self.__next_item_index = 5

    def item_selected(self, widget: Widgets.ListWidget, current_index: int) -> None:
        items = self.items_model.value or list()
        text = items[current_index] if 0 <= current_index < len(items) else None
        self.status_model.value = f"Selected: {text}"

    def add_item(self, widget: UserInterface.PushButtonWidget) -> None:
        items = list(self.items_model.value or list())
        items.append(f"Item {self.__next_item_index}")
        self.__next_item_index += 1
        self.items_model.value = items

    def remove_item(self, widget: UserInterface.PushButtonWidget) -> None:
        items = list(self.items_model.value or list())
        current_index = self.current_index_model.value or 0
        if 0 <= current_index < len(items):
            del items[current_index]
            self.items_model.value = items

    def item_context_menu(self, widget: Widgets.ListWidget, index: typing.Optional[int], x: int, y: int, gx: int, gy: int) -> bool:
        self.status_model.value = f"Context menu requested for item {index}"
        return True


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    list_box = u.create_list_box(items_ref="@binding(items_model.value)",
                                  current_index="@binding(current_index_model.value)",
                                  on_item_selected="item_selected",
                                  on_item_handle_context_menu="item_context_menu",
                                  height=120)

    add_button = u.create_push_button(text="Add Item", on_clicked="add_item")
    remove_button = u.create_push_button(text="Remove Selected", on_clicked="remove_item")
    button_row = u.create_row(add_button, remove_button, u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(list_box, button_row, status_label, spacing=8)
