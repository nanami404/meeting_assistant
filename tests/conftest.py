import asyncio
import os
import sys
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 确保项目根路径在 sys.path 中
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from router import user_manage as user_router
from services.service_models import Base, User, UserRole, UserStatus
import bcrypt

# 使用本地SQLite文件，便于并发与跨线程访问
TEST_DB_URL = "sqlite:///./test_api.db"

# 创建测试数据库引擎与会话工厂
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建所有模型表
Base.metadata.create_all(bind=engine)

# 依赖覆盖：将生产环境的 MySQL 会话替换为测试SQLite会话
async def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def app() -> FastAPI:
    app = FastAPI()
    # 挂载用户与认证路由（包含 /api 前缀）
    app.include_router(user_router.router)
    # 覆盖依赖
    app.dependency_overrides[user_router.get_db] = _override_get_db
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function")
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def seed_admin(db_session):
    # 种子管理员用户
    password = "AdminPass1!"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    admin = User(
        name="Admin",
        user_name="admin_user",
        email="admin@example.com",
        phone="13800000000",
        company="IT",
        user_role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
        password_hash=password_hash
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return {"id": admin.id, "username": admin.user_name, "password": password}
