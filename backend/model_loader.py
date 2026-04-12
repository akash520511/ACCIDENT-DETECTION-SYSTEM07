import os
import cv2
import numpy as np
from typing import Tuple, Dict, Any

# Import torch to load the model correctly
import torch

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), 
    "..", "AccidentDetectionProject", "models", "accident_detection_model", "best", "data.pkl"
)

_model = None

def load_model():
    """Load the trained model from disk using PyTorch"""
    global _model
    
    if _model is not None:
        return _model
    
    try:
        # Check if file exists
        if not os.path.exists(MODEL_PATH):
            print(f"Model file not found at {MODEL_PATH}")
            return None

        print(f"Loading model from {MODEL_PATH} using PyTorch...")
        
        # Use torch.load for PyTorch/Ultralytics models (.pkl or .pt)
        # map_location='cpu' ensures it runs on Render (which often has no GPU)
        _model = torch.load(MODEL_PATH, map_location='cpu')
        
        print("Model loaded successfully.")
        return _model
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

def preprocess_image(image: np.ndarray, target_size: Tuple[int, int] = (640, 640)) -> np.ndarray:
    """Preprocess image for YOLO prediction"""
    # YOLO expects RGB, OpenCV reads BGR
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Resize to standard YOLO input size
    image_resized = cv2.resize(image_rgb, target_size)
    return image_resized

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    """Run prediction on a single frame"""
    try:
        # 1. Check if it's an Ultralytics YOLO model
        if hasattr(model, 'predict'):
            # Run YOLO inference
            results = model.predict(source=image, verbose=False, conf=0.25)
            
            accident_detected = False
            max_confidence = 0.0
            
            if results and len(results) > 0:
                result = results[0]
                
                if result.boxes is not None and len(result.boxes) > 0:
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        
                        # Check class name (assuming 'accident' or class 0)
                        # You may need to verify what your model actually detects
                        class_name = model.names.get(cls_id, "").lower()
                        
                        # Assuming class 0 or 'accident' is the target
                        if "accident" in class_name or cls_id == 0:
                            accident_detected = True
                            if conf > max_confidence:
                                max_confidence = conf
            
            if accident_detected:
                return {
                    "result": "Accident",
                    "confidence": max_confidence * 100,
                    "raw_prediction": "Accident"
                }
            else:
                return {
                    "result": "No Accident",
                    "confidence": 0.0,
                    "raw_prediction": "Clear"
                }

        # 2. Fallback for generic PyTorch models (if not YOLO)
        else:
            # This part depends on your specific model architecture if it's NOT YOLO
            # For now, returning a placeholder logic
            return {
                "result": "No Accident", 
                "confidence": 0.0,
                "raw_prediction": "Unknown Model Type"
            }
            
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return {"result": "Error", "confidence": 0.0, "error": str(e)}

def get_model():
    """Get the loaded model instance"""
    global _model
    if _model is None:
        _model = load_model()
    return _model
