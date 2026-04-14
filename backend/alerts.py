import os
import requests
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# Twilio Configuration (SMS) - UPDATED
# ========================================
TWILIO_SID = "ACf60f450f29fabf5d4dd01680f2052f48"
TWILIO_TOKEN = "23e740f40d9a83da528c411d10133e4f"
TWILIO_PHONE = "+14787395985"

# ========================================
# SendGrid Configuration (Email)
# ========================================
SENDGRID_KEY = "ff69aee0-d6ac-4471-9359-ca339d9f316c"
SENDER_EMAIL = "alert4559@gmail.com"

# ========================================
# Test Phone Number (Your personal number for testing)
# ========================================
TEST_PHONE_NUMBER = "+919994247213"  # Add your personal number here

# ========================================
# Emergency Service Contacts
# ========================================

# Traffic Police Contacts (Update with real numbers)
TRAFFIC_POLICE_CONTACTS = [
    {
        "id": 1,
        "name": "Police Control Room",
        "badge_id": "PCR001",
        "phone": TEST_PHONE_NUMBER,  # Replace with actual police number
        "email": "controlroom@trafficpolice.gov.in",
        "zone": "Central",
        "type": "police",
        "active": True
    }
]

# Ambulance Services Contacts (Update with real numbers)
AMBULANCE_CONTACTS = [
    {
        "id": 1,
        "name": "Emergency Response Unit",
        "service_id": "AMB001",
        "phone": TEST_PHONE_NUMBER,  # Replace with actual ambulance number
        "email": "dispatch@ambulance.com",
        "zone": "Central",
        "type": "ambulance",
        "active": True
    }
]

# Zone mapping
ZONE_MAPPING = {
    "Intersection A": "North Zone",
    "Main St": "North Zone",
    "Highway 101": "East Zone",
    "Downtown": "South Zone",
    "Market Square": "South Zone",
    "Tunnel Entrance": "West Zone",
    "Bridge Crossing": "West Zone",
    "Image Upload Station": "Central",
    "Video Upload": "Central",
    "Live Camera Feed": "Central",
    "Upload": "Central"
}

# Vehicle Registration Database
VEHICLE_REGISTRATION_DB = {
    "MH01AB1234": {
        "owner_name": "Rajesh Sharma",
        "owner_phone": TEST_PHONE_NUMBER,
        "owner_email": "owner@example.com",
        "relation": "Self",
        "emergency_contact_name": "Family Member",
        "emergency_contact_phone": TEST_PHONE_NUMBER,
        "emergency_contact_relation": "Spouse"
    }
}

# ========================================
# Helper Functions
# ========================================

def get_zone_from_location(location):
    for key, value in ZONE_MAPPING.items():
        if key.lower() in location.lower():
            return value
    return "Central"

def get_contacts_by_zone(zone, contact_type=None):
    all_contacts = []
    if contact_type in [None, "police"]:
        all_contacts.extend([p for p in TRAFFIC_POLICE_CONTACTS if p["zone"] == zone and p["active"]])
    if contact_type in [None, "ambulance"]:
        all_contacts.extend([a for a in AMBULANCE_CONTACTS if a["zone"] == zone and a["active"]])
    return all_contacts

def get_vehicle_owner_from_plate(license_plate):
    if not license_plate:
        return None
    plate_clean = license_plate.upper().replace(" ", "")
    return VEHICLE_REGISTRATION_DB.get(plate_clean, None)

def get_family_members(owner_details):
    family_members = []
    if not owner_details:
        return family_members
    family_members.append({
        "name": owner_details.get("owner_name"),
        "phone": owner_details.get("owner_phone"),
        "email": owner_details.get("owner_email"),
        "relation": owner_details.get("relation", "Self"),
        "priority": 1
    })
    if owner_details.get("emergency_contact_phone"):
        family_members.append({
            "name": owner_details.get("emergency_contact_name", "Emergency Contact"),
            "phone": owner_details.get("emergency_contact_phone"),
            "email": None,
            "relation": owner_details.get("emergency_contact_relation", "Emergency Contact"),
            "priority": 2
        })
    return family_members

# ========================================
# SMS Function (Twilio)
# ========================================

def send_sms(phone_number, message, recipient_name=None, recipient_type=None):
    """Send SMS using Twilio"""
    
    print(f"\n📱 [DEBUG] Sending SMS:")
    print(f"   → To: {phone_number}")
    print(f"   → Type: {recipient_type}")
    print(f"   → Name: {recipient_name}")
    
    if not phone_number:
        print(f"   ❌ No phone number provided")
        return False, "No phone number"
    
    # Format phone number
    phone_number = phone_number.strip()
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    print(f"   → Formatted: {phone_number}")
    
    # Check credentials
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        print(f"   ❌ Twilio credentials missing!")
        return False, "Twilio not configured"
    
    try:
        # Twilio API
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        
        data = {
            "To": phone_number,
            "From": TWILIO_PHONE,
            "Body": message[:1600]
        }
        
        print(f"   📡 Sending to Twilio API...")
        response = requests.post(url, data=data, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=15)
        
        print(f"   📊 Response Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            print(f"   ✅ SMS SENT SUCCESSFULLY!")
            logger.info(f"SMS sent to {recipient_type}: {recipient_name}")
            return True, "SMS sent"
        else:
            print(f"   ❌ Twilio Error: {response.status_code}")
            print(f"   📝 Response: {response.text[:500]}")
            return False, f"Twilio error: {response.status_code}"
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return False, str(e)

# ========================================
# Email Function (SendGrid)
# ========================================

def send_email(email_address, subject, body_html, recipient_name=None, recipient_type=None):
    """Send Email using SendGrid"""
    
    print(f"\n📧 [DEBUG] Sending Email:")
    print(f"   → To: {email_address}")
    print(f"   → Subject: {subject}")
    
    if not email_address:
        return False, "No email"
    
    if not SENDGRID_KEY or not SENDER_EMAIL:
        print(f"   ❌ SendGrid credentials missing!")
        return False, "SendGrid not configured"
    
    try:
        url = "https://api.sendgrid.com/v3/mail/send"
        
        headers = {
            "Authorization": f"Bearer {SENDGRID_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "personalizations": [{"to": [{"email": email_address}]}],
            "from": {"email": SENDER_EMAIL},
            "subject": subject,
            "content": [{"type": "text/html", "value": body_html}]
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=15)
        
        if response.status_code == 202:
            print(f"   ✅ EMAIL SENT SUCCESSFULLY!")
            return True, "Email sent"
        else:
            print(f"   ❌ SendGrid Error: {response.status_code}")
            return False, f"SendGrid error: {response.status_code}"
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return False, str(e)

# ========================================
# Message Templates
# ========================================

def format_police_sms(alert_data):
    severity = alert_data.get("severity", "Unknown")
    confidence = alert_data.get("confidence", 0)
    location = alert_data.get("location", "Unknown")
    
    return f"""🚨 ACCIDENT DETECTED!

Severity: {severity}
Confidence: {confidence}%
Location: {location}
Time: {datetime.now().strftime('%H:%M:%S')}

ACTIONS REQUIRED:
1. Dispatch patrol unit
2. Coordinate ambulance
3. Secure the scene"""

def format_ambulance_sms(alert_data):
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    
    return f"""🚑 MEDICAL EMERGENCY!

Accident Reported
Severity: {severity}
Location: {location}
Time: {datetime.now().strftime('%H:%M:%S')}

ACTION: Dispatch nearest ambulance
Prepare trauma team for {severity} severity"""

def format_family_sms(alert_data, owner_details):
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    owner_name = owner_details.get("owner_name", "Your family member") if owner_details else "Your family member"
    
    return f"""🚨 ACCIDENT ALERT

Dear Family Member,

An accident has been detected involving {owner_name}.

Location: {location}
Severity: {severity}
Time: {datetime.now().strftime('%H:%M:%S')}

Emergency Response:
✓ Police dispatched
✓ Ambulance en route

Stay calm. Help is on the way."""

def format_police_email(alert_data):
    return """<html><body><h2>🚨 ACCIDENT ALERT</h2><p>Check the dashboard for details.</p></body></html>"""

def format_ambulance_email(alert_data):
    return """<html><body><h2>🚑 MEDICAL EMERGENCY</h2><p>Check the dashboard for details.</p></body></html>"""

def format_family_email(alert_data, owner_details):
    return """<html><body><h2>🚨 ACCIDENT ALERT</h2><p>Check the dashboard for details.</p></body></html>"""

# ========================================
# MAIN ALERT FUNCTION
# ========================================

def send_alerts(alert_data):
    """Main alert function - sends to Police, Ambulance, and Family"""
    
    print(f"\n{'='*70}")
    print(f"🚨 ALERT TRIGGERED!")
    print(f"📦 Alert Data: {alert_data}")
    print(f"{'='*70}")
    
    location = alert_data.get("location", "Unknown")
    zone = get_zone_from_location(location)
    license_plate = alert_data.get("license_plate", None)
    
    print(f"\n📍 Location: {location}")
    print(f"📍 Zone: {zone}")
    print(f"📊 Severity: {alert_data.get('severity', 'Unknown')}")
    print(f"📊 Confidence: {alert_data.get('confidence', 0)}%")
    
    alerts_summary = {
        "police": {"sms": 0, "email": 0, "contacts": []},
        "ambulance": {"sms": 0, "email": 0, "contacts": []},
        "family": {"sms": 0, "email": 0, "contacts": []}
    }
    
    # 1. Send to Police
    print(f"\n📡 NOTIFYING POLICE...")
    police_contacts = get_contacts_by_zone(zone, "police")
    
    for officer in police_contacts:
        sms_msg = format_police_sms(alert_data)
        sms_success, _ = send_sms(officer["phone"], sms_msg, officer["name"], "police")
        if sms_success:
            alerts_summary["police"]["sms"] += 1
            alerts_summary["police"]["contacts"].append(officer["name"])
    
    # 2. Send to Ambulance
    print(f"\n🚑 NOTIFYING AMBULANCE...")
    ambulance_contacts = get_contacts_by_zone(zone, "ambulance")
    
    for ambulance in ambulance_contacts:
        sms_msg = format_ambulance_sms(alert_data)
        sms_success, _ = send_sms(ambulance["phone"], sms_msg, ambulance["name"], "ambulance")
        if sms_success:
            alerts_summary["ambulance"]["sms"] += 1
            alerts_summary["ambulance"]["contacts"].append(ambulance["name"])
    
    # 3. Send to Family
    if license_plate:
        print(f"\n👨‍👩‍👧 NOTIFYING FAMILY...")
        owner_details = get_vehicle_owner_from_plate(license_plate)
        if owner_details:
            family_members = get_family_members(owner_details)
            for member in family_members:
                sms_msg = format_family_sms(alert_data, owner_details)
                sms_success, _ = send_sms(member["phone"], sms_msg, member["name"], "family")
                if sms_success:
                    alerts_summary["family"]["sms"] += 1
                    alerts_summary["family"]["contacts"].append(member["name"])
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 ALERT SUMMARY")
    print(f"{'='*70}")
    print(f"👮 Police: {len(alerts_summary['police']['contacts'])} notified")
    print(f"🚑 Ambulance: {len(alerts_summary['ambulance']['contacts'])} notified")
    print(f"👨‍👩‍👧 Family: {len(alerts_summary['family']['contacts'])} notified")
    print(f"{'='*70}\n")
    
    return {
        "success": True,
        "summary": alerts_summary
    }

# ========================================
# Quick Test Function
# ========================================

def test_sms():
    """Quick test to verify SMS is working"""
    print("\n🧪 TESTING SMS...")
    test_message = "🧪 TEST: Your Accident Detection System SMS is working!"
    success, message = send_sms(TEST_PHONE_NUMBER, test_message, "Test User", "test")
    if success:
        print("\n✅ SMS TEST PASSED! Check your phone.")
    else:
        print(f"\n❌ SMS TEST FAILED: {message}")
    return success

if __name__ == "__main__":
    test_sms()
