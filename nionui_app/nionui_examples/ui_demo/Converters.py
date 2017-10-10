from nion.utils import Converter
from nion.utils import Model


class Handler:
    hello3_converter = Converter.FloatToStringConverter(format="{0:#.4g}")
    hello3_model = Model.PropertyModel(5.6)


def construct_ui(ui):
    hello3_line_edit = ui.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value, converter=hello3_converter)")
    hello3_label = ui.create_label(text="@binding(hello3_model.value, converter=hello3_converter)")
    hello3 = ui.create_column(hello3_label, hello3_line_edit, spacing=8)
    return hello3
