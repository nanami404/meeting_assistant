# 从新模块导入所有模型以保持向后兼容性
from models.database.enums import UserRole, UserStatus, GenderType
from models.database.user import User
from models.database.meeting import Meeting, Participant, Transcription, PersonSign
from models.database.message import Message, MessageRecipient

# 保持原有的导入，以确保其他模块的兼容性
from db.databases import Base

# 为了保持兼容性，重新导出所有类
__all__ = [
    'UserRole', 'UserStatus', 'GenderType',
    'User', 'PersonSign',
    'Meeting', 'Participant', 'Transcription',
    'Message', 'MessageRecipient',
    'Base'
]
