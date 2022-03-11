from nion.ui import Declarative
from nion.utils import Model


class Handler(Declarative.Handler):
    stack_index_model = Model.PropertyModel(1)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    stack0 = u.create_column(u.create_label(text="111"), u.create_label(text="ONE"))
    stack1 = u.create_column(u.create_label(text="222"), u.create_label(text="TWO"))
    stack2 = u.create_column(u.create_label(text="333"), u.create_label(text="THREE"))
    stack = u.create_stack(stack0, stack1, stack2, current_index="@binding(stack_index_model.value)")
    chooser = u.create_combo_box(items=["One", "Two", "Three"], current_index="@binding(stack_index_model.value)")
    return u.create_column(stack, chooser, spacing=8)
