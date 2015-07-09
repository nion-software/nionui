# standard libraries
import gettext
import numpy
import random

# third party libraries
# None

# local libraries
from nion.ui import ThriftUI

_ = gettext.gettext

ui = ThriftUI.make_ui()

# the program

document_window = ui.create_document_window()
def about_to_show():
    print("ABOUT TO SHOW!")
document_window.on_about_to_show = about_to_show
document_window.show()

file_menu = document_window.add_menu(_("File"))
edit_menu = document_window.add_menu(_("Edit"))
extra_menu = document_window.add_menu(_("Extra"))
extra_menu.add_separator()

root_widget = ui.create_column_widget(properties={"min-width": 640, "min-height": 480})
one_label = ui.create_label_widget(_("One"))
#scroll_area = ui.create_scroll_area_widget(dict())
#scroll_area.content = one_label
root_widget.add(one_label)
canvas_widget = ui.create_canvas_widget()
layer = canvas_widget.create_layer()
def canvas_size_changed(width, height):
    if width > 0 and height > 0:
        ctx = layer.drawing_context
        ctx.clear()
        ctx.save()
        ctx.begin_path()
        ctx.move_to(0, 0)
        ctx.line_to(0, canvas_widget.height)
        ctx.line_to(canvas_widget.width, canvas_widget.height)
        ctx.line_to(canvas_widget.width, 0)
        ctx.close_path()
        gradient = ctx.create_linear_gradient(canvas_widget.width, canvas_widget.height, 0, 0, 0, canvas_widget.height)
        gradient.add_color_stop(0, '#ededed')
        gradient.add_color_stop(1, '#cacaca')
        ctx.fill_style = gradient
        ctx.fill()
        ctx.restore()
        ctx.save()
        ctx.begin_path()
        # line is adjust 1/2 pixel down to align to pixel boundary
        ctx.move_to(0, 0.5)
        ctx.line_to(canvas_widget.width, 0.5)
        ctx.stroke_style = '#FFF'
        ctx.stroke()
        ctx.restore()
        ctx.save()
        img = ui.load_rgba_data_from_file("/Users/cmeyer/Developer/Nion/NionImaging/Graphics/Swift_512x512.png")
        # comes back as uint32, bgra
        if False:
            img = numpy.zeros((1024, 1024, 4), dtype=numpy.uint8)
            img[:,:,0] = random.randint(0, 255)
            img[:,:,1] = random.randint(0, 255)
            img[:,:,2] = random.randint(0, 255)
            img[:,:,3] = 255
        ctx.draw_image(img, 0, 0, 200, 200)
        ctx.restore()
        ctx.save()
        ctx.begin_path()
        # line is adjust 1/2 pixel down to align to pixel boundary
        ctx.move_to(0, canvas_widget.height-0.5)
        ctx.line_to(canvas_widget.width, canvas_widget.height-0.5)
        ctx.stroke_style = '#b0b0b0'
        ctx.stroke()
        ctx.restore()
        ctx.save()
        ctx.font = 'normal 11px serif'
        ctx.text_align = 'center'
        ctx.text_baseline = 'middle'
        ctx.fill_style = '#000'
        ctx.fill_text(u"Hello World\u2192", canvas_widget.width/2, canvas_widget.height/2+1)
        ctx.restore()
        canvas_widget.draw()
canvas_widget.on_size_changed = canvas_size_changed
root_widget.add(canvas_widget)
button_widget = ui.create_push_button_widget(_(u"\u2190Three"))
a = numpy.zeros((48, 48, 4), dtype=numpy.uint8)
a[:,:,0] = 255
a[:,:,1] = 0
a[:,:,2] = 255
a[:,:,3] = 255
def button_clicked():
    print("button clicked")
button_widget.icon = a
button_widget.on_clicked = button_clicked
root_widget.add(button_widget)

document_window.attach(root_widget)

ThriftUI.run()
