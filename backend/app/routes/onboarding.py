from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.workspace import Workspace
from app.models.integration import Integration, IntegrationType
from app.models.service import Service
from app.models.form import Form
from app.models.inventory import InventoryItem
from app.models.user import User, UserRole
from app.config import settings



router = APIRouter()



# Step 2: Email/SMS Integration
class IntegrationSetup(BaseModel):
    email_provider: str = "brevo"
    email_api_key: Optional[str] = None
    sms_provider: Optional[str] = None
    sms_account_sid: Optional[str] = None
    sms_auth_token: Optional[str] = None
    sms_phone: Optional[str] = None


@router.post("/workspace/{workspace_id}/integrations")
def setup_integrations(
    workspace_id: int,
    data: IntegrationSetup,
    db: Session = Depends(get_db)
):
    """Step 2: Set up email and SMS integrations"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        # 🔧 QUICK FIX: Fallback to first available workspace
        workspace = db.query(Workspace).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="No workspace found")
        workspace_id = workspace.id
    
    # ✅ NEW: Support "auto" to use .env key
    if data.email_api_key == "auto" and settings.BREVO_API_KEY:
        api_key = settings.BREVO_API_KEY
    else:
        api_key = data.email_api_key
    
    # Email integration (mandatory)
    if api_key:
        existing_email = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.EMAIL
        ).first()
        
        if existing_email:
            existing_email.config = {
                "api_key": api_key,
                "from_email": "nexspace.appointments@gmail.com",
                "from_name": workspace.name
            }
            existing_email.is_active = True
        else:
            email_integration = Integration(
                workspace_id=workspace_id,
                type=IntegrationType.EMAIL,
                provider=data.email_provider,
                config={
                    "api_key": api_key,
                    "from_email": "nexspace.appointments@gmail.com",
                    "from_name": workspace.name
                },
                is_active=True
            )
            db.add(email_integration)
        
        workspace.email_configured = True
    
    # SMS integration (optional)
    if data.sms_provider and data.sms_account_sid and data.sms_auth_token:
        existing_sms = db.query(Integration).filter(
            Integration.workspace_id == workspace_id,
            Integration.type == IntegrationType.SMS
        ).first()
        
        if existing_sms:
            existing_sms.config = {
                "account_sid": data.sms_account_sid,
                "auth_token": data.sms_auth_token,
                "phone": data.sms_phone
            }
            existing_sms.is_active = True
        else:
            sms_integration = Integration(
                workspace_id=workspace_id,
                type=IntegrationType.SMS,
                provider=data.sms_provider,
                config={
                    "account_sid": data.sms_account_sid,
                    "auth_token": data.sms_auth_token,
                    "phone": data.sms_phone
                },
                is_active=True
            )
            db.add(sms_integration)
        
        workspace.sms_configured = True
    
    workspace.onboarding_step = max(workspace.onboarding_step, 2)
    db.commit()
    
    return {"message": "Integrations configured", "step": 2}



# Step 3: Create Contact Form
class ContactFormSetup(BaseModel):
    form_name: str = "Contact Form"
    form_type: str = "contact"
    fields: List[dict] = []
    external_url: Optional[str] = None



@router.post("/workspace/{workspace_id}/contact-form")
def setup_contact_form(
    workspace_id: int,
    data: ContactFormSetup,
    db: Session = Depends(get_db)
):
    """Step 3: Set up contact form (custom or external)"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create form record
    contact_form = Form(
        workspace_id=workspace_id,
        name=data.form_name,
        description="Public contact form for lead generation",
        fields=data.fields,
        external_url=data.external_url,
        is_active=True
    )
    db.add(contact_form)
    
    workspace.onboarding_step = max(workspace.onboarding_step, 3)
    db.commit()
    db.refresh(contact_form)
    
    form_url = f"/contact/{workspace_id}" if not data.external_url else data.external_url
    
    return {
        "message": "Contact form created",
        "form_id": contact_form.id,
        "form_type": data.form_type,
        "form_url": form_url,
        "step": 3
    }



# Step 4: Setup Services
class ServiceSetup(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int
    location: str
    available_days: str
    start_time: str
    end_time: str



@router.post("/workspace/{workspace_id}/services")
def create_service(
    workspace_id: int,
    data: ServiceSetup,
    db: Session = Depends(get_db)
):
    """Step 4: Create a service/booking type"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    service = Service(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        duration_minutes=data.duration_minutes,
        location=data.location,
        available_days=data.available_days,
        start_time=data.start_time,
        end_time=data.end_time,
        is_active=True
    )
    db.add(service)
    
    workspace.onboarding_step = max(workspace.onboarding_step, 4)
    db.commit()
    db.refresh(service)
    
    return {
        "message": "Service created",
        "service_id": service.id,
        "booking_url": f"/booking/{workspace_id}/{service.id}",
        "step": 4
    }



# Step 5: Setup Post-Booking Forms
class PostBookingFormSetup(BaseModel):
    form_name: str
    form_type: str
    fields: List[dict]



@router.post("/workspace/{workspace_id}/post-booking-forms")
def create_post_booking_form(
    workspace_id: int,
    data: PostBookingFormSetup,
    db: Session = Depends(get_db)
):
    """Step 5: Create post-booking forms"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    form = Form(
        workspace_id=workspace_id,
        name=data.form_name,
        description=f"Automated {data.form_type} form sent after booking",
        fields=data.fields,
        is_active=True
    )
    db.add(form)
    
    workspace.onboarding_step = max(workspace.onboarding_step, 5)
    db.commit()
    db.refresh(form)
    
    return {
        "message": "Post-booking form created",
        "form_id": form.id,
        "step": 5
    }



# Step 6: Setup Inventory
class InventorySetup(BaseModel):
    name: str
    description: Optional[str] = None
    quantity: int
    low_stock_threshold: int
    unit: str



@router.post("/workspace/{workspace_id}/inventory")
def create_inventory_item(
    workspace_id: int,
    data: InventorySetup,
    db: Session = Depends(get_db)
):
    """Step 6: Add inventory items"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    item = InventoryItem(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        quantity=data.quantity,
        low_stock_threshold=data.low_stock_threshold,
        unit=data.unit
    )
    db.add(item)
    
    workspace.onboarding_step = max(workspace.onboarding_step, 6)
    db.commit()
    db.refresh(item)
    
    return {
        "message": "Inventory item added",
        "item_id": item.id,
        "step": 6
    }



# Step 7: Add Staff
class StaffInvite(BaseModel):
    email: str
    full_name: str
    can_access_inbox: bool = True
    can_manage_bookings: bool = True
    can_view_forms: bool = True
    can_view_inventory: bool = False



@router.post("/workspace/{workspace_id}/staff")
def invite_staff(
    workspace_id: int,
    data: StaffInvite,
    db: Session = Depends(get_db)
):
    """Step 7: Invite staff members"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check if user already exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    from app.utils.security import get_password_hash
    
    staff_user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash("temp123"),
        role=UserRole.STAFF,
        workspace_id=workspace_id,
        can_access_inbox=data.can_access_inbox,
        can_manage_bookings=data.can_manage_bookings,
        can_view_forms=data.can_view_forms,
        can_view_inventory=data.can_view_inventory
    )
    db.add(staff_user)
    
    workspace.onboarding_step = max(workspace.onboarding_step, 7)
    db.commit()
    db.refresh(staff_user)
    
    return {
        "message": "Staff member added",
        "user_id": staff_user.id,
        "temp_password": "temp123",
        "step": 7
    }



# Step 8: Activate Workspace
@router.post("/workspace/{workspace_id}/activate")
def activate_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """Step 8: Activate workspace after completing onboarding"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Verify minimum requirements
    if not workspace.email_configured:
        raise HTTPException(status_code=400, detail="Email integration required")
    
    services_count = db.query(Service).filter(Service.workspace_id == workspace_id).count()
    if services_count == 0:
        raise HTTPException(status_code=400, detail="At least one service required")
    
    workspace.is_active = True
    workspace.is_onboarding_complete = True
    workspace.onboarding_step = 8
    db.commit()
    
    return {
        "message": "Workspace activated successfully!",
        "workspace_id": workspace_id,
        "is_active": True
    }



# Get onboarding status
@router.get("/workspace/{workspace_id}/onboarding-status")
def get_onboarding_status(workspace_id: int, db: Session = Depends(get_db)):
    """Get current onboarding progress"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    services_count = db.query(Service).filter(Service.workspace_id == workspace_id).count()
    forms_count = db.query(Form).filter(Form.workspace_id == workspace_id).count()
    inventory_count = db.query(InventoryItem).filter(InventoryItem.workspace_id == workspace_id).count()
    staff_count = db.query(User).filter(
        User.workspace_id == workspace_id,
        User.role == UserRole.STAFF
    ).count()
    
    return {
        "current_step": workspace.onboarding_step,
        "completed": workspace.is_onboarding_complete,
        "is_active": workspace.is_active,
        "email_configured": workspace.email_configured,
        "sms_configured": workspace.sms_configured,
        "services_count": services_count,
        "forms_count": forms_count,
        "inventory_count": inventory_count,
        "staff_count": staff_count
    }


@router.post("/workspace/{workspace_id}/ai-setup")
async def ai_complete_setup(
    workspace_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Complete onboarding setup using AI-extracted data
    Creates integration, contact form, and service in one go
    """
    try:
        workspace = db.query(Workspace).filter(
            Workspace.id == workspace_id
        ).first()
        
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # 1. Setup Email Integration (using settings)
        api_key = settings.BREVO_API_KEY if hasattr(settings, 'BREVO_API_KEY') else None
        
        if api_key:
            # Check if integration already exists
            existing_integration = db.query(Integration).filter(
                Integration.workspace_id == workspace_id,
                Integration.type == IntegrationType.EMAIL
            ).first()
            
            if not existing_integration:
                email_integration = Integration(
                    workspace_id=workspace_id,
                    type=IntegrationType.EMAIL,
                    provider="brevo",
                    config={
                        "api_key": api_key,
                        "from_email": "nexspace.appointments@gmail.com",
                        "from_name": data.get("business_name", workspace.name or "Your Business")
                    },
                    is_active=True
                )
                db.add(email_integration)
                workspace.email_configured = True
        
        # 2. Create Contact Form
        contact_form = Form(
            workspace_id=workspace_id,
            name="Contact Us",
            description="Public contact form for lead generation",
            fields=[
                {"name": "name", "label": "Full Name", "type": "text", "required": True},
                {"name": "email", "label": "Email", "type": "email", "required": True},
                {"name": "phone", "label": "Phone", "type": "tel", "required": False},
                {"name": "message", "label": "Message", "type": "textarea", "required": False}
            ],
            external_url=None,
            is_active=True
        )
        db.add(contact_form)
        
        # 3. Create Service from AI data
        service = Service(
            workspace_id=workspace_id,
            name=data.get("service_name", "Consultation"),
            description=data.get("service_description", ""),
            duration_minutes=data.get("service_duration", 30),
            location=data.get("service_location", data.get("business_address", "")),
            available_days="1,2,3,4,5",
            start_time="09:00",
            end_time="17:00",
            is_active=True
        )
        db.add(service)
        
        # 4. Update workspace details
        if data.get("business_name"):
            workspace.business_name = data["business_name"]
        if data.get("business_address"):
            workspace.address = data["business_address"]
        if data.get("contact_email"):
            workspace.contact_email = data["contact_email"]
        
        workspace.onboarding_step = 5
        
        db.commit()
        db.refresh(workspace)
        
        return {
            "message": "AI setup completed successfully",
            "workspace": {
                "id": workspace.id,
                "business_name": workspace.business_name,
                "onboarding_step": workspace.onboarding_step
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"AI setup error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
