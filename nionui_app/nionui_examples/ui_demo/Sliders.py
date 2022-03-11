import typing

from nion.ui import Declarative
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.slider_value_model = Model.PropertyModel(50)
        self.vv = 25
        self.slider2: typing.Optional[UserInterface.SliderWidget] = None

    def reset(self, widget: Declarative.UIWidget) -> None:
        assert self.slider2
        self.slider_value_model.value = 50
        self.slider2.value = 50

    def value_changed(self, widget: Declarative.UIWidget, value: str) -> None:
        print(f"V {value}")

    def slider_moved(self, widget: Declarative.UIWidget, value: str) -> None:
        print(f"M {value}")


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    slider = u.create_slider(value="@binding(slider_value_model.value)")
    slider2 = u.create_slider(name="slider2", value="vv", on_value_changed="value_changed", on_slider_moved="slider_moved")
    label = u.create_label(text="@binding(slider_value_model.value)")
    button = u.create_push_button(text="Reset to 50", on_clicked="reset")
    return u.create_column(slider, slider2, label, button, spacing=8)
