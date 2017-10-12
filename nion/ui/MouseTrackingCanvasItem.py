import asyncio
import functools
import sys
import typing

from nion.ui import CanvasItem
from nion.utils import Geometry


class TrackingCanvasItem(CanvasItem.CanvasItemComposition):

    """Track changes to the mouse without showing the cursor.

    Callers should configure this item by adding a layout and canvas items.

    Callers should listen to the on_mouse_position_changed_by(dx, dy) message.

    Callers should call track(ui, global_pos, window_size) to track the mouse.

    It is an error to call track(...) while already tracking.
    """

    def __init__(self):
        super(TrackingCanvasItem, self).__init__()
        self.wants_mouse_events = True
        self.focusable = True
        self.on_close = None
        self.on_mouse_position_changed_by = None

    def close(self):
        self.on_close = None
        self.on_mouse_position_changed_by = None
        super(TrackingCanvasItem, self).close()

    def mouse_clicked(self, x, y, modifiers):
        self.on_close()
        return True

    def mouse_double_clicked(self, x, y, modifiers):
        self.on_close()
        return True

    def context_menu_event(self, x, y, gx, gy):
        self.on_close()
        return True

    def key_pressed(self, key):
        self.on_close()
        return True

    def grab_mouse(self, gx, gy):
        self.__discard_first = True
        self.root_container.grab_mouse(self, gx, gy)

    def release_mouse(self):
        self.root_container.release_mouse()

    def grabbed_mouse_position_changed(self, dx, dy, modifiers):
        if not self.__discard_first:
            self.on_mouse_position_changed_by(Geometry.IntPoint(x=dx, y=dy))
        self.__discard_first = False
        return True


def start_mouse_tracker(ui, event_loop: asyncio.AbstractEventLoop, canvas_item: CanvasItem.AbstractCanvasItem,
                        mouse_position_changed_by_fn: typing.Callable[[Geometry.IntPoint], None], global_pos: Geometry.IntPoint, size: Geometry.IntSize):

    tracking_canvas_item = TrackingCanvasItem()
    tracking_canvas_item.on_mouse_position_changed_by = mouse_position_changed_by_fn
    tracking_canvas_item.add_canvas_item(canvas_item)

    async def handle_close_later(document_window):
        document_window.request_close()

    def handle_close(document_window):
        tracking_canvas_item.release_mouse()
        event_loop.create_task(handle_close_later(document_window))

    def activation_changed(document_window, activated):
        if not activated:
            handle_close(document_window)

    # create the popup window
    document_window = ui.create_document_window()
    document_window.window_style = "mousegrab"

    def close_window(geometry, state):
        ui.destroy_document_window(document_window)

    document_window.on_about_to_close = close_window

    document_window.on_activation_changed = functools.partial(activation_changed, document_window)
    tracking_canvas_item.on_close = functools.partial(handle_close, document_window)

    # configure canvas widget, attach to document window
    mousegrab_window_pos = global_pos - Geometry.IntPoint(x=size.width, y=size.height / 2)
    document_window.show(size=size, position=mousegrab_window_pos)
    if sys.platform == "win32":
        relative_pos = Geometry.IntPoint()
    else:
        relative_pos = mousegrab_window_pos
        document_window.fill_screen()
    canvas_widget = ui.create_canvas_widget()
    tracking_canvas_item.sizing.set_fixed_size(size)
    content_row_canvas_item = CanvasItem.CanvasItemComposition()
    content_row_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
    content_row_canvas_item.add_spacing(relative_pos.x)
    content_row_canvas_item.add_canvas_item(tracking_canvas_item)
    content_row_canvas_item.add_stretch()
    content_canvas_item = CanvasItem.CanvasItemComposition()
    content_canvas_item.layout = CanvasItem.CanvasItemColumnLayout()
    content_canvas_item.add_spacing(relative_pos.y)
    content_canvas_item.add_canvas_item(content_row_canvas_item)
    content_canvas_item.add_stretch()
    canvas_widget.canvas_item.add_canvas_item(content_canvas_item)
    document_window.attach(canvas_widget)
    tracking_canvas_item.request_focus()
    tracking_canvas_item.cursor_shape = "blank"
    canvas_widget.set_cursor_shape("blank")
    tracking_canvas_item.grab_mouse(relative_pos.x + size.width // 2, relative_pos.y + size.height // 2)
