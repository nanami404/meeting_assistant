# -*- coding: utf-8 -*-
from sqlalchemy import String, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

# 自定义基类
from db.base import Base  # AuditedBase 用于需审计的表，Base 用于简单表

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
