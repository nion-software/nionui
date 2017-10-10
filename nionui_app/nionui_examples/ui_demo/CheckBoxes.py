class Handler:

    all_cb = None
    gain_cb = None
    dark_cb = None

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
    gain_cb = ui.create_check_box(text="Gain Normalize", name="gain_cb", checked=True, on_checked_changed="checked")
    dark_cb = ui.create_check_box(text="Dark Subtract", name="dark_cb", on_checked_changed="checked")
    cb_group = ui.create_column(gain_cb, dark_cb, spacing=8)
    cb_row = ui.create_row(ui.create_spacing(12), cb_group)
    all_group = ui.create_column(all_cb, cb_row, spacing=8)
    return all_group
