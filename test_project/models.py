from django.db import models


class User(models.Model):
    """
    User model
    """
    email = models.CharField(max_length=256)
