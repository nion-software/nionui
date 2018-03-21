from nion.ui import Declarative

class Handler:

    width = "20"
    height = "30"

    width_field = None
    height_field = None

    def width_changed(self, widget, value):
        self.width = value
        print(f"New width {self.width}")

    def height_changed(self, widget, value):
        self.height = value
        print(f"New height {self.height}")

    def reset(self, widget):
        self.width_field.handler.value_widget.text = "20"
        self.height_field.handler.value_widget.text = "30"

    def create_handler(self, component_id: str, **kwargs):

        class FieldHandler:

            def __init__(self):
                self.label_widget = None
                self.value_widget = None
                self.on_value_changed = None
                self.label = None
                self.value = None

            def init_handler(self):
                # when this is called, all fields will be populated
                self.label_widget.text = self.label
                self.value_widget.text = self.value

            def value_changed(self, widget, text):
                self.value = text
                if widget.focused:
                    widget.select_all()
                if callable(self.on_value_changed):
                    self.on_value_changed(value=text)

        if component_id == "field":
            return FieldHandler()

    @property
    def resources(self):
        ui = Declarative.DeclarativeUI()
        field_label = ui.create_label(name="label_widget")
        field_line_edit = ui.create_line_edit(name="value_widget", on_editing_finished="value_changed")
        field = ui.create_row(field_label, field_line_edit, ui.create_stretch(), spacing=8)
        field_events = [{"event": "on_value_changed", "parameters": ["value"]}]
        field_component = ui.define_component(content=field, component_id="field", events=field_events)
        return {"field": field_component}


def construct_ui(ui):
    field_width = ui.create_component_instance("field", {"label": "Width", "value": "20"}, name="width_field", on_value_changed="width_changed")
    field_height = ui.create_component_instance("field", {"label": "Height", "value": "30"}, name="height_field", on_value_changed="height_changed")
    reset_button = ui.create_push_button(text="Reset", on_clicked="reset")
    return ui.create_column(field_width, field_height, reset_button, spacing=8)
