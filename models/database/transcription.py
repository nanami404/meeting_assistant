# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from typing import Optional, Text
from models.database import Meeting
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义基类
from db.base import Base


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
