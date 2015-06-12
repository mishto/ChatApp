import os
from orm.models import MessageModel
from server import ChatWebSocketServer, user_pool, RouteMessageController
import server

print os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
from orm.models import UserModel
from client import UIController
from server import MessageUtils, UserPool
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


class UserPoolTest(TestCase):
    def test_create_user(self):
        connection = MagicMock()
        user_pool = UserPool()
        user_pool.register_user("username", connection)

        user = user_pool.find_user("username")
        self.assertEquals(user.sockets[0], connection)


    def test_create_user_when_username_already_taken(self):
        ws1 = MagicMock()
        ws2 = MagicMock()
        user_pool = UserPool()
        user_pool.register_user("username", ws1)
        user_pool.register_user("username", ws2)

        user = user_pool.find_user("username")
        self.assertEquals(set(user.sockets), {ws1, ws2})

    def test_user_removed_from_pool_on_all_ws_close(self):
        ws1 = MagicMock()
        ws2 = MagicMock()
        user_pool = UserPool()
        user_pool.register_user("username", ws1)
        user_pool.register_user("username", ws2)

        user = user_pool.find_user("username")
        self.assertEquals(set(user.sockets), {ws1, ws2})

        user_pool.unregister("username", ws1)

        user = user_pool.find_user("username")
        self.assertEquals(user.sockets, [ws2])

        user_pool.unregister("username", ws2)
        self.assertFalse ("username" in user_pool.user_models)



class MessageControllerTest(TestCase):
    def setUp(self):
        server.user_pool = UserPool()

    def test_route_message_sends_message_to_every_user_socket(self):
        ws1 = MagicMock()
        ws2 = MagicMock()
        controller = RouteMessageController()

        from_user = UserModel(username = "from_user")
        from_user.save()

        server.user_pool.register_user("to_user", ws1)
        server.user_pool.register_user("to_user", ws2)

        controller.send_message("@to_user some message", from_user)

        ws1.send.assert_called_with(MessageUtils().make_message("from_user", "some message"))
        ws2.send.assert_called_with(MessageUtils().make_message("from_user", "some message"))


    def test_send_message_saves_message_when_user_in_pool(self):
        ws = MagicMock()
        controller = RouteMessageController()

        from_user = UserModel(username = "from_user")
        from_user.save()

        server.user_pool.register_user("to_user", ws)
        controller.send_message("@to_user some message", from_user)
        self.assertEquals(MessageModel.objects.count(), 1)
        self.assertTrue(MessageModel.objects.get().delivered)

    def test_send_message_saves_message_when_user_in_database(self):
        controller = RouteMessageController()

        from_user = UserModel(username = "from_user")
        from_user.save()

        from_user = UserModel(username = "to_user")
        from_user.save()


        controller.send_message("@to_user some message", from_user)
        self.assertEquals(MessageModel.objects.count(), 1)


    def test_process_message_sends_alert_when_user_not_found(self):
        ws = MagicMock()
        ws.send = MagicMock()

        user_pool.register_user("from_user", ws)

        from_user = UserModel(username = "to_user")
        from_user.save()

        RouteMessageController().process_message("@wrong_user some message", ws)
        self.assertEquals(MessageModel.objects.count(), 0)
        ws.send.assert_called_with("User does not exist.")


class ChatWebSocketServerTest(TestCase):
    def setUp(self):
        server.user_pool = UserPool()

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
        ws2.send.assert_called_with(MessageUtils().make_message("from_user", "secret message"))

    def test_messages_not_delivered_after_user_closes_connection(self):
        ws1 = ChatWebSocketServer(MagicMock())
        ws1.received_message("from_user")
        ws2 = ChatWebSocketServer(MagicMock())
        ws2.send = MagicMock()
        ws2.received_message("to_user")

        ws2.closed(1000)

        ws1.received_message("@to_user secret message")

        self.assertEquals(MessageModel.objects.count(), 1)
        self.assertEquals(MessageModel.objects.get().message_text, "secret message")
        self.assertFalse(MessageModel.objects.get().delivered)

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


    def test_user_receives_offline_messages_when_connecting(self):
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