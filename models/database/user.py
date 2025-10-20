# -*- coding: utf-8 -*-
from typing import Optional, List
from sqlalchemy import String, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 自定义库
from db.base import AuditedBase  # ✅ 关键：继承 AuditedBase
from models.database.meeting import Meeting,Participant
from models.database.enums import UserRole, UserStatus


class User(AuditedBase):
    """用户模型 - 管理系统用户信息"""
    __tablename__ = "users"

    # 主键字段（AuditedBase 不包含 id，需显式定义）
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="用户主键ID（自增）"
    )

    # 基本信息字段
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="用户姓名")
    user_name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="用户账号"
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="性别：male-男性，female-女性，other-其他"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, unique=True, comment="手机号码"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, comment="邮箱地址"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="所属单位名称"
    )

    # 权限和状态字段
    user_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UserRole.USER.value,
        comment="用户角色：admin-管理员，user-普通用户"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UserStatus.ACTIVE.value,
        comment="用户状态：active-激活，inactive-未激活，suspended-暂停"
    )

    # 安全信息字段
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值（bcrypt加密）"
    )

    # ✅ 审计字段已由 AuditedBase 提供，无需重复定义：
    # created_at, updated_at, created_by, updated_by

    # 关联关系
    created_meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting", foreign_keys="Meeting.created_by", back_populates="creator"
    )
    updated_meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting", foreign_keys="Meeting.updated_by", back_populates="updater"
    )
    participations: Mapped[List["Participant"]] = relationship(
        "Participant", foreign_keys="Participant.user_code", back_populates="user"
    )

    # 自引用关系（创建者/更新者用户信息）
    creator_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[AuditedBase.created_by], remote_side=[id]
    )
    updater_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[AuditedBase.updated_by], remote_side=[id]
    )

    # 索引
    __table_args__ = (
        Index('idx_users_user_name', 'user_name'),
        Index('idx_users_role', 'user_role'),
        Index('idx_users_status', 'status'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', user_name='{self.user_name}')>"
