# 标准库
import uuid
from datetime import datetime
import pytz

# 第三方库 - SQLAlchemy相关
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    func
)
from sqlalchemy import (
    BigInteger,
    Text,
    Integer,
    Boolean
)
from sqlalchemy.orm import relationship

# 自定义库
from db.databases import Base

shanghai_tz = pytz.timezone('Asia/Shanghai')


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(75), nullable=False)
    description = Column(Text)
    date_time = Column(DateTime, nullable=False)
    location = Column(String(100))
    duration_minutes = Column(Integer, default=60)
    agenda = Column(Text)
    # scheduled, in_progress, completed, cancelled
    status = Column(String(50), default="scheduled")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), onupdate=datetime.utcnow)
    # 关联字段：创建者/更新者
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")

    # 创建者/更新者反向关系
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_meetings")
    updater = relationship("User", foreign_keys=[updated_by], back_populates="updated_meetings")


class Participant(Base):
    __tablename__ = "participants"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    user_code = Column(String(50), ForeignKey("users.id"), nullable=False)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    user_role = Column(String(50), default="participant")
    is_required = Column(Boolean, default=True)
    attendance_status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz))

    user = relationship(
        "User",
        foreign_keys=[user_code],
        back_populates="participations"  # 与 User 模型中的 participations 对应
    )
    meeting = relationship("Meeting", back_populates="participants")


class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    speaker_id = Column(String(50), nullable=False)
    speaker_name = Column(String(50))
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.utcnow(), nullable=False)
    confidence_score = Column(Integer, default=100)
    is_action_item = Column(Boolean, default=False)
    is_decision = Column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="transcriptions")


# 定义人员签到表模型
class PersonSign(Base):
    __tablename__ = "person_sign"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    user_code = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    is_signed = Column(Boolean, default=False)
    is_on_leave = Column(Boolean, default=False)