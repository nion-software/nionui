from nion.utils import Model
from nion.utils import Converter

class Handler:
    radio_button_value = Model.PropertyModel(2)
    label_widget = None

    def reset_clicked(self, widget):
        self.radio_button_value.value = 2

    radio_converter = Converter.IntegerToStringConverter('{0}')


def construct_ui(ui):
    radio0 = ui.create_radio_button(
        text="One", value=1, group_value="@binding(radio_button_value.value)")
    radio1 = ui.create_radio_button(
        text="Two", value=2, group_value="@binding(radio_button_value.value)")
    radio2 = ui.create_radio_button(
        text="Three", value=3, group_value="@binding(radio_button_value.value)")
    label = ui.create_label(
        text="@binding(radio_button_value.value, converter=radio_converter)")
    button = ui.create_push_button(text="Reset", on_clicked="reset_clicked")
    return ui.create_column(radio0, radio1, radio2, label, button, spacing=8)
