# 标准库
import sys
import os
import ssl
from loguru import logger
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# 第三方库
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

# 自定义类
from db.databases import DatabaseConfig, DatabaseSessionManager
from db.conn_manager import ConnectionManager
from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
import router
from router import user_manage as user_router

# 对外暴露的依赖注入函数
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖
get_async_db = db_manager.get_async_session

# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()

load_dotenv()

Base = declarative_base()
engine = create_engine(
    db_config.sync_url,
    echo=True  # Set to False in production
)
# Create database tables
Base.metadata.create_all(bind=engine)


# ✅ 新增：Lifespan 事件处理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭事件"""
    # ===== 启动逻辑 =====
    logger.info("Meeting Assistant API 正在启动...")
    # 可在此处添加初始化逻辑，如连接池预热、缓存加载等
    logger.success("Meeting Assistant API 启动完成")
    
    yield  # 应用运行期间
    
    # ===== 关闭逻辑 =====
    logger.info("Meeting Assistant API 正在关闭...")
    # 可在此处添加清理逻辑，如关闭数据库连接、释放资源等
    logger.info("Meeting Assistant API 已关闭")


# 创建 FastAPI 应用，传入 lifespan
app = FastAPI(title="Meeting Assistant API", version="1.0.0", lifespan=lifespan)  # 👈 关键：传入 lifespan


# 读取API配置（从环境变量）
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# CORS 配置
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_ssl_paths():
    """从.env读取并返回证书和密钥的路径（Path对象），若未配置或文件不存在则回退到HTTP模式"""
    cert_path_str = os.getenv("CERT_FILE_PATH", "")
    key_path_str = os.getenv("KEY_FILE_PATH", "")

    cert_path = Path(cert_path_str) if cert_path_str else None
    key_path = Path(key_path_str) if key_path_str else None

    if not cert_path or not key_path:
        logger.warning("未配置证书路径，服务将以HTTP模式启动")
        return None, None
    if (cert_path and not cert_path.exists()) or (key_path and not key_path.exists()):
        logger.warning(f"证书或密钥文件不存在：{cert_path} 或 {key_path}，服务将以HTTP模式启动")
        return None, None

    return cert_path, key_path


full_cert_path, full_key_path = get_ssl_paths()

ssl_context = None
if full_cert_path and full_key_path:
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=str(full_cert_path), keyfile=str(full_key_path))


# 日志配置
DEFAULT_FORMAT = '{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] - {name}:{function}:{line} - {message}'
handlers = [
    {'level': 'DEBUG', 'format': DEFAULT_FORMAT, 'sink': sys.stdout},
    {'level': 'INFO', 'format': DEFAULT_FORMAT, 'sink': 'meeting-assistant-info.log'},
    {'level': 'ERROR', 'format': DEFAULT_FORMAT, 'sink': 'meeting-assistant-error.log'},
]
logger.configure(handlers=handlers)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 路由
manager = ConnectionManager()
app.include_router(router.user_manage)
app.include_router(router.meeting_manage)
app.include_router(router.attendance_manage)
app.include_router(router.message_manage)

# 健康检查
from router.health_check import router as health_router
app.include_router(health_router)


# 启动入口
if __name__ == "__main__":
    import uvicorn
    if full_cert_path and full_key_path:
        logger.info(f"以HTTPS模式启动，证书: {full_cert_path}, 密钥: {full_key_path}")
        uvicorn.run(
            "main:app",
            host=API_HOST,
            port=API_PORT,
            ssl_certfile=str(full_cert_path),
            ssl_keyfile=str(full_key_path)
        )
    else:
        logger.info("未检测到有效证书，使用HTTP模式启动")
        uvicorn.run(
            "main:app",
            host=API_HOST,
            port=API_PORT
        )