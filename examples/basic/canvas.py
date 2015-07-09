# standard libraries
import gettext
import logging
import numpy
import random

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import Geometry
from nion.ui import ThriftUI

_ = gettext.gettext

logging.basicConfig(level=logging.DEBUG)

ui = ThriftUI.make_ui()

# the program

document_window = ui.create_document_window()
document_window.show()

root_widget = ui.create_column_widget(properties={"min-width": 640, "min-height": 480})

root_canvas = CanvasItem.RootCanvasItem(ui)

sub_canvas = CanvasItem.CanvasItemComposition()
sub_canvas.layout = CanvasItem.CanvasItemColumnLayout(spacing=10)
sub_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"))
sub_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"))

grid_canvas = CanvasItem.CanvasItemComposition()
grid_canvas.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(2, 2))
grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"), Geometry.IntPoint(x=0, y=0))
grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#0F0"), Geometry.IntPoint(x=1, y=0))
grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#888"), Geometry.IntPoint(x=0, y=1))
grid_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#00F"), Geometry.IntPoint(x=1, y=1))
grid_canvas.canvas_items[1].sizing.minimum_height = 430
grid_canvas.canvas_items[1].sizing.minimum_width = 160

root_canvas.layout = CanvasItem.CanvasItemRowLayout(spacing=10, margins=Geometry.Margins(10, 10, 10, 10))
root_canvas.add_canvas_item(CanvasItem.BackgroundCanvasItem("#F00"))
root_canvas.add_canvas_item(sub_canvas)
root_canvas.add_canvas_item(grid_canvas)

root_widget.add(root_canvas.canvas_widget)

document_window.attach(root_widget)

ThriftUI.run()
