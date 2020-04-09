"""
    Dialog classes.
"""

# standard libraries
import gettext
import time

# typing
from typing import Callable

# third party libraries
# none

# local libraries
from nion.ui import Application
from nion.ui import Window
from nion.ui import UserInterface
from nion.utils import Geometry

_ = gettext.gettext


class OkCancelDialog(Window.Window):
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """

    def __init__(self, ui, include_ok: bool = True, include_cancel: bool = True, ok_title: str = None,
                 cancel_title: str = None, persistent_id: str = None, *, app: Application.BaseApplication = None,
                 parent_window: Window.Window = None):
        super().__init__(ui, app=app, parent_window=parent_window, window_style="dialog", persistent_id=persistent_id)

        self.on_reject = None
        self.on_accept = None

        self.content = self.ui.create_column_widget()

        content_column = self.ui.create_column_widget()

        content_column.add(self.content)

        button_row = self.ui.create_row_widget()

        button_row.add_stretch()

        if include_cancel:
            def on_cancel_clicked():
                if self.on_reject:
                    self.on_reject()
                self.request_close()

            cancel_title = cancel_title if cancel_title else _("Cancel")
            cancel_button = self.ui.create_push_button_widget(cancel_title, properties={"min-width": 100})
            cancel_button.on_clicked = on_cancel_clicked
            button_row.add(cancel_button)
            button_row.add_spacing(13)

        if include_ok:
            def on_ok_clicked():
                if self.on_accept:
                    self.on_accept()
                self.request_close()

            ok_title = ok_title if ok_title else _("OK")
            ok_button = self.ui.create_push_button_widget(ok_title, properties={"min-width": 100})
            ok_button.on_clicked = on_ok_clicked
            button_row.add(ok_button)
            button_row.add_spacing(13)

        content_column.add(button_row)
        content_column.add_spacing(8)

        self.attach_widget(content_column)

        if parent_window:
            parent_window.register_dialog(self)
        elif app:
            app.register_dialog(self)

    def close(self) -> None:
        self.on_reject = None
        self.on_accept = None
        super().close()

    def about_to_close(self, geometry: str, state: str) -> None:
        if self.on_reject:
            self.on_reject()
        super().about_to_close(geometry, state)


class ActionDialog(Window.Window):
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """

    def __init__(self, ui: UserInterface.UserInterface, title: str = None, app: Application.BaseApplication = None,
                 parent_window: Window.Window = None, persistent_id: str = None, window_style: str = None):
        if window_style is None:
            window_style = "tool"
        super().__init__(ui, app=app, parent_window=parent_window, persistent_id=persistent_id, window_style=window_style)

        self.title = title

        self.content = self.ui.create_column_widget()

        content_column = self.ui.create_column_widget()

        content_column.add(self.content)

        self.button_row = self.ui.create_row_widget()

        self.button_row.add_spacing(13)
        self.button_row.add_stretch()

        content_column.add(self.button_row)
        content_column.add_spacing(8)

        self.attach_widget(content_column)

        if parent_window:
            parent_window.register_dialog(self)
        elif app:
            app.register_dialog(self)

    def add_button(self, title: str, on_clicked_fn: Callable[[], bool]) -> UserInterface.PushButtonWidget:
        def on_clicked():
            do_close = on_clicked_fn()
            if do_close:
                self.request_close()

        button = self.ui.create_push_button_widget(title)
        button.on_clicked = on_clicked
        self.button_row.add(button)
        self.button_row.add_spacing(13)
        return button


class NotificationDialog(Window.Window):
    width = 320

    def __init__(self, ui: UserInterface.UserInterface, *, message: str, parent_window: Window.Window):
        super().__init__(ui, parent_window=parent_window)
        self._document_window.set_window_style(["tool", "frameless-hint"])
        self._document_window.set_palette_color("background", 255, 255, 204, 224)
        content_column = ui.create_column_widget()
        content_row = ui.create_row_widget()
        label = ui.create_label_widget(message, properties={"width": NotificationDialog.width})
        label.word_wrap = True
        content_row.add_spacing(8)
        content_row.add(label)
        content_row.add_spacing(8)
        content_column.add_spacing(8)
        content_column.add(content_row)
        content_column.add_stretch()
        content_column.add_spacing(8)
        self.__start_time = time.time()
        self.attach_widget(content_column)
        parent_window.register_dialog(self)

    def periodic(self) -> None:
        if time.time() - self.__start_time > 5.0:
            self.request_close()

    def show(self, *, size: Geometry.IntSize=None, position: Geometry.IntPoint=None) -> None:
        if size is None and position is None:
            parent_window = self.parent_window
            position = parent_window._document_window.position + Geometry.IntSize(w=parent_window._document_window.size.width // 2 - NotificationDialog.width // 2)
        super().show(position=position)
