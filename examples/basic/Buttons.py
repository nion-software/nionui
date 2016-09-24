# standard libraries
# None

# third party libraries
import numpy

# local libraries
from nion.ui import Application
from nion.ui import Window
from nion.utils import Binding
from nion.utils import Converter
from nion.utils import Model


# user program below

class ButtonsApplication(Application.Application):

    def __init__(self, ui):
        super().__init__(ui)

    def start(self):
        # the start method should create a document window that will be the focus of the ui
        self.window = ButtonsWindow(self.ui, app=self)
        self.window.title = "Buttons"
        self.window.show()
        return True


class ButtonsWindow(Window.Window):

    def __init__(self, ui, app=None):
        super().__init__(ui, app)

        # a text model to hold the label widget text
        text_model = Model.PropertyModel(0)

        # make bitmap_data (random static) for icon push button
        bitmap = numpy.zeros((32, 32, 4), numpy.uint8)
        bitmap[..., 0] = (numpy.random.randn(32, 32) * 255).astype(numpy.uint8)  # blue
        bitmap[..., 1] = (numpy.random.randn(32, 32) * 255).astype(numpy.uint8)  # green
        bitmap[..., 2] = (numpy.random.randn(32, 32) * 255).astype(numpy.uint8)  # red
        bitmap[..., 3] = 255
        bitmap_data = bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1])

        # create the widgets for the window
        label_widget = self.ui.create_label_widget()
        push_button_widget = self.ui.create_push_button_widget("Push Me")
        icon_button_widget = self.ui.create_push_button_widget()
        icon_button_widget.icon = bitmap_data

        # create a row for the buttons
        button_row = self.ui.create_row_widget()
        button_row.add_spacing(13)
        button_row.add(push_button_widget)
        button_row.add_spacing(13)
        button_row.add(icon_button_widget)
        button_row.add_stretch()

        # create a row for the label
        label_row = self.ui.create_row_widget()
        label_row.add_spacing(13)
        label_row.add(label_widget)
        label_row.add_stretch()

        # create a column to hold the two rows and attach it to the window
        content = self.ui.create_column_widget()
        content.add(button_row)
        content.add(label_row)
        self.attach_widget(content)

        # when either button is clicked, this will be called
        def button_clicked():
            text_model.value = text_model.value + 1

        # connect the buttons to the button_clicked function
        push_button_widget.on_clicked = button_clicked
        icon_button_widget.on_clicked = button_clicked

        # and bind the label txt to the 'value' property of the text_model, but attach an integer-to-string converter to it.
        label_widget.bind_text(Binding.PropertyBinding(text_model, "value", Converter.IntegerToStringConverter(format="You have clicked {:d} times.")))


def main(args, bootstrap_args):
    app = ButtonsApplication(Application.make_ui(bootstrap_args))
    app.initialize()
    return app
