"""
消息通知 API 测试脚本

- 覆盖发送消息、列表查询（分页/过滤）、标记单条已读、全部标记已读、删除单条、按类型批量删除
- 输出风格对齐 test_users_auth_api.py / test_create_update_user_api.py
"""

import json
import time
import requests
from datetime import datetime


class MessagesAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_credentials = {"username": "admin", "password": "Admin123456"}
        self.user_credentials = {"username": "demo_user", "password": "123456"}
        self.admin_tokens = {}
        self.user_tokens = {}
        self.created_message_ids = []
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

    # 用例：发送消息
    def test_send_message(self, title: str, content: str, receiver_id: int) -> int:
        payload = {"title": title, "content": content, "receiver_id": receiver_id}
        resp = self.make_request("POST", "/api/messages/send", headers=self.get_auth_headers("admin"), json_data=payload)
        data = self.assert_response(resp, 200, "发送消息")
        msg_id = data["data"]["id"]
        self.created_message_ids.append(msg_id)
        self.log(f"消息发送成功: ID={msg_id}, 标题={data['data']['title']}")
        return msg_id

    # 用例：获取消息列表
    def test_list_messages(self, role: str = "user", is_read: bool | None = None, page: int = 1, page_size: int = 20):
        params = {"page": page, "page_size": page_size}
        if is_read is not None:
            params["is_read"] = str(is_read).lower()
        resp = self.make_request("GET", "/api/messages/list", headers=self.get_auth_headers(role), params=params)
        data = self.assert_response(resp, 200, f"获取消息列表({role}, is_read={is_read})")
        msgs = data["data"]["messages"]
        self.log(f"获取到 {len(msgs)} 条消息，分页: {data['data']['pagination']}")
        return msgs, data["data"]["pagination"]

    # 用例：标记单条已读
    def test_mark_read(self, message_id: int):
        resp = self.make_request("POST", "/api/messages/mark-read", headers=self.get_auth_headers("user"), json_data={"message_id": message_id})
        data = self.assert_response(resp, 200, "标记单条消息为已读")
        assert data["data"]["updated"] is True, "标记已读失败"

    # 用例：全部标记已读
    def test_mark_all_read(self):
        resp = self.make_request("POST", "/api/messages/mark-all-read", headers=self.get_auth_headers("user"))
        data = self.assert_response(resp, 200, "全部标记为已读")
        updated_count = data["data"]["updated_count"]
        self.log(f"全部标记已读，更新条数: {updated_count}")
        return updated_count

    # 用例：删除单条
    def test_delete_message(self, message_id: int):
        resp = self.make_request("POST", "/api/messages/delete", headers=self.get_auth_headers("user"), json_data={"message_id": message_id})
        data = self.assert_response(resp, 200, "删除单条消息")
        assert data["data"]["deleted"] is True, "删除消息失败"

    # 用例：按类型批量删除
    def test_delete_by_type(self, type_: str):
        resp = self.make_request("POST", "/api/messages/delete-by-type", headers=self.get_auth_headers("user"), json_data={"type": type_})
        data = self.assert_response(resp, 200, f"按类型批量删除(type={type_})")
        deleted_count = data["data"]["deleted_count"]
        self.log(f"批量删除完成，删除条数: {deleted_count}")
        return deleted_count

    def run_all(self):
        # 登录
        self.admin_login()
        self.user_login()

        # 获取普通用户信息（用于 receiver_id 推断）
        # 这里使用 /api/auth/profile 获取 demo_user 的 id
        resp_profile = self.make_request("GET", "/api/auth/profile", headers=self.get_auth_headers("user"))
        profile_data = self.assert_response(resp_profile, 200, "获取普通用户信息")
        receiver_id = profile_data["data"]["id"]

        # 1) 发送两条消息，验证列表与全部标记已读
        msg_id_1 = self.test_send_message("欢迎消息", "欢迎使用会议助手", receiver_id)
        time.sleep(0.2)
        msg_id_2 = self.test_send_message("系统通知", "您的权限已更新", receiver_id)

        # 列表（未读）
        msgs_unread, _ = self.test_list_messages("user", is_read=False)
        assert any(m["id"] == msg_id_1 for m in msgs_unread), "未读列表未包含消息1"
        assert any(m["id"] == msg_id_2 for m in msgs_unread), "未读列表未包含消息2"

        # 全部标记已读
        updated_count = self.test_mark_all_read()
        assert updated_count >= 2, "全部标记已读数量不正确"

        # 列表（已读）
        msgs_read, _ = self.test_list_messages("user", is_read=True)
        assert any(m["id"] == msg_id_1 for m in msgs_read), "已读列表未包含消息1"
        assert any(m["id"] == msg_id_2 for m in msgs_read), "已读列表未包含消息2"

        # 2) 发送一条新消息，测试单条标记已读
        msg_id_3 = self.test_send_message("单条标记用例", "这是一条需要标记已读的消息", receiver_id)
        self.test_mark_read(msg_id_3)
        msgs_read_after, _ = self.test_list_messages("user", is_read=True)
        assert any(m["id"] == msg_id_3 for m in msgs_read_after), "单条标记已读后未在已读列表中"

        # 3) 删除单条
        msg_id_4 = self.test_send_message("删除单条用例", "这条消息将被删除", receiver_id)
        self.test_delete_message(msg_id_4)
        msgs_all, _ = self.test_list_messages("user", is_read=None)
        assert not any(m["id"] == msg_id_4 for m in msgs_all), "删除单条后仍能在列表中找到"

        # 4) 批量删除：再发两条，分别置为已读/未读后按类型删除
        msg_id_5 = self.test_send_message("批量删除-已读", "将被标记为已读并删除", receiver_id)
        msg_id_6 = self.test_send_message("批量删除-未读", "保持未读并删除", receiver_id)
        self.test_mark_read(msg_id_5)
        deleted_read = self.test_delete_by_type("read")
        assert deleted_read >= 1, "删除已读数量异常"
        # 删除未读
        deleted_unread = self.test_delete_by_type("unread")
        assert deleted_unread >= 1, "删除未读数量异常"

        # 最后校验列表为空或仅剩历史数据
        msgs_final, _ = self.test_list_messages("user")
        self.log(f"最终消息数: {len(msgs_final)}")


def main():
    tester = MessagesAPITester()
    try:
        tester.run_all()
        print("\n=== 测试完成 ===")
        print(json.dumps(tester.test_results, ensure_ascii=False, indent=2))
    except Exception:
        print("\n=== 测试失败 ===")
        print(json.dumps(tester.test_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()