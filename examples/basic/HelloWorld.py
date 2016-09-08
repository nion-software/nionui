# standard libraries
import gettext
import math

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import CanvasItem
from nion.ui import Window

_ = gettext.gettext


# user program below

class HelloWorldApplication(Application.Application):

    def start(self):
        # the start method should create a window that will be the focus of the ui
        self.window = HelloWorldWindow(self.ui, app=self)
        self.window.show()
        return True


class BrownSquareCanvasItem(CanvasItem.AbstractCanvasItem):

    def __init__(self):
        super().__init__()
        self.sizing.set_fixed_height(40)
        self.sizing.set_fixed_width(40)

    def _repaint(self, drawing_context):
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.rect(10, 10, 20, 20)
        drawing_context.fill_style = "#C84"
        drawing_context.fill()
        drawing_context.restore()
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.rect(0, 0, 40, 40)
        drawing_context.stroke_style = "#000"
        drawing_context.stroke()
        drawing_context.restore()
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.arc(20, 20, 8, 0, 2 * math.pi)
        drawing_context.stroke_style = "#FFF"
        drawing_context.stroke()
        drawing_context.restore()
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.round_rect(5, 5, 30, 30, 8)
        drawing_context.stroke_style = "#F04"
        drawing_context.stroke()
        drawing_context.restore()


class HelloWorldWindow(Window.Window):

    def __init__(self, ui, app=None):
        super().__init__(ui, app)

        hello_world_str_ref = ["Hello World!", ]

        # place the hello world text into a row so that the text can be left justified within the row
        # by adding a stretch on the right side of the row. then configure the height of the row to match
        # the height of the hello world text.

        # make a column in which to place the hello world text and a custom canvas item, add the items,
        # then add stretch at the bottom so that the fixed height items get pushed to the top.
        progress_bar_row = CanvasItem.CanvasItemComposition()
        progress_bar_row.layout = CanvasItem.CanvasItemRowLayout(spacing=4)
        progress_bar_canvas_item = CanvasItem.ProgressBarCanvasItem()
        progress_bar_canvas_item.progress = 0
        progress_bar_canvas_item.sizing.set_fixed_width(500)
        progress_bar_row.add_canvas_item(progress_bar_canvas_item)
        progress_bar_row.add_stretch()
        progress_bar_row.sizing.set_fixed_height(progress_bar_canvas_item.sizing.preferred_height)
        check_box_row = CanvasItem.CanvasItemComposition()
        check_box_row.layout = CanvasItem.CanvasItemRowLayout(spacing=4)
        check_box_canvas_item = CanvasItem.CheckBoxCanvasItem()
        check_box_canvas_item.sizing.set_fixed_width(20)
        check_box_canvas_item.sizing.set_fixed_height(20)
        check_box_row.add_canvas_item(check_box_canvas_item)
        check_box_row.add_stretch()
        check_box_row.sizing.set_fixed_height(20)
        column_canvas_item = CanvasItem.CanvasItemComposition()
        column_canvas_item.layout = CanvasItem.CanvasItemColumnLayout(spacing=12, alignment="start")
        brown_square_row = CanvasItem.CanvasItemComposition()
        brown_square_row.layout = CanvasItem.CanvasItemRowLayout(spacing=4)
        brown_square_canvas_item = BrownSquareCanvasItem()
        brown_square_row.add_canvas_item(brown_square_canvas_item)
        brown_square_row.add_stretch()
        brown_square_row.sizing.set_fixed_height(brown_square_canvas_item.sizing.preferred_height)
        column_canvas_item.add_canvas_item(brown_square_row)
        column_canvas_item.add_canvas_item(progress_bar_row)
        column_canvas_item.add_canvas_item(check_box_row)
        column_canvas_item.add_stretch()

        # configure what happens when the button is pressed
        click_count_ref = [0]
        def button_clicked():
            click_count_ref[0] += 1
            hello_widget.text = hello_world_str_ref[0] + " (" + str(click_count_ref[0]) + ")"
            progress_bar_canvas_item.progress += 0.1

        def checked_changed(value):
            hello_world_str_ref[0] = "Goodbye World..." if value else "Hello World!"
            button_clicked()

        # finally add the column to a root widget and attach the root widget to the document window.
        root_widget = ui.create_column_widget(alignment="start")

        one_row = ui.create_row_widget()
        one_row.add_stretch()
        one_row.add(ui.create_label_widget("Centered"))
        one_row.add_stretch()

        check_box_widget = ui.create_check_box_widget("Check BOX")

        hello_widget = ui.create_push_button_widget(hello_world_str_ref[0])

        canvas_widget = ui.create_canvas_widget(properties={"height": 500, "width": 600})
        canvas_widget.canvas_item.add_canvas_item(column_canvas_item)

        root_widget.add(one_row)
        root_widget.add(check_box_widget)
        root_widget.add(hello_widget)
        root_widget.add(canvas_widget)

        self.attach_widget(root_widget)

        hello_widget.on_clicked = button_clicked
        check_box_widget.on_checked_changed = checked_changed


def main(args, bootstrap_args):
    app = HelloWorldApplication(Application.make_ui(bootstrap_args))
    app.initialize()
    return app
