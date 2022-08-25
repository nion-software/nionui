import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import Event
from nion.utils import Model


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        # method 1: explicitly handle events
        self.hello1_label: typing.Optional[UserInterface.LabelWidget] = None

        # method 2: dialog handler becomes a model, explicit handling of hello2_text model property
        self.property_changed_event = Event.Event()
        self.__hello2_text = "Hello World Two"

        # method 3: use a property model
        self.hello3_model = Model.PropertyModel("Hello World Three")

        # method 4: use a handler property directly, no update mechanism
        self.hello4_text = "Hello World Four"

    def hello1_updated(self, widget: Declarative.UIWidget, text: str) -> None:
        assert self.hello1_label
        self.hello1_label.text = text
        line_edit = typing.cast(UserInterface.LineEditWidget, widget)
        if line_edit.focused:
            line_edit.select_all()

    @property
    def hello2_text(self) -> str:
        return self.__hello2_text

    @hello2_text.setter
    def hello2_text(self, value: str) -> None:
        self.__hello2_text = value
        self.property_changed_event.fire("hello2_text")


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:

    hello1_line_edit = u.create_line_edit(placeholder_text="Enter Text", on_editing_finished="hello1_updated")
    hello1_label = u.create_label(name="hello1_label", text="Hello World One")
    hello1 = u.create_column(hello1_label, hello1_line_edit)

    hello2_line_edit = u.create_line_edit(placeholder_text="Enter Text", text="@binding(hello2_text)")
    hello2_label = u.create_label(name="hello2_label", text="@binding(hello2_text)")
    hello2 = u.create_column(hello2_label, hello2_line_edit)

    hello3_line_edit = u.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value)")
    hello3_label = u.create_label(text="@binding(hello3_model.value)")
    hello3 = u.create_column(hello3_label, hello3_line_edit)

    hello4_line_edit = u.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value)")
    hello4_label = u.create_label(text="@binding(hello4_text)")
    hello4 = u.create_column(hello4_label, hello4_line_edit)

    hellos = u.create_column(hello1, hello2, hello3, hello4, spacing=12)

    return hellos
