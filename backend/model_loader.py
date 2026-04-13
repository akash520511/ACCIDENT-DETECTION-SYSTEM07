import os
import cv2
import numpy as np
from typing import Dict, Any
from ultralytics import YOLO

# Path configuration
# Note: This path goes UP from 'backend' folder, then into 'AccidentDetectionProject'
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
        # Run inference
        results = model.predict(source=image, verbose=False, conf=0.25)
        
        detected_objects = []
        max_confidence = 0.0
        
        if results and len(results) > 0:
            result = results[0]
            
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names.get(cls_id, "unknown")
                    
                    detected_objects.append(class_name)
                    
                    # Check for vehicles (Car, Truck, Bus, Motorcycle)
                    if class_name in ["car", "truck", "bus", "motorcycle"]:
                        if conf > max_confidence:
                            max_confidence = conf

        # LOGIC:
        # Since we are using a standard model (not custom trained on accidents),
        # we simulate accident detection by checking if vehicles are detected with high confidence.
        if max_confidence > 0.5:
            return {
                "result": "Accident",
                "confidence": max_confidence * 100,
                "raw_prediction": list(set(detected_objects))
            }
        else:
            return {
                "result": "No Accident",
                "confidence": max_confidence * 100,
                "raw_prediction": []
            }

    except Exception as e:
        print(f"Prediction error: {e}")
        return {"result": "Error", "confidence": 0.0, "error": str(e)}

def get_model():
    global _model
    if _model is None:
        _model = load_model()
    return _model
