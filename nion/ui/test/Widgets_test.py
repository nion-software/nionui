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
            canvas_item.update_layout(Geometry.IntPoint(x=0, y=0), Geometry.IntSize(width=300, height=200), immediate=True)
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
            self.assertFalse(canvas_item._needs_layout_for_testing)
            widget.items = ["abc"]
            # self.assertTrue(canvas_item._needs_layout_for_testing)
            # check that column was laid out again
            canvas_item.layout_immediate(Geometry.IntSize(width=300, height=200), force=False)
            scroll_canvas_rect = scroll_area_canvas_item.canvas_rect or Geometry.IntRect.empty_rect()
            scroll_content = scroll_area_canvas_item.content
            assert scroll_content
            scroll_content_rect = scroll_content.canvas_rect or Geometry.IntRect.empty_rect()
            self.assertEqual(scroll_canvas_rect.height, 200)
            self.assertEqual(scroll_content_rect.height, 20)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
