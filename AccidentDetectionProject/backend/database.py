from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()
engine = create_engine('sqlite:///accidents.db', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine)

class AccidentRecord(Base):
    __tablename__ = 'accidents'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    video_name = Column(String)
    confidence = Column(Float)
    severity = Column(String)
    response_time = Column(Float)
    impact_zones = Column(JSON)
    location = Column(String, default="Unknown")

class DetectionLog(Base):
    __tablename__ = 'detection_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)  # accident, near_miss, false_positive
    confidence = Column(Float)
    details = Column(JSON)

def init_db():
    Base.metadata.create_all(bind=engine)

def save_accident_record(video_name, detection_result):
    db = SessionLocal()
    record = AccidentRecord(
        video_name=video_name,
        confidence=detection_result['confidence_score'],
        severity=detection_result['severity'],
        response_time=detection_result['response_time'],
        impact_zones=json.dumps(detection_result['impact_zones'])
    )
    db.add(record)
    db.commit()
    db.close()
    return record.id
