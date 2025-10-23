import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.third_party_service import ThirdPartyTokenService

# 测试环境变量配置
os.environ["THIRD_PARTY_APP_ID"] = "test_app_id"
os.environ["THIRD_PARTY_APP_SECRET"] = "test_app_secret"
os.environ["THIRD_PARTY_BASE_URL"] = "https://api.example.com"

def test_third_party_service():
    # 创建服务实例
    service = ThirdPartyTokenService()
    
    # 测试默认配置
    print("默认配置:")
    print(f"app_id: {service.app_id}")
    print(f"app_secret: {service.app_secret}")
    print(f"base_url: {service.base_url}")
    
    # 测试使用传入参数
    print("\n使用传入参数:")
    # 注意：这里只是测试配置的设置，不实际调用API
    # 我们直接设置属性来模拟参数传递的效果
    service.app_id = "custom_app_id" or service.default_app_id
    service.app_secret = "custom_app_secret" or service.default_app_secret
    service.base_url = "https://custom.example.com" or service.default_base_url
    print(f"app_id: {service.app_id}")
    print(f"app_secret: {service.app_secret}")
    print(f"base_url: {service.base_url}")

if __name__ == "__main__":
    test_third_party_service()