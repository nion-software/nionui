# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import DocumentController
from nion.utils import Binding
from nion.utils import Converter
from nion.utils import Model


# user program below

class ButtonsApplication(Application.Application):

    def __init__(self, ui):
        super().__init__(ui)

    def start(self):
        # the start method should create a document window that will be the focus of the ui
        self.document_controller = ButtonsDocumentController(self.ui, app=self)
        self.document_controller.document_window.title = "Buttons"
        self.document_controller.document_window.show()
        return True


class ButtonsDocumentController(DocumentController.DocumentController):

    def __init__(self, ui, app=None):
        super().__init__(ui, app)

        text_model = Model.PropertyModel(0)

        label_widget = self.ui.create_label_widget()
        push_button_widget = self.ui.create_push_button_widget("Push Me")

        button_row = self.ui.create_row_widget()
        button_row.add_spacing(13)
        button_row.add(push_button_widget)
        button_row.add_stretch()

        label_row = self.ui.create_row_widget()
        label_row.add_spacing(13)
        label_row.add(label_widget)
        label_row.add_stretch()

        content = self.ui.create_column_widget()
        content.add(button_row)
        content.add(label_row)

        content_column = self.ui.create_column_widget()
        content_column.add(content)
        self.document_window.attach(content_column)

        def button_clicked():
            text_model.value = text_model.value + 1

        push_button_widget.on_clicked = button_clicked
        label_widget.bind_text(Binding.PropertyBinding(text_model, "value", Converter.IntegerToStringConverter(format="You have clicked {:d} times.")))


def main(args, bootstrap_args):
    app = ButtonsApplication(Application.make_ui(bootstrap_args))
    app.initialize()
    return app
