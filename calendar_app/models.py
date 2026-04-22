from django.db import models

class UserCalendarCredential(models.Model):
    phone_number = models.CharField(max_length = 20, unique = True)
    access_token = models.TextField() #short lived 1hour
    # These come from Google after OAuth:
    refresh_token = models.TextField()    # long lived (forever until revoked)
    token_expiry  = models.DateTimeField()