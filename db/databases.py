# -*- coding: utf-8 -*-
import os
from urllib.parse import quote_plus
from typing import Generator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,  # 👈 关键：使用 async_sessionmaker
)
from sqlalchemy.orm import sessionmaker, Session

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础模型类（所有数据库模型继承此类）
Base = declarative_base()


class DatabaseConfig:
    """数据库配置类，负责解析环境变量并生成连接URL"""

    def __init__(self):
        # 从环境变量读取配置，提供默认值
        self.mysql_host = os.getenv("MYSQL_HOST", "118.89.93.181")
        self.mysql_port = os.getenv("MYSQL_PORT", "3306")
        self.mysql_user = os.getenv("MYSQL_USER", "nokia_cs")
        self.db_password_raw = os.getenv("MYSQL_PASSWORD", "Siryuan#525@614")
        self.mysql_database = os.getenv("MYSQL_DATABASE", "rjgf_meeting")

        # 对密码中的特殊字符进行URL编码（如#、@等）
        self.mysql_password = quote_plus(self.db_password_raw)

        # 生成同步/异步连接URL
        self.sync_url = f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        self.async_url = f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"


class DatabaseSessionManager:
    """数据库会话管理器，封装同步/异步引擎与会话创建逻辑"""

    def __init__(self, config: DatabaseConfig):
        self.config = config

        # ========== 同步引擎与会话工厂 ==========
        self.sync_engine = create_engine(
            self.config.sync_url,
            echo=True,  # 开发环境打印SQL日志，生产环境设为False
            pool_pre_ping=True  # 连接有效性检查
        )
        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            autocommit=False,
            autoflush=False
        )

        # ========== 异步引擎与会话工厂（使用 async_sessionmaker）==========
        self.async_engine = create_async_engine(
            self.config.async_url,
            echo=True,
            pool_size=30,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        self.async_session_factory = async_sessionmaker(
            bind=self.async_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=True
        )

    # ------------------------------ 同步会话管理 ------------------------------
    def get_sync_session(self) -> Generator[Session, None, None]:
        """同步会话依赖注入生成器（用于非异步路由）"""
        session = self.sync_session_factory()
        try:
            yield session
        finally:
            session.close()

    # ------------------------------ 异步会话管理 ------------------------------
    @asynccontextmanager
    async def safe_async_session(self) -> AsyncIterator[AsyncSession]:
        """安全的异步会话上下文管理器，自动处理提交/回滚/关闭"""
        session: AsyncSession = self.async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_async_session(self) -> AsyncIterator[AsyncSession]:
        """异步会话依赖注入生成器（用于异步路由）"""
        async with self.safe_async_session() as session:
            yield session


# 单例实例化（项目中全局使用一个管理器）
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)

# 对外暴露的依赖注入函数（与FastAPI路由配合使用）
get_db = db_manager.get_sync_session      # 同步会话依赖
get_async_db = db_manager.get_async_session  # 异步会话依赖