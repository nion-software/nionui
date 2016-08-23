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
        self.root_container.grab_mouse(self, gx, gy)

    def release_mouse(self):
        self.root_container.release_mouse()

    def grabbed_mouse_position_changed(self, dx, dy, modifiers):
        self.on_mouse_position_changed_by(dx, dy)
        return True
