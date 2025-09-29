from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import List, Optional


class ParticipantBase(BaseModel):
    name: str
    email: EmailStr
    role: str = "participant"
    is_required: bool = True


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantResponse(ParticipantBase):
    id: str
    meeting_id: str
    attendance_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    date_time: datetime
    location: Optional[str] = None
    duration_minutes: int = 60
    agenda: Optional[str] = None


class MeetingCreate(MeetingBase):
    participants: List[ParticipantCreate] = []


class MeetingResponse(MeetingBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    participants: List[ParticipantResponse] = []

    class Config:
        from_attributes = True


class TranscriptionBase(BaseModel):
    """
    转录文本基础模型

    Attributes:
        speaker_id: 说话者唯一标识，最大长度50字符
        speaker_name: 说话者姓名，可选，最大长度100字符
        text: 转录文本内容，非空
        confidence_score: 置信度分数，范围0-100，默认80
    """
    speaker_id: str = Field(..., max_length=50)
    speaker_name: Optional[str] = Field(None, max_length=100)
    text: str = Field(..., min_length=1)
    confidence_score: int = Field(default=80, ge=0, le=100)

    @validator('confidence_score')
    def validate_confidence(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('置信度分数必须在0到100之间')
        return v

class TranscriptionCreate(TranscriptionBase):
    meeting_id: str
    timestamp: Optional[datetime] = None


class TranscriptionResponse(TranscriptionBase):
    """转录文本响应模型

    Attributes:
        id: 转录记录唯一标识
        meeting_id: 关联的会议ID
        timestamp: 转录时间戳，必须为过去时间
        is_action_item: 是否为行动项，默认False
        is_decision: 是否为决策项，默认False
    """
    id: str = Field(..., description="转录记录唯一标识")
    meeting_id: str = Field(..., description="关联的会议ID")
    timestamp: datetime = Field(
        ...,
        description="转录时间戳",
        # 确保时间戳是过去时间
        lt=datetime.now(),
    )
    is_action_item: bool = Field(
        default=False,
        description="是否为行动项",
    )
    is_decision: bool = Field(
        default=False,
        description="是否为决策项",
    )

    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    type: str  # "audio_chunk", "text_message", "transcription"
    meeting_id: str
    speaker_id: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded audio
    text: Optional[str] = None
    timestamp: Optional[datetime] = None