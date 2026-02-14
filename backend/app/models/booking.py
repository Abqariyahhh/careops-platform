from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    booking_date = Column(DateTime, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    notes = Column(Text)
    
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"))
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    calendar_event_id = Column(String, nullable=True)  # Google Calendar event ID

    # Relationships
    contact = relationship("Contact", back_populates="bookings")
    service = relationship("Service", back_populates="bookings")
    workspace = relationship("Workspace", back_populates="bookings")
    form_submissions = relationship("FormSubmission", back_populates="booking", cascade="all, delete-orphan")
