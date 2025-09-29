# 标准库
from typing import Optional, List, Tuple

# 第三方库
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session
from loguru import logger

# 自定义模块
from db.databases import get_db
from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_dependencies import get_current_user, require_auth, require_admin
from services.service_models import User, UserStatus
from schemas import UserLogin, UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/api", tags=["Users & Auth"])

# Services
user_service = UserService()
auth_service = AuthService()

# ----------------------------- 辅助方法 -----------------------------

def _resp(data=None, message="success", code=0):
    return {"code": code, "message": message, "data": data}


def _raise(status_code: int, message: str, code: str):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        _raise(status.HTTP_401_UNAUTHORIZED, "缺少Authorization头", "unauthorized")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        _raise(status.HTTP_401_UNAUTHORIZED, "Authorization格式错误，应为'Bearer <token>'", "unauthorized")
    return parts[1]


# ============================= 认证相关 =============================
@router.post("/auth/login", summary="用户登录", response_model=dict)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    """用户登录，返回access与refresh令牌"""
    try:
        tokens = await auth_service.login_and_issue(db, payload.username, payload.password, user_service)
        if not tokens:
            _raise(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误", "auth_failed")
        access_token, refresh_token = tokens
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
        payload = auth_service.verify_token(refresh_token, expected_type="refresh")
        if not payload:
            _raise(status.HTTP_401_UNAUTHORIZED, "无效或过期的刷新令牌", "unauthorized")
        user_id = payload.get("sub")
        user = await user_service.get_user_by_id(db, user_id)
        if not user:
            _raise(status.HTTP_401_UNAUTHORIZED, "用户不存在或已删除", "unauthorized")
        if user.status != UserStatus.ACTIVE.value:
            _raise(status.HTTP_403_FORBIDDEN, f"用户状态为{user.status}，禁止刷新", "forbidden")
        new_tokens = auth_service.refresh_access_token(refresh_token, user)
        if not new_tokens:
            _raise(status.HTTP_400_BAD_REQUEST, "刷新令牌失败", "refresh_failed")
        access_token, new_refresh = new_tokens
        return _resp({"access_token": access_token, "refresh_token": new_refresh})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/auth/profile", summary="获取当前用户信息", response_model=dict)
async def profile(current_user: User = Depends(require_auth)):
    """返回当前用户的安全信息（过滤敏感字段）"""
    try:
        data = UserResponse(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            gender=current_user.gender,
            phone=current_user.phone,
            id_number=current_user.id_number,
            company=current_user.company,
            role=current_user.role,
            status=current_user.status,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            created_by=current_user.created_by,
            updated_by=current_user.updated_by,
        )
        return _resp(data.dict())
    except Exception as e:
        logger.error(f"获取用户Profile异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


# ============================= 用户管理 =============================
@router.post("/users/", summary="创建用户", response_model=dict)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """创建新用户（管理员权限）"""
    try:
        user = await user_service.create_user(db, payload, created_by=current_user.id)
        data = UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            gender=user.gender,
            phone=user.phone,
            id_number=user.id_number,
            company=user.company,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            updated_by=user.updated_by,
        )
        return _resp(data.dict())
    except HTTPException:
        raise
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "bad_request")
    except Exception as e:
        logger.error(f"创建用户异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/users/", summary="获取用户列表", response_model=dict)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    role: Optional[str] = Query(None, description="角色过滤"),
    status_: Optional[str] = Query(None, alias="status", description="状态过滤"),
    keyword: Optional[str] = Query(None, description="关键词"),
    order_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="排序方向(desc/asc)")
):
    """获取用户列表（管理员权限）"""
    try:
        items, total = await user_service.get_users(db, page, page_size, role, status_, keyword, order_by, order)
        data_items: List[dict] = []
        for u in items:
            data_items.append(UserResponse(
                id=u.id,
                name=u.name,
                email=u.email,
                gender=u.gender,
                phone=u.phone,
                id_number=u.id_number,
                company=u.company,
                role=u.role,
                status=u.status,
                created_at=u.created_at,
                updated_at=u.updated_at,
                created_by=u.created_by,
                updated_by=u.updated_by,
            ).dict())
        return _resp({"items": data_items, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        logger.error(f"获取用户列表异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.get("/users/{user_id}", summary="获取用户详情", response_model=dict)
async def get_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
    """获取用户详情（登录可访问）"""
    try:
        user = await user_service.get_user_by_id(db, user_id)
        if not user:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        data = UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            gender=user.gender,
            phone=user.phone,
            id_number=user.id_number,
            company=user.company,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            updated_by=user.updated_by,
        )
        return _resp(data.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户详情异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.put("/users/{user_id}", summary="更新用户信息", response_model=dict)
async def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """更新用户信息（管理员权限）"""
    try:
        user = await user_service.update_user(db, user_id, payload, updated_by=current_user.id)
        if not user:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        data = UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            gender=user.gender,
            phone=user.phone,
            id_number=user.id_number,
            company=user.company,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            updated_by=user.updated_by,
        )
        return _resp(data.dict())
    except HTTPException:
        raise
    except ValueError as ve:
        _raise(status.HTTP_400_BAD_REQUEST, str(ve), "bad_request")
    except Exception as e:
        logger.error(f"更新用户信息异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.delete("/users/{user_id}", summary="删除用户(软删除)", response_model=dict)
async def delete_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """软删除用户（管理员权限）"""
    try:
        ok = await user_service.delete_user(db, user_id, operator_id=current_user.id)
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        return _resp({"deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除用户异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")


@router.patch("/users/{user_id}/status", summary="修改用户状态", response_model=dict)
async def change_status(user_id: str, status_: str = Query(..., alias="status"), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """修改用户状态（管理员权限）"""
    try:
        if status_ not in [UserStatus.ACTIVE.value, UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value]:
            _raise(status.HTTP_400_BAD_REQUEST, "非法的用户状态", "bad_request")
        ok = await user_service.change_user_status(db, user_id, status_, operator_id=current_user.id)
        if not ok:
            _raise(status.HTTP_404_NOT_FOUND, "用户不存在", "not_found")
        return _resp({"user_id": user_id, "status": status_})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改用户状态异常: {e}")
        _raise(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误", "server_error")