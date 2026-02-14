from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.service import Service
from app.models.conversation import Conversation, Message, MessageChannel
from app.services.email_service import send_email
from app.services.sms_service import send_sms


router = APIRouter()


@router.get("/all/{workspace_id}")
def get_all_bookings(workspace_id: int, db: Session = Depends(get_db)):
    """Get all bookings for workspace"""
    
    bookings = db.query(Booking).filter(
        Booking.workspace_id == workspace_id
    ).join(Booking.contact).join(Booking.service).order_by(Booking.booking_date.desc()).all()
    
    return [
        {
            "id": b.id,
            "booking_date": b.booking_date.isoformat(),
            "status": b.status.value,
            "notes": b.notes,
            "customer_id": b.contact_id,
            "customer_name": b.contact.name,
            "customer_email": b.contact.email,
            "customer_phone": b.contact.phone,
            "service_id": b.service_id,
            "service_name": b.service.name,
            "duration_minutes": b.service.duration_minutes,
            "location": b.service.location,
            "created_at": b.created_at.isoformat()
        }
        for b in bookings
    ]


@router.get("/{booking_id}")
def get_booking_details(booking_id: int, db: Session = Depends(get_db)):
    """Get single booking details"""
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "id": booking.id,
        "booking_date": booking.booking_date.isoformat(),
        "status": booking.status.value,
        "notes": booking.notes,
        "customer": {
            "id": booking.contact.id,
            "name": booking.contact.name,
            "email": booking.contact.email,
            "phone": booking.contact.phone
        },
        "service": {
            "id": booking.service.id,
            "name": booking.service.name,
            "duration_minutes": booking.service.duration_minutes,
            "location": booking.service.location
        },
        "created_at": booking.created_at.isoformat()
    }


class UpdateBookingStatus(BaseModel):
    status: str  # "pending", "confirmed", "completed", "cancelled"
    send_notification: bool = True


@router.patch("/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    update: UpdateBookingStatus,
    db: Session = Depends(get_db)
):
    """Update booking status"""
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Update status
    if update.status == "pending":
        booking.status = BookingStatus.PENDING
    elif update.status == "confirmed":
        booking.status = BookingStatus.CONFIRMED
    elif update.status == "completed":
        booking.status = BookingStatus.COMPLETED
    elif update.status == "cancelled":
        booking.status = BookingStatus.CANCELLED
    else:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    db.commit()
    
    # Send notification if requested
    if update.send_notification:
        contact = booking.contact
        service = booking.service
        
        # Create notification message
        if update.status == "confirmed":
            subject = f"Booking Confirmed - {service.name}"
            message = f"Your booking for {service.name} on {booking.booking_date.strftime('%B %d, %Y at %I:%M %p')} has been confirmed!"
        elif update.status == "cancelled":
            subject = f"Booking Cancelled - {service.name}"
            message = f"Your booking for {service.name} on {booking.booking_date.strftime('%B %d, %Y at %I:%M %p')} has been cancelled."
        elif update.status == "completed":
            subject = f"Booking Completed - {service.name}"
            message = f"Thank you for visiting! Your booking for {service.name} has been completed."
        else:
            subject = None
            message = None
        
        if subject and message:
            # Find or create conversation
            conversation = db.query(Conversation).filter(
                Conversation.workspace_id == booking.workspace_id,
                Conversation.contact_id == booking.contact_id
            ).first()
            
            if conversation:
                # Log status change message
                status_msg = Message(
                    conversation_id=conversation.id,
                    content=f"Booking status updated to: {update.status}",
                    channel=MessageChannel.SYSTEM,
                    is_from_customer=False,
                    is_automated=True,
                    is_read=True
                )
                db.add(status_msg)
                db.commit()
                
                # Send email
                try:
                    if contact.email:
                        email_html = f"""
                        <html>
                            <body>
                                <h2>{subject}</h2>
                                <p>Hi {contact.name},</p>
                                <p>{message}</p>
                                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 15px 0;">
                                    <p><strong>Booking Details:</strong></p>
                                    <p>Service: {service.name}</p>
                                    <p>Date & Time: {booking.booking_date.strftime('%B %d, %Y at %I:%M %p')}</p>
                                    <p>Location: {service.location}</p>
                                    <p>Status: {update.status.upper()}</p>
                                </div>
                                <p>If you have any questions, please contact us.</p>
                                <p>Best regards,<br>Team</p>
                            </body>
                        </html>
                        """
                        
                        send_email(
                            db=db,
                            workspace_id=booking.workspace_id,
                            to_email=contact.email,
                            subject=subject,
                            html_content=email_html
                        )
                        
                        # Log email sent
                        email_msg = Message(
                            conversation_id=conversation.id,
                            content=f"Status notification email sent: {subject}",
                            channel=MessageChannel.EMAIL,
                            is_from_customer=False,
                            is_automated=True,
                            is_read=True
                        )
                        db.add(email_msg)
                        db.commit()
                except Exception as e:
                    print(f"Failed to send notification: {e}")
    
    return {
        "success": True,
        "booking_id": booking.id,
        "status": booking.status.value,
        "notification_sent": update.send_notification
    }


class UpdateBookingNotes(BaseModel):
    notes: str


@router.patch("/{booking_id}/notes")
def update_booking_notes(
    booking_id: int,
    update: UpdateBookingNotes,
    db: Session = Depends(get_db)
):
    """Update booking notes"""
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.notes = update.notes
    db.commit()
    
    return {"success": True, "booking_id": booking.id, "notes": booking.notes}


@router.delete("/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    """Delete booking"""
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    db.delete(booking)
    db.commit()
    
    return {"success": True, "message": "Booking deleted"}
