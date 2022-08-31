from nion.ui import Declarative
from nion.utils import Model


class Handler(Declarative.Handler):
    tab_index_model = Model.PropertyModel(1)

    def switch3(self, widget: Declarative.UIWidget) -> None:
        print("CLICKED 3")
        self.tab_index_model.value = 2


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    def create_tab_content(tab_label: str, text: str, check_text: str, button_text: str) -> Declarative.UIDescription:
        label = u.create_label(text=text)
        check_box = u.create_check_box(text=check_text)
        button = u.create_push_button(text=button_text)
        return u.create_tab(tab_label, u.create_column(label, check_box, button, spacing=8, margin=4))

    tab0 = create_tab_content("First", "ONE", "Check 1", "Push ONE")
    tab1 = create_tab_content("Second", "TWO", "Check 2", "Push TWO")
    tab2 = create_tab_content("Third", "THREE", "Check 3", "Push THREE")
    tabs = u.create_tabs(tab0, tab1, tab2, current_index="@binding(tab_index_model.value)", style="minimal")
    button = u.create_push_button(text="3", on_clicked="switch3")
    label_row = u.create_row(u.create_label(text="Tab: "), u.create_label(text="@binding(tab_index_model.value)"), spacing=8)
    return u.create_column(tabs, label_row, button)
