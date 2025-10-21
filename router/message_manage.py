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

router = APIRouter(prefix="/api/messages", tags=["Messages"])

# Services
message_service = MessageService()

# 依赖注入（与其他路由保持一致）
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖


def _resp(data=None, message: str = "success", code: int = 0):
    return {"code": code, "message": message, "data": data}


@router.post("/send", summary="发送消息", response_model=dict)
async def send_message(payload: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
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
        recipients: List[MessageRecipientResponse] = [
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
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/list", summary="查询我的消息", response_model=dict)
async def list_my_messages(
    only_unread: bool = Query(default=False, description="是否仅查询未读消息"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """查询当前用户收到的消息"""
    try:
        messages = await message_service.list_messages(db, recipient_id=str(current_user.id), only_unread=only_unread)
        results: List[dict] = []
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
        return _resp(results)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"查询消息异常: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post("/{message_id}/mark-read", summary="标记消息为已读", response_model=dict)
async def mark_read(message_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
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
        raise HTTPException(status_code=500, detail="服务器内部错误")