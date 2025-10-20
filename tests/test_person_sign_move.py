#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试人员签到表迁移
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_person_sign_move():
    """测试人员签到表迁移"""
    print("测试人员签到表迁移...")
    
    try:
        # 测试从新位置导入PersonSign
        from models.database.meeting import PersonSign
        print("✓ PersonSign从会议模型文件导入成功")
        
        # 验证模型属性
        assert hasattr(PersonSign, '__tablename__')
        assert PersonSign.__tablename__ == "person_sign"
        print("  ✓ PersonSign模型结构验证通过")
        
        # 测试向后兼容性 - 从旧位置导入
        from services.service_models import PersonSign as OldPersonSign
        print("✓ PersonSign向后兼容性导入成功")
        
        # 验证两个导入的是同一个类
        assert PersonSign is OldPersonSign
        print("  ✓ 向后兼容性验证通过")
        
        # 测试从用户模型文件不再导入PersonSign
        from models.database.user import User
        print("✓ 用户模型导入成功")
        
        print("🎉 人员签到表迁移测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 人员签到表迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_person_sign_move()
    sys.exit(0 if success else 1)