from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.integration import Integration, IntegrationType

def create_calendar_event(db: Session, workspace_id: int, booking_data: dict):
    """Create Google Calendar event for booking"""
    try:
        # Get calendar integration
        integration = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.CALENDAR,
            Integration.is_active == True
        ).first()
        
        if not integration:
            print("⚠️ Calendar integration not configured")
            return {"success": False, "error": "Calendar not configured"}
        
        # Get credentials from integration config
        creds_data = integration.config.get('credentials')
        if not creds_data:
            return {"success": False, "error": "No credentials found"}
        
        # Build credentials
        creds = Credentials.from_authorized_user_info(creds_data)
        
        # Build calendar service
        service = build('calendar', 'v3', credentials=creds)
        
        # Create event
        event = {
            'summary': f"{booking_data['service_name']} - {booking_data['customer_name']}",
            'description': f"Customer: {booking_data['customer_name']}\nEmail: {booking_data.get('customer_email', 'N/A')}\nPhone: {booking_data.get('customer_phone', 'N/A')}\nNotes: {booking_data.get('notes', 'N/A')}",
            'start': {
                'dateTime': booking_data['start_time'],
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': booking_data['end_time'],
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': booking_data.get('customer_email')}
            ] if booking_data.get('customer_email') else [],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }
        
        # Insert event
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        
        print(f"✅ Calendar event created: {event_result.get('htmlLink')}")
        
        return {
            "success": True,
            "event_id": event_result.get('id'),
            "link": event_result.get('htmlLink')
        }
        
    except Exception as e:
        print(f"❌ Failed to create calendar event: {e}")
        return {"success": False, "error": str(e)}


def update_calendar_event(db: Session, workspace_id: int, event_id: str, booking_data: dict):
    """Update Google Calendar event"""
    try:
        integration = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.CALENDAR,
            Integration.is_active == True
        ).first()
        
        if not integration:
            return {"success": False, "error": "Calendar not configured"}
        
        creds_data = integration.config.get('credentials')
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build('calendar', 'v3', credentials=creds)
        
        # Get existing event
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        # Update event
        event['summary'] = f"{booking_data['service_name']} - {booking_data['customer_name']}"
        event['start']['dateTime'] = booking_data['start_time']
        event['end']['dateTime'] = booking_data['end_time']
        
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        
        print(f"✅ Calendar event updated: {updated_event.get('htmlLink')}")
        
        return {"success": True, "event_id": updated_event.get('id')}
        
    except Exception as e:
        print(f"❌ Failed to update calendar event: {e}")
        return {"success": False, "error": str(e)}


def delete_calendar_event(db: Session, workspace_id: int, event_id: str):
    """Delete Google Calendar event"""
    try:
        integration = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.CALENDAR,
            Integration.is_active == True
        ).first()
        
        if not integration:
            return {"success": False, "error": "Calendar not configured"}
        
        creds_data = integration.config.get('credentials')
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build('calendar', 'v3', credentials=creds)
        
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        print(f"✅ Calendar event deleted")
        
        return {"success": True}
        
    except Exception as e:
        print(f"❌ Failed to delete calendar event: {e}")
        return {"success": False, "error": str(e)}
