"""管理后台系统设置路由单元测试。"""

import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="admin_settings_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-admin-settings"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

import app.database as _db_mod
from app.database import init_db
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
    resp = client.post("/v1/admin/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    return resp.json()["token"]


# ── GET /admin/settings 测试 ──


class TestSettingsPage:
    """GET /admin/settings 路由测试。"""

    def test_without_token_returns_401(self, client):
        resp = client.get("/v1/admin/settings")
        assert resp.status_code == 401

    def test_with_valid_token_returns_json(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = resp.json()
        assert data["code"] == 1

    def test_response_contains_qrcode_status(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert "qrcode_status" in data
        qs = data["qrcode_status"]
        assert "configured" in qs
        assert "qrcode_url" in qs

    def test_response_contains_credential_status(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert "credential_status" in data
        cs = data["credential_status"]
        assert "status" in cs

    def test_unconfigured_defaults(self, client):
        """未配置时，qrcode 未配置且凭证为 unconfigured。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["qrcode_status"]["configured"] is False
        assert data["credential_status"]["status"] == "unconfigured"

    def test_credential_status_includes_app_id_when_configured(self, client):
        """凭证配置后，credential_status 应包含 app_id。"""
        token = _get_token(client)
        # 先配置凭证
        client.post("/v1/admin/settings/alipay-credentials",
                     json={"app_id": "2021001234", "public_key": "pubkey123", "private_key": "privkey123"},
                     headers={"Authorization": f"Bearer {token}"})
        # 再查询设置
        resp = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        cs = data["credential_status"]
        assert "app_id" in cs
        assert cs["app_id"] == "2021001234"


# ── POST /admin/settings/change-password 测试 ──


class TestChangePassword:
    """POST /admin/settings/change-password 路由测试。"""

    def test_change_password_success(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/change-password",
                           json={"old_password": "admin123", "new_password": "newpass123"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert "成功" in data["msg"]

        # 验证新密码可以登录
        resp2 = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "newpass123",
        })
        assert resp2.json()["code"] == 1

    def test_change_password_wrong_old(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/change-password",
                           json={"old_password": "wrongpass", "new_password": "newpass123"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "原密码" in data["msg"]

    def test_change_password_without_token(self, client):
        resp = client.post("/v1/admin/settings/change-password",
                           json={"old_password": "admin123", "new_password": "newpass123"})
        assert resp.status_code == 401

    def test_change_password_too_short(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/change-password",
                           json={"old_password": "admin123", "new_password": "12345"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "6" in data["msg"]


# ── POST /admin/settings/alipay-credentials 测试 ──


class TestAlipayCredentials:
    """POST /admin/settings/alipay-credentials 路由测试。"""

    def test_save_credentials_success(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/alipay-credentials",
                           json={"app_id": "2021001234", "public_key": "pubkey123", "private_key": "privkey123"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1

    def test_save_credentials_without_token(self, client):
        resp = client.post("/v1/admin/settings/alipay-credentials",
                           json={"app_id": "2021001234", "public_key": "pubkey123", "private_key": "privkey123"})
        assert resp.status_code == 401

    def test_save_empty_credentials_returns_error(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/alipay-credentials",
                           json={"app_id": "", "public_key": "pubkey123", "private_key": "privkey123"},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1


# ── POST /admin/settings/qrcode 测试 ──


class TestQrcodeUpload:
    """POST /admin/settings/qrcode 路由测试。"""

    def test_upload_without_token(self, client):
        resp = client.post("/v1/admin/settings/qrcode",
                           files={"file": ("test.png", b"fakepng", "image/png")})
        assert resp.status_code == 401

    def test_upload_invalid_file_type(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/qrcode",
                           files={"file": ("test.txt", b"not an image", "text/plain")},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
        assert "格式" in data["msg"] or "PNG" in data["msg"]

    def test_upload_empty_file(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/settings/qrcode",
                           files={"file": ("test.png", b"", "image/png")},
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == -1
