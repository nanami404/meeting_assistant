# 标准库
from typing import Optional, List

# 第三方库
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session
from loguru import logger

# 自定义模块
from db.databases import DatabaseConfig, DatabaseSessionManager
from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_dependencies import require_auth, require_admin
from models.database.user import User
from models.database.enums import UserStatus, UserRole
from models.schemas import UserLogin, UserCreate, UserUpdate, UserResponse, UserBasicResponse

router = APIRouter(prefix="/api", tags=["Users & Auth"])

# Services
user_service = UserService()
auth_service = AuthService()

# 对外暴露的依赖注入函数
db_config: DatabaseConfig = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖

# ----------------------------- 辅助方法 -----------------------------

def _resp(data=None, message="success", code=0):
    return {"code": code, "message": message, "data": data}


def _raise(status_code: int, message: str, code: str):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _extract_bearer_token(authorization: Optional[str]) -> str:
    # 确保 authorization 不为 None 后再调用 split()
    if not authorization:
        _raise(status.HTTP_401_UNAUTHORIZED, "缺少Authorization头", "unauthorized")
    parts: list[str] = authorization.split()  # type: ignore
    if len(parts) != 2 or parts[0].lower() != "bearer":
        _raise(status.HTTP_401_UNAUTHORIZED, "Authorization格式错误，应为'Bearer <token>'", "unauthorized")
    return parts[1]


# ============================= 认证相关 =============================
@router.post("/auth/login", summary="用户登录", response_model=dict)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    """用户登录，返回access与refresh令牌"""
    try:
        result: Optional[tuple[str, str]] = await auth_service.login_and_issue(db, payload.username, payload.password, user_service)
        if not result:
            _raise(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误", "auth_failed")
        access_token, refresh_token = result  
        return _resp({"access_token": access_token, "refresh_token": refresh_token})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/auth/logout", summary="用户登出", response_model=dict)
async def logout(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    current_user: User = Depends(require_auth)
):
    """撤销当前Authorization中的令牌"""
    try:
        token = _extract_bearer_token(authorization)
        ok = auth_service.revoke_token(token)
        if not ok:
            _raise(status.HTTP_400_BAD_REQUEST, "令牌撤销失败", "revoke_failed")
        logger.info(f"用户登出成功 user_id={current_user.id}")
        return _resp({"revoked": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登出异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/auth/refresh", summary="刷新令牌", response_model=dict)
async def refresh(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """使用Authorization中的refresh令牌刷新access与refresh（令牌轮换）"""
    try:
        refresh_token = _extract_bearer_token(authorization)
        # 先验证刷新令牌，获取用户ID
        payload: Optional[dict] = auth_service.verify_token(refresh_token, expected_type="refresh")
        if not payload:
            _raise(status.HTTP_401_UNAUTHORIZED, "无效或过期的刷新令牌", "unauthorized")
        user_id: str = payload.get("sub", "")  # type: ignore
        if not user_id:
            _raise(status.HTTP_401_UNAUTHORIZED, "令牌缺少用户标识", "unauthorized")
        user: Optional[User] = await user_service.get_user_by_id(db, int(user_id))
        if not user:
            _raise(status.HTTP_401_UNAUTHORIZED, "用户不存在或已删除", "unauthorized")
        # 修复 ColumnElement[bool] 类型错误：将比较结果转换为 Python 布尔值
        if user is not None and str(user.status) != UserStatus.ACTIVE.value:  
            _raise(status.HTTP_403_FORBIDDEN, f"用户状态为{user.status}，禁止刷新", "forbidden")
        result: Optional[tuple[str, str]] = auth_service.refresh_access_token(refresh_token, user)  # type: ignore
        if not result:
            _raise(status.HTTP_400_BAD_REQUEST, "刷新令牌失败", "refresh_failed")
        access_token, new_refresh = result  
        return _resp({"access_token": access_token, "refresh_token": new_refresh})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


# ============================= 用户信息相关 =============================
@router.get("/auth/profile", summary="获取当前用户信息", response_model=dict)
async def profile(current_user: User = Depends(require_auth)):
    """获取当前登录用户的详细信息"""
    try:
        user_data = UserResponse(
            id=int(str(current_user.id)),  
            name=str(current_user.name),  
            user_name=str(current_user.user_name),  
            gender=str(current_user.gender) if current_user.gender is not None else None,  
            phone=str(current_user.phone) if current_user.phone is not None else None,  
            email=str(current_user.email) if current_user.email is not None else None,  
            company=str(current_user.company) if current_user.company is not None else None,  
            user_role=str(current_user.user_role),  
            status=str(current_user.status),  
            created_at=current_user.created_at,  
            updated_at=current_user.updated_at,  
            created_by=int(str(current_user.created_by)) if current_user.created_by is not None else None,  
            updated_by=int(str(current_user.updated_by)) if current_user.updated_by is not None else None  
        )
        return _resp(user_data.dict())
    except Exception as e:
        logger.error(f"获取用户信息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


# ============================= 公共接口 =============================
@router.get("/public/users", summary="公共用户列表查询", response_model=dict)
async def list_users_public(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    name_keyword: Optional[str] = Query(None, description="用户姓名关键词（模糊匹配）"),
    company_keyword: Optional[str] = Query(None, description="部门/单位关键词（模糊匹配）"),
    order_by: str = Query("name", description="排序字段：name（姓名）、company（部门）、created_at（创建时间）"),
    order: str = Query("asc", description="排序方向：asc（升序）、desc（降序）")
):
    """
    公共用户列表查询接口
    
    - 支持按用户姓名和部门进行模糊查询
    - 仅返回活跃状态的用户基础信息
    - 主要用于业务场景如创建会议时选择指定用户
    - 无需认证，作为公共接口开放给其他业务系统调用
    
    **查询参数说明：**
    - name_keyword: 按用户姓名进行模糊匹配
    - company_keyword: 按部门/单位进行模糊匹配
    - 多个查询条件之间为AND关系
    
    **返回数据说明：**
    - 仅返回用户基础信息：ID、姓名、用户名、手机号、邮箱、部门
    - 自动过滤非活跃状态用户
    - 支持分页和排序
    """
    try:
        users, total = await user_service.get_users_basic(
            db=db,
            page=page,
            page_size=page_size,
            name_keyword=name_keyword,
            company_keyword=company_keyword,
            order_by=order_by,
            order=order
        )
        
        # 转换为基础响应格式
        user_list = []
        for user in users:
            user_basic = UserBasicResponse(
                id=int(str(user.id)),  
                name=str(user.name),  
                user_name=str(user.user_name),  
                phone=str(user.phone) if user.phone is not None else None,  
                email=str(user.email) if user.email is not None else None,  
                company=str(user.company) if user.company is not None else None  
            )
            user_list.append(user_basic.dict())
        
        # 计算分页信息
        total_pages = (total + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        result = {
            "users": user_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
        return _resp(result)
        
    except Exception as e:
        logger.error(f"公共用户列表查询异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


# ============================= 管理员用户管理 =============================
@router.post("/users/", summary="创建用户", response_model=dict)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """创建新用户（仅管理员）"""
    try:
        user: User = await user_service.create_user(db, payload, created_by=int(str(current_user.id)))  
        user_data = UserResponse(
            id=int(str(user.id)),  
            name=str(user.name),  
            user_name=str(user.user_name),  
            gender=str(user.gender) if user.gender is not None else None,  
            phone=str(user.phone) if user.phone is not None else None,  
            email=str(user.email) if user.email is not None else None,  
            company=str(user.company) if user.company is not None else None,  
            user_role=str(user.user_role),  
            status=str(user.status),  
            created_at=user.created_at,  
            updated_at=user.updated_at,  
            created_by=int(str(user.created_by)) if user.created_by is not None else None,  
            updated_by=int(str(user.updated_by)) if user.updated_by is not None else None  
        )
        return _resp(user_data.dict())
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except Exception as e:
        logger.error(f"创建用户异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


# ============================= 用户注册（固定一般用户） =============================
@router.post("/auth/register", summary="匿名用户注册（角色固定为一般用户）", response_model=dict)
async def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db)
):
    """
    匿名用户注册接口：
    - 角色强制设置为一般用户（user）
    - 创建人设置为 null（匿名注册）
    - 包含必要的参数校验与错误处理
    - 密码由服务层进行bcrypt哈希安全存储
    """
    try:
        # 密码必填校验（与管理员创建不同，这里要求注册必须提供密码）
        if not payload.password or not payload.password.strip():
            _raise(status.HTTP_422_UNPROCESSABLE_ENTITY, "注册需提供有效密码", "validation_error")

        # 强制角色为一般用户
        payload.user_role = UserRole.USER.value

        # 创建用户（匿名：creator=None）
        user: User = await user_service.create_user(db, payload, created_by=None)

        # 构造响应
        user_data = UserResponse(
            id=int(str(user.id)),  
            name=str(user.name),  
            user_name=str(user.user_name),  
            gender=str(user.gender) if user.gender is not None else None,  
            phone=str(user.phone) if user.phone is not None else None,  
            email=str(user.email) if user.email is not None else None,  
            company=str(user.company) if user.company is not None else None,  
            user_role=str(user.user_role),  
            status=str(user.status),  
            created_at=user.created_at,  
            updated_at=user.updated_at,  
            created_by=int(str(user.created_by)) if user.created_by is not None else None,  
            updated_by=int(str(user.updated_by)) if user.updated_by is not None else None  
        )
        return _resp(user_data.dict(), message="注册成功")
    except HTTPException:
        # 透传显式的HTTP异常
        raise
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "validation_error")
    except Exception as e:
        logger.error(f"用户注册异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/users/", summary="获取用户列表", response_model=dict)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    user_role: Optional[str] = Query(None, description="角色过滤"),
    status_: Optional[str] = Query(None, alias="status", description="状态过滤"),
    keyword: Optional[str] = Query(None, description="通用关键词模糊匹配（姓名、账号、邮箱、单位、4A账号）"),
    name_keyword: Optional[str] = Query(None, description="姓名模糊匹配"),
    user_name_keyword: Optional[str] = Query(None, description="用户账号模糊匹配"),
    email_keyword: Optional[str] = Query(None, description="邮箱模糊匹配"),
    company_keyword: Optional[str] = Query(None, description="单位模糊匹配"),
    order_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="排序方向(desc/asc)")
):
    """获取用户列表（管理员权限）"""
    try:
        items, total = await user_service.get_users(
            db=db,
            page=page,
            page_size=page_size,
            user_role=user_role,
            status=status_,
            keyword=keyword,
            name_keyword=name_keyword,
            user_name_keyword=user_name_keyword,
            email_keyword=email_keyword,
            company_keyword=company_keyword,
            order_by=order_by,
            order=order,
        )
        data_items: List[dict] = []
        for u in items:
            data_items.append(UserResponse(
                id=int(str(u.id)),  
                user_name=str(u.user_name),  
                name=str(u.name),  
                email=str(u.email) if u.email is not None else None,  
                gender=str(u.gender) if u.gender is not None else None,  
                phone=str(u.phone) if u.phone is not None else None,  
                company=str(u.company) if u.company is not None else None,  
                user_role=str(u.user_role),  
                status=str(u.status),  
                created_at=u.created_at,  
                updated_at=u.updated_at,  
                created_by=int(str(u.created_by)) if u.created_by is not None else None,  
                updated_by=int(str(u.updated_by)) if u.updated_by is not None else None,  
            ).dict())
        return _resp({"items": data_items, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        logger.error(f"获取用户列表异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/users/{user_id}", summary="获取用户详情", response_model=dict)
async def get_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
    """获取用户详情（权限控制：普通用户只能查询自己的信息，管理员可以查询任意用户信息）"""
    try:
        # 权限检查：普通用户只能查询自己的信息，管理员可以查询任意用户信息
        # 修复 ColumnElement[bool] 类型错误：将比较结果转换为 Python 布尔值
        if str(current_user.user_role) != "admin" and int(str(current_user.id)) != user_id:  
            _raise(status.HTTP_403_FORBIDDEN, "权限不足，只能查询自己的用户信息", "forbidden")
        
        user_obj: Optional[User] = await user_service.get_user_by_id(db, user_id)
        if not user_obj:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        data: UserResponse = UserResponse(
            id=int(str(user_obj.id)),  
            user_name=str(user_obj.user_name),  
            name=str(user_obj.name),  
            email=str(user_obj.email) if user_obj.email is not None else None,  
            gender=str(user_obj.gender) if user_obj.gender is not None else None,  
            phone=str(user_obj.phone) if user_obj.phone is not None else None,  
            company=str(user_obj.company) if user_obj.company is not None else None,  
            user_role=str(user_obj.user_role),  
            status=str(user_obj.status),  
            created_at=user_obj.created_at,  
            updated_at=user_obj.updated_at,  
            created_by=int(str(user_obj.created_by)) if user_obj.created_by is not None else None,  
            updated_by=int(str(user_obj.updated_by)) if user_obj.updated_by is not None else None,  
        )
        return _resp(data.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户详情异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.put("/users/{user_id}", summary="更新用户信息", response_model=dict)
async def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """更新用户信息（管理员权限）"""
    try:
        user_obj: Optional[User] = await user_service.update_user(db, user_id, payload, updated_by=int(str(current_user.id)))  
        if not user_obj:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        data = UserResponse(
            id=int(str(user_obj.id)),  
            user_name=str(user_obj.user_name),  
            name=str(user_obj.name),  
            email=str(user_obj.email) if user_obj.email is not None else None,  
            gender=str(user_obj.gender) if user_obj.gender is not None else None,  
            phone=str(user_obj.phone) if user_obj.phone is not None else None,  
            company=str(user_obj.company) if user_obj.company is not None else None,  
            user_role=str(user_obj.user_role),  
            status=str(user_obj.status),  
            created_at=user_obj.created_at,  
            updated_at=user_obj.updated_at,  
            created_by=int(str(user_obj.created_by)) if user_obj.created_by is not None else None,  
            updated_by=int(str(user_obj.updated_by)) if user_obj.updated_by is not None else None,  
        )
        return _resp(data.dict())
    except HTTPException:
        raise
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "bad_request")
    except Exception as e:
        logger.error(f"更新用户信息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.delete("/users/{user_id}", summary="删除用户(软/硬删除)", response_model=dict)
async def delete_user(user_id: int, hard: bool = Query(False, description="是否执行硬删除(物理删除并清理引用)"), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """删除用户（管理员权限）
    - 默认软删除：将用户状态置为inactive
    - hard=true：物理删除用户并清理相关引用
    """
    try:
        ok = await user_service.delete_user(db, user_id, operator_id=int(str(current_user.id)), hard=hard)  
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        return _resp({"deleted": True, "hard": hard})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除用户异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.patch("/users/{user_id}/status", summary="修改用户状态", response_model=dict)
async def change_status(user_id: int, status_: str = Query(..., alias="status"), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """修改用户状态（管理员权限）"""
    try:
        if status_ not in [UserStatus.ACTIVE.value, UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value]:
            _raise(status.HTTP_400_BAD_REQUEST, "非法的用户状态", "bad_request")
        ok = await user_service.change_user_status(db, user_id, status_, operator_id=int(str(current_user.id)))  
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        return _resp({"user_id": user_id, "status": status_})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改用户状态异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.post("/users/{user_id}/reset_password", summary="重置用户密码为默认值(仅管理员)", response_model=dict)
async def reset_password(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """重置指定用户密码为默认值（管理员权限）"""
    try:
        ok = await user_service.reset_password(db, user_id, operator_id=int(str(current_user.id)))  
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        return _resp({"user_id": user_id, "reset": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置用户密码异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")