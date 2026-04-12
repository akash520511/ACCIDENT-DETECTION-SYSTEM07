from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import json
from loguru import logger

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./accident_detection.db")

# Handle different database URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DetectionRecord(Base):
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    accident_detected = Column(Boolean, default=False, index=True)
    severity = Column(String, default="None", index=True)
    confidence_score = Column(Float, default=0)
    severity_score = Column(Float, default=0)
    vehicle_count = Column(Integer, default=0)
    motion_score = Column(Float, default=0)
    impact_force = Column(Float, default=0)
    response_time = Column(Float, default=0)
    location = Column(String, default="Unknown")
    file_id = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    frame_number = Column(Integer, nullable=True)
    detection_time_seconds = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_timestamp_severity', 'timestamp', 'severity'),
        Index('idx_accident_detected', 'accident_detected', 'timestamp'),
    )

class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    severity = Column(String, index=True)
    confidence = Column(Float)
    location = Column(String)
    vehicle_count = Column(Integer)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)

class SystemMetric(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metric_name = Column(String, index=True)
    metric_value = Column(Float)
    unit = Column(String, default="count")

class DatabaseManager:
    def __init__(self):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    def get_session(self) -> Session:
        return SessionLocal()
    
    def save_detection_result(self, result: Dict):
        """Save detection result to database"""
        session = self.get_session()
        try:
            record = DetectionRecord(
                accident_detected=result.get('accident_detected', False),
                severity=result.get('severity', 'None'),
                confidence_score=result.get('confidence_score', 0),
                severity_score=result.get('severity_score', 0),
                vehicle_count=result.get('vehicle_count', 0),
                motion_score=result.get('motion_score', 0),
                impact_force=result.get('impact_force', 0),
                response_time=result.get('response_time', 0),
                location=result.get('location', 'Unknown'),
                file_id=result.get('file_id'),
                filename=result.get('filename'),
                frame_number=result.get('frame_number'),
                detection_time_seconds=result.get('detection_time_seconds')
            )
            session.add(record)
            session.commit()
            logger.info(f"Detection saved to database: {record.id}")
            return record.id
        except Exception as e:
            logger.error(f"Error saving detection: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def save_emergency_alert(self, alert_data: Dict):
        """Save emergency alert to database"""
        session = self.get_session()
        try:
            import uuid
            alert = EmergencyAlert(
                alert_id=str(uuid.uuid4()),
                severity=alert_data.get('severity'),
                confidence=alert_data.get('confidence_score'),
                location=alert_data.get('location', 'Unknown'),
                vehicle_count=alert_data.get('vehicle_count', 0)
            )
            session.add(alert)
            session.commit()
            logger.info(f"Emergency alert saved: {alert.alert_id}")
            return alert.alert_id
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def get_dashboard_stats(self) -> Dict:
        """Get statistics for dashboard"""
        session = self.get_session()
        try:
            total_detections = session.query(DetectionRecord).count()
            accident_detections = session.query(DetectionRecord).filter(
                DetectionRecord.accident_detected == True
            ).count()
            
            # Calculate average metrics for accidents only
            accidents = session.query(DetectionRecord).filter(
                DetectionRecord.accident_detected == True
            )
            
            avg_confidence = session.query(func.avg(DetectionRecord.confidence_score)).filter(
                DetectionRecord.accident_detected == True
            ).scalar() or 0
            
            avg_response = session.query(func.avg(DetectionRecord.response_time)).filter(
                DetectionRecord.accident_detected == True
            ).scalar() or 0
            
            # Severity breakdown
            severity_stats = {}
            for severity in ['Minor', 'Major', 'Critical']:
                count = session.query(DetectionRecord).filter(
                    DetectionRecord.severity == severity
                ).count()
                severity_stats[severity] = count
            
            # Recent detections (last 24 hours)
            recent = session.query(DetectionRecord).filter(
                DetectionRecord.timestamp > datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            # Active alerts (unacknowledged)
            active_alerts = session.query(EmergencyAlert).filter(
                EmergencyAlert.acknowledged == False
            ).count()
            
            return {
                'total_detections': total_detections,
                'accident_detections': accident_detections,
                'avg_confidence': round(avg_confidence, 2),
                'avg_response_time': round(avg_response, 3),
                'severity_breakdown': severity_stats,
                'recent_detections': recent,
                'false_alarms': total_detections - accident_detections,
                'active_alerts': active_alerts
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
        finally:
            session.close()
    
    def get_accident_history(self, limit: int = 100, offset: int = 0, severity: Optional[str] = None) -> List[Dict]:
        """Get accident history with pagination"""
        session = self.get_session()
        try:
            query = session.query(DetectionRecord).filter(
                DetectionRecord.accident_detected == True
            )
            
            if severity:
                query = query.filter(DetectionRecord.severity == severity)
            
            records = query.order_by(DetectionRecord.timestamp.desc()).offset(offset).limit(limit).all()
            
            return [
                {
                    'id': r.id,
                    'timestamp': r.timestamp.isoformat(),
                    'severity': r.severity,
                    'confidence': r.confidence_score,
                    'vehicle_count': r.vehicle_count,
                    'location': r.location,
                    'response_time': r.response_time,
                    'filename': r.filename
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
        finally:
            session.close()
    
    def get_accident_details(self, accident_id: int) -> Optional[Dict]:
        """Get detailed accident information"""
        session = self.get_session()
        try:
            record = session.query(DetectionRecord).filter(DetectionRecord.id == accident_id).first()
            if not record:
                return None
            
            return {
                'id': record.id,
                'timestamp': record.timestamp.isoformat(),
                'accident_detected': record.accident_detected,
                'severity': record.severity,
                'confidence_score': record.confidence_score,
                'severity_score': record.severity_score,
                'vehicle_count': record.vehicle_count,
                'motion_score': record.motion_score,
                'impact_force': record.impact_force,
                'response_time': record.response_time,
                'location': record.location,
                'filename': record.filename,
                'frame_number': record.frame_number,
                'detection_time_seconds': record.detection_time_seconds
            }
        except Exception as e:
            logger.error(f"Error getting accident details: {e}")
            return None
        finally:
            session.close()
    
    def get_total_detections(self) -> int:
        session = self.get_session()
        try:
            return session.query(DetectionRecord).count()
        finally:
            session.close()
    
    def get_false_alarms(self) -> int:
        session = self.get_session()
        try:
            return session.query(DetectionRecord).filter(
                DetectionRecord.accident_detected == False
            ).count()
        finally:
            session.close()
    
    def get_true_positives(self) -> int:
        session = self.get_session()
        try:
            return session.query(DetectionRecord).filter(
                DetectionRecord.accident_detected == True
            ).count()
        finally:
            session.close()
    
    def get_false_negatives(self) -> int:
        # This would require ground truth data
        return 15  # Based on your metrics
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge emergency alert"""
        session = self.get_session()
        try:
            alert = session.query(EmergencyAlert).filter(
                EmergencyAlert.alert_id == alert_id
            ).first()
            if alert:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def export_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Export accident data"""
        session = self.get_session()
        try:
            query = session.query(DetectionRecord)
            
            if start_date:
                start = datetime.fromisoformat(start_date)
                query = query.filter(DetectionRecord.timestamp >= start)
            if end_date:
                end = datetime.fromisoformat(end_date)
                query = query.filter(DetectionRecord.timestamp <= end)
            
            records = query.order_by(DetectionRecord.timestamp.desc()).all()
            
            return {
                'export_date': datetime.utcnow().isoformat(),
                'total_records': len(records),
                'data': [
                    {
                        'id': r.id,
                        'timestamp': r.timestamp.isoformat(),
                        'severity': r.severity,
                        'confidence': r.confidence_score,
                        'vehicle_count': r.vehicle_count,
                        'location': r.location,
                        'response_time': r.response_time
                    }
                    for r in records
                ]
            }
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return {}
        finally:
            session.close()
    
    def check_connection(self) -> bool:
        """Check database connection"""
        try:
            session = self.get_session()
            session.execute("SELECT 1")
            session.close()
            return True
        except:
            return False
