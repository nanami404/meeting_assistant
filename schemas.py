from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import List, Optional
import re


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


# ==================== 用户管理相关模型 ====================

class UserBase(BaseModel):
    """
    用户基础模型
    
    包含用户的基本信息字段，用作其他用户相关模型的基类。
    
    Attributes:
        name: 用户姓名，必填，最大长度100字符
        email: 邮箱地址，必填，自动验证邮箱格式
        gender: 性别，可选，限制为male/female/other
        phone: 手机号码，可选，验证中国大陆手机号格式
        id_number: 证件号码/工号，可选，最大长度18字符
        company: 所属公司/单位，可选，最大长度200字符
        role: 用户角色，默认为user，限制为admin/user
        status: 用户状态，默认为active，限制为active/inactive/suspended
    """
    name: str = Field(..., min_length=1, max_length=100, description="用户姓名")
    email: EmailStr = Field(..., description="邮箱地址")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="手机号码")
    id_number: Optional[str] = Field(None, max_length=18, description="证件号码/工号")
    company: Optional[str] = Field(None, max_length=200, description="所属公司/单位")
    role: str = Field(default="user", description="用户角色")
    status: str = Field(default="active", description="用户状态")

    @validator('gender')
    def validate_gender(cls, v):
        if v is not None and v not in ['male', 'female', 'other']:
            raise ValueError('性别必须为male、female或other')
        return v

    @validator('phone')
    def validate_phone(cls, v):
        if v is not None:
            # 中国大陆手机号验证
            pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
            if not re.match(pattern, v):
                raise ValueError('手机号格式不正确')
        return v

    @validator('role')
    def validate_role(cls, v):
        if v not in ['admin', 'user']:
            raise ValueError('用户角色必须为admin或user')
        return v

    @validator('status')
    def validate_status(cls, v):
        if v not in ['active', 'inactive', 'suspended']:
            raise ValueError('用户状态必须为active、inactive或suspended')
        return v


class UserCreate(UserBase):
    """
    创建用户请求模型
    
    用于用户注册和管理员创建用户的请求。
    包含密码字段并进行强度验证。
    
    Attributes:
        password: 用户密码，必填，进行强度验证
    """
    password: str = Field(..., min_length=8, max_length=128, description="用户密码")

    @validator('password')
    def validate_password(cls, v):
        """
        密码强度验证：
        - 至少8位字符
        - 包含大写字母、小写字母、数字和特殊字符中的至少3种
        """
        if len(v) < 8:
            raise ValueError('密码长度至少为8位')
        
        # 检查密码复杂度
        has_upper = bool(re.search(r'[A-Z]', v))
        has_lower = bool(re.search(r'[a-z]', v))
        has_digit = bool(re.search(r'\d', v))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', v))
        
        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_count < 3:
            raise ValueError('密码必须包含大写字母、小写字母、数字和特殊字符中的至少3种')
        
        return v


class UserUpdate(BaseModel):
    """
    更新用户请求模型
    
    用于更新用户信息的请求，所有字段都是可选的。
    不包含密码字段，密码更新需要单独的接口。
    
    Attributes:
        name: 用户姓名，可选
        gender: 性别，可选
        phone: 手机号码，可选
        id_number: 证件号码/工号，可选
        company: 所属公司/单位，可选
        role: 用户角色，可选（仅管理员可修改）
        status: 用户状态，可选（仅管理员可修改）
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="用户姓名")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="手机号码")
    id_number: Optional[str] = Field(None, max_length=18, description="证件号码/工号")
    company: Optional[str] = Field(None, max_length=200, description="所属公司/单位")
    role: Optional[str] = Field(None, description="用户角色")
    status: Optional[str] = Field(None, description="用户状态")

    @validator('gender')
    def validate_gender(cls, v):
        if v is not None and v not in ['male', 'female', 'other']:
            raise ValueError('性别必须为male、female或other')
        return v

    @validator('phone')
    def validate_phone(cls, v):
        if v is not None:
            pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
            if not re.match(pattern, v):
                raise ValueError('手机号格式不正确')
        return v

    @validator('role')
    def validate_role(cls, v):
        if v is not None and v not in ['admin', 'user']:
            raise ValueError('用户角色必须为admin或user')
        return v

    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['active', 'inactive', 'suspended']:
            raise ValueError('用户状态必须为active、inactive或suspended')
        return v


class UserResponse(UserBase):
    """
    用户响应模型
    
    用于API响应的用户信息模型。
    不包含敏感信息如密码哈希。
    
    Attributes:
        id: 用户唯一标识
        created_at: 创建时间
        updated_at: 更新时间
        created_by: 创建者用户ID，可选
        updated_by: 更新者用户ID，可选
    """
    id: str = Field(..., description="用户唯一标识")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    created_by: Optional[str] = Field(None, description="创建者用户ID")
    updated_by: Optional[str] = Field(None, description="更新者用户ID")

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """
    用户登录请求模型
    
    用于用户登录验证的请求模型。
    支持邮箱或手机号登录。
    
    Attributes:
        username: 用户名（邮箱或手机号），必填
        password: 密码，必填
    """
    username: str = Field(..., min_length=1, max_length=255, description="用户名（邮箱或手机号）")
    password: str = Field(..., min_length=1, max_length=128, description="密码")

    @validator('username')
    def validate_username(cls, v):
        """
        验证用户名格式：必须是有效的邮箱或手机号
        """
        # 检查是否为邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        # 检查是否为手机号格式
        phone_pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
        
        if not (re.match(email_pattern, v) or re.match(phone_pattern, v)):
            raise ValueError('用户名必须是有效的邮箱地址或手机号码')
        
        return v