import typing

from nion.ui import Declarative
from nion.ui import Dialog
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Model


class Handler(Declarative.Handler):
    """Pose each of the popup dialogs and report what the user chose."""

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it when a popup needs to be posed.
        self.container_handler: typing.Any = None
        self.status_model = Model.PropertyModel("")
        self.__string = "editable string"

    @property
    def __window(self) -> Window.Window:
        return typing.cast(Window.Window, getattr(self.container_handler, "window"))

    def select_item(self, widget: UserInterface.PushButtonWidget) -> None:
        def handle_selection(item: typing.Optional[str]) -> None:
            self.status_model.value = f"Selected: {item}" if item is not None else "Selected: nothing"

        Dialog.pose_select_item_popup(["Alpha", "Beta", "Gamma", "Delta"], handle_selection,
                                      window=self.__window, title="Choose an Item", current_item=1)

    def select_item_from_long_names(self, widget: UserInterface.PushButtonWidget) -> None:
        def handle_selection(item: typing.Optional[str]) -> None:
            self.status_model.value = f"Selected: {item}" if item is not None else "Selected: nothing"

        items = [f"A considerably longer item name, number {index}" for index in range(12)]
        Dialog.pose_select_item_popup(items, handle_selection, window=self.__window, title="Choose a Long Item")

    def select_item_from_nothing(self, widget: UserInterface.PushButtonWidget) -> None:
        def handle_selection(item: typing.Optional[str]) -> None:
            self.status_model.value = f"Selected: {item}" if item is not None else "Selected: nothing"

        Dialog.pose_select_item_popup(list(), handle_selection, window=self.__window, title="Choose from Nothing")

    def edit_string(self, widget: UserInterface.PushButtonWidget) -> None:
        def handle_edit(string: typing.Optional[str]) -> None:
            if string is not None:
                self.__string = string
            self.status_model.value = f"Edited: {string}" if string is not None else "Edited: cancelled"

        Dialog.pose_edit_string_popup(self.__string, handle_edit, window=self.__window, title="Edit String",
                                      show_buttons=True)

    def confirm(self, widget: UserInterface.PushButtonWidget) -> None:
        def handle_confirmation(confirmed: bool) -> None:
            self.status_model.value = "Confirmed" if confirmed else "Not confirmed"

        Dialog.pose_confirmation_popup(handle_confirmation, window=self.__window, title="Confirm",
                                       caption="Proceed with the operation?", show_buttons=True)


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # each button poses one of the popups. the popups are sized to their content, so the item popups differ in width.
    select_row = u.create_row(u.create_push_button(text="Select Item...", on_clicked="select_item"),
                              u.create_push_button(text="Select Long Item...", on_clicked="select_item_from_long_names"),
                              u.create_push_button(text="Select from Nothing...", on_clicked="select_item_from_nothing"),
                              u.create_stretch(), spacing=8)

    other_row = u.create_row(u.create_push_button(text="Edit String...", on_clicked="edit_string"),
                             u.create_push_button(text="Confirm...", on_clicked="confirm"),
                             u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(u.create_label(text="Popups are posed on the window containing this page."),
                           select_row, other_row, status_label, spacing=8)
