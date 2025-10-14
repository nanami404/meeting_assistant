# 标准库
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
import re

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from loguru import logger
import bcrypt

# 自定义模块
from .service_models import User, UserRole, UserStatus
from schemas import UserCreate, UserUpdate


class UserService(object):
    """用户业务逻辑层
    参考 MeetingService 的代码结构与风格，提供用户的增删改查与安全相关操作。
    所有方法使用 async 定义以保持一致的异步接口风格，内部使用同步 Session 操作。
    """

    async def create_user(self, db: Session, user_data: UserCreate, created_by: Optional[int] = None) -> User:
        """创建新用户（包含密码加密与唯一性检查）
        - 使用 bcrypt 对密码进行加密存储
        - 唯一性校验对齐初始化脚本：仅校验 user_name
        """
        try:
            # 唯一性检查（仅用户名）
            exists = db.query(User).filter(User.user_name == user_data.user_name).first()
            if exists:
                raise ValueError("user_name 已被占用")

            # 加密密码
            hashed = bcrypt.hashpw(user_data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            # 创建用户
            user = User(
                name=user_data.name,
                user_name=user_data.user_name,
                gender=user_data.gender,
                phone=user_data.phone,
                email=user_data.email,
                company=user_data.company,
                role=user_data.role or UserRole.USER.value,
                status=user_data.status or UserStatus.ACTIVE.value,
                password_hash=hashed,
                created_by=created_by,
                # created_at/updated_at 由模型默认处理
            )

            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"成功创建用户: {user.id} ({user.email})")
            return user
        except ValueError as ve:
            logger.warning(f"创建用户参数错误: {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            db.rollback()
            raise e

    async def get_users_basic(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        name_keyword: Optional[str] = None,
        company_keyword: Optional[str] = None,
        order_by: str = "name",
        order: str = "asc",
    ) -> Tuple[List[User], int]:
        """获取用户基础信息列表（公共接口专用）
        
        专门用于公共接口，支持按用户名和部门进行模糊查询。
        仅返回活跃状态的用户，用于业务场景如创建会议时选择指定用户。
        
        Args:
            db: 数据库会话
            page: 页码，从1开始
            page_size: 每页数量，默认20
            name_keyword: 用户姓名关键词（模糊匹配）
            company_keyword: 部门/单位关键词（模糊匹配）
            order_by: 排序字段，默认按姓名排序
            order: 排序方向，asc/desc，默认升序
            
        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        try:
            # 基础查询：仅查询活跃状态的用户
            query = db.query(User).filter(User.status == UserStatus.ACTIVE.value)
            
            # 按用户姓名模糊匹配
            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))
            
            # 按部门/单位模糊匹配
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))

            # 获取总数
            total = query.count()

            # 排序
            valid_order_fields = ["name", "company", "created_at"]
            if order_by not in valid_order_fields:
                order_by = "name"
            
            sort_col = getattr(User, order_by, User.name)
            if order.lower() == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

            # 分页
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 20
            if page_size > 100:  # 限制最大页面大小
                page_size = 100
                
            items = query.offset((page - 1) * page_size).limit(page_size).all()
            
            logger.info(f"公共接口查询用户列表: 页码={page}, 页大小={page_size}, 总数={total}")
            return items, total
            
        except Exception as e:
            logger.error(f"公共接口查询用户列表失败: {e}")
            raise e

    async def get_users(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        role: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        name_keyword: Optional[str] = None,
        user_name_keyword: Optional[str] = None,
        email_keyword: Optional[str] = None,
        company_keyword: Optional[str] = None,
        order_by: str = "created_at",
        order: str = "desc",
    ) -> Tuple[List[User], int]:
        """获取用户列表（支持分页与筛选）
        返回 (items, total) 二元组
        """
        try:
            query = db.query(User)

            if role:
                query = query.filter(User.role == role)
            if status:
                query = query.filter(User.status == status)
            
            # 原有的通用关键词匹配（保持向后兼容）
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    or_(
                        User.name.like(like),
                        User.email.like(like),
                        User.company.like(like),
                        User.user_name.like(like),
                    )
                )
            
            # 独立字段的模糊匹配（AND 关系）
            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))
            if user_name_keyword:
                query = query.filter(User.user_name.like(f"%{user_name_keyword}%"))
            if email_keyword:
                query = query.filter(User.email.like(f"%{email_keyword}%"))
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))
            # 去除 id_number 相关过滤（对齐初始化脚本）

            total = query.count()

            # 排序
            sort_col = getattr(User, order_by, User.created_at)
            if order.lower() == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

            # 分页
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 20
            items = query.offset((page - 1) * page_size).limit(page_size).all()
            return items, total
        except Exception as e:
            logger.error(f"查询用户列表失败: {e}")
            raise e

    async def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        try:
            return db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(f"查询用户失败(id={user_id}): {e}")
            raise e

    async def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        try:
            return db.query(User).filter(User.email == email).first()
        except Exception as e:
            logger.error(f"查询用户失败(email={email}): {e}")
            raise e

    async def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            return db.query(User).filter(User.user_name == username).first()
        except Exception as e:
            logger.error(f"查询用户失败(username={username}): {e}")
            raise e

    async def get_user_by_phone(self, db: Session, phone: str) -> Optional[User]:
        """根据手机号获取用户"""
        try:
            return db.query(User).filter(User.phone == phone).first()
        except Exception as e:
            logger.error(f"查询用户失败(phone={phone}): {e}")
            raise e

    async def get_user_by_login_identifier(self, db: Session, identifier: str) -> Optional[User]:
        """
        根据登录标识符获取用户
        支持用户名、邮箱、手机号三种方式
        """
        import re
        
        try:
            # 检查是否为邮箱格式
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            # 检查是否为手机号格式
            phone_pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
            
            if re.match(email_pattern, identifier):
                # 邮箱登录
                return await self.get_user_by_email(db, identifier)
            elif re.match(phone_pattern, identifier):
                # 手机号登录
                return await self.get_user_by_phone(db, identifier)
            else:
                # 用户名登录
                return await self.get_user_by_username(db, identifier)
                
        except Exception as e:
            logger.error(f"根据登录标识符查询用户失败(identifier={identifier}): {e}")
            raise e

    async def update_user(self, db: Session, user_id: int, update_data: UserUpdate, updated_by: Optional[int] = None) -> Optional[User]:
        """更新用户信息（包含唯一性检查）"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            # 如果更新 user_name，需要检查唯一性（对齐初始化脚本）
            def check_unique(field_name: str, new_value: Optional[str]):
                if new_value is None:
                    return
                exists = db.query(User).filter(getattr(User, field_name) == new_value, User.id != user_id).first()
                if exists:
                    raise ValueError(f"{field_name} 已被占用")

            check_unique("user_name", update_data.user_name if hasattr(update_data, "user_name") else None)

            # 应用更新（仅更新提供的字段）
            for field in [
                "name", "gender", "phone", "email", "company", "role", "status"
            ]:
                value = getattr(update_data, field, None)
                if value is not None:
                    setattr(user, field, value)

            # 审计字段
            if updated_by:
                user.updated_by = updated_by
            user.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(user)
            logger.info(f"用户更新成功: {user.id}")
            return user
        except ValueError as ve:
            logger.warning(f"更新用户参数错误(id={user_id}): {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"更新用户失败(id={user_id}): {e}")
            db.rollback()
            raise e

    async def delete_user(self, db: Session, user_id: int, operator_id: Optional[int] = None) -> bool:
        """软删除用户：将用户状态置为 inactive，而非物理删除"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            user.status = UserStatus.INACTIVE.value
            if operator_id:
                user.updated_by = operator_id
            user.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"已软删除用户: {user_id}")
            return True
        except Exception as e:
            logger.error(f"软删除用户失败(id={user_id}): {e}")
            db.rollback()
            raise e

    async def verify_password(self, user: User, plain_password: str) -> bool:
        """验证用户密码（bcrypt）"""
        try:
            if not user.password_hash:
                return False
            return bcrypt.checkpw(plain_password.encode("utf-8"), user.password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"验证密码失败(user={user.id}): {e}")
            return False

    async def change_user_status(self, db: Session, user_id: int, status: str, operator_id: Optional[int] = None) -> bool:
        """修改用户状态：active / inactive / suspended"""
        try:
            if status not in [UserStatus.ACTIVE.value, UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value]:
                raise ValueError("非法的用户状态")
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            user.status = status
            if operator_id:
                user.updated_by = operator_id
            user.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"用户状态修改成功: {user_id} -> {status}")
            return True
        except ValueError as ve:
            logger.warning(f"修改用户状态参数错误(id={user_id}): {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"修改用户状态失败(id={user_id}): {e}")
            db.rollback()
            raise e