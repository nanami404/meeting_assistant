"""
测试多字段模糊匹配功能
验证新增的独立字段查询参数
"""
import requests
import json

def test_multi_field_search():
    """测试多字段模糊匹配功能"""
    base_url = "http://localhost:8000"
    
    # 先登录获取token
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin123456"}
    )
    
    if login_response.status_code != 200:
        print("❌ 登录失败")
        return
    
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("🔍 测试多字段模糊匹配功能")
    print("=" * 50)
    
    # 测试1: 使用原有的keyword参数
    print("\n1. 测试原有的keyword参数（向后兼容）")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"keyword": "admin"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ keyword='admin' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ keyword查询失败: {response.status_code}")
    
    # 测试2: 使用独立的name_keyword参数
    print("\n2. 测试独立的name_keyword参数")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"name_keyword": "管理员"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ name_keyword='管理员' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ name_keyword查询失败: {response.status_code}")
    
    # 测试3: 使用独立的user_name_keyword参数
    print("\n3. 测试独立的user_name_keyword参数")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"user_name_keyword": "admin"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ user_name_keyword='admin' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ user_name_keyword查询失败: {response.status_code}")
    
    # 测试4: 组合多个字段查询（AND关系）
    print("\n4. 测试组合多字段查询（AND关系）")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={
            "name_keyword": "管理员",
            "user_name_keyword": "admin"
        }
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ 组合查询成功，找到 {len(data['items'])} 个用户")
        if data['items']:
            user = data['items'][0]
            print(f"  - 用户: {user.get('name', 'N/A')} ({user.get('user_name', 'N/A')})")
    else:
        print(f"❌ 组合查询失败: {response.status_code}")
    
    # 测试5: 测试email_keyword
    print("\n5. 测试email_keyword参数")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"email_keyword": "@"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ email_keyword='@' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ email_keyword查询失败: {response.status_code}")
    
    # 测试6: 测试company_keyword
    print("\n6. 测试company_keyword参数")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"company_keyword": "公司"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ company_keyword='公司' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ company_keyword查询失败: {response.status_code}")
    
    # 测试7: 测试id_number_keyword
    print("\n7. 测试id_number_keyword参数")
    response = requests.get(
        f"{base_url}/api/users/",
        headers=headers,
        params={"id_number_keyword": "001"}
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ id_number_keyword='001' 查询成功，找到 {len(data['items'])} 个用户")
    else:
        print(f"❌ id_number_keyword查询失败: {response.status_code}")
    
    print("\n" + "=" * 50)
    print("🎉 多字段模糊匹配功能测试完成！")

if __name__ == "__main__":
    test_multi_field_search()