# 标准库
import uuid
from datetime import datetime

# 第三方库
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Enum, Index, Table
from sqlalchemy.orm import relationship
import enum

# 自定义库
from db.databases import Base

# 枚举定义
class UserRole(enum.Enum):
    """用户角色枚举"""
    admin = "admin"  # 管理员
    user = "user"    # 普通用户

class UserStatus(enum.Enum):
    """用户状态枚举"""
    active = "active"        # 激活
    inactive = "inactive"    # 未激活
    suspended = "suspended"  # 暂停

# 用户-会议关联表（多对多关系）
user_meeting_association = Table(
    'user_meetings',
    Base.metadata,
    Column('user_id', String(50), ForeignKey('users.id'), primary_key=True),
    Column('meeting_id', String(50), ForeignKey('meetings.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
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
    # Relationships
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")
    # 与用户的多对多关系
    users = relationship("User", secondary=user_meeting_association, back_populates="meetings")

class Participant(Base):
    __tablename__ = "participants"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    # organizer, participant, presenter
    role = Column(String(50), default="participant")
    is_required = Column(Boolean, default=True)
    # pending, accepted, declined, tentative
    attendance_status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    meeting = relationship("Meeting", back_populates="participants")

class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    # Could be participant ID or name
    speaker_id = Column(String(50), nullable=False)
    speaker_name = Column(String(50))
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    # 0-100 speech recognition confidence
    confidence_score = Column(Integer, default=100)
    is_action_item = Column(Boolean, default=False)
    is_decision = Column(Boolean, default=False)
    # Relationships
    meeting = relationship("Meeting", back_populates="transcriptions")

class User(Base):
    """
    用户模型
    
    用于管理系统用户信息，包括基本信息、身份信息、安全信息和审计信息。
    支持与会议的多对多关联关系，实现用户参与会议的管理。
    
    字段说明:
    - 基础字段: id(主键), name(姓名), gender(性别), phone(电话), email(邮箱)
    - 身份字段: id_number(证件号), company(公司), role(角色), status(状态)
    - 安全字段: password_hash(密码哈希)
    - 审计字段: created_at(创建时间), updated_at(更新时间), created_by(创建人), updated_by(更新人)
    """
    __tablename__ = "users"
    
    # 主键字段
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 基础字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, comment="手机号码")
    email = Column(String(255), nullable=False, comment="邮箱地址")
    
    # 身份字段
    id_number = Column(String(18), nullable=True, comment="证件号码/工号")
    company = Column(String(200), nullable=True, comment="所属公司/单位")
    role = Column(Enum(UserRole), nullable=False, default=UserRole.user, comment="用户角色")
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.active, comment="用户状态")
    
    # 安全字段
    password_hash = Column(String(255), nullable=True, comment="密码哈希值（bcrypt加密）")
    
    # 审计字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")
    
    # 关联关系
    # 与会议的多对多关系
    meetings = relationship("Meeting", secondary=user_meeting_association, back_populates="users")
    
    # 自引用关系（创建者和更新者）
    creator = relationship("User", remote_side=[id], foreign_keys=[created_by], post_update=True)
    updater = relationship("User", remote_side=[id], foreign_keys=[updated_by], post_update=True)
    
    # 索引定义
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_phone', 'phone'),
        Index('idx_users_role', 'role'),
        Index('idx_users_status', 'status'),
        Index('idx_users_company', 'company'),
        Index('idx_users_created_at', 'created_at'),
        Index('idx_users_created_by', 'created_by'),
        Index('idx_users_updated_by', 'updated_by'),
    )
