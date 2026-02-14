from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    business_type = Column(String(100))
    onboarding_step = Column(Integer, default=0)
    is_onboarding_complete = Column(Boolean, default=False)
    
    # Integration status
    email_configured = Column(Boolean, default=False)
    sms_configured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_workspaces", foreign_keys=[owner_id])
    users = relationship("User", back_populates="workspace", foreign_keys="User.workspace_id")
    contacts = relationship("Contact", back_populates="workspace", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="workspace", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="workspace", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="workspace", cascade="all, delete-orphan")
    forms = relationship("Form", back_populates="workspace", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="workspace", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="workspace", cascade="all, delete-orphan")
