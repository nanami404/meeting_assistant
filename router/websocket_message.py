# -*- coding: utf-8 -*-
"""
WebSocket 消息推送路由模块
提供实时消息推送功能，支持 JWT 认证和未读消息推送
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session

from services.auth_service import AuthService
from services.message_service import MessageService
from services.user_service import UserService
from services.service_models import User, UserStatus
from db.databases import get_db
from websocket.messages_manager import message_ws_manager

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# 服务实例
auth_service = AuthService()
message_service = MessageService()
user_service = UserService()


async def authenticate_websocket_user(websocket: WebSocket, token: Optional[str], db: Session) -> Optional[User]:
    """
    WebSocket JWT 认证函数 - 支持从 Header 和 Query 两种方式获取 token
    
    Args:
        websocket: WebSocket 连接对象
        token: 来自 Query 参数的 JWT 令牌（可选）
        db: 数据库会话
        
    Returns:
        用户对象，认证失败返回 None
    """
    # 优先从 Authorization Header 获取 token
    auth_token = None
    
    # 1. 尝试从 Authorization Header 获取 Bearer token
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        auth_token = auth_header[7:]  # 移除 "Bearer " 前缀
        logger.info("从 Authorization Header 获取到 token")
    
    # 2. 检查是否通过Query参数模拟Header认证
    elif websocket.query_params.get("use_header_auth") == "true":
        authorization_param = websocket.query_params.get("authorization")
        if authorization_param and authorization_param.startswith("Bearer "):
            auth_token = authorization_param[7:]  # 移除 "Bearer " 前缀
            logger.info("从模拟 Authorization Header（Query参数）获取到 token")
    
    # 3. 如果 Header 中没有，则使用 Query 参数中的 token
    elif token:
        auth_token = token
        logger.info("从 Query 参数获取到 token")
    
    # 4. 如果所有方式都没有获取到 token
    if not auth_token:
        logger.warning("WebSocket 认证失败: 未提供 token（Header 或 Query 参数）")
        return None
    try:
        # 验证 JWT 令牌（与 auth_dependencies 保持一致）
        payload = auth_service.verify_token(auth_token, expected_type="access")
        if not payload:
            logger.warning(f"WebSocket JWT 验证失败: 无效令牌")
            return None
            
        # 从 payload 中提取用户ID
        user_id = payload.get("sub")
        if not user_id:
            logger.warning(f"WebSocket JWT 验证失败: 缺少用户ID")
            return None
            
        # 查询用户并检查状态（与 auth_dependencies 保持一致）
        try:
            user = await user_service.get_user_by_id(db, user_id)
        except Exception:
            logger.error("WebSocket 查询当前用户异常", user_id=user_id)
            return None

        if not user:
            logger.warning(f"WebSocket 用户不存在或已被删除 - 用户ID: {user_id}")
            return None
            
        if user.status != UserStatus.ACTIVE.value:
            logger.warning(f"WebSocket 用户状态异常: {user.status} - 用户ID: {user_id}")
            return None
            
        return user
        
    except Exception as e:
        logger.error(f"WebSocket JWT 认证异常: {e}")
        return None


async def push_unread_messages_to_user(user_id: int, websocket: WebSocket, db: Session):
    """
    推送用户未读消息
    
    Args:
        user_id: 用户ID
        websocket: WebSocket 连接
        db: 数据库会话
    """
    try:
        # 获取用户未读消息（只获取未读的）
        messages, total_count = await message_service.list_messages(
            db=db,
            user_id=user_id,
            is_read=False,  # 只获取未读消息
            page=1,
            page_size=50  # 限制推送数量，避免过多消息
        )
        
        if messages:
            # 构建推送消息格式
            push_data = {
                "type": "unread_messages",
                "data": {
                    "messages": messages,
                    "total_count": total_count,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # 发送未读消息
            await websocket.send_text(json.dumps(push_data, ensure_ascii=False))
            logger.info(f"已向用户 {user_id} 推送 {len(messages)} 条未读消息")
        else:
            # 发送空消息通知
            push_data = {
                "type": "unread_messages",
                "data": {
                    "messages": [],
                    "total_count": 0,
                    "timestamp": datetime.now().isoformat()
                }
            }
            await websocket.send_text(json.dumps(push_data, ensure_ascii=False))
            logger.info(f"用户 {user_id} 暂无未读消息")
            
    except Exception as e:
        logger.error(f"推送未读消息失败 - 用户ID: {user_id}, 错误: {e}")
        # 发送错误通知
        error_data = {
            "type": "error",
            "data": {
                "message": "获取未读消息失败",
                "timestamp": datetime.now().isoformat()
            }
        }
        try:
            await websocket.send_text(json.dumps(error_data, ensure_ascii=False))
        except Exception:
            pass  # 连接可能已断开


@router.websocket("/ws/messages")
async def websocket_messages_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT 认证令牌（可选，优先使用 Authorization Header）"),
    db: Session = Depends(get_db)
):
    """
    WebSocket 消息推送端点
    
    功能：
    1. JWT 令牌认证（支持 Authorization Header 和 Query 参数两种方式）
    2. 建立 WebSocket 连接
    3. 推送未读消息
    4. 维持连接以接收实时消息推送
    
    认证方式：
    - 优先从 Authorization Header 获取 Bearer token
    - 如果 Header 中没有，则从 Query 参数获取 token
    
    Args:
        websocket: WebSocket 连接对象
        token: JWT 认证令牌（Query 参数，可选）
        db: 数据库会话
    """
    # 1. JWT 认证（支持 Header 和 Query 双重获取方式）
    user = await authenticate_websocket_user(websocket, token, db)
    if not user:
        logger.warning(f"WebSocket 连接被拒绝: JWT 认证失败")
        await websocket.close(code=4001, reason="认证失败")
        return
    
    user_id = user.id
    logger.info(f"WebSocket 用户认证成功 - 用户ID: {user_id}, 用户名: {user.user_name}")
    
    # 2. 接受 WebSocket 连接
    await websocket.accept()
    logger.info(f"WebSocket 连接已建立 - 用户ID: {user_id}")
    
    # 3. 注册到连接管理器
    await message_ws_manager.connect(websocket, user_id)
    
    try:
        # 4. 推送未读消息（连接建立后立即推送一次）
        await push_unread_messages_to_user(user_id, websocket, db)
        
        # 5. 保持连接，监听客户端消息（心跳等）
        while True:
            try:
                # 接收客户端消息（可用于心跳检测或其他控制消息）
                data = await websocket.receive_text()
                
                # 解析客户端消息
                try:
                    client_message = json.loads(data)
                    message_type = client_message.get("type")
                    
                    if message_type == "ping":
                        # 心跳响应
                        pong_data = {
                            "type": "pong",
                            "data": {
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        await websocket.send_text(json.dumps(pong_data, ensure_ascii=False))
                        
                    elif message_type == "refresh_unread":
                        # 客户端请求刷新未读消息
                        await push_unread_messages_to_user(user_id, websocket, db)
                        
                    else:
                        logger.warning(f"收到未知消息类型: {message_type} - 用户ID: {user_id}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"收到无效 JSON 消息 - 用户ID: {user_id}")
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket 连接断开 - 用户ID: {user_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket 消息处理异常 - 用户ID: {user_id}, 错误: {e}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket 连接处理异常 - 用户ID: {user_id}, 错误: {e}")
    finally:
        # 6. 清理连接
        await message_ws_manager.disconnect(user_id, websocket)
        logger.info(f"WebSocket 连接已清理 - 用户ID: {user_id}")