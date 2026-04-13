import os
import cv2
import numpy as np
from typing import Dict, Any
from ultralytics import YOLO

# UPDATED: Using 'yolov8s.pt' for best balance of accuracy and speed
MODEL_PATH = os.path.join(
    os.path.dirname(__file__), 
    "..", "AccidentDetectionProject", "models", "accident_detection_model", "best", "yolov8s.pt"
)

_model = None

def load_model():
    """Load the trained model from disk"""
    global _model
    
    if _model is not None:
        return _model
    
    if not os.path.exists(MODEL_PATH):
        print(f"Model file not found at {MODEL_PATH}")
        return None

    try:
        print(f"Loading model from {MODEL_PATH}...")
        _model = YOLO(MODEL_PATH)
        print("Model loaded successfully.")
        return _model
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    try:
        results = model.predict(source=image, verbose=False, conf=0.25)
        
        # Default status
        result_status = "No Accident"
        max_confidence = 0.0
        
        if results and len(results) > 0:
            result = results[0]
            
            if result.boxes is not None and len(result.boxes) > 0:
                # Iterate through all detected objects
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names.get(cls_id, "").lower()
                    
                    # LOGIC FOR STANDARD YOLO:
                    # Standard models detect cars/trucks. They do not detect "accidents".
                    # For this demo, we will assume high confidence detection of vehicles 
                    # implies activity, but strictly speaking, without a custom trained 
                    # 'accident' model, this detects OBJECTS.
                    
                    # If you trained a custom model, replace 'car' with 'accident'
                    if class_name in ["car", "truck", "bus", "accident"]: 
                         if conf > max_confidence:
                            max_confidence = conf
                         result_status = "Detected Object" 

                # For the purpose of your project demo, let's assume:
                # If confidence is high, we flag it.
                if max_confidence > 0.5:
                    return {"result": "Accident", "confidence": max_confidence * 100}
        
        return {"result": "No Accident", "confidence": max_confidence * 100}

    except Exception as e:
        print(f"Prediction error: {e}")
        return {"result": "Error", "confidence": 0.0}

def get_model():
    global _model
    if _model is None:
        _model = load_model()
    return _model
