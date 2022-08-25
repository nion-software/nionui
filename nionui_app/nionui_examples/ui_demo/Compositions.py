import typing

from nion.ui import Declarative
from nion.ui import UserInterface


class Handler(Declarative.Handler):

    width = "20"
    height = "30"

    width_field: typing.Optional[Declarative.ComponentWidget] = None
    height_field: typing.Optional[Declarative.ComponentWidget] = None

    def width_changed(self, widget: Declarative.UIWidget, value: str) -> None:
        self.width = value
        print(f"New width {self.width}")

    def height_changed(self, widget: Declarative.UIWidget, value: str) -> None:
        self.height = value
        print(f"New height {self.height}")

    def reset(self, widget: Declarative.UIWidget) -> None:
        getattr(self.width_field, "handler").value_widget.text = "20"
        getattr(self.height_field, "handler").value_widget.text = "30"

    def create_handler(self, component_id: str, container: typing.Any = None, item: typing.Any = None, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:

        class FieldHandler(Declarative.Handler):

            def __init__(self) -> None:
                super().__init__()
                self.label_widget: typing.Optional[UserInterface.LabelWidget] = None
                self.value_widget: typing.Optional[UserInterface.LabelWidget] = None
                self.on_value_changed: typing.Optional[typing.Callable[[str], None]] = None
                self.label: typing.Optional[str] = None
                self.value: typing.Optional[str] = None

            def init_handler(self) -> None:
                assert self.label_widget
                assert self.value_widget
                # when this is called, all fields will be populated
                self.label_widget.text = self.label
                self.value_widget.text = self.value

            def value_changed(self, widget: Declarative.UIWidget, text: str) -> None:
                self.value = text
                line_edit = typing.cast(UserInterface.LineEditWidget, widget)
                if line_edit.focused:
                    line_edit.select_all()
                if callable(self.on_value_changed):
                    self.on_value_changed(text)

        if component_id == "field":
            return FieldHandler()

        return None

    @property
    def resources(self) -> typing.Mapping[str, typing.Any]:
        ui = Declarative.DeclarativeUI()
        field_label = ui.create_label(name="label_widget")
        field_line_edit = ui.create_line_edit(name="value_widget", on_editing_finished="value_changed")
        field = ui.create_row(field_label, field_line_edit, ui.create_stretch(), spacing=8)
        field_events = [{"event": "on_value_changed", "parameters": ["value"]}]
        field_component = ui.define_component(content=field, events=field_events)
        return {"field": field_component}


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    field_width = u.create_component_instance("field", {"label": "Width", "value": "20"}, name="width_field", on_value_changed="width_changed")
    field_height = u.create_component_instance("field", {"label": "Height", "value": "30"}, name="height_field", on_value_changed="height_changed")
    reset_button = u.create_push_button(text="Reset", on_clicked="reset")
    return u.create_column(field_width, field_height, reset_button, spacing=8)
