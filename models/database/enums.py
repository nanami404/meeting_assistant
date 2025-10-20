# 标准库
from enum import Enum


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