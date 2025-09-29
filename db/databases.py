#-*- coding: utf-8 -*-
# 标准库
import os
from urllib.parse import quote_plus
from typing import AsyncGenerator
from typing import Generator

# 第三方库
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session  # 确保导入Session
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# Database configuration from environment
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "nokia_cs")
DB_PASSWORD_RAW = os.getenv("MYSQL_PASSWORD", "Siryuan#525@614")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "rjgf_meeting")

# 关键：对密码中的特殊字符进行URL编码（#→%23，@→%40）
MYSQL_PASSWORD = quote_plus(DB_PASSWORD_RAW)
# 构建MySQL连接URL

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

DATABASE_URL2 = f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    # Set to False in production
    echo=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get database session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 2. 创建异步引擎（管理数据库连接池，生产环境需调整池参数）
async_engine = create_async_engine(
    DATABASE_URL2,
    # 生产环境关闭 SQL 日志打印，开发环境可设为 True
    echo=False,
    pool_size=30,  # 连接池大小
    max_overflow=20,  # 超出池大小的临时连接数
    pool_recycle=3600,  # 连接超时回收（秒）
    pool_pre_ping=True  # 连接前检查有效性，避免无效连接
)

# 3. 创建异步会话工厂（每次调用生成新会话，非线程安全，需依赖注入隔离）
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,  # 强制使用异步会话类
    autoflush=False,     # 关闭自动刷新（避免未提交的修改影响查询）
    # 关闭自动提交（需手动 await db.commit()）
    autocommit=False,
    expire_on_commit=True  # 提交后不失效对象，便于后续访问属性
)






@asynccontextmanager
async def safe_async_db()-> AsyncGenerator[AsyncSession, None]:
    """
    安全的异步数据库会话管理器
    """
    async_session = AsyncSessionLocal()
    try:
        yield async_session
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        raise e
    finally:
        # 检查会话状态后再关闭
        if not async_session.in_transaction():
            await async_session.close()
        else:
            # 如果仍在事务中，先回滚再关闭
            try:
                await async_session.rollback()
                await async_session.close()
            except Exception:
                # 如果关闭失败，忽略错误以避免循环异常
                pass

# 修改依赖项
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with safe_async_db() as db:
        yield db
