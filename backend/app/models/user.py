from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    OWNER = "owner"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STAFF)
    is_active = Column(Boolean, default=True)
    
    # Permissions (for staff)
    can_access_inbox = Column(Boolean, default=True)
    can_manage_bookings = Column(Boolean, default=True)
    can_view_forms = Column(Boolean, default=True)
    can_view_inventory = Column(Boolean, default=False)
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="users", foreign_keys=[workspace_id])
    owned_workspaces = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
