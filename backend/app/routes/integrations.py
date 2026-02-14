from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.database import get_db
from app.models.integration import Integration, IntegrationType

router = APIRouter()

# Google OAuth Configuration
GOOGLE_CLIENT_ID = "639807016624-49f32l03g84c6d7kob8qvubkg8eqt1j2.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:8000/api/integrations/google/callback"
SCOPES = ['https://www.googleapis.com/auth/calendar']

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

@router.get("/google/authorize/{workspace_id}")
def authorize_google_calendar(workspace_id: int):
    """Start Google Calendar OAuth flow"""
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=str(workspace_id)
        )
        
        return {"authorization_url": authorization_url}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        workspace_id = int(state)
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        service = build('calendar', 'v3', credentials=credentials)
        calendar_list = service.calendarList().list().execute()
        
        integration = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.CALENDAR
        ).first()
        
        if integration:
            integration.config = {
                'credentials': {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                },
                'calendar_id': 'primary'
            }
            integration.is_active = True
        else:
            integration = Integration(
                workspace_id=workspace_id,
                type=IntegrationType.CALENDAR,
                provider='google',
                config={
                    'credentials': {
                        'token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes
                    },
                    'calendar_id': 'primary'
                },
                is_active=True
            )
            db.add(integration)
        
        db.commit()
        
        print(f"✅ Google Calendar connected for workspace {workspace_id}")
        
        return RedirectResponse(url=f"http://localhost:3000/settings?calendar=success")
        
    except Exception as e:
        print(f"❌ Google Calendar connection failed: {e}")
        return RedirectResponse(url=f"http://localhost:3000/settings?calendar=error")

@router.get("/google/status/{workspace_id}")
def get_google_calendar_status(workspace_id: int, db: Session = Depends(get_db)):
    """Check if Google Calendar is connected"""
    integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.CALENDAR,
        Integration.is_active == True
    ).first()
    
    return {
        "connected": integration is not None,
        "provider": integration.provider if integration else None
    }

@router.delete("/google/disconnect/{workspace_id}")
def disconnect_google_calendar(workspace_id: int, db: Session = Depends(get_db)):
    """Disconnect Google Calendar"""
    integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.CALENDAR
    ).first()
    
    if integration:
        integration.is_active = False
        db.commit()
        return {"success": True, "message": "Google Calendar disconnected"}
    
    return {"success": False, "message": "No calendar integration found"}
