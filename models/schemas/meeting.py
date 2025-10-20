from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import List, Optional


class ParticipantBase(BaseModel):
    name: str = Field(..., max_length=50)
    email: EmailStr = Field(..., max_length=100)
    user_role: str = "participant"
    is_required: bool = True
    attendance_status: str = "pending"


class ParticipantCreate(ParticipantBase):
    user_code: int
    meeting_id: str


class ParticipantResponse(ParticipantBase):
    id: str
    meeting_id: str
    user_code: int
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingBase(BaseModel):
    title: str = Field(..., max_length=75)
    description: Optional[str] = None
    date_time: datetime
    location: Optional[str] = Field(None, max_length=100)
    duration_minutes: int = 60
    agenda: Optional[str] = None
    status: str = "scheduled"


class MeetingCreate(MeetingBase):
    participants: List[ParticipantCreate] = []


class MeetingResponse(MeetingBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    participants: List[ParticipantResponse] = []
    class Config:
        from_attributes = True


# 定义人员签到数据模型
class PersonSignBase(BaseModel):
    name: str = Field(..., max_length=50)
    user_code: int
    meeting_id: str
    is_signed: bool = False
    is_on_leave: bool = False


class PersonSignCreate(PersonSignBase):
    pass


class PersonSignResponse(PersonSignBase):
    id: int

    class Config:
        from_attributes = True


class PersonSignUpdate(BaseModel):
    is_signed: bool
    is_on_leave: bool