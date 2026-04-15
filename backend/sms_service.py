import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
_twilio_client = None
_twilio_phone_number = None
_initialized = False

def init_twilio(account_sid: str, auth_token: str, phone_number: str):
    """Initialize Twilio client"""
    global _twilio_client, _twilio_phone_number, _initialized
    
    try:
        _twilio_client = Client(account_sid, auth_token)
        _twilio_phone_number = phone_number
        _initialized = True
        logger.info(f"✅ Twilio initialized with phone: {phone_number}")
        
        # Test the connection
        account = _twilio_client.api.accounts(account_sid).fetch()
        logger.info(f"✅ Twilio account verified: {account.friendly_name}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize Twilio: {str(e)}")
        _initialized = False
        return False

def is_initialized():
    """Check if Twilio is initialized"""
    return _initialized and _twilio_client is not None

async def send_sms(to: str, message: str) -> dict:
    """
    Send SMS using Twilio
    
    Args:
        to: Recipient phone number (with country code, e.g., +919994247213)
        message: SMS message content
    
    Returns:
        dict with success status and details
    """
    if not is_initialized():
        logger.error("Twilio not initialized")
        return {
            "success": False,
            "error": "SMS service not initialized",
            "simulated": True
        }
    
    try:
        # Validate phone number format
        if not to.startswith('+'):
            to = '+' + to
        
        # Send SMS
        sms = _twilio_client.messages.create(
            body=message,
            from_=_twilio_phone_number,
            to=to
        )
        
        logger.info(f"✅ SMS sent successfully to {to}")
        logger.info(f"   Message SID: {sms.sid}")
        logger.info(f"   Status: {sms.status}")
        
        return {
            "success": True,
            "sid": sms.sid,
            "status": sms.status,
            "to": to,
            "message": message[:50] + "..." if len(message) > 50 else message
        }
        
    except TwilioRestException as e:
        logger.error(f"❌ Twilio error: {str(e)}")
        
        # User-friendly error messages
        if e.code == 21211:
            error_msg = "Invalid phone number format"
        elif e.code == 21408:
            error_msg = "Phone number not verified in Twilio trial account"
        elif e.code == 21610:
            error_msg = "Phone number is not SMS capable"
        else:
            error_msg = str(e)
        
        return {
            "success": False,
            "error": error_msg,
            "code": e.code
        }
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def send_bulk_sms(recipients: list, message: str) -> list:
    """Send SMS to multiple recipients"""
    results = []
    for recipient in recipients:
        result = await send_sms(recipient, message)
        results.append(result)
    return results

def get_usage_stats():
    """Get Twilio account usage statistics"""
    if not is_initialized():
        return {"error": "Twilio not initialized"}
    
    try:
        # Get account info
        account = _twilio_client.api.accounts(_twilio_client.account_sid).fetch()
        
        return {
            "account_name": account.friendly_name,
            "account_status": account.status,
            "phone_number": _twilio_phone_number,
            "initialized": True
        }
    except Exception as e:
        return {"error": str(e), "initialized": False}
