from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class MessageChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    SYSTEM = "system"


class ConversationStatus(str, enum.Enum):
    NEW = "new"
    ONGOING = "ongoing"
    CLOSED = "closed"


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255))
    status = Column(Enum(ConversationStatus), default=ConversationStatus.NEW)
    
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))  # ADD THIS
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", back_populates="conversations")
    workspace = relationship("Workspace", back_populates="conversations")  # ADD THIS
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    channel = Column(Enum(MessageChannel), nullable=False)
    is_from_customer = Column(Boolean, default=True)
    is_automated = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
