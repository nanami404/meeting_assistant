from fastapi import WebSocket
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime

# 导入消息相关的模型和服务
from models.database import Message, MessageRecipient
from services.message_service import MessageService

logger = logging.getLogger(__name__)

class ConnectionManager(object):
    def __init__(self):
        # Store active connections: client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Store room connections: room_id -> List[client_id]
        self.room_connections: Dict[str, List[str]] = {}
        # Store client metadata: client_id -> metadata
        self.client_metadata: Dict[str, dict] = {}

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

    def join_room(self, client_id: str, room_id: str, metadata: Optional[dict] = None):
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

    def get_room_clients(self, room_id: str) -> List[str]:
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

    async def send_message_to_user(self, user_id: str, message_data: dict):
        """向指定用户发送消息
        
        Args:
            user_id: 用户ID
            message_data: 消息数据
        """
        try:
            await self.send_json_to_client(message_data, user_id)
            logger.info(f"成功向用户 {user_id} 发送消息")
        except Exception as e:
            logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")

    async def send_unread_messages_on_connect(self, user_id: str, db: Session):
        """用户连接时发送未读消息
        
        Args:
            user_id: 用户ID
            db: 数据库会话
        """
        try:
            # 创建消息服务实例
            message_service = MessageService()
            
            # 查询用户未读消息（is_read=False）
            unread_messages, _ = await message_service.get_user_messages(
                db, 
                int(user_id), 
                page=1, 
                page_size=5,  # 获取所有未读消息，限制最多5条
                is_read=False
            )
            
            # 按创建时间升序排列（从旧到新）
            unread_messages.sort(key=lambda x: str(x.created_at) if x.created_at else "")
            
            # 逐条推送未读消息
            for msg_recipient in unread_messages:
                # 获取完整消息内容
                message = msg_recipient.message
                
                # 构造消息推送格式
                created_at_str = str(message.created_at) if message.created_at else None
                read_at_str = str(msg_recipient.read_at) if msg_recipient.read_at else None
                
                # 构造消息推送格式
                message_payload = {
                    "type": "message",
                    "id": msg_recipient.id,
                    "message_id": message.id,
                    "title": message.title,
                    "content": message.content,
                    "sender_id": message.sender_id,
                    "is_read": msg_recipient.is_read,
                    "created_at": created_at_str,
                    "read_at": read_at_str
                }
                
                # 发送消息
                await self.send_message_to_user(user_id, message_payload)
                
            logger.info(f"用户 {user_id} 连接时推送了 {len(unread_messages)} 条未读消息")
        except Exception as e:
            logger.error(f"用户 {user_id} 连接时推送未读消息失败: {str(e)}")

    async def broadcast_new_message(self, message_data: dict, recipient_ids: List[int]):
        """向多个用户广播新消息
        
        Args:
            message_data: 消息数据
            recipient_ids: 接收者ID列表
        """
        try:
            # 构造消息推送格式
            message_payload = {
                "type": "new_message",
                "id": message_data.get("id"),
                "message_id": message_data.get("message_id"),
                "title": message_data.get("title"),
                "content": message_data.get("content"),
                "sender_id": message_data.get("sender_id"),
                "is_read": False,
                "created_at": message_data.get("created_at"),
                "read_at": None
            }
            
            # 向在线的接收者推送消息
            online_recipients = []
            for recipient_id in recipient_ids:
                recipient_id_str = str(recipient_id)
                if recipient_id_str in self.active_connections:
                    await self.send_message_to_user(recipient_id_str, message_payload)
                    online_recipients.append(recipient_id)
                    
            logger.info(f"广播新消息给 {len(online_recipients)} 个在线用户: {online_recipients}")
        except Exception as e:
            logger.error(f"广播新消息失败: {str(e)}")