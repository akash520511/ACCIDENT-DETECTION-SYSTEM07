import os
import cv2
import numpy as np
import time
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import requests
import json

# Import custom modules
from model_loader import load_model, predict_single_frame
import database
import sms_service

# Initialize FastAPI app
app = FastAPI(
    title="Intelligent Accident Detection System",
    description="AI-powered accident detection with real-time analysis and SMS alerts",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories for saved frames
SAVED_FRAMES_DIR = os.path.join(os.path.dirname(__file__), "..", "saved_frames")
os.makedirs(SAVED_FRAMES_DIR, exist_ok=True)

# Mount static files
app.mount("/saved_frames", StaticFiles(directory=SAVED_FRAMES_DIR), name="saved_frames")

# Global variables
model = None
detection_active = False

# SMS Configuration (from your screenshot)
TWILIO_CONFIG = {
    "account_sid": "ACf60f450f29fabf5d4dd01680f2052f48",
    "auth_token": "23e740f40d9a83da528c411d10133e4f",
    "phone_number": "+14787395985"
}

# Emergency contact numbers (store in database in production)
EMERGENCY_CONTACTS = [
    {"name": "Police", "number": "+911", "type": "police"},
    {"name": "Ambulance", "number": "+912", "type": "medical"},
    {"name": "Fire Department", "number": "+913", "type": "fire"},
]

@app.on_event("startup")
async def startup_event():
    """Initialize model, database, and SMS service on startup"""
    global model
    print("🚀 Starting up Accident Detection System...")
    model = load_model()
    database.init_database()
    sms_service.init_twilio(
        TWILIO_CONFIG["account_sid"],
        TWILIO_CONFIG["auth_token"],
        TWILIO_CONFIG["phone_number"]
    )
    print("✅ System ready with SMS alerts!")
    print(f"📱 Twilio Phone: {TWILIO_CONFIG['phone_number']}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Accident Detection System",
        "version": "2.0.0",
        "model_loaded": model is not None,
        "sms_enabled": sms_service.is_initialized()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "model_status": "loaded" if model else "not_loaded",
        "database": "connected",
        "sms_service": "active" if sms_service.is_initialized() else "inactive",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/predict-image")
async def predict_image(
    file: UploadFile = File(...),
    phone_number: str = None,
    send_alert: bool = True
):
    """Process uploaded image for accident detection with SMS alert"""
    start_time = time.time()
    
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
        
        prediction = predict_single_frame(model, image)
        response_time = time.time() - start_time
        
        saved_path = None
        sms_sent = False
        
        if prediction["result"] == "Accident":
            # Save accident frame
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"accident_img_{timestamp}.jpg"
            saved_path = os.path.join(SAVED_FRAMES_DIR, filename)
            cv2.imwrite(saved_path, image)
            
            # Send SMS alerts
            if send_alert:
                location = get_location_from_ip()  # You can implement this
                sms_result = await send_accident_alert(
                    confidence=prediction["confidence"],
                    location=location,
                    image_path=saved_path,
                    phone_number=phone_number
                )
                sms_sent = sms_result.get("success", False)
        
        database.insert_detection(
            result=prediction["result"],
            confidence=prediction["confidence"],
            input_type="image",
            file_name=file.filename,
            severity="High" if prediction["confidence"] > 85 else "Medium" if prediction["confidence"] > 70 else "Low",
            response_time=response_time,
            sms_sent=sms_sent
        )
        
        return {
            "success": True,
            "result": prediction["result"],
            "confidence": round(prediction["confidence"], 2),
            "response_time": round(response_time, 3),
            "severity": "High" if prediction["confidence"] > 85 else "Medium" if prediction["confidence"] > 70 else "Low",
            "saved_frame": saved_path is not None,
            "sms_sent": sms_sent,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/predict-video")
async def predict_video(
    file: UploadFile = File(...),
    phone_number: str = None,
    send_alert: bool = True
):
    """Process uploaded video for accident detection with SMS alerts"""
    start_time = time.time()
    
    try:
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        temp_video_path = os.path.join(SAVED_FRAMES_DIR, f"temp_{file.filename}")
        contents = await file.read()
        with open(temp_video_path, 'wb') as f:
            f.write(contents)
        
        cap = cv2.VideoCapture(temp_video_path)
        
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file")
        
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, fps // 5)
        
        accident_frames = []
        accident_count = 0
        frame_count = 0
        confidences = []
        first_accident_frame = None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                prediction = predict_single_frame(model, frame)
                confidences.append(prediction["confidence"])
                
                if prediction["result"] == "Accident":
                    accident_count += 1
                    timestamp_sec = frame_count / fps
                    
                    accident_filename = f"accident_vid_{datetime.now().strftime('%Y%m%d_%H%M%S')}_frame_{frame_count}.jpg"
                    accident_path = os.path.join(SAVED_FRAMES_DIR, accident_filename)
                    cv2.imwrite(accident_path, frame)
                    
                    if first_accident_frame is None:
                        first_accident_frame = accident_path
                    
                    accident_frames.append({
                        "frame_index": frame_count,
                        "timestamp": round(timestamp_sec, 2),
                        "confidence": round(prediction["confidence"], 2),
                        "saved_frame": accident_filename
                    })
            
            frame_count += 1
        
        cap.release()
        
        try:
            os.remove(temp_video_path)
        except:
            pass
        
        total_processed = frame_count // frame_interval
        accident_ratio = accident_count / max(total_processed, 1)
        avg_confidence = sum(confidences) / max(len(confidences), 1)
        
        overall_result = "Accident" if accident_ratio > 0.15 else "No Accident"
        overall_confidence = max(confidences) if confidences else 0
        
        response_time = time.time() - start_time
        sms_sent = False
        
        # Send SMS if accident detected
        if overall_result == "Accident" and send_alert:
            location = get_location_from_ip()
            sms_result = await send_accident_alert(
                confidence=overall_confidence,
                location=location,
                image_path=first_accident_frame,
                phone_number=phone_number,
                is_video=True,
                accident_count=accident_count
            )
            sms_sent = sms_result.get("success", False)
        
        database.insert_detection(
            result=overall_result,
            confidence=overall_confidence,
            input_type="video",
            file_name=file.filename,
            accident_frames=accident_count,
            frame_timestamps=str([f["timestamp"] for f in accident_frames]),
            severity="Critical" if accident_count > 10 else "Major" if accident_count > 5 else "Minor",
            response_time=response_time,
            sms_sent=sms_sent
        )
        
        return {
            "success": True,
            "result": overall_result,
            "confidence": round(overall_confidence, 2),
            "total_frames": total_frames,
            "frames_processed": total_processed,
            "accident_frames_count": accident_count,
            "accident_frames": accident_frames,
            "average_confidence": round(avg_confidence, 2),
            "severity": "Critical" if accident_count > 10 else "Major" if accident_count > 5 else "Minor" if accident_count > 0 else "None",
            "response_time": round(response_time, 3),
            "sms_sent": sms_sent,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing error: {str(e)}")

@app.post("/send-test-sms")
async def send_test_sms(phone_number: str):
    """Send a test SMS to verify Twilio integration"""
    try:
        result = await sms_service.send_sms(
            to=phone_number,
            message="✅ TEST: Your Accident Detection System is working! You will receive alerts when accidents are detected."
        )
        return {
            "success": result["success"],
            "message": "Test SMS sent!" if result["success"] else result.get("error", "Failed to send"),
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add-emergency-contact")
async def add_emergency_contact(name: str, phone_number: str, contact_type: str = "general"):
    """Add emergency contact number"""
    EMERGENCY_CONTACTS.append({
        "name": name,
        "number": phone_number,
        "type": contact_type
    })
    return {"success": True, "contacts": EMERGENCY_CONTACTS}

@app.get("/emergency-contacts")
async def get_emergency_contacts():
    """Get all emergency contacts"""
    return {"contacts": EMERGENCY_CONTACTS}

@app.websocket("/ws/live-detection")
async def websocket_live_detection(websocket: WebSocket):
    await websocket.accept()
    global detection_active
    detection_active = True
    last_alert_time = 0
    alert_cooldown = 30  # seconds between alerts
    
    try:
        while detection_active:
            data = await websocket.receive_bytes()
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                prediction = predict_single_frame(model, frame)
                current_time = time.time()
                
                # Send alert if accident detected and cooldown passed
                if prediction["result"] == "Accident" and (current_time - last_alert_time) > alert_cooldown:
                    last_alert_time = current_time
                    
                    # Save frame
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"live_accident_{timestamp}.jpg"
                    saved_path = os.path.join(SAVED_FRAMES_DIR, filename)
                    cv2.imwrite(saved_path, frame)
                    
                    # Send SMS alerts to all emergency contacts
                    for contact in EMERGENCY_CONTACTS:
                        await sms_service.send_sms(
                            to=contact["number"],
                            message=f"🚨 ACCIDENT DETECTED! Confidence: {prediction['confidence']:.1f}% Time: {datetime.now().strftime('%H:%M:%S')}"
                        )
                    
                    database.insert_detection(
                        result=prediction["result"],
                        confidence=prediction["confidence"],
                        input_type="live",
                        severity="Detected",
                        sms_sent=True
                    )
                
                await websocket.send_json({
                    "result": prediction["result"],
                    "confidence": round(prediction["confidence"], 2),
                    "timestamp": datetime.now().isoformat()
                })
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        detection_active = False

async def send_accident_alert(confidence, location, image_path=None, phone_number=None, is_video=False, accident_count=0):
    """Send accident alert SMS"""
    message = f"🚨 ACCIDENT DETECTED!\n"
    message += f"Confidence: {confidence:.1f}%\n"
    message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if location:
        message += f"Location: {location}\n"
    
    if is_video:
        message += f"Accident frames detected: {accident_count}\n"
    
    message += f"Please check immediately and call emergency services if needed.\n"
    message += f"Alert from Accident Detection System"
    
    results = []
    
    # Send to provided phone number
    if phone_number:
        result = await sms_service.send_sms(phone_number, message)
        results.append(result)
    
    # Send to all emergency contacts
    for contact in EMERGENCY_CONTACTS:
        result = await sms_service.send_sms(contact["number"], message)
        results.append(result)
    
    success = any(r.get("success", False) for r in results)
    return {"success": success, "details": results}

def get_location_from_ip():
    """Get approximate location from IP (you can enhance this)"""
    try:
        response = requests.get('http://ip-api.com/json/', timeout=5)
        data = response.json()
        if data.get('status') == 'success':
            return f"{data.get('city')}, {data.get('country')}"
    except:
        pass
    return "Location unavailable"

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
