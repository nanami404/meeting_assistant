import json
import os
import requests
from datetime import datetime


class ResetPasswordAPITester:
    def __init__(self, base_url: str | None = None):
        if base_url is None:
            port = os.getenv("API_PORT", "8000")
            base_url = f"http://localhost:{port}"
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_credentials = {"username": "admin", "password": "Admin123456"}
        self.user_credentials = {"username": "demo_user", "password": "123456"}
        self.admin_tokens = {}
        self.created_user_ids = []
        self.test_results = []  # (测试名称, 是否成功)

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{level}] {message}")

    def make_request(self, method: str, endpoint: str, headers=None, json_data=None) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        self.log(f"{method.upper()} {url}")
        if json_data is not None:
            self.log(f"请求数据: {json.dumps(json_data, ensure_ascii=False)}")
        return self.session.request(method=method, url=url, headers=default_headers, json=json_data)

    def assert_response(self, response: requests.Response, expected_status: int = 200, test_name: str = ""):
        if response.status_code != expected_status:
            self.log(f"✗ {test_name} - 状态码错误: 期望{expected_status}, 实际{response.status_code}", "FAIL")
            self.log(f"响应内容: {response.text}", "DEBUG")
            raise AssertionError("状态码错误")
        try:
            data = response.json()
        except Exception:
            self.log(f"✗ {test_name} - 响应不是JSON", "FAIL")
            raise
        if data.get("code") != 0:
            self.log(f"✗ {test_name} - 业务错误: {data}", "FAIL")
            raise AssertionError("业务错误")
        self.log(f"✓ {test_name} - 通过", "PASS")
        return data

    def get_auth_headers(self):
        if not self.admin_tokens.get("access_token"):
            raise ValueError("管理员未登录")
        return {"Authorization": f"Bearer {self.admin_tokens['access_token']}"}

    def admin_login(self):
        resp = self.make_request("POST", "/api/auth/login", json_data=self.admin_credentials)
        data = self.assert_response(resp, 200, "管理员登录")
        self.admin_tokens = data["data"]

    def create_user_with_custom_password(self) -> tuple[int, str]:
        payload = {
            "name": "重置密码测试用户",
            "user_name": f"reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "email": f"reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            "password": "CustomPwd123",
            "gender": "male",
            "company": "测试部门"
        }
        resp = self.make_request("POST", "/api/users/", headers=self.get_auth_headers(), json_data=payload)
        data = self.assert_response(resp, 200, "创建自定义密码用户")
        user_id = data["data"]["id"]
        self.created_user_ids.append(user_id)
        return user_id, payload["user_name"]

    def try_login(self, username: str, password: str) -> bool:
        resp = self.make_request("POST", "/api/auth/login", json_data={"username": username, "password": password})
        # 改为非强制断言，以便在预期失败时不打印FAIL日志
        if resp.status_code == 200:
            try:
                data = resp.json()
                ok = data.get("code") == 0 and "access_token" in data.get("data", {})
                if ok:
                    self.log(f"✓ 尝试登录({password}) - 成功", "PASS")
                else:
                    self.log(f"✗ 尝试登录({password}) - 业务错误: {data}", "FAIL")
                return ok
            except Exception:
                self.log(f"✗ 尝试登录({password}) - 响应不是JSON", "FAIL")
                return False
        else:
            # 对于401等失败情况，记录信息而不是FAIL（因为在部分测试步骤中属于预期）
            self.log(f"尝试登录({password}) - 失败，状态码: {resp.status_code}", "INFO")
            self.log(f"响应内容: {resp.text}", "DEBUG")
            return False

    def reset_password_admin(self, user_id: int):
        resp = self.make_request("POST", f"/api/users/{user_id}/reset_password", headers=self.get_auth_headers())
        data = self.assert_response(resp, 200, "管理员重置密码")
        assert data["data"]["reset"] is True, "重置返回标志不正确"

    def user_forbidden_reset(self, user_id: int, username: str, password: str):
        # 使用非管理员用户尝试重置，应该403
        resp_login = self.make_request("POST", "/api/auth/login", json_data={"username": username, "password": password})
        data_login = self.assert_response(resp_login, 200, "普通用户登录(用于权限验证)")
        headers = {"Authorization": f"Bearer {data_login['data']['access_token']}"}
        resp = self.make_request("POST", f"/api/users/{user_id}/reset_password", headers=headers)
        if resp.status_code != 403:
            self.log(f"预期403，实际{resp.status_code}: {resp.text}", "FAIL")
            raise AssertionError("普通用户重置密码未被禁止")
        self.log("✓ 普通用户重置密码被正确禁止(403)", "PASS")

    def cleanup(self):
        for uid in list(self.created_user_ids):
            try:
                resp = self.make_request("DELETE", f"/api/users/{uid}", headers=self.get_auth_headers())
                if resp.status_code == 200:
                    self.log(f"清理用户成功: {uid}")
            except Exception:
                pass
            finally:
                self.created_user_ids.remove(uid)

    def add_result(self, test_name: str, success: bool):
        """记录单个测试结果"""
        self.test_results.append((test_name, success))

    def print_summary(self) -> bool:
        """打印测试汇总并返回是否全部通过"""
        print(f"\n{'='*60}")
        print("测试总结")
        print(f"{'='*60}")
        passed = sum(1 for _, s in self.test_results if s)
        total = len(self.test_results)
        for name, s in self.test_results:
            status = "✅ 通过" if s else "❌ 失败"
            print(f"{name}: {status}")
        print(f"\n总计: {passed}/{total} 个测试通过")
        if passed == total:
            print("🎉 所有测试通过！重置密码流程正常。")
            all_passed = True
        else:
            print("⚠️  部分测试失败，请检查接口或测试逻辑。")
            all_passed = False
        return all_passed

    def run(self):
        try:
            # 1. 管理员登录
            try:
                self.admin_login()
                self.add_result("管理员登录", True)
            except Exception:
                self.add_result("管理员登录", False)
                return False

            # 2. 创建自定义密码用户
            try:
                user_id, username = self.create_user_with_custom_password()
                self.add_result("创建自定义密码用户", True)
            except Exception:
                self.add_result("创建自定义密码用户", False)
                return False

            # 3. 使用自定义密码登录应成功
            custom_login_ok = self.try_login(username, "CustomPwd123")
            self.add_result("自定义密码可登录", custom_login_ok)
            if not custom_login_ok:
                return False

            # 4. 管理员重置密码
            try:
                self.reset_password_admin(user_id)
                self.add_result("管理员重置密码", True)
            except Exception:
                self.add_result("管理员重置密码", False)
                return False

            # 5. 重置后自定义密码应不可登录
            custom_after_reset_fail = not self.try_login(username, "CustomPwd123")
            self.add_result("重置后自定义密码不可登录", custom_after_reset_fail)

            # 6. 重置后默认密码应可登录
            default_login_ok = self.try_login(username, "Test@1234")
            self.add_result("重置后默认密码可登录", default_login_ok)
            if not default_login_ok:
                return False

            # 7. 普通用户禁止重置（403）
            try:
                self.user_forbidden_reset(user_id, username, "Test@1234")
                self.add_result("普通用户重置密码被禁止(403)", True)
            except Exception:
                self.add_result("普通用户重置密码被禁止(403)", False)
                return False

            return True
        finally:
            self.cleanup()


def main():
    tester = ResetPasswordAPITester()
    success = tester.run()
    # 统一输出测试汇总
    tester.print_summary()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()