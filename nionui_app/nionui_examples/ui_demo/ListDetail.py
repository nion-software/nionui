import typing

import numpy
import numpy.typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import ListModel
from nion.utils import Model
from nion.utils import Observable

IconType = numpy.typing.NDArray[typing.Any]

ColorType = typing.Tuple[int, int, int]

_colors: typing.Sequence[ColorType] = ((90, 160, 230), (230, 150, 90), (140, 200, 120), (200, 120, 200))


def make_icon(w: int, h: int, color: ColorType) -> IconType:
    bitmap: IconType = numpy.zeros((h, w, 4), numpy.uint8)
    bitmap[..., 0] = color[2]  # blue
    bitmap[..., 1] = color[1]  # green
    bitmap[..., 2] = color[0]  # red
    bitmap[..., 3] = 255
    return bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1])


class Item(Observable.Observable):
    """An item of the list. Observable so that editing it in the detail updates the row displaying it."""

    def __init__(self, title: str, notes: str, color: ColorType) -> None:
        super().__init__()
        self.__title = title
        self.__notes = notes
        self.icon = make_icon(12, 12, color)

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        self.__title = value
        self.notify_property_changed("title")

    @property
    def notes(self) -> str:
        return self.__notes

    @notes.setter
    def notes(self, value: str) -> None:
        self.__notes = value
        self.notify_property_changed("notes")


class RowHandler(Declarative.Handler):
    """Display one item in the master list: its icon and its title."""

    def __init__(self, item: Item) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.item = item
        self.ui_view = u.create_row(u.create_image(image="@binding(item.icon)", width=12, height=12),
                                    u.create_label(text="@binding(item.title)"),
                                    u.create_stretch(), spacing=8, margin=4)


class DetailHandler(Declarative.Handler):
    """Display one item in the detail pane. Constructed when the item is first displayed, not before."""

    build_count = 0

    def __init__(self, item: Item) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.item = item
        DetailHandler.build_count += 1
        # the detail panes are built as they are displayed, so this number shows the order in which that happened.
        self.build_label = f"detail #{DetailHandler.build_count}, built when first displayed"
        self.ui_view = u.create_column(
            u.create_row(u.create_label(text="Title:", width=60),
                         u.create_line_edit(text="@binding(item.title)"), spacing=8),
            u.create_row(u.create_label(text="Notes:", width=60),
                         u.create_line_edit(text="@binding(item.notes)"), spacing=8),
            u.create_row(u.create_label(text="@binding(build_label)"), u.create_stretch()),
            u.create_stretch(), spacing=8, margin=4)


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        titles = ("Alpha", "Beta", "Gamma", "Delta")
        items = [Item(title, f"notes for {title}", _colors[index % len(_colors)]) for index, title in enumerate(titles)]
        self.items_model = ListModel.ListModel[Item]("items", items=items)
        self.current_index_model = Model.PropertyModel(0)
        self.__next_item_index = len(titles) + 1

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:
        # the master and the detail are built from the same list of items, each with its own component.
        if component_id == "row":
            return RowHandler(item)
        if component_id == "detail":
            return DetailHandler(item)
        return None

    def add_item(self, widget: UserInterface.PushButtonWidget) -> None:
        index = self.__next_item_index
        self.__next_item_index += 1
        self.items_model.append_item(Item(f"Item {index}", str(), _colors[index % len(_colors)]))
        self.current_index_model.value = len(self.items_model.items) - 1

    def remove_item(self, widget: UserInterface.PushButtonWidget) -> None:
        current_index = self.current_index_model.value or 0
        if 0 <= current_index < len(self.items_model.items):
            self.items_model.remove_item(current_index)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # the master and the detail share one list of items and one current index: selecting a row displays its detail.
    master = u.create_list_view(items="items_model.items",
                                item_component_id="row",
                                item_height=24,
                                current_index="@binding(current_index_model.value)",
                                width=160, height=160)

    # the detail panes are constructed as they are first displayed, rather than all of them up front.
    detail = u.create_stack(items="items_model.items",
                            item_component_id="detail",
                            current_index="@binding(current_index_model.value)",
                            item_construction="deferred",
                            min_width=260, min_height=160)

    add_button = u.create_push_button(text="Add Item", on_clicked="add_item")
    remove_button = u.create_push_button(text="Remove Selected", on_clicked="remove_item")
    button_row = u.create_row(add_button, remove_button, u.create_stretch(), spacing=8)

    return u.create_column(u.create_row(master, detail, u.create_stretch(), spacing=8), button_row, spacing=8)
