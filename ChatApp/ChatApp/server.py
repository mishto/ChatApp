from gevent import monkey
from ChatApp.models import UserModel, MessageModel

monkey.patch_all(socket=True, dns=True, time=True, select=True,thread=False,
    os=True, ssl=True, httplib=False, aggressive=True)

from ws4py.websocket import WebSocket
from ws4py.server.geventserver import WSGIServer
from ws4py.server.wsgiutils import WebSocketWSGIApplication


class MessageUtils:
    def make_message(self, username, message_text):
        """ Given a username and text, this returns the full message to be sent
        to the user.
        """
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


        raise Exception("Message cannot be parsed: %s" % message)


class User(object):
    def __init__(self, username, connection = None, ):
        self.username = username
        if connection:
            self.connections = [connection]
        else:
            self.connections = []

    def send_message(self, message_text, from_username):
        message = MessageUtils().make_message(from_username, message_text)
        for connection in self.connections:
            connection.send(message)

    def add_connection(self, connection):
        self.connections.append(connection)

    def save(self):
        user = UserModel(username = self.username)
        user.save()


class UserPool():
    def __init__(self):
        self.user_models = {}
        self.user_sockets = {}

    def register_user(self, username, ws):
        """
        If a user with the username exists already in self.users
        add the ws to the user's list of sockets.
        Otherwise create a new user (and save to database if not there) with the given socket.
        """

        if username not in self.user_models:
            user = UserModel(username = username)
            user.save()
            self.user_models[username] = user

        self.user_models[username].sockets.append(ws)
        return self.user_models[username]


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

        return None


class MessageController(object):
    def __init__(self):
        self.user_pool = UserPool()


    def _route_message(self, msg):
        delivered = False

        for ws in msg.to_user.sockets:
            message = MessageUtils().make_message(msg.from_user.username, msg.message_text)
            ws.send(message)
            delivered = True

        return delivered


    def send_message(self, message, from_user):
        """
        Attempts to send a message and/or save the message to the database.
         If the destination user is not found returns False.  Otherwise returns True.
        """
        to_username, message_text = MessageUtils().parse_message(message)
        to_user = self.user_pool.find_user(to_username)
        if to_user:
            msg = MessageModel(from_user=from_user, to_user=to_user, message_text=message_text)
            msg.delivered = self._route_message(msg)
            msg.save()
            return True
        return False


    def process_message(self, message, ws):
        """
        Takes a message from a websocket and takes the appropriate action.
        If the ws does not have a user, then uses the message to authenticate user
          and create it in the database.  It keeps track of the users and associated ws.
        If the ws is associated to a user, then it tries to send the message to destination.
        """

        if ws.user:
            if not self.send_message(message, ws.user):
                ws.send("User does not exist.")
        else:
            self.authenticate(message, ws)

    def authenticate(self, message, ws):
        auth = ChatAuth()
        username = auth.authenticate(username = message)
        if username:
            ws.authenticated = True
            ws.user = self.user_pool.register_user(username, ws)

        ws.send("Invalid username.")



class ChatAuth(object):
    def authenticate(self, username):
        username = str(username)
        if len(username.split()) == 1:
            return username

        return None

class ChatWebSocketServer(WebSocket):
    def __init__(self, *args, **kwargs):
        WebSocket.__init__(self, *args, **kwargs)
        self.authenticated = False
        self.user = None


    def opened(self):
        self.send("Welcome to ChatServer.")
        self.send("To authenticate enter your username.")


    def received_message(self, message):
        controller.process_message(message, self)


    def is_authenticated(self):
        return self.authenticated


controller = MessageController()

if __name__ == "__main__":
    server = WSGIServer(('127.0.0.1', 9000), WebSocketWSGIApplication(handler_cls=ChatWebSocketServer))
    server.serve_forever()


