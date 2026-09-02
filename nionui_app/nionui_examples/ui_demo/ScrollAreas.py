import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import Geometry
from nion.utils import Model


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.scroll_area: typing.Optional[UserInterface.ScrollAreaWidget] = None
        self.viewport_model = Model.PropertyModel("")

    def viewport_changed(self, widget: UserInterface.ScrollAreaWidget, viewport: Geometry.IntRect) -> None:
        self.viewport_model.value = f"Viewport: top={viewport.top}, left={viewport.left}, height={viewport.height}, width={viewport.width}"

    def scroll_to_top(self, widget: UserInterface.PushButtonWidget) -> None:
        assert self.scroll_area
        self.scroll_area.scroll_to(0, 0)

    def scroll_to_bottom(self, widget: UserInterface.PushButtonWidget) -> None:
        assert self.scroll_area
        content = self.scroll_area.content
        content_height = content.size.height if content and content.size else 0
        self.scroll_area.scroll_to(0, content_height)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    rows = [u.create_row(u.create_label(text=f"Item {index}"), u.create_stretch(), spacing=8)
            for index in range(30)]
    content_column = u.create_column(*rows, spacing=4, margin=4)

    scroll_area = u.create_scroll_area(content_column, name="scroll_area", on_viewport_changed="viewport_changed", height=160)

    top_button = u.create_push_button(text="Scroll to Top", on_clicked="scroll_to_top")
    bottom_button = u.create_push_button(text="Scroll to Bottom", on_clicked="scroll_to_bottom")
    button_row = u.create_row(top_button, bottom_button, u.create_stretch(), spacing=8)

    viewport_label = u.create_label(text="@binding(viewport_model.value)")

    return u.create_column(scroll_area, button_row, viewport_label, spacing=8)
