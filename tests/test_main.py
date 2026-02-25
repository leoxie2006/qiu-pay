"""app/main.py 启动配置和路由注册测试。"""

import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# 测试环境设置
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="main_test_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-main"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["TESTING"] = "1"

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


class TestHealthEndpoint:
    """健康检查端点测试。"""

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestRouteRegistration:
    """路由注册验证测试。"""

    def test_payment_route_registered(self, client):
        """支付接口路由已注册（POST /xpay/epay/mapi.php）。"""
        resp = client.post("/xpay/epay/mapi.php", data={})
        # 应返回参数缺失错误，而非 404
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == -1

    def test_query_route_registered(self, client):
        """查询接口路由已注册（GET /xpay/epay/api.php）。"""
        resp = client.get("/xpay/epay/api.php")
        # 应返回参数错误，而非 404
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == -1

    def test_admin_login_route_registered(self, client):
        """管理后台登录路由已注册。"""
        resp = client.post("/v1/admin/auth/login", json={
            "username": "admin", "password": "wrong"
        })
        # 应返回认证错误，而非 404
        assert resp.status_code in (200, 401)


class TestStartupEvent:
    """启动事件测试。"""

    def test_init_db_called_on_startup(self):
        """应用启动时调用 init_db（通过验证数据库表存在来确认）。"""
        # lifespan 中 init_db 是延迟导入的，直接验证效果
        with TestClient(app):
            db = get_db()
            try:
                row = db.execute(
                    "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type='table' AND name='admin'"
                ).fetchone()
                assert row["cnt"] == 1
            finally:
                db.close()

    def test_background_tasks_skipped_in_testing(self):
        """测试模式下不启动后台任务。"""
        os.environ["TESTING"] = "1"
        with patch("asyncio.create_task") as mock_create:
            with TestClient(app):
                mock_create.assert_not_called()

    def test_database_tables_exist_after_startup(self, client):
        """启动后数据库表应存在。"""
        db = get_db()
        try:
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row["name"] for row in tables}
            assert "admin" in table_names
            assert "merchants" in table_names
            assert "orders" in table_names
            assert "system_config" in table_names
            assert "callback_logs" in table_names
            assert "balance_logs" in table_names
        finally:
            db.close()

    def test_default_admin_created(self, client):
        """启动后默认管理员应已创建。"""
        db = get_db()
        try:
            row = db.execute(
                "SELECT username FROM admin LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row["username"] == "admin"
        finally:
            db.close()


class TestSPAFallback:
    """SPA 静态文件服务与 Fallback 测试。"""

    def test_no_spa_fallback_when_dir_missing(self, client):
        """SPA 目录不存在时，非 API 路径返回 404（无 fallback）。"""
        resp = client.get("/some-random-page")
        assert resp.status_code == 404

    def test_api_routes_not_affected(self, client):
        """API 路由不受 SPA fallback 影响。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_spa_fallback_serves_index_html(self, tmp_path):
        """SPA 目录存在时，非 API 路径返回 index.html。"""
        import importlib
        from pathlib import Path
        from unittest.mock import patch

        # 创建临时 SPA 目录和 index.html
        spa_dir = tmp_path / "static" / "spa"
        spa_dir.mkdir(parents=True)
        index_html = spa_dir / "index.html"
        index_html.write_text("<!DOCTYPE html><html><body>SPA</body></html>", encoding="utf-8")

        assets_dir = spa_dir / "assets"
        assets_dir.mkdir()

        # 构建一个带 SPA fallback 的测试 app
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles

        test_app = FastAPI()

        @test_app.get("/health")
        async def health():
            return {"status": "ok"}

        test_app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

        @test_app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            idx = spa_dir / "index.html"
            if idx.exists():
                return FileResponse(str(idx), media_type="text/html")
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        client = TestClient(test_app)

        # 非 API 路径应返回 index.html
        resp = client.get("/v1/admin/dashboard")
        assert resp.status_code == 200
        assert "SPA" in resp.text

        # 健康检查仍然正常
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_spa_fallback_returns_404_when_index_missing(self, tmp_path):
        """SPA 目录存在但 index.html 不存在时返回 404。"""
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, JSONResponse

        spa_dir = tmp_path / "spa"
        spa_dir.mkdir()

        test_app = FastAPI()

        @test_app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            idx = spa_dir / "index.html"
            if idx.exists():
                return FileResponse(str(idx), media_type="text/html")
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        client = TestClient(test_app)
        resp = client.get("/anything")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}

    def test_spa_assets_served_as_static(self, tmp_path):
        """SPA assets 目录中的文件可通过 /assets/ 路径访问。"""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        js_file = assets_dir / "app.js"
        js_file.write_text("console.log('hello')", encoding="utf-8")

        test_app = FastAPI()
        test_app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

        client = TestClient(test_app)
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "hello" in resp.text
