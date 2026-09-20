import typing

import numpy
import numpy.typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import ListModel
from nion.utils import Model

IconType = numpy.typing.NDArray[typing.Any]

ColorType = typing.Tuple[int, int, int]

# the mime type the demo describes its own items with. a drag carrying it comes from one of the lists here; one
# without it comes from somewhere else, and is taken as text.
ITEM_MIME_TYPE = "text/vnd.nion.ui-demo-item"

TEXT_MIME_TYPE = "text/plain"

_colors: typing.Sequence[ColorType] = ((90, 160, 230), (230, 150, 90), (140, 200, 120), (200, 120, 200))


def make_icon(w: int, h: int, color: ColorType) -> IconType:
    # make bitmap data for the item icon, a solid block of the given color
    bitmap: IconType = numpy.zeros((h, w, 4), numpy.uint8)
    bitmap[..., 0] = color[2]  # blue
    bitmap[..., 1] = color[1]  # green
    bitmap[..., 2] = color[0]  # red
    bitmap[..., 3] = 255
    return bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1])


class ListItem:
    """An item of one of the lists, with a title and the color of its icon."""

    def __init__(self, title: str, color: ColorType) -> None:
        self.title = title
        self.color = color
        self.icon = make_icon(16, 16, color)


class ItemHandler(Declarative.Handler):
    """Display one item of a list: its icon and its title."""

    def __init__(self, item: ListItem) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.title = item.title
        self.icon = item.icon
        self.is_selected_model = Model.PropertyModel(False)
        self.ui_view = u.create_row(
            u.create_image(image="@binding(icon)", width=16, height=16),
            u.create_label(text="@binding(title)"),
            u.create_stretch(),
            spacing=8, margin=4)


class Handler(Declarative.Handler):
    """Move items between two lists by dragging them.

    Dragging an item describes it as mime data and starts a drag; dropping puts it into the gap the drag was over,
    in whichever list took the drop, so an item can be dropped before the first item, after the last one, or into a
    list which has been emptied. The same drag also carries the item title as plain text, so an item can be dropped
    on something outside the demo, and text dragged in from outside becomes a new item.
    """

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it for reaching the user interface.
        self.container_handler: typing.Any = None
        # the left list holds more items than it has room for, so that it scrolls: a drop on a scrolled list lands at
        # the gap under the mouse rather than at the gap the same distance down the room the list is shown in.
        left_titles = ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta")
        right_titles = ("Iota", "Kappa")
        self.left_model = ListModel.ListModel[ListItem]("items", items=[ListItem(title, _colors[index % len(_colors)])
                                                                        for index, title in enumerate(left_titles)])
        self.right_model = ListModel.ListModel[ListItem]("items", items=[ListItem(title, _colors[index % len(_colors)])
                                                                         for index, title in enumerate(right_titles)])
        self.left_list_view: typing.Optional[UserInterface.Widget] = None
        self.right_list_view: typing.Optional[UserInterface.Widget] = None
        self.status_model = Model.PropertyModel("Drag an item from one list to the other.")

    @property
    def __ui(self) -> UserInterface.UserInterface:
        return typing.cast(Window.Window, getattr(self.container_handler, "window")).ui

    def create_handler(self, component_id: str, item: typing.Any = None, container: typing.Any = None,
                       **kwargs: typing.Any) -> typing.Optional[ItemHandler]:
        return ItemHandler(item) if component_id == "item" else None

    def __model_for_widget(self, widget: Declarative.UIWidget) -> ListModel.ListModel[ListItem]:
        return self.left_model if widget == self.left_list_view else self.right_model

    def __find_item(self, title: str) -> typing.Optional[typing.Tuple[ListModel.ListModel[ListItem], int]]:
        for model in (self.left_model, self.right_model):
            for index, item in enumerate(model.items):
                if item.title == title:
                    return model, index
        return None

    def item_drag_started(self, widget: Declarative.UIWidget, index: int, x: int, y: int,
                          modifiers: UserInterface.KeyboardModifiers) -> bool:
        item = self.__model_for_widget(widget).items[index]
        mime_data = self.__ui.create_mime_data()
        mime_data.set_data_as_string(ITEM_MIME_TYPE, item.title)
        mime_data.set_data_as_string(TEXT_MIME_TYPE, item.title)

        def drag_finished(action: str) -> None:
            self.status_model.value = f"Dragged {item.title}: {action}"

        # the whole row goes along as the thumbnail, icon and title together, so what follows the cursor looks like
        # the item being dragged. the row is grabbed where it was clicked, so the point is taken relative to the row
        # rather than to the list.
        list_view = typing.cast(Widgets.ListViewWidget, widget)
        item_rect = list_view.item_rect(index)
        list_view.drag(mime_data, list_view.render_item(index), hot_spot_x=x - item_rect.left,
                       hot_spot_y=y - item_rect.top, drag_finished_fn=drag_finished)
        self.status_model.value = f"Dragging {item.title}"
        return True

    def can_drop_mime_data(self, widget: Declarative.UIWidget, mime_data: UserInterface.MimeData, action: str,
                           drop_index: typing.Optional[int]) -> bool:
        # asked as the drag moves over the list, which is how the list knows to show the gap the drop would go into.
        return mime_data.has_format(ITEM_MIME_TYPE) or mime_data.has_format(TEXT_MIME_TYPE)

    def drop_mime_data(self, widget: Declarative.UIWidget, mime_data: UserInterface.MimeData, action: str,
                       drop_index: typing.Optional[int]) -> str:
        model = self.__model_for_widget(widget)
        # the drop index is the gap the item goes into: zero before the first item, the number of items after the
        # last one, and zero for a list with no items left in it at all.
        index = drop_index if drop_index is not None else len(model.items)
        title = mime_data.data_as_string(ITEM_MIME_TYPE if mime_data.has_format(ITEM_MIME_TYPE) else TEXT_MIME_TYPE)
        if not title:
            return "ignore"
        source = self.__find_item(title)
        if source is None:
            # nothing here is named that, so the drag came from outside; make an item of the text it carried.
            model.insert_item(index, ListItem(title, _colors[len(model.items) % len(_colors)]))
            self.status_model.value = f"Added {title} at position {index + 1}"
            return "copy"
        source_model, source_index = source
        item = source_model.items[source_index]
        # taking the item out of the list it came from shifts the gaps after it up by one.
        if source_model == model and source_index < index:
            index -= 1
        source_model.remove_item(source_index)
        model.insert_item(index, item)
        self.status_model.value = f"Moved {title} to position {index + 1}"
        return "move"


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # both lists drag their items out and take a drop, so an item can be moved either way between them, and moved
    # within a list to reorder it.
    left_list_view = u.create_list_view(items="left_model.items", item_component_id="item", item_height=24,
                                        name="left_list_view", width=160, height=160,
                                        on_item_drag_started="item_drag_started",
                                        on_can_drop_mime_data="can_drop_mime_data",
                                        on_drop_mime_data="drop_mime_data")

    right_list_view = u.create_list_view(items="right_model.items", item_component_id="item", item_height=24,
                                         name="right_list_view", width=160, height=160,
                                         on_item_drag_started="item_drag_started",
                                         on_can_drop_mime_data="can_drop_mime_data",
                                         on_drop_mime_data="drop_mime_data")

    list_row = u.create_row(left_list_view, right_list_view, u.create_stretch(), spacing=12)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(list_row, status_label, spacing=8)
