# standard libraries
import gettext
import json
import sys

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import CanvasItem
from nion.ui import CanvasUI
from nion.ui import TreeCanvasItem
from nion.ui import Window

_ = gettext.gettext


# user program below

class MetadataEditorApplication(Application.Application):

    def start(self):
        # the start method should create a document window that will be the focus of the ui
        self.window = MetadataEditorWindow(self.ui, app=self)
        self.window.show()


class MetadataEditorTreeDelegate:
    def __init__(self, metadata):
        self.__metadata = metadata
        self.__expanded_value_paths = set()

    @property
    def metadata(self):
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        self.__metadata = value

    def __is_expanded(self, value_path):
        return json.dumps(value_path) in self.__expanded_value_paths

    def toggle_is_expanded(self, value_path):
        value_path_key = json.dumps(value_path)
        if value_path_key in self.__expanded_value_paths:
            self.__expanded_value_paths.remove(value_path_key)
        else:
            self.__expanded_value_paths.add(value_path_key)

    def build_items(self, get_font_metrics_fn, item_width):
        items = list()
        text_font = "normal 12px monospace"

        def visit_value(value_path, value):
            if isinstance(value, dict):
                is_expanded = self.__is_expanded(value_path)
                format_str = "{} {{{}}}"
                text_item = CanvasItem.StaticTextCanvasItem(format_str.format(value_path[-1], len(value)))
                text_item.font = text_font
                text_item.size_to_content(get_font_metrics_fn)
                items.append((text_item, "parent", is_expanded, value_path))
                if is_expanded:
                    visit_dict(value, value_path)
            elif isinstance(value, list) or isinstance(value, tuple):
                is_expanded = self.__is_expanded(value_path)
                format_str = "{} ({})"
                text_item = CanvasItem.StaticTextCanvasItem(format_str.format(value_path[-1], len(value)))
                text_item.font = text_font
                text_item.size_to_content(get_font_metrics_fn)
                items.append((text_item, "parent", is_expanded, value_path))
                if is_expanded:
                    visit_list(value, value_path)
            else:
                text_item = CanvasItem.StaticTextCanvasItem("{}: {}".format(value_path[-1], value))
                text_item.font = text_font
                text_item.size_to_content(get_font_metrics_fn)
                items.append((text_item, "child", None, value_path))

        def visit_list(l, path):
            for index, value in enumerate(l):
                value_path = path + (index,)
                visit_value(value_path, value)

        def visit_dict(d, path):
            for key in sorted(d.keys()):
                value = d[key]
                value_path = path + (key,)
                visit_value(value_path, value)

        visit_dict(self.__metadata, ())

        return items


class MetadataEditorWindow(Window.Window):

    def __init__(self, ui, app=None):
        super().__init__(ui, app)

        # first create a root canvas item in which the rest of the user interface will go
        canvas_widget = ui.create_canvas_widget()

        background_canvas_item = CanvasItem.BackgroundCanvasItem("#FFF")

        metadata = {"Dictionary1": {"abc": 5, "def": "hello", "List2": ["Red", "Green", "Blue"]}, "List1": [4, 5, 6]}

        metadata_editor_canvas_item = TreeCanvasItem.TreeCanvasItem(ui.get_font_metrics,
                                                                    MetadataEditorTreeDelegate(metadata))
        metadata_editor_canvas_item.reconstruct()

        # finally add the column to the root canvas item.
        canvas_widget.canvas_item.add_canvas_item(background_canvas_item)
        canvas_widget.canvas_item.add_canvas_item(metadata_editor_canvas_item)

        # attach the root canvas item to the document window
        self.attach_widget(canvas_widget)


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
                app = MetadataEditorApplication(user_interface)
                app.initialize()
                app.start()
                user_interface.run(server.event_queue)
            TwistedWebSocketServer.TwistedWebSocketServer().launch(run_server)
