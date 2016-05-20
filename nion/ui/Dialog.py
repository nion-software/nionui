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
# none


_ = gettext.gettext


class OkCancelDialog:
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """
    def __init__(self, ui, include_ok: bool=True, include_cancel: bool=True, ok_title: str=None, cancel_title: str=None):
        super().__init__()

        self.ui = ui

        self.on_reject = None
        self.on_accept = None

        self.document_window = self.ui.create_document_window()
        self.document_window.window_style = "dialog"
        self.document_window.on_periodic = lambda: self.periodic()
        self.document_window.on_about_to_show = lambda: self.about_to_show()
        self.document_window.on_about_to_close = lambda geometry, state: self.about_to_close(geometry, state)
        self.document_window.on_activation_changed = lambda activated: self.activation_changed(activated)

        self.content = self.ui.create_column_widget()

        content_column = self.ui.create_column_widget()

        content_column.add(self.content)

        button_row = self.ui.create_row_widget()

        button_row.add_stretch()

        if include_cancel:
            def on_cancel_clicked():
                if self.on_reject:
                    self.on_reject()
                self.document_window.request_close()
                self.document_window = None

            cancel_title = cancel_title if cancel_title else _("Cancel")
            cancel_button = self.ui.create_push_button_widget(cancel_title, properties={"min-width": 100})
            cancel_button.on_clicked = on_cancel_clicked
            button_row.add(cancel_button)
            button_row.add_spacing(13)

        if include_ok:
            def on_ok_clicked():
                if self.on_accept:
                    self.on_accept()
                self.document_window.request_close()
                self.document_window = None

            ok_title = ok_title if ok_title else _("OK")
            ok_button = self.ui.create_push_button_widget(ok_title, properties={"min-width": 100})
            ok_button.on_clicked = on_ok_clicked
            button_row.add(ok_button)
            button_row.add_spacing(13)

        content_column.add(button_row)

        self.document_window.attach(content_column)

    def close(self) -> None:
        # recognize when we're running as test and finish out periodic operations
        if not self.document_window.has_event_loop:
            self.periodic()
        self.on_reject = None
        self.on_accept = None
        self.document_window = None

    def periodic(self) -> None:
        pass

    def about_to_show(self) -> None:
        pass

    def about_to_close(self, geometry: str, state: str) -> None:
        if self.on_reject:
            self.on_reject()
        self.close()

    def activation_changed(self, activated: bool) -> None:
        pass

    def show(self) -> None:
        self.document_window.show()


class ActionDialog:
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """
    def __init__(self, ui, title: str=None):
        super().__init__()

        self.ui = ui

        self.on_reject = None
        self.on_accept = None

        self.document_window = self.ui.create_document_window(title=title)
        self.document_window.on_periodic = lambda: self.periodic()
        self.document_window.on_about_to_show = lambda: self.about_to_show()
        self.document_window.on_about_to_close = lambda geometry, state: self.about_to_close(geometry, state)
        self.document_window.on_activation_changed = lambda activated: self.activation_changed(activated)

        self.content = self.ui.create_column_widget()

        content_column = self.ui.create_column_widget()

        content_column.add(self.content)

        self.button_row = self.ui.create_row_widget()

        self.button_row.add_spacing(13)
        self.button_row.add_stretch()

        content_column.add(self.button_row)

        self.document_window.attach(content_column)

    def close(self) -> None:
        # recognize when we're running as test and finish out periodic operations
        if not self.document_window.has_event_loop:
            self.periodic()
        self.on_reject = None
        self.on_accept = None
        self.document_window = None

    def periodic(self) -> None:
        pass

    def about_to_show(self) -> None:
        pass

    def about_to_close(self, geometry: str, state: str) -> None:
        self.close()

    def activation_changed(self, activated: bool) -> None:
        pass

    def show(self) -> None:
        self.document_window.show()

    def add_button(self, title: str, on_clicked_fn: Callable[[], bool]) -> None:
        def on_clicked():
            do_close = on_clicked_fn()
            if do_close:
                self.document_window.request_close()
                self.document_window = None

        button = self.ui.create_push_button_widget(title, properties={"min-width": 100})
        button.on_clicked = on_clicked
        self.button_row.add(button)
        self.button_row.add_spacing(13)
