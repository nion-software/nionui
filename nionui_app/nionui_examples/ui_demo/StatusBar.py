from nion.ui import Declarative
from nion.utils import Model


class Handler(Declarative.Handler):
    slider_value_model = Model.PropertyModel(50)

    def reset(self, widget: Declarative.UIWidget) -> None:
        self.slider_value_model.value = 50


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    label = u.create_label(text="@binding(slider_value_model.value)")
    button = u.create_push_button(text="Reset to 50", on_clicked="reset")
    content = u.create_column(label, button, spacing=8)
    left = u.create_label(text="LEFT")
    right = u.create_label(text="RIGHT")
    group_row = u.create_row(left, u.create_stretch(), right, spacing=8)
    status_bar = u.create_group(group_row)
    return u.create_column(content, u.create_stretch(), status_bar, spacing=8)
