# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime:
    """返回当前 UTC 时间（naive，无 tzinfo），适配 MySQL DATETIME"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """最简基类，所有模型都应继承此类（不包含任何字段）"""
    pass


class AuditedBase(Base):
    """带审计字段的基类，仅需审计的模型继承此类"""
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime,  # MySQL DATETIME，无时区
        default=_utc_now,
        comment="创建时间（UTC）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        onupdate=_utc_now,
        comment="更新时间（UTC）"
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
        comment="创建者用户ID"
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
        comment="更新者用户ID"
    )