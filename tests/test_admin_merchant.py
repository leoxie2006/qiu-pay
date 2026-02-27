"""管理后台商户管理路由单元测试。"""

import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="admin_merchant_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-admin-merchant"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

import app.database as _db_mod
from app.database import init_db, get_db
from app.main import app


@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前重建数据库。"""
    os.environ["DB_PATH"] = _tmp.name
    _db_mod.DB_PATH = _tmp.name
    conn = sqlite3.connect(_tmp.name)
    conn.executescript("""
        DROP TABLE IF EXISTS callback_logs;
        DROP TABLE IF EXISTS balance_logs;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS merchant_credentials;
        DROP TABLE IF EXISTS merchants;
        DROP TABLE IF EXISTS system_config;
        DROP TABLE IF EXISTS admin;
    """)
    conn.close()
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _get_token(client) -> str:
    """登录获取 JWT token。"""
    resp = client.post("/v1/admin/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    return resp.json()["token"]


# ── GET /admin/merchants 测试 ──


class TestMerchantListPage:
    """GET /admin/merchants 路由测试。"""

    def test_without_token_returns_401(self, client):
        """未携带 token 访问商户列表返回 401。"""
        resp = client.get("/v1/admin/merchants")
        assert resp.status_code == 401

    def test_with_invalid_token_returns_401(self, client):
        """无效 token 访问商户列表返回 401。"""
        resp = client.get("/v1/admin/merchants", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401

    def test_with_valid_token_returns_200_json(self, client):
        """有效 token 访问商户列表返回 200 JSON。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/merchants", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = resp.json()
        assert data["code"] == 1
        assert "merchants" in data
        assert isinstance(data["merchants"], list)

    def test_response_contains_required_fields(self, client):
        """商户列表 JSON 包含所有必要字段。"""
        token = _get_token(client)
        # 先创建商户
        client.post("/v1/admin/merchants", json={"username": "fieldtest", "email": "f@t.com"},
                     headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/v1/admin/merchants", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        m = data["merchants"][0]
        for field in ("pid", "username", "email", "key", "active", "money", "orders", "order_today", "created_at"):
            assert field in m, f"缺少字段: {field}"

    def test_list_shows_created_merchant(self, client):
        """创建商户后列表包含该商户。"""
        token = _get_token(client)
        client.post("/v1/admin/merchants", json={"username": "testshop", "email": "t@t.com"},
                     headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/v1/admin/merchants", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        usernames = [m["username"] for m in data["merchants"]]
        assert "testshop" in usernames

    def test_empty_merchant_list(self, client):
        """无商户时返回空数组。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/merchants", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert data["merchants"] == []


# ── POST /admin/merchants 测试 ──


class TestCreateMerchant:
    """POST /admin/merchants 路由测试。"""

    def test_create_merchant_success(self, client):
        """创建商户成功返回商户信息。"""
        token = _get_token(client)
        resp = client.post("/v1/admin/merchants", json={"username": "shop1", "email": "s@s.com"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert data["merchant"]["username"] == "shop1"
        assert data["merchant"]["email"] == "s@s.com"
        assert len(data["merchant"]["key"]) == 32
        assert data["merchant"]["active"] == 1
        assert data["merchant"]["pid"] > 0

    def test_create_merchant_without_token_returns_401(self, client):
        """未携带 token 创建商户返回 401。"""
        resp = client.post("/v1/admin/merchants", json={"username": "shop1", "email": "s@s.com"})
        assert resp.status_code == 401

    def test_create_duplicate_username(self, client):
        """重复用户名创建商户失败。"""
        token = _get_token(client)
        client.post("/v1/admin/merchants", json={"username": "dup", "email": "a@a.com"},
                     headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/v1/admin/merchants", json={"username": "dup", "email": "b@b.com"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "已存在" in data["msg"]

    def test_create_multiple_merchants_unique_pid(self, client):
        """多次创建商户 pid 唯一。"""
        token = _get_token(client)
        pids = []
        for i in range(3):
            resp = client.post("/v1/admin/merchants",
                               json={"username": f"m{i}", "email": f"m{i}@t.com"},
                               headers={"Authorization": f"Bearer {token}"})
            pids.append(resp.json()["merchant"]["pid"])
        assert len(set(pids)) == 3


# ── PUT /admin/merchants/{pid} 测试 ──


class TestUpdateMerchant:
    """PUT /admin/merchants/{pid} 路由测试。"""

    def _create(self, client, token, username="testm"):
        resp = client.post("/v1/admin/merchants",
                           json={"username": username, "email": f"{username}@t.com"},
                           headers={"Authorization": f"Bearer {token}"})
        return resp.json()["merchant"]

    def test_toggle_ban_merchant(self, client):
        """封禁商户成功。"""
        token = _get_token(client)
        m = self._create(client, token)
        resp = client.put(f"/v1/admin/merchants/{m['pid']}",
                          json={"action": "toggle", "active": 0},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert "封禁" in data["msg"]

    def test_toggle_unban_merchant(self, client):
        """解封商户成功。"""
        token = _get_token(client)
        m = self._create(client, token)
        # 先封禁
        client.put(f"/v1/admin/merchants/{m['pid']}",
                   json={"action": "toggle", "active": 0},
                   headers={"Authorization": f"Bearer {token}"})
        # 再解封
        resp = client.put(f"/v1/admin/merchants/{m['pid']}",
                          json={"action": "toggle", "active": 1},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert "解封" in data["msg"]

    def test_toggle_missing_active_param(self, client):
        """封禁/解封缺少 active 参数返回错误。"""
        token = _get_token(client)
        m = self._create(client, token)
        resp = client.put(f"/v1/admin/merchants/{m['pid']}",
                          json={"action": "toggle"},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "active" in data["msg"]

    def test_reset_key(self, client):
        """重置密钥成功返回新密钥。"""
        token = _get_token(client)
        m = self._create(client, token)
        old_key = m["key"]
        resp = client.put(f"/v1/admin/merchants/{m['pid']}",
                          json={"action": "reset_key"},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert "key" in data
        assert len(data["key"]) == 32
        assert data["key"] != old_key

    def test_invalid_action(self, client):
        """未知操作返回错误。"""
        token = _get_token(client)
        m = self._create(client, token)
        resp = client.put(f"/v1/admin/merchants/{m['pid']}",
                          json={"action": "unknown"},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "未知" in data["msg"]

    def test_update_nonexistent_merchant(self, client):
        """操作不存在的商户返回错误。"""
        token = _get_token(client)
        resp = client.put("/v1/admin/merchants/99999",
                          json={"action": "toggle", "active": 0},
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "不存在" in data["msg"]

    def test_update_without_token_returns_401(self, client):
        """未携带 token 更新商户返回 401。"""
        resp = client.put("/v1/admin/merchants/1", json={"action": "toggle", "active": 0})
        assert resp.status_code == 401

    def test_ban_reflects_in_list(self, client):
        """封禁后商户列表显示封禁状态。"""
        token = _get_token(client)
        m = self._create(client, token)
        client.put(f"/v1/admin/merchants/{m['pid']}",
                   json={"action": "toggle", "active": 0},
                   headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/v1/admin/merchants", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        merchant = next(x for x in data["merchants"] if x["pid"] == m["pid"])
        assert merchant["active"] == 0
