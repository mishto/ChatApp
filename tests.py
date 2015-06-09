import unittest
from ChatClient import UIController, ChatConsoleUI
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

if __name__ == '__main__':
    unittest.main()