from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.models.integration import Integration, IntegrationType
from app.utils.security import verify_password, get_password_hash, create_access_token
from app.config import settings
from pydantic import BaseModel, validator

router = APIRouter()

# Combined signup request
class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    business_name: str
    
    @validator('password')
    def password_length(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot be longer than 72 characters')
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

@router.post("/signup", response_model=dict)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    """Sign up - Create workspace and owner user"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create owner user FIRST (without workspace_id)
    hashed_password = get_password_hash(data.password)
    user = User(
        email=data.email,
        hashed_password=hashed_password,
        full_name=data.full_name,
        role=UserRole.OWNER,
        workspace_id=None  # Set later
    )
    db.add(user)
    db.flush()  # Get user.id
    
    # Create workspace with owner_id
    workspace = Workspace(
        name=data.business_name,
        owner_id=user.id,
        onboarding_step=0,
        is_onboarding_complete=False
    )
    db.add(workspace)
    db.flush()  # Get workspace.id
    
    # Link user to workspace
    user.workspace_id = workspace.id
    
    # ✅ AUTO-CREATE EMAIL INTEGRATION
    if settings.BREVO_API_KEY:
        email_integration = Integration(
            workspace_id=workspace.id,
            type=IntegrationType.EMAIL,
            provider="brevo",
            config={
                "api_key": settings.BREVO_API_KEY,
                "from_email": "nexspace.appointments@gmail.com",
                "from_name": workspace.name
            },
            is_active=True
        )
        db.add(email_integration)
        workspace.email_configured = True
    
    # ✅ NEW: AUTO-CREATE SMS INTEGRATION
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
        sms_integration = Integration(
            workspace_id=workspace.id,
            type=IntegrationType.SMS,
            provider="twilio",
            config={
                "account_sid": settings.TWILIO_ACCOUNT_SID,
                "auth_token": settings.TWILIO_AUTH_TOKEN,
                "phone": settings.TWILIO_PHONE_NUMBER
            },
            is_active=True
        )
        db.add(sms_integration)
        workspace.sms_configured = True
    
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "workspace_id": workspace.id, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "workspace_id": workspace.id
        },
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "onboarding_step": workspace.onboarding_step,
            "is_onboarding_complete": workspace.is_onboarding_complete
        }
    }

@router.post("/login", response_model=dict)
def login(credentials: dict, db: Session = Depends(get_db)):
    """Login - Get access token"""
    email = credentials.get("email")
    password = credentials.get("password")
    
    # Find user
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "workspace_id": user.workspace_id, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    # Get workspace
    workspace = db.query(Workspace).filter(Workspace.id == user.workspace_id).first()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "workspace_id": user.workspace_id
        },
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "onboarding_step": workspace.onboarding_step,
            "is_onboarding_complete": workspace.is_onboarding_complete
        } if workspace else None
    }
