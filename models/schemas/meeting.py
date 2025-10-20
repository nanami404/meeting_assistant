from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import List, Optional


class ParticipantBase(BaseModel):
    name: str
    email: EmailStr
    user_role: str = "participant"
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


# 定义人员签到数据模型
class PersonSignCreate(BaseModel):
    name: str
    user_code: Optional[str] = None
    meeting_id: str
    is_signed: bool
    is_on_leave: bool


class PersonSignResponse(BaseModel):
    id: int
    name: str
    is_signed: bool
    is_on_leave: bool