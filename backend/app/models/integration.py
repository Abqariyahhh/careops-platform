from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class IntegrationType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    CALENDAR = "CALENDAR"
    WEBHOOK = "webhook"

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(IntegrationType), nullable=False)
    provider = Column(String(100))  # e.g., "sendgrid", "twilio"
    config = Column(JSON)  # Store API keys and config securely
    is_active = Column(Boolean, default=True)
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="integrations")
