# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from models.database import User
from typing import List, Optional
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义基类
from db.base import AuditedBase, Base  # AuditedBase 用于需审计的表，Base 用于简单表

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

    # 关联关系
    participants: Mapped[List["Participant"]] = relationship(
        "Participant", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcriptions: Mapped[List["Transcription"]] = relationship(
        "Transcription", back_populates="meeting", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[AuditedBase.created_by], back_populates="created_meetings"
    )
    updater: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[AuditedBase.updated_by], back_populates="updated_meetings"
    )

    __table_args__ = (
        Index("idx_meetings_created_by", "created_by"),
        Index("idx_meetings_status", "status"),
        Index("idx_meetings_date_time", "date_time"),
    )




# ==========================
# Transcription 模型（简单表，无审计）
# ==========================
class Transcription(Base):
    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    speaker_id: Mapped[str] = mapped_column(String(50), nullable=False)
    speaker_name: Mapped[Optional[str]] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 使用 func.now() 存储 UTC 时间（naive），兼容 MySQL
    timestamp: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, default=100)
    is_action_item: Mapped[bool] = mapped_column(Boolean, default=False)
    is_decision: Mapped[bool] = mapped_column(Boolean, default=False)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="transcriptions")


# ========================
# PersonSign 模型（简单表，无审计）
# ========================
class PersonSign(Base):
    __tablename__ = "person_sign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    user_code: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_on_leave: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_person_sign_user_meeting", "user_code", "meeting_id"),
    )