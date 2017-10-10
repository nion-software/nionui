# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Declarative

_ = gettext.gettext


# user program below

class Handler:
    label_item = None
    click_count = 0

    def button_clicked(self, widget):
        self.click_count += 1
        self.label_item.text = _("Clicked") + " " + str(self.click_count)


def main(args, bootstrap_args):
    ui = Declarative.DeclarativeUI()
    d = ui.create_push_button(text=_("Hello World"), on_clicked="button_clicked")
    l = ui.create_label(name="label_item", text=_("Not Clicked"))
    w = ui.create_window(ui.create_column(d, l, spacing=8), title=_("Hello World"), margin=12)
    return Declarative.run_ui(args, bootstrap_args, w, Handler())
