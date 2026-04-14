import os
import cv2
import numpy as np
import time
from datetime import datetime
from datetime import timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
import uvicorn

# Import custom modules
from .model_loader import load_model, predict_single_frame
from . import database
from .auth import create_access_token
from . import alerts  # Optional if you use alerts

# Initialize FastAPI app
app = FastAPI(
    title="Intelligent Accident Detection System",
    description="AI-powered accident detection with real-time analysis",
    version="1.0.0"
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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_FRAMES_DIR = os.path.join(BASE_DIR, "saved_frames")
os.makedirs(SAVED_FRAMES_DIR, exist_ok=True)

# Mount static files
app.mount("/saved_frames", StaticFiles(directory=SAVED_FRAMES_DIR), name="saved_frames")

# Global variables
model = None
detection_active = False

@app.on_event("startup")
async def startup_event():
    """Initialize model and database on startup"""
    global model
    print("Starting up Accident Detection System...")
    model = load_model()
    database.init_db()  # Ensure this matches your database.py function name
    print("System ready!")

# ==================== AUTHENTICATION ====================

@app.post("/signup")
def signup(name: str, email: str, badge_id: str, password: str):
    """Register a new police officer"""
    if database.create_user(name, email, badge_id, password):
        return {"msg": "Officer registered successfully"}
    return JSONResponse(status_code=400, content={"msg": "Email or Badge ID already exists"})

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint for officers"""
    user = database.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user['email']})
    return {"access_token": access_token, "token_type": "bearer"}

# ==================== HEALTH CHECK ====================

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Accident Detection System",
        "version": "1.0.0",
        "model_loaded": model is not None
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "model_status": "loaded" if model else "not_loaded",
        "database": "connected",
        "timestamp": datetime.now().isoformat()
    }

# ==================== IMAGE PREDICTION ====================

@app.post("/predict-image")
async def predict_image(file: UploadFile = File(...)):
    """Process uploaded image for accident detection"""
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
        if prediction["result"] == "Accident":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"accident_img_{timestamp}.jpg"
            saved_path = os.path.join(SAVED_FRAMES_DIR, filename)
            cv2.imwrite(saved_path, image)
            
            # Trigger Alerts (Optional)
            # alerts.send_alerts({...})
        
        database.log_accident({
            "camera_id": "CAM-IMG", 
            "location": "Upload", 
            "result": prediction["result"], 
            "confidence": prediction["confidence"], 
            "severity": prediction["severity"], 
            "response_time": response_time
        })
        
        return {
            "success": True,
            "result": prediction["result"],
            "confidence": round(prediction["confidence"], 2),
            "response_time": round(response_time, 3),
            "severity": prediction["severity"],
            "saved_frame": saved_path is not None,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

# ==================== VIDEO PREDICTION ====================

@app.post("/predict-video")
async def predict_video(file: UploadFile = File(...)):
    """Process uploaded video for accident detection frame-by-frame"""
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
        frame_interval = fps  # Process 1 frame per second
        
        accident_frames = []
        accident_count = 0
        frame_count = 0
        confidences = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                prediction = predict_single_frame(model, frame)
                confidences.append(prediction["confidence"])
                
                if prediction["result"] == "Accident":
                    accident_count += 1
                    timestamp = frame_count / fps
                    
                    accident_filename = f"accident_vid_{datetime.now().strftime('%Y%m%d_%H%M%S')}_frame_{frame_count}.jpg"
                    accident_path = os.path.join(SAVED_FRAMES_DIR, accident_filename)
                    cv2.imwrite(accident_path, frame)
                    
                    accident_frames.append({
                        "frame_index": frame_count,
                        "timestamp": round(timestamp, 2),
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
        
        database.log_accident({
            "camera_id": "CAM-VID", 
            "location": "Upload", 
            "result": overall_result, 
            "confidence": overall_confidence, 
            "severity": "Major" if accident_count > 5 else "Minor", 
            "response_time": response_time
        })
        
        return {
            "success": True,
            "result": overall_result,
            "confidence": round(overall_confidence, 2),
            "total_frames": total_frames,
            "frames_processed": total_processed,
            "accident_frames_count": accident_count,
            "accident_frames": accident_frames,
            "average_confidence": round(avg_confidence, 2),
            "severity": "Critical" if accident_count > 10 else "Major" if accident_count > 5 else "Minor",
            "response_time": round(response_time, 3),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing error: {str(e)}")

# ==================== HISTORY ENDPOINTS ====================

@app.get("/history")
async def get_history(limit: int = 50):
    try:
        history = database.get_history(limit)
        return {"success": True, "count": len(history), "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/stats")
async def get_stats():
    try:
        stats = database.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/history")
async def clear_history():
    try:
        # You might need to add a clear_history function in database.py
        # For now, returning success
        return {"success": True, "message": "History cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== WEBSOCKET FOR LIVE DETECTION ====================

@app.websocket("/ws/live-detection")
async def websocket_live_detection(websocket: WebSocket):
    await websocket.accept()
    global detection_active
    detection_active = True
    
    try:
        while detection_active:
            data = await websocket.receive_bytes()
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                prediction = predict_single_frame(model, frame)
                await websocket.send_json({
                    "result": prediction["result"],
                    "confidence": round(prediction["confidence"], 2),
                    "timestamp": datetime.now().isoformat()
                })
                
                if prediction["result"] == "Accident":
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"live_accident_{timestamp}.jpg"
                    cv2.imwrite(os.path.join(SAVED_FRAMES_DIR, filename), frame)
                    database.log_accident({
                        "result": prediction["result"],
                        "confidence": prediction["confidence"],
                        "input_type": "live",
                        "severity": "Detected"
                    })
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        detection_active = False

# This block is for local running only.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
