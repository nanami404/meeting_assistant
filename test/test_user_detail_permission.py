#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户详情接口权限控制测试脚本
测试场景：
1. 普通用户查询自己的信息 - 应该成功
2. 普通用户查询其他用户信息 - 应该返回403权限不足
3. 管理员查询任意用户信息 - 应该成功
4. 未登录用户访问 - 应该返回401未授权
"""

import requests
import json
from typing import Dict, Any

# 测试配置
BASE_URL = "http://localhost:8000/api"
TEST_RESULTS = []

def log_test(test_name: str, success: bool, message: str = ""):
    """记录测试结果"""
    status = "✅ PASS" if success else "❌ FAIL"
    result = f"{status} {test_name}"
    if message:
        result += f" - {message}"
    print(result)
    TEST_RESULTS.append({"test": test_name, "success": success, "message": message})

def login_user(username: str, password: str) -> Dict[str, Any]:
    """用户登录并返回token信息"""
    login_data = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"登录失败: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        print(f"登录异常: {e}")
        return {}

def get_user_detail(user_id: str, token: str = None) -> requests.Response:
    """获取用户详情"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers, timeout=10)
        return response
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None

def test_normal_user_access_own_info():
    """测试1: 普通用户查询自己的信息"""
    print("\n=== 测试1: 普通用户查询自己的信息 ===")
    
    # 使用普通用户登录（使用默认的测试用户）
    login_result = login_user("demo_user", "123456")
    if not login_result.get("data", {}).get("access_token"):
        log_test("普通用户登录", False, "登录失败，无法获取token")
        return
    
    token = login_result["data"]["access_token"]
    
    # 获取当前用户信息来获取用户ID
    profile_response = requests.get(
        f"{BASE_URL}/auth/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if profile_response.status_code != 200:
        log_test("获取用户信息", False, f"无法获取当前用户信息: {profile_response.status_code}")
        return
    
    current_user_id = profile_response.json()["data"]["id"]
    
    # 查询自己的信息
    response = get_user_detail(current_user_id, token)
    
    if response.status_code == 200:
        log_test("普通用户查询自己信息", True, "成功获取自己的用户信息")
    else:
        log_test("普通用户查询自己信息", False, f"期望200，实际: {response.status_code}")

def test_normal_user_access_others_info():
    """测试2: 普通用户查询其他用户信息"""
    print("\n=== 测试2: 普通用户查询其他用户信息 ===")
    
    # 使用普通用户登录
    login_result = login_user("demo_user", "123456")
    if not login_result.get("data", {}).get("access_token"):
        log_test("普通用户登录", False, "登录失败，无法获取token")
        return
    
    token = login_result["data"]["access_token"]
    
    # 登录管理员获取真实ID
    admin_login = login_user("admin", "Admin123456")
    if not admin_login.get("data", {}).get("access_token"):
        log_test("管理员登录用于获取ID", False, "登录失败，无法获取管理员ID")
        return
    admin_token = admin_login["data"]["access_token"]
    
    admin_profile = requests.get(
        f"{BASE_URL}/auth/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    if admin_profile.status_code != 200:
        log_test("获取管理员用户信息", False, f"无法获取管理员ID: {admin_profile.status_code}")
        return
    other_user_id = admin_profile.json()["data"]["id"]
    
    # 普通用户查询管理员信息，应返回403
    response = get_user_detail(other_user_id, token)
    
    if response.status_code == 403:
        log_test("普通用户查询其他用户信息", True, "正确返回403禁止访问")
    else:
        log_test("普通用户查询其他用户信息", False, f"期望403，实际: {response.status_code}")

def test_admin_access_any_user_info():
    """测试3: 管理员查询任意用户信息"""
    print("\n=== 测试3: 管理员查询任意用户信息 ===")
    
    # 使用管理员登录（使用默认的管理员用户）
    login_result = login_user("admin", "Admin123456")
    if not login_result.get("data", {}).get("access_token"):
        log_test("管理员登录", False, "登录失败，无法获取token")
        return
    
    token = login_result["data"]["access_token"]
    
    # 登录 demo_user 获取真实ID
    demo_login = login_user("demo_user", "123456")
    if not demo_login.get("data", {}).get("access_token"):
        log_test("获取被查询用户ID", False, "demo_user登录失败，无法获取ID")
        return
    demo_token = demo_login["data"]["access_token"]
    
    demo_profile = requests.get(
        f"{BASE_URL}/auth/profile",
        headers={"Authorization": f"Bearer {demo_token}"},
        timeout=10,
    )
    if demo_profile.status_code != 200:
        log_test("获取被查询用户信息", False, f"无法获取demo_user ID: {demo_profile.status_code}")
        return
    test_user_id = demo_profile.json()["data"]["id"]
    
    response = get_user_detail(test_user_id, token)
    
    # 管理员应该能够查询任意用户，即使用户不存在也应该返回404而不是403
    if response and response.status_code in [200, 404]:
        log_test("管理员查询任意用户", True, f"状态码: {response.status_code} (200=成功, 404=用户不存在)")
    else:
        status_code = response.status_code if response else "无响应"
        log_test("管理员查询任意用户", False, f"期望200或404，实际: {status_code}")

def test_unauthorized_access():
    """测试4: 未登录用户访问"""
    print("\n=== 测试4: 未登录用户访问 ===")
    
    try:
        # 使用有效的整数型ID以触发鉴权逻辑，而非422参数错误
        response = requests.get(f"{BASE_URL}/users/1", timeout=10)
        if response.status_code == 401:
            log_test("未登录访问", True, "正确返回401未授权")
        else:
            log_test("未登录访问", False, f"期望401，实际: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_test("未登录访问", False, f"请求异常: {e}")

def main():
    """主测试函数"""
    print("🚀 开始用户详情接口权限控制测试")
    print(f"测试目标: {BASE_URL}/users/{{user_id}}")
    
    # 执行所有测试
    test_normal_user_access_own_info()
    test_normal_user_access_others_info()
    test_admin_access_any_user_info()
    test_unauthorized_access()
    
    # 统计测试结果
    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for result in TEST_RESULTS if result["success"])
    failed_tests = total_tests - passed_tests
    
    print(f"\n📊 测试结果统计:")
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {failed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    if failed_tests > 0:
        print("\n❌ 失败的测试:")
        for result in TEST_RESULTS:
            if not result["success"]:
                print(f"  - {result['test']}: {result['message']}")
    else:
        print("\n🎉 所有测试通过！权限控制功能正常工作。")

if __name__ == "__main__":
    main()