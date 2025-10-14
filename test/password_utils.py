"""
测试密码工具类的功能
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.password_utils import PasswordUtils


def test_password_encryption():
    """测试密码加密功能"""
    print("=" * 50)
    print("测试密码加密功能")
    print("=" * 50)
    
    password_utils = PasswordUtils()
    
    # 测试密码列表
    test_passwords = ["admin", "Admin123456", "test123", "mypassword"]
    
    for password in test_passwords:
        try:
            hashed = password_utils.hash_password(password)
            print(f"原始密码: {password}")
            print(f"加密后: {hashed}")
            print(f"验证结果: {password_utils.verify_password(password, hashed)}")
            print("-" * 30)
        except Exception as e:
            print(f"加密密码 '{password}' 时出错: {e}")


def test_common_password_verification():
    """测试常见密码验证功能"""
    print("=" * 50)
    print("测试常见密码验证功能")
    print("=" * 50)
    
    password_utils = PasswordUtils()
    
    # 测试常见密码
    common_passwords = ["admin", "Admin123456", "123456", "password"]
    
    for password in common_passwords:
        try:
            # 先加密密码
            hashed = password_utils.hash_password(password)
            print(f"测试密码: {password}")
            print(f"加密后: {hashed}")
            
            # 使用常见密码验证
            matched_password = password_utils.verify_with_common_passwords(hashed)
            if matched_password:
                print(f"✓ 匹配到常见密码: {matched_password}")
            else:
                print("✗ 未匹配到常见密码")
            print("-" * 30)
        except Exception as e:
            print(f"验证密码 '{password}' 时出错: {e}")


def test_custom_password_verification():
    """测试自定义密码验证功能"""
    print("=" * 50)
    print("测试自定义密码验证功能")
    print("=" * 50)
    
    password_utils = PasswordUtils()
    
    # 测试自定义密码
    custom_password = "mycustompassword123"
    
    try:
        # 先加密密码
        hashed = password_utils.hash_password(custom_password)
        print(f"自定义密码: {custom_password}")
        print(f"加密后: {hashed}")
        
        # 测试正确的自定义密码
        result = password_utils.verify_with_custom_password(custom_password, hashed)
        print(f"✓ 正确密码验证: {result}")
        
        # 测试错误的自定义密码
        wrong_password = "wrongpassword"
        result = password_utils.verify_with_custom_password(wrong_password, hashed)
        print(f"✗ 错误密码验证: {result}")
        
    except Exception as e:
        print(f"测试自定义密码验证时出错: {e}")


def test_comprehensive_verification():
    """测试综合验证功能"""
    print("=" * 50)
    print("测试综合验证功能")
    print("=" * 50)
    
    password_utils = PasswordUtils()
    
    # 测试场景1：常见密码
    print("场景1：测试常见密码")
    common_password = "admin"
    hashed_common = password_utils.hash_password(common_password)
    result = password_utils.comprehensive_verify(hashed_common)
    print(f"结果: {result}")
    print()
    
    # 测试场景2：非常见密码，提供正确的自定义密码
    print("场景2：测试非常见密码 + 正确自定义密码")
    custom_password = "myspecialpassword"
    hashed_custom = password_utils.hash_password(custom_password)
    result = password_utils.comprehensive_verify(hashed_custom, custom_password)
    print(f"结果: {result}")
    print()
    
    # 测试场景3：非常见密码，提供错误的自定义密码
    print("场景3：测试非常见密码 + 错误自定义密码")
    result = password_utils.comprehensive_verify(hashed_custom, "wrongpassword")
    print(f"结果: {result}")
    print()
    
    # 测试场景4：非常见密码，不提供自定义密码
    print("场景4：测试非常见密码 + 不提供自定义密码")
    result = password_utils.comprehensive_verify(hashed_custom)
    print(f"结果: {result}")


def interactive_test():
    """交互式测试"""
    print("=" * 50)
    print("交互式测试")
    print("=" * 50)
    
    password_utils = PasswordUtils()
    
    while True:
        print("\n请选择测试功能:")
        print("1. 生成加密密码")
        print("2. 验证加密密码")
        print("3. 退出")
        
        choice = input("请输入选择 (1-3): ").strip()
        
        if choice == "1":
            password = input("请输入要加密的密码: ").strip()
            if password:
                try:
                    hashed = password_utils.hash_password(password)
                    print(f"加密后的密码: {hashed}")
                except Exception as e:
                    print(f"加密失败: {e}")
            else:
                print("密码不能为空")
                
        elif choice == "2":
            hashed_password = input("请输入加密后的密码: ").strip()
            if hashed_password:
                try:
                    # 先尝试常见密码
                    result = password_utils.comprehensive_verify(hashed_password)
                    if result["success"]:
                        print(f"验证成功! {result['message']}")
                    else:
                        # 如果没有匹配到常见密码，让用户输入自定义密码
                        custom_password = input("未匹配到常见密码，请输入密码进行验证: ").strip()
                        if custom_password:
                            result = password_utils.comprehensive_verify(hashed_password, custom_password)
                            if result["success"]:
                                print(f"验证成功! {result['message']}")
                            else:
                                print(f"验证失败! {result['message']}")
                        else:
                            print("未提供密码")
                except Exception as e:
                    print(f"验证失败: {e}")
            else:
                print("加密密码不能为空")
                
        elif choice == "3":
            print("退出测试")
            break
        else:
            print("无效选择，请重新输入")


def main():
    """主函数"""
    print("密码工具类测试程序")
    print("=" * 50)
    
    # 运行所有测试
    test_password_encryption()
    test_common_password_verification()
    test_custom_password_verification()
    test_comprehensive_verification()
    
    # 交互式测试
    print("\n是否进行交互式测试? (y/n): ", end="")
    if input().strip().lower() == 'y':
        interactive_test()


if __name__ == "__main__":
    main()