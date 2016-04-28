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
        self.__document_window = None

    def close(self):
        self.on_close = None
        self.on_mouse_position_changed_by = None
        self.__document_window = None
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

    def grab_mouse(self):
        self.root_container.grab_mouse(self)

    def release_mouse(self):
        self.root_container.release_mouse()

    def grabbed_mouse_position_changed(self, dx, dy, modifiers):
        self.on_mouse_position_changed_by(dx, dy)
        return True

    def track(self, ui, gp, size):
        if not self.__document_window:
            self.__document_window = ui.create_document_window()
            self.__document_window.window_style = "popup"
            self.__canvas_widget = ui.create_canvas_widget(properties={"height": 18, "width": 18})
            def close():
                self.release_mouse()
                self.__document_window.request_close()
                self.__document_window = None
            self.on_close = close
            def activation_changed(activated):
                if not activated:
                    close()
            self.__document_window.on_activation_changed = activation_changed
            self.__canvas_widget.canvas_item.add_canvas_item(self)
            self.__document_window.attach(self.__canvas_widget)
            self.__document_window.show(size=size, position=gp - Geometry.IntPoint(x=size.width, y=size.height / 2))
            self.request_focus()
            self.grab_mouse()
