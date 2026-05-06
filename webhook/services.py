import logging
from parser.services import parse_event_from_message

from calendar_app.models import UserCalendarCredential
from calendar_app.services import create_calendar_event


logger = logging.getLogger(__name__)

def handle_message(phone_number: str, text: str):
    text_lower = text.strip().lower()
    # User comes for the first time 
    if text_lower in ['start', 'setup', 'connect', 'hello', 'hi']:
        send_whatsapp_message(
            phone_number=phone_number,
            message=(
                "Welcome! To create calendar events,"
                "first connect your Google Calendar here:\n\n"
                f"https://smartness-rekindle-alright.ngrok-free.dev/auth/google/?phone={phone_number}"
            )
        )
        return  # Stop here
        
    try:
        credentials = UserCalendarCredential.objects.get(phone_number = phone_number)
    except UserCalendarCredential.DoesNotExist:
        send_whatsapp_message(
            phone_number=phone_number,
            message=(
                "It seems you haven't connected your Google Calendar yet."
                "first connect your Google Calendar here:\n\n"
                f"https://smartness-rekindle-alright.ngrok-free.dev/auth/google/?phone={phone_number}"
            )
        )
        return  # Stop here

    from calendar_app.services import get_user_token, create_calendar_event
    token = get_user_token(phone_number)
    if not token:
        # We don't have their token they haven't done setup yet
        send_whatsapp_message(
            phone_number=phone_number,
            message="❌ You haven't connected your Google Calendar yet. Send 'start' to begin."
        )
        return

    # Parse the message text into structured event data
    event_data = parse_event_from_message(text)

    # if not event_data:
    #     # Parser couldn't find a date/time in the message
    #     send_whatsapp_message(
    #         phone_number=phone_number,
    #         message="I couldn't understand the message."
    #     )
    #     return

    if isinstance(event_data,str): #check if there was an error that is a string was being sent
        send_whatsapp_message(phone_number, event_data)
        return
    # Everything looks good — create the event!
    event_link = create_calendar_event(access_token=token, event_data=event_data, phone_number=phone_number)

    send_whatsapp_message(
        phone_number=phone_number,
        message=f"Event created! View it here: {event_link}.\n\nThe event was created on your primary calendar."
    )


def send_whatsapp_message(phone_number: str, message: str):
    import requests
    from django.conf import settings
    
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=payload)
    print("STATUS:", response.status_code)
    print("BODY:", response.text)