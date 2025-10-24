import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from services.service_models import UserStatus, UserRole

# ------------------------- 工具函数 -------------------------
async def login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    data = resp.json()["data"]
    return data["access_token"]

async def auth_headers(client: AsyncClient, username: str, password: str) -> dict:
    token = await login(client, username, password)
    return {"Authorization": f"Bearer {token}"}

# ------------------------- 测试用例 -------------------------
@pytest.mark.asyncio
async def test_update_basic_info_and_persistence(client: AsyncClient):
    # 1) 注册普通用户
    reg = await client.post("/api/auth/register", json={
        "name": "Jane",
        "user_name": "jane_user",
        "email": "jane@example.com",
        "password": "JaneNew1!",
        "gender": "female",
        "phone": "13812345678",
        "company": "Marketing"
    })
    assert reg.status_code == 200
    jane = reg.json()["data"]
    jane_id = jane["id"]

    # 2) 登录获取头
    headers = await auth_headers(client, "jane_user", "JaneNew1!")

    # 3) 更新基本信息
    update_payload = {
        "name": "Jane Doe",
        "user_name": "jane_user",
        "email": "jane.doe@example.com",
        "gender": "female",
        "phone": "13812345679",
        "company": "Sales"
    }
    resp = await client.put(f"/api/users/{jane_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200

    # 4) 再次获取详情确认持久化
    detail = await client.get(f"/api/users/{jane_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane.doe@example.com"
    assert data["phone"] == "13812345679"
    assert data["company"] == "Sales"


@pytest.mark.asyncio
async def test_forbid_normal_user_change_role_and_status(client: AsyncClient):
    # 注册用户并登录
    reg = await client.post("/api/auth/register", json={
        "name": "Tom",
        "user_name": "tom_user",
        "email": "tom@example.com",
        "password": "TomNew1!",
        "gender": "male",
        "phone": "13912345678",
        "company": "Support"
    })
    assert reg.status_code == 200
    tom_id = reg.json()["data"]["id"]
    headers = await auth_headers(client, "tom_user", "TomNew1!")

    # 普通用户尝试修改角色/状态应被拒绝
    resp = await client.put(f"/api/users/{tom_id}", json={
        "name": "Tom",
        "user_name": "tom_user",
        "user_role": UserRole.ADMIN.value,
        "status": UserStatus.SUSPENDED.value
    }, headers=headers)
    assert resp.status_code == 403
    err = resp.json()["detail"]
    assert err["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_can_change_role_and_status(client: AsyncClient, seed_admin):
    # 管理员登录
    admin_headers = await auth_headers(client, seed_admin["username"], seed_admin["password"])

    # 新增一个普通用户
    create = await client.post("/api/users/", json={
        "name": "Bob",
        "user_name": "bob_user",
        "email": "bob@example.com",
        "password": "BobNew1!",
        "gender": "male",
        "phone": "13712345678",
        "company": "HR",
        "user_role": UserRole.USER.value,
        "status": UserStatus.ACTIVE.value
    }, headers=admin_headers)
    assert create.status_code == 200
    bob = create.json()["data"]
    bob_id = bob["id"]

    # 管理员更新角色与状态
    update = await client.put(f"/api/users/{bob_id}", json={
        "name": "Bob",
        "user_name": "bob_user",
        "user_role": UserRole.ADMIN.value,
        "status": UserStatus.SUSPENDED.value
    }, headers=admin_headers)
    assert update.status_code == 200

    # 获取详情检查变更生效
    detail = await client.get(f"/api/users/{bob_id}", headers=admin_headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["user_role"] == UserRole.ADMIN.value
    assert data["status"] == UserStatus.SUSPENDED.value


@pytest.mark.asyncio
async def test_password_change_encryption_and_login_flow(client: AsyncClient):
    # 注册并登录用户
    reg = await client.post("/api/auth/register", json={
        "name": "Alice",
        "user_name": "alice_user",
        "email": "alice@example.com",
        "password": "AliceOld1!",
        "gender": "female",
        "phone": "13612345678",
        "company": "Ops"
    })
    assert reg.status_code == 200
    alice_id = reg.json()["data"]["id"]

    # 旧密码登录成功
    old_headers = await auth_headers(client, "alice_user", "AliceOld1!")

    # 修改密码
    change = await client.post(f"/api/users/{alice_id}/change_password", json={
        "old_password": "AliceOld1!",
        "new_password": "AliceNew1!"
    }, headers=old_headers)
    assert change.status_code == 200

    # 旧密码应登录失败
    bad = await client.post("/api/auth/login", json={"username": "alice_user", "password": "AliceOld1!"})
    assert bad.status_code == 401

    # 新密码应登录成功
    new = await client.post("/api/auth/login", json={"username": "alice_user", "password": "AliceNew1!"})
    assert new.status_code == 200


@pytest.mark.asyncio
async def test_update_boundary_validation_phone_invalid(client: AsyncClient):
    # 注册用户
    reg = await client.post("/api/auth/register", json={
        "name": "Eve",
        "user_name": "eve_user",
        "email": "eve@example.com",
        "password": "EveNew1!",
        "gender": "female",
        "phone": "13512345678",
        "company": "QA"
    })
    assert reg.status_code == 200
    eve_id = reg.json()["data"]["id"]
    headers = await auth_headers(client, "eve_user", "EveNew1!")

    # 手机号格式非法
    resp = await client.put(f"/api/users/{eve_id}", json={
        "name": "Eve",
        "user_name": "eve_user",
        "phone": "123456"
    }, headers=headers)
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert err["code"] == "validation_error"


@pytest.mark.asyncio
async def test_transaction_rollback_on_username_conflict(client: AsyncClient, seed_admin):
    # 管理员登录
    admin_headers = await auth_headers(client, seed_admin["username"], seed_admin["password"])

    # 创建两个用户
    u1 = await client.post("/api/users/", json={
        "name": "U1",
        "user_name": "user_one",
        "email": "u1@example.com",
        "password": "UserOne1!",
        "phone": "13112345678",
        "company": "A"
    }, headers=admin_headers)
    assert u1.status_code == 200
    u1_id = u1.json()["data"]["id"]

    u2 = await client.post("/api/users/", json={
        "name": "U2",
        "user_name": "user_two",
        "email": "u2@example.com",
        "password": "UserTwo1!",
        "phone": "13212345678",
        "company": "B"
    }, headers=admin_headers)
    assert u2.status_code == 200

    # 尝试将 U1 的 user_name 更新为 U2 的（冲突）
    conflict = await client.put(f"/api/users/{u1_id}", json={
        "name": "U1",
        "user_name": "user_two"
    }, headers=admin_headers)
    assert conflict.status_code == 400
    err = conflict.json()["detail"]
    assert err["code"] in ["validation_error", "bad_request"]

    # 再次获取 U1，保证原 user_name 未被修改（事务回滚）
    detail = await client.get(f"/api/users/{u1_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["user_name"] == "user_one"


@pytest.mark.asyncio
async def test_concurrent_updates_atomicity(client: AsyncClient, seed_admin):
    # 管理员登录
    admin_headers = await auth_headers(client, seed_admin["username"], seed_admin["password"])

    # 创建一个用户
    create = await client.post("/api/users/", json={
        "name": "ConcUser",
        "user_name": "conc_user",
        "email": "conc@example.com",
        "password": "ConcUser1!",
        "phone": "13012345678",
        "company": "R&D"
    }, headers=admin_headers)
    assert create.status_code == 200
    user_id = create.json()["data"]["id"]

    # 两个并发更新：
    payload_a = {"name": "Conc A", "user_name": "conc_user", "phone": "13012345679", "company": "LabA"}
    payload_b = {"name": "Conc B", "user_name": "conc_user", "phone": "13012345680", "company": "LabB"}

    async def do_update(payload):
        return await client.put(f"/api/users/{user_id}", json=payload, headers=admin_headers)

    r1, r2 = await asyncio.gather(do_update(payload_a), do_update(payload_b))
    assert r1.status_code == 200
    assert r2.status_code == 200

    # 读取最终结果，验证原子性：结果应完全匹配其中一个请求，不出现字段“混搭”
    detail = await client.get(f"/api/users/{user_id}", headers=admin_headers)
    assert detail.status_code == 200
    data = detail.json()["data"]

    # 有效组合集合
    final_a = (data["name"] == payload_a["name"] and data["phone"] == payload_a["phone"] and data["company"] == payload_a["company"])
    final_b = (data["name"] == payload_b["name"] and data["phone"] == payload_b["phone"] and data["company"] == payload_b["company"])
    assert final_a or final_b, f"最终数据不匹配任何一次完整更新: {data}"
