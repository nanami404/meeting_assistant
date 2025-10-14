"""
测试用例：验证用户邮箱更新接口是否存在未更新的 Bug。

场景说明：
- 创建一个测试用户（管理员权限覆盖）。
- 通过 PUT /api/users/{user_id} 尝试更新邮箱。
- 再次查询用户详情，验证邮箱是否更新为新值。

预期：
- 接口应返回 200，且响应数据与数据库中的邮箱字段均更新为新邮箱。
- 若邮箱未更新，测试将失败，从而确认存在 Bug。
"""

import os
import sys
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# 允许从项目根目录导入 main 和依赖
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from main import app
from services.auth_dependencies import require_admin, require_auth
from services.service_models import User, UserRole, UserStatus


def _fake_admin_user() -> User:
    """返回一个模拟的管理员用户对象用于依赖覆盖。"""
    return User(
        id=str(uuid.uuid4()),
        name="Test Admin",
        user_name="admin_tester",
        email="admin@test.local",
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """提供带有管理员/认证依赖覆盖的 TestClient。"""
    # 覆盖依赖，跳过真实鉴权
    app.dependency_overrides[require_admin] = lambda: _fake_admin_user()
    app.dependency_overrides[require_auth] = lambda: _fake_admin_user()

    with TestClient(app) as c:
        yield c

    # 清理覆盖
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_auth, None)


def _unique_identity(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_update_user_email(client: TestClient):
    """验证更新用户邮箱后，邮箱字段应当被正确持久化更新。"""
    # 1) 创建用户
    orig_email = f"{_unique_identity('user')}@example.com"
    user_name = _unique_identity("uname")
    create_payload = {
        "name": "邮箱更新测试用户",
        "email": orig_email,
        "gender": "female",
        "phone": "13300000000",
        "id_number": None,
        "company": "测试部门",
        "role": "user",
        "status": "active",
        "user_name": user_name,
        "password": "StrongPass123!",
    }

    resp = client.post("/api/users/", json=create_payload)
    assert resp.status_code == 200, f"创建用户失败，状态码: {resp.status_code}, 响应: {resp.text}"
    data = resp.json()["data"]
    user_id = data["id"]
    assert data["email"] == orig_email, "创建用户的邮箱不匹配"

    # 2) 更新邮箱
    new_email = f"{_unique_identity('updated')}@example.com"
    update_payload = {"email": new_email}
    resp_upd = client.put(f"/api/users/{user_id}", json=update_payload)
    assert resp_upd.status_code == 200, f"更新用户失败，状态码: {resp_upd.status_code}, 响应: {resp_upd.text}"
    upd_data = resp_upd.json()["data"]

    # 期望接口响应中的邮箱即为新邮箱
    assert upd_data["email"] == new_email, (
        "邮箱更新后接口响应未反映新值 —— 确认存在邮箱未更新的 Bug"
    )

    # 3) 再次查询详情验证持久化
    resp_get = client.get(f"/api/users/{user_id}")
    assert resp_get.status_code == 200, f"查询用户详情失败，状态码: {resp_get.status_code}, 响应: {resp_get.text}"
    get_data = resp_get.json()["data"]
    assert get_data["email"] == new_email, (
        "邮箱更新未持久化 —— 再次查询到的邮箱仍为旧值，确认存在 Bug"
    )


def test_update_other_field_still_works(client: TestClient):
    """对比测试：更新非邮箱字段（如公司）应当正常生效。"""
    orig_email = f"{_unique_identity('user')}@example.com"
    user_name = _unique_identity("uname")
    create_payload = {
        "name": "字段更新对比用户",
        "email": orig_email,
        "gender": "male",
        "phone": "13300000001",
        "company": "初始公司",
        "role": "user",
        "status": "active",
        "user_name": user_name,
        "password": "StrongPass123!",
    }

    resp = client.post("/api/users/", json=create_payload)
    assert resp.status_code == 200, f"创建用户失败，状态码: {resp.status_code}, 响应: {resp.text}"
    user_id = resp.json()["data"]["id"]

    # 更新公司字段
    resp_upd = client.put(f"/api/users/{user_id}", json={"company": "更新后公司"})
    assert resp_upd.status_code == 200, f"更新用户失败，状态码: {resp_upd.status_code}, 响应: {resp_upd.text}"
    assert resp_upd.json()["data"]["company"] == "更新后公司"

    # 再次查询确认
    resp_get = client.get(f"/api/users/{user_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["company"] == "更新后公司"