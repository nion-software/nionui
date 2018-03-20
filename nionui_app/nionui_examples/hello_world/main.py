# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Declarative

_ = gettext.gettext


# user program below

class Handler:
    def __init__(self):
        self.label_item = None
        self.click_count = 0

    def button_clicked(self, widget):
        self.click_count += 1
        self.label_item.text = _("Clicked") + " " + str(self.click_count)


def main(args, bootstrap_args):
    ui = Declarative.DeclarativeUI()
    button = ui.create_push_button(text=_("Hello World"), on_clicked="button_clicked")
    label = ui.create_label(name="label_item", text=_("Not Clicked"))
    column = ui.create_column(button, label, spacing=8)
    window = ui.create_window(column, title=_("Hello World"), margin=12)
    handler = Handler()
    return Declarative.run_ui(args, bootstrap_args, window, handler)
