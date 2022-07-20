"""
    Dialog classes.
"""

from __future__ import annotations

# standard libraries
import gettext
import time
import typing

# third party libraries
# none

# local libraries
from nion.ui import Window
from nion.ui import UserInterface
from nion.utils import Geometry
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import Application
    from nion.ui import Declarative


_ = gettext.gettext


class OkCancelDialog(Window.Window):
    """
        Present a modeless dialog with Ok and Cancel buttons.
    """

    def __init__(self, ui: UserInterface.UserInterface, include_ok: bool = True, include_cancel: bool = True,
                 ok_title: typing.Optional[str] = None, cancel_title: typing.Optional[str] = None,
                 persistent_id: typing.Optional[str] = None, *,
                 app: typing.Optional[Application.BaseApplication] = None,
                 parent_window: typing.Optional[Window.Window] = None):
        super().__init__(ui, app=app, parent_window=parent_window, window_style="dialog", persistent_id=persistent_id)

        self.on_reject: typing.Optional[typing.Callable[[], None]] = None
        self.on_accept: typing.Optional[typing.Callable[[], None]] = None

        self.content = self.ui.create_column_widget()

        content_column = self.ui.create_column_widget()

        content_column.add(self.content)

        button_row = self.ui.create_row_widget()

        button_row.add_stretch()

        if include_cancel:
            def on_cancel_clicked() -> None:
                if self.on_reject:
                    self.on_reject()
                self.request_close()

            cancel_title = cancel_title if cancel_title else _("Cancel")
            cancel_button = self.ui.create_push_button_widget(cancel_title, properties={"min-width": 100})
            cancel_button.on_clicked = on_cancel_clicked
            button_row.add(cancel_button)
            button_row.add_spacing(13)

        if include_ok:
            def on_ok_clicked() -> None:
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

    def __init__(self, ui: UserInterface.UserInterface, title: typing.Optional[str] = None,
                 app: typing.Optional[Application.BaseApplication] = None,
                 parent_window: typing.Optional[Window.Window] = None, persistent_id: typing.Optional[str] = None,
                 window_style: typing.Optional[str] = None):
        if window_style is None:
            window_style = "tool"
        super().__init__(ui, app=app, parent_window=parent_window, persistent_id=persistent_id, window_style=window_style)

        if title is not None:
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

    def add_button(self, title: str, on_clicked_fn: typing.Callable[[], bool]) -> UserInterface.PushButtonWidget:
        def on_clicked() -> None:
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

    def show(self, *, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        if size is None and position is None:
            parent_window = self.parent_window
            assert parent_window
            position = parent_window._document_window.position + Geometry.IntSize(w=parent_window._document_window.size.width // 2 - NotificationDialog.width // 2)
        super().show(position=position)


class PopupWindow(Window.Window):

    def __init__(self, parent_window: Window.Window, ui_widget: Declarative.UIDescription, ui_handler: Declarative.HandlerLike) -> None:
        super().__init__(parent_window.ui, app=parent_window.app, parent_window=parent_window, window_style="popup")

        from nion.ui import Declarative  # avoid circular reference

        def request_close() -> None:
            # this may be called in response to the user clicking a button to close.
            # make sure that the button is not destructed as a side effect of closing
            # the window by queueing the close. and it is not possible to use event loop
            # here because the event loop limitations: not able to run both parent and child
            # event loops simultaneously.
            parent_window.queue_task(self.request_close)

        # make and attach closer for the handler; put handler into container closer
        self.__closer = Declarative.Closer()
        if ui_handler and hasattr(ui_handler, "close"):
            setattr(ui_handler, "_closer", Declarative.Closer())
            self.__closer.push_closeable(ui_handler)

        finishes: typing.List[typing.Callable[[], None]] = list()

        self.widget = Declarative.construct(parent_window.ui, self, ui_widget, ui_handler, finishes)

        self.attach_widget(self.widget)

        for finish in finishes:
            finish()
        if ui_handler and hasattr(ui_handler, "init_handler"):
            getattr(ui_handler, "init_handler")()
        if ui_handler and hasattr(ui_handler, "init_popup"):
            getattr(ui_handler, "init_popup")(request_close)

        self.__ui_handler = ui_handler

    def show(self, *, size: typing.Optional[Geometry.IntSize] = None, position: typing.Optional[Geometry.IntPoint] = None) -> None:
        if size is None and position is None:
            parent_window = self.parent_window
            assert parent_window
            position = parent_window._document_window.position + Geometry.IntSize(w=parent_window._document_window.size.width // 2 - 300 // 2,
                                                                                  h=parent_window._document_window.size.height // 2 - 300 // 2)
        super().show(size=size, position=position)
        ui_handler = self.__ui_handler
        if ui_handler and hasattr(ui_handler, "did_show"):
            getattr(ui_handler, "did_show")()

    def close(self) -> None:
        self.__closer.close()
        super().close()


def pose_select_item_pop_up(items: typing.Sequence[typing.Any], completion_fn: typing.Callable[[typing.Any], None], *,
                            window: Window.Window, current_item: int = 0,
                            item_getter: typing.Optional[typing.Callable[[typing.Any], str]] = None,
                            title: typing.Optional[str] = None) -> None:

    item_getter = item_getter or str

    class Handler:
        def __init__(self) -> None:
            self.is_rejected = True
            self.index_model = Model.PropertyModel(current_item)
            self.item_list: typing.Optional[typing.Any] = None

        def close(self) -> None:
            pass

        def init_popup(self, request_close_fn: typing.Callable[[], None]) -> None:
            self.__request_close_fn = request_close_fn

        def did_show(self) -> None:
            if self.item_list:
                self.item_list.focused = True

        def reject(self, widget: UserInterface.Widget) -> bool:
            # receive this when the user hits escape. let the window handle the escape by returning False.
            # mark popup as rejected.
            return False

        def accept(self, widget: UserInterface.Widget) -> bool:
            # receive this when the user hits return. need to request a close and return True to say we handled event.
            self.__request_close_fn()
            self.is_rejected = False
            return True

        def handle_select(self, widget: UserInterface.Widget) -> None:
            self.is_rejected = False
            self.__request_close_fn()

        def handle_cancel(self, widget: UserInterface.Widget) -> None:
            self.__request_close_fn()

    from nion.ui import Declarative  # avoid circular reference

    # calculate the max string width, add 10%, min 200, max 480
    width = min(max(int(max([window.get_font_metrics("system", item_getter(c)).width for c in items]) * 1.10), 200), 480)

    ui_handler = Handler()
    u = Declarative.DeclarativeUI()
    title_row = u.create_row(u.create_label(text=title or _("Select Item")), u.create_stretch())
    item_list = u.create_list_box(name="item_list", items=[item_getter(c) for c in items], width=width, height=120, min_height=90, size_policy_horizontal="expanding", current_index="@binding(index_model.value)", on_return_pressed="accept", on_escape_pressed="reject")
    button_row = u.create_row(u.create_stretch(), u.create_push_button(text=_("Cancel"), on_clicked="handle_cancel"), u.create_push_button(text=_("Select"), on_clicked="handle_select"), spacing=8)
    column = u.create_column(title_row, item_list, button_row, spacing=4, margin=8)
    popup = PopupWindow(window, column, ui_handler)

    def handle_close() -> None:
        if not ui_handler.is_rejected:
            computation = items[ui_handler.index_model.value or 0]
            completion_fn(computation)
        else:
            completion_fn(None)

    popup.on_close = handle_close
    popup.show()#position=position, size=size)
