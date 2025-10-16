# 标准库
import base64
import os
import json
from typing import List
from typing import Generator
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
import pytz
from loguru import logger
from httpx import AsyncClient

#第三方库
from fastapi import  WebSocket, WebSocketDisconnect, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from pydub import AudioSegment
from fastapi import APIRouter,HTTPException, Depends

#自定义库
from services.meeting_service import MeetingService
from services.document_service import DocumentService
from services.speech_service import SpeechService
from services.email_service import EmailService
from schemas import MeetingCreate, MeetingResponse, TranscriptionCreate
from db.conn_manager import ConnectionManager
from db.databases import get_async_db

router = APIRouter()
# 获取东八区当前时间
tz = pytz.timezone("Asia/Shanghai")

# Services
meeting_service = MeetingService()
document_service = DocumentService()
speech_service = SpeechService()
email_service = EmailService()

manager = ConnectionManager()

MEETING_NOT_FOUND_DETAIL = "Meeting not found"


# Database configuration from environment
MYSQL_HOST = os.getenv("MYSQL_HOST", "118.89.93.181")
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

def get_db()-> Generator[Session, None, None]:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get("/")
async def root()->dict[str, str]:
    return {"message": "Meeting Assistant API is running"}

# Meeting management endpoints
@router.post("/api/meetings", response_model=MeetingResponse)
async def create_meeting(meeting: MeetingCreate, db: Session = Depends(get_db)) ->MeetingResponse:
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
    try:
        # 开始数据库事务
        db.begin()

        # 创建会议记录
        new_meeting = await meeting_service.create_meeting(db, meeting)

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

@router.get("/api/meetings", response_model=List[MeetingResponse])
async def get_meetings(db: Session = Depends(get_db))-> list[MeetingResponse]:
    """Get all meetings"""
    return await meeting_service.get_meetings(db)


@router.get("/api/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: str, db: Session = Depends(get_db))-> MeetingResponse:
    """Get a specific meeting"""
    meeting = await meeting_service.get_meeting(db, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return meeting


@router.put("/api/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(meeting_id: str, meeting: MeetingCreate, db: Session = Depends(get_db))-> MeetingResponse:
    """Update a meeting"""
    updated_meeting = await meeting_service.update_meeting(db, meeting_id, meeting)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return updated_meeting


@router.delete("/api/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str, db: Session = Depends(get_db))-> dict[str, str]:
    """Delete a meeting"""
    success = await meeting_service.delete_meeting(db, meeting_id)
    if not success:
        raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)
    return {"message": "Meeting deleted successfully"}


# Document generation endpoints
@router.post("/api/meetings/{meeting_id}/generate-notification")
async def generate_notification(meeting_id: str, db: Session = Depends(get_db)):
    """Generate meeting notification document
        生成会议通知文档
    """
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        doc_path = await document_service.generate_notification(meeting)
        return {"document_path": doc_path, "message": "Notification generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/meetings/{meeting_id}/generate-minutes")
async def generate_minutes(meeting_id: str, db: Session = Depends(get_db)):
    """Generate meeting minutes document
       生成会议纪要文档
    """
    try:
        meeting = await meeting_service.get_meeting(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
        doc_path = await document_service.generate_minutes(meeting, transcriptions)
        return {"document_path": doc_path, "message": "Meeting minutes generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/meetings/{meeting_id}/send-notification")
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



EXTERNAL_API_URL = "ws://192.168.18.246:10095"

# 复用 AsyncClient（避免每次调用创建新连接，提升性能）
async_client = AsyncClient(timeout=5)



@router.websocket("/ws/{meeting_id}")
#@router.websocket("wss://ai.csg.cn/aihear-50-249/app/hisee/websocket/storage/57fb5931-f776-4b18-be59-a137f706a949/appid=tainsureAssistant,uid=555fd741-5023-4ea8-84ff-b702a087137b,ack=1,pk_on=1")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """
        await websocket.accept()
    # 获取请求头中的鉴权信息
    token = websocket.headers.get("access-token")
    if not token:
        await websocket.close(code=1008, reason="Missing access token")
        return

    :param websocket:
    :param meeting_id:
    :return:
    """

    await manager.connect(websocket, meeting_id)
    # 音频块累积缓冲区（解决单块过短问题，例如累积1秒再转译）
    audio_buffer = b""  # 二进制缓冲区
    # 16kHz * 1秒 * 16bit（2字节/样本）≈32000字节
    buffer_threshold = 16000 * 1 * 2

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "audio_chunk":

                # 1. 提取并解码音频数据（关键修复：Base64转二进制）
                audio_base64 = message_data.get("audio_data")
                speaker_id = message_data.get("speaker_id", "unknown")

                if not audio_base64:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Missing audio_data in request"
                    }))
                    continue
                try:
                    # Base64解码为二进制音频数据
                    audio_bytes = base64.b64decode(audio_base64)
                except ValueError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid Base64 encoding for audio_data"
                    }))
                    continue

                # 2. 累积音频块（解决单块过短问题）
                audio_buffer += audio_bytes
                # 达到阈值（如2秒）再转译
                if len(audio_buffer) >= buffer_threshold:
                    try:
                        # 3. 调用转译服务（确保服务支持二进制PCM输入）
                        transcription = await speech_service.transcribe_audio(
                            audio_buffer,  # 传入二进制数据
                            speaker_id
                        )

                        if transcription:
                            # 4. 异步保存到数据库（使用异步会话）
                            async_db: AsyncSession = await anext(get_async_db())  # 异步获取会话
                            transcription_record = TranscriptionCreate(
                                meeting_id=meeting_id,
                                speaker_id=speaker_id,
                                text=transcription,
                                timestamp = datetime.now(tz)
                            )
                            await meeting_service.save_transcription(async_db, transcription_record)
                            await async_db.commit()  # 异步提交

                            # 5. 广播转译结果
                            response = {
                                "type": "transcription",
                                "meeting_id": meeting_id,
                                "speaker_id": speaker_id,
                                "text": transcription,
                                "timestamp": datetime.utcnow().isoformat() + "Z"  # 带时区标识
                            }
                            await manager.broadcast(json.dumps(response), meeting_id)

                        # 清空缓冲区（或保留部分用于连续识别，根据需求调整）
                        audio_buffer = b""

                    except Exception as e:
                        # 捕获转译过程中的错误并反馈
                        error_msg = f"Transcription failed: {str(e)}"
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": error_msg
                        }))
                        print(f"转译错误：{error_msg}")  # 输出日志便于排查
                        audio_buffer = b""  # 出错后清空缓冲区

            elif message_data.get("type") == "text_message":
                # 文本消息处理（保持原有逻辑，优化数据库调用）
                speaker_id = message_data.get("speaker_id", "unknown")
                text = message_data.get("text", "")
                print("当前文本是", text)

                if text:
                    try:
                        async_db: AsyncSession = await anext(get_async_db())
                        transcription_record = TranscriptionCreate(
                            meeting_id=meeting_id,
                            speaker_id=speaker_id,
                            text=text,
                            timestamp=datetime.utcnow()
                        )
                        await meeting_service.save_transcription(async_db, transcription_record)
                        await async_db.commit()

                        response = {
                            "type": "transcription",
                            "meeting_id": meeting_id,
                            "speaker_id": speaker_id,
                            "text": text,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                        await manager.broadcast(json.dumps(response), meeting_id)
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Failed to save text message: {str(e)}"
                        }))

    except WebSocketDisconnect:
        manager.disconnect(websocket, meeting_id)
    except Exception as e:
        # 捕获全局异常，避免WebSocket意外关闭
        print(f"WebSocket意外错误：{str(e)}")
        await websocket.close(code=1011, reason=f"Server error: {str(e)}")

# Upload audio file for transcription
@router.post("/api/meetings/{meeting_id}/upload-audio")
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
@router.get("/api/meetings/{meeting_id}/transcriptions")
async def get_meeting_transcriptions(meeting_id: str, db: Session = Depends(get_db)):
    """Get all transcriptions for a meeting"""
    transcriptions = await meeting_service.get_meeting_transcriptions(db, meeting_id)
    return transcriptions


