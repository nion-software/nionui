from nion.utils import Model

class Handler:

    all_cb = None
    gain_cb = None
    dark_cb = None

    gain_enabled = True

    extra_model = Model.PropertyModel(True)

    def __init__(self):
        def extra_changed(value):
            print(f"Extra {value}")

        self.extra_model.on_value_changed = extra_changed

    def checked(self, widget, checked):
        print(f"Checked: {checked}")
        self.__update_check_state()

    def check_state_changed(self, widget, check_state):
        print(f"Check state: {check_state}")
        if check_state == "partial":
            check_state = "checked"
        if check_state != "partial":
            c = check_state == "checked"
            self.gain_cb.checked = c
            self.dark_cb.checked = c
            self.all_cb.checked = c
        self.extra_model.value = check_state == "checked"

    def __update_check_state(self):
        print(f"Compare {self.gain_cb.checked} to {self.dark_cb.checked}")
        if self.gain_cb.checked == self.dark_cb.checked:
            print(f"Setting {self.gain_cb.check_state}")
            self.all_cb.check_state = self.gain_cb.check_state
        else:
            print(f"Setting PARTIAL")
            self.all_cb.check_state = "partial"


def construct_ui(ui):
    all_cb = ui.create_check_box(text="Enable All", name="all_cb", tristate=True, check_state="partial", on_check_state_changed="check_state_changed")
    gain_cb = ui.create_check_box(text="Gain Normalize", name="gain_cb", checked="gain_enabled", on_checked_changed="checked")
    dark_cb = ui.create_check_box(text="Dark Subtract", name="dark_cb", on_checked_changed="checked")
    extra_cb = ui.create_check_box(text="Extra", checked="@binding(extra_model.value)")
    extra_extra_cb = ui.create_check_box(text="Extra2", enabled=False)
    label = ui.create_label(text="Label", visible="@binding(extra_model.value)", tool_tip="A tool tip.")
    cb_group = ui.create_column(gain_cb, dark_cb, spacing=8, enabled="@binding(extra_model.value)")
    cb_row = ui.create_row(ui.create_spacing(12), cb_group)
    all_group = ui.create_column(all_cb, cb_row, extra_cb, extra_extra_cb, label, spacing=8)
    return all_group
