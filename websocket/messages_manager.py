from typing import Dict, List, Union
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)


class MessageConnectionManager:
    """简单的用户级 WebSocket 连接管理器（MVP）

    - 使用内存维护 `user_id -> [WebSocket]`
    - 支持多设备同时在线（同一用户的多个连接）
    - 提供按用户发送 JSON 或文本的能力
    - 不包含心跳、在线状态持久化等阶段2功能
    """

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: Union[str, int]) -> None:
        """注册到用户连接列表（WebSocket 连接应该在调用此方法前已被接受）"""
        uid = str(user_id)
        self.active_connections.setdefault(uid, []).append(websocket)
        logger.debug(f"WebSocket connected: user_id={uid}, total={len(self.active_connections[uid])}")

    def disconnect(self, websocket: WebSocket, user_id: Union[str, int]) -> None:
        """从用户连接列表移除指定连接（异常兜底）"""
        uid = str(user_id)
        conns = self.active_connections.get(uid)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            # 清理空列表，避免泄漏
            self.active_connections.pop(uid, None)
        logger.debug(f"WebSocket disconnected: user_id={uid}, remaining={len(conns) if conns else 0}")

    async def send_to_user(self, user_id: Union[str, int], data: Union[dict, str]) -> None:
        """向指定用户的所有连接发送消息（JSON优先）"""
        uid = str(user_id)
        conns = self.active_connections.get(uid)
        if not conns:
            return

        disconnected: List[WebSocket] = []
        for ws in list(conns):
            try:
                if isinstance(data, dict):
                    await ws.send_json(data)
                else:
                    await ws.send_text(str(data))
            except WebSocketDisconnect:
                disconnected.append(ws)
            except Exception as e:
                logger.warning(f"Send to user failed: user_id={uid}, err={e}")

        for ws in disconnected:
            self.disconnect(ws, uid)

    async def broadcast_to_users(self, user_ids: List[Union[str, int]], data: Union[dict, str]) -> None:
        """向多个用户广播消息（逐个发送）"""
        for uid in user_ids:
            await self.send_to_user(uid, data)


# 全局单例：在应用内复用，满足阶段1的内存管理需求
message_ws_manager = MessageConnectionManager()