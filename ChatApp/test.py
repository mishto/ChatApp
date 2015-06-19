import gc
from greenlet import greenlet
import gevent
from gevent.greenlet import Greenlet
import os
from orm.models import MessageModel
from server import ChatWebSocketServer, ChatMessageController
import server
from orm.models import UserModel
from client import UIController
from server import MessageUtils
from mock import MagicMock, call
from django.test import TestCase



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


class ChatMessageControllerTest(TestCase):
    def setUp(self):
        kill_greenlets()
        self.from_user = UserModel.objects.create(username = "from_user")
        self.to_user = UserModel.objects.create(username = "to_user")

    def test_route_message_sends_message_to_every_user_socket(self):
        ws = MagicMock()
        ws.user = self.from_user
        ws1 = MagicMock()
        ws2 = MagicMock()

        server.redis_adapter.add_connection("to_user", ws1)
        server.redis_adapter.add_connection("to_user", ws2)
        server.redis_adapter.store_user(self.to_user)
        controller = ChatMessageController()

        controller.process_message("@to_user some message", ws)

        ws1.send.assert_called_with(MessageUtils().make_message("from_user", "some message"))
        ws2.send.assert_called_with(MessageUtils().make_message("from_user", "some message"))


    def test_send_message_saves_message_when_user_in_pool(self):
        controller = ChatMessageController()

        ws = MagicMock()
        ws.user = self.from_user

        server.redis_adapter.store_user(self.to_user)
        server.redis_adapter.add_connection("to_user", MagicMock())

        controller.process_message("@to_user some message", ws)

        self.assertEquals(MessageModel.objects.count(), 1)
        self.assertTrue(MessageModel.objects.get().delivered)

    def test_send_message_saves_message_when_user_in_database(self):
        controller = ChatMessageController()

        ws = MagicMock()
        ws.user = self.from_user

        controller.process_message("@to_user some message", ws)
        self.assertEquals(MessageModel.objects.count(), 1)


    def test_process_message_sends_alert_when_user_not_found(self):
        ws = MagicMock()
        ws.send = MagicMock()

        ChatMessageController().process_message("@wrong_user some message", ws)
        self.assertEquals(MessageModel.objects.count(), 0)
        ws.send.assert_called_with('UserModel matching query does not exist.')

    def test_sends_error_message_when_cannot_parse_msg(self):
        ws = MagicMock()
        ws.send = MagicMock()

        ChatMessageController().process_message("bad message", ws)
        self.assertEquals(MessageModel.objects.count(), 0)
        ws.send.assert_called_with("Message could not be parsed.")


class ChatWebSocketServerTest(TestCase):
    def setUp(self):
        kill_greenlets()
        server.redis_adapter = server.RedisAdapter()

    def test_user_created_when_first_auth(self):
        ws = ChatWebSocketServer(MagicMock())
        ws.received_message("my_username")

        self.assertEquals(UserModel.objects.count(), 1)
        self.assertEquals(UserModel.objects.all()[0].username, "my_username")

    def test_user_not_created_when_username_invalid(self):
        ws = ChatWebSocketServer(MagicMock())
        ws.received_message("bad username")

        self.assertEquals(UserModel.objects.count(), 0)


    def test_user_receives_message(self):
        #auth from_user
        ws1 = ChatWebSocketServer(MagicMock())
        ws1.received_message("from_user")

        #auth to_user
        ws2 = ChatWebSocketServer(MagicMock())
        ws2.opened()
        ws2.send = MagicMock()
        ws2.received_message("to_user")

        #from_user socket received message for to_user
        ws1.received_message("@to_user secret message")

        #message has been saved
        self.assertEquals(MessageModel.objects.count(), 1)
        self.assertEquals(MessageModel.objects.get().message_text, "secret message")

        #message has been saved as delivered
        self.assertTrue(MessageModel.objects.get().delivered)

        #and indeed the send function for to_user has been called
        calls = [call("Authentication successful.  Write a message like this: '@username your message' "),
                 call(MessageUtils().make_message("from_user", "secret message"))]

        ws2.send.assert_has_calls(calls)


    def test_socket_closed_checks_for_un_authenticated_user(self):
        ws1 = ChatWebSocketServer(MagicMock())

        #should work w/o raising error
        ws1.closed(1000)


    def test_user_can_diconnect_and_connect_again(self):
        ws = ChatWebSocketServer(MagicMock())
        ws.received_message("to_user")
        ws.closed(1000)

        ws = ChatWebSocketServer(MagicMock())
        ws.received_message("to_user")


    def _test_user_receives_offline_messages_when_connecting(self):
        ws1 = ChatWebSocketServer(MagicMock())
        ws1.received_message("from_user")

        #connecting and disconnecting to_user
        ws2 = ChatWebSocketServer(MagicMock())
        ws2.send = MagicMock()
        ws2.received_message("to_user")
        ws2.closed(1000)

        #to_user receives a message while offline
        ws1.received_message("@to_user first message")
        ws1.received_message("@to_user second message")

        #message has been set to not delivered in DB
        offline_messages = MessageModel.objects.filter()
        self.assertFalse(offline_messages[0].delivered)
        self.assertFalse(offline_messages[1].delivered)

        #connecting to_user again
        ws2 = ChatWebSocketServer(MagicMock())
        ws2.send = MagicMock()
        ws2.received_message("to_user")

        #message has been set to delivered in DB
        offline_messages = MessageModel.objects.filter()
        self.assertTrue(offline_messages[0].delivered)
        self.assertTrue(offline_messages[1].delivered)


        #and has been actually delivered

        calls = [call(MessageUtils().make_message("from_user", "first message")),
                 call(MessageUtils().make_message("from_user", "second message"))]
        ws2.send.assert_has_calls(calls, any_order=True)


class DataStoreAdapterTest(TestCase):
    def test_send_message_to_channel(self):
        ws = MagicMock()
        ds = server.RedisAdapter()
        ds.add_connection("username", ws)

        #should publish on redis
        ds.send_message_to_channel("username", "message")

        ws.send.assert_called_with("message")

def kill_greenlets():
    for ob in gc.get_objects():
        if isinstance(ob, Greenlet):
            ob.kill()