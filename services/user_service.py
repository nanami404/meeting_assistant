# 标准库
from models.database.user import User
from services.service_models import User


from re import Pattern

from datetime import datetime, timezone
from typing import Optional, List, Tuple
import re

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy import or_
from loguru import logger
import bcrypt

# 自定义模块
from .service_models import User, UserRole, UserStatus, Meeting
from schemas import UserCreate, UserUpdate


class UserService(object):
    """用户业务逻辑层
    提供用户的增删改查与安全相关操作。
    所有方法使用 async 定义以保持一致的异步接口风格，内部使用同步 Session 操作。
    """

    # 登录标识符正则（类级别缓存，避免重复编译）
    EMAIL_PATTERN: Pattern[str] = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN: Pattern[str] = re.compile(r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$')

    async def create_user(self, db: Session, user_data: UserCreate, created_by: Optional[int] = None) -> User:
        """创建新用户（包含密码加密与唯一性检查）
        - 使用 bcrypt 对密码进行加密存储
        - 唯一性校验对齐初始化脚本：仅校验 user_name
        """
        try:
            if db.query(User).filter(User.user_name == user_data.user_name).first():
                raise ValueError("user_name 已被占用")

            plain_password: str = user_data.password or "Test@1234"
            hashed: str = bcrypt.hashpw(plain_password.encode(encoding="utf-8"), bcrypt.gensalt()).decode(encoding="utf-8")

            user: User = User(
                name=user_data.name,
                user_name=user_data.user_name,
                gender=user_data.gender,
                phone=user_data.phone,
                email=user_data.email,
                company=user_data.company,
                user_role=user_data.user_role or UserRole.USER.value,
                status=user_data.status or UserStatus.ACTIVE.value,
                password_hash=hashed,
                created_by=created_by,
                created_at=datetime.now(timezone.utc),
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

    def _apply_pagination_and_sort(
        self,
        query,
        page: int,
        page_size: int,
        order_by: str,
        order: str,
        model_class,
        default_order_field: str = "created_at",
        valid_fields: Optional[List[str]] = None,
    ):
        """通用分页与排序逻辑"""
        if valid_fields and order_by not in valid_fields:
            order_by = default_order_field
        sort_col = getattr(model_class, order_by, getattr(model_class, default_order_field))
        if order.lower() == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        page = max(1, page)
        page_size = max(1, min(page_size, 100))  # 限制最大100

        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()
        return items, page, page_size

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
        仅返回活跃状态的用户，用于业务场景如创建会议时选择指定用户。
        """
        try:
            query = db.query(User).filter(User.status == UserStatus.ACTIVE.value)

            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))

            total = query.count()

            valid_order_fields = ["name", "company", "created_at"]
            items, _, _ = self._apply_pagination_and_sort(
                query, page, page_size, order_by, order, User, "name", valid_order_fields
            )

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
        user_role: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        name_keyword: Optional[str] = None,
        user_name_keyword: Optional[str] = None,
        email_keyword: Optional[str] = None,
        company_keyword: Optional[str] = None,
        order_by: str = "created_at",
        order: str = "desc",
    ) -> Tuple[List[User], int]:
        """获取用户列表（支持分页与筛选）"""
        try:
            query = db.query(User)

            if user_role:
                query = query.filter(User.user_role == user_role)
            if status:
                query = query.filter(User.status == status)

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

            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))
            if user_name_keyword:
                query = query.filter(User.user_name.like(f"%{user_name_keyword}%"))
            if email_keyword:
                query = query.filter(User.email.like(f"%{email_keyword}%"))
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))

            total = query.count()

            items, _, _ = self._apply_pagination_and_sort(
                query, page, page_size, order_by, order, User
            )
            return items, total

        except Exception as e:
            logger.error(f"查询用户列表失败: {e}")
            raise e

    async def get_user_by_id(self, db: Session, user_id: int, active_only: bool = True) -> Optional[User]:
        """根据ID获取用户"""
        try:
            query = db.query(User).filter(User.id == user_id)
            if active_only:
                query = query.filter(User.status == UserStatus.ACTIVE.value)
            return query.first()
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
        """根据登录标识符获取用户（支持用户名、邮箱、手机号）"""
        try:
            if self.EMAIL_PATTERN.match(identifier):
                return await self.get_user_by_email(db, identifier)
            elif self.PHONE_PATTERN.match(identifier):
                return await self.get_user_by_phone(db, identifier)
            else:
                return await self.get_user_by_username(db, identifier)
        except Exception as e:
            logger.error(f"根据登录标识符查询用户失败(identifier={identifier}): {e}")
            raise e

    async def update_user(self, db: Session, user_id: int, update_data: UserUpdate, updated_by: Optional[int] = None) -> Optional[User]:
        """更新用户信息（包含唯一性检查）"""
        try:
            user: User | None = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            provided = update_data.model_dump(exclude_unset=True)

            # 检查 user_name 唯一性
            if "user_name" in provided:
                new_username = provided["user_name"]
                if new_username is not None:
                    exists = db.query(User).filter(User.user_name == new_username, User.id != user_id).first()
                    if exists:
                        raise ValueError("user_name 已被占用")

            # 映射字段更新
            field_mapping: dict[str, str] = {
                "name": "name",
                "user_name": "user_name",
                "gender": "gender",
                "phone": "phone",
                "email": "email",
                "company": "company",
                "status": "status",
                "user_role": "user_role"
            }

            for api_field, model_field in field_mapping.items():
                if api_field in provided:
                    setattr(user, model_field, provided[api_field])

            # 更新审计字段
            user.updated_at = datetime.now(tz=timezone.utc)  # type: ignore
            if updated_by:
                user.updated_by = updated_by  # type: ignore

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

    async def delete_user(self, db: Session, user_id: int, operator_id: Optional[int] = None, hard: bool = False) -> bool:
        """删除用户（软删除或硬删除）"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            if not hard:
                user.status = UserStatus.INACTIVE.value  # type: ignore
                user.updated_at = datetime.now(timezone.utc)  # type: ignore
                if operator_id:
                    user.updated_by = operator_id  # type: ignore
                db.commit()
                logger.info(f"已软删除用户: {user_id}")
                return True

            # 硬删除：清理外键引用
            db.query(Meeting).filter(Meeting.created_by == user_id).update({Meeting.created_by: None})
            db.query(Meeting).filter(Meeting.updated_by == user_id).update({Meeting.updated_by: None})
            db.query(User).filter(User.created_by == user_id).update({User.created_by: None})
            db.query(User).filter(User.updated_by == user_id).update({User.updated_by: None})

            db.delete(user)
            db.commit()
            logger.info(f"已硬删除用户并清理引用: {user_id}")
            return True

        except Exception as e:
            logger.error(f"删除用户失败(id={user_id}, hard={hard}): {e}")
            db.rollback()
            raise e

        async def verify_password(self, user: User, plain_password: str) -> bool:
            """验证用户密码（bcrypt）"""
            try:
                if not user.password_hash:  # type: ignore
                    return False
                return bcrypt.checkpw(plain_password.encode("utf-8"), user.password_hash.encode("utf-8"))  # type: ignore
            except Exception as e:
                logger.error(f"验证密码失败(user={user.id}): {e}")
                return False

        async def change_user_status(self, db: Session, user_id: int, status: str, operator_id: Optional[int] = None) -> bool:
            """修改用户状态：active / inactive / suspended"""
            try:
                valid_statuses = {UserStatus.ACTIVE.value, UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value}
                if status not in valid_statuses:
                    raise ValueError("非法的用户状态")

                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return False

                user.status = status  # type: ignore
                user.updated_at = datetime.now(timezone.utc)  # type: ignore
                if operator_id:
                    user.updated_by = operator_id  # type: ignore

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

        async def reset_password(
            self,
            db: Session,
            user_id: int,
            operator_id: Optional[int] = None,
            default_password: str = "Test@1234"
        ) -> bool:
            """重置用户密码为默认值（bcrypt加密）"""
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return False

                hashed = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                user.password_hash = hashed  # type: ignore
                user.updated_at = datetime.now(timezone.utc)  # type: ignore
                if operator_id:
                    user.updated_by = operator_id  # type: ignore

                db.commit()
                logger.info(f"用户密码已重置: user_id={user_id}")
                return True

            except Exception as e:
                logger.error(f"重置用户密码失败(id={user_id}): {e}")
                db.rollback()
                raise e