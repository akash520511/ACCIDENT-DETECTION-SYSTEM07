import os
import requests
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# Twilio Configuration (SMS)
# ========================================
TWILIO_SID = "ACf601450f29fabf5d4dd01680f2052f48"
TWILIO_TOKEN = "614f4f07bfff3587434f76ae4be21d25"
TWILIO_PHONE = "+14787395985"

# ========================================
# SendGrid Configuration (Email)
# ========================================
SENDGRID_KEY = "ff69aee0-d6ac-4471-9359-ca339d9f316c"
SENDER_EMAIL = "alert4559@gmail.com"

# ========================================
# Emergency Service Contacts
# ========================================

# Traffic Police Contacts
TRAFFIC_POLICE_CONTACTS = [
    {
        "id": 1,
        "name": "Officer Rajesh Kumar",
        "badge_id": "TP001",
        "phone": "+919876543210",
        "email": "rajesh.kumar@trafficpolice.gov.in",
        "zone": "North Zone",
        "type": "police",
        "active": True
    },
    {
        "id": 2,
        "name": "Officer Priya Sharma",
        "badge_id": "TP002",
        "phone": "+919876543211",
        "email": "priya.sharma@trafficpolice.gov.in",
        "zone": "South Zone",
        "type": "police",
        "active": True
    },
    {
        "id": 3,
        "name": "Officer Amit Patel",
        "badge_id": "TP003",
        "phone": "+919876543212",
        "email": "amit.patel@trafficpolice.gov.in",
        "zone": "East Zone",
        "type": "police",
        "active": True
    },
    {
        "id": 4,
        "name": "Officer Sunita Verma",
        "badge_id": "TP004",
        "phone": "+919876543213",
        "email": "sunita.verma@trafficpolice.gov.in",
        "zone": "West Zone",
        "type": "police",
        "active": True
    },
    {
        "id": 5,
        "name": "Police Control Room",
        "badge_id": "PCR001",
        "phone": "+919876543214",
        "email": "controlroom@trafficpolice.gov.in",
        "zone": "Central",
        "type": "police",
        "active": True
    }
]

# Ambulance Services Contacts
AMBULANCE_CONTACTS = [
    {
        "id": 1,
        "name": "City Hospital Ambulance",
        "service_id": "AMB001",
        "phone": "+919876543215",
        "email": "ambulance@cityhospital.com",
        "zone": "North Zone",
        "type": "ambulance",
        "active": True
    },
    {
        "id": 2,
        "name": "Medicare Emergency Services",
        "service_id": "AMB002",
        "phone": "+919876543216",
        "email": "dispatch@medicare.com",
        "zone": "South Zone",
        "type": "ambulance",
        "active": True
    },
    {
        "id": 3,
        "name": "LifeLine Ambulance",
        "service_id": "AMB003",
        "phone": "+919876543217",
        "email": "emergency@lifeline.com",
        "zone": "East Zone",
        "type": "ambulance",
        "active": True
    },
    {
        "id": 4,
        "name": "Central Ambulance Service",
        "service_id": "AMB004",
        "phone": "+919876543218",
        "email": "dispatch@centralambulance.com",
        "zone": "West Zone",
        "type": "ambulance",
        "active": True
    },
    {
        "id": 5,
        "name": "Emergency Response Unit",
        "service_id": "AMB005",
        "phone": "+919876543219",
        "email": "eru@health.gov.in",
        "zone": "Central",
        "type": "ambulance",
        "active": True
    }
]

# Zone mapping for location-based routing
ZONE_MAPPING = {
    "Intersection A": "North Zone",
    "Main St": "North Zone",
    "Highway 101": "East Zone",
    "Downtown": "South Zone",
    "Market Square": "South Zone",
    "Tunnel Entrance": "West Zone",
    "Bridge Crossing": "West Zone",
    "Upload": "Central",
    "Video Upload": "Central",
    "Live Camera Feed": "Central"
}

# Vehicle Registration Database (to find family members)
# In production, this would come from RTO database
VEHICLE_REGISTRATION_DB = {
    "MH01AB1234": {
        "owner_name": "Rajesh Sharma",
        "owner_phone": "+919876543220",
        "owner_email": "rajesh.sharma@email.com",
        "relation": "Self",
        "alternative_contact": "+919876543221",
        "address": "Andheri East, Mumbai"
    },
    "DL02CD5678": {
        "owner_name": "Priya Patel",
        "owner_phone": "+919876543222",
        "owner_email": "priya.patel@email.com",
        "relation": "Self",
        "alternative_contact": "+919876543223",
        "address": "Connaught Place, Delhi"
    },
    "KA03EF9012": {
        "owner_name": "Amit Kumar",
        "owner_phone": "+919876543224",
        "owner_email": "amit.kumar@email.com",
        "relation": "Self",
        "emergency_contact_name": "Sneha Kumar",
        "emergency_contact_phone": "+919876543225",
        "emergency_contact_relation": "Spouse",
        "address": "Indiranagar, Bangalore"
    },
    "TN04GH3456": {
        "owner_name": "Sunil Verma",
        "owner_phone": "+919876543226",
        "owner_email": "sunil.verma@email.com",
        "relation": "Self",
        "emergency_contact_name": "Anita Verma",
        "emergency_contact_phone": "+919876543227",
        "emergency_contact_relation": "Wife",
        "address": "T Nagar, Chennai"
    },
    "GJ05IJ7890": {
        "owner_name": "Meera Desai",
        "owner_phone": "+919876543228",
        "owner_email": "meera.desai@email.com",
        "relation": "Self",
        "emergency_contact_name": "Rahul Desai",
        "emergency_contact_phone": "+919876543229",
        "emergency_contact_relation": "Brother",
        "address": "Vastrapur, Ahmedabad"
    }
}


# ========================================
# Helper Functions
# ========================================

def get_zone_from_location(location):
    """Determine zone based on accident location"""
    for key, value in ZONE_MAPPING.items():
        if key.lower() in location.lower():
            return value
    return "Central"


def get_contacts_by_zone(zone, contact_type=None):
    """Get contacts filtered by zone and type"""
    all_contacts = []
    
    if contact_type in [None, "police"]:
        all_contacts.extend([p for p in TRAFFIC_POLICE_CONTACTS if p["zone"] == zone and p["active"]])
    
    if contact_type in [None, "ambulance"]:
        all_contacts.extend([a for a in AMBULANCE_CONTACTS if a["zone"] == zone and a["active"]])
    
    return all_contacts


def get_vehicle_owner_from_plate(license_plate):
    """Get vehicle owner details from license plate number"""
    # In production, this would query your database
    # For now, we'll use a demo lookup
    plate_clean = license_plate.upper().replace(" ", "")
    return VEHICLE_REGISTRATION_DB.get(plate_clean, None)


def get_family_members(owner_details):
    """Get family members/emergency contacts for the vehicle owner"""
    family_members = []
    
    if not owner_details:
        return family_members
    
    # Add owner as primary contact
    family_members.append({
        "name": owner_details.get("owner_name"),
        "phone": owner_details.get("owner_phone"),
        "email": owner_details.get("owner_email"),
        "relation": owner_details.get("relation", "Self"),
        "priority": 1
    })
    
    # Add emergency contact if available
    if owner_details.get("emergency_contact_phone"):
        family_members.append({
            "name": owner_details.get("emergency_contact_name", "Emergency Contact"),
            "phone": owner_details.get("emergency_contact_phone"),
            "email": None,
            "relation": owner_details.get("emergency_contact_relation", "Emergency Contact"),
            "priority": 2
        })
    
    # Add alternative contact
    if owner_details.get("alternative_contact"):
        family_members.append({
            "name": "Alternative Contact",
            "phone": owner_details.get("alternative_contact"),
            "email": None,
            "relation": "Family",
            "priority": 3
        })
    
    return family_members


# ========================================
# SMS Functions
# ========================================

def send_sms(phone_number, message, recipient_name=None, recipient_type=None):
    """Send SMS using Twilio"""
    if not phone_number:
        return False, "No phone number provided"
    
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        logger.warning("Twilio credentials not configured.")
        return False, "Twilio not configured"
    
    try:
        # Clean phone number
        phone_number = phone_number.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Add prefix based on recipient type
        prefix = ""
        if recipient_type == "police":
            prefix = f"🚔 To: Officer {recipient_name}\n"
        elif recipient_type == "ambulance":
            prefix = f"🚑 To: {recipient_name}\n"
        elif recipient_type == "family":
            prefix = f"👨‍👩‍👧 To: {recipient_name}\n"
        
        full_message = prefix + message
        
        # Twilio API
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        
        data = {
            "To": phone_number,
            "From": TWILIO_PHONE,
            "Body": full_message[:1600]  # SMS length limit
        }
        
        response = requests.post(url, data=data, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"SMS sent to {recipient_type}: {recipient_name} at {phone_number}")
            return True, "SMS sent"
        else:
            return False, f"Twilio error: {response.status_code}"
            
    except Exception as e:
        logger.error(f"SMS error: {str(e)}")
        return False, str(e)


# ========================================
# Email Functions
# ========================================

def send_email(email_address, subject, body_html, recipient_name=None, recipient_type=None):
    """Send Email using SendGrid"""
    if not email_address:
        return False, "No email provided"
    
    if not SENDGRID_KEY or not SENDER_EMAIL:
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
        
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 202:
            logger.info(f"Email sent to {recipient_type}: {recipient_name}")
            return True, "Email sent"
        else:
            return False, f"SendGrid error: {response.status_code}"
            
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False, str(e)


# ========================================
# Message Templates for Different Recipients
# ========================================

def format_police_sms(alert_data):
    """SMS for Traffic Police"""
    severity = alert_data.get("severity", "Unknown")
    confidence = alert_data.get("confidence", 0)
    location = alert_data.get("location", "Unknown")
    camera_id = alert_data.get("camera_id", "Unknown")
    
    return f"""🚨 ACCIDENT ALERT!

Severity: {severity}
Confidence: {confidence}%
Location: {location}
Camera: {camera_id}

ACTION REQUIRED:
- Dispatch patrol unit
- Coordinate ambulance
- Secure scene
- Direct traffic

Control Room: +919876543214"""


def format_ambulance_sms(alert_data):
    """SMS for Ambulance Services"""
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    camera_id = alert_data.get("camera_id", "Unknown")
    timestamp = alert_data.get("timestamp", datetime.now().strftime("%H:%M:%S"))
    
    return f"""🚑 MEDICAL EMERGENCY!

Accident Reported
Severity: {severity}
Location: {location}
Time: {timestamp}

PATIENT INFO: Unknown - Prepare trauma team
NEAREST HOSPITAL: Check dispatch

Priority: URGENT
Ambulance dispatched to: {location}"""


def format_family_sms(alert_data, owner_details):
    """SMS for Family Members"""
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    camera_id = alert_data.get("camera_id", "Unknown")
    timestamp = alert_data.get("timestamp", datetime.now().strftime("%H:%M:%S"))
    
    vehicle_plate = alert_data.get("license_plate", "Unknown")
    owner_name = owner_details.get("owner_name", "Your family member") if owner_details else "Your family member"
    
    return f"""🚨 ACCIDENT ALERT - FAMILY NOTIFICATION

Dear Family Member,

We regret to inform you that an accident involving vehicle {vehicle_plate} has been detected.

Owner: {owner_name}
Location: {location}
Time: {timestamp}
Severity: {severity}

EMERGENCY RESPONSE:
✓ Police dispatched
✓ Ambulance en route
✓ Hospital on standby

For updates, contact:
Police Control: +919876543214
Ambulance: +919876543219

Please proceed to the location if needed.
Stay calm. Help is on the way.

- Accident Detection System"""


def format_police_email(alert_data):
    """Detailed Email for Police"""
    severity = alert_data.get("severity", "Unknown")
    confidence = alert_data.get("confidence", 0)
    location = alert_data.get("location", "Unknown")
    camera_id = alert_data.get("camera_id", "Unknown")
    timestamp = alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    license_plate = alert_data.get("license_plate", "Not detected")
    
    severity_colors = {
        "Critical": "#FF0000",
        "High": "#FF4444",
        "Major": "#FF6666",
        "Medium": "#FFA500",
        "Minor": "#FFCC00",
        "Low": "#00CC00"
    }
    color = severity_colors.get(severity, "#FF0000")
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f4f4f4; padding: 20px; border-radius: 0 0 10px 10px; }}
        .alert-box {{ background: white; border-left: 4px solid {color}; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .label {{ font-weight: bold; color: #333; width: 140px; display: inline-block; }}
        .action-box {{ background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 TRAFFIC POLICE ALERT</h2>
            <p>Accident Detection System - Immediate Action Required</p>
        </div>
        <div class="content">
            <div class="alert-box">
                <h3 style="color: {color};">⚠️ ACCIDENT DETECTED</h3>
                <p><span class="label">Severity:</span> <strong style="color:{color};">{severity}</strong></p>
                <p><span class="label">Confidence:</span> {confidence}%</p>
                <p><span class="label">Location:</span> {location}</p>
                <p><span class="label">Camera ID:</span> {camera_id}</p>
                <p><span class="label">Vehicle Plate:</span> {license_plate}</p>
                <p><span class="label">Time:</span> {timestamp}</p>
            </div>
            
            <div class="action-box">
                <h4>📋 IMMEDIATE ACTIONS REQUIRED</h4>
                <ul>
                    <li>✓ Dispatch patrol unit to {location}</li>
                    <li>✓ Coordinate with ambulance services</li>
                    <li>✓ Secure accident scene and manage traffic</li>
                    <li>✓ Identify vehicle owner and notify family</li>
                    <li>✓ File incident report in system</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>This is an automated alert. Please acknowledge receipt.</p>
                <p>🚔 Police Control Room: +919876543214 | 24x7</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def format_ambulance_email(alert_data):
    """Detailed Email for Ambulance"""
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    timestamp = alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #c0392b, #e74c3c); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f4f4f4; padding: 20px; border-radius: 0 0 10px 10px; }}
        .alert-box {{ background: white; border-left: 4px solid #e74c3c; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .action-box {{ background: #ffeaa7; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚑 MEDICAL EMERGENCY</h2>
            <p>Accident Alert - Immediate Dispatch Required</p>
        </div>
        <div class="content">
            <div class="alert-box">
                <h3>⚠️ ACCIDENT REPORT</h3>
                <p><strong>Severity:</strong> {severity}</p>
                <p><strong>Location:</strong> {location}</p>
                <p><strong>Time:</strong> {timestamp}</p>
                <p><strong>Status:</strong> Active - Responding</p>
            </div>
            
            <div class="action-box">
                <h4>🚑 AMBULANCE DISPATCH INSTRUCTIONS</h4>
                <ul>
                    <li>Dispatch nearest ambulance to {location}</li>
                    <li>Alert nearest hospital emergency room</li>
                    <li>Prepare trauma team for {severity} severity</li>
                    <li>Coordinate with police at scene</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>Emergency Response Unit | 24x7</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def format_family_email(alert_data, owner_details):
    """Detailed Email for Family Members"""
    severity = alert_data.get("severity", "Unknown")
    location = alert_data.get("location", "Unknown")
    timestamp = alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    license_plate = alert_data.get("license_plate", "Unknown")
    owner_name = owner_details.get("owner_name", "Your family member") if owner_details else "Your family member"
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #e67e22, #f39c12); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f4f4f4; padding: 20px; border-radius: 0 0 10px 10px; }}
        .alert-box {{ background: white; border-left: 4px solid #e67e22; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .action-box {{ background: #d5f5e3; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 ACCIDENT ALERT</h2>
            <p>Family Notification - Important Information</p>
        </div>
        <div class="content">
            <div class="alert-box">
                <h3>Dear Family Member,</h3>
                <p>We regret to inform you that an accident has been detected involving vehicle <strong>{license_plate}</strong>.</p>
                <p><strong>Vehicle Owner:</strong> {owner_name}</p>
                <p><strong>Location:</strong> {location}</p>
                <p><strong>Time:</strong> {timestamp}</p>
                <p><strong>Severity:</strong> {severity}</p>
            </div>
            
            <div class="action-box">
                <h4>✅ EMERGENCY RESPONSE INITIATED</h4>
                <ul>
                    <li>✓ Police dispatched to location</li>
                    <li>✓ Ambulance en route</li>
                    <li>✓ Hospital on standby</li>
                    <li>✓ Investigation in progress</li>
                </ul>
            </div>
            
            <div class="alert-box">
                <h4>📞 CONTACT INFORMATION</h4>
                <p><strong>Police Control Room:</strong> +919876543214</p>
                <p><strong>Ambulance Services:</strong> +919876543219</p>
                <p><strong>Nearest Hospital:</strong> Check with dispatch</p>
            </div>
            
            <div class="footer">
                <p>Please proceed to the location if needed.</p>
                <p>Stay calm. Help is on the way.</p>
                <p>This is an automated notification from the Accident Detection System.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


# ========================================
# Main Alert Function - Sends to ALL
# ========================================

def send_alerts(alert_data):
    """
    Send alerts to:
    1. Traffic Police (zone-based)
    2. Ambulance Services (zone-based)
    3. Vehicle Owner's Family Members
    """
    
    alerts_summary = {
        "police": {"sms": 0, "email": 0, "contacts": []},
        "ambulance": {"sms": 0, "email": 0, "contacts": []},
        "family": {"sms": 0, "email": 0, "contacts": []},
        "total_notified": 0
    }
    
    location = alert_data.get("location", "Unknown")
    zone = get_zone_from_location(location)
    license_plate = alert_data.get("license_plate", None)
    
    print(f"\n{'='*70}")
    print(f"🚨 ACCIDENT DETECTED AT: {location}")
    print(f"📍 Zone: {zone}")
    print(f"🚗 Vehicle Plate: {license_plate or 'Not detected'}")
    print(f"{'='*70}\n")
    
    # ========================================
    # 1. Send to Traffic Police
    # ========================================
    print("📡 NOTIFYING TRAFFIC POLICE...")
    police_contacts = get_contacts_by_zone(zone, "police")
    
    for officer in police_contacts:
        # SMS
        sms_msg = format_police_sms(alert_data)
        sms_success, _ = send_sms(officer["phone"], sms_msg, officer["name"], "police")
        if sms_success:
            alerts_summary["police"]["sms"] += 1
            alerts_summary["police"]["contacts"].append(officer["name"])
            print(f"  ✅ SMS to: {officer['name']} (Police)")
        
        # Email
        email_body = format_police_email(alert_data)
        email_success, _ = send_email(officer["email"], f"🚨 ACCIDENT ALERT - {location}", email_body, officer["name"], "police")
        if email_success:
            alerts_summary["police"]["email"] += 1
    
    # ========================================
    # 2. Send to Ambulance Services
    # ========================================
    print("\n🚑 NOTIFYING AMBULANCE SERVICES...")
    ambulance_contacts = get_contacts_by_zone(zone, "ambulance")
    
    for ambulance in ambulance_contacts:
        # SMS
        sms_msg = format_ambulance_sms(alert_data)
        sms_success, _ = send_sms(ambulance["phone"], sms_msg, ambulance["name"], "ambulance")
        if sms_success:
            alerts_summary["ambulance"]["sms"] += 1
            alerts_summary["ambulance"]["contacts"].append(ambulance["name"])
            print(f"  ✅ SMS to: {ambulance['name']} (Ambulance)")
        
        # Email
        email_body = format_ambulance_email(alert_data)
        email_success, _ = send_email(ambulance["email"], f"🚑 MEDICAL EMERGENCY - {location}", email_body, ambulance["name"], "ambulance")
        if email_success:
            alerts_summary["ambulance"]["email"] += 1
    
    # ========================================
    # 3. Send to Family Members (if license plate detected)
    # ========================================
    if license_plate:
        print(f"\n👨‍👩‍👧 NOTIFYING FAMILY MEMBERS for vehicle {license_plate}...")
        
        owner_details = get_vehicle_owner_from_plate(license_plate)
        
        if owner_details:
            family_members = get_family_members(owner_details)
            
            for member in family_members:
                # SMS
                sms_msg = format_family_sms(alert_data, owner_details)
                sms_success, _ = send_sms(member["phone"], sms_msg, member["name"], "family")
                if sms_success:
                    alerts_summary["family"]["sms"] += 1
                    alerts_summary["family"]["contacts"].append(member["name"])
                    print(f"  ✅ SMS to: {member['name']} ({member['relation']})")
                
                # Email (if available)
                if member.get("email"):
                    email_body = format_family_email(alert_data, owner_details)
                    email_success, _ = send_email(member["email"], f"🚨 Accident Alert - Vehicle {license_plate}", email_body, member["name"], "family")
                    if email_success:
                        alerts_summary["family"]["email"] += 1
        else:
            print(f"  ⚠️ No vehicle registration found for plate: {license_plate}")
    else:
        print("\n⚠️ License plate not detected - Family notification skipped")
    
    # ========================================
    # Summary
    # ========================================
    total_sms = alerts_summary["police"]["sms"] + alerts_summary["ambulance"]["sms"] + alerts_summary["family"]["sms"]
    total_email = alerts_summary["police"]["email"] + alerts_summary["ambulance"]["email"] + alerts_summary["family"]["email"]
    total_contacts = len(alerts_summary["police"]["contacts"]) + len(alerts_summary["ambulance"]["contacts"]) + len(alerts_summary["family"]["contacts"])
    
    print(f"\n{'='*70}")
    print(f"📊 ALERT SUMMARY")
    print(f"{'='*70}")
    print(f"👮 Police Notified: {len(alerts_summary['police']['contacts'])} officers")
    print(f"🚑 Ambulance Notified: {len(alerts_summary['ambulance']['contacts'])} services")
    print(f"👨‍👩‍👧 Family Notified: {len(alerts_summary['family']['contacts'])} members")
    print(f"-" * 40)
    print(f"📱 Total SMS Sent: {total_sms}")
    print(f"📧 Total Emails Sent: {total_email}")
    print(f"👥 Total Contacts Alerted: {total_contacts}")
    print(f"{'='*70}\n")
    
    # Log to database
    try:
        from . import database
        database.log_alert({
            "timestamp": datetime.now().isoformat(),
            "severity": alert_data.get("severity"),
            "confidence": alert_data.get("confidence"),
            "location": location,
            "camera_id": alert_data.get("camera_id"),
            "license_plate": license_plate,
            "police_notified": len(alerts_summary["police"]["contacts"]),
            "ambulance_notified": len(alerts_summary["ambulance"]["contacts"]),
            "family_notified": len(alerts_summary["family"]["contacts"]),
            "total_sms": total_sms,
            "total_email": total_email
        })
    except Exception as e:
        logger.error(f"Failed to log alert: {str(e)}")
    
    return {
        "success": total_contacts > 0,
        "summary": alerts_summary,
        "message": f"Alerts sent to {total_contacts} people (Police: {len(alerts_summary['police']['contacts'])}, Ambulance: {len(alerts_summary['ambulance']['contacts'])}, Family: {len(alerts_summary['family']['contacts'])})"
    }


# ========================================
# Test Function
# ========================================

def test_alerts():
    """Test the complete alert system"""
    test_data = {
        "severity": "High",
        "confidence": 94.2,
        "location": "Intersection A - Main St & 1st Ave",
        "camera_id": "CAM-1001",
        "license_plate": "MH01AB1234",  # Test with a known plate
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return send_alerts(test_data)
