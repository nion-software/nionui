import typing

import numpy
import numpy.typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import Converter
from nion.utils import ListModel
from nion.utils import Model

IconType = numpy.typing.NDArray[typing.Any]

ColorType = typing.Tuple[int, int, int]

_colors: typing.Sequence[ColorType] = ((90, 160, 230), (230, 150, 90), (140, 200, 120), (200, 120, 200))


def make_icon(w: int, h: int, color: ColorType) -> IconType:
    # make bitmap data for the item icon, a solid block of the given color
    bitmap: IconType = numpy.zeros((h, w, 4), numpy.uint8)
    bitmap[..., 0] = color[2]  # blue
    bitmap[..., 1] = color[1]  # green
    bitmap[..., 2] = color[0]  # red
    bitmap[..., 3] = 255
    return bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1])


class SelectedMarkConverter(Converter.ConverterLike[bool, str]):
    """Convert the selected state of an item to the mark displayed at the end of its row."""

    def convert(self, value: typing.Optional[bool]) -> typing.Optional[str]:
        return "●" if value else "○"

    def convert_back(self, formatted_value: typing.Optional[str]) -> typing.Optional[bool]:
        raise NotImplementedError()


class ListItem:
    """An item of the list, with a title and the color of its icon."""

    def __init__(self, title: str, color: ColorType) -> None:
        self.title = title
        self.icon = make_icon(12, 12, color)


class ItemHandler(Declarative.Handler):
    """Display one item of the list: its icon, its title, and a mark when it is selected.

    Unlike a list box, whose items are strings drawn by the list box, an item of a list view is described by its own
    ui view and displayed by its own handler, so it can be any arrangement of widgets.
    """

    def __init__(self, item: ListItem) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.title = item.title
        self.icon = item.icon
        # the list view replaces this with a model tracking whether this item is selected.
        self.is_selected_model = Model.PropertyModel(False)
        self.selected_converter = SelectedMarkConverter()
        self.ui_view = u.create_row(
            u.create_image(image="@binding(icon)", width=12, height=12),
            u.create_label(text="@binding(title)"),
            u.create_stretch(),
            u.create_label(text="@binding(is_selected_model.value, converter=selected_converter)"),
            spacing=8, margin=4)


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        titles = ("Alpha", "Beta", "Gamma", "Delta")
        items = [ListItem(title, _colors[index % len(_colors)]) for index, title in enumerate(titles)]
        self.items_model = ListModel.ListModel[ListItem]("items", items=items)
        self.current_index_model = Model.PropertyModel(0)
        self.status_model = Model.PropertyModel("")
        self.__next_item_index = len(titles) + 1

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[ItemHandler]:
        # called for each item of the list; the returned handler describes and displays that item.
        return ItemHandler(item) if component_id == "item" else None

    def item_changed(self, widget: UserInterface.Widget, current_index: int) -> None:
        items = self.items_model.items
        title = items[current_index].title if 0 <= current_index < len(items) else None
        self.status_model.value = f"Selected: {title}"

    def item_selected(self, widget: UserInterface.Widget, current_index: int) -> bool:
        items = self.items_model.items
        title = items[current_index].title if 0 <= current_index < len(items) else None
        self.status_model.value = f"Chose: {title}"
        return True

    def add_item(self, widget: UserInterface.PushButtonWidget) -> None:
        # the list view follows the insert, adding a component for the new item and leaving the others alone.
        index = self.__next_item_index
        self.__next_item_index += 1
        self.items_model.append_item(ListItem(f"Item {index}", _colors[index % len(_colors)]))

    def remove_item(self, widget: UserInterface.PushButtonWidget) -> None:
        current_index = self.current_index_model.value or 0
        if 0 <= current_index < len(self.items_model.items):
            self.items_model.remove_item(current_index)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    list_view = u.create_list_view(items="items_model.items",
                                   item_component_id="item",
                                   item_height=24,
                                   current_index="@binding(current_index_model.value)",
                                   on_item_changed="item_changed",
                                   on_item_selected="item_selected",
                                   height=140)

    add_button = u.create_push_button(text="Add Item", on_clicked="add_item")
    remove_button = u.create_push_button(text="Remove Selected", on_clicked="remove_item")
    button_row = u.create_row(add_button, remove_button, u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(list_view, button_row, status_label, spacing=8)
