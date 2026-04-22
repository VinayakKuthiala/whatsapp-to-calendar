from django.urls import path
from . import views

urlpatterns = [
    path('auth/google/',    views.google_login,    name='google_login'),
    path('auth/google/callback',  views.google_callback, name='google_callback'),
]