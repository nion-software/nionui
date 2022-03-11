from nion.ui import Declarative
from nion.utils import Model


class Handler(Declarative.Handler):

    slider_value_model = Model.PropertyModel(50)

    def reset(self, widget: Declarative.UIWidget) -> None:
        self.slider_value_model.value = 50


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:

    slider = u.create_slider(value="@binding(slider_value_model.value)")

    progress_bar = u.create_progress_bar(value="@binding(slider_value_model.value)")

    label = u.create_label(text="@binding(slider_value_model.value)")

    button = u.create_push_button(text="Reset to 50", on_clicked="reset")

    group_column = u.create_column(slider, label, spacing=8)

    group = u.create_group(group_column, title="Group", margin=4)

    return u.create_column(progress_bar, group, button, spacing=8)
