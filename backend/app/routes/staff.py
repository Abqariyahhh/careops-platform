from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from passlib.context import CryptContext
from app.services.email_service import send_email


router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/all/{workspace_id}")
def get_all_staff(workspace_id: int, db: Session = Depends(get_db)):
    """Get all staff members for workspace"""
    
    # Get workspace to access owner
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get all users for this workspace
    all_users = db.query(User).filter(User.workspace_id == workspace_id).all()
    
    staff_list = []
    for user in all_users:
        staff_list.append({
            "id": user.id,
            "user_id": user.id,
            "name": user.full_name,
            "email": user.email,
            "role": "owner" if user.id == workspace.owner_id else "staff",  # FIXED
            "can_access_inbox": user.can_access_inbox,
            "can_manage_bookings": user.can_manage_bookings,
            "can_view_forms": user.can_view_forms,
            "can_view_inventory": user.can_view_inventory,
            "joined_at": user.created_at.isoformat()
        })
    
    return staff_list


class InviteStaff(BaseModel):
    email: str
    full_name: str
    can_access_inbox: bool = True
    can_manage_bookings: bool = True
    can_view_forms: bool = True
    can_view_inventory: bool = False


@router.post("/invite/{workspace_id}")
def invite_staff_member(
    workspace_id: int,
    invite: InviteStaff,
    db: Session = Depends(get_db)
):
    """Invite a new staff member"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == invite.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Get workspace for email context
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create new user with temporary password
    temp_password = "temp123"
    hashed_password = pwd_context.hash(temp_password)
    
    new_user = User(
        email=invite.email,
        hashed_password=hashed_password,
        full_name=invite.full_name,
        role=UserRole.STAFF,  # FIXED: Changed from "member" to UserRole.STAFF
        is_active=True,
        can_access_inbox=invite.can_access_inbox,
        can_manage_bookings=invite.can_manage_bookings,
        can_view_forms=invite.can_view_forms,
        can_view_inventory=invite.can_view_inventory,
        workspace_id=workspace_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Send invitation email
    try:
        subject = f"🎉 You've been invited to join {workspace.name}"
        
        # Build permissions list
        permissions_list = []
        if invite.can_access_inbox:
            permissions_list.append("📬 Access Inbox")
        if invite.can_manage_bookings:
            permissions_list.append("📅 Manage Bookings")
        if invite.can_view_forms:
            permissions_list.append("📝 View Forms")
        if invite.can_view_inventory:
            permissions_list.append("📦 View Inventory")
        
        permissions_html = "<br>".join([f"• {p}" for p in permissions_list])
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">Welcome to {workspace.name}! 🎉</h1>
                </div>
                
                <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb;">
                    <p style="font-size: 16px; color: #374151;">Hi {invite.full_name},</p>
                    
                    <p style="font-size: 16px; color: #374151;">
                        You've been invited to join the <strong>{workspace.name}</strong> team! 
                        We're excited to have you on board.
                    </p>
                    
                    <div style="background: white; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 4px;">
                        <h3 style="margin-top: 0; color: #111827;">Your Login Credentials</h3>
                        <p style="margin: 10px 0; color: #374151;">
                            <strong>Email:</strong> {invite.email}
                        </p>
                        <p style="margin: 10px 0; color: #374151;">
                            <strong>Temporary Password:</strong> <code style="background: #fee; padding: 4px 8px; border-radius: 4px; font-size: 16px; font-weight: bold;">temp123</code>
                        </p>
                        <p style="margin: 10px 0; color: #dc2626; font-size: 14px;">
                            ⚠️ Please change your password after logging in for the first time.
                        </p>
                    </div>
                    
                    <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <h3 style="margin-top: 0; color: #1e40af;">Your Permissions</h3>
                        <p style="margin: 5px 0; color: #1e40af; line-height: 1.8;">
                            {permissions_html}
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="http://localhost:3000/auth/login" 
                           style="display: inline-block; background: #667eea; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">
                            Login to Your Account →
                        </a>
                    </div>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                        If you have any questions, please contact the workspace owner.<br>
                        Best regards,<br>
                        <strong>{workspace.name} Team</strong>
                    </p>
                </div>
            </body>
        </html>
        """
        
        send_email(
            db=db,
            workspace_id=workspace_id,
            to_email=invite.email,
            subject=subject,
            html_content=html_content
        )
        
        email_sent = True
    except Exception as e:
        print(f"❌ Failed to send invitation email: {e}")
        email_sent = False
    
    return {
        "success": True,
        "user_id": new_user.id,
        "email": new_user.email,
        "temporary_password": temp_password,
        "email_sent": email_sent,
        "message": "Staff member invited successfully. " + 
                   ("Invitation email sent!" if email_sent else "Failed to send email - please share credentials manually.")
    }


class UpdatePermissions(BaseModel):
    can_access_inbox: bool
    can_manage_bookings: bool
    can_view_forms: bool
    can_view_inventory: bool


@router.patch("/{member_id}/permissions")
def update_staff_permissions(
    member_id: int,
    update: UpdatePermissions,
    db: Session = Depends(get_db)
):
    """Update staff member permissions"""
    
    user = db.query(User).filter(User.id == member_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is owner
    workspace = db.query(Workspace).filter(Workspace.owner_id == user.id).first()
    if workspace:
        raise HTTPException(status_code=403, detail="Cannot modify owner permissions")
    
    user.can_access_inbox = update.can_access_inbox
    user.can_manage_bookings = update.can_manage_bookings
    user.can_view_forms = update.can_view_forms
    user.can_view_inventory = update.can_view_inventory
    
    db.commit()
    
    return {
        "success": True,
        "user_id": user.id,
        "permissions": {
            "can_access_inbox": user.can_access_inbox,
            "can_manage_bookings": user.can_manage_bookings,
            "can_view_forms": user.can_view_forms,
            "can_view_inventory": user.can_view_inventory
        }
    }


@router.delete("/{member_id}")
def remove_staff_member(member_id: int, db: Session = Depends(get_db)):
    """Remove staff member from workspace"""
    
    user = db.query(User).filter(User.id == member_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is owner
    workspace = db.query(Workspace).filter(Workspace.owner_id == user.id).first()
    if workspace:
        raise HTTPException(status_code=403, detail="Cannot remove workspace owner")
    
    db.delete(user)
    db.commit()
    
    return {"success": True, "message": "Staff member removed"}
