from nion.ui import Declarative
from nion.utils import Model


class Handler:

    stack_index_model = Model.PropertyModel(1)


def construct_ui(ui: Declarative.DeclarativeUI) -> Declarative.UIDescription:

    stack0 = ui.create_column(ui.create_label(text="111"), ui.create_label(text="ONE"))
    stack1 = ui.create_column(ui.create_label(text="222"), ui.create_label(text="TWO"))
    stack2 = ui.create_column(ui.create_label(text="333"), ui.create_label(text="THREE"))

    stack = ui.create_stack(stack0, stack1, stack2, current_index="@binding(stack_index_model.value)")

    chooser = ui.create_combo_box(items=["One", "Two", "Three"], current_index="@binding(stack_index_model.value)")

    return ui.create_column(stack, chooser, spacing=8)
