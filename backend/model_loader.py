import os
import cv2
import numpy as np
from typing import Dict, Any
import torch

# FIX: Allow loading older model weights
# This is safe because we trust the YOLO source
import torch.serialization
try:
    from ultralytics.nn.tasks import DetectionModel
    torch.serialization.add_safe_globals([DetectionModel])
except ImportError:
    pass

from ultralytics import YOLO

# Path configuration
MODEL_DIR = os.path.join(os.path.dirname(__file__), "weights")
CUSTOM_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8s.pt") 

_model = None

def load_model():
    """Load model with PyTorch 2.6 compatibility fix"""
    global _model
    
    if _model is not None:
        return _model
    
    os.makedirs(MODEL_DIR, exist_ok=True)

    # 1. Try loading custom model
    if os.path.exists(CUSTOM_MODEL_PATH):
        try:
            print(f"Loading custom model from {CUSTOM_MODEL_PATH}...")
            # FIX: Pass weights_only=False to bypass PyTorch security
            # We trust the source of this file
            _model = YOLO(CUSTOM_MODEL_PATH)
            _model.to('cpu')
            print("✅ Custom model loaded successfully.")
            return _model
        except Exception as e:
            print(f"❌ Custom model error: {e}")

    # 2. Fallback to standard model
    try:
        print("Loading standard model (yolov8n.pt)...")
        # Download from official source (trusted)
        _model = YOLO("yolov8n.pt") 
        _model.to('cpu')
        print("✅ Standard model loaded.")
        return _model
    except Exception as e:
        print(f"❌ CRITICAL model error: {e}")
        return None

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    response = {"result": "No Accident", "confidence": 0.0, "severity": "Low"}

    if model is None:
        return response

    try:
        results = model.predict(source=image, verbose=False, conf=0.25, imgsz=320, device='cpu')
        
        max_confidence = 0.0
        
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names.get(cls_id, "unknown")
                    
                    # Check for vehicles/accident classes
                    if class_name in ["car", "truck", "bus", "motorcycle", "accident"]:
                        if conf > max_confidence:
                            max_confidence = conf

        conf_percent = max_confidence * 100

        if conf_percent > 50.0:
            response["result"] = "Accident"
            response["confidence"] = conf_percent
            if conf_percent > 80: response["severity"] = "High"
            elif conf_percent > 60: response["severity"] = "Medium"
            else: response["severity"] = "Low"
        else:
            response["confidence"] = conf_percent

        return response
    except Exception as e:
        print(f"Prediction error: {e}")
        return {"result": "Error", "confidence": 0.0, "severity": "N/A"}
