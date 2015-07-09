import logging
import math

import numpy
import scipy.misc

from nion.ui import DrawingContext
from nion.ui import Geometry


logging.getLogger().setLevel(logging.DEBUG)

dc = DrawingContext.DrawingContext()

dc.save()
dc.begin_path()
dc.rect(20, 20, 30, 40)
dc.stroke_style = "#F00"
dc.fill_style = "#0F0"
dc.translate(35, 40)
dc.rotate(math.radians(15))
dc.translate(-35, -40)
dc.fill()
dc.stroke()
dc.restore()

dc.save()
dc.translate(100, 100)
dc.begin_path()
dc.rect(20, 20, 30, 40)
dc.stroke_style = "#048"
dc.fill_style = "#CCF"
dc.translate(35, 40)
dc.rotate(math.radians(-15))
dc.translate(-35, -40)
dc.fill()
dc.stroke()
dc.restore()

dc.save()
dc.translate(100, 0)
dc.clip_rect(0, 0, 40, 40)
dc.begin_path()
dc.rect(20, 20, 30, 40)
dc.stroke_style = "#008"
dc.fill_style = "#F8F"
dc.translate(35, 40)
dc.rotate(math.radians(65))
dc.translate(-35, -40)
dc.fill()
dc.stroke()
dc.restore()

dc.save()
dc.translate(0, 100)
gradient = dc.create_linear_gradient(40, 40, 0, 0, 0, 40)
gradient.add_color_stop(0, '#F00')
gradient.add_color_stop(1, '#0F0')
dc.rect(20, 20, 30, 40)
dc.fill_style = gradient
dc.stroke_style = "#00F"
dc.translate(35, 40)
dc.rotate(math.radians(45))
dc.translate(-35, -40)
dc.fill()
dc.stroke()
dc.restore()

dc.save()
dc.translate(200, 0)
dc.fill_text("Left", 8, 40)
dc.save()
dc.text_align="right"
dc.fill_text("Right", 92, 60)
dc.restore()
dc.save()
dc.text_align="center"
dc.fill_text("Center", 50, 80)
dc.restore()
dc.begin_path()
dc.move_to(8, 0)
dc.line_to(8, 100)
dc.move_to(92, 0)
dc.line_to(92, 100)
dc.move_to(50, 0)
dc.line_to(50, 100)
for v in range(20, 100, 20):
    dc.move_to(0, v)
    dc.line_to(100, v)
dc.stroke_style = "#EEE"
dc.stroke()
dc.restore()

dc.save()
dc.translate(200, 100)
dc.text_align="center"
dc.save()
dc.text_baseline="top"
dc.fill_text("Top", 50, 0)
dc.restore()
dc.save()
dc.text_baseline="bottom"
dc.fill_text("Bottom", 50, 40)
dc.restore()
dc.save()
dc.text_baseline="middle"
dc.fill_text("Middle", 50, 60)
dc.restore()
dc.save()
dc.text_baseline="alphabetic"
dc.fill_text("Alphabetic", 50, 80)
dc.restore()
dc.begin_path()
dc.move_to(8, 0)
dc.line_to(8, 100)
dc.move_to(92, 0)
dc.line_to(92, 100)
dc.move_to(50, 0)
dc.line_to(50, 100)
for v in range(20, 100, 20):
    dc.move_to(0, v)
    dc.line_to(100, v)
dc.stroke_style = "#EEE"
dc.stroke()
dc.restore()

dc.save()
dc.translate(0, 200)
dc.line_width = 8
dc.stroke_style = "#080"
dc.line_cap = "square"
dc.move_to(25, 25)
dc.line_to(25, 75)
dc.stroke()
dc.line_cap = "round"
dc.move_to(50, 25)
dc.line_to(50, 75)
dc.stroke()
dc.line_cap = "butt"
dc.move_to(75, 25)
dc.line_to(75, 75)
dc.stroke()
dc.restore()

dc.save()
dc.translate(100, 200)
dc.line_width = 8
dc.stroke_style = "#080"
dc.line_join = "round"
dc.begin_path()
dc.move_to(25, 25)
dc.line_to(75, 25)
dc.line_to(60, 40)
dc.stroke()
dc.line_join = "miter"
dc.begin_path()
dc.move_to(40, 45)
dc.line_to(25, 60)
dc.line_to(75, 60)
dc.stroke()
dc.line_join = "bevel"
dc.begin_path()
dc.move_to(25, 75)
dc.line_to(75, 75)
dc.line_to(60, 90)
dc.stroke()
dc.restore()

dc.save()
dc.translate(200, 200)
dc.stroke_style = "#088"
dc.line_dash = 4
dc.rect(25, 25, 50, 50)
dc.stroke()
dc.line_dash = 2
dc.begin_path()
dc.move_to(25, 25)
dc.line_to(75, 75)
dc.move_to(75, 25)
dc.line_to(25, 75)
dc.stroke()
dc.restore()

dc.save()
dc.translate(300, 0)
dc.text_align="center"
dc.text_baseline="middle"
dc.font = "24px"
dc.fill_text("Font 24", 50, 20)
dc.font = "sans-serif"
dc.fill_text("Sans Serif", 50, 40)
dc.font = "bold 16px"
dc.fill_text("Bold 16", 50, 60)
dc.font = "italic 18px"
dc.fill_text("Italic 18", 50, 80)
dc.restore()

dc.save()
dc.translate(300, 100)
image_raw = scipy.misc.lena()
image = numpy.empty(image_raw.shape + (4, ), dtype='uint8')
image[:,:,0] = image_raw
image[:,:,1] = image_raw
image[:,:,2] = image_raw
image[:,:,3] = 255
# note the statement below requires scipy and PIL to be installed
dc.draw_image(image.view(numpy.uint32).reshape(image.shape[:-1]), 20, 20, 60, 60)
dc.restore()

dc.begin_path()
dc.rect(0, 0, 600, 400)
dc.stroke_style = "#CCC"
dc.stroke()
dc.begin_path()
for h in range(100, 600, 100):
    dc.move_to(h, 0)
    dc.line_to(h, 400)
for v in range(100, 400, 100):
    dc.move_to(0, v)
    dc.line_to(600, v)
dc.stroke_style = "#CCC"
dc.stroke()

viewbox = Geometry.IntRect(Geometry.IntPoint(), Geometry.IntSize(width=640, height=480))
size = viewbox.size

print(dc.to_svg(size, viewbox))
