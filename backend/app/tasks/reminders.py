from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.service import Service
from app.models.workspace import Workspace
from app.services.email_service import send_email
import logging

logger = logging.getLogger(__name__)

def send_booking_reminders():
    """
    Check for bookings in the next 24 hours and send reminders
    Run this function every hour via cron job or scheduler
    Works globally for any timezone by using UTC consistently
    """
    db = SessionLocal()
    
    try:
        # ✅ FIX: Use UTC consistently (works for any timezone globally)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        reminder_start = now + timedelta(hours=23)
        reminder_end = now + timedelta(hours=25)
        
        print(f"🕐 Current UTC: {now}")
        print(f"🔍 Checking for bookings between {reminder_start} and {reminder_end} UTC")
        
        # Find bookings in this window that need reminders
        bookings_to_remind = db.query(Booking).filter(
            Booking.booking_date >= reminder_start,
            Booking.booking_date <= reminder_end,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING])
        ).all()
        
        print(f"📋 Found {len(bookings_to_remind)} booking(s) to remind")
        
        reminders_sent = 0
        
        for booking in bookings_to_remind:
            try:
                # Get related data
                contact = db.query(Contact).filter(Contact.id == booking.contact_id).first()
                service = db.query(Service).filter(Service.id == booking.service_id).first()
                workspace = db.query(Workspace).filter(Workspace.id == booking.workspace_id).first()
                
                if not contact or not service or not workspace:
                    print(f"⚠️ Missing data for booking {booking.id}")
                    continue
                
                if not contact.email:
                    print(f"⚠️ No email for contact {contact.id}")
                    continue
                
                # Build reminder email
                reminder_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #F59E0B 0%, #EF4444 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                        <h1 style="color: white; margin: 0;">⏰ Appointment Reminder</h1>
                    </div>
                    
                    <div style="background: white; padding: 30px; border: 1px solid #e5e7eb;">
                        <p style="font-size: 18px; color: #111827;">Hi <strong>{contact.name}</strong>,</p>
                        
                        <p style="color: #4b5563; font-size: 16px;">This is a friendly reminder about your upcoming appointment <strong>tomorrow</strong>:</p>
                        
                        <div style="background: #FEF3C7; padding: 20px; border-radius: 8px; border-left: 4px solid #F59E0B; margin: 20px 0;">
                            <h3 style="margin-top: 0; color: #92400E;">📅 Your Appointment</h3>
                            <table style="width: 100%; color: #78350F;">
                                <tr>
                                    <td style="padding: 8px 0; width: 40%;"><strong>Service:</strong></td>
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
                                <tr>
                                    <td style="padding: 8px 0;"><strong>Location:</strong></td>
                                    <td style="padding: 8px 0;">{service.location}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div style="background: #DBEAFE; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <p style="color: #1E40AF; margin: 0; font-size: 15px;">
                                <strong>📍 Important Reminder:</strong><br/>
                                Please arrive 5-10 minutes early to complete any required check-in procedures.
                            </p>
                        </div>
                        
                        <div style="background: #FEE2E2; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <p style="color: #991B1B; margin: 0; font-size: 14px;">
                                <strong>Need to reschedule?</strong><br/>
                                Please contact us as soon as possible if you need to make any changes.
                            </p>
                        </div>
                        
                        <p style="color: #111827; margin-top: 20px; font-size: 16px;">
                            We look forward to seeing you tomorrow! 😊
                        </p>
                    </div>
                    
                    <div style="background: #F9FAFB; padding: 20px; text-align: center; border-radius: 0 0 10px 10px;">
                        <p style="color: #6B7280; font-size: 12px; margin: 0;">
                            Powered by <strong>{workspace.name}</strong>
                        </p>
                    </div>
                </div>
                """
                
                # Send reminder email
                send_email(
                    db=db,
                    workspace_id=booking.workspace_id,
                    to_email=contact.email,
                    subject=f"⏰ Reminder: {service.name} Tomorrow at {booking.booking_date.strftime('%I:%M %p')}",
                    html_content=reminder_html
                )
                
                reminders_sent += 1
                print(f"✅ Reminder sent for booking {booking.id} to {contact.email}")
                
            except Exception as e:
                print(f"❌ Failed to send reminder for booking {booking.id}: {e}")
                logger.error(f"Failed to send reminder for booking {booking.id}: {e}")
        
        print(f"📧 Sent {reminders_sent} booking reminders")
        logger.info(f"Sent {reminders_sent} booking reminders")
        return reminders_sent
        
    except Exception as e:
        print(f"❌ Error in send_booking_reminders: {e}")
        logger.error(f"Error in send_booking_reminders: {e}")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    # For testing - run directly
    print("🚀 Starting reminder check...")
    count = send_booking_reminders()
    print(f"✅ Complete! Sent {count} reminders")
