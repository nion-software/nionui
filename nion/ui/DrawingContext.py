"""
    DrawingContext module contains classes related to drawing context.

    DrawingContexts are able to be handled directly by the UI system or
    produce javascript or svg to do the drawing.
"""
from __future__ import annotations

# standard libraries
import base64
import collections
import contextlib
import copy
import enum
import io
import logging
import math
import re
import struct
import sys
import threading
import time
import typing
import xml.sax.saxutils

# third party libraries
import imageio.v3 as imageio
import numpy

# local libraries
from nion.utils import Color
from nion.utils import Geometry


# pylint: disable=star-args


RGBA32Type = typing.Any
RGBA8Type = typing.Any
GrayscaleF32Type = typing.Any
C8Type = typing.Any

ByteOrderType = typing.Optional[typing.Union[typing.Literal["little"], typing.Literal["big"]]]


def get_rgba_view_from_rgba_data(rgba_data: RGBA32Type) -> RGBA8Type:
    return rgba_data.view(numpy.uint8).reshape(rgba_data.shape + (4,))


def get_rgba_data_from_rgba(rgba_image: RGBA8Type) -> RGBA32Type:
    return rgba_image.view(numpy.uint32).reshape(rgba_image.shape[:-1])


def get_byte_view(rgba_image: RGBA32Type) -> RGBA8Type:
    return rgba_image.view(numpy.uint8).reshape(rgba_image.shape + (-1, ))


def get_red_view(rgba_image: RGBA32Type, byteorder: ByteOrderType = None) -> C8Type:
    if byteorder is None:
        byteorder = typing.cast(ByteOrderType, sys.byteorder)
    bytes = get_byte_view(rgba_image)
    assert bytes.shape[-1] == 4
    if byteorder == 'little':
        return typing.cast(C8Type, bytes[..., 2])  # strip A off BGRA
    else:
        return typing.cast(C8Type, bytes[..., 1])  # strip A off ARGB


def get_green_view(rgba_image: RGBA32Type, byteorder: ByteOrderType = None) -> C8Type:
    if byteorder is None:
        byteorder = typing.cast(ByteOrderType, sys.byteorder)
    bytes = get_byte_view(rgba_image)
    assert bytes.shape[-1] == 4
    if byteorder == 'little':
        return typing.cast(C8Type, bytes[..., 1])  # strip A off BGRA
    else:
        return typing.cast(C8Type, bytes[..., 2])  # strip A off ARGB


def get_blue_view(rgba_image: RGBA32Type, byteorder: ByteOrderType = None) -> C8Type:
    if byteorder is None:
        byteorder = typing.cast(ByteOrderType, sys.byteorder)
    bytes = get_byte_view(rgba_image)
    assert bytes.shape[-1] == 4
    if byteorder == 'little':
        return typing.cast(C8Type, bytes[..., 0])  # strip A off BGRA
    else:
        return typing.cast(C8Type, bytes[..., 3])  # strip A off ARGB


def get_alpha_view(rgba_image: RGBA32Type, byteorder: ByteOrderType = None) -> C8Type:
    if byteorder is None:
        byteorder = typing.cast(ByteOrderType, sys.byteorder)
    bytes = get_byte_view(rgba_image)
    assert bytes.shape[-1] == 4
    if byteorder == 'little':
        return typing.cast(C8Type, bytes[..., 3])  # A of BGRA
    else:
        return typing.cast(C8Type, bytes[..., 0])  # A of ARGB


class DrawingContext:
    """
        Path commands (begin_path, close_path, move_to, line_to, etc.) should not be intermixed
        with transform commands (translate, scale, rotate).
    """

    # TODO: stroke_fill
    # TODO: circle

    __image_id = 0
    __image_id_lock = threading.RLock()

    def __init__(self) -> None:
        self.commands: typing.List[typing.Sequence[typing.Any]] = []
        self.binary_commands = bytearray()
        self.save_count = 0
        self.images: typing.Dict[str, RGBA32Type] = dict()

    def copy_from(self, drawing_context: DrawingContext) -> None:
        assert self.save_count == 0
        assert drawing_context.save_count == 0
        self.commands = drawing_context.commands
        self.binary_commands = drawing_context.binary_commands
        self.images = drawing_context.images

    def add(self, drawing_context: DrawingContext) -> None:
        self.commands.extend(drawing_context.commands)
        self.binary_commands.extend(drawing_context.binary_commands)
        self.images.update(drawing_context.images)

    def clear(self) -> None:
        self.commands = []
        self.binary_commands = bytearray()
        self.save_count = 0
        self.images = dict()

    def to_js(self) -> str:
        js = ""
        for command in self.commands:
            command_id = command[0]
            command_args = command[1:]
            if command_id == "save":
                js += "ctx.save();"
            elif command_id == "restore":
                js += "ctx.restore();"
            elif command_id == "beginPath":
                js += "ctx.beginPath();"
            elif command_id == "closePath":
                js += "ctx.closePath();"
            elif command_id == "clip":
                js += "ctx.beginPath();"
                js += "ctx.rect({0}, {1}, {2}, {3});".format(*command_args)
                js += "ctx.clip();"
            elif command_id == "translate":
                js += "ctx.translate({0}, {1});".format(*command_args)
            elif command_id == "scale":
                js += "ctx.scale({0}, {1});".format(*command_args)
            elif command_id == "rotate":
                js += "ctx.rotate({0});".format(*command_args)
            elif command_id == "moveTo":
                js += "ctx.moveTo({0}, {1});".format(*command_args)
            elif command_id == "lineTo":
                js += "ctx.lineTo({0}, {1});".format(*command_args)
            elif command_id == "rect":
                js += "ctx.rect({0}, {1}, {2}, {3});".format(*command_args)
            elif command_id == "arc":
                x, y, r, sa, ea, ac = command_args
                js += "ctx.arc({0}, {1}, {2}, {3}, {4}, {5});".format(x, y, r, sa, ea, "true" if ac else "false")
            elif command_id == "arcTo":
                x1, y1, x2, y2, r = command_args
                js += "ctx.arcTo({0}, {1}, {2}, {3}, {4});".format(x1, y1, x2, y2, r)
            elif command_id == "cubicTo":
                x1, y1, x2, y2, x, y = command_args
                js += "ctx.bezierCurveTo({0}, {1}, {2}, {3}, {4}, {5});".format(x1, y1, x2, y2, x, y)
            elif command_id == "quadraticTo":
                x1, y1, x, y = command_args
                js += "ctx.quadraticCurveTo({0}, {1}, {2}, {3});".format(x1, y1, x, y)
            elif command_id == "image":
                w, h, image, image_id, a, b, c, d = command_args
                js += "ctx.rect({0}, {1}, {2}, {3});".format(a, b, c, d)
            elif command_id == "data":
                w, h, data, data_id, a, b, c, d, low, high, color_table = command_args
                js += "ctx.rect({0}, {1}, {2}, {3});".format(a, b, c, d)
            elif command_id == "stroke":
                js += "ctx.stroke();"
            elif command_id == "sleep":
                pass  # used for performance testing
            elif command_id == "fill":
                js += "ctx.fill();"
            elif command_id == "fillText":
                text, x, y, max_width = command_args
                js += "ctx.fillText('{0}', {1}, {2}{3});".format(xml.sax.saxutils.escape(text), x, y, ", {0}".format(max_width) if max_width else "")
            elif command_id == "fillStyleGradient":
                command_var = command_args[0]
                js += "ctx.fillStyle = {0};".format("grad" + str(command_var))
            elif command_id == "fillStyle":
                js += "ctx.fillStyle = '{0}';".format(*command_args)
            elif command_id == "font":
                js += "ctx.font = '{0}';".format(*command_args)
            elif command_id == "textAlign":
                js += "ctx.textAlign = '{0}';".format(*command_args)
            elif command_id == "textBaseline":
                js += "ctx.textBaseline = '{0}';".format(*command_args)
            elif command_id == "strokeStyle":
                js += "ctx.strokeStyle = '{0}';".format(*command_args)
            elif command_id == "lineWidth":
                js += "ctx.lineWidth = {0};".format(*command_args)
            elif command_id == "lineDash":
                js += "ctx.lineDash = {0};".format(*command_args)
            elif command_id == "lineCap":
                js += "ctx.lineCap = '{0}';".format(*command_args)
            elif command_id == "lineJoin":
                js += "ctx.lineJoin = '{0}';".format(*command_args)
            elif command_id == "gradient":
                command_var, width, height, x1, y1, x2, y2 = command_args  # pylint: disable=invalid-name
                js_var = "grad" + str(command_var)
                js += "var {0} = ctx.createLinearGradient({1}, {2}, {3}, {4});".format(js_var, x1, y1, x2 - x1, y2 - y1)
            elif command_id == "colorStop":
                command_var, x, color = command_args
                js_var = "grad" + str(command_var)
                js += "{0}.addColorStop({1}, '{2}');".format(js_var, x, color)
        return js

    def to_svg(self, size: Geometry.IntSize, viewbox: Geometry.IntRect) -> str:
        svg = ""
        defs = ""
        path = ""
        next_clip_id = 1
        transform: typing.List[str] = list()
        closers: typing.List[str] = list()
        fill_style: typing.Optional[str] = None
        fill_opacity = 1.0
        stroke_style: typing.Optional[str] = None
        stroke_opacity = 1.0
        line_cap = "square"
        line_join = "bevel"
        line_width = 1.0
        line_dash: typing.Optional[int] = None
        text_anchor = "start"
        text_baseline = "alphabetic"
        font_style: typing.Optional[str] = None
        font_weight: typing.Optional[str] = None
        font_size: typing.Optional[int] = None
        font_unit: typing.Optional[str] = None
        font_family: typing.Optional[str] = None
        # Python 3.9+: collections.deque[typing.Dict[str, typing.Any]]
        contexts: typing.Any = collections.deque()
        gradient_start: typing.Optional[str] = None
        gradient_stops: typing.List[str] = list()

        # make a SVG 1.1 compatible color, opacity tuple
        def parse_color(color_str: str) -> typing.Tuple[str, float]:
            color_str = ''.join(color_str.split())
            if color_str.startswith("rgba"):
                c = re.split("rgba\((\d+),(\d+),(\d+),([\d.]+)\)", color_str)
                return f"rgb({c[1]}, {c[2]}, {c[3]})", float(c[4])
            return color_str, 1.0

        for command in self.commands:
            command_id = command[0]
            #logging.debug(command_id)
            command_args = command[1:]
            if command_id == "save":
                context: typing.Dict[str, typing.Any] = dict()
                context["path"] = path
                context["transform"] = copy.deepcopy(transform)
                context["fill_style"] = fill_style
                context["fill_opacity"] = fill_opacity
                context["stroke_style"] = stroke_style
                context["stroke_opacity"] = stroke_opacity
                context["line_cap"] = line_cap
                context["line_join"] = line_join
                context["line_width"] = line_width
                context["line_dash"] = line_dash
                context["font_style"] = font_style
                context["font_weight"] = font_weight
                context["font_size"] = font_size
                context["font_unit"] = font_unit
                context["font_family"] = font_family
                context["text_anchor"] = text_anchor
                context["text_baseline"] = text_baseline
                context["closers"] = copy.deepcopy(closers)
                closers = list()
                contexts.append(context)
            elif command_id == "restore":
                svg += "".join(closers)
                context = contexts.pop()
                path = context["path"]
                transform = context["transform"]
                fill_style = context["fill_style"]
                fill_opacity = context["fill_opacity"]
                font_style = context["font_style"]
                font_weight = context["font_weight"]
                font_size = context["font_size"]
                font_unit = context["font_unit"]
                font_family = context["font_family"]
                text_anchor = context["text_anchor"]
                text_baseline = context["text_baseline"]
                stroke_style = context["stroke_style"]
                stroke_opacity = context["stroke_opacity"]
                line_cap = context["line_cap"]
                line_join = context["line_join"]
                line_width = context["line_width"]
                line_dash = context["line_dash"]
                closers = context["closers"]
            elif command_id == "beginPath":
                path = ""
            elif command_id == "closePath":
                path += " Z"
            elif command_id == "moveTo":
                path += " M {0} {1}".format(*command_args)
            elif command_id == "lineTo":
                path += " L {0} {1}".format(*command_args)
            elif command_id == "rect":
                x, y, w, h = command_args
                path += " M {0} {1}".format(x, y)
                path += " L {0} {1}".format(x + w, y)
                path += " L {0} {1}".format(x + w, y + h)
                path += " L {0} {1}".format(x, y + h)
                path += " Z"
            elif command_id == "arc":
                x, y, r, sa, ea, ac = command_args
                # js += "ctx.arc({0}, {1}, {2}, {3}, {4}, {5});".format(x, y, r, sa, ea, "true" if ac else "false")
            elif command_id == "arcTo":
                x1, y1, x2, y2, r = command_args
                # js += "ctx.arcTo({0}, {1}, {2}, {3}, {4});".format(x1, y1, x2, y2, r)
            elif command_id == "cubicTo":
                path += " C {0} {1}, {2} {3}, {4} {5}".format(*command_args)
            elif command_id == "quadraticTo":
                path += " Q {0} {1}, {2} {3}".format(*command_args)
            elif command_id == "clip":
                x, y, w, h = command_args
                clip_id = "clip" + str(next_clip_id)
                next_clip_id += 1
                transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                defs_format_str = "<clipPath id='{0}'><rect x='{1}' y='{2}' width='{3}' height='{4}'{5} /></clipPath>"
                defs += defs_format_str.format(clip_id, x, y, w, h, transform_str)
                svg += "<g style='clip-path: url(#{0});'>".format(clip_id)
                closers.append("</g>")
            elif command_id == "translate":
                transform.append("translate({0},{1})".format(*command_args))
            elif command_id == "scale":
                transform.append("scale({0},{1})".format(*command_args))
            elif command_id == "rotate":
                transform.append("rotate({0})".format(*command_args))
            elif command_id == "image":
                w, h, image, image_id, a, b, c, d = command_args
                png_file = io.BytesIO()
                rgba_data = get_rgba_view_from_rgba_data(image)
                # image compression is time consuming. pass parameters to make this step as fast as possible.
                # see nionswift-642.
                # TODO: fix typing when imageio gets their numpy typing correct.
                imageio.imwrite(png_file, rgba_data[..., (2, 1, 0, 3)], extension=".png", optimize=False, compress_level=1)  # type: ignore
                png_encoded = base64.b64encode(png_file.getvalue()).decode('utf=8')
                transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                svg_format_str = "<image x='{0}' y='{1}' width='{2}' height='{3}' xlink:href='data:image/png;base64,{4}'{5} />"
                svg += svg_format_str.format(a, b, c, d, png_encoded, transform_str)
            elif command_id == "data":
                w, h, data, data_id, a, b, c, d, low, high, color_table, color_table_image_id = command_args
                m = 255.0 / (high - low) if high != low else 1
                image = numpy.empty(data.shape, numpy.uint32)
                if color_table is not None:
                    adj_color_table: numpy.typing.NDArray[numpy.uint32] = numpy.empty(color_table.shape, numpy.uint32)
                    # ordering of color_table is BGRA
                    # ordering of adj_color_table is RGBA
                    get_byte_view(adj_color_table)[:, 0] = get_byte_view(color_table)[:, 2]
                    get_byte_view(adj_color_table)[:, 1] = get_byte_view(color_table)[:, 1]
                    get_byte_view(adj_color_table)[:, 2] = get_byte_view(color_table)[:, 0]
                    get_byte_view(adj_color_table)[:, 3] = get_byte_view(color_table)[:, 3]
                    clipped_array = numpy.clip((m * (data - low)).astype(int), 0, 255).astype(numpy.uint8)
                    image[:] = adj_color_table[clipped_array]
                else:
                    clipped_array = numpy.clip(data, low, high)
                    numpy.subtract(clipped_array, low, out=clipped_array)
                    numpy.multiply(clipped_array, m, out=clipped_array)
                    get_red_view(image)[:] = clipped_array
                    get_green_view(image)[:] = clipped_array
                    get_blue_view(image)[:] = clipped_array
                    get_alpha_view(image)[:] = 255
                png_file = io.BytesIO()
                # image compression is time consuming. pass parameters to make this step as fast as possible.
                # see nionswift-642.
                # TODO: fix typing when imageio gets their numpy typing correct.
                imageio.imwrite(png_file, get_rgba_view_from_rgba_data(image), extension=".png", optimize=False, compress_level=1)  # type: ignore
                png_encoded = base64.b64encode(png_file.getvalue()).decode('utf=8')
                transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                svg_format_str = "<image x='{0}' y='{1}' width='{2}' height='{3}' xlink:href='data:image/png;base64,{4}'{5} />"
                svg += svg_format_str.format(a, b, c, d, png_encoded, transform_str)
            elif command_id == "stroke":
                if stroke_style is not None:
                    transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                    dash_str = " stroke-dasharray='{0}, {1}'".format(line_dash, line_dash) if line_dash else ""
                    svg += f"<path d='{path}' fill='none' stroke='{stroke_style}' stroke-opacity='{stroke_opacity}' stroke-width='{line_width}' stroke-linejoin='{line_join}' stroke-linecap='{line_cap}'{dash_str}{transform_str} />"
            elif command_id == "sleep":
                pass  # used for performance testing
            elif command_id == "fill":
                if fill_style is not None:
                    transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                    svg += f"<path d='{path}' fill='{fill_style}' fill-opacity='{fill_opacity}' stroke='none'{transform_str} />"
            elif command_id == "fillText":
                text, x, y, max_width = command_args
                transform_str = " transform='{0}'".format(" ".join(transform)) if len(transform) > 0 else ""
                font_str = ""
                if font_style:
                    font_str += " font-style='{0}'".format(font_style)
                if font_weight:
                    font_str += " font-weight='{0}'".format(font_weight)
                if font_size:
                    font_str += " font-size='{0}{1}'".format(font_size, font_unit)
                if font_family:
                    font_str += " font-family='{0}'".format(font_family)
                if fill_style:
                    font_str += " fill='{0}'".format(fill_style)
                if fill_opacity < 1.0:
                    font_str += " fill-opacity='{0}'".format(fill_opacity)
                svg_format_str = "<text x='{0}' y='{1}' text-anchor='{3}' alignment-baseline='{4}'{5}{6}>{2}</text>"
                svg += svg_format_str.format(x, y, xml.sax.saxutils.escape(text), text_anchor, text_baseline, font_str,
                                             transform_str)
            elif command_id == "fillStyleGradient":
                command_var = command_args[0]
                assert gradient_start is not None
                defs += gradient_start + "".join(gradient_stops) + "</linearGradient>"
                fill_style = "url(#{0})".format("grad" + str(command_var))
            elif command_id == "fillStyle":
                fill_style, fill_opacity = parse_color(command_args[0])
            elif command_id == "font":
                font_style = None
                font_weight = None
                font_size = None
                font_unit = None
                font_family = None
                for font_part in [s for s in command_args[0].split(" ") if s]:
                    if font_part == "italic":
                        font_style = "italic"
                    elif font_part == "bold":
                        font_weight = "bold"
                    elif font_part.endswith("px") and int(font_part[0:-2]) > 0:
                        font_size = int(font_part[0:-2])
                        font_unit = "px"
                    elif font_part.endswith("pt") and int(font_part[0:-2]) > 0:
                        font_size = int(font_part[0:-2])
                        font_unit = "pt"
                    else:
                        font_family = font_part
            elif command_id == "textAlign":
                text_anchors = {"start": "start", "end": "end", "left": "start", "center": "middle", "right": "end"}
                text_anchor = text_anchors.get(command_args[0], "start")
            elif command_id == "textBaseline":
                text_baselines = {"top": "hanging", "hanging": "hanging", "middle": "middle",
                                  "alphabetic": "alphabetic", "ideaographic": "ideaographic", "bottom": "bottom"}
                text_baseline = text_baselines.get(command_args[0], "alphabetic")
            elif command_id == "strokeStyle":
                stroke_style, stroke_opacity = parse_color(command_args[0])
            elif command_id == "lineWidth":
                line_width = command_args[0]
            elif command_id == "lineDash":
                line_dash = command_args[0]
            elif command_id == "lineCap":
                line_caps = {"square": "square", "round": "round", "butt": "butt"}
                line_cap = line_caps.get(command_args[0], "square")
            elif command_id == "lineJoin":
                line_joins = {"round": "round", "miter": "miter", "bevel": "bevel"}
                line_join = line_joins.get(command_args[0], "bevel")
            elif command_id == "gradient":
                # assumes that gradient will be used immediately after being
                # declared and stops being defined. this is currently enforced by
                # the way the commands are generated in drawing context.
                command_var, w, h, x1, y1, x2, y2 = command_args
                grad_id = "grad" + str(command_var)
                gradient_start = "<linearGradient id='{0}' x1='{1}' y1='{2}' x2='{3}' y2='{4}'>".format(grad_id,
                                                                                                        float(x1 / w),
                                                                                                        float(y1 / h),
                                                                                                        float(x2 / w),
                                                                                                        float(y2 / h))
            elif command_id == "colorStop":
                command_var, x, color = command_args
                gradient_stops.append("<stop offset='{0}%' stop-color='{1}' />".format(int(x * 100), color))
            else:
                logging.debug("Unknown command %s", command)
        xmlns = "xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'"
        viewbox_str = "{0} {1} {2} {3}".format(viewbox.left, viewbox.top, viewbox.width, viewbox.height)
        result = "<svg version='1.1' baseProfile='full' width='{0}' height='{1}' viewBox='{2}' {3}>".format(size.width,
                                                                                                            size.height,
                                                                                                            viewbox_str,
                                                                                                            xmlns)
        result += "<defs>" + defs + "</defs>"
        result += svg
        result += "</svg>"
        return result

    @contextlib.contextmanager
    def saver(self) -> typing.Iterator[typing.Any]:
        self.save()
        try:
            yield
        finally:
           self.restore()

    def save(self) -> None:
        self.commands.append(("save", ))
        self.binary_commands.extend(b"save")
        self.save_count += 1

    def restore(self) -> None:
        self.commands.append(("restore", ))
        self.binary_commands.extend(b"rest")
        self.save_count -= 1

    def begin_layer(self, layer_id: int, layer_seed: int, a: float, b: float, c: float, d: float) -> None:
        self.commands.append(("begin_layer", int(layer_id), int(layer_seed), float(a), float(b), float(c), float(d)))
        self.binary_commands.extend(struct.pack("4siiffff", b"bgly", int(layer_id), int(layer_seed), float(a), float(b), float(c), float(d)))

    def end_layer(self, layer_id: int, layer_seed: int, a: float, b: float, c: float, d: float) -> None:
        self.commands.append(("end_layer", int(layer_id), int(layer_seed), float(a), float(b), float(c), float(d)))
        self.binary_commands.extend(struct.pack("4siiffff", b"enly", int(layer_id), int(layer_seed), float(a), float(b), float(c), float(d)))

    def begin_path(self) -> None:
        self.commands.append(("beginPath", ))
        self.binary_commands.extend(b"bpth")

    def close_path(self) -> None:
        self.commands.append(("closePath", ))
        self.binary_commands.extend(b"cpth")

    def add_path(self, path: Path) -> None:
        path.add_commands(self)

    def clip_rect(self, a: float, b: float, c: float, d: float) -> None:
        self.commands.append(("clip", float(a), float(b), float(c), float(d)))
        self.binary_commands.extend(struct.pack("4sffff", b"clip", float(a), float(b), float(c), float(d)))

    def translate(self, x: float, y: float) -> None:
        self.commands.append(("translate", float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sff", b"tran", float(x), float(y)))

    def scale(self, x: float, y: float) -> None:
        self.commands.append(("scale", float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sff", b"scal", float(x), float(y)))

    def rotate(self, radians: float) -> None:
        self.commands.append(("rotate", math.degrees(float(radians))))
        self.binary_commands.extend(struct.pack("4sf", b"rota", math.degrees(float(radians))))

    def move_to(self, x: float, y: float) -> None:
        self.commands.append(("moveTo", float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sff", b"move", float(x), float(y)))

    def line_to(self, x: float, y: float) -> None:
        self.commands.append(("lineTo", float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sff", b"line", float(x), float(y)))

    # optimization; use with care.
    def _line_to_multi(self, line_commands: typing.Sequence[typing.Tuple[float, float]]) -> None:
        for x, y in line_commands:
            self.commands.append(("lineTo", x, y))
            self.binary_commands.extend(struct.pack("4sff", b"line", x, y))

    def rect(self, l: float, t: float, w: float, h: float) -> None:
        self.commands.append(("rect", float(l), float(t), float(w), float(h)))
        self.binary_commands.extend(struct.pack("4sffff", b"rect", float(l), float(t), float(w), float(h)))

    def round_rect(self, x: float, y: float, w: float, h: float, r: float) -> None:
        self.move_to(x + r, y)
        self.arc_to(x + w, y, x + w, y + r, r)
        self.arc_to(x + w, y + h, x + w - r, y + h, r)
        self.arc_to(x, y + h, x, y + h - r, r)
        self.arc_to(x, y, x + r, y, r)
        self.close_path()

    def arc(self, x: float, y: float, r: float, sa: float, ea: float, ac: bool = False) -> None:
        self.commands.append(("arc", float(x), float(y), float(r), float(sa), float(ea), bool(ac)))
        self.binary_commands.extend(struct.pack("4sfffffi", b"arc ", float(x), float(y), float(r), float(sa), float(ea), bool(ac)))

    def arc_to(self, x1: float, y1: float, x2: float, y2: float, r: float) -> None:
        self.commands.append(("arcTo", float(x1), float(y1), float(x2), float(y2), float(r)))
        self.binary_commands.extend(struct.pack("4sfffff", b"arct", float(x1), float(y1), float(x2), float(y2), float(r)))

    def bezier_curve_to(self, x1: float, y1: float, x2: float, y2: float, x: float, y: float) -> None:
        self.commands.append(("cubicTo", float(x1), float(y1), float(x2), float(y2), float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sffffff", b"cubc", float(x1), float(y1), float(x2), float(y2), float(x), float(y)))

    def quadratic_curve_to(self, x1: float, y1: float, x: float, y: float) -> None:
        self.commands.append(("quadraticTo", float(x1), float(y1), float(x), float(y)))
        self.binary_commands.extend(struct.pack("4sffff", b"quad", float(x1), float(y1), float(x), float(y)))

    def draw_image(self, img: RGBA32Type, x: float, y: float, width: float, height: float) -> None:
        # img should be rgba pack, uint32
        assert img.dtype == numpy.uint32
        with DrawingContext.__image_id_lock:
            DrawingContext.__image_id += 1
            image_id = DrawingContext.__image_id
        self.commands.append(
            ("image", img.shape[1], img.shape[0], img, int(image_id), float(x), float(y), float(width), float(height)))
        self.images[str(image_id)] = img
        self.binary_commands.extend(struct.pack("4siiiffff", b"imag", img.shape[1], img.shape[0], int(image_id), float(x), float(y), float(width), float(height)))

    def draw_data(self, img: GrayscaleF32Type, x: float, y: float, width: float, height: float, low: float, high: float, color_map_data: typing.Optional[RGBA32Type]) -> None:
        # img should be float
        assert img.dtype == numpy.float32
        with DrawingContext.__image_id_lock:
            DrawingContext.__image_id += 1
            image_id = DrawingContext.__image_id
            if color_map_data is not None:
                DrawingContext.__image_id += 1
                color_map_image_id = DrawingContext.__image_id
            else:
                color_map_image_id = 0
        self.images[str(image_id)] = img
        if color_map_data is not None:
            self.images[str(color_map_image_id)] = color_map_data
        self.commands.append(
            ("data", img.shape[1], img.shape[0], img, int(image_id), float(x), float(y), float(width), float(height),
             float(low), float(high), color_map_data, int(color_map_image_id)))
        self.binary_commands.extend(
            struct.pack("4siiiffffffi", b"data", img.shape[1], img.shape[0], int(image_id), float(x), float(y),
                        float(width), float(height), float(low), float(high), int(color_map_image_id)))

    def stroke(self) -> None:
        self.commands.append(("stroke", ))
        self.binary_commands.extend(b"strk")

    def sleep(self, duration: float) -> None:
        self.commands.append(("sleep", float(duration)))
        self.binary_commands.extend(struct.pack("4sf", b"slep", float(duration)))

    def mark_latency(self) -> None:
        self.commands.append(("latency", time.perf_counter()))
        self.binary_commands.extend(struct.pack("<4sd", b"latn", time.perf_counter()))

    def message(self, text: str) -> None:
        self.commands.append(("message", text))
        text_encoded = text.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(text_encoded)), b"mesg", len(text_encoded), text_encoded))

    def timestamp(self, timestamp: str) -> None:
        self.commands.append(("timestamp", timestamp))
        timestamp_encoded = timestamp.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(timestamp_encoded)), b"time", len(timestamp_encoded), timestamp_encoded))

    def fill(self) -> None:
        self.commands.append(("fill", ))
        self.binary_commands.extend(b"fill")

    def fill_text(self, text: str, x: float, y: float, max_width: typing.Optional[int] = None) -> None:
        text = str(text) if text is not None else str()
        self.commands.append(("fillText", text, float(x), float(y), float(max_width) if max_width else 0))
        text_encoded = text.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}sfff".format(len(text_encoded)), b"text", len(text_encoded), text_encoded, float(x), float(y), float(max_width) if max_width else 0))

    @property
    def fill_style(self) -> typing.Optional[typing.Union[str, LinearGradient]]:
        raise NotImplementedError()

    @fill_style.setter
    def fill_style(self, a: typing.Optional[typing.Union[str, LinearGradient]]) -> None:
        a = a or "rgba(0, 0, 0, 0.0)"
        if isinstance(a, DrawingContext.LinearGradient):
            self.commands.extend(a.commands)
            self.commands.append(("fillStyleGradient", int(a.command_var)))
            self.binary_commands.extend(a.binary_commands)
            self.binary_commands.extend(struct.pack("4si", b"flsg", int(a.command_var)))
        else:
            self.commands.append(("fillStyle", str(a)))
            a_encoded = a.encode("utf-8")
            self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"flst", len(a_encoded), a_encoded))

    @property
    def font(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @font.setter
    def font(self, a: typing.Optional[str]) -> None:
        """
            Set the text font.

            Supports 'normal', 'bold', 'italic', size specific as '14px', and font-family.
        """
        assert a is not None
        self.commands.append(("font", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"font", len(a_encoded), a_encoded))

    @property
    def text_align(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @text_align.setter
    def text_align(self, a: typing.Optional[str]) -> None:
        """Set text alignment.

        Valid values are 'start', 'end', 'left', 'center', 'right'. Default is 'start'.

        Default is 'start'.
        """
        assert a is not None
        self.commands.append(("textAlign", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"algn", len(a_encoded), a_encoded))

    @property
    def text_baseline(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @text_baseline.setter
    def text_baseline(self, a: typing.Optional[str]) -> None:
        """Set the text baseline.

        Valid values are 'top', 'hanging', 'middle', 'alphabetic', 'ideographic', and 'bottom'.

        Default is 'alphabetic'.
        """
        assert a is not None
        self.commands.append(("textBaseline", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"tbas", len(a_encoded), a_encoded))

    @property
    def stroke_style(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @stroke_style.setter
    def stroke_style(self, a: typing.Optional[str]) -> None:
        a = a or "rgba(0, 0, 0, 0.0)"
        self.commands.append(("strokeStyle", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"stst", len(a_encoded), a_encoded))

    @property
    def line_width(self) -> float:
        raise NotImplementedError()

    @line_width.setter
    def line_width(self, a: float) -> None:
        self.commands.append(("lineWidth", float(a)))
        self.binary_commands.extend(struct.pack("4sf", b"linw", float(a)))

    @property
    def line_dash(self) -> typing.Optional[int]:
        raise NotImplementedError()

    @line_dash.setter
    def line_dash(self, a: typing.Optional[int]) -> None:
        """Set the line dash. Takes a single value with the length of the dash."""
        assert a is not None
        self.commands.append(("lineDash", float(a)))
        self.binary_commands.extend(struct.pack("4sf", b"ldsh", float(a)))

    @property
    def line_cap(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @line_cap.setter
    def line_cap(self, a: typing.Optional[str]) -> None:
        """Set the line join. Valid values are 'square', 'round', 'butt'. Default is 'square'."""
        assert a is not None
        self.commands.append(("lineCap", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"lcap", len(a_encoded), a_encoded))

    @property
    def line_join(self) -> typing.Optional[str]:
        raise NotImplementedError()

    @line_join.setter
    def line_join(self, a: typing.Optional[str]) -> None:
        """Set the line join. Valid values are 'round', 'miter', 'bevel'. Default is 'bevel'."""
        assert a is not None
        self.commands.append(("lineJoin", str(a)))
        a_encoded = a.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(a_encoded)), b"lnjn", len(a_encoded), a_encoded))

    class LinearGradient:
        next = 1

        def __init__(self, width: float, height: float, x1: float, y1: float, x2: float, y2: float) -> None:
            self.commands: typing.List[typing.Sequence[typing.Any]] = []
            self.binary_commands = bytearray()
            self.command_var = DrawingContext.LinearGradient.next
            self.commands.append(("gradient", self.command_var, float(width), float(height), float(x1), float(y1), float(x2), float(y2)))
            self.binary_commands.extend(struct.pack("4siffffff", b"grad", self.command_var, float(width), float(height), float(x1), float(y1), float(x2), float(y2)))
            DrawingContext.LinearGradient.next += 1

        def add_color_stop(self, x: float, color: str) -> None:
            self.commands.append(("colorStop", self.command_var, float(x), str(color)))
            color_encoded = color.encode("utf-8")
            self.binary_commands.extend(struct.pack("4sifi{}s0i".format(len(color_encoded)), b"grcs", self.command_var, float(x), len(color_encoded), color_encoded))

    def create_linear_gradient(self, width: float, height: float, x1: float, y1: float, x2: float, y2: float) -> DrawingContext.LinearGradient:
        gradient = DrawingContext.LinearGradient(width, height, x1, y1, x2, y2)
        return gradient

    def statistics(self, stat_id: str) -> None:
        self.commands.append(("statistics", str(stat_id)))
        stat_id_encoded = stat_id.encode("utf-8")
        self.binary_commands.extend(struct.pack("4si{}s0i".format(len(stat_id_encoded)), b"stat", len(stat_id_encoded), stat_id_encoded))


class Path:
    def __init__(self) -> None:
        self.__path = DrawingContext()

    def __deepcopy__(self, memo: typing.Dict[typing.Any, typing.Any]) -> Path:
        path = Path()
        path.__path = copy.deepcopy(self.__path)
        return path

    def add_commands(self, drawing_context: DrawingContext) -> None:
        drawing_context.add(self.__path)

    def move_to(self, x: float, y: float) -> None:
        self.__path.move_to(x, y)

    def line_to(self, x: float, y: float) -> None:
        self.__path.line_to(x, y)

    def close_path(self) -> None:
        self.__path.close_path()


def color_without_alpha(color: typing.Optional[str]) -> typing.Optional[str]:
    return Color.Color(color).to_color_without_alpha().color_str


def named_color_without_alpha(color: str) -> typing.Optional[str]:
    return Color.Color(color).to_named_color_without_alpha().color_str


def hex_color(color: typing.Union[str, Color.Color]) -> typing.Optional[str]:
    return Color.Color(color).hex_color_str
