# 标准库
from typing import Optional
import re
from datetime import datetime

# 第三方库
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from loguru import logger

# 自定义模块
from db.databases import DatabaseConfig, DatabaseSessionManager
from services.message_service import MessageService
from services.auth_dependencies import require_auth, require_admin
from models.database.user import User
from models.database.message import Message, MessageRecipient
from models.schemas import (
    MessageCreate, 
    MessageResponse, 
    MessageListRequest, 
    MessageListResponse, 
    MessageRecipientResponse,
    MarkReadRequest, 
    DeleteMessageRequest, 
    BatchOperationResponse
)

router = APIRouter(prefix="/api/messages", tags=["Messages"])

# Services
message_service = MessageService()

# 对外暴露的依赖注入函数
db_config: DatabaseConfig = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖

# ----------------------------- 辅助方法 -----------------------------

def _resp(data=None, message="success", code=0):
    return {"code": code, "message": message, "data": data}


def _raise(status_code: int, message: str, code: str):
    logger.warning(f"API错误响应: status_code={status_code}, code={code}, message={message}")
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _validate_input(text: str, max_length: int = 10000) -> bool:
    """验证输入文本的安全性"""
    if not text:
        return True
    if len(text) > max_length:
        return False
    # 检查是否包含潜在的恶意字符
    if re.search(r'[<>"\']', text):
        logger.warning(f"检测到潜在的恶意字符: {text[:50]}...")
        return False
    return True


# ============================= 消息管理接口 =============================

@router.post("/send", summary="管理员发送消息", response_model=dict)
async def send_message(
    payload: MessageCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """管理员发送消息接口
    
    管理员可通过此接口向一个或多个指定用户发送系统消息。
    
    Args:
        payload: 消息创建数据，包含标题、内容和接收者ID列表
        current_user: 当前登录用户（必须为管理员）
        db: 数据库会话
        
    Returns:
        dict: 包含创建的消息信息
        
    Raises:
        HTTPException: 当用户不是管理员或参数错误时
    """
    try:
        # 输入验证
        if payload.title and not _validate_input(payload.title, 100):
            _raise(status.HTTP_400_BAD_REQUEST, "消息标题过长或包含非法字符", "validation_error")
            
        if not _validate_input(payload.content):
            _raise(status.HTTP_400_BAD_REQUEST, "消息内容过长或包含非法字符", "validation_error")
            
        if not payload.recipient_ids:
            _raise(status.HTTP_400_BAD_REQUEST, "接收者列表不能为空", "validation_error")
            
        # 验证接收者ID列表
        for recipient_id in payload.recipient_ids:
            if not isinstance(recipient_id, int) or recipient_id <= 0:
                _raise(status.HTTP_400_BAD_REQUEST, "接收者ID必须为正整数", "validation_error")

        # 调用服务层创建消息
        message: Message = await message_service.create_message(
            db, 
            int(str(current_user.id)), 
            payload
        )
        
        # 构造响应数据
        response_data = MessageResponse(
            id=message.id,
            title=message.title,
            content=message.content,
            sender_id=message.sender_id,
            created_at=message.created_at if isinstance(message.created_at, datetime) else datetime.fromisoformat(str(message.created_at)),
            updated_at=message.updated_at if isinstance(message.updated_at, datetime) else (datetime.fromisoformat(str(message.updated_at)) if message.updated_at else None)
        )
        
        logger.info(f"管理员 {current_user.id} 成功发送消息 {message.id}")
        return _resp(response_data.model_dump(), "消息发送成功")
        
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/list", summary="获取当前用户消息列表", response_model=dict)
async def list_messages(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_read: Optional[bool] = Query(None, description="是否已读状态过滤"),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """获取当前用户消息列表接口
    
    用户可通过此接口查询自己接收到的所有消息，支持分页和已读状态过滤。
    
    Args:
        page: 页码，默认为1
        page_size: 每页数量，默认为20，最大100
        is_read: 已读状态过滤，None表示不过滤，True表示只返回已读消息，False表示只返回未读消息
        current_user: 当前登录用户
        db: 数据库会话
        
    Returns:
        dict: 包含消息列表和分页信息
        
    Raises:
        HTTPException: 当查询失败时
    """
    try:
        # 调用服务层查询消息
        items, total = await message_service.get_user_messages(
            db,
            int(str(current_user.id)),
            page,
            page_size,
            is_read
        )
        
        # 转换为响应格式
        message_list = []
        for item in items:
            read_at = item.read_at if isinstance(item.read_at, datetime) else (datetime.fromisoformat(str(item.read_at)) if item.read_at else None)
            created_at = item.created_at if isinstance(item.created_at, datetime) else datetime.fromisoformat(str(item.created_at))
            
            message_recipient = MessageRecipientResponse(
                id=item.id,
                message_id=item.message_id,
                recipient_id=item.recipient_id,
                is_read=item.is_read,
                read_at=read_at,
                created_at=created_at
            )
            message_list.append(message_recipient.model_dump())
        
        # 计算分页信息
        total_pages = (total + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        pagination = {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
        
        response_data = {
            "messages": message_list,
            "pagination": pagination
        }
        
        logger.info(f"用户 {current_user.id} 查询消息列表: 页码={page}, 页大小={page_size}, 总数={total}")
        return _resp(response_data, "查询成功")
        
    except Exception as e:
        logger.error(f"查询消息列表异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/mark-read", summary="标记消息为已读", response_model=dict)
async def mark_message_as_read(
    payload: MarkReadRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """标记单条消息为已读接口
    
    用户可通过此接口将指定消息标记为已读。
    
    Args:
        payload: 标记已读请求数据，包含消息ID
        current_user: 当前登录用户
        db: 数据库会话
        
    Returns:
        dict: 包含更新数量的信息
        
    Raises:
        HTTPException: 当参数错误或更新失败时
    """
    try:
        # 验证参数
        if payload.message_id is None:
            _raise(status.HTTP_400_BAD_REQUEST, "message_id不能为空", "validation_error")
            
        if not isinstance(payload.message_id, int) or payload.message_id <= 0:
            _raise(status.HTTP_400_BAD_REQUEST, "message_id必须为正整数", "validation_error")

        # 调用服务层标记消息为已读
        updated_count = await message_service.mark_messages_as_read(
            db,
            int(str(current_user.id)),
            message_id=payload.message_id
        )
        
        response_data = BatchOperationResponse(updated_count=updated_count, deleted_count=0)
        
        logger.info(f"用户 {current_user.id} 标记消息 {payload.message_id} 为已读")
        return _resp(response_data.model_dump(), "标记成功")
        
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记消息为已读异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/mark-all-read", summary="标记所有未读消息为已读", response_model=dict)
async def mark_all_messages_as_read(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """标记所有未读消息为已读接口
    
    用户可通过此接口将所有未读消息标记为已读。
    
    Args:
        current_user: 当前登录用户
        db: 数据库会话
        
    Returns:
        dict: 包含更新数量的信息
        
    Raises:
        HTTPException: 当更新失败时
    """
    try:
        # 调用服务层标记所有未读消息为已读
        updated_count = await message_service.mark_messages_as_read(
            db,
            int(str(current_user.id)),
            mark_all=True
        )
        
        response_data = BatchOperationResponse(updated_count=updated_count, deleted_count=0)
        
        logger.info(f"用户 {current_user.id} 标记所有未读消息为已读，更新数量: {updated_count}")
        return _resp(response_data.model_dump(), "标记成功")
        
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except Exception as e:
        logger.error(f"标记所有消息为已读异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/delete", summary="删除消息", response_model=dict)
async def delete_message(
    payload: DeleteMessageRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """删除消息接口
    
    用户可通过此接口删除指定消息或按类型删除消息。
    
    Args:
        payload: 删除消息请求数据，包含消息ID或删除类型
        current_user: 当前登录用户
        db: 数据库会话
        
    Returns:
        dict: 包含删除数量的信息
        
    Raises:
        HTTPException: 当参数错误或删除失败时
    """
    try:
        # 验证参数
        if payload.message_id is None and payload.type is None:
            _raise(status.HTTP_400_BAD_REQUEST, "message_id和type不能同时为空", "validation_error")
        
        if payload.message_id is not None:
            if not isinstance(payload.message_id, int) or payload.message_id <= 0:
                _raise(status.HTTP_400_BAD_REQUEST, "message_id必须为正整数", "validation_error")
        
        if payload.type and payload.type not in ["read", "unread", "all"]:
            _raise(status.HTTP_400_BAD_REQUEST, "type参数必须为read、unread或all", "validation_error")

        # 调用服务层删除消息
        deleted_count = await message_service.delete_messages(
            db,
            int(str(current_user.id)),
            message_id=payload.message_id,
            delete_type=payload.type
        )
        
        response_data = BatchOperationResponse(deleted_count=deleted_count, updated_count=0)
        
        action = f"删除消息 {payload.message_id}" if payload.message_id else f"按类型删除消息 {payload.type}"
        logger.info(f"用户 {current_user.id} {action}，删除数量: {deleted_count}")
        return _resp(response_data.model_dump(), "删除成功")
        
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除消息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")