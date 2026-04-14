import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_PATH = os.path.join(os.path.dirname(__file__), "accident_system.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users Table (Police Officers)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        badge_id TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT DEFAULT 'officer'
    )''')

    # Accident Logs
    c.execute('''CREATE TABLE IF NOT EXISTS accident_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        camera_id TEXT,
        location TEXT,
        vehicle_number TEXT,
        owner_name TEXT,
        address TEXT,
        result TEXT,
        confidence REAL,
        severity TEXT,
        response_time REAL,
        alert_sent INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def create_user(name, email, badge_id, password):
    hashed = pwd_context.hash(password)
    try:
        conn = get_db()
        conn.execute("INSERT INTO users (name, email, badge_id, hashed_password) VALUES (?, ?, ?, ?)",
                     (name, email, badge_id.upper(), hashed))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False

def authenticate_user(email: str, password: str):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user: return None
    if not pwd_context.verify(password, user['hashed_password']): return None
    return dict(user)

def get_user_by_email(email: str):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def log_accident(data: dict):
    conn = get_db()
    conn.execute("""INSERT INTO accident_logs 
        (timestamp, camera_id, location, vehicle_number, owner_name, address, result, confidence, severity, response_time, alert_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now(), data.get('camera_id'), data.get('location'), data.get('vehicle_number'),
         data.get('owner_name'), data.get('address'), data.get('result'), data.get('confidence'),
         data.get('severity'), data.get('response_time'), data.get('alert_sent', 0)))
    conn.commit()
    conn.close()

def get_history(limit=100):
    conn = get_db()
    rows = conn.execute("SELECT * FROM accident_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM accident_logs").fetchone()[0]
    accidents = conn.execute("SELECT COUNT(*) FROM accident_logs WHERE result = 'Accident'").fetchone()[0]
    conn.close()
    return {"total_detections": total, "accidents_detected": accidents, "safe_detections": total - accidents}
