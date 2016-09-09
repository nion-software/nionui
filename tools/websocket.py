import importlib
import os
import sys

try:
    from nion.ui import TwistedWebSocketServer
except ImportError as e:
    print("Cannot import TwistedWebSocketServer.")
    print(e)
    raise
def run_server(server):
    module_name = "main"
    if len(sys.argv) > 1:
        path = os.path.abspath(sys.argv[1])
        if os.path.isfile(path):
            dirname = os.path.dirname(path)
            module_name = os.path.splitext(os.path.basename(path))[0]
            sys.path.insert(0, dirname)
        else:
            sys.path.insert(0, path)
    module = importlib.import_module(module_name)
    app = getattr(module, "main")((), {"server": server})
    if app.start():
        app.ui.run(server.event_queue)
TwistedWebSocketServer.TwistedWebSocketServer().launch(run_server)
