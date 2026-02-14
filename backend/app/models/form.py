from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class FormStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved" 
    REJECTED = "rejected" 
    COMPLETED = "completed"
    OVERDUE = "overdue"


class Form(Base):
    __tablename__ = "forms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    fields = Column(JSON)  # Store form fields as JSON
    external_url = Column(String(500), nullable=True)  # NEW: For Google Forms, Typeform, etc.
    is_active = Column(Boolean, default=True)
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # NEW
    
    # Relationships
    workspace = relationship("Workspace", back_populates="forms")
    submissions = relationship("FormSubmission", back_populates="form", cascade="all, delete-orphan")


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    form_data = Column(JSON, nullable=False)  # Submitted data
    status = Column(Enum(FormStatus), default=FormStatus.PENDING)
    submitter_email = Column(String(255), nullable=True)  # NEW: Track who submitted
    submitter_name = Column(String(255), nullable=True)   # NEW
    
    form_id = Column(Integer, ForeignKey("forms.id", ondelete="CASCADE"))
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    form = relationship("Form", back_populates="submissions")
    booking = relationship("Booking", back_populates="form_submissions")
