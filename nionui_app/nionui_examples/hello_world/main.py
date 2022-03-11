# standard libraries
import gettext
import typing

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import Declarative

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


_ = gettext.gettext


# user program below

class Handler(Declarative.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.label_item: typing.Optional[UserInterface.LabelWidget] = None
        self.click_count = 0

    def button_clicked(self, widget: Declarative.UIWidget) -> None:
        assert self.label_item
        self.click_count += 1
        self.label_item.text = _("Clicked") + " " + str(self.click_count)


def main(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any]) -> Application.BaseApplication:
    ui = Declarative.DeclarativeUI()
    button = ui.create_push_button(text=_("Hello World"), on_clicked="button_clicked")
    label = ui.create_label(name="label_item", text=_("Not Clicked"))
    column = ui.create_column(button, label, spacing=8)
    window = ui.create_window(column, title=_("Hello World"), margin=12)
    return Application.run_window(args, bootstrap_args, window, Handler())
