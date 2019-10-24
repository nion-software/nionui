from nion.utils import Event
from nion.utils import Model


class Handler:

    def __init__(self):
        # method 1: explicitly handle events
        self.hello1_label = None

        # method 2: dialog handler becomes a model, explicit handling of hello2_text model property
        self.property_changed_event = Event.Event()
        self.__hello2_text = "Hello World Two"

        # method 3: use a property model
        self.hello3_model = Model.PropertyModel("Hello World Three")

        # method 4: use a handler property directly, no update mechanism
        self.hello4_text = "Hello World Four"

    def hello1_updated(self, widget, text):
        self.hello1_label.text = text
        if widget.focused:
            widget.select_all()

    @property
    def hello2_text(self):
        return self.__hello2_text

    @hello2_text.setter
    def hello2_text(self, value):
        self.__hello2_text = value
        self.property_changed_event.fire("hello2_text")


def construct_ui(ui):
    hello1_line_edit = ui.create_line_edit(placeholder_text="Enter Text", on_editing_finished="hello1_updated")
    hello1_label = ui.create_label(name="hello1_label", text="Hello World One")
    hello1 = ui.create_column(hello1_label, hello1_line_edit)

    hello2_line_edit = ui.create_line_edit(placeholder_text="Enter Text", text="@binding(hello2_text)")
    hello2_label = ui.create_label(name="hello2_label", text="@binding(hello2_text)")
    hello2 = ui.create_column(hello2_label, hello2_line_edit)

    hello3_line_edit = ui.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value)")
    hello3_label = ui.create_label(text="@binding(hello3_model.value)")
    hello3 = ui.create_column(hello3_label, hello3_line_edit)

    hello4_line_edit = ui.create_line_edit(placeholder_text="Enter Text", text="@binding(hello3_model.value)")
    hello4_label = ui.create_label(text="@binding(hello4_text)")
    hello4 = ui.create_column(hello4_label, hello4_line_edit)

    hellos = ui.create_column(hello1, hello2, hello3, hello4, spacing=12)

    return hellos
