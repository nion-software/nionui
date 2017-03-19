"""
Twisted web socket server for interacting with a web page and CanvasUI.
"""

# futures
from __future__ import absolute_import
from __future__ import division

# standard libraries
import collections
import json
import os
import signal
import sys
import threading

# conditional imports
if sys.version < '3':
    import Queue as queue
else:
    import queue

# third party libraries
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import reactor
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

# local libraries
# None

class TwistedWebSocketServer(object):

    def __init__(self):
        log.startLogging(sys.stdout)

        event = threading.Event()
        message_queue = queue.Queue()
        event_queue = queue.Queue()
        measure_text_event = threading.Event()
        measurement = [0]

        class MyServerProtocol(WebSocketServerProtocol):

            def __init__(self):
                self.send_my_messages()
                self.alive = True
                super(MyServerProtocol, self).__init__()

            def onConnect(self, request):
                print("Client connecting: {0}".format(request.peer))

            def send_my_messages(self):
                while not message_queue.empty() and self.alive:
                    message = message_queue.get()
                    self.sendMessage(message)
                    message_queue.task_done()
                reactor.callLater(1/100.0, self.send_my_messages)

            def onMessage(self, payload, isBinary):
                event_dict = json.loads(payload.decode('utf8'))
                event_type = event_dict.get("type")
                if event_type == "measure_text":
                    measurement[0] = event_dict
                    measure_text_event.set()
                else:
                    event_queue.put(event_dict)

            def onOpen(self):
                event.set()

            def onClose(self, wasClean, code, reason):
                self.alive = False
                event_queue.put({"type":"quit"})

        def stop_thread(*args):
            print("Stopping Ctrl-C")
            reactor.callFromThread(reactor.stop)
            sys.exit(0)

        if signal.getsignal(signal.SIGINT) == signal.default_int_handler:
            signal.signal(signal.SIGINT, stop_thread)
        signal.signal(signal.SIGTERM, stop_thread)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, stop_thread)

        factory = WebSocketServerFactory("ws://localhost:9000")
        factory.protocol = MyServerProtocol

        def reactor_thread():
            dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
            resource = File(os.path.join(dir, "html"))
            site_factory = Site(resource)
            reactor.listenTCP(8888, site_factory)
            reactor.listenTCP(9000, factory)
            reactor.run(installSignalHandlers=0)

        threading.Thread(target=reactor_thread).start()

        def launch(fn):
            while True:
                if event.wait(0.1):
                    event.clear()
                    print("start")
                    fn(self)
                    print("finish")

        def put_message(message):
            if sys.version < '3':
                message_queue.put(message)
            else:
                message_queue.put(bytes(message, "utf8"))

        def draw(drawing_context):
            put_message(json.dumps({"message": "draw", "js": drawing_context.to_js()}))

        def get_font_metrics(font, text):
            measure_text_event.clear()
            put_message(json.dumps({"message": "measure", "font": font, "text": text}))
            measure_text_event.wait()
            FontMetrics = collections.namedtuple("FontMetrics", ["width", "height", "ascent", "descent", "leading"])
            return FontMetrics(width=measurement[0].get("width"), height=measurement[0].get("height"), ascent=measurement[0].get("ascent"), descent=measurement[0].get("descent"), leading=0)

        self.launch = launch
        self.event_queue = event_queue
        self.draw = draw
        self.get_font_metrics = get_font_metrics
