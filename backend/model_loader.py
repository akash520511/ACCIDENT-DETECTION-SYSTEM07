import os
import cv2
import numpy as np
from typing import Dict, Any
from ultralytics import YOLO

# Correct path for deployment (weights folder inside backend)
# Assumes you put your 'best.pt' file in 'backend/weights/'
MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "best.pt")

_model = None

def load_model():
    """Load the trained model from disk"""
    global _model
    
    if _model is not None:
        return _model
    
    if not os.path.exists(MODEL_PATH):
        print(f"⚠️ Model file not found at {MODEL_PATH}")
        print("Please ensure 'best.pt' is inside the 'backend/weights/' folder.")
        return None

    try:
        print(f"Loading model from {MODEL_PATH}...")
        _model = YOLO(MODEL_PATH)
        print("✅ Model loaded successfully.")
        return _model
    except Exception as e:
        print(f"❌ Error loading model: {str(e)}")
        return None

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    """
    Run inference on a single frame.
    Returns: dict with 'result', 'confidence', 'severity'
    """
    # Default response (safest assumption)
    response = {
        "result": "No Accident",
        "confidence": 0.0,
        "severity": "Low"
    }

    if model is None:
        return response

    try:
        # Run inference
        results = model.predict(source=image, verbose=False, conf=0.35, imgsz=320)
        
        max_confidence = 0.0
        
        if results and len(results) > 0:
            result = results[0]
            
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names.get(cls_id, "unknown")
                    
                    # Check for vehicles or accident classes
                    # Adjust this logic based on what your model actually detects
                    if class_name in ["car", "truck", "bus", "motorcycle", "accident"]:
                        if conf > max_confidence:
                            max_confidence = conf

        # Convert confidence to 0-100 scale
        conf_percent = max_confidence * 100

        # Decision Logic
        # If confidence > 70%, classify as Accident
        if conf_percent > 70.0:
            response["result"] = "Accident"
            response["confidence"] = conf_percent
            
            # Calculate Severity based on confidence
            if conf_percent > 85:
                response["severity"] = "High"
            elif conf_percent > 70:
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
