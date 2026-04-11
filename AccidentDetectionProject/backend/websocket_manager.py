import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from fastapi import WebSocket, WebSocketDisconnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.room_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room: str = "dashboard"):
        await websocket.accept()
        self.active_connections.append(websocket)
        if room not in self.room_connections:
            self.room_connections[room] = []
        self.room_connections[room].append(websocket)
        logger.info(f"✅ WebSocket connected to room: {room}")
    
    def disconnect(self, websocket: WebSocket, room: str = "dashboard"):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if room in self.room_connections and websocket in self.room_connections[room]:
            self.room_connections[room].remove(websocket)
        logger.info(f"❌ WebSocket disconnected")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except:
            pass
    
    async def broadcast(self, message: dict, room: str = "dashboard"):
        if room in self.room_connections:
            for connection in self.room_connections[room]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def send_accident_alert(self, detection_result: dict, room: str = "dashboard"):
        alert = {
            "type": "accident_alert",
            "data": detection_result,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(alert, room)
    
    async def send_metrics_update(self, metrics: dict, room: str = "dashboard"):
        message = {
            "type": "metrics_update",
            "data": metrics,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message, room)
    
    def get_connection_count(self) -> int:
        return len(self.active_connections)

manager = ConnectionManager()
