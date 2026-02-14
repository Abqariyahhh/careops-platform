from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models.conversation import Conversation, ConversationStatus, Message, MessageChannel
from app.models.contact import Contact
from app.services.email_service import send_email
from app.services.sms_service import send_sms


router = APIRouter()


@router.get("/conversations/{workspace_id}")
def get_conversations(workspace_id: int, db: Session = Depends(get_db)):
    """Get all conversations for workspace"""
    
    conversations = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id
    ).join(Conversation.contact).order_by(Conversation.updated_at.desc()).all()
    
    result = []
    for conv in conversations:
        # Get unread count
        unread_count = db.query(Message).filter(
            Message.conversation_id == conv.id,
            Message.is_from_customer == True,
            Message.is_read == False
        ).count()
        
        # Get last message
        last_msg = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.created_at.desc()).first()
        
        # Get total messages
        total_messages = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).count()
        
        result.append({
            "id": conv.id,
            "subject": conv.subject,
            "status": conv.status.value,
            "contact_id": conv.contact_id,
            "contact_name": conv.contact.name,
            "contact_email": conv.contact.email,
            "contact_phone": conv.contact.phone,
            "unread_count": unread_count,
            "total_messages": total_messages,
            "last_message": last_msg.content if last_msg else None,
            "last_message_time": last_msg.created_at.isoformat() if last_msg else None,
            "updated_at": conv.updated_at.isoformat(),
            "created_at": conv.created_at.isoformat()
        })
    
    return result


@router.get("/conversation/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Get all messages in a conversation"""
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    
    return {
        "conversation_id": conversation_id,
        "subject": conversation.subject,
        "status": conversation.status.value,
        "contact": {
            "id": conversation.contact.id,
            "name": conversation.contact.name,
            "email": conversation.contact.email,
            "phone": conversation.contact.phone
        },
        "messages": [
            {
                "id": msg.id,
                "content": msg.content,
                "channel": msg.channel.value,
                "is_from_customer": msg.is_from_customer,
                "is_automated": msg.is_automated,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    }


class ReplyMessage(BaseModel):
    content: str
    channel: str  # "email" or "sms"


@router.post("/conversation/{conversation_id}/reply")
def reply_to_conversation(
    conversation_id: int,
    reply: ReplyMessage,
    db: Session = Depends(get_db)
):
    """Send reply to customer"""
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    contact = conversation.contact
    
    # Mark all customer messages as read
    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_from_customer == True,
        Message.is_read == False
    ).update({"is_read": True})
    
    # Create reply message
    reply_msg = Message(
        conversation_id=conversation_id,
        content=reply.content,
        channel=MessageChannel.EMAIL if reply.channel == "email" else MessageChannel.SMS,
        is_from_customer=False,
        is_automated=False,
        is_read=True
    )
    db.add(reply_msg)
    
    # Update conversation status and timestamp
    conversation.status = ConversationStatus.ONGOING
    conversation.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(reply_msg)
    
    # Send actual email/SMS
    send_success = False
    error_msg = None
    
    try:
        if reply.channel == "email" and contact.email:
            result = send_email(
                db=db,
                workspace_id=conversation.workspace_id,
                to_email=contact.email,
                subject=f"Re: {conversation.subject}",
                html_content=f"<p>{reply.content}</p>"
            )
            send_success = result.get("success", False)
            error_msg = result.get("error")
        
        elif reply.channel == "sms" and contact.phone:
            result = send_sms(
                db=db,
                workspace_id=conversation.workspace_id,
                to_phone=contact.phone,
                message=reply.content
            )
            send_success = result.get("success", False)
            error_msg = result.get("error")
    except Exception as e:
        error_msg = str(e)
    
    return {
        "success": True,
        "message_id": reply_msg.id,
        "sent": send_success,
        "error": error_msg,
        "reply": {
            "id": reply_msg.id,
            "content": reply_msg.content,
            "channel": reply_msg.channel.value,
            "created_at": reply_msg.created_at.isoformat()
        }
    }


@router.patch("/conversation/{conversation_id}/mark-read")
def mark_conversation_read(conversation_id: int, db: Session = Depends(get_db)):
    """Mark all messages in conversation as read"""
    
    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_from_customer == True
    ).update({"is_read": True})
    
    db.commit()
    
    return {"success": True, "message": "Conversation marked as read"}


@router.patch("/conversation/{conversation_id}/status")
def update_conversation_status(
    conversation_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Update conversation status"""
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if status == "new":
        conversation.status = ConversationStatus.NEW
    elif status == "ongoing":
        conversation.status = ConversationStatus.ONGOING
    elif status == "closed":
        conversation.status = ConversationStatus.CLOSED
    else:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    conversation.updated_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "status": conversation.status.value}
