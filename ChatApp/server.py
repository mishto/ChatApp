#from gevent import monkey; monkey.patch_all(socket=True, dns=True, time=True, select=True,thread=False,
#    os=True, ssl=True, httplib=False, aggressive=True)
from gevent.greenlet import Greenlet
import redis

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
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)

    def is_user_stored(self, username):
        return username in self.subscriptions.keys()

    def add_connection(self, username, ws):
        """
        Ads ws to the key username.
        """

        subscriber = self.redis.pubsub()
        subscriber.subscribe(username)
        g_listener = Greenlet(self._listen_to_channel, subscriber, ws.send)
        g_listener.start()
        ws.greenlet_listener = g_listener

        if self.is_user_stored(username):
            self.subscriptions[username].append(ws)
        else:
            self.subscriptions[username] = [ws]


    def send_message_to_channel(self, channel, message):
        self.redis.publish(channel, message)

    def _listen_to_channel(self, subscriber, handler):
        for message in subscriber.listen():
            if message["type"] == "message":
                handler(message["data"])

class UserPool():
    def __init__(self):
        self.user_models = {}
        self.data_store = RedisAdapter()


    def register_user(self, username, ws):
        """
        If a user with the username exists already in self.users
        add the ws to the user's list of sockets.
        Otherwise create a new user (and save to database if not there) with the given socket.
        """

        if username not in self.user_models:
            user, dummy = UserModel.objects.get_or_create(username = username)

            self.user_models[username] = user

        self.user_models[username].sockets.append(ws)

        ws.user = self.user_models[username]

    def unregister(self, username, ws):
        self.user_models[username].sockets.remove(ws)
        if not self.user_models[username].sockets:
            self.user_models.pop(username, None)


    def find_user(self, username):
        """
        Attempts to find user with correct username in the cache or in the database.
        If the user is in the cache it will have one or more associated websocket connections.
        """
        if username in self.user_models:
            return self.user_models[username]

        else:
            user =  UserModel.objects.filter(username = username)
            if user:
                user = user[0]
                return user

        raise Exception("User does not exist.")


class ChatMessageController(object):
    def process_message(self, message, ws):
        """
        Takes a message from a websocket and tries to send the message to destination.
        """

        try:
            to_username, message_text = MessageUtils().parse_message(message)
            to_user = user_pool.find_user(to_username)
            msg = MessageModel(from_user=ws.user, to_user=to_user, message_text=message_text)
            msg.delivered = self._route_message(msg)
            msg.save()

        except Exception, e:
            ws.send(str(e))

    def socket_closed(self, ws):
        if ws.user:
            user_pool.unregister(ws.user.username, ws)

    def _route_message(self, msg):
        delivered = False

        for ws in msg.to_user.sockets:
            message = MessageUtils().make_message(msg.from_user.username, msg.message_text)
            ws.send(message)
            delivered = True

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
            ws.authenticated = True
            user_pool.register_user(username, ws)

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


    def opened(self):
        self.send("Welcome to ChatServer.")
        self.send("To authenticate enter your username.")

    def closed(self, code, reason=None):
        self.controller.socket_closed(self)

    def received_message(self, message):
        self.controller.process_message(message, self)

    def set_authenticated(self):
        self.controller = ChatMessageController()


user_pool = UserPool()

redis_adapter = RedisAdapter

if __name__ == "__main__":
    server = WSGIServer(('127.0.0.1', 9000), WebSocketWSGIApplication(handler_cls=ChatWebSocketServer))
    server.serve_forever()

