from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from fastapi.responses import RedirectResponse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.workspace import Workspace
from app.models.user import User
from app.models.integration import Integration, IntegrationType


router = APIRouter()


@router.get("/{workspace_id}")
def get_workspace_settings(workspace_id: int, db: Session = Depends(get_db)):
    """Get workspace settings"""
    
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get owner info
    owner = db.query(User).filter(User.id == workspace.owner_id).first()
    
    # Get email integration
    email_integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.EMAIL
    ).first()
    
    # Get SMS integration
    sms_integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.SMS
    ).first()
    
    # Get calendar integration
    calendar_integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.CALENDAR
    ).first()
    
    return {
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "business_type": workspace.business_type,
            "is_active": workspace.is_active,
            "email_configured": workspace.email_configured,
            "sms_configured": workspace.sms_configured,
            "onboarding_complete": workspace.is_onboarding_complete,
            "created_at": workspace.created_at.isoformat()
        },
        "owner": {
            "name": owner.full_name if owner else "Unknown",
            "email": owner.email if owner else "Unknown"
        },
        "integrations": {
            "email": {
                "configured": email_integration is not None,
                "provider": email_integration.provider if email_integration else None,
                "from_email": email_integration.config.get("from_email") if email_integration else None
            } if email_integration else None,
            "sms": {
                "configured": sms_integration is not None,
                "provider": sms_integration.provider if sms_integration else None,
                "phone_number": sms_integration.config.get("phone") if sms_integration else None
            } if sms_integration else None,
            "calendar": {
                "configured": calendar_integration is not None and calendar_integration.is_active,
                "provider": calendar_integration.provider if calendar_integration else None
            } if calendar_integration else {"configured": False, "provider": None}
        }
    }


class UpdateWorkspaceSettings(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None


@router.patch("/{workspace_id}")
def update_workspace_settings(
    workspace_id: int,
    update: UpdateWorkspaceSettings,
    db: Session = Depends(get_db)
):
    """Update workspace settings"""
    
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if update.name:
        workspace.name = update.name
    if update.business_type:
        workspace.business_type = update.business_type
    
    db.commit()
    db.refresh(workspace)
    
    return {
        "success": True,
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "business_type": workspace.business_type
        }
    }


class UpdateEmailIntegration(BaseModel):
    api_key: str
    from_email: Optional[str] = None


@router.patch("/{workspace_id}/email")
def update_email_integration(
    workspace_id: int,
    update: UpdateEmailIntegration,
    db: Session = Depends(get_db)
):
    """Update email integration"""
    
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.EMAIL
    ).first()
    
    if integration:
        # Update existing
        integration.config["api_key"] = update.api_key
        if update.from_email:
            integration.config["from_email"] = update.from_email
    else:
        # Create new
        integration = Integration(
            workspace_id=workspace_id,
            type=IntegrationType.EMAIL,
            provider="sendgrid",
            config={
                "api_key": update.api_key,
                "from_email": update.from_email or "noreply@example.com"
            }
        )
        db.add(integration)
    
    workspace.email_configured = True
    db.commit()
    
    return {
        "success": True,
        "message": "Email integration updated"
    }


# Google Calendar OAuth
@router.get("/{workspace_id}/integrations/google/connect")
def connect_google_calendar(workspace_id: int, db: Session = Depends(get_db)):
    """Initiate Google Calendar OAuth flow"""
    
    # Create OAuth flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": "639807016624-49f32l03g84c6d7kob8qvubkg8eqt1j2.apps.googleusercontent.com",
                "client_secret": "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",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8000/api/settings/integrations/google/callback"]
            }
        },
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    
    flow.redirect_uri = "http://localhost:8000/api/settings/integrations/google/callback"
    
    # Generate authorization URL with workspace_id in state
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=str(workspace_id)  # Pass workspace_id via state parameter
    )
    
    return {"authorization_url": authorization_url}


@router.get("/integrations/google/callback")
def google_calendar_callback(
    code: str,
    state: str,  # This contains workspace_id
    db: Session = Depends(get_db)
):
    """Handle Google Calendar OAuth callback"""
    
    try:
        workspace_id = int(state)
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": "639807016624-49f32l03g84c6d7kob8qvubkg8eqt1j2.apps.googleusercontent.com",
                    "client_secret": "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",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8000/api/settings/integrations/google/callback"]
                }
            },
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        
        flow.redirect_uri = "http://localhost:8000/api/settings/integrations/google/callback"
        
        # Exchange code for credentials
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Save to database
        integration = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.CALENDAR
        ).first()
        
        if integration:
            # Update existing
            integration.config = {
                'credentials': {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
            }
            integration.is_active = True
        else:
            # Create new
            integration = Integration(
                workspace_id=workspace_id,
                type=IntegrationType.CALENDAR,
                provider="google",
                config={
                    'credentials': {
                        'token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes
                    }
                },
                is_active=True
            )
            db.add(integration)
        
        db.commit()
        
        print("✅ Calendar integration saved successfully!")
        
        # Redirect back to frontend settings page
        return RedirectResponse(url="http://localhost:3000/settings?calendar=success")
        
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        return RedirectResponse(url="http://localhost:3000/settings?calendar=error")

class UpdateContactForm(BaseModel):
    form_mode: str  # 'custom' or 'external'
    external_url: Optional[str] = None
    form_name: Optional[str] = "Contact Us"

@router.patch("/{workspace_id}/contact-form")
def update_contact_form(
    workspace_id: int,
    update: UpdateContactForm,
    db: Session = Depends(get_db)
):
    """Update contact form configuration"""
    
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get or create contact form
    from app.models.form import Form
    contact_form = db.query(Form).filter(
        Form.workspace_id == workspace_id,
        Form.name.contains("Contact")
    ).first()
    
    if not contact_form:
        # Create new form
        contact_form = Form(
            workspace_id=workspace_id,
            name=update.form_name,
            description="Public contact form",
            fields=[
                {"name": "name", "label": "Full Name", "type": "text", "required": True},
                {"name": "email", "label": "Email", "type": "email", "required": True},
                {"name": "phone", "label": "Phone", "type": "tel", "required": False},
                {"name": "message", "label": "Message", "type": "textarea", "required": False}
            ],
            external_url=update.external_url if update.form_mode == 'external' else None,
            is_active=True
        )
        db.add(contact_form)
    else:
        # Update existing
        if update.form_mode == 'external':
            contact_form.external_url = update.external_url
        else:
            contact_form.external_url = None
    
    db.commit()
    
    return {
        "success": True,
        "message": "Contact form updated",
        "form_url": f"/contact/{workspace_id}" if update.form_mode == 'custom' else update.external_url
    }