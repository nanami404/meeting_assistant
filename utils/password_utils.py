"""
临时密码工具类
提供密码加密和验证功能
"""
import bcrypt
from typing import List, Optional
from loguru import logger


class PasswordUtils:
    """密码工具类"""
    
    # 常见密码列表
    COMMON_PASSWORDS = [
        "123456",
        "password",
        "123456789",
        "12345678",
        "12345",
        "1234567",
        "admin",
        "Admin123",
        "Admin123456",
        "123123",
        "qwerty",
        "abc123",
        "password123",
        "admin123",
        "root",
        "test",
        "guest",
        "user",
        "demo",
        "welcome"
    ]
    
    def __init__(self):
        """初始化密码工具类"""
        pass
    
    def hash_password(self, plain_password: str) -> str:
        """
        生成加密后的密码
        
        Args:
            plain_password: 明文密码
            
        Returns:
            str: 加密后的密码哈希值
        """
        try:
            if not plain_password:
                raise ValueError("密码不能为空")
            
            # 使用bcrypt加密密码，参考UserService的实现
            hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            logger.info(f"密码加密成功")
            return hashed
            
        except Exception as e:
            logger.error(f"密码加密失败: {e}")
            raise e
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        验证密码
        
        Args:
            plain_password: 明文密码
            hashed_password: 加密后的密码哈希值
            
        Returns:
            bool: 验证结果
        """
        try:
            if not plain_password or not hashed_password:
                return False
            
            # 使用bcrypt验证密码，参考UserService的实现
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
            
        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False
    
    def verify_with_common_passwords(self, hashed_password: str) -> Optional[str]:
        """
        使用常见密码验证加密后的密码
        
        Args:
            hashed_password: 加密后的密码哈希值
            
        Returns:
            Optional[str]: 如果匹配到常见密码，返回明文密码；否则返回None
        """
        try:
            if not hashed_password:
                return None
            
            logger.info("开始使用常见密码进行验证...")
            
            for common_password in self.COMMON_PASSWORDS:
                if self.verify_password(common_password, hashed_password):
                    logger.info(f"匹配到常见密码: {common_password}")
                    return common_password
            
            logger.info("未匹配到任何常见密码")
            return None
            
        except Exception as e:
            logger.error(f"常见密码验证失败: {e}")
            return None
    
    def verify_with_custom_password(self, custom_password: str, hashed_password: str) -> bool:
        """
        使用自定义密码验证加密后的密码
        
        Args:
            custom_password: 用户输入的自定义密码
            hashed_password: 加密后的密码哈希值
            
        Returns:
            bool: 验证结果
        """
        try:
            if not custom_password or not hashed_password:
                return False
            
            result = self.verify_password(custom_password, hashed_password)
            if result:
                logger.info("自定义密码验证成功")
            else:
                logger.info("自定义密码验证失败")
            
            return result
            
        except Exception as e:
            logger.error(f"自定义密码验证失败: {e}")
            return False
    
    def comprehensive_verify(self, hashed_password: str, custom_password: Optional[str] = None) -> dict:
        """
        综合密码验证：先尝试常见密码，如果没有匹配再使用自定义密码
        
        Args:
            hashed_password: 加密后的密码哈希值
            custom_password: 可选的自定义密码
            
        Returns:
            dict: 验证结果，包含是否成功、匹配的密码类型和密码值
        """
        result = {
            "success": False,
            "password_type": None,  # "common" 或 "custom"
            "password": None,
            "message": ""
        }
        
        try:
            # 1. 先尝试常见密码
            common_password = self.verify_with_common_passwords(hashed_password)
            if common_password:
                result["success"] = True
                result["password_type"] = "common"
                result["password"] = common_password
                result["message"] = f"匹配到常见密码: {common_password}"
                return result
            
            # 2. 如果没有匹配到常见密码，且提供了自定义密码，则验证自定义密码
            if custom_password:
                if self.verify_with_custom_password(custom_password, hashed_password):
                    result["success"] = True
                    result["password_type"] = "custom"
                    result["password"] = custom_password
                    result["message"] = "自定义密码验证成功"
                else:
                    result["message"] = "自定义密码验证失败"
            else:
                result["message"] = "未匹配到常见密码，请提供自定义密码进行验证"
            
            return result
            
        except Exception as e:
            logger.error(f"综合密码验证失败: {e}")
            result["message"] = f"验证过程出错: {str(e)}"
            return result
    
    def get_common_passwords(self) -> List[str]:
        """
        获取常见密码列表
        
        Returns:
            List[str]: 常见密码列表
        """
        return self.COMMON_PASSWORDS.copy()
    
    def add_common_password(self, password: str) -> bool:
        """
        添加常见密码到列表中
        
        Args:
            password: 要添加的密码
            
        Returns:
            bool: 是否添加成功
        """
        try:
            if password and password not in self.COMMON_PASSWORDS:
                self.COMMON_PASSWORDS.append(password)
                logger.info(f"添加常见密码成功: {password}")
                return True
            return False
        except Exception as e:
            logger.error(f"添加常见密码失败: {e}")
            return False


# 创建全局实例
password_utils = PasswordUtils()