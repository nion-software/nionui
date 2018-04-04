"""
    Dialog classes.
"""

# standard libraries
import gettext

# typing
from typing import Callable

# third party libraries
# none

# local libraries
from nion.ui import Window
from nion.ui import UserInterface

_ = gettext.gettext


class OkCancelDialog(Window.Window):
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """
    def __init__(self, ui, include_ok: bool=True, include_cancel: bool=True, ok_title: str=None, cancel_title: str=None, persistent_id: str=None):
        super().__init__(ui, window_style="dialog", persistent_id=persistent_id)

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

    def close(self) -> None:
        self.finish_periodic()  # required to finish periodic operations during tests
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
    def __init__(self, ui, title: str=None, app=None, parent_window=None, persistent_id=None, window_style=None):
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

    def close(self) -> None:
        self.finish_periodic()  # required to finish periodic operations during tests
        super().close()

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
