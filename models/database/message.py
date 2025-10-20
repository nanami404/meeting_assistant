# -*- coding: utf-8 -*-
"""
消息管理模块 - 数据库模型定义
"""
from typing import Optional, List
from sqlalchemy import String, BigInteger, Text, Boolean, DateTime, Index, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义库
from db.base import Base


class Message(Base):
    """消息内容表 - 存储系统发送的消息内容"""
    __tablename__ = "messages"

    # 主键字段
    id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True, 
        comment="主键ID（自增）"
    )

    # 消息内容相关字段
    title: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        comment="消息标题"
    )
    
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        comment="消息内容"
    )

    # 关联字段
    sender_id: Mapped[int] = mapped_column(
        BigInteger, 
        nullable=False, 
        comment="发送者ID"
    )

    # 时间戳字段
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=func.now(), 
        comment="创建时间"
    )
    
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, 
        nullable=True, 
        onupdate=func.now(), 
        comment="更新时间"
    )

    # 关系
    recipients: Mapped[List["MessageRecipient"]] = relationship(
        "MessageRecipient", 
        back_populates="message"
    )

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, title='{self.title}', sender_id={self.sender_id})>"


class MessageRecipient(Base):
    """消息接收者关联表 - 记录消息与接收者的关联关系及阅读状态"""
    __tablename__ = "message_recipients"

    # 主键字段
    id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True, 
        comment="主键ID（自增）"
    )

    # 关联字段
    message_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("messages.id"),
        nullable=False, 
        comment="消息ID（外键指向 messages.id）"
    )
    
    recipient_id: Mapped[int] = mapped_column(
        BigInteger, 
        nullable=False, 
        comment="接收者ID"
    )

    # 状态字段
    is_read: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False, 
        comment="是否已读(0未读/1已读)"
    )
    
    read_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, 
        nullable=True, 
        comment="阅读时间（可选）"
    )

    # 时间戳字段
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=func.now(), 
        comment="创建时间（关联时间）"
    )

    # 关系
    message: Mapped["Message"] = relationship(
        "Message", 
        back_populates="recipients"
    )

    # 索引和唯一约束
    __table_args__ = (
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
        # 唯一约束：防止重复发送
        # 注意：SQLAlchemy 中的唯一约束需要在数据库层面也定义
    )

    def __repr__(self):
        return f"<MessageRecipient(id={self.id}, message_id={self.message_id}, recipient_id={self.recipient_id}, is_read={self.is_read})>"