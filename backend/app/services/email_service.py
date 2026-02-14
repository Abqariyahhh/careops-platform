import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from app.models.integration import Integration, IntegrationType
from sqlalchemy.orm import Session


def send_email(db: Session, workspace_id: int, to_email: str, subject: str, html_content: str, from_email: str = None):
    """Send email using Brevo (SendInBlue)"""
    
    # Get email integration
    integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.EMAIL,
        Integration.is_active == True
    ).first()
    
    if not integration:
        raise Exception("Email integration not configured")
    
    # Configure Brevo API
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = integration.config.get('api_key')
    
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    # Get from details
    if not from_email:
        from_email = integration.config.get('from_email', 'nexspace.appointments@gmail.com')
    from_name = integration.config.get('from_name', 'NexSpace Appointments')
    
    try:
        # Send email
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender={"name": from_name, "email": from_email},
            subject=subject,
            html_content=html_content
        )
        
        response = api_instance.send_transac_email(send_smtp_email)
        
        print(f"✅ Email sent via Brevo to {to_email}")
        
        return {
            "success": True,
            "message": "Email sent successfully",
            "message_id": response.message_id
        }
    except ApiException as e:
        print(f"❌ Failed to send email: {e}")
        return {
            "success": False,
            "error": str(e)
        }
