from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    location = Column(Text)  # For in-person meetings
    is_active = Column(Boolean, default=True)
    
    # Availability (simple version - can be enhanced)
    available_days = Column(String(50))  # e.g., "1,2,3,4,5" for Mon-Fri
    start_time = Column(String(10))  # e.g., "09:00"
    end_time = Column(String(10))    # e.g., "17:00"
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="services")
    bookings = relationship("Booking", back_populates="service", cascade="all, delete-orphan")
