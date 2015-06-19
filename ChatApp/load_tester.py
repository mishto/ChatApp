import random
import sys
import gevent
from client import ChatWebsocketClient
WEBSOCKET_URL = 'ws://127.0.0.1:9000'
PROTOCOLS = ['http-only', 'chat']


class Connection:
    """
    Simulates a connection with a username
    """
    def __init__(self, username):
        self.client = ChatWebsocketClient(WEBSOCKET_URL, PROTOCOLS)
        self.username = username

    def close(self):
        self.client.close()

    def authenticate(self):
        self.client.send(self.username)

    def send_message_to_username(self, message, to_username):
        self.client.send("@%s %s" % (to_username, message))

    def receive(self):
        while True:
            message = self.client.receive()
            print "%s: %s" % (self.username, message)


if __name__ == "__main__":
    random.seed(111)
    users_num = 0
    if len(sys.argv) == 2:
        users_num = int(sys.argv[1])
    else:
        print "Usage to start 1000 connections : load_tester.py 1000"
        exit()


    #create some usernames
    usernames = []
    for i in range(0, users_num):
        usernames.append("user_%d" % i)

    #create one connection for each user
    connections = []
    for i in range(0, users_num):
        connections.append(Connection(usernames[i]))

    greenlets = []
    #spawn receivers' micro threads
    for i in range(0, users_num):
        gevent.spawn(connections[i].receive),

    #randomly send messages from one user to another
    for i in range(0, 10):
        from_connection = connections[random.randrange(0, users_num)]
        to_connection = connections[random.randrange(0, users_num)]


    gevent.joinall(greenlets)

    gevent.sleep(10)


