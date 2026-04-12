import os
import pickle
import numpy as np
import cv2
from typing import Tuple, Dict, Any

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), 
    "..", "models", "accident_detection_model", "best", "data.pkl"
)

# Global model variable
_model = None

def load_model():
    """Load the trained model from disk"""
    global _model
    
    if _model is not None:
        return _model
    
    try:
        with open(MODEL_PATH, 'rb') as f:
            _model = pickle.load(f)
        print(f"Model loaded successfully from {MODEL_PATH}")
        return _model
    except FileNotFoundError:
        print(f"Model file not found at {MODEL_PATH}")
        return None
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

def preprocess_image(image: np.ndarray, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """Preprocess image for model prediction"""
    # Convert BGR to RGB if needed
    if len(image.shape) == 3 and image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Resize image
    image = cv2.resize(image, target_size)
    
    # Normalize pixel values
    image = image.astype(np.float32) / 255.0
    
    # Flatten or reshape based on model requirements
    image = image.flatten().reshape(1, -1)
    
    return image

def predict_single_frame(model, image: np.ndarray) -> Dict[str, Any]:
    """Run prediction on a single frame"""
    try:
        # Preprocess the image
        processed = preprocess_image(image)
        
        # Get prediction
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(processed)[0]
            confidence = max(probabilities)
            prediction = model.predict(processed)[0]
        else:
            prediction = model.predict(processed)[0]
            confidence = 0.85  # Default confidence if no probability available
        
        # Determine result based on model output
        if isinstance(prediction, (int, np.integer)):
            result = "Accident" if prediction == 1 else "No Accident"
        else:
            result = "Accident" if str(prediction).lower() in ['accident', '1', 'yes', 'true'] else "No Accident"
        
        return {
            "result": result,
            "confidence": float(confidence) * 100,
            "raw_prediction": int(prediction) if isinstance(prediction, (int, np.integer)) else str(prediction)
        }
        
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return {
            "result": "Error",
            "confidence": 0.0,
            "error": str(e)
        }

def get_model():
    """Get the loaded model instance"""
    global _model
    if _model is None:
        _model = load_model()
    return _model
