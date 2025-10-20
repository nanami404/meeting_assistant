# Pydantic schemas package

# 导入所有Pydantic模型
from .user import *
from .meeting import *
from .transcription import *

# 定义公共接口
__all__ = [
    "UserCreate", "UserUpdate", "UserResponse", "UserBasicResponse", "UserLogin",
    "MeetingCreate", "MeetingResponse", "MeetingBase",
    "ParticipantCreate", "ParticipantResponse", "ParticipantBase",
    "PersonSignCreate", "PersonSignResponse", "PersonSignBase", "PersonSignUpdate",
    "TranscriptionCreate", "TranscriptionResponse", "TranscriptionBase"
]