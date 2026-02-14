from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class WorkspaceCreate(BaseModel):
    business_name: str
    address: Optional[str] = None
    timezone: str = "UTC"
    contact_email: EmailStr
    contact_phone: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: int
    business_name: str
    address: Optional[str]
    timezone: str
    contact_email: str
    contact_phone: Optional[str]
    is_active: bool
    onboarding_step: int
    onboarding_completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
