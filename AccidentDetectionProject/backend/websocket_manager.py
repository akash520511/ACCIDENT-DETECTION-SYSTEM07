
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional
import json
import logging
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    ACCIDENT_ALERT = "accident_alert"
    HEATMAP_UPDATE = "heatmap_update"
    METRICS_UPDATE = "metrics_update"
    STATUS_UPDATE = "status_update"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    PONG = "pong"
    CONNECTION_ESTABLISHED = "connection_established"
    ERROR = "error"


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    Supports multiple rooms and broadcast messaging
    """
    
    def __init__(self):
        # Store active connections with their rooms
        self.active_connections: List[WebSocket] = []
        self.room_connections: Dict[str, List[WebSocket]] = {}
        
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Store last broadcast data for new connections
        self.last_broadcasts: Dict[str, Any] = {}
    
    async def connect(self, websocket: WebSocket, room: str = "dashboard", client_id: str = None):
        """
        Accept and store a new WebSocket connection
        
        Args:
            websocket: WebSocket connection object
            room: Room name to join (default: "dashboard")
            client_id: Optional client identifier
        """
        await websocket.accept()
        
        # Store connection
        self.active_connections.append(websocket)
        
        # Add to room
        if room not in self.room_connections:
            self.room_connections[room] = []
        self.room_connections[room].append(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "room": room,
            "client_id": client_id or str(id(websocket)),
            "ip": getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown'
        }
        
        logger.info(f"✅ WebSocket connected: {self.connection_metadata[websocket]['client_id']} to room '{room}'")
        logger.info(f"   Total connections: {len(self.active_connections)}")
        
        # Send welcome message
        await self.send_personal_message({
            "type": MessageType.CONNECTION_ESTABLISHED,
            "message": "Connected to Accident Detection System",
            "timestamp": datetime.now().isoformat(),
            "room": room,
            "client_id": self.connection_metadata[websocket]['client_id'],
            "active_connections": len(self.active_connections)
        }, websocket)
        
        # Send last known data to new connection
        await self._send_cached_data(websocket, room)
        
        # Broadcast connection update to room
        await self.broadcast({
            "type": MessageType.NOTIFICATION,
            "title": "Client Connected",
            "message": f"New client connected to {room}",
            "severity": "info",
            "total_connections": len(self.active_connections),
            "timestamp": datetime.now().isoformat()
        }, room, exclude=websocket)
        
        return self.connection_metadata[websocket]['client_id']
    
    async def _send_cached_data(self, websocket: WebSocket, room: str):
        """Send last known data to newly connected client"""
        # Send last accident alert if exists
        if 'last_accident' in self.last_broadcasts:
            await self.send_personal_message(self.last_broadcasts['last_accident'], websocket)
        
        # Send last metrics if exists
        if 'last_metrics' in self.last_broadcasts:
            await self.send_personal_message(self.last_broadcasts['last_metrics'], websocket)
    
    def disconnect(self, websocket: WebSocket, room: str = "dashboard"):
        """
        Remove a WebSocket connection
        
        Args:
            websocket: WebSocket connection to remove
            room: Room name to remove from
        """
        client_info = self.connection_metadata.get(websocket, {})
        client_id = client_info.get('client_id', 'unknown')
        
        # Remove from active connections
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from room
        if room in self.room_connections and websocket in self.room_connections[room]:
            self.room_connections[room].remove(websocket)
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(f"❌ WebSocket disconnected: {client_id} from room '{room}'")
        logger.info(f"   Remaining connections: {len(self.active_connections)}")
        
        # Broadcast disconnection update
        asyncio.create_task(self.broadcast({
            "type": MessageType.NOTIFICATION,
            "title": "Client Disconnected",
            "message": f"Client disconnected from {room}",
            "severity": "info",
            "total_connections": len(self.active_connections),
            "timestamp": datetime.now().isoformat()
        }, room))
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific connection
        
        Args:
            message: Dictionary containing message data
            websocket: Target WebSocket connection
        """
        try:
            # Ensure timestamp is present
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now().isoformat()
            
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            return False
    
    async def broadcast(self, message: dict, room: str = "dashboard", exclude: WebSocket = None):
        """
        Broadcast a message to all connections in a room
        
        Args:
            message: Dictionary containing message data
            room: Room name to broadcast to
            exclude: Optional connection to exclude from broadcast
        """
        # Ensure timestamp is present
        if 'timestamp' not in message:
            message['timestamp'] = datetime.now().isoformat()
        
        message['room'] = room
        
        if room not in self.room_connections:
            return 0
        
        disconnected = []
        sent_count = 0
        
        for connection in self.room_connections[room][:]:  # Use slice copy to avoid modification during iteration
            if connection == exclude:
                continue
            
            try:
                await connection.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn, room)
        
        return sent_count
    
    async def broadcast_to_all(self, message: dict):
        """
        Broadcast a message to all active connections regardless of room
        
        Args:
            message: Dictionary containing message data
        """
        message['timestamp'] = message.get('timestamp', datetime.now().isoformat())
        message['is_global'] = True
        
        disconnected = []
        sent_count = 0
        
        for connection in self.active_connections[:]:  # Use slice copy
            try:
                await connection.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to all: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            for room in list(self.room_connections.keys()):
                if conn in self.room_connections[room]:
                    self.disconnect(conn, room)
        
        return sent_count
    
    async def send_accident_alert(self, detection_result: dict, room: str = "dashboard"):
        """
        Send an accident alert to all connected clients
        
        Args:
            detection_result: Dictionary containing detection results
            room: Room to broadcast to
        """
        alert_message = {
            "type": MessageType.ACCIDENT_ALERT,
            "data": {
                "accident_detected": detection_result.get("accident_detected", False),
                "confidence_score": detection_result.get("confidence_score", 0),
                "severity": detection_result.get("severity", "Unknown"),
                "response_time": detection_result.get("response_time", 0),
                "video_name": detection_result.get("video_name", "Unknown"),
                "timestamp": datetime.now().isoformat(),
                "impact_zones": detection_result.get("impact_zones", []),
                "record_id": detection_result.get("record_id")
            }
        }
        
        # Cache for new connections
        self.last_broadcasts['last_accident'] = alert_message
        
        sent = await self.broadcast(alert_message, room)
        logger.info(f"🚨 ACCIDENT ALERT broadcasted to {sent} clients in room '{room}' - Severity: {detection_result.get('severity')}")
        
        # Also send a notification
        await self.send_notification(
            title="🚨 Accident Detected!",
            message=f"Severity: {detection_result.get('severity')} | Confidence: {detection_result.get('confidence_score')}%",
            severity="error",
            room=room
        )
    
    async def send_metrics_update(self, metrics: dict, room: str = "dashboard"):
        """
        Send real-time metrics to clients
        
        Args:
            metrics: Dictionary containing system metrics
            room: Room to broadcast to
        """
        metrics_message = {
            "type": MessageType.METRICS_UPDATE,
            "data": {
                "accuracy": metrics.get("accuracy", 94.2),
                "precision": metrics.get("precision", 94.0),
                "recall": metrics.get("recall", 94.0),
                "f1_score": metrics.get("f1_score", 94.2),
                "response_time_avg": metrics.get("response_time_avg", 1.3),
                "total_detections": metrics.get("total_detections", 0),
                "active_connections": len(self.active_connections),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Cache for new connections
        self.last_broadcasts['last_metrics'] = metrics_message
        
        await self.broadcast(metrics_message, room)
    
    async def send_heatmap_update(self, heatmap_data: dict, room: str = "dashboard"):
        """
        Send real-time heatmap data to clients
        
        Args:
            heatmap_data: Dictionary containing heatmap coordinates and intensities
            room: Room to broadcast to
        """
        heatmap_message = {
            "type": MessageType.HEATMAP_UPDATE,
            "data": {
                "zones": heatmap_data.get("zones", []),
                "frame": heatmap_data.get("frame", 0),
                "video_name": heatmap_data.get("video_name", "Unknown"),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.broadcast(heatmap_message, room)
    
    async def send_status_update(self, status: dict, room: str = "dashboard"):
        """
        Send system status update to all clients
        
        Args:
            status: Dictionary containing system status
            room: Room to broadcast to
        """
        status_message = {
            "type": MessageType.STATUS_UPDATE,
            "data": {
                "system_online": status.get("online", True),
                "model_loaded": status.get("model_loaded", False),
                "active_cameras": status.get("active_cameras", 0),
                "detections_today": status.get("detections_today", 0),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.broadcast(status_message, room)
    
    async def send_notification(self, title: str, message: str, severity: str = "info", room: str = "dashboard"):
        """
        Send a notification to clients
        
        Args:
            title: Notification title
            message: Notification message
            severity: Severity level (info, warning, error, success)
            room: Room to broadcast to
        """
        notification = {
            "type": MessageType.NOTIFICATION,
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.broadcast(notification, room)
    
    async def send_heartbeat(self, websocket: WebSocket):
        """Send heartbeat to keep connection alive"""
        await self.send_personal_message({
            "type": MessageType.HEARTBEAT,
            "timestamp": datetime.now().isoformat()
        }, websocket)
    
    def get_connection_count(self, room: str = None) -> int:
        """Get number of active connections"""
        if room:
            return len(self.room_connections.get(room, []))
        return len(self.active_connections)
    
    def get_rooms(self) -> List[str]:
        """Get list of active rooms"""
        return [room for room, connections in self.room_connections.items() if connections]
    
    def get_connection_info(self) -> dict:
        """Get detailed connection information"""
        return {
            "total_connections": len(self.active_connections),
            "rooms": {
                room: len(connections) 
                for room, connections in self.room_connections.items()
            },
            "connections": [
                {
                    "room": meta.get("room"),
                    "connected_at": meta.get("connected_at"),
                    "client_id": meta.get("client_id")
                }
                for ws, meta in self.connection_metadata.items()
            ]
        }


# Import asyncio for background tasks
import asyncio

# Create global instance
manager = ConnectionManager()


# ==================== WebSocket Endpoint Handler ====================

async def websocket_handler(websocket: WebSocket, room: str = "dashboard"):
    """
    Handle WebSocket connections with heartbeat and message processing
    
    Args:
        websocket: WebSocket connection
        room: Room name to join
    """
    client_id = await manager.connect(websocket, room)
    
    # Start heartbeat task
    heartbeat_task = None
    
    async def send_heartbeat():
        """Send heartbeat every 30 seconds"""
        while True:
            await asyncio.sleep(30)
            try:
                await manager.send_heartbeat(websocket)
            except:
                break
    
    try:
        heartbeat_task = asyncio.create_task(send_heartbeat())
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type", "unknown")
                
                # Handle different message types
                if message_type == "ping":
                    await websocket.send_json({
                        "type": MessageType.PONG,
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif message_type == "get_status":
                    await manager.send_status_update({
                        "online": True,
                        "model_loaded": True,
                        "active_cameras": 24,
                        "detections_today": 0
                    }, room)
                
                elif message_type == "get_metrics":
                    # Send current metrics
                    pass
                
                elif message_type == "subscribe":
                    new_room = message.get("room")
                    if new_room and new_room != room:
                        # Move connection to new room
                        manager.disconnect(websocket, room)
                        await manager.connect(websocket, new_room)
                        room = new_room
                
                else:
                    # Echo back unknown messages
                    await manager.send_personal_message({
                        "type": "echo",
                        "received": message,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": MessageType.ERROR,
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        if heartbeat_task:
            heartbeat_task.cancel()
        manager.disconnect(websocket, room)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if heartbeat_task:
            heartbeat_task.cancel()
        manager.disconnect(websocket, room)


# ==================== Helper Functions ====================

async def broadcast_accident(detection_result: dict):
    """Convenience function to broadcast accident alerts"""
    await manager.send_accident_alert(detection_result)


async def broadcast_metrics(metrics: dict):
    """Convenience function to broadcast metrics"""
    await manager.send_metrics_update(metrics)


async def broadcast_heatmap(heatmap_data: dict):
    """Convenience function to broadcast heatmap data"""
    await manager.send_heatmap_update(heatmap_data)


async def broadcast_notification(title: str, message: str, severity: str = "info"):
    """Convenience function to broadcast notifications"""
    await manager.send_notification(title, message, severity)
