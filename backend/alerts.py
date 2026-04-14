import os
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")
ALERT_PHONE = os.getenv("ALERT_PHONE_NUMBER")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

def send_alerts(details):
    if TWILIO_SID:
        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(body=f"ALERT: {details}", from_=TWILIO_PHONE, to=ALERT_PHONE)
        except: pass
