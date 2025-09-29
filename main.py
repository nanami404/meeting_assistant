# 标准库
import sys
import os
import ssl
from loguru import logger
from pathlib import Path
from dotenv import load_dotenv

#第三方库
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 自定义类
from db.databases import engine, Base
from db.conn_manager import  ConnectionManager
from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
import router

# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()

load_dotenv()
# Create database tables
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Meeting Assistant API", version="1.0.0")

# 读取API配置（从环境变量）
API_HOST = os.getenv("API_HOST", "0.0.0.0")  # 默认0.0.0.0
API_PORT = int(os.getenv("API_PORT", 8000))  # 转换为整数，默认8000
DEBUG = os.getenv("DEBUG", "False").lower() == "true"  # 转换为布尔值，默认False

# 从 .env 中获取 CORS_ORIGINS，若未配置则用默认值
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
# 用英文逗号拆分字符串为列表（处理空字符串情况）
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    # In production, specify exact origins
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
针对加密协议新增代码
"""


def get_ssl_paths():
    """从.env读取并返回证书和密钥的路径（Path对象），若未配置或文件不存在则回退到HTTP模式"""
    cert_path_str = os.getenv("CERT_FILE_PATH", "")
    key_path_str = os.getenv("KEY_FILE_PATH", "")

    cert_path = Path(cert_path_str) if cert_path_str else None
    key_path = Path(key_path_str) if key_path_str else None

    # 未配置或至少有一个不存在时，回退到HTTP
    if not cert_path or not key_path:
        logger.warning("未配置证书路径，服务将以HTTP模式启动")
        return None, None
    if (cert_path and not cert_path.exists()) or (key_path and not key_path.exists()):
        logger.warning(f"证书或密钥文件不存在：{cert_path} 或 {key_path}，服务将以HTTP模式启动")
        return None, None

    return cert_path, key_path


full_cert_path, full_key_path = get_ssl_paths()

# 仅当证书配置有效时加载SSL上下文
ssl_context = None
if full_cert_path and full_key_path:
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=str(full_cert_path), keyfile=str(full_key_path))

DEFAULT_FORMAT = '{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] - {name}:{function}:{line} - {message}'
handlers = [
    {'level': 'DEBUG', 'format': DEFAULT_FORMAT, 'sink': sys.stdout},
    {'level': 'INFO', 'format': DEFAULT_FORMAT, 'sink': 'meeting-assistant-info.log'},
    {'level': 'ERROR', 'format': DEFAULT_FORMAT, 'sink': 'meeting-assistant-error.log'},
]
logger.configure(handlers=handlers)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = ConnectionManager()
app.include_router(router.meeting_manage)

if __name__ == "__main__":
    import uvicorn
    # 根据证书配置选择HTTPS或HTTP启动
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
