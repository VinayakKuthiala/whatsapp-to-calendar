from django.urls import path
from . import views

urlpatterns = [
    path('webhook', views.WhatsAppWebhookView.as_view(), name='webhook'),
    path('webhook/', views.WhatsAppWebhookView.as_view(), name='webhook'),
]