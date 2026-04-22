from django.shortcuts import redirect
from django.http import response
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response

from google_auth_oauthlib.flow import Flow
from django.utils import timezone
from datetime import datetime

from .models import UserCalendarCredential 
from .services import get_google_auth_url, generate_state_token, exchange_code_for_tokens
from django.http import HttpResponse
from webhook.services import send_whatsapp_message 

def google_login(request):
    phone_number = request.GET.get('phone')
    # print("CLIENT_ID:", settings.GOOGLE_CLIENT_ID)
    # User visits /auth/google?phone=917820851066
    # request.GET is a dict of URL query parameters

    if not phone_number:
        return HttpResponse("Provide phone number: /auth/google?phone=91XXXXXXXXXX", status=400)

    state = generate_state_token()

    request.session['oauth_state'] = state
    request.session['user_phone']  = phone_number
    # request.session is like a dict that persists across requests FOR THIS USER.
    # Django stores it in the DB and gives the browser a session cookie.
    # On the next request (callback), you can read these values back.
    # We store phone here because it won't be in the URL at the callback stage.

    auth_url = get_google_auth_url(state)
    return redirect(auth_url)
    # redirect() sends HTTP 302. Browser automatically navigates to Google.

def google_callback(request):
    code  = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    # URL looks like: /auth/callback?code=4/ABC123&state=xK9mP...
    # OR if denied:   /auth/callback?error=access_denied&state=xK9mP...

    if error:
        return HttpResponse(f"You denied access: {error}", status=400)

    # CSRF check
    if state != request.session.get('oauth_state'):
        return HttpResponse("Security check failed.", status=400)
    # If someone forged this request, the state won't match what we stored.

    phone_number = request.session.get('user_phone')

    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as e:
        return HttpResponse(f"Token exchange failed: {e}", status=500)

    refresh_token = tokens.get('refresh_token')
    access_token = tokens.get('access_token')
    expires_in = tokens.get('expires_in')
    expiry_time = timezone.now() + timezone.timedelta(seconds=expires_in)
    
    defaults = {
        'access_token': access_token,
        'token_expiry': expiry_time,
    }
    
    # if not refresh_token:
    #     return HttpResponse("No refresh token. Revoke access at myaccount.google.com and retry.", status=400)
    
    if not access_token:
        return HttpResponse("Failed to get access token", status=400)
        
    if refresh_token:
        defaults['refresh_token'] = refresh_token

    UserCalendarCredential.objects.update_or_create(
        phone_number=phone_number,
        defaults=defaults
        # update_or_create:
        # - Looks for a row WHERE phone_number matches
        # - If found  → updates refresh_token
        # - If not found → creates a new row
        # This is atomic — safe, no race conditions, no duplicates
    )

    del request.session['oauth_state']
    del request.session['user_phone']
    # Clean up. No reason to keep this data after we're done.
    send_whatsapp_message(
           phone_number,
           "✅ Google Calendar connected!\n\n"
           "You can now create events by sending me a message like:\n\n"
           "Title: Meeting with friends\n"
           "Start: 6:00pm\n"
           "End: 7:00pm\n"
           "Description: Meeting with school friends\n\n"
           "Date is optional — if you skip it I'll schedule for tomorrow."
    )
    return HttpResponse("✅ Google Calendar connected! You can now send WhatsApp messages.")