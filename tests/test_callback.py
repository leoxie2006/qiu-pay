"""回调通知服务单元测试。"""

import os
import sqlite3
import tempfile
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="callback_svc_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-callback-tests"

import app.database as _db_mod
from app.database import get_db, init_db
from app.services.merchant_service import MerchantService
from app.services.callback_service import CallbackService
from app.services.sign import generate_sign, verify_sign


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
def svc():
    return CallbackService()


@pytest.fixture
def merchant():
    """创建一个测试商户。"""
    return MerchantService().create_merchant("cb_test_shop", "cb@example.com")


def _insert_paid_order(merchant, **overrides):
    """插入一笔已支付订单，返回 order_id。"""
    defaults = {
        "trade_no": "T20250101000001",
        "out_trade_no": "OT001",
        "type": "alipay",
        "name": "测试商品",
        "original_money": "10.00",
        "money": "10.00",
        "status": 1,
        "notify_url": "https://merchant.example.com/notify",
        "return_url": "https://merchant.example.com/return",
        "param": "extra_data",
        "base_balance": "100.00",
        "callback_status": 0,
        "callback_attempts": 0,
    }
    defaults.update(overrides)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO orders
               (trade_no, out_trade_no, merchant_id, type, name,
                original_money, money, status, notify_url, return_url,
                param, base_balance, callback_status, callback_attempts, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                defaults["trade_no"], defaults["out_trade_no"], merchant.id,
                defaults["type"], defaults["name"],
                defaults["original_money"], defaults["money"], defaults["status"],
                defaults["notify_url"], defaults["return_url"],
                defaults["param"], defaults["base_balance"],
                defaults["callback_status"], defaults["callback_attempts"], now,
            ),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()


# ── send_notify 测试 ──────────────────────────────────────


class TestSendNotify:
    """send_notify 单元测试。"""

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_success(self, mock_client_cls, svc, merchant):
        """商户返回 'success' 时标记回调成功。"""
        order_id = _insert_paid_order(merchant)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "success"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = svc.send_notify(order_id)

        assert result is True
        # 验证数据库状态
        db = get_db()
        try:
            row = db.execute(
                "SELECT callback_status, callback_attempts FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            assert row["callback_status"] == 1  # 成功
            assert row["callback_attempts"] == 1
        finally:
            db.close()

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_failure(self, mock_client_cls, svc, merchant):
        """商户返回非 'success' 时不标记成功。"""
        order_id = _insert_paid_order(merchant)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "fail"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = svc.send_notify(order_id)

        assert result is False
        db = get_db()
        try:
            row = db.execute(
                "SELECT callback_status, callback_attempts FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            assert row["callback_status"] == 3  # 通知中（等待重试）
            assert row["callback_attempts"] == 1
        finally:
            db.close()

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_http_exception(self, mock_client_cls, svc, merchant):
        """HTTP 请求异常时不标记成功。"""
        order_id = _insert_paid_order(merchant)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client_cls.return_value = mock_client

        result = svc.send_notify(order_id)

        assert result is False

    def test_send_notify_nonexistent_order(self, svc):
        """不存在的订单返回 False。"""
        result = svc.send_notify(99999)
        assert result is False

    def test_send_notify_no_notify_url(self, svc, merchant):
        """无 notify_url 的订单返回 False。"""
        order_id = _insert_paid_order(merchant, notify_url=None)
        result = svc.send_notify(order_id)
        assert result is False

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_logs_callback(self, mock_client_cls, svc, merchant):
        """每次通知应记录到 callback_logs 表。"""
        order_id = _insert_paid_order(merchant)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "success"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.send_notify(order_id)

        db = get_db()
        try:
            logs = db.execute(
                "SELECT * FROM callback_logs WHERE order_id = ?", (order_id,)
            ).fetchall()
            assert len(logs) == 1
            assert logs[0]["attempt"] == 1
            assert logs[0]["http_status"] == 200
            assert logs[0]["response_body"] == "success"
            assert logs[0]["method"] == "POST"
        finally:
            db.close()

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_params_contain_all_fields(self, mock_client_cls, svc, merchant):
        """通知参数应包含所有必要字段。"""
        order_id = _insert_paid_order(merchant)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "success"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.send_notify(order_id)

        # 检查 POST 调用的参数
        call_args = mock_client.post.call_args
        posted_data = call_args.kwargs.get("data") or call_args[1].get("data")

        required_fields = [
            "pid", "trade_no", "out_trade_no", "type", "name",
            "money", "trade_status", "param", "sign", "sign_type",
        ]
        for field in required_fields:
            assert field in posted_data, f"缺少字段: {field}"

        assert posted_data["trade_status"] == "TRADE_SUCCESS"
        assert posted_data["sign_type"] == "MD5"

    @patch("app.services.callback_service.httpx.Client")
    def test_send_notify_sign_is_valid(self, mock_client_cls, svc, merchant):
        """通知参数的签名应可通过验证。"""
        order_id = _insert_paid_order(merchant)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "success"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.send_notify(order_id)

        call_args = mock_client.post.call_args
        posted_data = call_args.kwargs.get("data") or call_args[1].get("data")

        # 验证签名
        sign = posted_data["sign"]
        assert verify_sign(posted_data, merchant.key, sign) is True


# ── retry_notify 测试 ─────────────────────────────────────


class TestRetryNotify:
    """retry_notify 单元测试。"""

    @patch("app.services.callback_service.httpx.Client")
    def test_retry_success(self, mock_client_cls, svc, merchant):
        """重试成功时标记回调成功。"""
        order_id = _insert_paid_order(merchant, callback_status=3, callback_attempts=1)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "success"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.retry_notify(order_id, attempt=1)

        db = get_db()
        try:
            row = db.execute(
                "SELECT callback_status, callback_attempts FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            assert row["callback_status"] == 1
            assert row["callback_attempts"] == 2  # attempt 1 + 1
        finally:
            db.close()

    @patch("app.services.callback_service.httpx.Client")
    def test_retry_all_failed_marks_failed(self, mock_client_cls, svc, merchant):
        """第 5 次重试失败后标记为失败（callback_status=2）。"""
        order_id = _insert_paid_order(merchant, callback_status=3, callback_attempts=5)

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.retry_notify(order_id, attempt=5)

        db = get_db()
        try:
            row = db.execute(
                "SELECT callback_status, callback_attempts FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            assert row["callback_status"] == 2  # 失败
        finally:
            db.close()

    @patch("app.services.callback_service.httpx.Client")
    def test_retry_skips_already_successful(self, mock_client_cls, svc, merchant):
        """已成功的回调不再重试。"""
        order_id = _insert_paid_order(merchant, callback_status=1, callback_attempts=1)

        svc.retry_notify(order_id, attempt=1)

        # httpx 不应被调用
        mock_client_cls.assert_not_called()

    def test_retry_invalid_attempt(self, svc, merchant):
        """无效的重试次数应被忽略。"""
        order_id = _insert_paid_order(merchant)
        # attempt=0 无效
        svc.retry_notify(order_id, attempt=0)
        # attempt=6 超出范围
        svc.retry_notify(order_id, attempt=6)

    @patch("app.services.callback_service.httpx.Client")
    def test_retry_logs_each_attempt(self, mock_client_cls, svc, merchant):
        """每次重试应记录到 callback_logs。"""
        order_id = _insert_paid_order(merchant, callback_status=3, callback_attempts=1)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "fail"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc.retry_notify(order_id, attempt=1)

        db = get_db()
        try:
            logs = db.execute(
                "SELECT * FROM callback_logs WHERE order_id = ?", (order_id,)
            ).fetchall()
            assert len(logs) == 1
            assert logs[0]["attempt"] == 2  # attempt 1 + 1
        finally:
            db.close()

    def test_retry_intervals_constant(self, svc):
        """重试间隔常量应正确。"""
        assert svc.RETRY_INTERVALS == [5, 30, 60, 300, 1800]
        assert len(svc.RETRY_INTERVALS) == 5


# ── build_return_url 测试 ─────────────────────────────────


class TestBuildReturnUrl:
    """build_return_url 单元测试。"""

    def test_build_return_url_basic(self, svc, merchant):
        """基本 return_url 构建。"""
        order_id = _insert_paid_order(merchant)
        url = svc.build_return_url(order_id)

        assert url.startswith("https://merchant.example.com/return?")
        # 应包含所有必要参数
        assert "pid=" in url
        assert "trade_no=" in url
        assert "out_trade_no=" in url
        assert "trade_status=TRADE_SUCCESS" in url
        assert "sign=" in url
        assert "sign_type=MD5" in url

    def test_build_return_url_no_return_url(self, svc, merchant):
        """无 return_url 时返回空字符串。"""
        order_id = _insert_paid_order(merchant, return_url=None)
        url = svc.build_return_url(order_id)
        assert url == ""

    def test_build_return_url_nonexistent_order(self, svc):
        """不存在的订单返回空字符串。"""
        url = svc.build_return_url(99999)
        assert url == ""

    def test_build_return_url_preserves_existing_params(self, svc, merchant):
        """return_url 已有查询参数时应保留。"""
        order_id = _insert_paid_order(
            merchant,
            return_url="https://merchant.example.com/return?existing=value",
        )
        url = svc.build_return_url(order_id)
        assert "existing=value" in url
        assert "trade_no=" in url

    def test_build_return_url_sign_valid(self, svc, merchant):
        """return_url 中的签名应可通过验证。"""
        order_id = _insert_paid_order(merchant)
        url = svc.build_return_url(order_id)

        # 从 URL 中提取参数
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        sign = params.pop("sign", None)
        assert sign is not None
        assert verify_sign(params, merchant.key, sign) is True

    def test_build_return_url_empty_param(self, svc, merchant):
        """param 为空时也应正确构建。"""
        order_id = _insert_paid_order(merchant, param="")
        url = svc.build_return_url(order_id)
        assert url != ""
        assert "trade_no=" in url
