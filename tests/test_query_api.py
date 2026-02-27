"""查询接口路由 GET /xpay/epay/api.php 单元测试。"""

import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="query_api_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-query-api"

import app.database as _db_mod
from app.database import init_db, get_db
from app.main import app
from app.services.merchant_service import MerchantService


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


@pytest.fixture
def merchant():
    return MerchantService().create_merchant("query_shop", "query@example.com")


def _insert_order(merchant_id, trade_no, out_trade_no="OT001",
                  money="10.00", status=0, name="测试商品",
                  paid_at=None, param="", buyer=""):
    """直接插入订单记录用于查询测试。"""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        db.execute(
            """INSERT INTO orders
               (trade_no, out_trade_no, merchant_id, type, name,
                original_money, money, base_balance, status, param,
                buyer, paid_at, created_at)
               VALUES (?, ?, ?, 'alipay', ?, ?, ?, '1000.00', ?, ?, ?, ?, ?)""",
            (trade_no, out_trade_no, merchant_id, name, money, money,
             status, param, buyer, paid_at, now),
        )
        db.commit()
    finally:
        db.close()


# ── act=order 订单查询测试 ──


class TestOrderQuery:
    """act=order 订单查询测试。"""

    def test_query_by_trade_no(self, client, merchant):
        """通过 trade_no 查询订单。"""
        _insert_order(merchant.id, "T001", "OT001", money="25.50", status=1,
                      name="商品A", paid_at="2025-01-01 12:00:00")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "trade_no": "T001",
        })
        data = resp.json()
        assert data["code"] == 1
        assert data["trade_no"] == "T001"
        assert data["out_trade_no"] == "OT001"
        assert data["money"] == "25.50"
        assert data["status"] == 1
        assert data["name"] == "商品A"
        assert data["pid"] == merchant.id

    def test_query_by_out_trade_no(self, client, merchant):
        """通过 out_trade_no 查询订单。"""
        _insert_order(merchant.id, "T002", "OT_UNIQUE", money="15.00")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "out_trade_no": "OT_UNIQUE",
        })
        data = resp.json()
        assert data["code"] == 1
        assert data["out_trade_no"] == "OT_UNIQUE"
        assert data["trade_no"] == "T002"

    def test_trade_no_takes_priority(self, client, merchant):
        """同时传入 trade_no 和 out_trade_no 时以 trade_no 为准。"""
        _insert_order(merchant.id, "T_PRIO", "OT_A", money="10.00", name="订单A")
        _insert_order(merchant.id, "T_OTHER", "OT_B", money="20.00", name="订单B")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key,
            "trade_no": "T_PRIO", "out_trade_no": "OT_B",
        })
        data = resp.json()
        assert data["code"] == 1
        assert data["trade_no"] == "T_PRIO"
        assert data["name"] == "订单A"

    def test_order_not_found(self, client, merchant):
        """查询不存在的订单返回 code=-1。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "trade_no": "NONEXISTENT",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "订单不存在" in data["msg"]

    def test_missing_trade_no_and_out_trade_no(self, client, merchant):
        """未传入 trade_no 和 out_trade_no 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key,
        })
        data = resp.json()
        assert data["code"] == -1

    def test_response_has_all_fields(self, client, merchant):
        """订单查询响应包含所有必要字段。"""
        _insert_order(merchant.id, "T_FULL", "OT_FULL", param="ext_data", buyer="buyer@test.com")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "trade_no": "T_FULL",
        })
        data = resp.json()
        required_fields = [
            "code", "msg", "trade_no", "out_trade_no", "api_trade_no",
            "type", "pid", "addtime", "endtime", "name", "money",
            "status", "param", "buyer",
        ]
        for field in required_fields:
            assert field in data, f"缺少字段: {field}"

    def test_unpaid_order_status_zero(self, client, merchant):
        """未支付订单 status 返回 0。"""
        _insert_order(merchant.id, "T_UNPAID", status=0)
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "trade_no": "T_UNPAID",
        })
        data = resp.json()
        assert data["status"] == 0

    def test_cannot_query_other_merchant_order(self, client, merchant):
        """不能查询其他商户的订单。"""
        other = MerchantService().create_merchant("other_shop", "other@example.com")
        _insert_order(other.id, "T_OTHER_M", "OT_OTHER_M")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": merchant.key, "trade_no": "T_OTHER_M",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "订单不存在" in data["msg"]


# ── act=query 商户信息查询测试 ──


class TestMerchantQuery:
    """act=query 商户信息查询测试。"""

    def test_query_merchant_info(self, client, merchant):
        """查询商户信息返回正确数据。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "query", "pid": str(merchant.id), "key": merchant.key,
        })
        data = resp.json()
        assert data["code"] == 1
        assert data["pid"] == merchant.id
        assert data["key"] == merchant.key
        assert data["active"] == 1

    def test_response_has_all_fields(self, client, merchant):
        """商户查询响应包含所有必要字段。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "query", "pid": str(merchant.id), "key": merchant.key,
        })
        data = resp.json()
        required_fields = [
            "code", "pid", "key", "active", "money", "type",
            "account", "username", "orders", "order_today", "order_lastday",
        ]
        for field in required_fields:
            assert field in data, f"缺少字段: {field}"

    def test_merchant_with_orders(self, client, merchant):
        """有订单的商户返回正确的订单统计。"""
        _insert_order(merchant.id, "T_STAT1", "OT_S1")
        _insert_order(merchant.id, "T_STAT2", "OT_S2")
        resp = client.get("/xpay/epay/api.php", params={
            "act": "query", "pid": str(merchant.id), "key": merchant.key,
        })
        data = resp.json()
        assert data["orders"] == 2
        assert data["order_today"] == 2


# ── pid/key 验证测试 ──


class TestPidKeyValidation:
    """pid 和 key 验证测试。"""

    def test_invalid_pid_order(self, client):
        """act=order 无效 pid 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": "abc", "key": "somekey", "trade_no": "T1",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_nonexistent_pid_order(self, client):
        """act=order 不存在的 pid 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": "99999", "key": "somekey", "trade_no": "T1",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "商户不存在" in data["msg"]

    def test_wrong_key_order(self, client, merchant):
        """act=order 错误 key 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id),
            "key": "wrong_key_value", "trade_no": "T1",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "密钥" in data["msg"]

    def test_invalid_pid_query(self, client):
        """act=query 无效 pid 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "query", "pid": "abc", "key": "somekey",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_wrong_key_query(self, client, merchant):
        """act=query 错误 key 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "query", "pid": str(merchant.id), "key": "wrong_key",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_missing_pid(self, client):
        """缺少 pid 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "key": "somekey", "trade_no": "T1",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_missing_key(self, client, merchant):
        """缺少 key 返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "order", "pid": str(merchant.id), "trade_no": "T1",
        })
        data = resp.json()
        assert data["code"] == -1


# ── act 参数测试 ──


class TestActParam:
    """act 参数测试。"""

    def test_missing_act(self, client):
        """缺少 act 参数返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "pid": "1", "key": "somekey",
        })
        data = resp.json()
        assert data["code"] == -1

    def test_invalid_act(self, client, merchant):
        """无效 act 值返回错误。"""
        resp = client.get("/xpay/epay/api.php", params={
            "act": "invalid", "pid": str(merchant.id), "key": merchant.key,
        })
        data = resp.json()
        assert data["code"] == -1
