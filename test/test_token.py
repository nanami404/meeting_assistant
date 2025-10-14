#!/usr/bin/env python3
"""
JWT Token 调试脚本
用于检查token的生成、验证和解码过程
"""

import requests
import json
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
import time

# 加载环境变量
load_dotenv()

def test_login_and_token():
    """测试登录并检查token"""
    base_url = "http://localhost:8000"
    
    # 1. 管理员登录
    print("=" * 60)
    print("1. 测试管理员登录")
    print("=" * 60)
    
    login_data = {
        "username": "admin",
        "password": "Admin123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    print(f"登录响应状态码: {response.status_code}")
    print(f"登录响应内容: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        access_token = data["data"]["access_token"]
        print(f"获取到的access_token: {access_token[:50]}...")
        
        # 2. 解码token查看内容
        print("\n" + "=" * 60)
        print("2. 解码token内容")
        print("=" * 60)
        
        try:
            # 不验证签名，只查看payload
            decoded = jwt.get_unverified_claims(access_token)
            print("Token payload:")
            print(json.dumps(decoded, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"解码token失败: {e}")
        
        # 3. 使用token访问受保护的API
        print("\n" + "=" * 60)
        print("3. 使用token访问受保护的API")
        print("=" * 60)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = requests.get(f"{base_url}/api/auth/profile", headers=headers)
        print(f"获取用户信息响应状态码: {profile_response.status_code}")
        print(f"获取用户信息响应内容: {profile_response.text}")
        
        # 4. 验证JWT_SECRET配置
        print("\n" + "=" * 60)
        print("4. 检查JWT配置")
        print("=" * 60)
        
        jwt_secret = os.getenv("JWT_SECRET", "")
        print(f"JWT_SECRET是否配置: {'是' if jwt_secret else '否'}")
        if jwt_secret:
            print(f"JWT_SECRET长度: {len(jwt_secret)}")
            print(f"JWT_SECRET前10位: {jwt_secret[:10]}...")
        
        # 5. 手动验证token
        print("\n" + "=" * 60)
        print("5. 手动验证token")
        print("=" * 60)
        
        if jwt_secret:
            try:
                verified_payload = jwt.decode(
                    access_token,
                    jwt_secret,
                    algorithms=["HS256"],
                    audience="meeting-assistant-clients",
                    issuer="meeting-assistant"
                )
                print("Token验证成功!")
                print("验证后的payload:")
                print(json.dumps(verified_payload, indent=2, ensure_ascii=False))
            except JWTError as e:
                print(f"Token验证失败: {e}")
        else:
            print("无法验证token: JWT_SECRET未配置")
    
    else:
        print("登录失败，无法继续测试")

def run_tests_with_interval(tests, interval_seconds=2):
    """
    以固定间隔执行测试方法
    tests: 可调用对象列表
    interval_seconds: 每个测试方法之间的等待秒数
    """
    for idx, test in enumerate(tests):
        print("\n" + "=" * 60)
        print(f"开始执行测试方法 {idx + 1}/{len(tests)}: {test.__name__}")
        print("=" * 60)
        try:
            test()
        except Exception as e:
            print(f"测试方法 {test.__name__} 执行异常: {e}")
        if idx < len(tests) - 1:
            print(f"\n等待 {interval_seconds} 秒后继续执行下一个测试方法...")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    interval = int(os.getenv("TEST_INTERVAL_SECONDS", "2"))
    run_tests_with_interval([test_login_and_token], interval_seconds=interval)