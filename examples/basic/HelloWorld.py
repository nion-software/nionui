# standard libraries
import gettext
import os
import sys

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import DocumentController
from nion.ui import CanvasItem
from nion.ui import CanvasUI

_ = gettext.gettext


# user program below

class HelloWorldApplication(Application.Application):

    def start(self):
        # the start method should create a document window that will be the focus of the ui
        self.document_controller = HelloWorldDocumentController(self.ui, app=self)
        self.document_controller.document_window.show()


class BrownSquareCanvasItem(CanvasItem.AbstractCanvasItem):

    def __init__(self):
        super(BrownSquareCanvasItem, self).__init__()
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
        import math
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


class HelloWorldDocumentController(DocumentController.DocumentController):

    def __init__(self, ui, app=None):
        super(HelloWorldDocumentController, self).__init__(ui, app)

        # first create a root canvas item in which the rest of the user interface will go
        canvas_widget = ui.create_canvas_widget()

        background_canvas_item = CanvasItem.BackgroundCanvasItem("#FFF")

        # create the hello world text and size it to its contents
        hello_world_canvas_item = CanvasItem.CanvasItemComposition()
        hello_world_str = _("Hello World!")
        hello_world_button = CanvasItem.TextButtonCanvasItem(hello_world_str)
        hello_world_button.font = "normal 15px sans-serif"
        hello_world_button.size_to_content(ui.get_font_metrics)
        hello_world_canvas_item.add_canvas_item(hello_world_button)
        hello_world_canvas_item.sizing.copy_from(hello_world_button.sizing)

        # place the hello world text into a row so that the text can be left justified within the row
        # by adding a stretch on the right side of the row. then configure the height of the row to match
        # the height of the hello world text.
        # TODO: be able to position item within row directly via add_canvas_item
        text_row_canvas_item = CanvasItem.CanvasItemComposition()
        text_row_canvas_item.layout = CanvasItem.CanvasItemRowLayout()
        # text_row_canvas_item.add_spacing(1.0)
        text_row_canvas_item.add_canvas_item(hello_world_canvas_item)
        text_row_canvas_item.add_stretch()
        text_row_canvas_item.sizing.set_fixed_height(hello_world_canvas_item.sizing.maximum_height)

        # make a column in which to place the hello world text and a custom canvas item, add the items,
        # then add stretch at the bottom so that the fixed height items get pushed to the top.
        column_canvas_item = CanvasItem.CanvasItemComposition()
        column_canvas_item.layout = CanvasItem.CanvasItemColumnLayout(spacing=12)
        column_canvas_item.add_canvas_item(text_row_canvas_item)
        column_canvas_item.add_canvas_item(BrownSquareCanvasItem())
        progress_bar_row = CanvasItem.CanvasItemComposition()
        progress_bar_row.layout = CanvasItem.CanvasItemRowLayout(spacing=4)
        progress_bar_canvas_item = CanvasItem.ProgressBarCanvasItem()
        progress_bar_canvas_item.progress = 0
        progress_bar_canvas_item.sizing.set_fixed_width(500)
        progress_bar_row.add_canvas_item(progress_bar_canvas_item)
        progress_bar_row.add_stretch()
        progress_bar_row.sizing.copy_from(progress_bar_canvas_item.sizing)
        check_box_row = CanvasItem.CanvasItemComposition()
        check_box_row.layout = CanvasItem.CanvasItemRowLayout(spacing=4)
        check_box_canvas_item = CanvasItem.CheckBoxCanvasItem()
        check_box_canvas_item.sizing.set_fixed_width(20)
        check_box_canvas_item.sizing.set_fixed_height(20)
        check_box_row.add_canvas_item(check_box_canvas_item)
        check_box_row.add_stretch()
        check_box_row.sizing.set_fixed_height(20)
        column_canvas_item.add_canvas_item(progress_bar_row)
        column_canvas_item.add_canvas_item(check_box_row)
        column_canvas_item.add_stretch()

        # finally add the column to the root canvas item.
        canvas_widget.canvas_item.add_canvas_item(background_canvas_item)
        canvas_widget.canvas_item.add_canvas_item(column_canvas_item)

        # attach the root canvas item to the document window
        self.document_window.attach(canvas_widget)

        # configure what happens when the button is pressed
        click_count_ref = [0]
        def button_clicked():
            click_count_ref[0] += 1
            hello_world_button.text = hello_world_str + " (" + str(click_count_ref[0]) + ")"
            # TODO: support some sort of auto sizing to make the code below automatic
            hello_world_button.size_to_content(ui.get_font_metrics)
            hello_world_canvas_item.sizing.copy_from(hello_world_button.sizing)
            text_row_canvas_item.refresh_layout()
            progress_bar_canvas_item.progress += 0.1
        hello_world_button.on_button_clicked = button_clicked


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "twisted":
            try:
                from nion.ui import TwistedWebSocketServer
            except ImportError as e:
                print("Cannot import TwistedWebSocketServer.")
                print(e)
                raise
            def run_server(server):
                user_interface = CanvasUI.CanvasUserInterface(server.draw, server.get_font_metrics)
                app = HelloWorldApplication(user_interface)
                app.initialize()
                app.start()
                user_interface.run(server.event_queue)
            TwistedWebSocketServer.TwistedWebSocketServer().launch(run_server)
