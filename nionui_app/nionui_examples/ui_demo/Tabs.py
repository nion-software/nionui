from nion.utils import Model


class Handler:

    tab_index_model = Model.PropertyModel(1)

    def switch3(self, widget):
        print("CLICKED 3")
        self.tab_index_model.value = 2


def construct_ui(ui):

    def create_tab_content(tab_label, text, check_text, button_text):
        label = ui.create_label(text=text)
        check_box = ui.create_check_box(text=check_text)
        button = ui.create_push_button(text=button_text)
        return ui.create_tab(tab_label, ui.create_column(label, check_box, button, spacing=8, margin=4))

    tab0 = create_tab_content("First", "ONE", "Check 1", "Push ONE")
    tab1 = create_tab_content("Second", "TWO", "Check 2", "Push TWO")
    tab2 = create_tab_content("Third", "THREE", "Check 3", "Push THREE")

    tabs = ui.create_tabs(tab0, tab1, tab2, current_index="@binding(tab_index_model.value)")

    button = ui.create_push_button(text="3", on_clicked="switch3")

    return ui.create_column(tabs, button)
