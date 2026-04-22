# parser/services.py

import parsedatetime
from datetime import datetime, timedelta
import re

cal = parsedatetime.Calendar()


def parse_date_string(date_str: str):
    """
    Tries multiple date formats before falling back to parsedatetime.
    parsedatetime assumes MM/DD/YYYY (American format).
    Indians write DD/MM/YYYY so "25/4/2026".
    """

    exact_formats = [
        "%d/%m/%Y",    # 25/4/2026  or  25/04/2026  ← Indian format
        "%d-%m-%Y",    # 25-4-2026
        "%d/%m/%y",    # 25/4/26
        "%d-%m-%y",    # 25-4-26
        "%Y-%m-%d",    # 2026-04-25  ← ISO format
        "%d %B %Y",    # 25 April 2026
        "%d %b %Y",    # 25 Apr 2026
        "%B %d %Y",    # April 25 2026
    ]

    for fmt in exact_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue    

    #  No exact format matched  try natural language 
    # This handles: "tomorrow", "next friday", "monday", "in 3 days" etc.
    time_struct, status = cal.parse(date_str)
    if status == 0:
        return None     # parsedatetime also couldn't understand it
        
    return datetime(*time_struct[:6]).date()
def parse_event_from_message(text: str) -> dict | None:
    """
    Parses a structured WhatsApp message like:
    
    Title: Meeting with friends
    Date: 22/4/2026
    Start: 8:00am
    End: 12:00pm
    Description: meeting about life with friends
    
    All fields are optional except Title.
    """

    # ── STEP 1: Extract each field from the message ──

    title       = extract_field(text, ['title', ])
    date_str    = extract_field(text, ['date'])
    start_str   = extract_field(text, ['start', 'start time', 'from'])
    end_str     = extract_field(text, ['end', 'end time', 'to'])
    description = extract_field(text, ['description', 'desc', 'note', 'notes'])

    # Title is required — if not found, return None
    if not title:
        return None

    # ── STEP 2: Parse the date ──

    today = datetime.now()

    if date_str:
        # User gave a date — parse it (handles "22/4/2026", "tomorrow", "next friday" etc)
        event_date = parse_date_string(date_str)
        if event_date is None:
            event_date = today.date()   # fallback to today if unparseable
    else:
        # No date given
        # If current time is already past 8am, default to tomorrow
        if today.hour >= 8:
            event_date = (today + timedelta(days=1)).date()
        else:
            event_date = today.date()

    # ── STEP 3: Parse start time ──

    if start_str:
        # User gave a start time — parse it (handles "8:00am", "midnight", "afternoon", "3pm" etc)
        time_struct, status = cal.parse(start_str)
        if status == 0:
            start_hour, start_minute = 8, 0     # fallback to 8am
        else:
            parsed_start = datetime(*time_struct[:6])
            start_hour   = parsed_start.hour
            start_minute = parsed_start.minute
    else:
        # No start time given — default 8:00am
        start_hour, start_minute = 8, 0

    # ── STEP 4: Parse end time ──

    if end_str:
        # User gave an end time — parse it
        time_struct, status = cal.parse(end_str)
        if status == 0:
            # Fallback: start + 1 hour
            end_hour   = start_hour + 1
            end_minute = start_minute
        else:
            parsed_end = datetime(*time_struct[:6])
            end_hour   = parsed_end.hour
            end_minute = parsed_end.minute
    else:
        # No end time — start + 1 hour
        end_hour   = start_hour + 1
        end_minute = start_minute

    # ── STEP 5: Combine date + time into full datetime objects ──

    start_datetime = datetime(
        year=event_date.year,
        month=event_date.month,
        day=event_date.day,
        hour=start_hour,
        minute=start_minute
    )

    end_datetime = datetime(
        year=event_date.year,
        month=event_date.month,
        day=event_date.day,
        hour=end_hour,
        minute=end_minute
    )

    # Handle midnight edge case — if end goes past midnight
    if end_datetime <= start_datetime:
        end_datetime = start_datetime + timedelta(hours=1)

    return {
        'summary'    : title,
        'start'      : start_datetime,
        'end'        : end_datetime,
        'description': description or title,
    }


def extract_field(text: str, field_names: list) -> str | None:
    """
    Searches the message for a field like "Title: something"
    and returns "something".
    
    field_names is a list because users might write
    "start", "start time", "from" — all meaning the same thing.
    
    Example:
        text = "Title: Meeting\nDate: tomorrow\nStart: 3pm"
        extract_field(text, ['title']) → "Meeting"
        extract_field(text, ['date'])  → "tomorrow"
        extract_field(text, ['start', 'start time']) → "3pm"
    """

    for field in field_names:
        # Build a regex pattern that matches "fieldname : value" or "fieldname: value"
        # re.IGNORECASE makes it work for "Title", "TITLE", "title" etc
        # re.MULTILINE makes ^ and $ match start/end of each line
        pattern = rf'^\s*{re.escape(field)}\s*:\s*(.+)$'
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        if match:
            return match.group(1).strip()
            # group(1) is the captured group — the value after the colon
            # .strip() removes any extra spaces
    
    return None     # field not found in message
    
msg = """
Title: Meeting with friends
Date: 29 Apr 2025
Start: 8:00am
End: 12:00pm
"""
msg = """
Title: happy
    Date: 23/4/2026
    Description: meeting about life with friends"""
print(parse_event_from_message(msg))