import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_app.settings")

from django.db import models

class UserModel(models.Model):
    username = models.CharField(max_length = 30, unique=True)


    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.sockets = []

class MessageModel(models.Model):
    from_user = models.ForeignKey(to=UserModel, related_name = "sent_messages")
    to_user = models.ForeignKey(to = UserModel, related_name = "received_messages")
    message_text = models.TextField()
    delivered = models.BooleanField(default=False)