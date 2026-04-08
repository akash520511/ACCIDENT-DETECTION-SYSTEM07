import torch
import cv2
import numpy as np
from ultralytics import YOLO
import asyncio
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AccidentDetectionModel:
    """Premium Model Loader with Async Support"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.confidence_threshold = 0.8
        self.frame_threshold = 3  # Consecutive frames for accident
        self.accident_buffer = []
        
    def load_model(self):
        """Load the pre-trained model"""
        try:
            self.model = YOLO(self.model_path)
            logger.info(f"✅ Model loaded successfully from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            return False
    
    async def detect_accident(self, video_path: str) -> Dict[str, Any]:
        """Async accident detection with severity classification"""
        
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_count = 0
        accident_detected = False
        accident_time = None
        detection_time = None
        confidence_scores = []
        severity = "Low"
        
        # Track vehicle positions for impact analysis
        vehicle_positions = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            timestamp = frame_count / fps
            
            # Run detection every 15th frame for performance
            if frame_count % 15 == 0:
                results = self.model(frame, verbose=False)
                
                # Get detection data
                boxes = results[0].boxes
                if boxes is not None:
                    vehicle_count = len(boxes)
                    conf = float(boxes.conf.mean()) if len(boxes.conf) > 0 else 0
                    confidence_scores.append(conf)
                    
                    # Store positions for impact analysis
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        vehicle_positions.append({
                            'x': (x1 + x2) / 2,
                            'y': (y1 + y2) / 2,
                            'timestamp': timestamp
                        })
                    
                    # Accident detection logic
                    if conf >= self.confidence_threshold:
                        self.accident_buffer.append(conf)
                        
                        if len(self.accident_buffer) >= self.frame_threshold:
                            accident_detected = True
                            accident_time = timestamp - (len(self.accident_buffer) / fps)
                            detection_time = timestamp
                            
                            # Calculate severity based on vehicle count and confidence
                            if vehicle_count >= 5:
                                severity = "Critical"
                            elif vehicle_count >= 3:
                                severity = "Major"
                            elif vehicle_count >= 2:
                                severity = "Moderate"
                            else:
                                severity = "Minor"
                            
                            break
                    else:
                        # Reset buffer if confidence drops
                        self.accident_buffer = []
        
        cap.release()
        
        # Calculate final confidence
        avg_confidence = np.mean(confidence_scores) * 100 if confidence_scores else 0
        
        # Generate impact heatmap data
        impact_zones = self._generate_impact_zones(vehicle_positions)
        
        return {
            'accident_detected': accident_detected,
            'confidence_score': round(avg_confidence, 2),
            'severity': severity,
            'accident_timestamp': accident_time,
            'detection_timestamp': detection_time,
            'response_time': round(detection_time - accident_time, 2) if accident_time and detection_time else None,
            'impact_zones': impact_zones,
            'total_frames': frame_count,
            'duration': round(frame_count / fps, 2)
        }
    
    def _generate_impact_zones(self, positions):
        """Generate heatmap data for impact visualization"""
        if len(positions) < 2:
            return []
        
        # Calculate collision points
        impact_zones = []
        for i in range(1, len(positions)):
            prev = positions[i-1]
            curr = positions[i]
            
            # Calculate distance and velocity
            distance = ((curr['x'] - prev['x'])**2 + (curr['y'] - prev['y'])**2)**0.5
            time_diff = curr['timestamp'] - prev['timestamp']
            velocity = distance / time_diff if time_diff > 0 else 0
            
            # High velocity change indicates impact
            if velocity > 50:  # Threshold for impact
                impact_zones.append({
                    'x': curr['x'],
                    'y': curr['y'],
                    'intensity': min(velocity / 100, 1.0),  # Normalize to 0-1
                    'timestamp': curr['timestamp']
                })
        
        return impact_zones

# Singleton instance
model_instance = None

def get_model():
    global model_instance
    if model_instance is None:
        model_instance = AccidentDetectionModel("models/accident_detection_model/data.pkl")
        model_instance.load_model()
    return model_instance
