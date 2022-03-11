import numpy
import numpy.typing
import typing

from nion.ui import Declarative
from nion.utils import Event
from nion.utils import Model

IconType = numpy.typing.NDArray[typing.Any]


def make_icon(w: int, h: int) -> IconType:
    # make bitmap_data (random static) for icon push button
    bitmap: IconType = numpy.zeros((h, w, 4), numpy.uint8)
    bitmap[..., 0] = (numpy.random.randn(h, w) * 255).astype(numpy.uint8)  # type: ignore  # blue
    bitmap[..., 1] = (numpy.random.randn(h, w) * 255).astype(numpy.uint8)  # type: ignore  # green
    bitmap[..., 2] = (numpy.random.randn(h, w) * 255).astype(numpy.uint8)  # type: ignore  # red
    bitmap[..., 3] = 255
    return bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1])


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.icon1 =  make_icon(12, 12)
        self.icon2 =  make_icon(48, 36)
        self.image_model = Model.PropertyModel(make_icon(16, 16), typing.cast(typing.Callable[[typing.Optional[IconType], typing.Optional[IconType]], bool], numpy.array_equal))
        self.property_changed_event = Event.Event()

    def click(self, widget: Declarative.UIWidget) -> None:
        self.icon1 =  make_icon(12, 12)
        self.property_changed_event.fire("icon1")

    def image_click(self, widget: Declarative.UIWidget) -> None:
        self.image_model.value = make_icon(16, 16)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    text_only_button = u.create_push_button(text="Change Button Icon", on_clicked="click")
    icon_only_button = u.create_push_button(icon="@binding(icon2)")
    text_and_icon_button = u.create_push_button(text="Text", icon="@binding(icon1)")
    image_button = u.create_image(image="@binding(image_model.value)", height=16, width=16, on_clicked="image_click")

    hellos = u.create_column(
        u.create_row(text_only_button, u.create_stretch()),
        u.create_row(icon_only_button, u.create_stretch()),
        u.create_row(text_and_icon_button, u.create_stretch()),
        u.create_row(u.create_label(text="Image (click me):"), image_button, u.create_stretch(), spacing=8),
        u.create_stretch(),
        spacing=12)

    return hellos
