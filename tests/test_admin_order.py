"""管理后台订单管理路由单元测试。"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="admin_order_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-admin-order"
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


def _get_token(client) -> str:
    resp = client.post("/v1/admin/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    return resp.json()["token"]


def _create_merchant(db) -> int:
    """创建测试商户，返回 pid。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO merchants (username, email, key, active, money, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 0, ?, ?)",
        ("testshop", "t@t.com", "a" * 32, now, now),
    )
    db.commit()
    return db.execute("SELECT id FROM merchants WHERE username='testshop'").fetchone()["id"]


def _create_order(db, merchant_id, trade_no="T001", status=0, money=10.00,
                  notify_url="http://example.com/notify", created_at=None):
    """创建测试订单。"""
    now = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """INSERT INTO orders (trade_no, out_trade_no, merchant_id, type, name,
           original_money, money, adjust_amount, status, notify_url, return_url,
           param, device, base_balance, callback_status, callback_attempts, created_at)
           VALUES (?, ?, ?, 'alipay', '测试商品', ?, ?, 0, ?, ?, '', '', 'pc', 100.00, 0, 0, ?)""",
        (trade_no, f"OUT_{trade_no}", merchant_id, money, money, status, notify_url, now),
    )
    db.commit()


def _create_callback_log(db, order_id, attempt=1):
    """创建测试回调日志。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO callback_logs (order_id, attempt, url, method, http_status, response_body, created_at) "
        "VALUES (?, ?, 'http://example.com/notify', 'POST', 200, 'success', ?)",
        (order_id, attempt, now),
    )
    db.commit()


# ── GET /admin/orders 测试 ──


class TestOrderList:
    """GET /admin/orders 路由测试（JSON 响应）。"""

    def test_without_token_returns_401(self, client):
        resp = client.get("/v1/admin/orders")
        assert resp.status_code == 401

    def test_returns_json_with_required_fields(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data

    def test_empty_order_list(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert data["orders"] == []
        assert data["total"] == 0

    def test_shows_orders(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "T100", status=1, money=25.50)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        assert len(data["orders"]) == 1
        order = data["orders"][0]
        assert order["trade_no"] == "T100"
        assert order["status"] == 1

    def test_order_fields(self, client):
        """验证订单对象包含所有必要字段。"""
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "FIELDS01", status=0, money=10.00)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
        order = resp.json()["orders"][0]
        expected_fields = [
            "trade_no", "out_trade_no", "merchant_id", "type", "name",
            "original_money", "money", "status", "callback_status",
            "created_at", "paid_at",
        ]
        for field in expected_fields:
            assert field in order, f"Missing field: {field}"

    def test_filter_by_status(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "PAID01", status=1)
            _create_order(db, pid, "PEND01", status=0)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders?status=1", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        trade_nos = [o["trade_no"] for o in data["orders"]]
        assert "PAID01" in trade_nos
        assert "PEND01" not in trade_nos

    def test_filter_by_merchant_id(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "M1ORDER")
        finally:
            db.close()
        token = _get_token(client)
        # Filter by existing merchant
        resp = client.get(f"/v1/admin/orders?pid={pid}", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert any(o["trade_no"] == "M1ORDER" for o in data["orders"])
        # Filter by non-existing merchant
        resp = client.get("/v1/admin/orders?pid=9999", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["orders"] == []

    def test_filter_by_trade_no(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "SEARCH01")
            _create_order(db, pid, "OTHER01")
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders?trade_no=SEARCH", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        trade_nos = [o["trade_no"] for o in data["orders"]]
        assert "SEARCH01" in trade_nos
        assert "OTHER01" not in trade_nos

    def test_filter_by_date_range(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "OLD01", created_at="2024-01-01 10:00:00")
            _create_order(db, pid, "NEW01", created_at="2024-06-15 10:00:00")
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get(
            "/v1/admin/orders?start_date=2024-06-01&end_date=2024-06-30",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        trade_nos = [o["trade_no"] for o in data["orders"]]
        assert "NEW01" in trade_nos
        assert "OLD01" not in trade_nos

    def test_pagination(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            for i in range(25):
                _create_order(db, pid, f"PAGE{i:03d}", money=10.00 + i * 0.01)
        finally:
            db.close()
        token = _get_token(client)
        # Page 1 default per_page=20
        resp = client.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert data["total_pages"] == 2
        assert len(data["orders"]) == 20
        # Page 2
        resp = client.get("/v1/admin/orders?page=2", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["page"] == 2
        assert len(data["orders"]) == 5

    def test_custom_per_page(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            for i in range(10):
                _create_order(db, pid, f"PP{i:03d}")
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders?per_page=5", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["per_page"] == 5
        assert data["total_pages"] == 2
        assert len(data["orders"]) == 5


# ── GET /admin/orders/{trade_no} 测试 ──


class TestOrderDetail:
    """GET /admin/orders/{trade_no} 路由测试（JSON 响应）。"""

    def test_order_detail_success(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "DETAIL01", status=1, money=88.88)
            order = db.execute("SELECT id FROM orders WHERE trade_no='DETAIL01'").fetchone()
            _create_callback_log(db, order["id"])
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders/DETAIL01", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert data["order"]["trade_no"] == "DETAIL01"
        assert data["order"]["money"] == "88.88"
        assert data["order"]["status"] == 1
        assert data["order"]["status_text"] == "已支付"
        assert data["order"]["callback_status_text"] == "未通知"
        assert len(data["callback_logs"]) == 1
        assert data["callback_logs"][0]["status_code"] == 200
        assert data["callback_logs"][0]["response_body"] == "success"

    def test_order_detail_required_fields(self, client):
        """验证订单详情包含所有必要字段。"""
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "FIELDS_D01", status=0, money=10.00)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders/FIELDS_D01", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["code"] == 1
        order = data["order"]
        for field in [
            "trade_no", "out_trade_no", "merchant_id", "type", "name",
            "original_money", "money", "status", "status_text",
            "callback_status", "callback_status_text",
            "notify_url", "return_url", "created_at", "paid_at",
        ]:
            assert field in order, f"Missing field: {field}"
        assert "callback_logs" in data

    def test_order_detail_not_found(self, client):
        token = _get_token(client)
        resp = client.get("/v1/admin/orders/NONEXIST", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == -1
        assert data["msg"] == "订单不存在"

    def test_order_detail_without_token(self, client):
        resp = client.get("/v1/admin/orders/DETAIL01")
        assert resp.status_code == 401


# ── POST /admin/orders/{trade_no}/renotify 测试 ──


class TestRenotify:
    """POST /admin/orders/{trade_no}/renotify 路由测试。"""

    def test_renotify_nonexistent_order(self, client):
        token = _get_token(client)
        resp = client.post("/v1/admin/orders/NOORDER/renotify",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_renotify_unpaid_order(self, client):
        """待支付订单也可以手动触发回调通知。"""
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "UNPAID01", status=0,
                          notify_url="http://127.0.0.1:19999/fake")
        finally:
            db.close()
        token = _get_token(client)
        resp = client.post("/v1/admin/orders/UNPAID01/renotify",
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        # 通知可能失败（目标不可达），但路由本身应返回 JSON
        assert "code" in data

    def test_renotify_without_token(self, client):
        resp = client.post("/v1/admin/orders/T001/renotify")
        assert resp.status_code == 401

    def test_renotify_paid_order(self, client):
        """重新通知已支付订单（回调可能失败因为 notify_url 不可达，但路由应正常工作）。"""
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "RENOTIFY01", status=1,
                          notify_url="http://127.0.0.1:19999/fake")
        finally:
            db.close()
        token = _get_token(client)
        resp = client.post("/v1/admin/orders/RENOTIFY01/renotify",
                           headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        # 通知可能失败（目标不可达），但路由本身应返回 JSON
        assert "code" in data


# ── GET /admin/orders/export 测试 ──


class TestExportOrders:
    """GET /admin/orders/export 路由测试。"""

    def test_export_csv_returns_csv(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "EXP001", status=1, money=50.00)
            _create_order(db, pid, "EXP002", status=0, money=30.00)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders/export", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        assert "平台订单号" in content  # CSV header
        assert "EXP001" in content
        assert "EXP002" in content

    def test_export_csv_with_filter(self, client):
        db = get_db()
        try:
            pid = _create_merchant(db)
            _create_order(db, pid, "FEXP01", status=1)
            _create_order(db, pid, "FEXP02", status=0)
        finally:
            db.close()
        token = _get_token(client)
        resp = client.get("/v1/admin/orders/export?status=1",
                           headers={"Authorization": f"Bearer {token}"})
        content = resp.text
        assert "FEXP01" in content
        assert "FEXP02" not in content

    def test_export_without_token_returns_401(self, client):
        resp = client.get("/v1/admin/orders/export")
        assert resp.status_code == 401
