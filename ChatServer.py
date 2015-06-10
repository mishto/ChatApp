import datetime
from gevent import monkey;monkey.patch_all()

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
        self.username = ""
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


class UserPool():
    def __init__(self):
        self.users = {}

    def create_user(self, username, ws):
        """
        If a user with the username exists already, add the ws to the user's list
        of sockets.  Otherwise create a new user with the given socket.
        """

        if username in self.users:
            self.users[username].add_connection(ws)
        else:
            user = User(username, ws)
            self.users[username] = user

    def get_user(self, username):
        if username in self.users:
            return self.users[username]
        return None


class ChatBackend(object):
    def __init__(self, user_pool):
        self.user_pool = user_pool

    def process_message(self, message, from_username):
        to_username, message_text = MessageUtils().parse_message(message)
        to_user = self.user_pool.get_user(to_username)
        if to_user:
            to_user.send_message(message_text, from_username)


class ChatAuth(object):
    def authenticate(self, username):
        username = str(username)
        return username

class ChatWebSocketServer(WebSocket):
    def __init__(self, *args, **kwargs):
        WebSocket.__init__(self, *args, **kwargs)
        self.authenticated = False
        self.username = None

    def opened(self):
        self.send("Welcome to ChatServer.")
        self.send("To authenticate enter your username.")

    def received_message(self, message):
        if self.is_authenticated():
            try:
                chat_backend.process_message(message, self.username)
            except Exception, e:
                self.send("Could not process message: ")
                self.send(str(e))
        else:
            self.username = self.authenticate(message)
            if self.username:
                self.send("Your username is %s." % self.username)
            else:
                self.send("Authentication failed.")

    def is_authenticated(self):
        return self.authenticated

    def authenticate(self, message):
        a = ChatAuth()
        username = a.authenticate(username = message)
        if username:
            self.authenticated = True
            user_pool.create_user(username, self)
            return username

        return None


if __name__ == "__main__":
    user_pool = UserPool()
    chat_backend = ChatBackend(user_pool)
    server = WSGIServer(('127.0.0.1', 9000), WebSocketWSGIApplication(handler_cls=ChatWebSocketServer))
    server.serve_forever()


