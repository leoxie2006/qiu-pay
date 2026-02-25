"""管理员认证模块单元测试。"""

import os
import sqlite3
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="auth_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-auth"
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


# ── 密码哈希测试 ──


class TestPasswordHashing:
    """密码哈希和验证测试。"""

    def test_hash_and_verify(self):
        """哈希后的密码可以正确验证。"""
        from app.services.auth import hash_password, verify_password
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed)

    def test_wrong_password_fails(self):
        """错误密码验证失败。"""
        from app.services.auth import hash_password, verify_password
        hashed = hash_password("mypassword")
        assert not verify_password("wrongpassword", hashed)

    def test_hash_is_different_from_plaintext(self):
        """哈希值与明文不同。"""
        from app.services.auth import hash_password
        hashed = hash_password("admin123")
        assert hashed != "admin123"

    def test_different_hashes_for_same_password(self):
        """同一密码两次哈希结果不同（bcrypt salt）。"""
        from app.services.auth import hash_password
        h1 = hash_password("test")
        h2 = hash_password("test")
        assert h1 != h2


# ── JWT 令牌测试 ──


class TestJWTToken:
    """JWT 令牌生成和验证测试。"""

    def test_create_and_verify_token(self):
        """生成的令牌可以正确验证。"""
        from app.services.auth import create_token, verify_token
        token = create_token("admin")
        payload = verify_token(token)
        assert payload["sub"] == "admin"

    def test_token_contains_exp(self):
        """令牌包含过期时间。"""
        from app.services.auth import create_token, verify_token
        token = create_token("admin")
        payload = verify_token(token)
        assert "exp" in payload

    def test_invalid_token_raises(self):
        """无效令牌抛出 ValueError。"""
        from app.services.auth import verify_token
        with pytest.raises(ValueError):
            verify_token("invalid.token.here")

    def test_tampered_token_raises(self):
        """篡改的令牌验证失败。"""
        from app.services.auth import create_token, verify_token
        token = create_token("admin")
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        with pytest.raises(ValueError):
            verify_token(tampered)


# ── 登录接口测试 ──


class TestLoginRoute:
    """POST /admin/auth/login 路由测试。"""

    def test_login_success(self, client):
        """正确用户名密码登录成功。"""
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == 1
        assert "token" in data

    def test_login_wrong_password(self, client):
        """错误密码登录失败。"""
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "wrongpass",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "错误" in data["msg"]

    def test_login_wrong_username(self, client):
        """不存在的用户名登录失败。"""
        resp = client.post("/v1/admin/auth/login", json={
            "username": "nonexistent", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_login_returns_valid_jwt(self, client):
        """登录返回的 token 可以被验证。"""
        from app.services.auth import verify_token
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        payload = verify_token(data["token"])
        assert payload["sub"] == "admin"


# ── 账号锁定测试 ──


class TestAccountLockout:
    """连续 5 次失败锁定 15 分钟测试。"""

    def test_lockout_after_5_failures(self, client):
        """连续 5 次错误密码后账号被锁定。"""
        for _ in range(5):
            client.post("/v1/admin/auth/login", json={
                "username": "admin", "password": "wrong",
            })
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "锁定" in data["msg"]

    def test_4_failures_not_locked(self, client):
        """4 次错误密码后仍可登录。"""
        for _ in range(4):
            client.post("/v1/admin/auth/login", json={
                "username": "admin", "password": "wrong",
            })
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == 1

    def test_success_resets_fail_count(self, client):
        """成功登录后失败计数重置。"""
        for _ in range(3):
            client.post("/v1/admin/auth/login", json={
                "username": "admin", "password": "wrong",
            })
        # 成功登录重置计数
        client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        # 再失败 4 次不应锁定
        for _ in range(4):
            client.post("/v1/admin/auth/login", json={
                "username": "admin", "password": "wrong",
            })
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == 1

    def test_lockout_expires(self, client):
        """锁定过期后可以重新登录。"""
        # 锁定账号
        for _ in range(5):
            client.post("/v1/admin/auth/login", json={
                "username": "admin", "password": "wrong",
            })
        # 手动将 locked_until 设置为过去时间
        db = get_db()
        try:
            db.execute(
                "UPDATE admin SET locked_until = datetime('now', '-1 minute') WHERE username = 'admin'"
            )
            db.commit()
        finally:
            db.close()
        # 现在应该可以登录
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        data = resp.json()
        assert data["code"] == 1


# ── JWT 中间件/依赖项测试 ──


class TestJWTMiddleware:
    """JWT 认证中间件测试。"""

    def test_valid_bearer_token(self, client):
        """有效 Bearer token 通过认证。"""
        from app.services.auth import create_token
        from starlette.requests import Request
        from starlette.testclient import TestClient as _TC
        from fastapi import FastAPI

        # 登录获取 token
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        token = resp.json()["token"]

        test_app = FastAPI()

        @test_app.get("/test-auth")
        async def test_auth(request: Request):
            from app.services.auth import get_current_admin
            admin = get_current_admin(request)
            return {"username": admin["sub"]}

        tc = _TC(test_app)
        resp = tc.get("/test-auth", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_missing_token_returns_401(self, client):
        """缺少 token 返回 401。"""
        from fastapi import FastAPI
        from starlette.requests import Request
        from starlette.testclient import TestClient as _TC

        test_app = FastAPI()

        @test_app.get("/test-auth")
        async def test_auth(request: Request):
            from app.services.auth import get_current_admin
            admin = get_current_admin(request)
            return {"username": admin["sub"]}

        tc = _TC(test_app)
        resp = tc.get("/test-auth")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """无效 token 返回 401。"""
        from fastapi import FastAPI
        from starlette.requests import Request
        from starlette.testclient import TestClient as _TC

        test_app = FastAPI()

        @test_app.get("/test-auth")
        async def test_auth(request: Request):
            from app.services.auth import get_current_admin
            admin = get_current_admin(request)
            return {"username": admin["sub"]}

        tc = _TC(test_app)
        resp = tc.get("/test-auth", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_cookie_token(self, client):
        """从 cookie 中获取 token。"""
        from app.services.auth import create_token
        from fastapi import FastAPI
        from starlette.requests import Request
        from starlette.testclient import TestClient as _TC

        token = create_token("admin")

        test_app = FastAPI()

        @test_app.get("/test-auth")
        async def test_auth(request: Request):
            from app.services.auth import get_current_admin
            admin = get_current_admin(request)
            return {"username": admin["sub"]}

        tc = _TC(test_app)
        resp = tc.get("/test-auth", cookies={"token": token})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"


# ── 仪表盘测试 ──


def _get_token(client) -> str:
    """登录获取 JWT token。"""
    resp = client.post("/v1/admin/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    return resp.json()["token"]


def _seed_orders(db, count=3, status=1):
    """向数据库插入测试商户和订单。"""
    # 确保商户存在
    existing = db.execute("SELECT id FROM merchants WHERE username = 'testmerchant'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO merchants (username, email, key, active) VALUES (?, ?, ?, ?)",
            ("testmerchant", "test@test.com", "a" * 32, 1),
        )
        db.commit()
    mid = db.execute("SELECT id FROM merchants WHERE username = 'testmerchant'").fetchone()["id"]

    for i in range(count):
        db.execute(
            """INSERT INTO orders (trade_no, out_trade_no, merchant_id, type, name,
               original_money, money, status, base_balance, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (f"T{1000 + i}", f"OT{1000 + i}", mid, "alipay", f"商品{i}",
             10.00 + i, 10.00 + i, status, 100.00),
        )
    db.commit()


class TestDashboard:
    """GET /admin/dashboard 路由测试。"""

    def test_dashboard_without_token_returns_401(self, client):
        """未携带 token 访问仪表盘返回 401。"""
        resp = client.get("/v1/admin/dashboard")
        assert resp.status_code == 401

    def test_dashboard_with_invalid_token_returns_401(self, client):
        """无效 token 访问仪表盘返回 401。"""
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401

    def test_dashboard_with_valid_token_returns_json(self, client):
        """有效 token 访问仪表盘返回 200 JSON。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = resp.json()
        assert data["code"] == 1

    def test_dashboard_contains_statistics(self, client):
        """仪表盘 JSON 包含统计字段。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        for key in ("today_stats", "yesterday_stats", "total_stats"):
            assert key in data
            stats = data[key]
            assert "total" in stats
            assert "success" in stats
            assert "amount" in stats

    def test_dashboard_contains_chart(self, client):
        """仪表盘 JSON 包含趋势图数据。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        chart = data["chart"]
        assert "labels" in chart
        assert "order_counts" in chart
        assert "amounts" in chart
        assert len(chart["labels"]) == 7

    def test_dashboard_contains_platform_status(self, client):
        """仪表盘 JSON 包含平台状态。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        platform = data["platform"]
        assert "merchant_count" in platform
        assert "qrcode_status" in platform
        assert "credential_status" in platform

    def test_dashboard_shows_recent_orders(self, client):
        """仪表盘 JSON 包含最近订单。"""
        db = get_db()
        try:
            _seed_orders(db, count=3, status=1)
        finally:
            db.close()

        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert len(data["recent_orders"]) > 0
        order = data["recent_orders"][0]
        assert "trade_no" in order
        assert "merchant_id" in order
        assert "name" in order
        assert "money" in order
        assert "status" in order
        assert "created_at" in order

    def test_dashboard_empty_orders(self, client):
        """无订单时仪表盘正常返回空列表。"""
        token = _get_token(client)
        resp = client.get("/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert data["recent_orders"] == []
