# 标准库
from typing import List
from loguru import logger

# 第三方库
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

# 自定义模块
from db.databases import DatabaseConfig, DatabaseSessionManager
from services.auth_dependencies import require_auth
from services.service_models import User
from services.message_service import MessageService
from schemas import MessageCreate, MessageResponse, MessageRecipientResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/messages", tags=["Messages"])

# Services
message_service = MessageService()

# 依赖注入（与其他路由保持一致）
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖

INTERNAL_SERVER_ERROR = "服务器内部错误"

def _resp(data=None, message: str = "success", code: int = 0):
    return {"code": code, "message": message, "data": data}


@router.post("/send", summary="发送消息", response_model=dict)
async def send_message(payload: MessageCreate,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(require_auth)):
    """发送消息，支持多个接收者
    - 将 sender_id 与 recipient_ids 强制转换为 int，匹配 BigInteger 字段
    """
    try:
        msg = await message_service.send_message(
            db=db,
            sender_id=str(current_user.id),
            title=payload.title,
            content=payload.content,
            recipient_ids=payload.recipient_ids,
        )
        # 转换响应模型
        recipients: list[MessageRecipientResponse] = [
            MessageRecipientResponse(
                recipient_id=str(r.recipient_id),
                is_read=r.is_read,
                read_at=r.read_at,
            ) for r in msg.recipients
        ]
        data = MessageResponse(
            id=msg.id,
            title=msg.title,
            content=msg.content,
            sender_id=str(msg.sender_id),
            created_at=msg.created_at,
            recipients=recipients,
        )
        return _resp(data.dict(), message="消息发送成功")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)


@router.get("/list", summary="查询我的消息", response_model=dict)
async def list_my_messages(
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量，最大100"),
    only_unread: bool | None = Query(default=None, description="是否仅查询未读消息"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """查询当前用户收到的消息（支持分页）"""
    try:
        # 根据 only_unread 控制是否仅查询未读消息；未提供则视为 False
        only_unread_effective = True if only_unread is True else False

        messages, total = await message_service.list_messages(
            db,
            recipient_id=str(current_user.id),
            only_unread=only_unread_effective,
            page=page,
            page_size=page_size,
        )

        results: list[dict] = []
        for m in messages:
            recipients = [
                MessageRecipientResponse(recipient_id=str(r.recipient_id), is_read=r.is_read, read_at=r.read_at)
                for r in m.recipients
                if str(r.recipient_id) == str(current_user.id)
            ]
            data = MessageResponse(
                id=m.id,
                title=m.title,
                content=m.content,
                sender_id=str(m.sender_id),
                created_at=m.created_at,
                recipients=recipients,
            )
            results.append(data.dict())

        total_pages = (total + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1

        return _resp({
            "items": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
        })
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"查询消息异常: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)


@router.post("/{message_id}/mark-read", summary="标记消息为已读", response_model=dict)
async def mark_read(message_id: str,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_auth)):
    """将当前用户的指定消息标记为已读"""
    try:
        ok = await message_service.mark_read(db, message_id=message_id, recipient_id=str(current_user.id))
        if not ok:
            raise HTTPException(status_code=404, detail="消息不存在或未关联到当前用户")
        return _resp({"message_id": message_id, "read": True})
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"标记已读异常: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)


@router.post("/mark-read/batch", summary="批量标记消息为已读", response_model=dict)
async def mark_read_batch(payload: BatchMarkReadRequest,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(require_auth)):
    """批量将当前用户的指定消息标记为已读"""
    try:
        updated = await message_service.mark_read_batch(
            db=db,
            recipient_id=str(current_user.id),
            message_ids=payload.message_ids,
        )
        return _resp({
            "updated": updated,
            "message_ids": payload.message_ids,
        }, message="批量标记已读成功")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"批量标记已读异常: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)


@router.delete("/delete", summary="删除当前用户与消息的关联(仅删除关联表)", response_model=dict)
async def delete_message_links(
    is_read: bool | None = Query(default=None, description="按已读/未读状态删除；不传表示不限"),
    message_id: str | None = Query(default=None, description="指定消息ID；与 is_read 可组合过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """安全删除当前用户与消息的关联关系
    - 仅删除关联表 `message_recipients` 中当前用户相关记录
    - 不删除 `messages` 表中的实际消息数据
    - 为避免误删，要求至少提供 `is_read` 或 `message_id` 之一
    """
    try:
        if is_read is None and message_id is None:
            raise HTTPException(status_code=400, detail="必须提供 is_read 或 message_id 之一")

        deleted = await message_service.delete_message_links(
            db=db,
            recipient_id=str(current_user.id),
            is_read=is_read,
            message_id=message_id,
        )
        return _resp({
            "deleted": deleted,
            "filters": {
                "is_read": is_read,
                "message_id": message_id,
            }
        }, message="删除关联成功")
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"删除消息关联异常: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

class BatchMarkReadRequest(BaseModel):
    message_ids: list[str]