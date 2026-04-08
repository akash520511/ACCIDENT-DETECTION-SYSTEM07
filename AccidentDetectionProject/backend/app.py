"""
Accident Detection System - Main Application
FastAPI backend with WebSocket support for real-time accident detection
"""

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import shutil
from pathlib import Path
import uuid
from datetime import datetime
from typing import Optional
import json
import logging

# Import local modules
from model_loader import get_model
from database import init_db, save_accident_record, get_all_records, get_statistics, SessionLocal, AccidentRecord
from websocket_manager import manager, websocket_handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Intelligent Accident Detection System",
    description="AI-powered real-time accident detection with severity analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "frontend"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates (if using Jinja2)
templates = Jinja2Templates(directory=str(STATIC_DIR))

# Initialize database and model on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database, model, and WebSocket on startup"""
    logger.info("🚀 Starting Accident Detection System...")
    
    # Initialize database
    init_db()
    logger.info("✅ Database initialized")
    
    # Load model
    model = get_model()
    if model.load_model():
        logger.info("✅ Model loaded successfully")
    else:
        logger.warning("⚠️ Model not loaded - using fallback detection")
    
    # Broadcast system online status
    await manager.broadcast_to_all({
        "type": "system_status",
        "status": "online",
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info("🎉 Accident Detection System Ready!")
    logger.info("📊 Dashboard available at: http://localhost:8000")
    logger.info("📡 WebSocket endpoint: ws://localhost:8000/ws/{room}")
    logger.info("📚 API docs: http://localhost:8000/api/docs")

@app.on_event("shutdown")
async def shutdown_event():
    """Broadcast shutdown message on server stop"""
    await manager.broadcast_to_all({
        "type": "system_status",
        "status": "offline",
        "timestamp": datetime.now().isoformat()
    })
    logger.info("👋 Accident Detection System Shutting Down")

# ==================== WebSocket Endpoint ====================

@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str = "dashboard"):
    """
    WebSocket endpoint for real-time communication
    Supports multiple rooms (dashboard, admin, mobile)
    """
    await websocket_handler(websocket, room)


@app.websocket("/ws")
async def websocket_default(websocket: WebSocket):
    """Default WebSocket endpoint (joins dashboard room)"""
    await websocket_handler(websocket, "dashboard")


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Serve the main dashboard page"""
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/dashboard")
async def dashboard():
    """Serve the dashboard page"""
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/index")
async def index():
    """Serve the landing page"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    model = get_model()
    return {
        "status": "healthy",
        "model_loaded": model.model is not None,
        "websocket_connections": manager.get_connection_count(),
        "active_rooms": manager.get_rooms(),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    stats = get_statistics()
    
    # Add real-time metrics
    stats.update({
        "active_connections": manager.get_connection_count(),
        "active_rooms": manager.get_rooms(),
        "system_uptime": "running",  # You can implement actual uptime tracking
        "websocket_status": "connected" if manager.get_connection_count() > 0 else "waiting"
    })
    
    return JSONResponse(content=stats)


@app.get("/api/records")
async def get_records(limit: int = 50, offset: int = 0):
    """Get accident detection records"""
    records = get_all_records(limit, offset)
    return JSONResponse(content={
        "total": len(records),
        "records": records,
        "limit": limit,
        "offset": offset
    })


@app.get("/api/record/{record_id}")
async def get_record(record_id: int):
    """Get specific accident record by ID"""
    db = SessionLocal()
    record = db.query(AccidentRecord).filter(AccidentRecord.id == record_id).first()
    db.close()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return JSONResponse(content={
        "id": record.id,
        "timestamp": record.timestamp.isoformat(),
        "video_name": record.video_name,
        "confidence": record.confidence,
        "severity": record.severity,
        "response_time": record.response_time,
        "impact_zones": record.impact_zones,
        "location": record.location
    })


@app.post("/api/detect")
async def detect_accident(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...)
):
    """
    Upload and detect accident in video
    Returns detection results and broadcasts alerts via WebSocket
    """
    
    # Validate file type
    if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload MP4, AVI, MOV, or MKV")
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(video.filename).suffix
    file_path = UPLOAD_DIR / f"{file_id}{file_extension}"
    
    # Save uploaded video
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        logger.info(f"📹 Video saved: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save video: {e}")
        raise HTTPException(status_code=500, detail="Failed to save video")
    
    # Notify clients that detection started
    await manager.broadcast({
        "type": "detection_started",
        "data": {
            "video_name": video.filename,
            "file_id": file_id,
            "timestamp": datetime.now().isoformat()
        }
    }, room="dashboard")
    
    # Run detection
    try:
        model = get_model()
        result = await model.detect_accident(str(file_path))
        
        # Add video metadata
        result['video_name'] = video.filename
        result['video_id'] = file_id
        result['timestamp'] = datetime.now().isoformat()
        result['file_size_mb'] = round(file_path.stat().st_size / (1024 * 1024), 2)
        
        # Save to database if accident detected
        record_id = None
        if result['accident_detected']:
            record_id = save_accident_record(video.filename, result)
            result['record_id'] = record_id
            logger.info(f"🚨 ACCIDENT DETECTED! Severity: {result['severity']}, Confidence: {result['confidence_score']}%")
            
            # Broadcast accident alert via WebSocket
            await manager.send_accident_alert(result, room="dashboard")
            
            # Send notification
            await manager.send_notification(
                title="🚨 Accident Detected!",
                message=f"Severity: {result['severity']} | Confidence: {result['confidence_score']}%",
                severity="error",
                room="dashboard"
            )
        else:
            logger.info(f"✅ No accident detected in {video.filename}")
            await manager.send_notification(
                title="Analysis Complete",
                message=f"No accident detected in {video.filename}",
                severity="success",
                room="dashboard"
            )
        
        # Broadcast metrics update
        stats = get_statistics()
        await manager.send_metrics_update(stats, room="dashboard")
        
        # Broadcast heatmap if impact zones exist
        if result.get('impact_zones') and len(result['impact_zones']) > 0:
            await manager.send_heatmap_update({
                "zones": result['impact_zones'],
                "frame": 0,
                "video_name": video.filename
            }, room="dashboard")
        
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        await manager.broadcast({
            "type": "detection_failed",
            "data": {
                "video_name": video.filename,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }, room="dashboard")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")
    
    # Cleanup temporary file
    background_tasks.add_task(cleanup_file, file_path)
    
    return JSONResponse(content=result)


@app.post("/api/detect/batch")
async def detect_batch(
    background_tasks: BackgroundTasks,
    videos: list[UploadFile] = File(...)
):
    """
    Batch upload and detect accidents in multiple videos
    """
    results = []
    
    for video in videos:
        # Validate file type
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            continue
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(video.filename).suffix
        file_path = UPLOAD_DIR / f"{file_id}{file_extension}"
        
        # Save video
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        # Run detection
        model = get_model()
        result = await model.detect_accident(str(file_path))
        
        # Add metadata
        result['video_name'] = video.filename
        result['video_id'] = file_id
        result['timestamp'] = datetime.now().isoformat()
        
        # Save if accident detected
        if result['accident_detected']:
            record_id = save_accident_record(video.filename, result)
            result['record_id'] = record_id
        
        results.append(result)
        
        # Cleanup
        background_tasks.add_task(cleanup_file, file_path)
    
    # Broadcast batch completion
    await manager.broadcast({
        "type": "batch_complete",
        "data": {
            "total_videos": len(videos),
            "accidents_detected": sum(1 for r in results if r['accident_detected']),
            "timestamp": datetime.now().isoformat()
        }
    }, room="dashboard")
    
    return JSONResponse(content={
        "total_processed": len(results),
        "results": results
    })


@app.get("/api/stream")
async def stream_detection():
    """
    Stream endpoint for real-time detection (alternative to WebSocket)
    """
    return {"message": "Use WebSocket at ws://localhost:8000/ws/dashboard for real-time updates"}


# ==================== Admin Endpoints ====================

@app.get("/api/admin/connections")
async def get_connections():
    """Get all active WebSocket connections (admin only)"""
    return JSONResponse(content=manager.get_connection_info())


@app.post("/api/admin/broadcast")
async def admin_broadcast(message: str, severity: str = "info"):
    """Broadcast message to all connected clients (admin only)"""
    await manager.send_notification("Admin Broadcast", message, severity, room="dashboard")
    return JSONResponse(content={"message": "Broadcast sent", "text": message})


@app.delete("/api/admin/clear")
async def clear_records():
    """Clear all accident records (admin only)"""
    db = SessionLocal()
    deleted = db.query(AccidentRecord).delete()
    db.commit()
    db.close()
    
    await manager.broadcast({
        "type": "records_cleared",
        "data": {"deleted_count": deleted},
        "timestamp": datetime.now().isoformat()
    }, room="dashboard")
    
    return JSONResponse(content={"message": f"Cleared {deleted} records"})


# ==================== Helper Functions ====================

async def cleanup_file(file_path: Path):
    """Clean up temporary files"""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Failed to cleanup {file_path}: {e}")


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ==================== Run Application ====================

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        ws_ping_interval=30,
        ws_ping_timeout=60
    )
