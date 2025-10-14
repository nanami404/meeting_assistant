# 标准库
from datetime import datetime
from typing import List, Optional, Tuple

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy import and_
from loguru import logger

# 自定义模块
from .service_models import Message


class MessageService:
    """消息业务逻辑层
    提供发送、查询、状态更新与删除操作。
    接口保持 async 以与项目其他服务一致，内部使用同步 Session。
    """

    async def send_message(
        self,
        db: Session,
        sender_id: int,
        receiver_id: int,
        title: str,
        content: str,
    ) -> Message:
        try:
            msg = Message(
                sender_id=sender_id,
                receiver_id=receiver_id,
                title=title,
                content=content,
                is_read=False,
                created_at=datetime.utcnow(),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            logger.info(f"消息发送成功 id={msg.id} sender={sender_id} -> receiver={receiver_id}")
            return msg
        except Exception as e:
            db.rollback()
            logger.error(f"消息发送失败: {e}")
            raise e

    async def list_messages(
        self,
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
    ) -> Tuple[List[Message], int]:
        try:
            query = db.query(Message).filter(Message.receiver_id == user_id)
            if is_read is not None:
                query = query.filter(Message.is_read == is_read)

            total = query.count()
            query = query.order_by(Message.created_at.desc())

            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 20
            if page_size > 100:
                page_size = 100

            items = query.offset((page - 1) * page_size).limit(page_size).all()
            return items, total
        except Exception as e:
            logger.error(f"查询消息列表失败: {e}")
            raise e

    async def mark_read(self, db: Session, user_id: int, message_id: int) -> bool:
        try:
            msg = db.query(Message).filter(and_(Message.id == message_id, Message.receiver_id == user_id)).first()
            if not msg:
                return False
            if msg.is_read:
                return True
            msg.is_read = True
            msg.updated_at = datetime.utcnow()
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"标记消息已读失败: {e}")
            raise e

    async def mark_all_read(self, db: Session, user_id: int) -> int:
        try:
            affected = db.query(Message).filter(and_(Message.receiver_id == user_id, Message.is_read == False)).update(
                {Message.is_read: True, Message.updated_at: datetime.utcnow()}, synchronize_session=False
            )
            db.commit()
            return affected or 0
        except Exception as e:
            db.rollback()
            logger.error(f"全部标记已读失败: {e}")
            raise e

    async def delete_message(self, db: Session, user_id: int, message_id: int) -> bool:
        try:
            msg = db.query(Message).filter(and_(Message.id == message_id, Message.receiver_id == user_id)).first()
            if not msg:
                return False
            db.delete(msg)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"删除消息失败: {e}")
            raise e

    async def delete_by_type(self, db: Session, user_id: int, type_: str) -> int:
        try:
            query = db.query(Message).filter(Message.receiver_id == user_id)
            if type_ == "read":
                query = query.filter(Message.is_read == True)
            elif type_ == "unread":
                query = query.filter(Message.is_read == False)
            elif type_ == "all":
                pass
            else:
                raise ValueError("type 必须为 read、unread 或 all")

            # 执行删除
            deleted = query.delete(synchronize_session=False)
            db.commit()
            return deleted or 0
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"批量删除消息失败: {e}")
            raise e