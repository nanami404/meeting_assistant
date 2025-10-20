# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义基类
from db.base import AuditedBase

# 仅在类型检查时导入，避免循环导入
if TYPE_CHECKING:
    from models.database.user import User
    from models.database.participant import Participant
    from models.database.transcription import Transcription

# ======================
# Meeting 模型（需审计）
# ======================
class Meeting(AuditedBase):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(75), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    date_time: Mapped[datetime] = mapped_column(nullable=False)  # 业务时间，可带时区或 naive（建议文档说明）
    location: Mapped[Optional[str]] = mapped_column(String(100))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    agenda: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")  # scheduled, in_progress, etc.

    # ✅ 审计字段（created_at, updated_at, created_by, updated_by）已由 AuditedBase 提供

    # 关联关系 - 使用字符串引用避免循环导入
    participants: Mapped[List["Participant"]] = relationship(
        "Participant", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcriptions: Mapped[List["Transcription"]] = relationship(
        "Transcription", back_populates="meeting", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys="Meeting.created_by", back_populates="created_meetings"
    )
    updater: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys="Meeting.updated_by", back_populates="updated_meetings"
    )

    __table_args__ = (
        Index("idx_meetings_created_by", "created_by"),
        Index("idx_meetings_status", "status"),
        Index("idx_meetings_date_time", "date_time"),
    )