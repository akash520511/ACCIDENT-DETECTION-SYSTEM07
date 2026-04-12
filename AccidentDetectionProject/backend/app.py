from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import cv2
import numpy as np
import pickle
import os
import json
import threading
import time
from datetime import datetime
from collections import deque

app = Flask(__name__, 
            template_folder='../docs',
            static_folder='../docs/static')
app.config['SECRET_KEY'] = 'visionguard-ai-secret-2024'

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ============================================
# ML MODEL INTEGRATION
# ============================================

class AccidentDetectionAI:
    def __init__(self):
        self.model = None
        self.model_type = None
        self.data = None
        self.prev_frame = None
        self.vehicle_tracker = {}
        
        # Load your existing ML model
        self.load_model()
        
        # Load your data.pkl
        self.load_data()
        
        # Performance metrics (from your PPT)
        self.metrics = {
            'accuracy': 94.2,
            'precision': 94.4,
            'recall': 94.0,
            'f1_score': 94.2,
            'response_time': 1.3
        }
        
        # Tracking variables
        self.frame_buffer = deque(maxlen=5)
        self.accident_history = []
        
    def load_model(self):
        """Load your existing ML model from models folder"""
        model_paths = [
            '../models/accident_detection_model.pkl',
            '../models/accident_detection_model.h5',
            '../models/accident_detection_model.pt',
            '../models/accident_detection_mo.pkl',
            '../models/accident_detection_mo',
            'models/accident_detection_model.pkl',
            'models/accident_detection_model.h5',
            '../data/model.pkl',
            'model.pkl'
        ]
        
        for path in model_paths:
            if os.path.exists(path):
                try:
                    if path.endswith('.pkl'):
                        with open(path, 'rb') as f:
                            self.model = pickle.load(f)
                        self.model_type = 'pickle'
                        print(f"✅ ML Model loaded: {path}")
                        return
                    elif path.endswith('.h5'):
                        import tensorflow as tf
                        self.model = tf.keras.models.load_model(path)
                        self.model_type = 'tensorflow'
                        print(f"✅ TensorFlow Model loaded: {path}")
                        return
                    elif os.path.isdir(path):
                        import tensorflow as tf
                        self.model = tf.keras.models.load_model(path)
                        self.model_type = 'tensorflow'
                        print(f"✅ TensorFlow Model directory loaded: {path}")
                        return
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
        
        print("⚠️ ML model not found. Using advanced CV detection.")
        self.model = None
    
    def load_data(self):
        """Load your existing data.pkl file"""
        data_paths = [
            '../data/data.pkl',
            'data/data.pkl',
            '../data.pkl',
            'data.pkl'
        ]
        
        for path in data_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        self.data = pickle.load(f)
                    print(f"✅ Data loaded: {path}")
                    return
                except:
                    pass
        
        print("⚠️ Data file not found")
    
    def preprocess_frame(self, frame):
        """Preprocess frame for ML model input"""
        # Resize to common size (adjust based on your model)
        resized = cv2.resize(frame, (224, 224))
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize
        normalized = rgb.astype(np.float32) / 255.0
        
        # Add batch dimension
        if len(normalized.shape) == 3:
            normalized = np.expand_dims(normalized, axis=0)
        
        return normalized
    
    def detect_vehicles_cv(self, frame):
        """Detect vehicles using computer vision"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        vehicle_count = 0
        vehicle_boxes = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if 500 < area < 15000:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Aspect ratio check for vehicles
                aspect_ratio = w / h if h > 0 else 0
                if 0.8 < aspect_ratio < 3.0:
                    vehicle_count += 1
                    vehicle_boxes.append((x, y, w, h))
        
        return vehicle_count, vehicle_boxes
    
    def detect_motion(self, frame):
        """Detect motion between frames"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return 0
        
        # Calculate frame difference
        diff = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        motion = np.sum(thresh) / 255
        self.prev_frame = gray
        
        return motion
    
    def predict_with_model(self, frame):
        """Run prediction using loaded ML model"""
        if self.model is None:
            return None
        
        try:
            processed = self.preprocess_frame(frame)
            
            if self.model_type == 'pickle':
                prediction = self.model.predict(processed)
                if isinstance(prediction, (list, np.ndarray)):
                    if len(prediction.shape) == 2 and prediction.shape[1] > 1:
                        # Binary classification output
                        confidence = float(prediction[0][1])
                    else:
                        confidence = float(prediction[0][0]) if len(prediction.shape) > 1 else float(prediction[0])
                else:
                    confidence = float(prediction)
                    
            elif self.model_type == 'tensorflow':
                prediction = self.model.predict(processed, verbose=0)
                confidence = float(prediction[0][0]) if len(prediction.shape) > 1 else float(prediction[0])
            else:
                return None
            
            # Normalize if needed
            if confidence > 1:
                confidence = confidence / 100
            
            return min(max(confidence, 0), 1)  # Clamp between 0-1
            
        except Exception as e:
            print(f"Prediction error: {e}")
            return None
    
    def calculate_severity(self, confidence, vehicle_count, motion):
        """Calculate accident severity based on multiple factors"""
        # Base severity from confidence
        severity_score = confidence * 100 if confidence else 0
        
        # Adjust based on vehicle count
        if vehicle_count >= 4:
            severity_score += 10
        elif vehicle_count >= 3:
            severity_score += 5
        
        # Adjust based on motion intensity
        if motion > 100000:
            severity_score += 15
        elif motion > 50000:
            severity_score += 8
        
        # Cap at 100
        severity_score = min(severity_score, 100)
        
        if severity_score >= 75:
            return 'Critical', severity_score
        elif severity_score >= 50:
            return 'Moderate', severity_score
        else:
            return 'Minor', severity_score
    
    def detect_accident(self, frame):
        """Main accident detection function"""
        start_time = time.time()
        
        # Get vehicle count and motion
        vehicle_count, vehicle_boxes = self.detect_vehicles_cv(frame)
        motion = self.detect_motion(frame)
        
        # Try ML model prediction first
        ml_confidence = self.predict_with_model(frame)
        
        if ml_confidence is not None:
            # Use ML model confidence
            confidence = ml_confidence * 100
            accident_detected = ml_confidence > 0.5
            
            if accident_detected:
                severity, adjusted_confidence = self.calculate_severity(
                    ml_confidence, vehicle_count, motion
                )
                confidence = adjusted_confidence
            else:
                severity = None
        else:
            # Fallback to rule-based detection
            # Accident conditions: high motion + multiple vehicles
            if vehicle_count >= 2 and motion > 30000:
                accident_detected = True
                # Calculate confidence based on rules
                confidence = min(60 + (vehicle_count * 8) + (motion / 2000), 94)
                severity, confidence = self.calculate_severity(
                    confidence / 100, vehicle_count, motion
                )
            else:
                accident_detected = False
                confidence = 0
                severity = None
        
        response_time = (time.time() - start_time) * 1000  # in milliseconds
        
        return {
            'accident_detected': accident_detected,
            'confidence': round(confidence, 1),
            'severity': severity,
            'vehicle_count': vehicle_count,
            'motion': round(motion, 2),
            'response_time': round(response_time, 2),
            'model_used': self.model is not None
        }

# ============================================
# INITIALIZE DETECTOR
# ============================================

detector = AccidentDetectionAI()

# Global variables
camera_active = True
current_frame = None
detection_history = []
alert_history = []
frame_skip = 0

# ============================================
# VIDEO PROCESSING
# ============================================

def generate_frames():
    """Generate video frames with real-time detection overlay"""
    global camera_active, current_frame, detection_history, frame_skip
    
    # Try to open camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2)
    
    # If no camera, use simulation
    if not cap.isOpened():
        print("No camera detected. Running simulation mode...")
        frame_num = 0
        while camera_active:
            # Create simulation frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.rectangle(frame, (0, 0), (640, 480), (15, 20, 35), -1)
            
            # Add grid lines for effect
            for i in range(0, 640, 50):
                cv2.line(frame, (i, 0), (i, 480), (30, 40, 60), 1)
            for i in range(0, 480, 50):
                cv2.line(frame, (0, i), (640, i), (30, 40, 60), 1)
            
            cv2.putText(frame, "VisionGuard AI - Active", (180, 100), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, "Camera Not Connected", (190, 200),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2)
            cv2.putText(frame, "Using Simulation Mode", (210, 250),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(frame, f"Accuracy: {detector.metrics['accuracy']}% | Response: {detector.metrics['response_time']}s", 
                       (140, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            
            # Simulate random vehicle count
            sim_vehicles = (frame_num // 30) % 5 + 1
            cv2.putText(frame, f"Vehicles: {sim_vehicles}", (30, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Simulate occasional accident
            if frame_num % 300 == 200:
                cv2.putText(frame, "!!! SIMULATED ACCIDENT DETECTED !!!", (120, 400),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Send simulated alert
                if frame_num % 300 == 200:
                    socketio.emit('accident_alert', {
                        'severity': 'Moderate',
                        'confidence': 78
                    })
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            frame_num += 1
            time.sleep(0.033)
        return
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    frame_count = 0
    
    while camera_active:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_frame = frame.copy()
        
        # Process every few frames for performance
        if frame_count % 2 == 0:
            # Detect accident
            result = detector.detect_accident(frame)
            
            # Store in history
            detection_history.append({
                'timestamp': datetime.now().isoformat(),
                'accident_detected': result['accident_detected'],
                'severity': result['severity'],
                'confidence': result['confidence'],
                'vehicle_count': result['vehicle_count']
            })
            
            # Keep only last 500
            if len(detection_history) > 500:
                detection_history.pop(0)
            
            # Trigger alert for accidents
            if result['accident_detected'] and result['severity'] in ['Moderate', 'Critical']:
                alert = {
                    'id': len(alert_history) + 1,
                    'timestamp': datetime.now().isoformat(),
                    'severity': result['severity'],
                    'confidence': result['confidence'],
                    'vehicle_count': result['vehicle_count']
                }
                alert_history.append(alert)
                
                print(f"\n🚨 ALERT: {result['severity']} accident detected!")
                print(f"   Confidence: {result['confidence']:.1f}%")
                print(f"   Vehicles involved: {result['vehicle_count']}")
                
                # Emit via Socket.IO
                socketio.emit('accident_alert', {
                    'severity': result['severity'],
                    'confidence': result['confidence'],
                    'vehicle_count': result['vehicle_count']
                })
            
            # Emit detection update
            socketio.emit('detection_update', {
                'vehicle_count': result['vehicle_count'],
                'accident_detected': result['accident_detected'],
                'confidence': result['confidence']
            })
        
        # Draw overlay on frame
        annotated = draw_overlay(frame, detection_history[-1] if detection_history else {})
        
        # Encode and yield
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        frame_count += 1
    
    cap.release()

def draw_overlay(frame, result):
    """Draw detection overlay on frame"""
    h, w = frame.shape[:2]
    
    # Top status bar
    cv2.rectangle(frame, (0, 0), (w, 40), (0, 0, 0), -1)
    cv2.putText(frame, "⚡ VisionGuard AI | Real-time Accident Detection", (10, 28),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # Vehicle count display
    cv2.putText(frame, f"🚗 VEHICLES: {result.get('vehicle_count', 0)}", (10, 70),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Model status
    if detector.model is not None:
        cv2.putText(frame, "🤖 ML Model: Active", (w - 180, 28),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    else:
        cv2.putText(frame, "⚠️ CV Mode", (w - 120, 28),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
    
    # Accuracy display
    cv2.putText(frame, f"📊 Accuracy: {detector.metrics['accuracy']}%", (w - 200, 70),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # Accident detection overlay
    if result.get('accident_detected'):
        severity = result.get('severity', 'Critical')
        confidence = result.get('confidence', 0)
        
        # Set colors based on severity
        if severity == 'Critical':
            color = (0, 0, 255)  # Red
            bg_color = (0, 0, 100)
        elif severity == 'Moderate':
            color = (0, 165, 255)  # Orange
            bg_color = (0, 85, 100)
        else:
            color = (0, 255, 0)  # Green
            bg_color = (0, 100, 0)
        
        # Alert banner at bottom
        cv2.rectangle(frame, (0, h - 80), (w, h), bg_color, -1)
        cv2.putText(frame, "!!! ACCIDENT DETECTED !!!", (10, h - 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, f"Severity: {severity.upper()} | Confidence: {confidence:.1f}%", (10, h - 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Red border for critical
        if severity == 'Critical':
            cv2.rectangle(frame, (3, 3), (w - 3, h - 3), color, 3)
    
    return frame

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('dashboard.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming endpoint"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_metrics')
def get_metrics():
    """Get system performance metrics"""
    accident_count = sum(1 for d in detection_history if d.get('accident_detected', False))
    
    return jsonify({
        'accuracy': detector.metrics['accuracy'],
        'precision': detector.metrics['precision'],
        'recall': detector.metrics['recall'],
        'f1_score': detector.metrics['f1_score'],
        'response_time': detector.metrics['response_time'],
        'accidents_detected': accident_count,
        'alerts_sent': len(alert_history),
        'model_loaded': detector.model is not None
    })

@app.route('/get_detections')
def get_detections():
    """Get recent detection history"""
    recent = detection_history[-50:] if len(detection_history) > 50 else detection_history
    return jsonify({'detections': recent})

@app.route('/get_alerts')
def get_alerts():
    """Get alert history"""
    return jsonify({'alerts': alert_history[-30:]})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': detector.model is not None,
        'data_loaded': detector.data is not None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/get_model_info')
def get_model_info():
    """Get model information"""
    return jsonify({
        'model_loaded': detector.model is not None,
        'model_type': detector.model_type,
        'data_loaded': detector.data is not None,
        'metrics': detector.metrics
    })

# ============================================
# SOCKET.IO EVENTS
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('✅ Client connected to VisionGuard AI')
    emit('connected', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat(),
        'model_loaded': detector.model is not None
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('❌ Client disconnected')

@socketio.on('request_metrics')
def handle_metrics_request():
    """Send metrics on request"""
    accident_count = sum(1 for d in detection_history if d.get('accident_detected', False))
    emit('metrics_update', {
        'accuracy': detector.metrics['accuracy'],
        'precision': detector.metrics['precision'],
        'recall': detector.metrics['recall'],
        'f1_score': detector.metrics['f1_score'],
        'response_time': detector.metrics['response_time'],
        'accidents_detected': accident_count
    })

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                                                                          ║
    ║              VISIONGUARD AI - ACCIDENT DETECTION SYSTEM                  ║
    ║                              PREMIUM EDITION                             ║
    ║                                                                          ║
    ║    🤖 ML Model Status: """ + ("✅ LOADED" if detector.model else "⚠️ FALLBACK MODE") + """                      ║
    ║    📊 Performance: 94.2% Accuracy | 1.3s Response Time                  ║
    ║                                                                          ║
    ║    🌐 Dashboard: http://localhost:5000                                  ║
    ║    📹 Video Feed: http://localhost:5000/video_feed                      ║
    ║                                                                          ║
    ║    Press CTRL+C to stop the server                                      ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
