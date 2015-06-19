#from gevent import monkey; monkey.patch_all(socket=True, dns=True, time=True, select=True,thread=False,
#    os=True, ssl=True, httplib=False, aggressive=True)
import gevent
from gevent.greenlet import Greenlet
import redis
import sys

from orm.models import UserModel, MessageModel
from ws4py.websocket import WebSocket
from ws4py.server.geventserver import WSGIServer
from ws4py.server.wsgiutils import WebSocketWSGIApplication


class MessageUtils:
    def make_message(self, username, message_text):
        """ Given a username and text, this formats the message to be sent to the user."""

        if username and message_text:
            return "@" + str(username) + " >> " + message_text

        raise Exception("Trying to create message with invalid username.")

    def parse_message(self, message):
        """
        Given a text message including the username and actual message, parses
        the message into username and actual message_text
        """

        tokens = str(message).split(None, 1)

        if len(tokens) == 2:
            user = tokens[0]
            message_text = tokens[1]

            if user.startswith('@') and message_text:
                return user[1:], message_text

        raise Exception("Message could not be parsed.")


class RedisAdapter():
    def __init__(self):
        self.subscriptions = {}
        self.users = {}
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)

    def is_user_stored(self, username):
        return username in self.users

    def store_user(self, user):
        if not self.is_user_stored(user.username):
            self.users[user.username] = user

    def get_user(self, username):
        return self.users[username]

    def add_connection(self, username, ws):
        """
        Ads ws to the key username.
        """

        subscriber = self.redis.pubsub()
        subscriber.subscribe(username)
        g_listener = Greenlet(self._listen_to_channel, subscriber, ws)
        g_listener.start()
        ws.greenlet_listener = g_listener

        if username in self.subscriptions:
            self.subscriptions[username].append(ws)
        else:
            self.subscriptions[username] = [ws]

    def remove_connection(self, username, ws):
        ws.greenlet_listener.kill()
        self.subscriptions[username].remove(ws)
        if not self.subscriptions[username]:
            self.subscriptions.pop(username, None)

    def send_message_to_channel(self, channel, message):
        return self.redis.publish(channel, message)


    def _listen_to_channel(self, subscriber, ws):
        while True:
            message = subscriber.get_message()
            if message and message["type"] == "message":
                ws.send(message["data"])

            if not ws.is_open:
                subscriber.unsubscribe()
                return

            gevent.sleep(0)



class ChatMessageController(object):
    def process_message(self, message, ws):
        """
        Takes a message from a websocket and tries to send the message to destination.
        """

        try:
            to_username, message_text = MessageUtils().parse_message(message)
            if redis_adapter.is_user_stored(to_username):
                to_user = redis_adapter.get_user(to_username)
            else:
                to_user = UserModel.objects.get(username = to_username)

            msg = MessageModel(from_user=ws.user, to_user=to_user, message_text=message_text)
            msg.delivered = self._route_message(msg)
            msg.save()

        except Exception, e:
            ws.send(str(e))

    def socket_closed(self, ws):
        if ws.user:
            redis_adapter.remove_connection(ws.user.username, ws)

    def _route_message(self, msg):
        message = MessageUtils().make_message(msg.from_user.username, msg.message_text)
        delivered = redis_adapter.send_message_to_channel(msg.to_user.username, message)
        return delivered


class AuthenticateMessageController(object):
    def process_message(self, message, ws):
        """
        It uses a websocket message to authenticate the ws.
        """

        self._authenticate_socket(message, ws)
        if ws.user:
            offline_messages = MessageModel.objects.filter(to_user = ws.user, delivered = False)
            self._send_offline_messages(offline_messages, ws)
            ws.send("Authentication successful.  Write a message like this: '@username your message' ")
            ws.set_authenticated()


    def socket_closed(self, ws):
        pass


    def _authenticate_socket(self, message, ws):
        username = Authentication().authenticate(username = message)
        if username:
            user, _ = UserModel.objects.get_or_create(username = username)
            ws.authenticated = True
            ws.user = user
            redis_adapter.add_connection(username, ws)
            redis_adapter.store_user(user)
        else:
            ws.send("Invalid username.")


    def _send_offline_messages(self, offline_messages, ws):
        for message in offline_messages:
            username = message.from_user.username
            text = message.message_text
            message_text = MessageUtils().make_message(username, text)
            ws.send(message_text)
            message.delivered = True
            message.save()


class Authentication(object):
    def authenticate(self, username):
        username = str(username)
        if len(username.split()) == 1:
            return username

        return None

class ChatWebSocketServer(WebSocket):
    def __init__(self, *args, **kwargs):
        WebSocket.__init__(self, *args, **kwargs)
        self.controller = AuthenticateMessageController()
        self.user = None
        self.greenlet_listener = None
        self.is_open= False

    def opened(self):
        self.send("Welcome to ChatServer.")
        self.send("To authenticate enter your username.")
        self.is_open = True

    def closed(self, code, reason=None):
        self.is_open = False
        self.controller.socket_closed(self)

    def received_message(self, message):
        self.controller.process_message(message, self)

    def set_authenticated(self):
        self.controller = ChatMessageController()


redis_adapter = RedisAdapter()

if __name__ == "__main__":
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    else:
        port = 9000

    server = WSGIServer(('127.0.0.1', port), WebSocketWSGIApplication(handler_cls=ChatWebSocketServer))
    server.serve_forever()

