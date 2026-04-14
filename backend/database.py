import sqlite3
import os
from datetime import datetime
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "accident_system.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            badge_id TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Detections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT,
            location TEXT,
            result TEXT NOT NULL,
            confidence REAL,
            severity TEXT,
            response_time REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ================== AUTH FUNCTIONS ==================

def create_user(name: str, email: str, badge_id: str, password: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_password = pwd_context.hash(password)
        cursor.execute(
            "INSERT INTO users (name, email, badge_id, hashed_password) VALUES (?, ?, ?, ?)",
            (name, email, badge_id, hashed_password)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(email: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    
    if not user:
        return False
    if not pwd_context.verify(password, user['hashed_password']):
        return False
    
    return dict(user)

# ================== LOGGING FUNCTIONS ==================

def log_accident(data: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO detections 
           (camera_id, location, result, confidence, severity, response_time) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data.get('camera_id'), data.get('location'), data.get('result'), 
         data.get('confidence'), data.get('severity'), data.get('response_time'))
    )
    conn.commit()
    conn.close()

# ================== HISTORY FUNCTIONS ==================

def get_history(limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM detections ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    accidents = cursor.execute("SELECT COUNT(*) FROM detections WHERE result = 'Accident'").fetchone()[0]
    safe = total - accidents
    avg_conf = cursor.execute("SELECT AVG(confidence) FROM detections").fetchone()[0] or 0
    
    conn.close()
    return {
        "total_detections": total,
        "accidents_detected": accidents,
        "safe_detections": safe,
        "average_confidence": round(avg_conf, 2)
    }
