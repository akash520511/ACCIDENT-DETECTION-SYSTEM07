import os
import cv2
import numpy as np
from typing import Dict, Any
from ultralytics import YOLO

# Path configuration
MODEL_DIR = os.path.join(os.path.dirname(__file__), "weights")
CUSTOM_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8s.pt")

_model = None

def load_model():
    """Load the trained model from disk, with fallback to standard model."""
    global _model
    
    if _model is not None:
        return _model
    
    # Ensure weights directory exists
    os.makedirs(MODEL_DIR, exist_ok=True)

    # 1. Try loading custom model
    if os.path.exists(CUSTOM_MODEL_PATH):
        try:
            print(f"Loading custom model from {CUSTOM_MODEL_PATH}...")
            _model = YOLO(CUSTOM_MODEL_PATH)
            print("✅ Custom model loaded successfully.")
            return _model
        except Exception as e:
            print(f"❌ Error loading custom model: {str(e)}")
            print("⚠️ Custom model file appears corrupted. Falling back to standard model...")

    # 2. Fallback to standard YOLO model (downloads automatically)
    try:
        print("Loading standard model (yolov8n.pt)...")
        # This will download automatically if not present
        _model = YOLO("yolov8n.pt") 
        print("✅ Standard model loaded. (Note: This is a generic model, not accident-specific).")
        return _model
    except Exception as e:
        print(f"❌ Critical error loading fallback model: {str(e)}")
        return None

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    """
    Run inference on a single frame.
    Returns: dict with 'result', 'confidence', 'severity'
    """
    # Default response
    response = {
        "result": "No Accident",
        "confidence": 0.0,
        "severity": "Low"
    }

    if model is None:
        return response

    try:
        # Run inference
        results = model.predict(source=image, verbose=False, conf=0.25, imgsz=320)
        
        max_confidence = 0.0
        
        if results and len(results) > 0:
            result = results[0]
            
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names.get(cls_id, "unknown")
                    
                    # For the fallback model, we look for cars/trucks/buses
                    # For a custom accident model, this might need adjustment
                    if class_name in ["car", "truck", "bus", "motorcycle", "accident"]:
                        if conf > max_confidence:
                            max_confidence = conf

        # Convert confidence to 0-100 scale
        conf_percent = max_confidence * 100

        # Decision Logic
        if conf_percent > 50.0: # Lower threshold for generic testing
            response["result"] = "Accident" # Or "Vehicle Detected" for generic model
            response["confidence"] = conf_percent
            
            if conf_percent > 80:
                response["severity"] = "High"
            elif conf_percent > 60:
                response["severity"] = "Medium"
            else:
                response["severity"] = "Low"
        else:
            response["result"] = "No Accident"
            response["confidence"] = conf_percent
            response["severity"] = "Low"

        return response

    except Exception as e:
        print(f"Prediction error: {e}")
        return {
            "result": "Error", 
            "confidence": 0.0, 
            "severity": "N/A", 
            "error": str(e)
        }

def get_model():
    global _model
    if _model is None:
        _model = load_model()
    return _model
