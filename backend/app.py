import os
import cv2
import numpy as np
import time
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import custom modules
from model_loader import load_model, predict_single_frame
import database

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
# Using absolute path helps avoid confusion on Render
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
    database.init_database()
    print("System ready!")

# ==================== HEALTH CHECK ====================

# FIX: Use api_route to allow both GET (browser) and HEAD (Render health check)
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
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
        
        # Get prediction
        prediction = predict_single_frame(model, image)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Save accident frame if detected
        saved_path = None
        if prediction["result"] == "Accident":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"accident_img_{timestamp}.jpg"
            saved_path = os.path.join(SAVED_FRAMES_DIR, filename)
            cv2.imwrite(saved_path, image)
        
        # Store in database
        database.insert_detection(
            result=prediction["result"],
            confidence=prediction["confidence"],
            input_type="image",
            file_name=file.filename,
            severity="High" if prediction["confidence"] > 85 else "Medium" if prediction["confidence"] > 70 else "Low",
            response_time=response_time
        )
        
        return {
            "success": True,
            "result": prediction["result"],
            "confidence": round(prediction["confidence"], 2),
            "response_time": round(response_time, 3),
            "severity": "High" if prediction["confidence"] > 85 else "Medium" if prediction["confidence"] > 70 else "Low",
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
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Save uploaded video temporarily
        temp_video_path = os.path.join(SAVED_FRAMES_DIR, f"temp_{file.filename}")
        contents = await file.read()
        with open(temp_video_path, 'wb') as f:
            f.write(contents)
        
        # Open video
        cap = cv2.VideoCapture(temp_video_path)
        
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file")
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # Process fewer frames to speed up analysis on server
        frame_interval = max(1, fps // 2)  # Process 2 frames per second
        
        accident_frames = []
        accident_count = 0
        frame_count = 0
        confidences = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process every Nth frame for efficiency
            if frame_count % frame_interval == 0:
                prediction = predict_single_frame(model, frame)
                confidences.append(prediction["confidence"])
                
                if prediction["result"] == "Accident":
                    accident_count += 1
                    timestamp = frame_count / fps
                    
                    # Save accident frame
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
        
        # Clean up temp file
        try:
            os.remove(temp_video_path)
        except:
            pass
        
        # Calculate overall result
        total_processed = frame_count // frame_interval
        accident_ratio = accident_count / max(total_processed, 1)
        avg_confidence = sum(confidences) / max(len(confidences), 1)
        
        overall_result = "Accident" if accident_ratio > 0.15 else "No Accident"
        overall_confidence = max(confidences) if confidences else 0
        
        response_time = time.time() - start_time
        
        # Store in database
        database.insert_detection(
            result=overall_result,
            confidence=overall_confidence,
            input_type="video",
            file_name=file.filename,
            accident_frames=accident_count,
            frame_timestamps=str([f["timestamp"] for f in accident_frames]),
            severity="Critical" if accident_count > 10 else "Major" if accident_count > 5 else "Minor",
            response_time=response_time
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
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing error: {str(e)}")

# ==================== HISTORY ENDPOINTS ====================

@app.get("/history")
async def get_history(limit: int = 50):
    """Get detection history"""
    try:
        history = database.get_all_detections(limit)
        return {
            "success": True,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get detection statistics"""
    try:
        stats = database.get_detection_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/history")
async def clear_history():
    """Clear all detection history"""
    try:
        database.clear_history()
        return {"success": True, "message": "History cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== WEBSOCKET FOR LIVE DETECTION ====================

@app.websocket("/ws/live-detection")
async def websocket_live_detection(websocket: WebSocket):
    """WebSocket endpoint for real-time detection"""
    await websocket.accept()
    global detection_active
    detection_active = True
    
    try:
        while detection_active:
            # Receive frame data
            data = await websocket.receive_bytes()
            
            # Decode image
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                # Get prediction
                prediction = predict_single_frame(model, frame)
                
                # Send result back
                await websocket.send_json({
                    "result": prediction["result"],
                    "confidence": round(prediction["confidence"], 2),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Save accident frame
                if prediction["result"] == "Accident":
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"live_accident_{timestamp}.jpg"
                    cv2.imwrite(os.path.join(SAVED_FRAMES_DIR, filename), frame)
                    
                    # Store in database
                    database.insert_detection(
                        result=prediction["result"],
                        confidence=prediction["confidence"],
                        input_type="live",
                        severity="Detected"
                    )
                    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        detection_active = False

# ==================== START SERVER ====================

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
