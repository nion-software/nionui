import pathlib
import typing

from nion.ui import Declarative
from nion.ui import Dialog
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Model


class ModelessHandler(Declarative.Handler):
    """The handler for the declarative modeless dialog."""

    def __init__(self, report_fn: typing.Callable[[str], None]) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.__report_fn = report_fn
        self.text_model = Model.PropertyModel("edit me")
        self.ui_view = u.create_column(u.create_label(text="A modeless dialog described declaratively."),
                                       u.create_line_edit(text="@binding(text_model.value)",
                                                          size_policy_horizontal="expanding"),
                                       u.create_row(u.create_stretch(),
                                                    u.create_push_button(text="Report", on_clicked="report"),
                                                    spacing=8),
                                       u.create_stretch(), spacing=8, margin=8)

    def report(self, widget: UserInterface.PushButtonWidget) -> None:
        self.__report_fn(f"Modeless dialog says: {self.text_model.value}")


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        # the page is displayed within a window; the container handler supplies it when a dialog needs a parent.
        self.container_handler: typing.Any = None
        self.status_model = Model.PropertyModel("")
        self.color_model = Model.PropertyModel("#4080c0")
        # a dialog is held weakly by the window it belongs to, so hold the ones opened here.
        self.__dialogs: typing.List[typing.Any] = list()
        self.__directory = str(pathlib.Path.home())

    def close(self) -> None:
        self.__dialogs = list()
        super().close()

    @property
    def __window(self) -> Window.Window:
        return typing.cast(Window.Window, getattr(self.container_handler, "window"))

    def show_ok_cancel(self, widget: UserInterface.PushButtonWidget) -> None:
        window = self.__window
        dialog = Dialog.OkCancelDialog(window.ui, parent_window=window, app=window.app)
        dialog.content.add(window.ui.create_label_widget("Accept or reject this dialog."))
        dialog.on_accept = lambda: self.__report("Ok/Cancel dialog accepted")
        dialog.on_reject = lambda: self.__report("Ok/Cancel dialog rejected")
        self.__dialogs.append(dialog)
        dialog.show()

    def show_action(self, widget: UserInterface.PushButtonWidget) -> None:
        window = self.__window
        dialog = Dialog.ActionDialog(window.ui, title="Action Dialog", parent_window=window, app=window.app)
        dialog.content.add(window.ui.create_label_widget("A dialog with buttons of its own."))

        def report_and_close(what: str) -> bool:
            self.__report(f"Action dialog: {what}")
            return True

        dialog.add_button("Later", lambda: report_and_close("later"))
        dialog.add_button("Now", lambda: report_and_close("now"))
        self.__dialogs.append(dialog)
        dialog.show()

    def show_notification(self, widget: UserInterface.PushButtonWidget) -> None:
        # a notification takes itself away after a few seconds.
        window = self.__window
        dialog = Dialog.NotificationDialog(window.ui, message="A notification, which closes itself.",
                                           parent_window=window)
        self.__dialogs.append(dialog)
        dialog.show()
        self.__report("Notification shown")

    def show_modeless(self, widget: UserInterface.PushButtonWidget) -> None:
        window = self.__window
        handler = ModelessHandler(self.__report)
        dialog = Declarative.run_window(Declarative.DeclarativeUI().create_window(handler.ui_view,
                                                                                 title="Modeless Dialog",
                                                                                 margin=8),
                                        handler, parent_window=window, window_style="dialog")
        self.__dialogs.append(dialog)

    # the dialogs below are provided by the host rather than built here.

    def open_file(self, widget: UserInterface.PushButtonWidget) -> None:
        file_paths, _filter, directory = self.__window.get_file_path_dialog("Open File", self.__directory, "All Files (*.*)")
        self.__directory = directory or self.__directory
        self.__report(f"Opened: {file_paths[0]}" if file_paths else "Opened: nothing")

    def open_files(self, widget: UserInterface.PushButtonWidget) -> None:
        file_paths, _filter, directory = self.__window.get_file_paths_dialog("Open Files", self.__directory, "All Files (*.*)")
        self.__directory = directory or self.__directory
        self.__report(f"Opened {len(file_paths)} file(s)" if file_paths else "Opened: nothing")

    def save_file(self, widget: UserInterface.PushButtonWidget) -> None:
        file_path, _filter, directory = self.__window.get_save_file_path("Save File As", self.__directory, "All Files (*.*)")
        self.__directory = directory or self.__directory
        self.__report(f"Saving to: {file_path}" if file_path else "Saving: nowhere")

    def choose_directory(self, widget: UserInterface.PushButtonWidget) -> None:
        directory, _directory = self.__window.ui.get_existing_directory_dialog("Choose Directory", self.__directory)
        self.__directory = directory or self.__directory
        self.__report(f"Directory: {directory}" if directory else "Directory: none")

    def choose_color(self, widget: UserInterface.PushButtonWidget) -> None:
        color = self.__window.ui.get_color_dialog("Choose Color", self.color_model.value, True)
        if color:
            self.color_model.value = color
        self.__report(f"Color: {color}" if color else "Color: unchanged")

    def __report(self, message: str) -> None:
        self.status_model.value = message


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    # each button opens one of the dialogs. they are all modeless: the page stays usable while they are open.
    dialog_row = u.create_row(u.create_push_button(text="Ok/Cancel...", on_clicked="show_ok_cancel"),
                              u.create_push_button(text="Action...", on_clicked="show_action"),
                              u.create_push_button(text="Notification...", on_clicked="show_notification"),
                              u.create_push_button(text="Modeless...", on_clicked="show_modeless"),
                              u.create_stretch(), spacing=8)

    # the dialogs the host provides: choosing files, a directory, a color.
    host_row = u.create_row(u.create_push_button(text="Open File...", on_clicked="open_file"),
                            u.create_push_button(text="Open Files...", on_clicked="open_files"),
                            u.create_push_button(text="Save File As...", on_clicked="save_file"),
                            u.create_stretch(), spacing=8)

    host_row2 = u.create_row(u.create_push_button(text="Choose Directory...", on_clicked="choose_directory"),
                             u.create_push_button(text="Choose Color...", on_clicked="choose_color"),
                             u.create_label(text="@binding(color_model.value)"),
                             u.create_stretch(), spacing=8)

    status_label = u.create_label(text="@binding(status_model.value)")

    return u.create_column(u.create_label(text="Dialogs built here, opened on the window containing this page."),
                           dialog_row,
                           u.create_spacing(8),
                           u.create_label(text="Dialogs provided by the host."),
                           host_row, host_row2,
                           status_label, spacing=8)
