import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Model


class Handler(Declarative.Handler):
    """Put text on the clipboard and take it back."""

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it for reaching the user interface.
        self.container_handler: typing.Any = None
        self.status_model = Model.PropertyModel("")
        self.text_model = Model.PropertyModel("text to copy")
        self.clipboard_model = Model.PropertyModel("")

    @property
    def __ui(self) -> UserInterface.UserInterface:
        return typing.cast(Window.Window, getattr(self.container_handler, "window")).ui

    def copy_text(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__ui.clipboard_set_text(self.text_model.value or str())
        self.__show_clipboard()
        self.status_model.value = "Copied the text to the clipboard"

    def paste_text(self, widget: UserInterface.PushButtonWidget) -> None:
        self.text_model.value = self.__ui.clipboard_text()
        self.__show_clipboard()
        self.status_model.value = "Pasted the text from the clipboard"

    def clear_clipboard(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__ui.clipboard_clear()
        self.__show_clipboard()
        self.status_model.value = "Cleared the clipboard"

    def show_clipboard(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__show_clipboard()
        self.status_model.value = "Read the clipboard"

    def __show_clipboard(self) -> None:
        self.clipboard_model.value = self.__ui.clipboard_text()


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # the text in the field goes to the clipboard and comes back from it. the clipboard is shared with the rest of the
    # system, so text copied from another application can be pasted here.
    text_row = u.create_row(u.create_line_edit(text="@binding(text_model.value)", width=240),
                            u.create_stretch(), spacing=8)

    button_row = u.create_row(u.create_push_button(text="Copy", on_clicked="copy_text"),
                              u.create_push_button(text="Paste", on_clicked="paste_text"),
                              u.create_push_button(text="Show", on_clicked="show_clipboard"),
                              u.create_push_button(text="Clear", on_clicked="clear_clipboard"),
                              u.create_stretch(), spacing=8)

    clipboard_row = u.create_row(u.create_label(text="Clipboard:"),
                                 u.create_label(text="@binding(clipboard_model.value)"),
                                 u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(u.create_label(text="Text on the clipboard, which is shared with the rest of the system."),
                           text_row, button_row, clipboard_row, status_label, spacing=8)
