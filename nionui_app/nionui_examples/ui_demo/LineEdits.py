from nion.utils import Model

class Handler:

    def __init__(self):
        self.color_line_edit = None
        self.model = Model.PropertyModel("red")

    def color_updated(self, widget, text):
        print(f"Color changed: {widget} {text}")

    def return_pressed(self, widget):
        self.color_line_edit.select_all()
        return False  # required so that editing_finished event is triggered

    def key_pressed(self, widget, key):
        if key.text == "*":
            return True
        return False


def construct_ui(ui):
    field_label = ui.create_label(text="Favorite Color?")
    field_line_edit = ui.create_line_edit(placeholder_text="Color", name="color_line_edit", on_editing_finished="color_updated", on_return_pressed="return_pressed", on_key_pressed="key_pressed")
    field_line_edit2 = ui.create_line_edit(text="@binding(model.value)")
    return ui.create_column(
        ui.create_row(field_label, field_line_edit, spacing=8),
        ui.create_row(ui.create_label(text="Another Color?"), field_line_edit2, ui.create_stretch(), spacing=8),
        ui.create_stretch(),
        spacing=8,
    )
