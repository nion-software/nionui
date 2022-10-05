from __future__ import annotations

# standard libraries
import typing

# third party libraries
import numpy

# local libraries
from nion.ui import DrawingContext
from nion.utils import Geometry


class Bitmap:
    def __init__(self, *, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type] = None, shape: typing.Optional[Geometry.IntSize] = None) -> None:
        self.__rgba_bitmap_data = rgba_bitmap_data
        self.__shape = shape

    @property
    def rgba_bitmap_data(self) -> typing.Optional[DrawingContext.RGBA32Type]:
        return self.__rgba_bitmap_data

    @rgba_bitmap_data.setter
    def rgba_bitmap_data(self, rgba_bitmap_data: typing.Optional[DrawingContext.RGBA32Type]) -> None:
        self.__rgba_bitmap_data = rgba_bitmap_data

    @property
    def shape(self) -> typing.Optional[Geometry.IntSize]:
        return self.__shape

    @shape.setter
    def shape(self, shape: typing.Optional[Geometry.IntSize]) -> None:
        self.__shape = shape

    @property
    def computed_shape(self) -> Geometry.IntSize:
        return self.__shape if self.__shape else (Geometry.IntSize.make(typing.cast(Geometry.IntSizeTuple, self.__rgba_bitmap_data.shape)) if self.__rgba_bitmap_data is not None else Geometry.IntSize())


def promote_bitmap(bitmap_or_array: typing.Optional[BitmapOrArray]) -> typing.Optional[Bitmap]:
    if isinstance(bitmap_or_array, Bitmap):
        return bitmap_or_array
    if isinstance(bitmap_or_array, numpy.ndarray) and len(bitmap_or_array.shape) == 2 and bitmap_or_array.dtype == numpy.uint32:
        return Bitmap(rgba_bitmap_data=bitmap_or_array)
    return None


BitmapOrArray = typing.Union[Bitmap, DrawingContext.RGBA32Type]


def bitmap_or_array_equal(b1: typing.Any, b2: typing.Any) -> bool:
    bitmap1 = promote_bitmap(b1)
    bitmap2 = promote_bitmap(b2)
    if not bitmap1 and not bitmap2:
        return True
    if bitmap1 and bitmap2 and bitmap1.rgba_bitmap_data is not None and bitmap2.rgba_bitmap_data is not None:
        return numpy.array_equal(bitmap1.rgba_bitmap_data, bitmap2.rgba_bitmap_data)
    return False
