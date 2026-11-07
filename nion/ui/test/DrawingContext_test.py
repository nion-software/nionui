# standard libraries
import typing
import unittest

# third party libraries
import numpy

# local libraries
from nion.ui import DrawingContext
from nion.utils import Color
from nion.utils import Geometry


class TestImageClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_draw_data_with_color_table(self) -> None:
        dc = DrawingContext.DrawingContext()
        data: numpy.typing.NDArray[numpy.float32] = numpy.zeros((4, 4), numpy.float32)
        color_map_data: numpy.typing.NDArray[numpy.uint32] = numpy.zeros((256, ), numpy.uint32)
        color_map_data[:] = 0xFF010203
        dc.draw_data(data, 0, 0, 4, 4, 0, 1, color_map_data)
        dc.to_svg(Geometry.IntSize(4, 4), Geometry.IntRect.from_tlbr(0, 0, 4, 4))

    def test_hex_color_with_alpha_is_drawn_as_rgba_with_the_same_alpha_when_truncated(self) -> None:
        # a host reads rgba() as CSS does, and may truncate its alpha times 255.
        for color_str, alpha_255 in (("#ff000080", 128), ("#f008", 136), ("#00ff0001", 1), ("#0000ff00", 0), ("#ffffffff", 255)):
            with self.subTest(color_str=color_str):
                rgba_color_str = DrawingContext._get_rgba_color_str(color_str)
                red, green, blue, alpha = Color.Color(rgba_color_str).to_rgba()
                self.assertEqual(Color.Color(color_str).to_rgb_255(), (red, green, blue))
                self.assertEqual(alpha_255, int(alpha * 255))
        self.assertEqual("#ff0000", DrawingContext._get_rgba_color_str("#ff0000"))
