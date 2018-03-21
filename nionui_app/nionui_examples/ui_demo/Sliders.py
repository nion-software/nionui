from nion.utils import Model


class Handler:

    def __init__(self):
        self.slider_value_model = Model.PropertyModel(50)
        self.vv = 25
        self.slider2 = None

    def reset(self, widget):
        self.slider_value_model.value = 50
        self.slider2.value = 50

    def value_changed(self, widget, value):
        print(f"V {value}")

    def slider_moved(self, widget, value):
        print(f"M {value}")


def construct_ui(ui):

    slider = ui.create_slider(value="@binding(slider_value_model.value)")

    slider2 = ui.create_slider(name="slider2", value="vv", on_value_changed="value_changed", on_slider_moved="slider_moved")

    label = ui.create_label(text="@binding(slider_value_model.value)")

    button = ui.create_push_button(text="Reset to 50", on_clicked="reset")

    return ui.create_column(slider, slider2, label, button, spacing=8)
