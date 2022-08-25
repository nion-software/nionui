from __future__ import annotations

import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import Model


class Handler(Declarative.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.color_line_edit: typing.Optional[UserInterface.LineEditWidget] = None
        self.model = Model.PropertyModel("red")

    def color_updated(self, widget: Declarative.UIWidget, text: str) -> None:
        print(f"Color changed: {widget} {text}")

    def return_pressed(self, widget: Declarative.UIWidget) -> bool:
        assert self.color_line_edit
        self.color_line_edit.select_all()
        return False  # required so that editing_finished event is triggered

    def key_pressed(self, widget: Declarative.UIWidget, key: UserInterface.Key) -> bool:
        if key.text == "*":
            return True
        return False


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    field_label = u.create_label(text="Favorite Color?")
    field_line_edit = u.create_line_edit(placeholder_text="Color", name="color_line_edit", on_editing_finished="color_updated", on_return_pressed="return_pressed", on_key_pressed="key_pressed")
    field_line_edit2 = u.create_line_edit(text="@binding(model.value)")
    return u.create_column(
        u.create_row(field_label, field_line_edit, spacing=8),
        u.create_row(u.create_label(text="Another Color?"), field_line_edit2, u.create_stretch(), spacing=8),
        u.create_stretch(),
        spacing=8,
    )
