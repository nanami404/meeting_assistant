# 标准库
import base64
import os
import json
from typing import List, Generator
from datetime import datetime
from typing import List
from typing import Generator
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
import pytz
from loguru import logger
from httpx import AsyncClient
from builtins import anext
from typing import Any, Dict,Optional
import time

#第三方库
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from pydub import AudioSegment
from pydantic import BaseModel
import json
import asyncio
import websockets  # 新增：异步 WebSocket 客户端库
from websockets.exceptions import ConnectionClosed


from fastapi import  UploadFile, File
from fastapi import APIRouter,HTTPException, Depends
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

#自定义库
from db.databases import DatabaseConfig, DatabaseSessionManager
from db.conn_manager import ConnectionManager
from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from services.auth_dependencies import require_auth, require_admin

from services.service_models import User, UserStatus, UserRole
from schemas import MeetingCreate, MeetingResponse, TranscriptionCreate, PersonSignResponse,ParticipantCreate

# 定义 Token 验证方案（Bearer Token）
security = HTTPBearer()

router = APIRouter(prefix="/api/meetings", tags=["Mettings"])
# 获取东八区当前时间
tz = pytz.timezone("Asia/Shanghai")

# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()
manager = ConnectionManager()

MEETING_NOT_FOUND_DETAIL = "Meeting not found"

# 对外暴露的依赖注入函数
db_config = DatabaseConfig()
db_manager = DatabaseSessionManager(db_config)
get_db = db_manager.get_sync_session  # 同步会话依赖
get_async_db = db_manager.get_async_session  #

@router.get("/open")
async def root()->dict[str, str]:
    return {"message": "Meeting Assistant API is running"}

# Meeting management endpoints
@router.post("/", response_model=MeetingResponse)
async def create_meeting(meeting: MeetingCreate, current_user: User = Depends(require_auth), db: Session = Depends(get_db)) ->MeetingResponse:
    """创建新会议
    Args:
        meeting (MeetingCreate): 会议创建数据，已通过Pydantic验证
        db (Session): 数据库会话
    Returns:
        MeetingResponse: 新创建的会议对象
    Raises:
        HTTPException: 400 - 输入数据无效
        HTTPException: 500 - 服务器内部错误
    """
    user_id = str(current_user.id)
    try:
        # 开始数据库事务
        db.begin()

        # 创建会议记录
        new_meeting = await meeting_service.create_meeting(db, meeting,user_id)

        # 提交事务
        db.commit()

        # 记录成功日志
        logger.info(f"成功创建会议: {new_meeting.id}")

        return new_meeting

    except ValueError as e:
        # 回滚事务
        db.rollback()
        # 记录警告日志
        logger.warning(f"无效的会议数据: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"无效的会议数据: {str(e)}"
        )

    except Exception as e:
        # 回滚事务
        db.rollback()
        # 记录错误日志
        logger.error(f"创建会议失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="服务器内部错误，创建会议失败"
        )

@router.get("/user/", response_model=List[MeetingResponse])
async def get_meetings(current_user: User = Depends(require_auth), db: Session = Depends(get_db))-> list[MeetingResponse]:
    """Get all meetings"""
    user_id = str(current_user.id)
    try:
        # 验证 current_user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user ID")

        # 获取会议列表
        meetings = await meeting_service.get_meetings(db, user_id)

        # 记录成功日志
        logger.info(f"Successfully retrieved meetings for user: {user_id}")

        return meetings
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meetings for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{meeting_id}/user/", response_model=MeetingResponse)
async def get_meeting(meeting_id: str, current_user: User = Depends(require_auth), db: Session = Depends(get_db)) -> MeetingResponse:
    """Get a specific meeting with user validation"""
    user_id = str(current_user.id)
    try:
        # 验证 user_id 是否合法
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user ID")

        # 验证 meeting_id 是否合法
        if not meeting_id or not isinstance(meeting_id, str):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")

        # 获取会议信息并验证用户权限
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        # 记录成功日志
        logger.info(f"Successfully retrieved meeting {meeting_id} for user: {user_id}")

        return meeting
    except HTTPException:
        raise
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to retrieve meeting {meeting_id} for user: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{meeting_id}/user/", response_model=MeetingResponse)
def update_meeting(meeting_id: str,  meeting: MeetingCreate,current_user: User = Depends(require_auth), db: Session = Depends(get_db))-> MeetingResponse:
    """Update a meeting"""
    user_id = str(current_user.id)
    updated_meeting = meeting_service.update_meeting(db, meeting_id, meeting,user_id)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return updated_meeting

@router.delete("/{meeting_id}/user/")
async def delete_meeting(meeting_id: str, current_user: User = Depends(require_auth), db: Session = Depends(get_db))-> dict[str, str]:
    """Delete a meeting"""
    user_id = str(current_user.id)
    success = await meeting_service.delete_meeting(db, meeting_id,user_id)
    if not success:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return {"message": "Meeting deleted successfully"}

# Document generation endpoints
@router.post("/{meeting_id}/generate-notification")
async def generate_notification(meeting_id: str, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Generate meeting notification document
        生成会议通知文档
    """
    user_id = str(current_user.id)
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        doc_path = await document_service.generate_notification(meeting)
        return {"document_path": doc_path, "message": "Notification generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{meeting_id}/generate-minutes")
async def generate_minutes(meeting_id: str,current_user: User = Depends(require_auth),  db: Session = Depends(get_db)):
    """Generate meeting minutes document
       生成会议纪要文档
    """
    user_id = str(current_user.id)
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id, user_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
        doc_path = await document_service.generate_minutes(meeting, transcriptions)
        return {"document_path": doc_path, "message": "Meeting minutes generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{meeting_id}/send-notification")
async def send_notification(meeting_id: str, db: Session = Depends(get_db))-> dict[str, str]:
    """
    Send meeting notification emails
    发送会议通知邮件
    """
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        success = await email_service.send_meeting_notification(meeting)
        if success:
            return {"message": "Notification emails sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send emails")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



# 复用 AsyncClient（避免每次调用创建新连接，提升性能）
async_client = AsyncClient(timeout=5)
# Token 验证（你的服务对客户端的验证）
security = HTTPBearer()

# 外部 wss 地址（目标服务）
EXTERNAL_WSS_URL = "wss://ai.csg.cn/aihear-50-249/app/hisee/websocket/storage/57fb5931-f776-4b18-be59-a137f706a949/appid=tainsureAssistant,uid=555fd741-5023-4ea8-84ff-b702a087137b,ack=1,pk_on=1"

EXTERNAL_ACCESS_TOKEN = "6c0a12ed344841859e486e46fbe1b881"


# 消息模型
class TextMessage(BaseModel):
    type: str
    content: str
    sender: str = "anonymous"


# 后台任务：连接外部 wss 服务并接收消息
async def connect_external_wss(max_retries: Optional[int] = None, retry_delay: int = 5):
    """
    连接外部 wss 服务，接收消息并广播给所有客户端
    """
    retry_count = 0

    while max_retries is None or retry_count < max_retries:
        try:
            logger.info(f"🔄 尝试连接外部 WSS 服务 (第 {retry_count + 1} 次)...")

            # 连接外部 wss 服务
            async with websockets.connect(
                    EXTERNAL_WSS_URL,
                    additional_headers=[
                        ("access-token", EXTERNAL_ACCESS_TOKEN),
                        ("User-Agent", "WebSocket-Client/1.0")
                    ],
                    ping_interval=10,  # 更频繁的心跳
                    ping_timeout=5,
                    close_timeout=10,
                    max_size=None,
                    open_timeout=30
            ) as external_ws:
                logger.info(f"✅ 已连接到外部 wss 服务")
                retry_count = 0

                # 连接建立后立即发送初始消息
                await send_initial_handshake(external_ws)

                # 创建心跳任务
                heartbeat_task = asyncio.create_task(
                    send_heartbeat(external_ws)
                )

                try:
                    # 监听消息直到连接关闭
                    async for message in external_ws:
                        try:
                            logger.info(f"📨 从外部 wss 收到消息：{message}")

                            # 处理消息
                            processed_message = await process_external_message(message)

                            # 转发给所有客户端
                            if manager.connections:
                                await manager.broadcast({
                                    "type": "external_message",
                                    "data": processed_message,
                                    "timestamp": time.time()
                                })
                                logger.info("✅ 消息已广播给所有客户端")

                            # 发送确认消息（如果服务端需要 ack）
                            await send_acknowledgment(external_ws, message)

                        except Exception as msg_error:
                            logger.error(f"❌ 处理消息时出错：{msg_error}", exc_info=True)

                except ConnectionClosed as e:
                    logger.warning(f"🔌 连接关闭：code={e.code}, reason={e.reason}")
                    if e.code == 1013:
                        logger.info("💡 服务端要求重连")
                finally:
                    # 取消心跳任务
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

        except ConnectionClosed as e:
            logger.warning(f"连接关闭：{e.code} - {e.reason}，{retry_delay}秒后重试...")

        except asyncio.TimeoutError:
            logger.error(f"连接超时，{retry_delay}秒后重试...")

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket 异常：{e}，{retry_delay}秒后重试...")

        except asyncio.CancelledError:
            logger.info("外部 wss 连接任务被取消")
            raise

        except Exception as e:
            logger.error(f"外部 wss 连接错误：{e}，{retry_delay}秒后重试...", exc_info=True)

        # 重试逻辑
        retry_count += 1
        if max_retries and retry_count >= max_retries:
            logger.error(f"🛑 达到最大重试次数 {max_retries}，停止连接外部 wss 服务")
            break

        # 递增延迟
        actual_delay = min(retry_delay * retry_count, 30)
        logger.info(f"⏳ 第 {retry_count} 次重试，等待 {actual_delay} 秒...")
        await asyncio.sleep(actual_delay)


async def send_initial_handshake(websocket):
    """发送初始握手消息"""
    try:
        # 根据 URL 参数构造初始消息
        init_message = {
            "type": "init",
            "appid": "tainsureAssistant",
            "uid": "555fd741-5023-4ea8-84ff-b702a087137b",
            "ack": 1,
            "pk_on": 1,
            "timestamp": int(time.time()),
            "action": "start"  # 可能需要开始动作
        }

        await websocket.send(json.dumps(init_message))
        logger.info("📤 已发送初始握手消息")

    except Exception as e:
        logger.error(f"发送初始握手消息失败: {e}")


async def send_heartbeat(websocket):
    """发送心跳保持连接"""
    try:
        while True:
            await asyncio.sleep(8)  # 每8秒发送一次心跳

            heartbeat_msg = {
                "type": "heartbeat",
                "timestamp": int(time.time())
            }
            await websocket.send(json.dumps(heartbeat_msg))
            logger.debug("💓 心跳已发送")

    except asyncio.CancelledError:
        logger.debug("心跳任务被取消")
    except Exception as e:
        logger.error(f"发送心跳失败: {e}")


async def send_acknowledgment(websocket, received_message):
    """发送消息确认（如果需要）"""
    try:
        # 如果服务端需要确认，发送 ack
        ack_message = {
            "type": "ack",
            "timestamp": int(time.time()),
            "received": True
        }
        await websocket.send(json.dumps(ack_message))
        logger.debug("✅ 已发送消息确认")

    except Exception as e:
        logger.debug(f"发送确认失败: {e}")


async def process_external_message(message):
    """处理外部消息"""
    try:
        parsed_message = json.loads(message)
        # 可以根据消息类型进行不同的处理
        message_type = parsed_message.get("type", "unknown")

        if message_type == "transcript":
            # 处理转写结果
            return f"转写结果: {parsed_message.get('text', '')}"
        elif message_type == "status":
            # 处理状态消息
            return f"状态更新: {parsed_message.get('status', '')}"
        else:
            return json.dumps(parsed_message, ensure_ascii=False)

    except json.JSONDecodeError:
        return message

# 使用示例
async def start_external_connection():
    """启动外部连接任务"""
    task = asyncio.create_task(
        connect_external_wss(
            max_retries=10,  # 最多重试10次
            retry_delay=5  # 每次重试间隔5秒
        )
    )
    return task

# 优雅关闭函数
async def stop_external_connection(task):
    """停止外部连接任务"""
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("外部 wss 连接任务已取消")

# 你的 WebSocket 端点（供客户端连接）
@router.websocket("/ws/text/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket 端点，处理客户端连接和消息转发
    """

    # 将客户端添加到连接管理器
    await manager.connect(websocket,meeting_id)

    # 启动外部 WSS 连接（如果尚未启动）
    external_task = None
    if not hasattr(manager, 'external_task') or manager.external_task is None or manager.external_task.done():
        external_task = await start_external_connection()
        manager.external_task = external_task  # 保存任务引用以便管理
        logger.info("外部 WSS 连接已启动")

    try:
        while True:
            # 接收客户端消息
            client_data = await websocket.receive_text()
            logger.info(f"收到客户端消息：{client_data}")

            # 可选：向客户端发送确认消息
            await websocket.send_json({
                "type": "acknowledge",
                "message": "消息已接收",
                "timestamp": asyncio.get_event_loop().time()
            })

    except WebSocketDisconnect:
        # 客户端主动断开连接
        logger.info(f"客户端断开连接：{websocket.client}")
        manager.disconnect(websocket, meeting_id)
        # 如果这是最后一个客户端连接，可以考虑停止外部连接
        if not manager.connections:
            logger.info("所有客户端已断开，外部连接保持运行")

    except Exception as e:
        # 处理其他异常
        logger.error(f"WebSocket 连接错误：{str(e)}", exc_info=True)

        try:
            # 尝试优雅关闭连接
            await websocket.close(code=1011, reason=f"服务端错误：{str(e)}")
        except Exception as close_error:
            logger.error(f"关闭 WebSocket 时出错：{close_error}")
        # 从连接管理器中移除
        manager.disconnect(websocket)


# Upload audio file for transcription
@router.post("/{meeting_id}/upload-audio")
async def upload_audio(
        meeting_id: str,
        audio_file: UploadFile = File(...),
        speaker_id: str = "unknown",
        db: Session = Depends(get_db)
):
    """Upload audio file for transcription"""
    try:
        # Save uploaded file temporarily
        # 校验音频格式,mpeg 对应 MP3
        allowed_formats = {"audio/wav", "audio/mpeg"}
        if audio_file.content_type not in allowed_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format. Allowed formats: WAV, MP3"
            )
        # 手动指定 ffmpeg 和 ffprobe 路径（替换为你的实际路径）
        ffmpeg_path = "D:/ffmpeg/bin/ffmpeg.exe"
        ffprobe_path = "D:/ffmpeg/bin/ffprobe.exe"
        # 2. 验证路径是否存在（可选，但能快速排查错误）
        if not os.path.exists(ffprobe_path):
            raise FileNotFoundError(f"ffprobe 不存在于该路径：{ffprobe_path}")

        # 告诉 pydub 工具路径
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffprobe_path

        file_path = f"temp/{audio_file.filename}"
        print("file_path------------------",file_path)
        with open(file_path, "wb") as buffer:
            content = await audio_file.read()
            buffer.write(content)
        # 读取上传的音频
        audio = AudioSegment.from_file(file_path)
        # 转换为 16kHz 单声道 WAV（语音识别常用格式）

        # 获取原始文件名和扩展名
        original_filename = audio_file.filename
        filename_stem = Path(original_filename).stem  # 获取不带扩展名的文件名部分
        # 构建转换后的文件路径
        converted_path = f"temp/converted_{filename_stem}.wav"
        audio = audio.set_frame_rate(16000).set_channels(1)  # 16kHz 单声道
        audio.export(converted_path, format="wav")
        # 后续用 converted_path 进行转录
        transcription = await speech_service.transcribe_audio_file(converted_path, speaker_id)

        # Transcribe audio
        #transcription = await speech_service.transcribe_audio_file(file_path, speaker_id)

        if transcription:
            # Save transcription to database
            transcription_record = TranscriptionCreate(
                meeting_id=meeting_id,
                speaker_id=speaker_id,
                text=transcription,
                timestamp=datetime.now(timezone.utc).isoformat() + "Z"
            )
            await meeting_service.save_transcription(db, transcription_record)

            return {"transcription": transcription, "message": "Audio transcribed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Get meeting transcriptions
@router.get("/{meeting_id}/transcriptions")
async def get_meeting_transcriptions(meeting_id: str, db: Session = Depends(get_db)):
    """Get all transcriptions for a meeting"""
    transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
    return transcriptions


