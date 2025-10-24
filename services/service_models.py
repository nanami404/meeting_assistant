# 标准库
import uuid
from datetime import datetime
from enum import Enum
import pytz

# 第三方库 - SQLAlchemy相关
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    func,
    UniqueConstraint
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

class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class TranslationText(Base):
    __tablename__ = "translation_texts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(100), nullable=False, index=True)
    speaker_name = Column(String(100), nullable=True)  # 如果没有说话人信息可以设为可选
    text = Column(Text, nullable=False)  # 使用Text类型存储长文本
    created_time = Column(DateTime, default=datetime.utcnow)

class GenderType(str, Enum):
    """性别类型枚举"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(Base):
    """用户模型 - 管理系统用户信息"""
    __tablename__ = "users"

    # 主键字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="用户主键ID（UUID）")
    # 基本信息字段
    name = Column(String(100), nullable=False, comment="用户姓名")
    user_name = Column(String(50), nullable=False, unique=True, comment="用户账号")
    gender = Column(String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号码")
    email = Column(String(255), nullable=True, unique=True, comment="邮箱地址")
    company = Column(String(200), nullable=True, comment="所属单位名称")

    # 权限和状态字段
    user_role = Column(String(20), nullable=False, default=UserRole.USER.value,
                       comment="用户角色：admin-管理员，user-普通用户")
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value,
                    comment="用户状态：active-激活，inactive-未激活，suspended-暂停")

    # 安全信息字段
    password_hash = Column(String(255), nullable=False, comment="密码哈希值（bcrypt加密）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="更新时间")

    # 关联字段
    created_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="创建者用户ID")
    updated_by = Column(String(50), ForeignKey("users.id"), nullable=True, comment="更新者用户ID")

    # 关联关系
    created_meetings = relationship("Meeting", foreign_keys="Meeting.created_by", back_populates="creator")
    updated_meetings = relationship("Meeting", foreign_keys="Meeting.updated_by", back_populates="updater")
    participations = relationship("Participant", foreign_keys="Participant.user_code", back_populates="user")


    # 自引用关系
    creator_user = relationship("User", foreign_keys=[created_by], remote_side=[id])
    updater_user = relationship("User", foreign_keys=[updated_by], remote_side=[id])

    # 添加索引
    __table_args__ = (
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'user_role'),
        Index('idx_users_status', 'status')
    )

# 定义人员签到表模型
class PersonSign(Base):
    __tablename__ = "person_sign"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50),index=True)
    user_code = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    meeting_id = Column(String(50), ForeignKey("meetings.id"), nullable=False)
    is_signed = Column(Boolean, default=False)
    is_on_leave = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(shanghai_tz), comment="创建时间")

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

    # 与 User 模型中的 participations 对应
    user = relationship(
        "User",
        foreign_keys=[user_code],
        back_populates="participations"
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


class Message(Base):
    """消息内容表 - 存储消息基本信息"""
    __tablename__ = "messages"

    # 主键（BIGINT 自增）
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 内容
    title = Column(String(100), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")

    # 关联用户
    # 注意：将 sender_id 显式声明为外键，以便 SQLAlchemy 正确建立 Message.sender 关系
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="发送者ID（UUID）")

    # 发送者关系 - 关联到 User 模型
    # 说明：为便于在查询中使用 joinedload(Message.sender) 以及在业务代码中访问 msg.sender.user_name
    # 定义从 Message 到 User 的多对一关系。
    sender = relationship("User", foreign_keys=[sender_id], lazy="joined")

    # 时间戳
    # 说明：与数据库 DDL 保持一致，使用 CURRENT_TIMESTAMP 语义
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系 - 与MessageRecipient的一对多关系
    recipients = relationship("MessageRecipient", back_populates="message", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_messages_sender_id', 'sender_id'),
        Index('idx_messages_created_at', 'created_at'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return f"<Message(id={self.id}, title='{self.title}', sender_id={self.sender_id})>"


class MessageRecipient(Base):
    """消息接收者关联表 - 支持多接收者消息功能"""
    __tablename__ = "message_recipients"

    # 主键字段
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID（自增）")

    # 关联字段
    message_id = Column(BigInteger, ForeignKey("messages.id"), nullable=False, comment="消息ID（外键指向 messages.id）")
    recipient_id = Column(String(36), nullable=False, comment="接收者ID（UUID）")

    # 状态字段
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读(0未读/1已读)")
    read_at = Column(DateTime(timezone=True), nullable=True, comment="阅读时间（可选）")

    # 时间戳字段
    created_at = Column(DateTime(timezone=True), default=func.now(), comment="创建时间（关联时间）")

    # 关联关系 - 与Message的多对一关系
    message = relationship("Message", back_populates="recipients")

    # 约束与索引 - 与数据库DDL保持一致
    __table_args__ = (
        UniqueConstraint('message_id', 'recipient_id', name='uk_message_recipient'),
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    # 索引设计 - 优化查询性能
    __table_args__ = (
        # 唯一约束：防止重复发送
        Index('uk_message_recipient', 'message_id', 'recipient_id', unique=True),
        # 索引
        Index('idx_message_recipients_recipient_id', 'recipient_id'),
        Index('idx_message_recipients_is_read', 'is_read'),
        Index('idx_message_recipients_message_id', 'message_id'),
    )

    def __repr__(self) -> str:
        """字符串表示方法，便于调试"""
        return (
            f"<MessageRecipient("
            f"id={self.id}, "
            f"message_id={self.message_id}, "
            f"recipient_id={self.recipient_id}, "
            f"is_read={self.is_read}"
            f")>"
        )


    def mark_as_read(self) -> None:
        """标记消息为已读"""
        self.is_read = True
        self.read_at = datetime.now(shanghai_tz)

    def mark_as_unread(self) -> None:
        """标记消息为未读"""
        self.is_read = False
        self.read_at = None
