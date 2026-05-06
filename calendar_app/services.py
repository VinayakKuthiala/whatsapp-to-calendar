import secrets
from urllib.parse import urlencode
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from django.conf import settings
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.errors import HttpError
from calendar_app.models import UserCalendarCredential
from django.utils import timezone
from datetime import timedelta

def refresh_google_token(credential):
    try:
        cred = Credentials(
            credential.access_token,
            refresh_token=credential.refresh_token,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            token_uri=settings.GOOGLE_TOKEN_URI, # "https://oauth2.googleapis.com/token"
        )
        cred.refresh(GoogleRequest())
        credential.access_token = cred.token
        credential.token_expiry = cred.expiry
        credential.save(update_fields=['access_token', 'token_expiry'])
        return cred.access_token
    except Exception as e:
        return None


def get_user_token(phone_number: str):
    try:
        credential = UserCalendarCredential.objects.get(phone_number=phone_number)
    except UserCalendarCredential.DoesNotExist:
        return None
        
    if credential.token_expiry > timezone.now()+timedelta(minutes=1): #token hasn't expired yet
        return credential.access_token
    else:
        return refresh_google_token(credential)
    
    
def generate_state_token():
    return secrets.token_urlsafe(32)
    # secrets module is for security-sensitive randomness. dont use random.random()
    # This returns something like "xK9mP2nQrT5vW3yA1bC4dE6fG7hJ0kL"
    
def get_google_auth_url(state):
    params = {
        'client_id'     : settings.GOOGLE_CLIENT_ID, # Tells Google which app is asking. Shows your app name on consent screen.

        'redirect_uri'  : settings.GOOGLE_REDIRECT_URI, # Where to send the user AFTER they approve. Must exactly match
                                                        # what you registered in Google Cloud Console. Even a trailing slash breaks it.

        'response_type' : 'code', # We want an authorization CODE back, not the token directly.
                                # The code travels through the browser. Tokens never should.

        'scope'         : 'https://www.googleapis.com/auth/calendar.events', 
        # Exactly what permission we need. We only ask for events,
        # not full calendar access. Users trust limited scopes more.

        'access_type'   : 'offline',
        # CRITICAL. Without this, Google won't give a refresh_token.
        # offline = our app needs to work even when the user isn't actively using it.

        'state'         : state,
        # Random string for CSRF protection. Google echoes it back unchanged.
        # We verify it in the callback. If it doesn't match, reject the request.

        'prompt'        : 'consent',
        # Forces the consent screen to always show.
        # Without this, if user authorized before, Google skips the screen
        # and doesn't send a refresh_token. Your app silently breaks.
    }
    return f"{settings.GOOGLE_AUTH_URI}?{urlencode(params)}"   


def exchange_code_for_tokens(code):
    response = requests.post(settings.GOOGLE_TOKEN_URI, data={
        'code'          : code,
        # The one-time code Google sent us. Expires in ~10 minutes.

        'client_id'     : settings.GOOGLE_CLIENT_ID,
        'client_secret' : settings.GOOGLE_CLIENT_SECRET,
        # client_secret is what makes this secure. Only YOUR server knows it.
        # Anyone can intercept the code in the URL, but it's useless
        # without the client_secret to exchange it.

        'redirect_uri'  : settings.GOOGLE_REDIRECT_URI,
        # Google cross-checks this matches the original request.

        'grant_type'    : 'authorization_code',
        # Tells Google what kind of exchange: "I have a code, give me tokens"
    })

    response.raise_for_status()
    # If Google returns an error, crash immediately with a clear exception.
    # Without this, you'd silently continue with broken data and get weird bugs.

    return response.json()
    # Returns:
    # {
    #   'access_token':  'ya29.a0...',   <- use this for API calls (1 hour)
    #   'refresh_token': '1//0gAbc...',  <- store this forever in DB
    #   'expires_in':    3600
    # }


def create_calendar_event(access_token, event_data, phone_number=None):
    credentials = Credentials(token=access_token)

    service = build('calendar', 'v3', credentials=credentials) # build() creates an SDK-like object with methods for every Calendar API endpoint. Think of it as: "give me a Google Calendar client I can call methods on"
    
    event_body = {
        'summary': event_data['summary'],   # event title
        "description": event_data['description'],
        'start': {
            'dateTime': event_data['start'].isoformat(), # isoformat() converts Python datetime to "2024-01-20T19:00:00"
            'timeZone': 'Asia/Kolkata',
            # Always set timezone or Google assumes UTC and your events
            # show at wrong times
        },
        'end': {
            'dateTime': event_data['end'].isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
    }
    try:
        created_event = service.events().insert(
            calendarId='primary',   # user's main calendar
            body=event_body
        ).execute() # .execute() is what actually sends the HTTP request. # Everything before it just builds the request object.
        return created_event.get('htmlLink')  # Returns URL like: https://calendar.google.com/event?eid=abc123 # Send this back to the user on WhatsApp as confirmation
    except HttpError as e:
        if e.resp.status == 401 and phone_number:
            #token expired
            new_token = get_user_token(phone_number)
            if not new_token:
                return None
            credentials = Credentials(token = new_token)
            service = build('calendar', 'v3', credentials=credentials)
            created_event = service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            return created_event.get('htmlLink')
        print("Google API error:", e)
        raise 
