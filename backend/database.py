import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "accident_detection.db")

def get_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            result VARCHAR(50) NOT NULL,
            confidence REAL NOT NULL,
            input_type VARCHAR(20) NOT NULL,
            file_name VARCHAR(255),
            accident_frames INTEGER DEFAULT 0,
            frame_timestamps TEXT,
            severity VARCHAR(20),
            response_time REAL,
            sms_sent BOOLEAN DEFAULT 0,
            sms_sid VARCHAR(255)
        )
    ''')
    
    # Add sms_sent column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE detection_history ADD COLUMN sms_sent BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE detection_history ADD COLUMN sms_sid VARCHAR(255)')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

def insert_detection(
    result: str,
    confidence: float,
    input_type: str,
    file_name: str = None,
    accident_frames: int = 0,
    frame_timestamps: str = None,
    severity: str = None,
    response_time: float = None,
    sms_sent: bool = False,
    sms_sid: str = None
) -> int:
    """Insert a new detection record"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO detection_history 
        (result, confidence, input_type, file_name, accident_frames, frame_timestamps, severity, response_time, sms_sent, sms_sid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (result, confidence, input_type, file_name, accident_frames, frame_timestamps, severity, response_time, sms_sent, sms_sid))
    
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return record_id

def get_all_detections(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch all detection records"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM detection_history 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_detection_stats() -> Dict[str, Any]:
    """Get detection statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as total FROM detection_history')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) as accidents FROM detection_history WHERE result = "Accident"')
    accidents = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) as sms_sent FROM detection_history WHERE sms_sent = 1')
    sms_sent = cursor.fetchone()[0]
    
    cursor.execute('SELECT AVG(confidence) as avg_conf FROM detection_history')
    avg_conf = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT AVG(response_time) as avg_resp FROM detection_history WHERE response_time IS NOT NULL')
    avg_resp = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_detections": total,
        "accidents_detected": accidents,
        "safe_detections": total - accidents,
        "average_confidence": round(avg_conf, 2),
        "average_response_time": round(avg_resp, 2),
        "sms_alerts_sent": sms_sent
    }

def clear_history() -> bool:
    """Clear all detection history"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM detection_history')
    conn.commit()
    conn.close()
    return True

# Initialize database on module load
init_database()
