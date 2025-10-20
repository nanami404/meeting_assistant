# 标准库
from datetime import datetime
import pytz

# 第三方库 - SQLAlchemy相关
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func
)
from sqlalchemy import (
    BigInteger,
    Text,
    Boolean
)
from sqlalchemy.orm import relationship

# 自定义库
from db.databases import Base

shanghai_tz = pytz.timezone('Asia/Shanghai')


class Message(Base):
    """消息内容表 - 存储消息基本信息"""
    __tablename__ = "messages"

    # 主键（BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 内容
    title = Column(String(100), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")

    # 关联用户
    # 注意：将 sender_id 显式声明为外键，以便 SQLAlchemy 正确建立 Message.sender 关系
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, comment="发送者ID")

    # 发送者关系 - 关联到 User 模型
    # 说明：为便于在查询中使用 joinedload(Message.sender) 以及在业务代码中访问 msg.sender.user_name
    # 定义从 Message 到 User 的多对一关系。
    sender = relationship("User", foreign_keys=[sender_id], lazy="joined")

    # 时间戳
    # 说明：与数据库 DDL 保持一致，使用 CURRENT_TIMESTAMP 语义
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系 - 与MessageRecipient的一对多关系
    recipients = relationship("MessageRecipient", back_populates="message", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_created_at', 'created_at'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return f"<Message(id={self.id}, title='{self.title}', sender_id={self.sender_id})>"


class MessageRecipient(Base):
    """消息接收者关联表 - 支持多接收者消息功能"""
    __tablename__ = "message_recipients"

    # 主键字段
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 关联字段
    message_id = Column(BigInteger, ForeignKey("messages.id"), nullable=False, comment="消息ID（外键指向 messages.id）")
    recipient_id = Column(BigInteger, nullable=False, comment="接收者ID")

    # 状态字段
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读(0未读/1已读)")
    read_at = Column(DateTime(timezone=True), nullable=True, comment="阅读时间（可选）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间（关联时间）")

    # 关联关系 - 与Message的多对一关系
    message = relationship("Message", back_populates="recipients")

    # 约束与索引 - 与数据库DDL保持一致
    __table_args__ = (
        UniqueConstraint('message_id', 'recipient_id', name='uk_message_recipient'),
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    # 索引设计 - 优化查询性能
    __table_args__ = (
        # 唯一约束：防止重复发送
        Index('uk_message_recipient', 'message_id', 'recipient_id', unique=True),
        # 索引
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return f"<MessageRecipient(id={self.id}, message_id={self.message_id}, recipient_id={self.recipient_id}, is_read={self.is_read})>"

    def mark_as_read(self) -> None:
        """标记消息为已读"""
        self.is_read = True
        self.read_at = datetime.now(shanghai_tz)

    def mark_as_unread(self) -> None:
        """标记消息为未读"""
        self.is_read = False
        self.read_at = None