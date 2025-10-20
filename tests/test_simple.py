#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简单模型导入测试
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_basic_imports():
    """测试基本导入"""
    print("测试基本导入...")
    
    try:
        # 测试数据库模型导入
        from models.database.enums import UserRole, UserStatus, GenderType
        print("✓ 数据库枚举导入成功")
        
        from models.database.user import User, PersonSign
        print("✓ 数据库用户模型导入成功")
        
        from models.database.meeting import Meeting, Participant, Transcription
        print("✓ 数据库会议模型导入成功")
        
        from models.database.message import Message, MessageRecipient
        print("✓ 数据库消息模型导入成功")
        
        # 测试Schema导入
        from models.schemas.user import UserBase, UserCreate
        print("✓ 用户Schema导入成功")
        
        from models.schemas.meeting import MeetingBase, MeetingCreate
        print("✓ 会议Schema导入成功")
        
        from models.schemas.transcription import TranscriptionBase
        print("✓ 转录Schema导入成功")
        
        from models.schemas.message import WebSocketMessage
        print("✓ 消息Schema导入成功")
        
        # 测试向后兼容性
        from services.service_models import User as ServiceUser
        print("✓ 服务模型向后兼容性导入成功")
        
        from schemas import UserCreate as OldUserCreate
        print("✓ Schema向后兼容性导入成功")
        
        print("🎉 所有基本导入测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_basic_imports()
    sys.exit(0 if success else 1)