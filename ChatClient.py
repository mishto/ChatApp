from gevent import monkey; monkey.patch_socket()
import gevent
import sys
from gevent import select
from ws4py.client.geventclient import WebSocketClient
from ws4py import configure_logger

logger = configure_logger()

class ChatWebsocketClient(WebSocketClient):
    def __init__(self, url, event_listeners, protocols=None, extensions=None, ssl_options=None, headers=None):
        WebSocketClient.__init__(self, url, protocols, extensions, ssl_options=ssl_options, headers=headers)
        self.listeners = event_listeners


class UIController(object):
    errors = {"connect": "There was an error connecting to the ChatServer:"}

    def __init__(self, ws_client, ui):
        self.ui = ui
        self.ws_client = ws_client

    def run(self):
        try:
            self.ws_client.connect()

            greenlets = [
                gevent.spawn(self.ui_input_loop),
                gevent.spawn(self.socket_loop),
                ]
            gevent.joinall(greenlets)
        except Exception, e:
            self.ui.show_message(self.errors["connect"])
            self.ui.show_message(e)

    def ui_input_loop(self):
        while True:
            m = self.ui.get_user_input()
            if self.ui.is_closed():
                break
            self.send_message(m)
            gevent.sleep(0)

        self.ws_client.close()

    def socket_loop(self):
        while True:
            msg = self.ws_client.receive()

            #msg is None iff ws_client is closed
            if msg is None:
                break

            self.ui.show_message(msg)
            gevent.sleep(0)

    def send_message(self, msg):
        self.ws_client.send(msg)


class ChatConsoleUI(object):
    def __init__(self):
        self.closed = False
        self.bye_string = "###"
        print "End your session by typing '%s'" % self.bye_string

    def is_closed(self):
        return self.closed

    def get_user_input(self):
        while True:
            input,o,e = select.select([sys.stdin],[],[],.2)

            if input:
                m = input[0].readline().strip()
                if m == self.bye_string:
                    self.closed = True
                    return None

                return m

    def show_message(self, msg):
        print msg


if __name__ == "__main__":
    WEBSOCKET_URL = 'ws://127.0.0.1:9000'
    PROTOCOLS = ['http-only', 'chat']

    ui = ChatConsoleUI()
    client = ChatWebsocketClient(WEBSOCKET_URL, PROTOCOLS)

    controller = UIController(client, ui)
    controller.run()