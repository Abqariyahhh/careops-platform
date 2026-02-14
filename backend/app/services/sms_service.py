from twilio.rest import Client
from app.models.integration import Integration, IntegrationType
from sqlalchemy.orm import Session

def send_sms(db: Session, workspace_id: int, to_phone: str, message: str):
    """Send SMS using workspace's configured SMS integration"""
    
    # Get SMS integration
    integration = db.query(Integration).filter(
        Integration.workspace_id == workspace_id,
        Integration.type == IntegrationType.SMS,
        Integration.is_active == True
    ).first()
    
    if not integration:
        raise Exception("SMS integration not configured")
    
    account_sid = integration.config.get('account_sid')
    auth_token = integration.config.get('auth_token')
    from_phone = integration.config.get('phone')
    
    try:
        client = Client(account_sid, auth_token)
        
        sms = client.messages.create(
            body=message,
            from_=from_phone,
            to=to_phone
        )
        
        return {
            "success": True,
            "sid": sms.sid,
            "message": "SMS sent successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
