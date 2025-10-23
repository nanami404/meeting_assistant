import hashlib
import time
import httpx
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

class ThirdPartyTokenService:
    def __init__(self):
        # 从环境变量中获取默认配置
        self.default_app_id = os.getenv("THIRD_PARTY_APP_ID", "alhear")
        self.default_app_secret = os.getenv("THIRD_PARTY_APP_SECRET", "z88zjsQirc4DOkMTKnfokU3fHOxFeZzoYwwGvHyG@r1j")
        self.default_base_url = os.getenv("THIRD_PARTY_BASE_URL", "")
        
        # 当前使用的配置，默认使用环境变量配置
        self.app_id = self.default_app_id
        self.app_secret = self.default_app_secret
        self.base_url = self.default_base_url
        
    def _generate_access_token(self, app_id: Optional[str] = None, app_secret: Optional[str] = None) -> str:
        """
        根据文档规范生成access-token
        格式: appld-(appld)#timestamp-(timestamp)#sign-(sign)
        sign计算规则: md5(appld + appsecret + timestamp)
        """
        # 使用传入的参数或当前实例的配置
        current_app_id = app_id or self.app_id
        current_app_secret = app_secret or self.app_secret
        
        timestamp = str(int(time.time() * 1000))  # 当前时间戳(毫秒)
        
        # 计算签名
        sign_str = f"{current_app_id}{current_app_secret}{timestamp}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        
        # 构造access-token
        access_token = f"appld-{current_app_id}#timestamp-{timestamp}#sign-{sign}"
        return access_token
    
    def _construct_headers(self, app_id: Optional[str] = None, app_secret: Optional[str] = None) -> Dict[str, str]:
        """
        构造请求头
        """
        access_token = self._generate_access_token(app_id, app_secret)
        return {
            "access-token": access_token,
            "Content-Type": "application/json"
        }
    
    async def get_third_party_token(
        self, 
        base_url: Optional[str] = None, 
        app_id: Optional[str] = None, 
        app_secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        请求第三方接口获取最新token
        
        Args:
            base_url: 第三方服务的基础URL
            app_id: 应用ID
            app_secret: 应用密钥
            
        Returns:
            包含token信息和过期时间的字典
        """
        # 使用传入的参数或默认配置
        self.app_id = app_id or self.default_app_id
        self.app_secret = app_secret or self.default_app_secret
        self.base_url = base_url or self.default_base_url
        
        # 检查基础URL是否已设置
        if not self.base_url:
            logger.error("Base URL is not set")
            return {
                "success": False,
                "error": "Base URL Missing",
                "message": "Base URL must be provided either as parameter or through environment variable THIRD_PARTY_BASE_URL"
            }
        
        url = f"{self.base_url}/app/open/thridLogin"
        
        headers = self._construct_headers(app_id, app_secret)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, timeout=30)
                
                # 检查HTTP状态码
                if response.status_code != 200:
                    logger.error(f"Third party API request failed with status code: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP Error: {response.status_code}",
                        "message": response.text
                    }
                
                # 解析响应
                response_data = response.json()
                
                # 检查业务状态码
                if response_data.get("code") != "200":
                    logger.error(f"Third party API business error: {response_data.get('message', 'Unknown error')}")
                    return {
                        "success": False,
                        "error": "Business Error",
                        "message": response_data.get("message", "Unknown business error"),
                        "code": response_data.get("code")
                    }
                
                # 提取token信息
                token = response_data.get("data")
                if not token:
                    logger.error("Token not found in response data")
                    return {
                        "success": False,
                        "error": "Token Missing",
                        "message": "Token not found in response"
                    }
                
                # 返回成功结果，包含7天过期时间
                return {
                    "success": True,
                    "token": token,
                    "expires_in": 7 * 24 * 60 * 60,  # 7天过期时间（秒）
                    "message": "Token retrieved successfully"
                }
                
        except httpx.TimeoutException:
            logger.error("Third party API request timeout")
            return {
                "success": False,
                "error": "Timeout",
                "message": "Request to third party API timed out"
            }
        except httpx.NetworkError:
            logger.error("Network error occurred when requesting third party API")
            return {
                "success": False,
                "error": "Network Error",
                "message": "Network error occurred when requesting third party API"
            }
        except Exception as e:
            logger.error(f"Unexpected error when requesting third party API: {str(e)}")
            return {
                "success": False,
                "error": "Internal Error",
                "message": f"Unexpected error: {str(e)}"
            }

# 创建服务实例
third_party_token_service = ThirdPartyTokenService()