#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共用户列表查询接口测试脚本

测试新开发的 /api/public/users 接口的各项功能：
1. 基础查询功能
2. 按用户姓名模糊查询
3. 按部门模糊查询
4. 组合查询（姓名+部门）
5. 分页功能
6. 排序功能
7. 参数验证
"""

import requests
import json
from typing import Dict, Any

# 测试配置
BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{BASE_URL}/api/public/users"

def make_request(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """发送GET请求到公共用户接口"""
    try:
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        return {
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": 0,
            "error": str(e)
        }

def print_test_result(test_name: str, result: Dict[str, Any], expected_status: int = 200):
    """打印测试结果"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"{'='*60}")
    
    if "error" in result:
        print(f"❌ 请求失败: {result['error']}")
        return False
    
    status_code = result["status_code"]
    data = result["data"]
    
    print(f"状态码: {status_code}")
    
    if status_code != expected_status:
        print(f"❌ 状态码不符合预期 (期望: {expected_status}, 实际: {status_code})")
        print(f"响应内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return False
    
    if status_code == 200 and isinstance(data, dict):
        if data.get("code") == 0:
            result_data = data.get("data", {})
            users = result_data.get("users", [])
            pagination = result_data.get("pagination", {})
            
            print(f"✅ 请求成功")
            print(f"用户数量: {len(users)}")
            print(f"总记录数: {pagination.get('total', 0)}")
            print(f"当前页: {pagination.get('page', 1)}")
            print(f"每页大小: {pagination.get('page_size', 20)}")
            print(f"总页数: {pagination.get('total_pages', 0)}")
            
            # 显示前3个用户的基础信息
            if users:
                print(f"\n前{min(3, len(users))}个用户信息:")
                for i, user in enumerate(users[:3]):
                    print(f"  {i+1}. {user.get('name', 'N/A')} ({user.get('user_name', 'N/A')}) - {user.get('company', 'N/A')}")
            
            return True
        else:
            print(f"❌ 业务错误: {data.get('message', '未知错误')}")
            return False
    elif status_code == 422:
        # 参数验证错误，这是预期的
        print(f"✅ 参数验证正确，返回422错误")
        if isinstance(data, dict) and "detail" in data:
            print(f"验证错误详情: {data['detail'][0]['msg'] if data['detail'] else '未知验证错误'}")
        return True
    else:
        print(f"❌ 响应格式异常: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return False

def run_tests():
    """运行所有测试用例"""
    print("开始测试公共用户列表查询接口...")
    
    test_results = []
    
    # 测试1: 基础查询（无参数）
    result = make_request()
    success = print_test_result("基础查询（无参数）", result)
    test_results.append(("基础查询", success))
    
    # 测试2: 按用户姓名模糊查询
    result = make_request({"name_keyword": "张"})
    success = print_test_result("按用户姓名模糊查询", result)
    test_results.append(("姓名模糊查询", success))
    
    # 测试3: 按部门模糊查询
    result = make_request({"company_keyword": "技术"})
    success = print_test_result("按部门模糊查询", result)
    test_results.append(("部门模糊查询", success))
    
    # 测试4: 组合查询（姓名+部门）
    result = make_request({"name_keyword": "李", "company_keyword": "部门"})
    success = print_test_result("组合查询（姓名+部门）", result)
    test_results.append(("组合查询", success))
    
    # 测试5: 分页测试
    result = make_request({"page": 1, "page_size": 5})
    success = print_test_result("分页测试（第1页，每页5条）", result)
    test_results.append(("分页测试", success))
    
    # 测试6: 排序测试（按部门降序）
    result = make_request({"order_by": "company", "order": "desc"})
    success = print_test_result("排序测试（按部门降序）", result)
    test_results.append(("排序测试", success))
    
    # 测试7: 参数验证测试（无效页码）
    result = make_request({"page": 0})
    success = print_test_result("参数验证测试（无效页码）", result, expected_status=422)
    test_results.append(("参数验证", success))
    
    # 测试8: 参数验证测试（超大页面大小）
    result = make_request({"page_size": 200})
    success = print_test_result("参数验证测试（超大页面大小）", result, expected_status=422)
    test_results.append(("页面大小验证", success))
    
    # 测试总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！公共用户列表查询接口功能正常。")
    else:
        print("⚠️  部分测试失败，请检查接口实现。")
    
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)