# 标准库
import uuid
from datetime import datetime
from enum import Enum

# 第三方库
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Index, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship

# 自定义库
from db.databases import Base


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class GenderType(str, Enum):
    """性别类型枚举"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(Base):
    """用户模型 - 管理系统用户信息"""
    __tablename__ = "users"

    # 主键字段
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()), comment="用户UUID主键")

    # 基本信息字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    user_name = Column(String(50), nullable=False, unique=True, comment="用户账号")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号码")
    email = Column(String(255), nullable=False, unique=True, comment="邮箱地址")
    id_number = Column(String(18), nullable=True, unique=True, comment="4A账号/工号")
    company = Column(String(200), nullable=True, comment="所属单位名称")

    # 权限和状态字段
    role = Column(String(20), nullable=False, default=UserRole.USER.value, comment="用户角色：admin-管理员，user-普通用户")
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value, comment="用户状态：active-激活，inactive-未激活，suspended-暂停")

    # 安全信息字段
    password_hash = Column(String(255), nullable=True, comment="密码哈希值（bcrypt加密）")

    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联字段
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    created_meetings = relationship("Meeting", foreign_keys="Meeting.created_by", back_populates="creator")
    updated_meetings = relationship("Meeting", foreign_keys="Meeting.updated_by", back_populates="updater")
    # 用户与会议的关联关系（多对多，通过中间表）
    meeting_associations = relationship(
        "UserMeetingAssociation",
        foreign_keys="UserMeetingAssociation.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # 自引用关系
    creator_user = relationship("User", foreign_keys=[created_by], remote_side=[id])
    updater_user = relationship("User", foreign_keys=[updated_by], remote_side=[id])

    # 添加索引
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_phone', 'phone'),
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'role'),
        Index('idx_users_status', 'status'),
        Index('idx_users_company', 'company'),
        Index('idx_users_created_at', 'created_at'),
        Index('idx_users_created_by', 'created_by'),
        Index('idx_users_updated_by', 'updated_by'),
    )


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # 关联字段：创建者/更新者
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    # 用户与会议的关联关系（多对多，通过中间表）
    user_associations = relationship("UserMeetingAssociation", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")

    # 创建者/更新者反向关系
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_meetings")
    updater = relationship("User", foreign_keys=[updated_by], back_populates="updated_meetings")


class Participant(Base):
    __tablename__ = "participants"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    role = Column(String(50), default="participant")
    is_required = Column(Boolean, default=True)
    attendance_status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="participants")


class UserMeetingAssociation(Base):
    """用户会议关联模型 - 管理用户与会议的多对多关系（简化版）
    对应数据库表：user_meeting_associations

    设计说明：
    - 使用自增BIGINT作为主键，便于高并发写入和引用
    - 保留必要字段以提升存储效率与查询性能
    - 提供唯一约束(user_id, meeting_id)防止重复关联
    """
    __tablename__ = "user_meeting_associations"

    # 主键字段（自增long类型）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="唯一ID（自增主键）")

    # 必要关联字段
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, comment="用户ID，关联users表")
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False, comment="会议ID，关联meetings表")

    # 备注信息
    notes = Column(Text, nullable=True, comment="备注信息（如请假原因、特殊说明等）")

    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 审计字段
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    user = relationship("User", foreign_keys=[user_id], back_populates="meeting_associations")
    meeting = relationship("Meeting", foreign_keys=[meeting_id], back_populates="user_associations")

    # 创建者/更新者（审计）
    created_by_user = relationship("User", foreign_keys=[created_by])
    updated_by_user = relationship("User", foreign_keys=[updated_by])

    # 索引与约束
    __table_args__ = (
        UniqueConstraint('user_id', 'meeting_id', name='uk_uma_user_meeting'),
        Index('idx_uma_user_id', 'user_id'),
        Index('idx_uma_meeting_id', 'meeting_id'),
        Index('idx_uma_created_at', 'created_at'),
        Index('idx_uma_created_by', 'created_by'),
        Index('idx_uma_updated_by', 'updated_by'),
    )


class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    speaker_id = Column(String(50), nullable=False)
    speaker_name = Column(String(50))
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Integer, default=100)
    is_action_item = Column(Boolean, default=False)
    is_decision = Column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="transcriptions")
