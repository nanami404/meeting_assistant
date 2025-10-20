# 从新模块导入所有模型以保持向后兼容性
from models.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserResponse, 
    UserBasicResponse, UserLogin
)
from models.schemas.meeting import (
    ParticipantBase, ParticipantCreate, ParticipantResponse,
    MeetingBase, MeetingCreate, MeetingResponse,
    PersonSignCreate, PersonSignResponse
)
from models.schemas.transcription import (
    TranscriptionBase, TranscriptionCreate, TranscriptionResponse
)

# 为了保持兼容性，重新导出所有类
__all__ = [
    # 用户相关模型
    'UserBase', 'UserCreate', 'UserUpdate', 'UserResponse', 
    'UserBasicResponse', 'UserLogin',
    
    # 会议相关模型
    'ParticipantBase', 'ParticipantCreate', 'ParticipantResponse',
    'MeetingBase', 'MeetingCreate', 'MeetingResponse',
    'PersonSignCreate', 'PersonSignResponse',
    
    # 转录相关模型
    'TranscriptionBase', 'TranscriptionCreate', 'TranscriptionResponse'
    
]