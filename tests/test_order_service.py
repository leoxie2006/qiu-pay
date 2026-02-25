"""订单服务单元测试。"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="order_svc_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-order-tests"

import app.database as _db_mod
from app.database import get_db, init_db
from app.services.merchant_service import MerchantService
from app.services.order_service import (
    AmountConflictError,
    OrderCreateError,
    OrderService,
)


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
def svc():
    return OrderService()


@pytest.fixture
def merchant():
    """创建一个测试商户。"""
    return MerchantService().create_merchant("test_shop", "test@example.com")


@pytest.fixture
def dummy_merchant():
    """创建一个用于直接插入订单的虚拟商户（返回 pid）。"""
    m = MerchantService().create_merchant("dummy_merchant", "dummy@example.com")
    return m.id


def _setup_platform_config():
    """配置平台收款码和凭证（模拟已配置状态）。"""
    from app.services.platform_config import set_config, _encrypt
    set_config("qrcode_url", "https://qr.alipay.com/fkxtest123")
    set_config("qrcode_path", "/tmp/test_qr.png")
    set_config("alipay_app_id", _encrypt("test_app_id"))
    set_config("alipay_public_key", _encrypt("test_public_key"))
    set_config("alipay_private_key", _encrypt("test_private_key"))
    set_config("credential_status", "verified")


def _make_order_params(merchant, **overrides):
    """构建标准订单参数。"""
    params = {
        "pid": str(merchant.id),
        "type": "alipay",
        "out_trade_no": "OT20250101001",
        "name": "测试商品",
        "money": "10.00",
        "device": "pc",
    }
    params.update(overrides)
    return params


# ── generate_trade_no 测试 ────────────────────────────────


class TestGenerateTradeNo:
    """trade_no 生成逻辑测试。"""

    def test_trade_no_is_string(self, svc):
        trade_no = svc.generate_trade_no()
        assert isinstance(trade_no, str)

    def test_trade_no_is_numeric(self, svc):
        trade_no = svc.generate_trade_no()
        assert trade_no.isdigit()

    def test_trade_no_unique(self, svc):
        """多次生成的 trade_no 应互不相同。"""
        trade_nos = {svc.generate_trade_no() for _ in range(20)}
        assert len(trade_nos) == 20

    def test_trade_no_contains_timestamp(self, svc):
        """trade_no 应包含当前日期。"""
        trade_no = svc.generate_trade_no()
        today = datetime.now().strftime("%Y%m%d")
        assert trade_no.startswith(today)


# ── adjust_amount 测试 ────────────────────────────────────


class TestAdjustAmount:
    """金额尾数调整测试。"""

    def test_no_conflict_returns_original(self, svc):
        """无冲突时返回原始金额。"""
        result = svc.adjust_amount(Decimal("10.00"))
        assert result == Decimal("10.00")

    def test_one_conflict_adds_one_cent(self, svc, dummy_merchant):
        """存在一笔同金额待支付订单时，加 0.01。"""
        db = get_db()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                ("T001", "OT001", dummy_merchant, "item", "10.00", "10.00", "100.00", now),
            )
            db.commit()
        finally:
            db.close()

        result = svc.adjust_amount(Decimal("10.00"))
        assert result == Decimal("10.01")

    def test_multiple_conflicts_increments(self, svc, dummy_merchant):
        """多笔同金额订单时，依次递增。"""
        db = get_db()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for i in range(5):
                amount = Decimal("20.00") + Decimal("0.01") * i
                db.execute(
                    """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                       original_money, money, base_balance, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (f"T{i:03d}", f"OT{i:03d}", dummy_merchant, "item",
                     "20.00", str(amount), "100.00", now),
                )
            db.commit()
        finally:
            db.close()

        result = svc.adjust_amount(Decimal("20.00"))
        assert result == Decimal("20.05")

    def test_ignores_non_pending_orders(self, svc, dummy_merchant):
        """已支付/已超时的订单不影响金额调整。"""
        db = get_db()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # status=1 已支付
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                ("T100", "OT100", dummy_merchant, "item", "30.00", "30.00", "100.00", now),
            )
            # status=2 已超时
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 2, ?)""",
                ("T101", "OT101", dummy_merchant, "item", "30.00", "30.00", "100.00", now),
            )
            db.commit()
        finally:
            db.close()

        result = svc.adjust_amount(Decimal("30.00"))
        assert result == Decimal("30.00")

    def test_100_conflicts_raises(self, svc, dummy_merchant):
        """100 笔同金额待支付订单时抛出 AmountConflictError。"""
        db = get_db()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for i in range(100):
                amount = Decimal("50.00") + Decimal("0.01") * i
                db.execute(
                    """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                       original_money, money, base_balance, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (f"T{i:04d}", f"OT{i:04d}", dummy_merchant, "item",
                     "50.00", str(amount), "100.00", now),
                )
            db.commit()
        finally:
            db.close()

        with pytest.raises(AmountConflictError, match="繁忙"):
            svc.adjust_amount(Decimal("50.00"))


# ── create_order 测试 ─────────────────────────────────────


class TestCreateOrder:
    """create_order 单元测试。"""

    @patch("app.services.alipay_client.AlipayClient")
    def test_create_order_success(self, mock_client_cls, svc, merchant):
        """成功创建订单。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.00"),
            "total_amount": Decimal("1000.00"),
            "freeze_amount": Decimal("0"),
        }
        mock_client_cls.return_value = mock_instance

        params = _make_order_params(merchant)
        order, qrcode_url = svc.create_order(params)

        assert order.trade_no is not None
        assert order.out_trade_no == "OT20250101001"
        assert order.merchant_id == merchant.id
        assert order.name == "测试商品"
        assert order.original_money == Decimal("10.00")
        assert order.status == 0
        assert order.base_balance == Decimal("1000.00")

    @patch("app.services.alipay_client.AlipayClient")
    def test_create_order_persisted(self, mock_client_cls, svc, merchant):
        """订单应持久化到数据库。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("500.00"),
        }
        mock_client_cls.return_value = mock_instance

        params = _make_order_params(merchant)
        order, _ = svc.create_order(params)

        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM orders WHERE trade_no = ?", (order.trade_no,)
            ).fetchone()
            assert row is not None
            assert row["status"] == 0
            assert row["merchant_id"] == merchant.id
        finally:
            db.close()

    def test_invalid_pid_raises(self, svc):
        """无效商户ID应抛出 OrderCreateError。"""
        _setup_platform_config()
        params = _make_order_params(MagicMock(id="abc"))
        with pytest.raises(OrderCreateError, match="商户ID无效"):
            svc.create_order(params)

    def test_nonexistent_merchant_raises(self, svc):
        """不存在的商户应抛出 OrderCreateError。"""
        _setup_platform_config()
        params = {"pid": "99999", "type": "alipay", "out_trade_no": "OT1",
                  "name": "item", "money": "10.00"}
        with pytest.raises(OrderCreateError, match="商户不存在"):
            svc.create_order(params)

    def test_banned_merchant_raises(self, svc, merchant):
        """封禁商户应抛出 OrderCreateError。"""
        _setup_platform_config()
        MerchantService().toggle_status(merchant.id, False)
        params = _make_order_params(merchant)
        with pytest.raises(OrderCreateError, match="封禁"):
            svc.create_order(params)

    def test_no_qrcode_raises(self, svc, merchant):
        """未配置收款码和凭证应抛出 OrderCreateError。"""
        # 不配置任何收款码和凭证
        params = _make_order_params(merchant)
        with pytest.raises(OrderCreateError, match="凭证"):
            svc.create_order(params)

    def test_no_credentials_raises(self, svc, merchant):
        """未配置凭证应抛出 OrderCreateError。"""
        from app.services.platform_config import set_config
        set_config("qrcode_url", "https://qr.alipay.com/fkxtest")
        set_config("qrcode_path", "/tmp/qr.png")
        # 不配置凭证

        params = _make_order_params(merchant)
        with pytest.raises(OrderCreateError, match="凭证"):
            svc.create_order(params)

    @patch("app.services.alipay_client.AlipayClient")
    def test_balance_query_failure_uses_zero(self, mock_client_cls, svc, merchant):
        """余额查询失败时 base_balance 使用 0。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = Exception("连接失败")
        mock_client_cls.return_value = mock_instance

        params = _make_order_params(merchant)
        order, _ = svc.create_order(params)
        assert order.base_balance == Decimal("0")

    @patch("app.services.alipay_client.AlipayClient")
    def test_create_order_with_optional_params(self, mock_client_cls, svc, merchant):
        """可选参数应正确保存。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {"available_amount": Decimal("100")}
        mock_client_cls.return_value = mock_instance

        params = _make_order_params(
            merchant,
            notify_url="https://example.com/notify",
            return_url="https://example.com/return",
            clientip="192.168.1.1",
            device="mobile",
            param="extra_data",
        )
        order, _ = svc.create_order(params)
        assert order.notify_url == "https://example.com/notify"
        assert order.return_url == "https://example.com/return"
        assert order.clientip == "192.168.1.1"
        assert order.device == "mobile"
        assert order.param == "extra_data"

    @patch("app.services.alipay_client.AlipayClient")
    def test_amount_adjustment_applied(self, mock_client_cls, svc, merchant):
        """同金额订单应自动调整尾数。"""
        _setup_platform_config()
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {"available_amount": Decimal("100")}
        mock_client_cls.return_value = mock_instance

        # 创建第一笔订单
        params1 = _make_order_params(merchant, out_trade_no="OT001")
        order1, _ = svc.create_order(params1)
        assert order1.money == Decimal("10.00")

        # 创建第二笔同金额订单
        params2 = _make_order_params(merchant, out_trade_no="OT002")
        order2, _ = svc.create_order(params2)
        assert order2.money == Decimal("10.01")
        assert order2.adjust_amount == Decimal("0.01")

    def test_invalid_money_raises(self, svc, merchant):
        """无效金额格式应抛出 OrderCreateError。"""
        _setup_platform_config()
        params = _make_order_params(merchant, money="not_a_number")
        with pytest.raises(OrderCreateError, match="金额"):
            svc.create_order(params)


# ── expire_orders 测试 ────────────────────────────────────


class TestExpireOrders:
    """expire_orders 单元测试。"""

    def test_expires_old_pending_orders(self, svc, dummy_merchant):
        """超过 10 分钟的待支付订单应被标记为超时。"""
        db = get_db()
        try:
            old_time = (datetime.now() - timedelta(minutes=11)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                ("TOLD001", "OT001", dummy_merchant, "item", "10.00", "10.00", "100.00", old_time),
            )
            db.commit()
        finally:
            db.close()

        svc.expire_orders()

        db = get_db()
        try:
            row = db.execute(
                "SELECT status, expired_at FROM orders WHERE trade_no = ?",
                ("TOLD001",),
            ).fetchone()
            assert row["status"] == 2
            assert row["expired_at"] is not None
        finally:
            db.close()

    def test_does_not_expire_recent_orders(self, svc, dummy_merchant):
        """10 分钟内的待支付订单不应被过期。"""
        db = get_db()
        try:
            recent_time = (datetime.now() - timedelta(minutes=5)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                ("TNEW001", "OT001", dummy_merchant, "item", "10.00", "10.00", "100.00", recent_time),
            )
            db.commit()
        finally:
            db.close()

        svc.expire_orders()

        db = get_db()
        try:
            row = db.execute(
                "SELECT status FROM orders WHERE trade_no = ?", ("TNEW001",)
            ).fetchone()
            assert row["status"] == 0
        finally:
            db.close()

    def test_does_not_expire_paid_orders(self, svc, dummy_merchant):
        """已支付订单不应被过期。"""
        db = get_db()
        try:
            old_time = (datetime.now() - timedelta(minutes=60)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                ("TPAID001", "OT001", dummy_merchant, "item", "10.00", "10.00", "100.00", old_time),
            )
            db.commit()
        finally:
            db.close()

        svc.expire_orders()

        db = get_db()
        try:
            row = db.execute(
                "SELECT status FROM orders WHERE trade_no = ?", ("TPAID001",)
            ).fetchone()
            assert row["status"] == 1
        finally:
            db.close()

    def test_expire_multiple_orders(self, svc, dummy_merchant):
        """多笔超时订单应全部被过期。"""
        db = get_db()
        try:
            old_time = (datetime.now() - timedelta(minutes=45)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            for i in range(3):
                db.execute(
                    """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                       original_money, money, base_balance, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (f"TMULTI{i:03d}", f"OT{i:03d}", dummy_merchant, "item",
                     "10.00", "10.00", "100.00", old_time),
                )
            db.commit()
        finally:
            db.close()

        svc.expire_orders()

        db = get_db()
        try:
            rows = db.execute(
                "SELECT status FROM orders WHERE trade_no LIKE 'TMULTI%'"
            ).fetchall()
            assert all(row["status"] == 2 for row in rows)
        finally:
            db.close()
