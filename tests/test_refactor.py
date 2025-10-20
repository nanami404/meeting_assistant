#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型重构测试脚本
用于验证模型文件重构是否成功，保持向后兼容性
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """测试基本导入功能"""
    print("开始测试模型导入...")
    print("=" * 50)
    
    success_count = 0
    total_tests = 0
    
    # 测试1: 数据库枚举导入
    total_tests += 1
    try:
        from models.database.enums import UserRole, UserStatus, GenderType
        print("✓ 数据库枚举导入成功")
        # 验证枚举值
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.INACTIVE.value == "inactive"
        assert UserStatus.SUSPENDED.value == "suspended"
        print("  ✓ 枚举值验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 数据库枚举导入失败: {e}")
    
    # 测试2: 数据库用户模型导入
    total_tests += 1
    try:
        from models.database.user import User, PersonSign
        print("✓ 数据库用户模型导入成功")
        # 验证模型属性
        assert hasattr(User, '__tablename__')
        assert hasattr(PersonSign, '__tablename__')
        print("  ✓ 用户模型结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 数据库用户模型导入失败: {e}")
    
    # 测试3: 数据库会议模型导入
    total_tests += 1
    try:
        from models.database.meeting import Meeting, Participant, Transcription
        print("✓ 数据库会议模型导入成功")
        # 验证模型属性
        assert hasattr(Meeting, '__tablename__')
        assert hasattr(Participant, '__tablename__')
        assert hasattr(Transcription, '__tablename__')
        print("  ✓ 会议模型结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 数据库会议模型导入失败: {e}")
    
    # 测试4: 数据库消息模型导入
    total_tests += 1
    try:
        from models.database.message import Message, MessageRecipient
        print("✓ 数据库消息模型导入成功")
        # 验证模型属性
        assert hasattr(Message, '__tablename__')
        assert hasattr(MessageRecipient, '__tablename__')
        print("  ✓ 消息模型结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 数据库消息模型导入失败: {e}")
    
    # 测试5: 用户Schema导入
    total_tests += 1
    try:
        from models.schemas.user import (
            UserBase, UserCreate, UserUpdate, UserResponse, 
            UserBasicResponse, UserLogin
        )
        print("✓ 用户Schema导入成功")
        # 验证模型属性
        assert hasattr(UserBase, 'name')
        assert hasattr(UserCreate, 'user_name')
        print("  ✓ 用户Schema结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 用户Schema导入失败: {e}")
    
    # 测试6: 会议Schema导入
    total_tests += 1
    try:
        from models.schemas.meeting import (
            ParticipantBase, ParticipantCreate, ParticipantResponse,
            MeetingBase, MeetingCreate, MeetingResponse,
            PersonSignCreate, PersonSignResponse
        )
        print("✓ 会议Schema导入成功")
        # 验证模型属性
        assert hasattr(MeetingBase, 'title')
        assert hasattr(ParticipantBase, 'name')
        print("  ✓ 会议Schema结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 会议Schema导入失败: {e}")
    
    # 测试7: 转录Schema导入
    total_tests += 1
    try:
        from models.schemas.transcription import (
            TranscriptionBase, TranscriptionCreate, TranscriptionResponse
        )
        print("✓ 转录Schema导入成功")
        # 验证模型属性
        assert hasattr(TranscriptionBase, 'text')
        assert hasattr(TranscriptionCreate, 'meeting_id')
        print("  ✓ 转录Schema结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 转录Schema导入失败: {e}")
    
    # 测试8: 消息Schema导入
    total_tests += 1
    try:
        from models.schemas.message import WebSocketMessage
        print("✓ 消息Schema导入成功")
        # 验证模型属性
        assert hasattr(WebSocketMessage, 'type')
        assert hasattr(WebSocketMessage, 'meeting_id')
        print("  ✓ 消息Schema结构验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 消息Schema导入失败: {e}")
    
    # 测试9: 向后兼容性 - 旧服务模型导入
    total_tests += 1
    try:
        from services.service_models import User as ServiceUser, Meeting as ServiceMeeting
        from services.service_models import UserRole as ServiceUserRole
        print("✓ 服务模型向后兼容性导入成功")
        # 验证模型属性
        assert hasattr(ServiceUser, '__tablename__')
        assert hasattr(ServiceMeeting, '__tablename__')
        print("  ✓ 服务模型向后兼容性验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ 服务模型向后兼容性导入失败: {e}")
    
    # 测试10: 向后兼容性 - 旧Schema导入
    total_tests += 1
    try:
        from schemas import UserCreate as OldUserCreate, MeetingCreate as OldMeetingCreate
        print("✓ Schema向后兼容性导入成功")
        # 验证模型属性
        assert hasattr(OldUserCreate, 'name')
        assert hasattr(OldMeetingCreate, 'title')
        print("  ✓ Schema向后兼容性验证通过")
        success_count += 1
    except Exception as e:
        print(f"✗ Schema向后兼容性导入失败: {e}")
    
    print("=" * 50)
    print(f"测试结果: {success_count}/{total_tests} 个测试通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！模型重构成功！")
        return True
    else:
        print("❌ 部分测试失败，请检查上述错误信息。")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)