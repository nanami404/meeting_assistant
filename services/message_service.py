from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from loguru import logger
from datetime import datetime
from pytz import timezone

from .service_models import Message, MessageRecipient

shanghai_tz = timezone("Asia/Shanghai")

class MessageService(object):
    """消息业务逻辑，实现消息发送、查询与状态更新
    - 确保 BigInteger 字段（sender_id、recipient_id、message_id）在写入/查询前正确转换为 int
    - 与 SQLAlchemy 模型一致，避免类型不匹配导致的数据库错误
    """

    async def send_message(self, db: Session, sender_id: str, title: str, content: str, recipient_ids: List[str]) -> Message:
        """发送消息：创建 Message 与多个 MessageRecipient 关联记录
        Args:
            db: 数据库会话
            sender_id: 发送者用户ID（字符串或数字字符串）
            title: 消息标题
            content: 消息内容
            recipient_ids: 接收者ID列表（字符串），将转换为 int 存储
        Returns:
            Message: 创建完成的消息对象
        """
        try:
            sender_int = int(str(sender_id))
        except (TypeError, ValueError):
            raise ValueError("sender_id 必须是数字或可转换为数字的字符串")

        # 过滤并转换接收者ID
        cast_recipient_ids: list[int] = []
        for rid in recipient_ids:
            try:
                cast_recipient_ids.append(int(str(rid)))
            except (TypeError, ValueError):
                logger.warning(f"跳过无效的接收者ID: {rid}")

        if not cast_recipient_ids:
            raise ValueError("recipient_ids 为空或全部无效")

        # 创建消息
        msg = Message(title=title, content=content, sender_id=sender_int)
        db.add(msg)
        db.flush()  # 确保 msg.id 可用

        # 创建接收者关联记录
        for rid_int in cast_recipient_ids:
            mr = MessageRecipient(message_id=msg.id, recipient_id=rid_int, is_read=False)
            db.add(mr)

        db.commit()
        db.refresh(msg)
        return msg

    async def list_messages(self, db: Session, recipient_id: str, only_unread: bool = False) -> list[Message]:
        """查询用户收到的消息列表
        Args:
            db: 数据库会话
            recipient_id: 接收者用户ID（字符串），转换为 int 查询
            only_unread: 仅查询未读消息
        Returns:
            list[Message]: 消息列表（包含 recipients 关系）
        """
        try:
            rid_int = int(str(recipient_id))
        except (TypeError, ValueError):
            raise ValueError("recipient_id 必须是数字或可转换为数字的字符串")

        q = (
            select(Message)
            .join(MessageRecipient, MessageRecipient.message_id == Message.id)
            .options(joinedload(Message.recipients))
            .where(MessageRecipient.recipient_id == rid_int)
        )
        if only_unread:
            q = q.where(MessageRecipient.is_read == False)

        result = db.execute(q)
        messages = result.scalars().all()
        return messages

    async def mark_read(self, db: Session, message_id: str, recipient_id: str) -> bool:
        """标记某条消息为已读
        Args:
            db: 数据库会话
            message_id: 消息ID（字符串），转换为 int
            recipient_id: 接收者ID（字符串），转换为 int
        Returns:
            bool: 是否标记成功
        """
        try:
            mid_int = int(str(message_id))
            rid_int = int(str(recipient_id))
        except (TypeError, ValueError):
            raise ValueError("message_id 与 recipient_id 必须是数字或可转换为数字的字符串")

        mr = db.execute(
            select(MessageRecipient).where(
                (MessageRecipient.message_id == mid_int) & (MessageRecipient.recipient_id == rid_int)
            ).limit(1)
        ).scalar_one_or_none()

        if not mr:
            return False

        mr.is_read = True
        mr.read_at = datetime.now(shanghai_tz)
        db.commit()
        return True