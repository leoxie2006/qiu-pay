"""支付接口路由 POST /xpay/epay/mapi.php 单元测试。"""

import os
import sqlite3
import tempfile
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="payment_route_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-payment-route"

import app.database as _db_mod
from app.database import init_db, get_db
from app.main import app
from app.services.merchant_service import MerchantService
from app.services.sign import generate_sign


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


@pytest.fixture
def merchant():
    return MerchantService().create_merchant("test_shop", "test@example.com")


def _setup_platform_config():
    """配置平台收款码和凭证。"""
    from app.services.platform_config import set_config, _encrypt
    set_config("qrcode_url", "https://qr.alipay.com/fkxtest123")
    set_config("qrcode_path", "/tmp/test_qr.png")
    set_config("alipay_app_id", _encrypt("test_app_id"))
    set_config("alipay_public_key", _encrypt("test_public_key"))
    set_config("alipay_private_key", _encrypt("test_private_key"))
    set_config("credential_status", "verified")


def _build_signed_form(merchant, **overrides):
    """构建带签名的表单参数。"""
    params = {
        "pid": str(merchant.id),
        "type": "alipay",
        "out_trade_no": "OT20250101001",
        "name": "测试商品",
        "money": "10.00",
        "sign_type": "MD5",
    }
    params.update(overrides)
    sign = generate_sign(params, merchant.key)
    params["sign"] = sign
    return params


class TestMissingParams:
    """缺少必填参数测试。"""

    def test_missing_pid(self, client):
        resp = client.post("/xpay/epay/mapi.php", data={
            "type": "alipay", "out_trade_no": "OT1", "name": "item",
            "money": "10.00", "sign": "abc", "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "pid" in data["msg"]

    def test_missing_money(self, client):
        resp = client.post("/xpay/epay/mapi.php", data={
            "pid": "1", "type": "alipay", "out_trade_no": "OT1",
            "name": "item", "sign": "abc", "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "money" in data["msg"]

    def test_missing_all(self, client):
        resp = client.post("/xpay/epay/mapi.php", data={})
        data = resp.json()
        assert data["code"] == -1


class TestMerchantValidation:
    """商户验证测试。"""

    def test_invalid_pid(self, client):
        resp = client.post("/xpay/epay/mapi.php", data={
            "pid": "abc", "type": "alipay", "out_trade_no": "OT1",
            "name": "item", "money": "10.00", "sign": "x", "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "商户ID无效" in data["msg"]

    def test_nonexistent_merchant(self, client):
        resp = client.post("/xpay/epay/mapi.php", data={
            "pid": "99999", "type": "alipay", "out_trade_no": "OT1",
            "name": "item", "money": "10.00", "sign": "x", "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "商户不存在" in data["msg"]

    def test_banned_merchant(self, client, merchant):
        MerchantService().toggle_status(merchant.id, False)
        resp = client.post("/xpay/epay/mapi.php", data={
            "pid": str(merchant.id), "type": "alipay", "out_trade_no": "OT1",
            "name": "item", "money": "10.00", "sign": "x", "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "封禁" in data["msg"]


class TestSignatureValidation:
    """签名验证测试。"""

    def test_wrong_sign_rejected(self, client, merchant):
        resp = client.post("/xpay/epay/mapi.php", data={
            "pid": str(merchant.id), "type": "alipay", "out_trade_no": "OT1",
            "name": "item", "money": "10.00", "sign": "wrong_sign",
            "sign_type": "MD5",
        })
        data = resp.json()
        assert data["code"] == -1
        assert "签名错误" in data["msg"]


class TestSuccessfulOrder:
    """成功创建订单测试。"""

    @patch("app.services.alipay_client.AlipayClient")
    def test_create_order_pc(self, mock_client_cls, client, merchant):
        """PC 设备应返回 qrcode。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.00"),
        }
        mock_client_cls.return_value = mock_instance

        form = _build_signed_form(merchant, device="pc")
        resp = client.post("/xpay/epay/mapi.php", data=form)
        data = resp.json()

        assert data["code"] == 1
        assert data["trade_no"]
        assert data["qrcode"] == "https://qr.alipay.com/fkxtest123"
        assert data["money"] == "10.00"

    @patch("app.services.alipay_client.AlipayClient")
    def test_create_order_mobile(self, mock_client_cls, client, merchant):
        """Mobile 设备也应返回 qrcode。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.00"),
        }
        mock_client_cls.return_value = mock_instance

        form = _build_signed_form(merchant, device="mobile")
        resp = client.post("/xpay/epay/mapi.php", data=form)
        data = resp.json()

        assert data["code"] == 1
        assert data["qrcode"] == "https://qr.alipay.com/fkxtest123"

    @patch("app.services.alipay_client.AlipayClient")
    def test_response_has_all_fields(self, mock_client_cls, client, merchant):
        """响应应包含所有必要字段。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.00"),
        }
        mock_client_cls.return_value = mock_instance

        form = _build_signed_form(merchant)
        resp = client.post("/xpay/epay/mapi.php", data=form)
        data = resp.json()

        assert "code" in data
        assert "trade_no" in data
        assert "qrcode" in data
        assert "money" in data


class TestPlatformConfigErrors:
    """平台配置缺失测试。"""

    def test_no_config_at_all(self, client, merchant):
        """未配置任何收款码和凭证应返回错误。"""
        form = _build_signed_form(merchant)
        resp = client.post("/xpay/epay/mapi.php", data=form)
        data = resp.json()

        assert data["code"] == -1
        assert "凭证" in data["msg"]

    def test_no_credentials_config(self, client, merchant):
        """未配置凭证应返回错误。"""
        from app.services.platform_config import set_config
        set_config("qrcode_url", "https://qr.alipay.com/fkxtest")
        set_config("qrcode_path", "/tmp/qr.png")

        form = _build_signed_form(merchant)
        resp = client.post("/xpay/epay/mapi.php", data=form)
        data = resp.json()

        assert data["code"] == -1
        assert "凭证" in data["msg"]


# ── 订单状态轮询接口测试 GET /api/order/status/{trade_no} ──


def _insert_order_directly(merchant_id, trade_no, money="10.00",
                           base_balance="1000.00", status=0):
    """直接插入订单记录用于状态查询测试。"""
    db = get_db()
    try:
        db.execute(
            """INSERT INTO orders
               (trade_no, out_trade_no, merchant_id, type, name,
                original_money, money, base_balance, status, created_at)
               VALUES (?, ?, ?, 'alipay', '测试商品', ?, ?, ?, ?, datetime('now'))""",
            (trade_no, f"OT_{trade_no}", merchant_id, money, money,
             base_balance, status),
        )
        db.commit()
    finally:
        db.close()


class TestOrderStatusPolling:
    """订单状态轮询接口测试。"""

    def test_nonexistent_order(self, client):
        """查询不存在的订单返回 code=-1。"""
        resp = client.get("/v1/api/order/status/NONEXISTENT")
        data = resp.json()
        assert data["code"] == -1
        assert "订单不存在" in data["msg"]

    def test_paid_order_returns_status_1(self, client, merchant):
        """已支付订单直接返回 status=1，不触发余额检测。"""
        _insert_order_directly(merchant.id, "T_PAID", status=1)
        resp = client.get("/v1/api/order/status/T_PAID")
        data = resp.json()
        assert data["code"] == 1
        assert data["trade_no"] == "T_PAID"
        assert data["status"] == 1
        assert data["status_text"] == "已支付"

    def test_expired_order_returns_status_2(self, client, merchant):
        """已超时订单返回 status=2，不触发余额检测。"""
        _insert_order_directly(merchant.id, "T_EXPIRED", status=2)
        resp = client.get("/v1/api/order/status/T_EXPIRED")
        data = resp.json()
        assert data["code"] == 1
        assert data["status"] == 2
        assert data["status_text"] == "已超时"

    def test_pending_order_returns_pending_status(self, client, merchant):
        """待支付订单直接返回数据库中的待支付状态，不触发余额检测。"""
        _insert_order_directly(merchant.id, "T_PENDING", status=0)
        resp = client.get("/v1/api/order/status/T_PENDING")
        data = resp.json()

        assert data["code"] == 1
        assert data["status"] == 0
        assert data["status_text"] == "待支付"

    def test_paid_in_db_returns_paid(self, client, merchant):
        """数据库中已支付的订单直接返回已支付状态。"""
        _insert_order_directly(merchant.id, "T_NOW_PAID", status=1)
        resp = client.get("/v1/api/order/status/T_NOW_PAID")
        data = resp.json()

        assert data["code"] == 1
        assert data["status"] == 1
        assert data["status_text"] == "已支付"

    def test_pending_order_no_balance_check(self, client, merchant):
        """轮询接口不应触发余额检测，仅返回数据库状态。"""
        _insert_order_directly(merchant.id, "T_ERR", status=0)
        resp = client.get("/v1/api/order/status/T_ERR")
        data = resp.json()

        assert data["code"] == 1
        assert data["status"] == 0
        assert data["status_text"] == "待支付"

    def test_response_has_all_fields(self, client, merchant):
        """响应包含所有必要字段。"""
        _insert_order_directly(merchant.id, "T_FIELDS", status=1)
        resp = client.get("/v1/api/order/status/T_FIELDS")
        data = resp.json()

        assert "code" in data
        assert "trade_no" in data
        assert "status" in data
        assert "status_text" in data


# ── 支付页面 GET /pay/{trade_no} 测试 ──


class TestPayPage:
    """支付页面路由测试 - JSON 响应。"""

    def test_nonexistent_order_returns_error(self, client):
        """不存在的订单返回 code=-1。"""
        resp = client.get("/v1/pay/NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == -1
        assert data["msg"] == "订单不存在"

    def test_pending_order_returns_json(self, client, merchant):
        """待支付订单返回包含 order、qrcode_url、return_url 的 JSON。"""
        from app.services.platform_config import set_config
        set_config("qrcode_url", "https://qr.alipay.com/fkxtest123")

        _insert_order_directly(merchant.id, "T_PAY_PENDING", money="10.50", status=0)
        resp = client.get("/v1/pay/T_PAY_PENDING")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert data["order"]["trade_no"] == "T_PAY_PENDING"
        assert data["order"]["money"] == "10.50"
        assert data["order"]["name"] == "测试商品"
        assert data["order"]["status"] == 0
        assert "created_at" in data["order"]
        assert data["qrcode_url"] == "https://qr.alipay.com/fkxtest123"
        assert "return_url" in data

    def test_paid_order_returns_json(self, client, merchant):
        """已支付订单返回 JSON，status=1。"""
        _insert_order_directly(merchant.id, "T_PAY_PAID", status=1)
        resp = client.get("/v1/pay/T_PAY_PAID")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert data["order"]["status"] == 1

    def test_expired_order_returns_json(self, client, merchant):
        """已超时订单返回 JSON，status=2。"""
        _insert_order_directly(merchant.id, "T_PAY_EXPIRED", status=2)
        resp = client.get("/v1/pay/T_PAY_EXPIRED")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 1
        assert data["order"]["status"] == 2

    def test_response_has_all_required_fields(self, client, merchant):
        """响应包含所有必要字段：code、order、qrcode_url、return_url。"""
        _insert_order_directly(merchant.id, "T_PAY_FIELDS", status=0)
        resp = client.get("/v1/pay/T_PAY_FIELDS")

        data = resp.json()
        assert data["code"] == 1
        assert "order" in data
        assert "qrcode_url" in data
        assert "return_url" in data

        # order 子对象包含必要字段
        order = data["order"]
        assert "trade_no" in order
        assert "name" in order
        assert "money" in order
        assert "status" in order
        assert "created_at" in order

    def test_return_url_populated_for_paid_order(self, client, merchant):
        """已支付订单有 return_url 时，JSON 中包含构建后的 return_url。"""
        db = get_db()
        try:
            db.execute(
                """INSERT INTO orders
                   (trade_no, out_trade_no, merchant_id, type, name,
                    original_money, money, base_balance, status,
                    return_url, created_at)
                   VALUES (?, ?, ?, 'alipay', '测试商品', '10.00', '10.00',
                           '1000.00', 1, 'https://example.com/return', datetime('now'))""",
                ("T_PAY_RET", "OT_RET", merchant.id),
            )
            db.commit()
        finally:
            db.close()

        resp = client.get("/v1/pay/T_PAY_RET")
        data = resp.json()
        assert data["code"] == 1
        assert data["return_url"] != ""

    def test_money_formatted_two_decimals(self, client, merchant):
        """金额格式化为两位小数。"""
        _insert_order_directly(merchant.id, "T_PAY_FMT", money="5", status=0)
        resp = client.get("/v1/pay/T_PAY_FMT")

        data = resp.json()
        assert data["order"]["money"] == "5.00"
