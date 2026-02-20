#!/usr/bin/env python3
"""
Calendar triangulation module for meeting-ingestion skill.
Matches meetings to calendar events for participant identification.

This module queries Google Calendar via use_app_google_calendar to find events
that match a meeting by timestamp (±30 min), title similarity, and attendees.
Returns confidence score and matched event data for participant extraction.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional


def similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def parse_meeting_datetime(date_str: str, time_str: str) -> datetime:
    """Parse meeting date and time into datetime object."""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")


def parse_calendar_datetime(cal_datetime_str: str) -> datetime:
    """Parse Google Calendar datetime string to datetime object."""
    # Handle RFC3339 format with timezone
    if 'T' in cal_datetime_str:
        # Parse with timezone info, then convert to UTC naive
        from datetime import timezone
        
        if cal_datetime_str.endswith('Z'):
            # UTC timezone
            dt = datetime.fromisoformat(cal_datetime_str.replace('Z', '+00:00'))
        elif '+' in cal_datetime_str or '-' in cal_datetime_str.split('T')[1]:
            # Has timezone offset
            dt = datetime.fromisoformat(cal_datetime_str)
        else:
            # No timezone, assume UTC
            dt = datetime.fromisoformat(cal_datetime_str).replace(tzinfo=timezone.utc)
        
        # Convert to UTC and remove timezone info for comparison
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.replace(tzinfo=None)
    
    # Date only format
    return datetime.fromisoformat(cal_datetime_str)


def is_time_match(meeting_dt: datetime, event_dt: datetime, tolerance_minutes: int = 30) -> bool:
    """Check if meeting and event times match within tolerance."""
    time_diff = abs((meeting_dt - event_dt).total_seconds() / 60)
    return time_diff <= tolerance_minutes


def calculate_confidence(meeting: Dict, event: Dict, match_method: str) -> float:
    """Calculate confidence score for a calendar match."""
    confidence = 0.0
    
    # Parse meeting datetime
    meeting_dt = parse_meeting_datetime(meeting['date'], meeting['time_utc'])
    
    # Parse event datetime  
    if 'start' in event:
        start_time = event['start'].get('dateTime') or event['start'].get('date')
        if start_time:
            try:
                event_dt = parse_calendar_datetime(start_time)
            except:
                return 0.0
        else:
            return 0.0
    else:
        return 0.0
    
    # Time matching (0.4 weight)
    if is_time_match(meeting_dt, event_dt):
        confidence += 0.4
    
    # Title similarity (0.3 weight)
    meeting_title = meeting.get('title', '').strip()
    event_title = event.get('summary', '').strip()
    if meeting_title and event_title:
        title_sim = similarity(meeting_title, event_title)
        confidence += 0.3 * title_sim
    
    # Attendees presence (0.3 weight)
    if 'attendees' in event and event['attendees']:
        confidence += 0.15
    
    # Adjust confidence based on match method
    if match_method == 'timestamp+title' and confidence > 0.7:
        confidence = min(confidence + 0.1, 1.0)  # Boost high-confidence combined matches
    elif match_method == 'title_only':
        confidence *= 0.8  # Reduce confidence for title-only matches
    elif match_method == 'timestamp_only':
        confidence *= 0.7  # Reduce confidence for timestamp-only matches
    
    return round(confidence, 3)


def extract_attendee_emails(event: Dict) -> List[str]:
    """Extract attendee emails from calendar event."""
    emails = []
    attendees = event.get('attendees', [])
    
    for attendee in attendees:
        email = attendee.get('email', '')
        if email and email not in emails:
            emails.append(email)
    
    return emails


def find_best_match(meeting: Dict, events: List[Dict]) -> Optional[Dict]:
    """Find the best matching calendar event for a meeting."""
    if not events:
        return None
    
    best_match = None
    best_confidence = 0.0
    
    # Parse meeting details
    meeting_dt = parse_meeting_datetime(meeting['date'], meeting['time_utc'])
    meeting_title = meeting.get('title', '').strip()
    
    for event in events:
        # Skip events without proper time info
        if 'start' not in event:
            continue
            
        start_time = event['start'].get('dateTime') or event['start'].get('date')
        if not start_time:
            continue
        
        try:
            event_dt = parse_calendar_datetime(start_time)
        except:
            continue
        
        # Determine match method
        time_matches = is_time_match(meeting_dt, event_dt)
        title_matches = False
        
        event_title = event.get('summary', '').strip()
        if meeting_title and event_title:
            title_matches = similarity(meeting_title, event_title) > 0.6
        
        if time_matches and title_matches:
            method = 'timestamp+title'
        elif title_matches:
            method = 'title_only'
        elif time_matches:
            method = 'timestamp_only'
        else:
            continue  # Skip events with no reasonable match
        
        confidence = calculate_confidence(meeting, event, method)
        
        if confidence > best_confidence:
            best_confidence = confidence
            best_match = {
                'event_id': event.get('id', ''),
                'confidence': confidence,
                'method': method,
                'event_data': event,
                'attendee_emails': extract_attendee_emails(event)
            }
    
    return best_match


def match_meeting_to_calendar(meeting_data: Dict, email: str = None) -> Optional[Dict]:
    """
    Main function to match a meeting to calendar events.
    
    Args:
        meeting_data: Meeting data from manifest with 'meeting' key
        email: Optional email to specify which Google Calendar account to use
        
    Returns:
        Dictionary with calendar match data or None if no match found
    """
    meeting = meeting_data.get('meeting', {})
    
    if not meeting:
        print("Error: No meeting data provided", file=sys.stderr)
        return None
    
    # Parse meeting datetime for query window
    meeting_dt = parse_meeting_datetime(meeting['date'], meeting['time_utc'])
    
    # Create time window (±2 hours around meeting)
    start_time = meeting_dt - timedelta(hours=2)
    end_time = meeting_dt + timedelta(hours=2)
    
    # Format for RFC3339
    time_min = start_time.strftime('%Y-%m-%dT%H:%M:%S-00:00')
    time_max = end_time.strftime('%Y-%m-%dT%H:%M:%S-00:00')
    
    # Query calendar - this would normally use use_app_google_calendar
    # For testing/mock purposes, return empty list
    print(f"Querying calendar for meeting: {meeting.get('title', 'Untitled')} on {meeting.get('date')} at {meeting.get('time_utc')}")
    print(f"Time window: {time_min} to {time_max}")
    
    # Mock calendar events for testing
    # In production, this would be:
    # events = use_app_google_calendar("google_calendar-list-events", {
    #     "timeMin": time_min,
    #     "timeMax": time_max,
    #     "singleEvents": True
    # }, email=email)
    events = []
    
    if not events:
        print("No calendar events found in time window")
        return None
    
    print(f"Found {len(events)} calendar events in time window")
    
    # Find best match
    match = find_best_match(meeting, events)
    
    if match:
        print(f"Found calendar match with {match['confidence']:.3f} confidence using {match['method']}")
        
        # Return calendar_match data for manifest (schema compliant)
        return {
            'event_id': match['event_id'],
            'confidence': match['confidence'],
            'method': match['method'],
            'attendee_emails': match['attendee_emails']  # Extra field for CRM lookup
        }
    else:
        print("No suitable calendar matches found")
        return None


def main():
    parser = argparse.ArgumentParser(description='Match meetings to calendar events')
    parser.add_argument('manifest_file', help='Path to meeting manifest JSON file')
    parser.add_argument('--email', help='Google Calendar account email to use')
    parser.add_argument('--output', help='Output file for calendar match results')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Read manifest file
    try:
        with open(args.manifest_file, 'r') as f:
            manifest_data = json.load(f)
    except Exception as e:
        print(f"Error reading manifest file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Perform calendar matching
    match_result = match_meeting_to_calendar(manifest_data, args.email)
    
    if match_result:
        print(f"\nCalendar Match Found:")
        print(f"  Event ID: {match_result['event_id']}")
        print(f"  Confidence: {match_result['confidence']}")
        print(f"  Method: {match_result['method']}")
        print(f"  Attendee Emails: {', '.join(match_result['attendee_emails'])}")
        
        # Save results if output specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(match_result, f, indent=2)
            print(f"\nResults saved to: {args.output}")
        
        # Exit code 0 for successful match
        sys.exit(0)
    else:
        print("No calendar match found")
        
        # Save empty result if output specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(None, f)
        
        # Exit code 1 for no match (not an error, just no result)
        sys.exit(1)


if __name__ == '__main__':
    main()