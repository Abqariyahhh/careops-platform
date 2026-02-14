from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from app.database import get_db
from app.models.booking import Booking, BookingStatus
from app.models.conversation import Conversation, ConversationStatus, Message
from app.models.form import FormSubmission, FormStatus
from app.models.inventory import InventoryItem
from app.models.contact import Contact
from app.models.service import Service



router = APIRouter()


@router.get("/stats/{workspace_id}")
def get_dashboard_stats(workspace_id: int, db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    
    # Today's date range
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Total counts
    total_bookings = db.query(Booking).filter(Booking.workspace_id == workspace_id).count()
    total_contacts = db.query(Contact).filter(Contact.workspace_id == workspace_id).count()
    total_conversations = db.query(Conversation).filter(Conversation.workspace_id == workspace_id).count()
    
    # Today's bookings
    today_bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.booking_date >= today_start,
        Booking.booking_date < today_end
    ).count()
    
    # Unread messages
    unread_messages = db.query(Message).join(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Message.is_from_customer == True,
        Message.is_read == False
    ).count()
    
    # Pending forms
    pending_forms = db.query(FormSubmission).join(FormSubmission.form).filter(
        FormSubmission.form.has(workspace_id=workspace_id),
        FormSubmission.status == FormStatus.PENDING
    ).count()
    
    # Low stock items
    low_stock = db.query(InventoryItem).filter(
        InventoryItem.workspace_id == workspace_id,
        InventoryItem.quantity <= InventoryItem.low_stock_threshold
    ).count()
    
    return {
        "total_bookings": total_bookings,
        "total_contacts": total_contacts,
        "total_conversations": total_conversations,
        "today_bookings": today_bookings,
        "unread_messages": unread_messages,
        "pending_forms": pending_forms,
        "low_stock_items": low_stock
    }


@router.get("/bookings/today/{workspace_id}")
def get_today_bookings(workspace_id: int, db: Session = Depends(get_db)):
    """Get today's bookings"""
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.booking_date >= today_start,
        Booking.booking_date < today_end
    ).join(Booking.contact).join(Booking.service).all()
    
    return [
        {
            "id": b.id,
            "booking_date": b.booking_date.isoformat(),
            "status": b.status.value,
            "customer_name": b.contact.name,
            "customer_email": b.contact.email,
            "customer_phone": b.contact.phone,
            "service_name": b.service.name,
            "duration": b.service.duration_minutes,
            "location": b.service.location,
            "notes": b.notes
        }
        for b in bookings
    ]


@router.get("/bookings/upcoming/{workspace_id}")
def get_upcoming_bookings(workspace_id: int, db: Session = Depends(get_db)):
    """Get upcoming bookings (next 7 days)"""
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_later = today + timedelta(days=7)
    
    bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.booking_date >= today,
        Booking.booking_date < week_later,
        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
    ).join(Booking.contact).join(Booking.service).order_by(Booking.booking_date).all()
    
    return [
        {
            "id": b.id,
            "booking_date": b.booking_date.isoformat(),
            "status": b.status.value,
            "customer_name": b.contact.name,
            "customer_email": b.contact.email,
            "service_name": b.service.name,
            "duration": b.service.duration_minutes
        }
        for b in bookings
    ]


@router.get("/conversations/new/{workspace_id}")
def get_new_conversations(workspace_id: int, db: Session = Depends(get_db)):
    """Get new/unread conversations"""
    
    conversations = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Conversation.status.in_([ConversationStatus.NEW, ConversationStatus.ONGOING])
    ).join(Conversation.contact).order_by(Conversation.updated_at.desc()).limit(10).all()
    
    result = []
    for conv in conversations:
        # Get unread message count
        unread_count = db.query(Message).filter(
            Message.conversation_id == conv.id,
            Message.is_from_customer == True,
            Message.is_read == False
        ).count()
        
        # Get last message
        last_msg = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.created_at.desc()).first()
        
        result.append({
            "id": conv.id,
            "subject": conv.subject,
            "status": conv.status.value,
            "contact_name": conv.contact.name,
            "contact_email": conv.contact.email,
            "unread_count": unread_count,
            "last_message": last_msg.content if last_msg else None,
            "last_message_time": last_msg.created_at.isoformat() if last_msg else None,
            "updated_at": conv.updated_at.isoformat()
        })
    
    return result


@router.get("/inventory/alerts/{workspace_id}")
def get_inventory_alerts(workspace_id: int, db: Session = Depends(get_db)):
    """Get low stock inventory items"""
    
    items = db.query(InventoryItem).filter(
        InventoryItem.workspace_id == workspace_id,
        InventoryItem.quantity <= InventoryItem.low_stock_threshold
    ).all()
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "threshold": item.low_stock_threshold,
            "unit": item.unit,
            "is_critical": item.quantity == 0
        }
        for item in items
    ]

@router.get("/analytics/{workspace_id}")
def get_dashboard_analytics(workspace_id: int, db: Session = Depends(get_db)):
    """Get comprehensive dashboard analytics for hackathon requirements"""
    
    from datetime import date
    
    # Get current date range
    today = date.today()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=7)
    
    # 1. BOOKING OVERVIEW
    today_bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.booking_date >= today_start,
        Booking.booking_date < today_start + timedelta(days=1)
    ).join(Booking.service).all()
    
    upcoming_bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.booking_date > datetime.now(),
        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
    ).count()
    
    completed_count = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.status == BookingStatus.COMPLETED,
        Booking.booking_date >= week_ago
    ).count()
    
    noshow_count = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.status == BookingStatus.NO_SHOW,
        Booking.booking_date >= week_ago
    ).count()
    
    # 2. LEADS & CONVERSATIONS
    new_inquiries = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Conversation.status == ConversationStatus.NEW
    ).count()
    
    ongoing_conversations = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Conversation.status == ConversationStatus.ONGOING
    ).count()
    
    unanswered = db.query(Message).join(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Message.is_from_customer == True,
        Message.is_read == False
    ).count()
    
    # 3. FORMS STATUS
    total_contacts = db.query(Contact).filter(
        Contact.workspace_id == workspace_id
    ).count()
    
    # 4. INVENTORY ALERTS
    low_stock_items = db.query(InventoryItem).filter(
        InventoryItem.workspace_id == workspace_id,
        InventoryItem.quantity <= InventoryItem.low_stock_threshold
    ).all()
    
    # 5. KEY ALERTS
    alerts = []
    
    unconfirmed_bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id,
        Booking.status == BookingStatus.PENDING,
        Booking.created_at < datetime.now() - timedelta(hours=24)
    ).count()
    
    if unconfirmed_bookings > 0:
        alerts.append({
            "type": "booking",
            "severity": "warning",
            "message": f"{unconfirmed_bookings} unconfirmed booking(s) need attention",
            "link": "/bookings",
            "count": unconfirmed_bookings
        })
    
    if unanswered > 0:
        alerts.append({
            "type": "message",
            "severity": "high",
            "message": f"{unanswered} unanswered message(s)",
            "link": "/inbox",
            "count": unanswered
        })
    
    if len(low_stock_items) > 0:
        alerts.append({
            "type": "inventory",
            "severity": "medium",
            "message": f"{len(low_stock_items)} low stock item(s)",
            "link": "/inventory",
            "count": len(low_stock_items)
        })
    
    # 6. BOOKING TRENDS (Last 7 days)
    booking_trends = []
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        count = db.query(Booking).filter(
            Booking.workspace_id == workspace_id,
            Booking.booking_date >= day_start,
            Booking.booking_date < day_end
        ).count()
        booking_trends.append({
            "date": day.strftime("%b %d"),
            "count": count
        })
    
    return {
        "booking_overview": {
            "today": len(today_bookings),
            "today_bookings": [
                {
                    "id": b.id,
                    "time": b.booking_date.strftime("%I:%M %p"),
                    "service": b.service.name,
                    "status": b.status.value
                } for b in today_bookings
            ],
            "upcoming": upcoming_bookings,
            "completed_this_week": completed_count,
            "no_show_this_week": noshow_count
        },
        "leads_conversations": {
            "new_inquiries": new_inquiries,
            "ongoing": ongoing_conversations,
            "unanswered": unanswered
        },
        "contacts": {
            "total": total_contacts
        },
        "inventory": {
            "low_stock_count": len(low_stock_items),
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "threshold": item.low_stock_threshold,
                    "is_critical": item.quantity == 0
                } for item in low_stock_items
            ]
        },
        "alerts": alerts,
        "booking_trends": booking_trends
    }