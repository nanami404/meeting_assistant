# 标准库
import uuid
from datetime import datetime
from enum import Enum

# 第三方库
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Index, BigInteger
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

    # 主键字段（对齐MySQL：BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID主键（自增）")

    # 基本信息字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    user_name = Column(String(50), nullable=False, unique=True, comment="用户账号")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, comment="手机号码")
    email = Column(String(255), nullable=True, comment="邮箱地址")
    company = Column(String(200), nullable=True, comment="所属单位名称")

    # 权限和状态字段（数据库列名改为 user_role，类型扩展至 36）
    role = Column('user_role', String(36), nullable=False, default=UserRole.USER.value, comment="用户角色：admin-管理员，user-普通用户")
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value, comment="用户状态：active-激活，inactive-未激活，suspended-暂停")

    # 安全信息字段
    password_hash = Column(String(255), nullable=True, comment="密码哈希值（bcrypt加密）")

    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联字段
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    created_meetings = relationship("Meeting", foreign_keys="Meeting.created_by", back_populates="creator")
    updated_meetings = relationship("Meeting", foreign_keys="Meeting.updated_by", back_populates="updater")

    # 自引用关系
    creator_user = relationship("User", foreign_keys=[created_by], remote_side=[id])
    updater_user = relationship("User", foreign_keys=[updated_by], remote_side=[id])

    # 添加索引
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_phone', 'phone'),
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'user_role'),
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
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    role = Column(String(50), default="participant")
    is_required = Column(Boolean, default=True)
    attendance_status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="participants")


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


class Message(Base):
    """消息模型 - 用户消息通知"""
    __tablename__ = "messages"

    # 主键（BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 内容
    title = Column(String(100), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")

    # 关联用户
    sender_id = Column(BigInteger, nullable=False, comment="发送者ID")
    receiver_id = Column(BigInteger, nullable=False, comment="接收者ID")

    # 状态与时间戳
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读(0未读/1已读)")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_receiver_id', 'receiver_id'),
        Index('idx_messages_is_read', 'is_read'),
        Index('idx_messages_created_at', 'created_at'),
    )
