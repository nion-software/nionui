from nion.ui import Declarative
from nion.utils import Converter
from nion.utils import Model



class Handler(Declarative.Handler):
    hello3_converter = Converter.FloatToStringConverter(format="{0:#.4g}")
    hello3_model = Model.PropertyModel(5.6)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    hello3_line_edit = u.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value, converter=hello3_converter)")
    hello3_label = u.create_label(text="@binding(hello3_model.value, converter=hello3_converter)")
    hello3 = u.create_column(hello3_label, hello3_line_edit, spacing=8)
    return hello3
