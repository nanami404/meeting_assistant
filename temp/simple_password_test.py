#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码工具类 - 支持验证和生成功能
"""

import bcrypt


class PasswordUtils:
    """密码工具类"""

    def __init__(self):
        self.hash_value = None
        print("=" * 60)
        print("            密码工具 - 启动")
        print("=" * 60)
        print("功能说明:")
        print("1. 密码验证 - 验证密码是否匹配指定的哈希值")
        print("2. 密码加密 - 生成密码的bcrypt哈希值")
        print("=" * 60)

    def verify_password(self, password: str, hash_value: str = None) -> bool:
        """验证密码"""
        try:
            target_hash = hash_value or self.hash_value
            if not target_hash:
                print("错误: 没有设置哈希值")
                return False

            password_bytes = password.encode('utf-8')
            hashed_bytes = target_hash.encode('utf-8')
            result = bcrypt.checkpw(password_bytes, hashed_bytes)

            if result:
                print(f"[OK] 成功: 密码 '{password}' 匹配!")
            else:
                print(f"[NO] 失败: 密码 '{password}' 不匹配")

            return result
        except Exception as e:
            print(f"错误: {e}")
            return False

    def generate_hash(self, password: str) -> str:
        """生成密码哈希"""
        try:
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            hashed_str = hashed.decode('utf-8')

            print(f"原始密码: {password}")
            print(f"生成哈希: {hashed_str}")
            print("-" * 50)
            print("注意: 请安全保存此哈希值，原始密码无法从哈希值恢复!")

            return hashed_str
        except Exception as e:
            print(f"错误: {e}")
            return ""

    def _hash_password(self, password: str) -> str:
        """使用bcrypt加密密码

        Args:
            password: 明文密码

        Returns:
            str: 加密后的密码哈希值
        """
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        print(f"原始密码: {password}")
        print(f"生成哈希: {hashed.decode('utf-8')}")
        print("-" * 50)
        print("注意: 请安全保存此哈希值，原始密码无法从哈希值恢复!")
        return hashed.decode('utf-8')

    def test_common_passwords(self):
        """测试常见密码"""
        if not self.hash_value:
            print("错误: 请先设置要验证的哈希值")
            return None

        common_passwords = [
            "123456",
            "password",
            "admin",
            "admin123",
            "admin123456",
            "password123",
            "test",
            "test123",
            "meeting",
            "meeting123",
            "assistant",
            "nokia_cs",
            "Siryuan#525@614",
            "12345678",
            "qwerty",
            "abc123",
            "root",
            "root123",
            "user",
            "user123",
            "demo",
            "demo123",
            "123321",
            "000000",
            "111111",
            "888888",
            "666666"
        ]

        print("开始测试常见密码...")
        print("-" * 50)

        found_passwords = []
        for i, pwd in enumerate(common_passwords, 1):
            print(f"[{i:2d}/{len(common_passwords)}] 测试: {pwd}")
            if self.verify_password(pwd):
                found_passwords.append(pwd)
                print(f"*** 找到匹配密码: {pwd}")
                break

        print("-" * 50)
        print(f"总共测试: {len(common_passwords)} 个")
        print(f"成功匹配: {len(found_passwords)} 个")

        if found_passwords:
            print(f"匹配的密码: {found_passwords}")
            return found_passwords[0]
        else:
            print("没有常见密码匹配")
            return None

    def interactive_verify(self):
        """交互式密码验证"""
        print("\n交互式密码验证")
        print("-" * 30)

        while True:
            password = input("请输入要验证的密码 (输入 'back' 返回主菜单): ").strip()

            if password.lower() in ['back', '返回', 'quit', '退出']:
                break

            if not password:
                print("请输入密码")
                continue

            if self.verify_password(password):
                print("*** 恭喜! 找到了正确的密码!")
                return password

            print()

    def password_verify_mode(self):
        """密码验证模式"""
        print("\n进入密码验证模式")
        print("=" * 40)

        # 输入哈希值
        while True:
            hash_input = input("请输入要验证的密码哈希值: ").strip()
            if hash_input:
                self.hash_value = hash_input
                print(f"已设置哈希值: {hash_input[:50]}...")
                break
            else:
                print("哈希值不能为空，请重新输入")

        # 测试常见密码
        print("\n开始测试常见密码...")
        found_password = self.test_common_passwords()

        if found_password:
            print(f"\n*** 在常见密码中找到匹配: '{found_password}'")
            return

        # 交互式验证
        print("\n常见密码未找到匹配，进入手动验证模式...")
        self.interactive_verify()

    def password_generate_mode(self):
        """密码生成模式"""
        print("\n进入密码生成模式")
        print("=" * 40)

        while True:
            choice = input("\n选择操作:\n1. 生成单个密码哈希\n2. 批量生成多个密码哈希\n3. 返回主菜单\n请选择 (1-3): ").strip()

            if choice == '1':
                password = input("请输入要生成哈希的密码: ").strip()
                if password:
                    print("-" * 50)
                    self._hash_password(password)
                    print("-" * 50)
                else:
                    print("密码不能为空")

            elif choice == '2':
                passwords_input = input("请输入多个密码 (用英文逗号分隔): ").strip()
                if passwords_input:
                    passwords = [pwd.strip() for pwd in passwords_input.split(',') if pwd.strip()]
                    print("-" * 50)
                    for i, pwd in enumerate(passwords, 1):
                        print(f"\n第 {i} 个密码:")
                        self._hash_password(pwd)
                    print("-" * 50)
                else:
                    print("请输入密码")

            elif choice == '3':
                break
            else:
                print("无效选择，请输入 1-3")

    def run(self):
        """运行主程序"""
        while True:
            print("\n主菜单")
            print("=" * 30)
            print("1. 密码验证 - 验证密码是否匹配哈希值")
            print("2. 密码加密 - 生成密码的bcrypt哈希")
            print("3. 退出程序")
            print("-" * 30)

            choice = input("请选择功能 (1-3): ").strip()

            if choice == '1':
                self.password_verify_mode()
            elif choice == '2':
                self.password_generate_mode()
            elif choice == '3':
                print("感谢使用密码工具! 再见!")
                break
            else:
                print("无效选择，请输入 1-3")


if __name__ == "__main__":
    try:
        utils = PasswordUtils()
        utils.run()
    except KeyboardInterrupt:
        print("\n\n用户中断，程序退出!")
    except Exception as e:
        print(f"\n程序出错: {e}")