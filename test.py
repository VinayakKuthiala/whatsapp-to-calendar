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
def parse_event_from_message(text: str) -> dict | str:
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

    known_fields = ['title', 'date', 'start', 'end', 'description', 'desc', 'note', 'notes']
    for field in known_fields:
        pattern = rf'^\s*{re.escape(field)}\s*[;\-=]\s*(.+)$'
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return (
                "Please use : not ;/-/=/ as the separator. Example:\n\n"
                "Title: Meeting with friends\n"
                "Date: 25/4/2026\n"
                "Start: 6:00pm\n"
                "End: 7:00pm"
            )



    # ---Rule 1: Title is required — if not found, return None---
    if not title: 
        return "Title is required. Please include:\nTitle: Your event name"

    today = datetime.now()
    
    from django.utils import timezone
    # today = timezone.localtime(timezone.now()).replace(tzinfo=None)
    
    #--- Parse date if given ---
    if date_str:
        event_date = parse_date_string(date_str)
        if event_date is None:
            return (
                "Could not understand the date. Try formats like:\n"
                "Date: 25/4/2026\n"
                "Date: tomorrow\n"
                "Date: next friday"
            )
        if event_date < today.date():
            return (
                "That date has already passed. Please set a date in the future or for Today."
            )
            
    else:
        event_date = None #For now none because date depends on current timing

    #--- Parse start time if given ---
    if start_str:
        time_struct,staus = cal.parse(start_str)
        if staus == 0:
            return (
                "❌ Could not understand the start time. Try:\n"
                "Start: 4pm\nStart: 16:00"
            )
        parsed_start = datetime(*time_struct[:6])
        start_hour   = parsed_start.hour
        start_minute = parsed_start.minute
        if event_date == today.date() and today.hour > start_hour and today.minute > start_minute:
            return (
                f"❌ {start_hour:02d}:{start_minute:02d} has already passed for today. "
                f"Please set a time in the future, or set a date in future:\n"
                f"Date: tomorrow"
            )
    else:
        start_hour, start_minute = None, None # Default start_time depends on the curr time

    #--- Parse end time ---
    if end_str:
        time_struct,staus = cal.parse(end_str)
        if staus == 0:
            return (
                "❌ Could not understand the end time. Try:\n"
                "End: 4pm\nEnd: 16:00"
            )
        
        parsed_end = datetime(*time_struct[:6])
        end_hour   = parsed_end.hour
        end_minute = parsed_end.minute
    else:
        end_hour, end_minute = None, None # Default end_time depends on the curr time and if end+1 <8pm

    #--- Rule 2 : if no date given, no time given start_time = next hr iff next hr < 8pm else tomorrow 8am-9am
    current_hour = today.hour
    current_minute = today.minute
    if event_date is None and start_hour is None:
        next_hour = current_hour+1

        if next_hour < 20: #that is nexthour < 8pm 
            event_date = today.date()
            start_hour = next_hour
            start_minute = 0
            end_hour = next_hour + 1
            end_minute = 0
        else:
            event_date = (today + timedelta(days = 1)).date()
            start_hour = 8
            start_minute = 0
            end_hour = 9
            end_minute = 0

    #--- Rule 3: Date given and time not given -> if curr_time < 8am timings = 8am-9am else start = next_hr
    elif event_date is not None and start_hour is None:
        if event_date == today.date() : #If date is today check if 8am has passed else set the time = next hr
            if current_hour < 8:
                start_hour   = 8
                start_minute = 0
                end_hour     = 9
                end_minute   = 0
            else:
                next_hour    = current_hour + 1
                start_hour   = next_hour
                start_minute = 0
                end_hour     = next_hour + 1
                end_minute   = 0
        else: #if date is not today set default time as 8am-9am
            start_hour   = 8
            start_minute = 0
            end_hour     = 9
            end_minute   = 0

    #--- Rule 4: No date given but time given set the time iff start_time > curr_time else throw error
    elif event_date is None and start_hour is not None:
            current_total = current_hour * 60 + current_minute
            start_total   = start_hour   * 60 + start_minute
            if current_total < start_total:
                event_date = today.date()   # time is in the future today ✅
            else:
                return (
                    f"❌ {start_hour:02d}:{start_minute:02d} has already passed today. "
                    f"Please set a time in the future, or include a date:\n"
                    f"Date: tomorrow"
                )

    #--- fill end_hour if its still not set---
    if end_hour is None:
        end_hour   = start_hour + 1
        end_minute = start_minute

    start_datetime = datetime(event_date.year, event_date.month, event_date.day, start_hour, start_minute)
    end_datetime   = datetime(event_date.year, event_date.month, event_date.day, end_hour,   end_minute)

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

msg = """Title: Meeting with friends\n
"""

print(parse_event_from_message(msg))

from datetime import datetime
print("-------------------------")
print(datetime.now())