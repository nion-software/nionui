# standard libraries
import typing
import unittest

# third party libraries
import numpy

# local libraries
from nion.ui import DrawingContext
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
