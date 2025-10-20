# -*- coding: utf-8 -*-
"""
消息管理模块 - Pydantic数据模型定义
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Union


class MessageBase(BaseModel):
    """消息基础模型"""
    title: Optional[str] = Field(None, max_length=100, description="消息标题")
    content: str = Field(..., description="消息内容")


class MessageCreate(MessageBase):
    """创建消息请求模型"""
    recipient_ids: List[int] = Field(..., description="接收者ID列表")


class MessageUpdate(BaseModel):
    """更新消息请求模型"""
    title: Optional[str] = Field(None, max_length=100, description="消息标题")
    content: Optional[str] = Field(None, description="消息内容")


class MessageResponse(MessageBase):
    """消息响应模型"""
    id: int = Field(..., description="消息ID")
    sender_id: int = Field(..., description="发送者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class MessageRecipientBase(BaseModel):
    """消息接收者基础模型"""
    message_id: int = Field(..., description="消息ID")
    recipient_id: int = Field(..., description="接收者ID")


class MessageRecipientCreate(MessageRecipientBase):
    """创建消息接收者请求模型"""
    pass


class MessageRecipientUpdate(BaseModel):
    """更新消息接收者请求模型"""
    is_read: Optional[bool] = Field(None, description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")


class MessageRecipientResponse(MessageRecipientBase):
    """消息接收者响应模型"""
    id: int = Field(..., description="关联ID")
    is_read: bool = Field(False, description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


class MessageListRequest(BaseModel):
    """消息列表查询请求模型"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    is_read: Optional[bool] = Field(None, description="是否已读状态过滤")


class MessageListResponse(BaseModel):
    """消息列表响应模型"""
    messages: List[MessageRecipientResponse] = Field(..., description="消息列表")
    pagination: dict = Field(..., description="分页信息")


class MarkReadRequest(BaseModel):
    """标记已读请求模型"""
    message_id: Optional[int] = Field(None, description="消息ID（标记单条）")
    type: Optional[str] = Field(None, description="标记类型（all-全部标记为已读）")


class DeleteMessageRequest(BaseModel):
    """删除消息请求模型"""
    message_id: Optional[int] = Field(None, description="消息ID（删除单条）")
    type: Optional[str] = Field(None, description="删除类型（read-已读消息，unread-未读消息，all-全部消息）")


class BatchOperationResponse(BaseModel):
    """批量操作响应模型"""
    updated_count: Optional[int] = Field(None, description="更新数量")
    deleted_count: Optional[int] = Field(None, description="删除数量")