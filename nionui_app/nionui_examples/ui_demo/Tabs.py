from nion.utils import Model


class Handler:

    tab_index_model = Model.PropertyModel(1)

    def switch3(self, widget):
        print("CLICKED 3")
        self.tab_index_model.value = 2


def construct_ui(ui):

    tab0 = ui.create_tab("First", ui.create_label(text="ONE"))
    tab1 = ui.create_tab("Second", ui.create_label(text="TWO"))
    tab2 = ui.create_tab("Third", ui.create_label(text="THREE"))

    tabs = ui.create_tabs(tab0, tab1, tab2, current_index="@binding(tab_index_model.value)")

    button = ui.create_push_button(text="3", on_clicked="switch3")

    return ui.create_column(tabs, button)
