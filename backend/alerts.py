import os
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# ==========================================
# CONFIGURATION (Loaded from Environment Variables)
# ==========================================
TWILIO_SID = os.getenv("ACf601450f29fabf5d4dd01680f2052f48")
TWILIO_TOKEN = os.getenv("614f4f07bfff3587434f76ae4be21d25")
TWILIO_PHONE = os.getenv("+14787395985")
ALERT_PHONE = os.getenv("+919994247213")

SENDGRID_KEY = os.getenv("ff69aee0-d6ac-4471-9359-ca339d9f316c")
SENDER_EMAIL = os.getenv("alert4559@gmail.com")

def send_alerts(details: dict):
    """
    Triggers both SMS and Email alerts.
    Called automatically by app.py when an accident is detected.
    """
    print(f"🚨 Attempting to send alerts for accident at {details.get('location')}...")
    
    # 1. Send SMS via Twilio
    send_sms(details)
    
    # 2. Send Email via SendGrid
    send_email(details)

def send_sms(details: dict):
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE, ALERT_PHONE]):
        print("⚠️ Twilio credentials missing. Skipping SMS.")
        return

    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        
        body_text = (
            f"🚨 ACCIDENT DETECTED!\n"
            f"Severity: {details.get('severity', 'High')}\n"
            f"Location: {details.get('location', 'Unknown')}\n"
            f"Time: {details.get('timestamp', 'Now')}\n"
            f"Action Required: Immediate response needed."
        )
        
        message = client.messages.create(
            body=body_text,
            from_=TWILIO_PHONE,
            to=ALERT_PHONE
        )
        print(f"✅ SMS Sent! SID: {message.sid}")
        
    except Exception as e:
        print(f"❌ SMS Error: {str(e)}")

def send_email(details: dict):
    if not all([SENDGRID_KEY, SENDER_EMAIL]):
        print("⚠️ SendGrid credentials missing. Skipping Email.")
        return

    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background: #f4f4f4;">
            <div style="background: white; padding: 20px; border-radius: 10px; max-width: 600px; margin: auto;">
                <h2 style="color: #d9534f;">🚨 Accident Alert</h2>
                <hr>
                <p><strong>Severity:</strong> {details.get('severity', 'High')}</p>
                <p><strong>Confidence:</strong> {details.get('confidence', 0)}%</p>
                <p><strong>Location:</strong> {details.get('location', 'Unknown')}</p>
                <p><strong>Camera ID:</strong> {details.get('camera_id', 'N/A')}</p>
                <div style="margin-top: 20px; padding: 10px; background: #f8d7da; color: #721c24; border-radius: 5px;">
                    <strong>Action Required:</strong> Please check the location immediately.
                </div>
            </div>
        </div>
        """
        
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails='emergency_services@example.com', # Replace with actual recipient
            subject='🚨 URGENT: Accident Detected',
            html_content=html_content
        )
        
        sg = SendGridAPIClient(SENDGRID_KEY)
        response = sg.send(message)
        print(f"✅ Email Sent! Status: {response.status_code}")
        
    except Exception as e:
        print(f"❌ Email Error: {str(e)}")
