"""
创建与更新用户接口测试脚本（输出风格参考 test_users_auth_api.py）

- 测试管理员创建用户（不提供 role 与 password，验证默认值）
- 测试默认密码可登录（Test@1234）
- 测试管理员更新用户（必填：name、user_name；其他可选）
- 覆盖错误用例：
  * 创建缺少必填字段（name / user_name）→ 422
  * 创建非法用户名（长度/字符集不合法）→ 422
  * 普通用户创建用户（权限不足）→ 403
  * 更新缺少必填字段（name / user_name）→ 422
  * 更新为重复账号（user_name 冲突）→ 400
"""

import json
import requests
from datetime import datetime


class CreateUpdateUserAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_credentials = {"username": "admin", "password": "Admin123456"}
        self.user_credentials = {"username": "demo_user", "password": "123456"}
        self.admin_tokens = {}
        self.user_tokens = {}
        self.created_user_ids = []
        self.test_results = {"total": 0, "passed": 0, "failed": 0, "errors": []}

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{level}] {message}")

    def make_request(self, method: str, endpoint: str, headers=None, json_data=None, params=None) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        self.log(f"{method.upper()} {url}")
        if json_data:
            self.log(f"请求数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}")
        resp = self.session.request(method=method, url=url, headers=default_headers, json=json_data, params=params)
        return resp

    def assert_response(self, response: requests.Response, expected_status: int = 200, test_name: str = "", should_have_data: bool = True):
        self.test_results["total"] += 1
        try:
            if response.status_code != expected_status:
                raise AssertionError(f"状态码错误: 期望 {expected_status}, 实际 {response.status_code}")
            try:
                data = response.json()
            except Exception:
                raise AssertionError("响应不是有效的JSON格式")
            if "code" not in data or "message" not in data:
                raise AssertionError("响应缺少必要字段 (code, message)")
            if data["code"] != 0:
                raise AssertionError(f"业务错误: code={data['code']}, message={data['message']}")
            if should_have_data and "data" not in data:
                raise AssertionError("响应缺少data字段")
            self.test_results["passed"] += 1
            self.log(f"✓ {test_name} - 测试通过", "PASS")
            return data
        except Exception as e:
            self.test_results["failed"] += 1
            msg = f"✗ {test_name} - 测试失败: {str(e)}"
            self.log(msg, "FAIL")
            self.test_results["errors"].append(msg)
            if hasattr(response, "text"):
                self.log(f"响应内容: {response.text}", "DEBUG")
            raise e

    def assert_status_code(self, response: requests.Response, expected_status: int, test_name: str):
        """用于错误用例（非200）的断言，输出风格对齐 test_users_auth_api.py"""
        self.test_results["total"] += 1
        if response.status_code == expected_status:
            self.test_results["passed"] += 1
            self.log(f"✓ {test_name} - 测试通过", "PASS")
        else:
            self.test_results["failed"] += 1
            msg = f"✗ {test_name} - 测试失败: 期望{expected_status}, 实际{response.status_code}"
            self.log(msg, "FAIL")
            self.test_results["errors"].append(msg)
            if hasattr(response, "text"):
                self.log(f"响应内容: {response.text}", "DEBUG")

    def get_auth_headers(self, role: str = "admin"):
        tokens = self.admin_tokens if role == "admin" else self.user_tokens
        if not tokens.get("access_token"):
            raise ValueError(f"{role}用户未登录，请先执行登录")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    # 登录
    def admin_login(self):
        resp = self.make_request("POST", "/api/auth/login", json_data=self.admin_credentials)
        data = self.assert_response(resp, 200, "管理员登录")
        self.admin_tokens = data["data"]
        self.log(f"管理员令牌已保存: access_token前10位={self.admin_tokens['access_token'][:10]}...")

    def user_login(self):
        resp = self.make_request("POST", "/api/auth/login", json_data=self.user_credentials)
        data = self.assert_response(resp, 200, "普通用户登录")
        self.user_tokens = data["data"]
        self.log(f"普通用户令牌已保存: access_token前10位={self.user_tokens['access_token'][:10]}...")

    # 成功用例
    def test_create_user_success(self) -> int:
        payload = {
            "name": "测试用户",
            "user_name": f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            "gender": "male",
            "phone": f"1380000{datetime.now().strftime('%H%M')}",
            "company": "测试公司"
        }
        resp = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload)
        data = self.assert_response(resp, 200, "创建用户")
        user_id = data["data"]["id"]
        self.created_user_ids.append(user_id)
        self.log(f"用户创建成功: ID={user_id}, 用户名={data['data']['user_name']}")
        # 校验默认角色
        assert data["data"]["role"] == "user", "创建用户默认角色不是 user"
        return user_id

    def test_login_with_default_password(self, user_name: str):
        resp = self.make_request("POST", "/api/auth/login", json_data={"username": user_name, "password": "Test@1234"})
        data = self.assert_response(resp, 200, "默认密码登录")
        assert "access_token" in data["data"], "默认密码登录失败，未返回 access_token"

    def test_update_user_success(self, user_id: int, old_user_name: str):
        new_user_name = f"{old_user_name}_updated"
        payload = {"name": "更新后的测试用户", "user_name": new_user_name, "company": "更新后的公司", "gender": "female"}
        resp = self.make_request("PUT", f"/api/users/{user_id}", headers=self.get_auth_headers("admin"), json_data=payload)
        data = self.assert_response(resp, 200, "更新用户信息")
        updated = data["data"]
        assert updated["name"] == payload["name"], "用户姓名更新失败"
        assert updated["user_name"] == new_user_name, "用户账号更新失败"
        assert updated["company"] == payload["company"], "用户公司更新失败"
        assert updated["gender"] == payload["gender"], "用户性别更新失败"

    # 错误用例
    def test_create_user_missing_required(self):
        # 缺少 name
        payload1 = {"user_name": f"miss_name_{datetime.now().strftime('%H%M%S')}"}
        resp1 = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload1)
        self.assert_status_code(resp1, 422, "创建用户缺少name返回422")
        # 缺少 user_name
        payload2 = {"name": "缺少账号的用户"}
        resp2 = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload2)
        self.assert_status_code(resp2, 422, "创建用户缺少user_name返回422")

    def test_create_user_invalid_username(self):
        # 用户名过短
        payload1 = {"name": "非法用户名用户", "user_name": "ab"}
        resp1 = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload1)
        self.assert_status_code(resp1, 422, "创建用户用户名过短返回422")
        # 用户名包含非法字符
        payload2 = {"name": "非法字符用户", "user_name": "invalid!*"}
        resp2 = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload2)
        self.assert_status_code(resp2, 422, "创建用户用户名非法字符返回422")

    def test_create_user_forbidden_by_user(self):
        payload = {"name": "普通用户非法创建", "user_name": f"illegal_{datetime.now().strftime('%H%M%S')}"}
        resp = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("user"), json_data=payload)
        self.assert_status_code(resp, 403, "普通用户创建用户返回403")

    def test_update_user_missing_required(self, user_id: int):
        # 缺少 name
        payload1 = {"user_name": f"upd_miss_name_{datetime.now().strftime('%H%M%S')}"}
        resp1 = self.make_request("PUT", f"/api/users/{user_id}", headers=self.get_auth_headers("admin"), json_data=payload1)
        self.assert_status_code(resp1, 422, "更新用户缺少name返回422")
        # 缺少 user_name
        payload2 = {"name": "更新缺少账号"}
        resp2 = self.make_request("PUT", f"/api/users/{user_id}", headers=self.get_auth_headers("admin"), json_data=payload2)
        self.assert_status_code(resp2, 422, "更新用户缺少user_name返回422")

    def test_update_user_duplicate_username(self, user_id: int):
        # 先创建一个对照用户
        payload = {"name": "对照用户", "user_name": f"dup_{datetime.now().strftime('%H%M%S')}"}
        resp_create = self.make_request("POST", "/api/users/", headers=self.get_auth_headers("admin"), json_data=payload)
        data = self.assert_response(resp_create, 200, "创建对照用户")
        other_user_id = data["data"]["id"]
        self.created_user_ids.append(other_user_id)
        # 将目标用户 user_name 更新为对照用户的 user_name，触发唯一性冲突 → 400
        resp_update = self.make_request("PUT", f"/api/users/{user_id}", headers=self.get_auth_headers("admin"), json_data={"name": "重复用户名", "user_name": payload["user_name"]})
        self.assert_status_code(resp_update, 400, "更新用户为重复账号返回400")

    # 清理
    def cleanup(self):
        for uid in list(self.created_user_ids):
            resp = self.make_request("DELETE", f"/api/users/{uid}", headers=self.get_auth_headers("admin"))
            try:
                data = self.assert_response(resp, 200, f"删除用户 {uid}")
                if data["data"].get("deleted"):
                    self.log(f"用户删除成功: ID={uid}")
            except Exception:
                # 即使删除失败也继续
                pass
            finally:
                self.created_user_ids.remove(uid)

    def run_all(self):
        try:
            # 登录
            self.admin_login()
            self.user_login()

            # 成功路径
            user_id = self.test_create_user_success()
            # 获取创建用户名
            resp_detail = self.make_request("GET", f"/api/users/{user_id}", headers=self.get_auth_headers("admin"))
            detail = self.assert_response(resp_detail, 200, "获取用户详情")
            created_user_name = detail["data"]["user_name"]

            self.test_login_with_default_password(created_user_name)
            self.test_update_user_success(user_id, created_user_name)

            # 错误路径
            self.test_create_user_missing_required()
            self.test_create_user_invalid_username()
            self.test_create_user_forbidden_by_user()
            self.test_update_user_missing_required(user_id)
            self.test_update_user_duplicate_username(user_id)

        finally:
            # 清理所有创建的用户
            self.cleanup()
            # 输出总结
            total = self.test_results["total"]
            passed = self.test_results["passed"]
            failed = self.test_results["failed"]
            self.log(f"测试完成: total={total}, passed={passed}, failed={failed}", "INFO")


def main():
    tester = CreateUpdateUserAPITester()
    tester.run_all()


if __name__ == "__main__":
    main()