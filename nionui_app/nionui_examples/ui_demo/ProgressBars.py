from nion.utils import Model
from nion.utils import Converter

class Handler:

    slider_value_model = Model.PropertyModel(50)

    def reset(self, widget):
        self.slider_value_model.value = 50

    slider_converter = Converter.IntegerToStringConverter('{0}')


def construct_ui(ui):

    slider = ui.create_slider(value="@binding(slider_value_model.value)")
    progress_bar = ui.create_progress_bar(
        value="@binding(slider_value_model.value)")
    label = ui.create_label(
        text="@binding(slider_value_model.value, converter=slider_converter)")
    button = ui.create_push_button(text="Reset to 50", on_clicked="reset")
    
    return ui.create_column(progress_bar, slider, label, button, spacing=8)
