import requests
from datetime import datetime


BASE_URL = "http://127.0.0.1:8000"


def log(msg):
    print(msg)


def admin_login():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Admin123456"}
    )
    assert resp.status_code == 200, f"管理员登录失败: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("code") == 0, f"业务错误: {data}"
    token = data["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_users_total(headers):
    resp = requests.get(f"{BASE_URL}/api/users/", headers=headers)
    assert resp.status_code == 200, f"获取用户列表失败: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("code") == 0, f"业务错误: {data}"
    return data["data"]["total"]


def create_temp_user(headers):
    payload = {
        "name": "删除测试用户",
        "user_name": f"del_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        # email 可选，留空以覆盖可空场景
        "email": None,
        "role": "user"
    }
    resp = requests.post(f"{BASE_URL}/api/users/", headers=headers, json=payload)
    assert resp.status_code == 200, f"创建测试用户失败: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("code") == 0, f"业务错误: {data}"
    return data["data"]["id"], data["data"]["user_name"]


def delete_user_hard(headers, user_id):
    resp = requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=headers, params={"hard": True})
    assert resp.status_code == 200, f"硬删除接口失败: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("code") == 0 and data["data"]["deleted"] is True, f"删除业务错误: {data}"
    assert data["data"].get("hard") is True, "删除类型未标记为硬删除"


def get_user_detail(headers, user_id):
    return requests.get(f"{BASE_URL}/api/users/{user_id}", headers=headers)


def test_hard_delete_user_flow():
    log("=" * 50)
    log("开始测试：用户硬删除功能")
    headers = admin_login()

    total_before = get_users_total(headers)
    log(f"当前用户总数: {total_before}")

    # 创建用户
    user_id, user_name = create_temp_user(headers)
    log(f"已创建测试用户: id={user_id}, user_name={user_name}")

    total_after_create = get_users_total(headers)
    assert total_after_create == total_before + 1, "创建后用户总数未增加"

    # 硬删除
    delete_user_hard(headers, user_id)
    log("已执行硬删除")

    # 再次获取用户详情，预期404
    resp_detail = get_user_detail(headers, user_id)
    assert resp_detail.status_code == 404, f"硬删除后仍能获取详情: {resp_detail.status_code} {resp_detail.text}"
    log("硬删除后获取详情返回404，符合预期")

    # 用户总数回到创建前
    total_after_delete = get_users_total(headers)
    assert total_after_delete == total_before, "硬删除后用户总数未回到删除前"
    log("用户总数恢复至删除前，未影响其他用户数据")

    log("🎉 用户硬删除功能测试通过")


if __name__ == "__main__":
    test_hard_delete_user_flow()