from typing import List, Dict
from fastapi import  WebSocket, WebSocketDisconnect

# WebSocket connection manager
class ConnectionManager(object):
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str) -> None:
        await websocket.accept()
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = []
        self.active_connections[meeting_id].append(websocket)

    def disconnect(self, websocket: WebSocket, meeting_id: str)-> None:
        if meeting_id in self.active_connections:
            self.active_connections[meeting_id].remove(websocket)
            if not self.active_connections[meeting_id]:
                del self.active_connections[meeting_id]

    async def send_personal_message(self, message: str, websocket: WebSocket)->None:
        """
        向指定WebSocket连接发送个人消息
        参数:
            message: 要发送的消息内容
            websocket: 目标WebSocket连接
        异常:
            ValueError: 当websocket参数无效时抛出
            WebSocketDisconnect: 当连接已断开时抛出
        """
        if not isinstance(websocket, WebSocket):
            raise ValueError("Invalid WebSocket connection")

        if not message:
            return  # 空消息不做处理
        try:
            await websocket.send_text(message)
        except WebSocketDisconnect:
            # 连接已断开，抛出异常让上层处理
            raise
        except Exception as e:
            # 记录其他异常日志
            print(f"Failed to send message: {str(e)}")
            raise

    async def broadcast(self, message: str, meeting_id: str) -> None:
        """
        向指定会议中的所有WebSocket连接广播消息
        参数:
            message: 要广播的消息内容
            meeting_id: 目标会议ID
        异常:
            ValueError: 当message或meeting_id无效时抛出
        """
        if not message or not isinstance(message, str):
            raise ValueError("Message must be a non-empty string")

        if not meeting_id or not isinstance(meeting_id, str):
            raise ValueError("Meeting ID must be a non-empty string")

        if meeting_id not in self.active_connections:
            return
        disconnected_sockets = []
        for connection in self.active_connections[meeting_id]:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                # 记录断开连接以便后续移除
                disconnected_sockets.append(connection)
                print(f"WebSocket disconnected during broadcast for meeting {meeting_id}")
            except Exception as e:
                # 记录其他发送错误
                print(f"Failed to send message to WebSocket in meeting {meeting_id}: {str(e)}")

        # 移除所有断开连接的socket
        for socket in disconnected_sockets:
            self.disconnect(socket, meeting_id)
