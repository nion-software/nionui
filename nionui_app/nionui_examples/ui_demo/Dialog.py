# standard libraries
import gettext
import typing


# third party libraries
# None

# local libraries
from nion.ui import Declarative
from nion.swift import Facade

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface

dialog_open = False

api: Facade.API_1 = Facade.get_api("~1.0", "~1.0")

_ = gettext.gettext


# user program below

class Handler(Declarative.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.label_item_lb: typing.Optional[UserInterface.LabelWidget] = None
        self.click_count = 0
        self.on_closed: typing.Optional[typing.Callable] = None

    def button_clicked(self, widget: Declarative.UIWidget) -> None:
        assert self.label_item_lb
        self.click_count += 1
        self.label_item_lb.text = _("Clicked") + " " + str(self.click_count)

    def close(self) -> None:
        if callable(self.on_closed):
            self.on_closed()
        super().close()


class View():
    def __init__(self):
        ui = Declarative.DeclarativeUI()
        self.label_item = ui.create_label(text="", name="label_item_lb")
        self.click_count = ui.create_push_button(text="Click", name = "click_count_pb",on_clicked="button_clicked")
        self.ui_view: Declarative.UIDescription = ui.create_column(self.click_count,self.label_item)

def open_dialog() -> None:
    global dialog_open
    if not dialog_open:
        ui = Declarative.DeclarativeUI()
        document_controller = api.application.document_controllers[0]._document_controller
        ui_handler = Handler()
        ui_view = View().ui_view
        def dialog_closed():
            print("close")
            global dialog_open
            dialog_open = False
        # note that a more straightforward way would be to directly put the dialog_closed
        # code into the close methode of the handler
        ui_handler.on_closed = dialog_closed
        ui_view = ui.create_modeless_dialog(ui_view,title="Clicker",)
        dialog: Declarative.Dialog = Declarative.construct(document_controller.ui, document_controller, ui_view, ui_handler,[dialog_closed])
        dialog.show()
        dialog_open = True