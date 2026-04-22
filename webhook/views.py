from django.shortcuts import render

from .services import handle_message
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.http import HttpResponse
from .services import send_whatsapp_message, handle_message
import json


VERIFY_TOKEN = "whatsapp_chatbot"  

class WhatsAppWebhookView(APIView):
    
    # Meta calls this ONCE to verify your server
    # https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint
    authentication_classes = []      
    permission_classes = [AllowAny]
    def get(self, request):
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge)  # Echo back the challenge
        return Response(status=status.HTTP_403_FORBIDDEN)
    
    # Meta calls this every time a user sends a message
    def post(self, request):
        data = request.data
        print("CALLING SEND FUNCTION")
        # Navigate the nested JSON to get the message text
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' not in value:
                return Response({"status": "not a message"}, status=status.HTTP_200_OK)
            message = value['messages'][0]
            
            phone_number = message['from']           # Sender's number
            
            msg_type     = message['type']
            if msg_type != 'text':
                return Response({"status": "non-text ignored"}, status=status.HTTP_200_OK)
            
            text = message['text']['body']          # Actual message on whatsapp
            # Parse the text and create calendar event
            handle_message(phone_number, text)
            
        except (KeyError, IndexError):
            pass  # Not a text message, ignore
        
        return Response({"status": "ok"})  # Always return 200 to Meta
