"""
Users & Auth API 接口测试类
测试所有认证和用户管理相关的API接口
支持管理员和普通用户两个角色的测试
"""
import asyncio
import json
import sys
import os
from typing import Optional, Dict, Any
import requests
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class UsersAuthAPITester:
    """Users & Auth API测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化测试类
        
        Args:
            base_url: API服务器地址
        """
        self.base_url = base_url
        self.session = requests.Session()
        
        # 测试账号信息（来自doc/账号.md）
        self.admin_credentials = {
            "username": "admin",
            "password": "Admin123456"
        }
        
        self.user_credentials = {
            "username": "demo_user", 
            "password": "123456"
        }
        
        # 存储令牌信息
        self.admin_tokens = {}
        self.user_tokens = {}
        
        # 测试结果统计
        self.test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
        # 创建的测试用户ID（用于清理）
        self.created_user_ids = []
    
    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def assert_response(self, response: requests.Response, expected_status: int = 200, 
                       test_name: str = "", should_have_data: bool = True):
        """断言响应结果"""
        self.test_results["total"] += 1
        
        try:
            # 检查状态码
            if response.status_code != expected_status:
                raise AssertionError(f"状态码错误: 期望 {expected_status}, 实际 {response.status_code}")
            
            # 检查响应格式
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise AssertionError("响应不是有效的JSON格式")
            
            # 检查响应结构
            if "code" not in data or "message" not in data:
                raise AssertionError("响应缺少必要字段 (code, message)")
            
            # 检查业务状态码
            if data["code"] != 0:
                raise AssertionError(f"业务错误: code={data['code']}, message={data['message']}")
            
            # 检查数据字段
            if should_have_data and "data" not in data:
                raise AssertionError("响应缺少data字段")
            
            self.test_results["passed"] += 1
            self.log(f"✓ {test_name} - 测试通过", "PASS")
            return data
            
        except Exception as e:
            self.test_results["failed"] += 1
            error_msg = f"✗ {test_name} - 测试失败: {str(e)}"
            self.log(error_msg, "FAIL")
            self.test_results["errors"].append(error_msg)
            if hasattr(response, 'text'):
                self.log(f"响应内容: {response.text}", "DEBUG")
            raise e
    
    def make_request(self, method: str, endpoint: str, headers: Optional[Dict] = None, 
                    json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> requests.Response:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        # 默认headers
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        
        self.log(f"{method.upper()} {url}")
        if json_data:
            self.log(f"请求数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}")
        
        response = self.session.request(
            method=method,
            url=url,
            headers=default_headers,
            json=json_data,
            params=params
        )
        
        return response
    
    def get_auth_headers(self, role: str = "admin") -> Dict[str, str]:
        """获取认证头"""
        tokens = self.admin_tokens if role == "admin" else self.user_tokens
        if not tokens.get("access_token"):
            raise ValueError(f"{role}用户未登录，请先执行登录测试")
        
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    
    # ============================= 认证相关测试 =============================
    
    def test_admin_login(self):
        """测试管理员登录"""
        self.log("=" * 50)
        self.log("测试管理员登录")
        
        response = self.make_request(
            "POST", 
            "/api/auth/login",
            json_data=self.admin_credentials
        )
        
        data = self.assert_response(response, 200, "管理员登录")
        
        # 保存令牌
        self.admin_tokens = data["data"]
        self.log(f"管理员令牌已保存: access_token前10位={self.admin_tokens['access_token'][:10]}...")
        
        return data
    
    def test_user_login(self):
        """测试普通用户登录"""
        self.log("=" * 50)
        self.log("测试普通用户登录")
        
        response = self.make_request(
            "POST",
            "/api/auth/login", 
            json_data=self.user_credentials
        )
        
        data = self.assert_response(response, 200, "普通用户登录")
        
        # 保存令牌
        self.user_tokens = data["data"]
        self.log(f"普通用户令牌已保存: access_token前10位={self.user_tokens['access_token'][:10]}...")
        
        return data
    
    def test_get_admin_profile(self):
        """测试获取管理员用户信息"""
        self.log("=" * 50)
        self.log("测试获取管理员用户信息")
        
        # 确保有有效的管理员Token
        if not self.admin_tokens.get("access_token"):
            self.log("管理员Token不存在，重新登录...")
            self.test_admin_login()
        
        response = self.make_request(
            "GET",
            "/api/auth/profile",
            headers=self.get_auth_headers("admin")
        )
        
        data = self.assert_response(response, 200, "获取管理员用户信息")
        
        # 验证返回的用户信息
        user_info = data["data"]
        assert "id" in user_info, "用户信息缺少id字段"
        assert "role" in user_info, "用户信息缺少role字段"
        assert user_info["role"] == "admin", f"管理员角色错误: {user_info['role']}"
        
        self.log(f"管理员信息: ID={user_info['id']}, 角色={user_info['role']}")
        return data
    
    def test_get_user_profile(self):
        """测试获取普通用户信息"""
        self.log("=" * 50)
        self.log("测试获取普通用户信息")
        
        response = self.make_request(
            "GET",
            "/api/auth/profile",
            headers=self.get_auth_headers("user")
        )
        
        data = self.assert_response(response, 200, "获取普通用户信息")
        
        # 验证返回的用户信息
        user_info = data["data"]
        assert "id" in user_info, "用户信息缺少id字段"
        assert "role" in user_info, "用户信息缺少role字段"
        assert user_info["role"] == "user", f"普通用户角色错误: {user_info['role']}"
        
        self.log(f"普通用户信息: ID={user_info['id']}, 角色={user_info['role']}")
        return data
    
    def test_refresh_token(self, role: str = "admin"):
        """测试刷新令牌"""
        self.log("=" * 50)
        self.log(f"测试{role}用户刷新令牌")
        
        tokens = self.admin_tokens if role == "admin" else self.user_tokens
        refresh_token = tokens.get("refresh_token")
        
        if not refresh_token:
            raise ValueError(f"{role}用户没有refresh_token")
        
        response = self.make_request(
            "POST",
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        
        data = self.assert_response(response, 200, f"{role}用户刷新令牌")
        
        # 更新令牌
        if role == "admin":
            self.admin_tokens.update(data["data"])
        else:
            self.user_tokens.update(data["data"])
        
        self.log(f"{role}用户令牌已更新")
        return data
    
    def test_logout(self, role: str = "admin"):
        """测试用户登出"""
        self.log("=" * 50)
        self.log(f"测试{role}用户登出")
        
        # 确保有有效的Token
        tokens = self.admin_tokens if role == "admin" else self.user_tokens
        if not tokens.get("access_token"):
            self.log(f"{role}用户Token不存在，重新登录...")
            if role == "admin":
                self.test_admin_login()
            else:
                self.test_user_login()
        
        response = self.make_request(
            "POST",
            "/api/auth/logout",
            headers=self.get_auth_headers(role)
        )
        
        data = self.assert_response(response, 200, f"{role}用户登出")
        
        # 清除本地令牌
        if role == "admin":
            self.admin_tokens = {}
        else:
            self.user_tokens = {}
        
        self.log(f"{role}用户登出成功，本地令牌已清除")
        return data
    
    # ============================= 用户管理测试 =============================
    
    def test_create_user(self):
        """测试创建用户（管理员权限）"""
        self.log("=" * 50)
        self.log("测试创建用户")
        
        # 确保有有效的管理员Token
        if not self.admin_tokens.get("access_token"):
            self.log("管理员Token不存在，重新登录...")
            self.test_admin_login()
        
        # 生成测试用户数据
        test_user_data = {
            "name": "测试用户",
            "user_name": f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            "password": "TestPassword123",
            "gender": "male",
            "phone": f"1380000{datetime.now().strftime('%H%M')}",
            "company": "测试公司",
            "role": "user"
        }
        
        response = self.make_request(
            "POST",
            "/api/users/",
            headers=self.get_auth_headers("admin"),
            json_data=test_user_data
        )
        
        data = self.assert_response(response, 200, "创建用户")
        
        # 保存创建的用户ID用于后续测试和清理
        user_id = data["data"]["id"]
        self.created_user_ids.append(user_id)
        
        self.log(f"用户创建成功: ID={user_id}, 用户名={data['data']['user_name']}")
        return data
    
    def test_list_users(self):
        """测试获取用户列表（管理员权限）"""
        self.log("=" * 50)
        self.log("测试获取用户列表")
        
        # 测试基本列表
        response = self.make_request(
            "GET",
            "/api/users/",
            headers=self.get_auth_headers("admin")
        )
        
        data = self.assert_response(response, 200, "获取用户列表")
        
        # 验证列表结构
        assert "items" in data["data"], "用户列表缺少items字段"
        assert "total" in data["data"], "用户列表缺少total字段"
        assert isinstance(data["data"]["items"], list), "items应该是列表"
        
        self.log(f"用户列表获取成功: 总数={data['data']['total']}, 当前页数量={len(data['data']['items'])}")
        
        # 测试分页和过滤
        response = self.make_request(
            "GET",
            "/api/users/",
            headers=self.get_auth_headers("admin"),
            params={"page": 1, "page_size": 5, "role": "admin"}
        )
        
        data2 = self.assert_response(response, 200, "获取用户列表（分页+过滤）")
        self.log(f"分页过滤测试成功: 管理员用户数量={len(data2['data']['items'])}")
        
        return data
    
    def test_get_user_detail(self):
        """测试获取用户详情"""
        self.log("=" * 50)
        self.log("测试获取用户详情")
        
        if not self.created_user_ids:
            raise ValueError("没有可用的测试用户ID，请先执行创建用户测试")
        
        user_id = self.created_user_ids[0]
        
        # 管理员获取用户详情
        response = self.make_request(
            "GET",
            f"/api/users/{user_id}",
            headers=self.get_auth_headers("admin")
        )
        
        data = self.assert_response(response, 200, "管理员获取用户详情")
        
        # 验证用户详情结构
        user_detail = data["data"]
        assert user_detail["id"] == user_id, f"用户ID不匹配: 期望{user_id}, 实际{user_detail['id']}"
        
        self.log(f"用户详情获取成功: ID={user_detail['id']}, 姓名={user_detail['name']}")
        
        # 普通用户也可以获取用户详情
        response = self.make_request(
            "GET",
            f"/api/users/{user_id}",
            headers=self.get_auth_headers("user")
        )
        
        data2 = self.assert_response(response, 200, "普通用户获取用户详情")
        
        return data
    
    def test_update_user(self):
        """测试更新用户信息（管理员权限）"""
        self.log("=" * 50)
        self.log("测试更新用户信息")
        
        if not self.created_user_ids:
            raise ValueError("没有可用的测试用户ID，请先执行创建用户测试")
        
        user_id = self.created_user_ids[0]
        
        # 更新用户信息
        update_data = {
            "name": "更新后的测试用户",
            "company": "更新后的公司",
            "gender": "female"
        }
        
        response = self.make_request(
            "PUT",
            f"/api/users/{user_id}",
            headers=self.get_auth_headers("admin"),
            json_data=update_data
        )
        
        data = self.assert_response(response, 200, "更新用户信息")
        
        # 验证更新结果
        updated_user = data["data"]
        assert updated_user["name"] == update_data["name"], "用户姓名更新失败"
        assert updated_user["company"] == update_data["company"], "用户公司更新失败"
        assert updated_user["gender"] == update_data["gender"], "用户性别更新失败"
        
        self.log(f"用户信息更新成功: 姓名={updated_user['name']}, 公司={updated_user['company']}")
        
        return data
    
    def test_change_user_status(self):
        """测试修改用户状态（管理员权限）"""
        self.log("=" * 50)
        self.log("测试修改用户状态")
        
        if not self.created_user_ids:
            raise ValueError("没有可用的测试用户ID，请先执行创建用户测试")
        
        user_id = self.created_user_ids[0]
        
        # 修改用户状态为inactive
        response = self.make_request(
            "PATCH",
            f"/api/users/{user_id}/status",
            headers=self.get_auth_headers("admin"),
            params={"status": "inactive"}
        )
        
        data = self.assert_response(response, 200, "修改用户状态为inactive")
        
        assert data["data"]["status"] == "inactive", "用户状态修改失败"
        self.log(f"用户状态修改成功: {data['data']['status']}")
        
        # 修改回active状态
        response = self.make_request(
            "PATCH",
            f"/api/users/{user_id}/status",
            headers=self.get_auth_headers("admin"),
            params={"status": "active"}
        )
        
        data2 = self.assert_response(response, 200, "修改用户状态为active")
        
        return data2
    
    def test_delete_user(self):
        """测试删除用户（管理员权限）"""
        self.log("=" * 50)
        self.log("测试删除用户")
        
        if not self.created_user_ids:
            raise ValueError("没有可用的测试用户ID，请先执行创建用户测试")
        
        user_id = self.created_user_ids[0]
        
        response = self.make_request(
            "DELETE",
            f"/api/users/{user_id}",
            headers=self.get_auth_headers("admin")
        )
        
        data = self.assert_response(response, 200, "删除用户")
        
        assert data["data"]["deleted"] == True, "用户删除失败"
        self.log(f"用户删除成功: ID={user_id}")
        
        # 从列表中移除已删除的用户ID
        self.created_user_ids.remove(user_id)
        
        return data
    
    def test_user_permission_restrictions(self):
        """测试普通用户权限限制"""
        self.log("=" * 50)
        self.log("测试普通用户权限限制")
        
        # 普通用户尝试创建用户（应该失败）
        test_user_data = {
            "name": "非法创建用户",
            "user_name": "illegal_user",
            "email": "illegal@example.com",
            "password": "IllegalPassword123",
            "role": "user"
        }
        
        response = self.make_request(
            "POST",
            "/api/users/",
            headers=self.get_auth_headers("user"),
            json_data=test_user_data
        )
        
        # 应该返回403 Forbidden
        self.test_results["total"] += 1
        if response.status_code == 403:
            self.test_results["passed"] += 1
            self.log("✓ 普通用户创建用户权限限制 - 测试通过", "PASS")
        else:
            self.test_results["failed"] += 1
            error_msg = f"✗ 普通用户创建用户权限限制 - 测试失败: 期望403, 实际{response.status_code}"
            self.log(error_msg, "FAIL")
            self.test_results["errors"].append(error_msg)
        
        # 普通用户尝试获取用户列表（应该失败）
        response = self.make_request(
            "GET",
            "/api/users/",
            headers=self.get_auth_headers("user")
        )
        
        self.test_results["total"] += 1
        if response.status_code == 403:
            self.test_results["passed"] += 1
            self.log("✓ 普通用户获取用户列表权限限制 - 测试通过", "PASS")
        else:
            self.test_results["failed"] += 1
            error_msg = f"✗ 普通用户获取用户列表权限限制 - 测试失败: 期望403, 实际{response.status_code}"
            self.log(error_msg, "FAIL")
            self.test_results["errors"].append(error_msg)
    
    # ============================= 测试执行方法 =============================
    
    def run_auth_tests(self):
        """运行认证相关测试"""
        self.log("开始执行认证相关测试")
        
        try:
            # 登录测试
            self.test_admin_login()
            self.test_user_login()
            
            # 获取用户信息测试
            self.test_get_admin_profile()
            self.test_get_user_profile()
            
            # 刷新令牌测试（保存原始令牌）
            admin_backup = self.admin_tokens.copy()
            user_backup = self.user_tokens.copy()
            
            self.test_refresh_token("admin")
            self.test_refresh_token("user")
            
            # 恢复原始令牌用于后续测试
            self.admin_tokens = admin_backup
            self.user_tokens = user_backup
            
        except Exception as e:
            self.log(f"认证测试过程中出现异常: {e}", "ERROR")
    
    def run_user_management_tests(self):
        """运行用户管理测试"""
        self.log("开始执行用户管理测试")
        
        try:
            # 确保管理员和普通用户已登录
            if not self.admin_tokens.get("access_token"):
                self.test_admin_login()
            
            if not self.user_tokens.get("access_token"):
                self.test_user_login()
            
            # 用户管理测试
            self.test_create_user()
            self.test_list_users()
            self.test_get_user_detail()
            self.test_update_user()
            self.test_change_user_status()
            
            # 权限限制测试
            self.test_user_permission_restrictions()
            
            # 删除测试用户
            self.test_delete_user()
            
        except Exception as e:
            self.log(f"用户管理测试过程中出现异常: {e}", "ERROR")
    
    def run_logout_tests(self):
        """运行登出测试"""
        self.log("开始执行登出测试")
        
        try:
            # 确保用户已登录
            if not self.admin_tokens.get("access_token"):
                self.test_admin_login()
            
            if not self.user_tokens.get("access_token"):
                self.test_user_login()
            
            # 登出测试 - 先登出普通用户，再登出管理员
            self.test_logout("user")
            self.test_logout("admin")
            
        except Exception as e:
            self.log(f"登出测试过程中出现异常: {e}", "ERROR")
    
    def cleanup(self):
        """清理测试数据"""
        self.log("开始清理测试数据")
        
        # 如果还有未删除的测试用户，尝试删除
        if self.created_user_ids:
            # 确保管理员已登录
            if not self.admin_tokens.get("access_token"):
                try:
                    self.test_admin_login()
                except:
                    self.log("清理时无法登录管理员账号", "WARN")
                    return
            
            for user_id in self.created_user_ids.copy():
                try:
                    response = self.make_request(
                        "DELETE",
                        f"/api/users/{user_id}",
                        headers=self.get_auth_headers("admin")
                    )
                    if response.status_code == 200:
                        self.log(f"清理测试用户成功: {user_id}")
                        self.created_user_ids.remove(user_id)
                    else:
                        self.log(f"清理测试用户失败: {user_id}", "WARN")
                except Exception as e:
                    self.log(f"清理测试用户异常: {user_id} - {e}", "WARN")
    
    def run_all_tests(self):
        """运行所有测试"""
        self.log("=" * 80)
        self.log("开始执行 Users & Auth API 完整测试")
        self.log("=" * 80)
        
        start_time = datetime.now()
        
        try:
            # 1. 认证相关测试（包含登录）
            self.run_auth_tests()
            
            # 2. 重新登录确保token有效性，然后执行用户管理测试
            self.log("重新登录以确保token有效性...")
            self.test_admin_login()
            self.test_user_login()
            self.run_user_management_tests()
            
            # 3. 重新登录确保token有效性，然后执行登出测试
            self.log("重新登录以确保token有效性...")
            self.test_admin_login()
            self.test_user_login()
            self.run_logout_tests()
            
        except Exception as e:
            self.log(f"测试执行过程中出现严重异常: {e}", "ERROR")
        
        finally:
            # 清理测试数据
            self.cleanup()
            
            # 输出测试结果
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.log("=" * 80)
            self.log("测试结果统计")
            self.log("=" * 80)
            self.log(f"总测试数: {self.test_results['total']}")
            self.log(f"通过数: {self.test_results['passed']}")
            self.log(f"失败数: {self.test_results['failed']}")
            self.log(f"成功率: {(self.test_results['passed'] / max(self.test_results['total'], 1) * 100):.1f}%")
            self.log(f"执行时间: {duration:.2f}秒")
            
            if self.test_results["errors"]:
                self.log("\n失败的测试:")
                for error in self.test_results["errors"]:
                    self.log(f"  {error}")
            
            self.log("=" * 80)
            
            return self.test_results


def main():
    """主函数"""
    print("Users & Auth API 接口测试程序")
    print("=" * 50)
    
    # 检查服务是否运行
    base_url = "http://localhost:8000"
    
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code != 200:
            print(f"❌ 服务器未正常运行，请检查 {base_url} 是否可访问")
            return
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到服务器 {base_url}: {e}")
        print("请确保服务器正在运行（python main.py）")
        return
    
    print(f"✅ 服务器连接正常: {base_url}")
    
    # 创建测试实例并运行测试
    tester = UsersAuthAPITester(base_url)
    results = tester.run_all_tests()
    
    # 根据测试结果设置退出码
    if results["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()