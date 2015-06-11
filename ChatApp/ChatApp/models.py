import os
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from django.db import models

class UserModel(models.Model):
    username = models.CharField(unique=True)


