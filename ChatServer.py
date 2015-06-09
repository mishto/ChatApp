from gevent import monkey;monkey.patch_all()

from ws4py.websocket import WebSocket
from ws4py.server.geventserver import WSGIServer
from ws4py.server.wsgiutils import WebSocketWSGIApplication


class ChatWebsocketServer(WebSocket):
    def opened(self):
        self.send("Welcome to ChatServer.")
        self.send("To authenticate enter your username.")

    def received_message(self, message):
        self.send("Echo: '" + str(message) + "'")




server = WSGIServer(('127.0.0.1', 9000), WebSocketWSGIApplication(handler_cls=ChatWebsocketServer))
server.serve_forever()
