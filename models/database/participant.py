# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timezone
from models.database import Meeting,User
from sqlalchemy import String, Boolean, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义基类
from db.base import Base


def _utc_now() -> datetime:
    """返回当前 UTC 时间（naive，无 tzinfo），适配 MySQL DATETIME"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ========================
# Participant 模型（需审计）
# ========================
class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    user_code: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # 注意：User.id 是 BigInteger
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    user_role: Mapped[str] = mapped_column(String(50), default="participant")
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    attendance_status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,  # MySQL DATETIME，无时区
        default=_utc_now,
        comment="创建时间（UTC）"
    )
    # 关联关系
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_code], back_populates="participations"
    )
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="participants")
