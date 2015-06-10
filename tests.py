import unittest
from ChatClient import UIController, ChatConsoleUI
from ChatServer import MessageUtils, User, UserPool, ChatBackend
from mock import MagicMock, Mock
from unittest import TestCase

class UIControllerTest(TestCase):
    def setUp(self):
        self.ws_client = MagicMock()
        self.ui = MagicMock()

        self.controller = UIController(self.ws_client, self.ui)

        self.ws_client.connect = MagicMock()


    def test_connects_to_ws_client(self):
        self.controller.ui_input_loop = MagicMock()
        self.controller.socket_loop = MagicMock()

        self.controller.run()
        self.ws_client.connect.assert_called_with()

    def test_ui_message_when_connect_raises_except(self):
        self.ws_client.connect = MagicMock(side_effect = Exception('could not connect'))
        self.controller.ui.show_message = MagicMock()

        self.controller.run()
        self.controller.ui.show_message.assert_any_call(self.controller.errors["connect"])

    def test_user_can_disconnect(self):
        self.ws_client.receive = MagicMock(return_value = None)
        self.ui.is_closed = MagicMock(side_effect = [False, True])
        self.controller.run()

        self.ws_client.close.assert_called_with()

    def test_message_passed_to_ui(self):
        message = "Message"
        self.ws_client.receive = MagicMock(side_effect = [message, None])
        self.ui.is_closed = MagicMock(side_effect = [False, True])
        self.controller.run()
        self.ui.show_message.assert_called_with(message)

    def test_message_passed_to_socket(self):
        message = "Message"
        self.ws_client.receive = MagicMock(side_effect = [None])
        self.ui.get_user_input = MagicMock(side_effect = [message, None])
        self.ui.is_closed = MagicMock(side_effect = [False, True])
        self.controller.run()
        self.ws_client.send.assert_called_with(message)


class MessageUtilsTest(TestCase):
    def test_make_message_works_with_correct_args(self):
        message = MessageUtils().make_message("username", "message text")
        self.assertEquals(message, "@username >> message text")

    def test_make_message_raises_exception_no_username(self):
        self.assertRaises(Exception, MessageUtils().make_message, "", "message text")
        self.assertRaises(Exception, MessageUtils().make_message, None, "message text")

    def test_make_message_raises_exception_no_message(self):
        self.assertRaises(Exception, MessageUtils().make_message, "username", "")
        self.assertRaises(Exception, MessageUtils().make_message, "username", None)

    def test_parse_message_works_with_correct_message(self):
        message = "@someuser It's a beautiful day."
        username, message_text = MessageUtils().parse_message(message)
        self.assertEquals(username, "someuser")
        self.assertEquals(message_text, "It's a beautiful day.")

    def test_parse_message_raises_exception_no_message(self):
        message = "@someuser \t "
        self.assertRaises(Exception, MessageUtils().parse_message, message)

    def test_parse_message_raises_exception_no_user(self):
        message = "someuser some message"
        self.assertRaises(Exception, MessageUtils().parse_message, message)


class UserTest(TestCase):
    def test_send_message(self):
        username = "username"
        message_text = "message text"
        connection = MagicMock()

        user = User(username, connection)
        user.send_message(message_text, from_username=username)

        message = MessageUtils().make_message(username, message_text)
        connection.send.assert_called_with(message)

    def test_send_message_sends_to_all_connections(self):
        username = "username"
        message_text = "message text"
        connection1 = MagicMock()
        connection2 = MagicMock()
        user = User(username, connection1)
        user.add_connection(connection2)

        user.send_message(message_text, from_username=username)
        message = MessageUtils().make_message(username, message_text)
        connection1.send.assert_called_with(message)
        connection2.send.assert_called_with(message)

class UserPoolTest(TestCase):
    def test_create_user(self):
        connection = MagicMock()
        user_pool = UserPool()
        user_pool.create_user("username", connection)

        user = user_pool.get_user("username")
        self.assertEquals(user.connections[0], connection)


    def test_create_user_when_username_already_taken(self):
        connection1 = MagicMock()
        connection2 = MagicMock()
        user_pool = UserPool()
        user_pool.create_user("username", connection1)
        user_pool.create_user("username", connection2)

        user = user_pool.get_user("username")
        self.assertEquals(user.connections[0], connection1)
        self.assertEquals(user.connections[1], connection2)


class ChatBackendTest(TestCase):
    def test_process_message_sends_message_to_destination(self):
        message_text = "message"
        from_username = "from_username"
        to_username = "to_username"

        user_pool = UserPool()
        backend = ChatBackend(user_pool)
        ws = MagicMock()
        user_pool.create_user(to_username, ws)
        backend.process_message("@" + to_username +" " + message_text, from_username)
        ws.send.assert_called_with(MessageUtils().make_message(from_username, message_text))




if __name__ == '__main__':
    unittest.main()