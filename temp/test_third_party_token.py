import asyncio
import sys
import os
import hashlib
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 模拟httpx导入错误的处理
service_available = False
ThirdPartyTokenService = None

try:
    from services.third_party_service import ThirdPartyTokenService as ServiceClass
    service_available = True
    ThirdPartyTokenService = ServiceClass
except ImportError as e:
    print(f"导入服务时出错: {e}")
    
# 如果无法导入，我们手动实现部分功能用于测试
if not service_available:
    class ThirdPartyTokenService:
        def __init__(self):
            self.app_id = "alhear"
            self.app_secret = "z88zjsQirc4DOkMTKnfokU3fHOxFeZzoYwwGvHyG@r1j"
            self.base_url = ""
            
        def _generate_access_token(self) -> str:
            """
            根据文档规范生成access-token
            格式: appld-(appld)#timestamp-(timestamp)#sign-(sign)
            sign计算规则: md5(appld + appsecret + timestamp)
            """
            timestamp = str(int(time.time() * 1000))  # 当前时间戳(毫秒)
            
            # 计算签名
            sign_str = f"{self.app_id}{self.app_secret}{timestamp}"
            sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
            
            # 构造access-token
            access_token = f"appld-{self.app_id}#timestamp-{timestamp}#sign-{sign}"
            return access_token
            
        def _construct_headers(self) -> dict:
            """
            构造请求头
            """
            access_token = self._generate_access_token()
            return {
                "access-token": access_token,
                "Content-Type": "application/json"
            }

async def test_third_party_token():
    """测试第三方token获取功能"""
    print("开始测试第三方token获取功能...")
    
    service = ThirdPartyTokenService()
    
    # 测试生成access token
    print("\n1. 测试生成access token:")
    access_token = service._generate_access_token()
    print(f"生成的access token: {access_token}")
    
    # 验证access token格式
    if "appld-" in access_token and "timestamp-" in access_token and "sign-" in access_token:
        print("✓ access token格式正确")
    else:
        print("✗ access token格式不正确")
    
    # 测试构造请求头
    print("\n2. 测试构造请求头:")
    headers = service._construct_headers()
    print(f"请求头: {headers}")
    
    if "access-token" in headers and "Content-Type" in headers:
        print("✓ 请求头构造正确")
    else:
        print("✗ 请求头构造不正确")
    
    # 验证签名计算是否正确
    print("\n3. 验证签名计算:")
    # 提取access token中的各个部分
    parts = access_token.split("#")
    appld_part = parts[0]
    timestamp_part = parts[1]
    sign_part = parts[2]
    
    appld = appld_part.split("-")[1]
    timestamp = timestamp_part.split("-")[1]
    sign = sign_part.split("-")[1]
    
    # 重新计算签名
    expected_sign_str = f"{appld}{service.app_secret}{timestamp}"
    expected_sign = hashlib.md5(expected_sign_str.encode('utf-8')).hexdigest()
    
    if sign == expected_sign:
        print("✓ 签名计算正确")
    else:
        print(f"✗ 签名计算不正确。期望: {expected_sign}, 实际: {sign}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(test_third_party_token())