from __future__ import annotations

import typing

from nion.ui import Declarative
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


class Handler(Declarative.Handler):

    radio_button_value = Model.PropertyModel(2)
    label_widget: typing.Optional[UserInterface.LabelWidget] = None

    def reset_clicked(self, widget: Declarative.UIWidget) -> None:
        self.radio_button_value.value = 2


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    radio0 = u.create_radio_button(text="One", value=1, group_value="@binding(radio_button_value.value)")
    radio1 = u.create_radio_button(text="Two", value=2, group_value="@binding(radio_button_value.value)")
    radio2 = u.create_radio_button(text="Three", value=3, group_value="@binding(radio_button_value.value)")
    label = u.create_label(text="@binding(radio_button_value.value)")
    button = u.create_push_button(text="Reset", on_clicked="reset_clicked")
    return u.create_column(radio0, radio1, radio2, label, button, spacing=8)
