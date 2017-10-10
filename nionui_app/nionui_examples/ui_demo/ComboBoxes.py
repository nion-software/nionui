from nion.utils import Model

class Handler:

    cb1 = None
    cb2_current_index_model = Model.PropertyModel(1)

    numbers = ["One", "Two", "Three"]

    numeros = Model.PropertyModel(["Uno", "Dos", "Tres"])

    def init_handler(self):
        # this method is called after all fields are populated
        self.cb1.current_index = 2
        self.cb2_current_index_model.on_value_changed = self.cb2_current_index_changed

    def cb1_current_index_changed(self, widget, current_index):
        print(f"CB1 {current_index}")

    def cb2_current_index_changed(self, current_index):
        print(f"CB2 {current_index}")


def construct_ui(ui):
    cb1 = ui.create_combo_box(name="cb1", items=["Red", "Green", "Blue"], on_current_index_changed="cb1_current_index_changed")
    cb2 = ui.create_combo_box(items=["Sheriff", "Astronaut", "Scientist"], current_index="@binding(cb2_current_index_model.value)")
    cb3 = ui.create_combo_box(items_ref="numbers", current_index="@binding(cb2_current_index_model.value)")
    cb4 = ui.create_combo_box(items_ref="@binding(numeros.value)", current_index="@binding(cb2_current_index_model.value)")

    cb_group = ui.create_column(cb1, cb2, cb3, cb4, spacing=12)

    return cb_group
