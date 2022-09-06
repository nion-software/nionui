import typing

from nion.ui import Declarative
from nion.ui import Widgets
from nion.utils import Model


class Handler(Declarative.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.expanded_model0 = Model.PropertyModel(False)
        self.expanded_model1 = Model.PropertyModel(True)
        self.expanded_model2 = Model.PropertyModel(False)
        self.section: typing.Optional[Widgets.SectionWidget] = None

    def switch3(self, widget: Declarative.UIWidget) -> None:
        self.expanded_model0.value = False
        self.expanded_model1.value = False
        self.expanded_model2.value = True
        if self.section:
            self.section.title = "Tres"


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:

    def create_section(tab_label: str, text: str, check_text: str, button_text: str, index: int) -> Declarative.UIDescription:
        label = u.create_label(text=text)
        check_box = u.create_check_box(text=check_text)
        button = u.create_push_button(text=button_text)
        return u.create_section(u.create_column(label, check_box, button, spacing=8, margin=4), title=tab_label, expanded=f"@binding(expanded_model{index}.value)", name="section")

    section0 = create_section("First", "ONE", "Check 1", "Push ONE", 0)
    section1 = create_section("Second", "TWO", "Check 2", "Push TWO", 1)
    section2 = create_section("Third", "THREE", "Check 3", "Push THREE", 2)

    button = u.create_push_button(text="3", on_clicked="switch3")

    return u.create_column(section0, section1, section2, button)
