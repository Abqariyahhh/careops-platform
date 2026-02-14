from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.workspace import Workspace
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationStatus, Message, MessageChannel
from app.models.form import Form
from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.services.email_service import send_email
from app.services.sms_service import send_sms
from datetime import datetime, timedelta

router = APIRouter()

# ============== CONTACT FORM ROUTES ==============

class ContactSubmission(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None

@router.get("/contact-form/{workspace_id}")
def get_contact_form(workspace_id: int, db: Session = Depends(get_db)):
    """Get contact form configuration"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get contact form
    form = db.query(Form).filter(
        Form.workspace_id == workspace_id,
        Form.name.contains("Contact")
    ).first()
    
    if not form:
        raise HTTPException(status_code=404, detail="Contact form not configured")
    
    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace.name,
        "form_id": form.id,
        "form_name": form.name,
        "fields": form.fields,
        "external_url": form.external_url
    }

@router.post("/contact-form/{workspace_id}/submit")
def submit_contact_form(
    workspace_id: int,
    data: ContactSubmission,
    db: Session = Depends(get_db)
):
    """Submit contact form - Creates contact, conversation, and sends welcome email"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create or get contact
    contact = db.query(Contact).filter(
        Contact.workspace_id == workspace_id,
        Contact.email == data.email
    ).first() if data.email else None
    
    if not contact:
        contact = Contact(
            workspace_id=workspace_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            message=data.message
        )
        db.add(contact)
        db.flush()
    
    # Create conversation
    conversation = Conversation(
        workspace_id=workspace_id,
        contact_id=contact.id,
        subject=f"Contact Form: {data.name}",
        status=ConversationStatus.NEW
    )
    db.add(conversation)
    db.flush()
    
    # Create initial message
    initial_message = Message(
        conversation_id=conversation.id,
        content=data.message or "No message provided",
        channel=MessageChannel.SYSTEM,
        is_from_customer=True,
        is_automated=False,
        is_read=False
    )
    db.add(initial_message)
    
    db.commit()
    db.refresh(contact)
    db.refresh(conversation)
    
    # Send welcome email (automation)
    if data.email and workspace.email_configured:
        try:
            welcome_html = f"""
            <html>
                <body>
                    <h2>Thank you for contacting {workspace.name}!</h2>
                    <p>Hi {data.name},</p>
                    <p>We've received your message and will get back to you shortly.</p>
                    <p>Best regards,<br>{workspace.name} Team</p>
                </body>
            </html>
            """
            
            email_result = send_email(
                db=db,
                workspace_id=workspace_id,
                to_email=data.email,
                subject=f"Thank you for contacting {workspace.name}",
                html_content=welcome_html
            )
            
            # Log automated welcome message
            if email_result.get("success"):
                welcome_msg = Message(
                    conversation_id=conversation.id,
                    content="Automated welcome email sent",
                    channel=MessageChannel.EMAIL,
                    is_from_customer=False,
                    is_automated=True,
                    is_read=True
                )
                db.add(welcome_msg)
                db.commit()
        except Exception as e:
            print(f"Email send failed: {e}")
    
    return {
        "success": True,
        "message": "Thank you! We'll be in touch soon.",
        "contact_id": contact.id,
        "conversation_id": conversation.id
    }

# ============== BOOKING ROUTES ==============

@router.get("/services/{workspace_id}")
def get_workspace_services(workspace_id: int, db: Session = Depends(get_db)):
    """Get all active services for a workspace"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    services = db.query(Service).filter(
        Service.workspace_id == workspace_id,
        Service.is_active == True
    ).all()
    
    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace.name,
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "duration_minutes": s.duration_minutes,
                "location": s.location,
                "available_days": s.available_days,
                "start_time": s.start_time,
                "end_time": s.end_time
            }
            for s in services
        ]
    }

@router.get("/service/{service_id}")
def get_service_details(service_id: int, db: Session = Depends(get_db)):
    """Get service details"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    workspace = db.query(Workspace).filter(Workspace.id == service.workspace_id).first()
    
    return {
        "service_id": service.id,
        "service_name": service.name,
        "description": service.description,
        "duration_minutes": service.duration_minutes,
        "location": service.location,
        "available_days": service.available_days,
        "start_time": service.start_time,
        "end_time": service.end_time,
        "workspace_name": workspace.name,
        "workspace_id": workspace.id
    }

class BookingSubmission(BaseModel):
    service_id: int
    booking_date: str  # ISO format datetime
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    notes: Optional[str] = None

@router.post("/book/{workspace_id}")
def create_booking(
    workspace_id: int,
    data: BookingSubmission,
    db: Session = Depends(get_db)
):
    """Create a booking"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    service = db.query(Service).filter(Service.id == data.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Create or get contact
    contact = db.query(Contact).filter(
        Contact.workspace_id == workspace_id,
        Contact.email == data.customer_email
    ).first()
    
    if not contact:
        contact = Contact(
            workspace_id=workspace_id,
            name=data.customer_name,
            email=data.customer_email,
            phone=data.customer_phone
        )
        db.add(contact)
        db.flush()
    
    # Create booking
    booking = Booking(
        workspace_id=workspace_id,
        contact_id=contact.id,
        service_id=service.id,
        booking_date=datetime.fromisoformat(data.booking_date.replace('Z', '+00:00')),
        status=BookingStatus.PENDING,
        notes=data.notes
    )
    db.add(booking)
    db.flush()
    
    # Create conversation
    conversation = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Conversation.contact_id == contact.id
    ).first()
    
    if not conversation:
        conversation = Conversation(
            workspace_id=workspace_id,
            contact_id=contact.id,
            subject=f"Booking: {data.customer_name}",
            status=ConversationStatus.ONGOING
        )
        db.add(conversation)
        db.flush()
    
    # Log booking message
    booking_message = Message(
        conversation_id=conversation.id,
        content=f"Booking created: {service.name} on {data.booking_date}",
        channel=MessageChannel.SYSTEM,
        is_from_customer=True,
        is_automated=False,
        is_read=False
    )
    db.add(booking_message)
    
    db.commit()
    db.refresh(booking)
    
    # ✅ FEATURE 0: Create Google Calendar Event
    try:
        from app.services.calendar_service import create_calendar_event
        
        # Calculate end time based on service duration
        end_time = booking.booking_date + timedelta(minutes=service.duration_minutes)
        
        calendar_result = create_calendar_event(
            db=db,
            workspace_id=workspace_id,
            booking_data={
                'service_name': service.name,
                'customer_name': data.customer_name,
                'customer_email': data.customer_email,
                'customer_phone': data.customer_phone,
                'notes': data.notes or '',
                'start_time': booking.booking_date.isoformat(),
                'end_time': end_time.isoformat()
            }
        )
        
        if calendar_result.get('success'):
            booking.calendar_event_id = calendar_result.get('event_id')
            db.commit()
            print(f"✅ Calendar event created: {calendar_result.get('link')}")
    except Exception as e:
        print(f"⚠️ Calendar event creation skipped: {e}")
        # Don't fail booking if calendar fails
    
    # ✅ FEATURE 1: Send confirmation email WITH post-booking forms
    if data.customer_email and workspace.email_configured:
        try:
            # Get forms associated with this workspace
            post_booking_forms = db.query(Form).filter(
                Form.workspace_id == workspace_id,
                Form.is_active == True
            ).all()
            
            # Build forms section for email
            forms_html = ""
            if post_booking_forms:
                forms_html = """
                <div style="background: #FEF3C7; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <h3 style="color: #92400E; margin-top: 0;">📝 Please Complete These Forms</h3>
                    <p style="color: #78350F;">To make your appointment smoother, please fill out the following forms before your visit:</p>
                    <ul style="color: #78350F;">
                """
                for form in post_booking_forms:
                    # Use external URL if exists, otherwise generate internal link
                    form_url = form.external_url if form.external_url else f"http://localhost:3000/form/{form.id}"
                    forms_html += f'<li style="margin: 10px 0;"><a href="{form_url}" style="color: #92400E; font-weight: bold; text-decoration: underline;">{form.name}</a>'
                    if form.description:
                        forms_html += f'<br/><span style="font-size: 13px; color: #78350F;">{form.description}</span>'
                    forms_html += '</li>'
                
                forms_html += """
                    </ul>
                    <p style="color: #78350F; font-size: 14px; margin-bottom: 0;">
                        <strong>⚠️ Important:</strong> Completing these forms in advance will help us serve you better.
                    </p>
                </div>
                """
            
            # Build complete email
            confirmation_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">✅ Booking Confirmed!</h1>
                </div>
                
                <div style="background: white; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p style="font-size: 18px; color: #111827;">Hi <strong>{data.customer_name}</strong>,</p>
                    
                    <p style="color: #4b5563; font-size: 16px;">Your booking has been confirmed! We're looking forward to seeing you.</p>
                    
                    <div style="background: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1F2937;">📅 Booking Details</h3>
                        <table style="width: 100%; color: #374151;">
                            <tr>
                                <td style="padding: 8px 0;"><strong>Service:</strong></td>
                                <td style="padding: 8px 0;">{service.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;"><strong>Date & Time:</strong></td>
                                <td style="padding: 8px 0;">{booking.booking_date.strftime('%B %d, %Y at %I:%M %p')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;"><strong>Duration:</strong></td>
                                <td style="padding: 8px 0;">{service.duration_minutes} minutes</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background: #DBEAFE; padding: 20px; border-radius: 8px; border-left: 4px solid #3B82F6; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1E40AF;">📍 Location</h3>
                        <p style="color: #1E3A8A; margin: 0; font-size: 16px; font-weight: bold;">{service.location}</p>
                        <p style="color: #1E40AF; margin-top: 10px; font-size: 14px;">
                            <strong>Important:</strong> Please arrive 5-10 minutes early.
                        </p>
                    </div>
                    
                    {forms_html}
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E5E7EB;">
                        <p style="color: #6B7280; font-size: 14px; margin: 0;">
                            Need to reschedule or have questions? Reply to this email or contact us.
                        </p>
                    </div>
                </div>
                
                <div style="background: #F9FAFB; padding: 20px; text-align: center; border-radius: 0 0 10px 10px;">
                    <p style="color: #6B7280; font-size: 12px; margin: 0;">
                        Powered by <strong>{workspace.name}</strong>
                    </p>
                </div>
            </div>
            """
            
            # Send email
            email_result = send_email(
                db=db,
                workspace_id=workspace_id,
                to_email=data.customer_email,
                subject=f"✅ Booking Confirmed - {service.name}",
                html_content=confirmation_html
            )
            
            # Log confirmation email
            if email_result.get("success"):
                email_msg = Message(
                    conversation_id=conversation.id,
                    content="Booking confirmation email sent",
                    channel=MessageChannel.EMAIL,
                    is_from_customer=False,
                    is_automated=True,
                    is_read=True
                )
                db.add(email_msg)
                db.commit()
                
                print(f"✅ Confirmation email sent to {data.customer_email}")
                if post_booking_forms:
                    print(f"📝 Included {len(post_booking_forms)} forms in email")
                    
        except Exception as e:
            print(f"⚠️ Failed to send confirmation email: {e}")
            # Don't fail the booking if email fails
    
    # ✅ FEATURE 2: Send SMS confirmation
    if data.customer_phone:
        try:
            sms_message = f"""✅ Booking Confirmed!

{service.name}
📅 {booking.booking_date.strftime('%b %d, %Y at %I:%M %p')}
📍 {service.location}

Please arrive 5-10 minutes early.

- {workspace.name}"""
            
            sms_result = send_sms(
                db=db,
                workspace_id=workspace_id,
                to_phone=data.customer_phone,
                message=sms_message
            )
            
            if sms_result.get("success"):
                sms_msg = Message(
                    conversation_id=conversation.id,
                    content="Booking confirmation SMS sent",
                    channel=MessageChannel.SMS,
                    is_from_customer=False,
                    is_automated=True,
                    is_read=True
                )
                db.add(sms_msg)
                db.commit()
                print(f"✅ Confirmation SMS sent to {data.customer_phone}")
        except Exception as e:
            print(f"⚠️ Failed to send confirmation SMS: {e}")
            # Don't fail the booking if SMS fails
    
    return {
        "success": True,
        "message": "Booking created successfully!",
        "booking_id": booking.id,
        "confirmation_sent": workspace.email_configured,
        "sms_sent": data.customer_phone is not None
    }

@router.post("/manual-lead/{workspace_id}")
def create_manual_lead(
    workspace_id: int,
    data: ContactSubmission,  # Reuse existing model
    db: Session = Depends(get_db)
):
    """Manual lead entry for external form submissions (demo/training)"""
    # Reuse exact same logic as submit_contact_form
    return submit_contact_form(workspace_id, data, db)