# 第三方库
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from loguru import logger

# 自定义模块
from db.databases import DatabaseConfig, DatabaseSessionManager
from services.auth_dependencies import require_auth
from services.message_service import MessageService
from services.service_models import User
from schemas import MessageCreate, MessageResponse, MarkReadRequest, DeleteMessageRequest, DeleteByTypeRequest

router = APIRouter(prefix="/api/messages", tags=["Messages"])

message_service = MessageService()

# 对外暴露的依赖注入函数
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖
get_async_db = db_manager.get_async_session  # 异步会话依赖

def _resp(data=None, message="success", code=0):
    return {"code": code, "message": message, "data": data}


def _raise(status_code: int, message: str, code: str):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.post("/send", summary="发送消息", response_model=dict)
async def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    try:
        msg = await message_service.send_message(
            db=db,
            sender_id=current_user.id,
            recipient_ids=payload.recipient_ids,
            title=payload.title,
            content=payload.content,
        )
        # 获取接收者ID列表
        recipient_ids = [recipient.recipient_id for recipient in msg.recipients]
        
        data = MessageResponse(
            id=msg.id,
            title=msg.title,
            content=msg.content,
            sender_id=msg.sender_id,
            recipient_ids=recipient_ids,
            created_at=msg.created_at,
        ).dict()
        return _resp(data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/list", summary="获取用户消息列表", response_model=dict)
async def list_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_read: bool | None = Query(None, description="是否已读(可选)")
):
    try:
        items, total = await message_service.list_messages(db, current_user.id, page, page_size, is_read)
        messages = []
        for m in items:
            # 获取每条消息的接收者ID列表
            recipient_ids = [recipient.recipient_id for recipient in m.recipients] if hasattr(m, 'recipients') and m.recipients else []
            
            messages.append(MessageResponse(
                id=m.id,
                title=m.title,
                content=m.content,
                sender_id=m.sender_id,
                recipient_ids=recipient_ids,
                created_at=m.created_at,
            ).dict())
        total_pages = (total + page_size - 1) // page_size
        result = {
            "messages": messages,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }
        return _resp(result)
    except Exception as e:
        logger.error(f"查询消息列表异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/mark-read", summary="标记消息为已读", response_model=dict)
async def mark_read(
    payload: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    try:
        ok = await message_service.mark_read(db, current_user.id, payload.message_id)
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "消息不存在或不属于当前用户", "not_found")
        return _resp({"updated": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记已读异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/mark-all-read", summary="全部标记消息为已读", response_model=dict)
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    try:
        count = await message_service.mark_all_read(db, current_user.id)
        return _resp({"updated_count": count})
    except Exception as e:
        logger.error(f"全部标记已读异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/delete", summary="删除单条消息", response_model=dict)
async def delete_message(
    payload: DeleteMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    try:
        ok = await message_service.delete_message(db, current_user.id, payload.message_id)
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "消息不存在或不属于当前用户", "not_found")
        return _resp({"deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除消息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/delete-by-type", summary="批量删除消息（按类型）", response_model=dict)
async def delete_by_type(
    payload: DeleteByTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    try:
        type_ = payload.type.lower()
        if type_ not in ("read", "unread", "all"):
            _raise(status.HTTP_400_BAD_REQUEST, "type 必须为 read、unread 或 all", "validation_error")
        count = await message_service.delete_by_type(db, current_user.id, type_)
        return _resp({"deleted_count": count})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"按类型批量删除异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")