from nion.utils import Model


class Handler:

    slider_value_model = Model.PropertyModel(50)

    def reset(self, widget):
        self.slider_value_model.value = 50


def construct_ui(ui):

    label = ui.create_label(text="@binding(slider_value_model.value)")

    button = ui.create_push_button(text="Reset to 50", on_clicked="reset")

    content = ui.create_column(label, button, spacing=8)

    left = ui.create_label(text="LEFT")

    right = ui.create_label(text="RIGHT")

    group_row = ui.create_row(left, ui.create_stretch(), right, spacing=8)

    status_bar = ui.create_group(group_row)

    return ui.create_column(content, ui.create_stretch(), status_bar, spacing=8)
