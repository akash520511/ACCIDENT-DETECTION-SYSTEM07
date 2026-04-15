import torch
import torch.nn as nn
import torchvision.models as models
import cv2
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class AccidentDetector:
    def __init__(self, model_path: str = "models/accident_detection_model/best"):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self._load_model(model_path)
        self.model.eval()
        
        # Motion detection parameters
        self.prev_frame = None
        self.motion_history = []
        self.accident_history = []
        
        # Vehicle detection parameters
        self.vehicle_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_fullbody.xml'
        )
        
        # Impact detection
        self.impact_threshold = 0.3
        
    def _load_model(self, model_path: str) -> nn.Module:
        """Load the trained accident detection model"""
        # Using ResNet50 as backbone
        model = models.resnet50(pretrained=True)
        num_features = model.fc.in_features
        
        # Custom classification head
        model.fc = nn.Sequential(
            nn.Linear(num_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 2)  # Binary classification
        )
        
        # Try to load trained weights
        try:
            import os
            if os.path.exists(f"{model_path}/model_weights.pth"):
                state_dict = torch.load(f"{model_path}/model_weights.pth", map_location=self.device)
                model.load_state_dict(state_dict, strict=False)
                print("Model loaded successfully from", model_path)
            else:
                print("No pre-trained weights found, using base model")
        except Exception as e:
            print(f"Error loading model: {e}")
            
        return model.to(self.device)
    
    def preprocess_frame(self, frame: np.ndarray) -> torch.Tensor:
        """Preprocess frame for model input"""
        # Resize to model input size
        frame_resized = cv2.resize(frame, (224, 224))
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        
        # Normalize
        frame_normalized = frame_rgb / 255.0
        
        # Apply ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        frame_normalized = (frame_normalized - mean) / std
        
        # Convert to tensor
        frame_tensor = torch.from_numpy(frame_normalized).float()
        frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
        
        return frame_tensor.to(self.device)
    
    def detect_motion(self, frame: np.ndarray) -> float:
        """Detect motion between frames"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return 0.0
        
        # Compute absolute difference
        frame_diff = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Dilate to fill holes
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Calculate motion area
        motion_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Minimum area threshold
                motion_area += area
        
        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_score = min(motion_area / total_pixels, 1.0)
        
        # Update previous frame
        self.prev_frame = gray
        
        # Store in history (keep last 30 frames)
        self.motion_history.append(motion_score)
        if len(self.motion_history) > 30:
            self.motion_history.pop(0)
            
        return motion_score
    
    def detect_vehicles(self, frame: np.ndarray) -> int:
        """Detect number of vehicles in frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Use HOG descriptor for vehicle detection
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Detect vehicles (using people detector as proxy)
        vehicles, _ = hog.detectMultiScale(gray, winStride=(8, 8), padding=(8, 8), scale=1.05)
        
        # Also detect using cascade
        cascades = self.vehicle_cascade.detectMultiScale(gray, 1.1, 3)
        
        # Combine detections
        all_detections = list(vehicles) + list(cascades)
        
        # Remove overlapping detections (simple NMS)
        if len(all_detections) > 0:
            all_detections = sorted(all_detections, key=lambda x: x[2] * x[3], reverse=True)
            final_detections = []
            for det in all_detections:
                x, y, w, h = det
                overlap = False
                for fd in final_detections:
                    fx, fy, fw, fh = fd
                    if (abs(x - fx) < (w + fw) / 2 and 
                        abs(y - fy) < (h + fh) / 2):
                        overlap = True
                        break
                if not overlap:
                    final_detections.append(det)
            vehicle_count = len(final_detections)
        else:
            vehicle_count = 0
            
        return min(vehicle_count, 30)  # Cap at 30 vehicles
    
    def calculate_impact_heatmap(self, frame: np.ndarray, motion_score: float) -> List[List[float]]:
        """Generate impact heatmap based on motion and intensity"""
        height, width = frame.shape[:2]
        heatmap = np.zeros((height, width))
        
        # Detect regions with high motion
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.prev_frame is not None:
            diff = cv2.absdiff(gray, self.prev_frame)
            diff = cv2.GaussianBlur(diff, (5, 5), 0)
            
            # Normalize difference
            diff_normalized = diff / 255.0
            
            # Scale by motion score
            heatmap = diff_normalized * motion_score
            
            # Apply threshold
            heatmap[heatmap < self.impact_threshold] = 0
            
        # Downsample for efficiency
        heatmap_resized = cv2.resize(heatmap, (32, 32))
        
        # Apply color map for better visualization
        heatmap_colored = cv2.applyColorMap(
            (heatmap_resized * 255).astype(np.uint8), 
            cv2.COLORMAP_JET
        )
        
        return heatmap_resized.tolist()
    
    def classify_severity(self, motion_score: float, vehicle_count: int, 
                          confidence: float, impact_force: float = None) -> Tuple[str, float]:
        """Classify accident severity based on multiple factors"""
        # Calculate severity score
        severity_score = (
            motion_score * 0.4 +
            min(vehicle_count / 10, 1.0) * 0.2 +
            (confidence / 100) * 0.3 +
            (impact_force if impact_force else motion_score) * 0.1
        )
        
        # Classify based on score
        if severity_score > 0.75:
            return "Critical", severity_score * 100
        elif severity_score > 0.5:
            return "Major", severity_score * 100
        elif severity_score > 0.25:
            return "Minor", severity_score * 100
        else:
            return "None", severity_score * 100
    
    def detect_frame(self, frame: np.ndarray) -> Dict:
        """Detect accident in a single frame"""
        start_time = datetime.now()
        
        # Preprocess frame
        input_tensor = self.preprocess_frame(frame)
        
        # Get model prediction
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = torch.softmax(outputs, dim=1)
            accident_prob = probabilities[0][1].item() * 100
        
        # Detect motion
        motion_score = self.detect_motion(frame)
        
        # Detect vehicles
        vehicle_count = self.detect_vehicles(frame)
        
        # Calculate impact force (based on motion change)
        impact_force = 0
        if len(self.motion_history) > 1:
            impact_force = max(0, motion_score - np.mean(self.motion_history[:-1]))
        
        # Determine if accident occurred
        accident_detected = (accident_prob > 45) or (motion_score > 0.35 and impact_force > 0.2)
        
        # Classify severity
        severity, severity_score = self.classify_severity(
            motion_score, vehicle_count, accident_prob, impact_force
        ) if accident_detected else ("None", 0)
        
        # Generate impact heatmap
        impact_heatmap = self.calculate_impact_heatmap(frame, motion_score) if accident_detected else []
        
        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'accident_detected': accident_detected,
            'severity': severity,
            'confidence_score': round(accident_prob, 2),
            'severity_score': round(severity_score, 2),
            'impact_heatmap': impact_heatmap,
            'vehicle_count': vehicle_count,
            'motion_score': round(motion_score, 3),
            'impact_force': round(impact_force, 3),
            'response_time': round(response_time, 3),
            'timestamp': datetime.now().isoformat()
        }
    
    def process_video(self, video_path: str, sample_rate: int = 5) -> Dict:
        """Process entire video for accident detection"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {'error': 'Could not open video file'}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        accident_frames = []
        max_confidence = 0
        final_result = None
        detection_times = []
        
        frame_count = 0
        start_time = datetime.now()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process every Nth frame for efficiency
            if frame_count % sample_rate == 0:
                result = self.detect_frame(frame)
                detection_times.append(result['response_time'])
                
                if result['accident_detected']:
                    result['frame_number'] = frame_count
                    result['timestamp_seconds'] = frame_count / fps
                    accident_frames.append(result)
                    
                    if result['confidence_score'] > max_confidence:
                        max_confidence = result['confidence_score']
                        final_result = result
            
            frame_count += 1
        
        cap.release()
        self.prev_frame = None  # Reset for next video
        self.motion_history = []
        
        # Calculate overall metrics
        total_time = (datetime.now() - start_time).total_seconds()
        avg_response_time = np.mean(detection_times) if detection_times else 0
        
        # Determine final result
        if accident_frames:
            # Get the most severe detection
            final_result = max(accident_frames, key=lambda x: x['severity_score'])
            final_result['detection_frame'] = final_result.get('frame_number', 0)
            final_result['detection_time_seconds'] = final_result.get('timestamp_seconds', 0)
            final_result['total_accident_frames'] = len(accident_frames)
            final_result['location'] = "Uploaded Video"
        else:
            final_result = {
                'accident_detected': False,
                'severity': 'None',
                'confidence_score': 0,
                'response_time': round(avg_response_time, 3),
                'timestamp': datetime.now().isoformat(),
                'location': "Uploaded Video"
            }
        
        final_result['total_frames_processed'] = frame_count // sample_rate
        final_result['processing_time'] = round(total_time, 2)
        final_result['avg_response_time'] = round(avg_response_time, 3)
        
        return final_result
    
    def reset(self):
        """Reset detector state"""
        self.prev_frame = None
        self.motion_history = []
        self.accident_history = []
