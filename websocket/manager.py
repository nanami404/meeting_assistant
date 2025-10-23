from fastapi import WebSocket
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager(object):
    def __init__(self):
        # Store active connections: client_id -> WebSocket
        self.active_connections: dict[str, WebSocket] = {}
        # Store room connections: room_id -> List[client_id]
        self.room_connections: dict[str, list[str]] = {}
        # Store client metadata: client_id -> metadata
        self.client_metadata: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str)->None:
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        """Disconnect WebSocket client"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from all rooms
        for room_id, clients in self.room_connections.items():
            if client_id in clients:
                clients.remove(client_id)

        # Remove metadata
        if client_id in self.client_metadata:
            del self.client_metadata[client_id]

        logger.info(f"Client {client_id} disconnected")

    async def send_personal_message(self, message: str, client_id: str):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {str(e)}")
                self.disconnect(client_id)

    async def send_json_to_client(self, data: dict, client_id: str):
        """Send JSON data to specific client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending JSON to {client_id}: {str(e)}")
                self.disconnect(client_id)

    async def broadcast_to_room(self, message: str, room_id: str) ->None:
        """Broadcast message to all clients in a room"""
        if room_id in self.room_connections:
            disconnected_clients = []
            for client_id in self.room_connections[room_id]:
                if client_id in self.active_connections:
                    try:
                        websocket = self.active_connections[client_id]
                        await websocket.send_text(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to {client_id}: {str(e)}")
                        disconnected_clients.append(client_id)
                else:
                    disconnected_clients.append(client_id)
            # Clean up disconnected clients
            for client_id in disconnected_clients:
                self.disconnect(client_id)

    async def broadcast_json_to_room(self, data: dict, room_id: str):
        """Broadcast JSON data to all clients in a room"""
        if room_id in self.room_connections:
            disconnected_clients = []
            for client_id in self.room_connections[room_id]:
                if client_id in self.active_connections:
                    try:
                        websocket = self.active_connections[client_id]
                        await websocket.send_json(data)
                    except Exception as e:
                        logger.error(f"Error broadcasting JSON to {client_id}: {str(e)}")
                        disconnected_clients.append(client_id)
                else:
                    disconnected_clients.append(client_id)

            # Clean up disconnected clients
            for client_id in disconnected_clients:
                self.disconnect(client_id)

    def join_room(self, client_id: str, room_id: str, metadata: dict = None):
        """Add client to a room"""
        if room_id not in self.room_connections:
            self.room_connections[room_id] = []

        if client_id not in self.room_connections[room_id]:
            self.room_connections[room_id].append(client_id)
        # Store client metadata
        if metadata:
            self.client_metadata[client_id] = metadata
        logger.info(f"Client {client_id} joined room {room_id}")

    def leave_room(self, client_id: str, room_id: str):
        """Remove client from a room"""
        if room_id in self.room_connections and client_id in self.room_connections[room_id]:
            self.room_connections[room_id].remove(client_id)
            # Remove empty rooms
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
        logger.info(f"Client {client_id} left room {room_id}")

    def get_room_clients(self, room_id: str) -> list[str]:
        """Get list of clients in a room"""
        return self.room_connections.get(room_id, [])

    def get_active_connections_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)

    def get_room_count(self) -> int:
        """Get total number of active rooms"""
        return len(self.room_connections)

    async def handle_speech_data(self, client_id: str, audio_data: bytes, meeting_id: str):
        """Handle incoming speech data for real-time transcription"""
        try:
            # Here you would integrate with speech recognition service
            # For now, we'll simulate transcription
            # Get client metadata
            metadata = self.client_metadata.get(client_id, {})
            speaker_name = metadata.get('speaker_name', 'Unknown Speaker')
            # Simulate transcription result
            transcription_result = {
                "type": "transcription",
                "meeting_id": meeting_id,
                "client_id": client_id,
                "speaker_name": speaker_name,
                "content": f"[实时转录示例] 来自 {speaker_name} 的语音内容",
                "timestamp": "2024-01-01T00:00:00Z",
                "confidence": "high"
            }
            # Broadcast transcription to all clients in the meeting room
            await self.broadcast_json_to_room(transcription_result, f"meeting_{meeting_id}")
        except Exception as e:
            logger.error(f"Error handling speech data from {client_id}: {str(e)}")
            # Send error message back to client
            error_message = {
                "type": "error",
                "message": f"语音处理错误: {str(e)}"
            }
            await self.send_json_to_client(error_message, client_id)
