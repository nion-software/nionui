import typing

from nion.ui import Declarative
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.cb1: typing.Optional[UserInterface.ComboBoxWidget] = None
        self.cb2_current_index_model = Model.PropertyModel(1)
        self.cb2_current_index_model.on_value_changed = self.cb2_current_index_changed
        self.numbers = ["One", "Two", "Three"]
        self.numeros = Model.PropertyModel[typing.List[str]]([])
        self.numeros.value = ["Uno", "Dos", "Tres"]

    def init_handler(self) -> None:
        # this method is called after all fields are populated
        assert self.cb1
        self.cb1.current_index = 2

    def cb1_current_index_changed(self, widget: Declarative.UIWidget, current_index: int) -> None:
        print(f"CB1 {current_index}")

    def cb2_current_index_changed(self, current_index: typing.Optional[int]) -> None:
        print(f"CB2 {current_index}")

    def change_items(self, widget: Declarative.UIWidget) -> None:
        self.numeros.value = ["Eins", "Zwei"]#, "Drei"]


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:

    cb1 = u.create_combo_box(name="cb1", items=["Red", "Green", "Blue"], on_current_index_changed="cb1_current_index_changed")
    cb2 = u.create_combo_box(items=["Sheriff", "Astronaut", "Scientist"], current_index="@binding(cb2_current_index_model.value)")
    cb3 = u.create_combo_box(items_ref="numbers", current_index="@binding(cb2_current_index_model.value)")
    cb4 = u.create_combo_box(items_ref="@binding(numeros.value)", current_index="@binding(cb2_current_index_model.value)")
    button = u.create_push_button(text="Change Items", on_clicked="change_items")

    cb_group = u.create_column(cb1, cb2, cb3, cb4, button, spacing=12)

    return cb_group
