# standard libraries
import contextlib
import logging
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.utils import Geometry


class TestCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        CanvasItem._threaded_rendering_enabled = False

    def tearDown(self) -> None:
        pass

    def test_add_item_to_string_list_widget_causes_container_to_relayout(self) -> None:
        # ugly type casting
        from nion.ui import Widgets
        ui = TestUI.UserInterface()
        widget = Widgets.StringListWidget(ui)
        with contextlib.closing(widget):
            canvas_item = typing.cast(CanvasItem.CanvasItemComposition, typing.cast(UserInterface.CanvasWidget, typing.cast(UserInterface.BoxWidget, widget.content_widget).children[0]).canvas_item)
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=300, height=200))
            scroll_area_canvas_item = typing.cast(CanvasItem.ScrollAreaCanvasItem, typing.cast(CanvasItem.CanvasItemComposition, canvas_item.canvas_items[0]).canvas_items[0])
            canvas_item.layout_immediate(Geometry.IntSize(width=300, height=200))
            # check assumptions
            scroll_canvas_rect = scroll_area_canvas_item.canvas_rect or Geometry.IntRect.empty_rect()
            scroll_content = scroll_area_canvas_item.content
            assert scroll_content
            self.assertEqual(scroll_canvas_rect.height, 200)
            scroll_content_rect = scroll_content.canvas_rect or Geometry.IntRect.empty_rect()
            self.assertEqual(scroll_content_rect.height, 0)
            # add item
            widget.items = ["abc"]
            # check that column was laid out again
            canvas_item.layout_immediate(Geometry.IntSize(width=300, height=200))
            scroll_canvas_rect = scroll_area_canvas_item.canvas_rect or Geometry.IntRect.empty_rect()
            scroll_content = scroll_area_canvas_item.content
            assert scroll_content
            scroll_content_rect = scroll_content.canvas_rect or Geometry.IntRect.empty_rect()
            self.assertEqual(scroll_canvas_rect.height, 200)
            self.assertEqual(scroll_content_rect.height, 20)

    def test_push_button_shows_both_text_and_icon_when_both_are_set(self) -> None:
        from nion.ui import Bitmap
        from nion.ui import Widgets
        import numpy
        ui = TestUI.UserInterface()
        controller = Widgets.BasicPushButtonWidgetCanvasItemController(ui)
        bitmap = Bitmap.promote_bitmap(numpy.zeros((16, 16), dtype=numpy.uint32))
        controller.set_text("Text")
        controller.set_icon(bitmap)
        stack = controller.widget_source.canvas_item
        icon_canvas_item, text_canvas_item = stack.canvas_items
        # both the icon and the text should be visible and contribute to the overall width.
        self.assertTrue(icon_canvas_item.visible)
        self.assertTrue(text_canvas_item.visible)
        # the stack should be at least as wide as its content, but never narrower than the
        # button's sensible default minimum width.
        content_width = icon_canvas_item.layout_sizing.preferred_width_int + text_canvas_item.layout_sizing.preferred_width_int
        self.assertEqual(stack.layout_sizing.preferred_width_int, max(content_width, Widgets.BasicPushButtonWidgetCanvasItemController.default_minimum_width))
        # setting the icon back to None should hide only the icon, leaving the text visible.
        controller.set_icon(None)
        self.assertFalse(icon_canvas_item.visible)
        self.assertTrue(text_canvas_item.visible)
        # setting the text back to None should hide only the text, leaving nothing visible.
        controller.set_text(None)
        self.assertFalse(icon_canvas_item.visible)
        self.assertFalse(text_canvas_item.visible)

    def test_push_button_shows_only_icon_when_only_icon_is_set(self) -> None:
        from nion.ui import Bitmap
        from nion.ui import Widgets
        import numpy
        ui = TestUI.UserInterface()
        controller = Widgets.BasicPushButtonWidgetCanvasItemController(ui)
        bitmap = Bitmap.promote_bitmap(numpy.zeros((16, 16), dtype=numpy.uint32))
        controller.set_icon(bitmap)
        controller.set_text(None)
        stack = controller.widget_source.canvas_item
        icon_canvas_item, text_canvas_item = stack.canvas_items
        self.assertTrue(icon_canvas_item.visible)
        self.assertFalse(text_canvas_item.visible)
        self.assertEqual(stack.layout_sizing.preferred_width_int,
                          max(icon_canvas_item.layout_sizing.preferred_width_int, Widgets.BasicPushButtonWidgetCanvasItemController.default_minimum_width))

    def test_push_button_shows_only_text_when_only_text_is_set(self) -> None:
        from nion.ui import Widgets
        ui = TestUI.UserInterface()
        controller = Widgets.BasicPushButtonWidgetCanvasItemController(ui)
        controller.set_text("Hello")
        controller.set_icon(None)
        stack = controller.widget_source.canvas_item
        icon_canvas_item, text_canvas_item = stack.canvas_items
        self.assertFalse(icon_canvas_item.visible)
        self.assertTrue(text_canvas_item.visible)
        self.assertEqual(stack.layout_sizing.preferred_width_int,
                          max(text_canvas_item.layout_sizing.preferred_width_int, Widgets.BasicPushButtonWidgetCanvasItemController.default_minimum_width))


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
