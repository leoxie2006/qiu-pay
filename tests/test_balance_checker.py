"""余额检测器单元测试。"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="balance_chk_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-balance-tests"

import app.database as _db_mod
from app.database import get_db, init_db
from app.services.alipay_client import AlipayClientError
from app.services.balance_checker import BalanceChecker
from app.services.merchant_service import MerchantService
from app.services.platform_config import set_config, _encrypt


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
    _setup_platform_config()
    yield


def _setup_platform_config():
    """配置平台凭证（模拟已配置状态）。"""
    set_config("alipay_app_id", _encrypt("test_app_id"))
    set_config("alipay_public_key", _encrypt("test_public_key"))
    set_config("alipay_private_key", _encrypt("test_private_key"))
    set_config("credential_status", "verified")


def _create_merchant() -> int:
    """创建测试商户，返回 pid。"""
    m = MerchantService().create_merchant("test_shop", "test@example.com")
    return m.id


def _insert_order(
    merchant_id: int,
    trade_no: str,
    money: str,
    base_balance: str,
    status: int = 0,
    created_at: str | None = None,
) -> int:
    """直接插入订单记录，返回 order id。"""
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO orders
               (trade_no, out_trade_no, merchant_id, type, name,
                original_money, money, base_balance, status, created_at)
               VALUES (?, ?, ?, 'alipay', '测试商品', ?, ?, ?, ?, ?)""",
            (trade_no, f"OT_{trade_no}", merchant_id, money, money,
             base_balance, status, created_at),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()


def _get_order_status(trade_no: str) -> int | None:
    """查询订单状态。"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT status FROM orders WHERE trade_no = ?", (trade_no,)
        ).fetchone()
        return row["status"] if row else None
    finally:
        db.close()


def _get_balance_log_count() -> int:
    """查询 balance_logs 表记录数。"""
    db = get_db()
    try:
        row = db.execute("SELECT COUNT(*) AS cnt FROM balance_logs").fetchone()
        return row["cnt"]
    finally:
        db.close()


def _get_latest_balance_log() -> dict | None:
    """获取最新的余额日志。"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM balance_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


# ── query_balance 测试 ────────────────────────────────────


class TestQueryBalance:
    """测试余额查询功能。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_query_balance_success(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.50"),
            "total_amount": Decimal("1200.00"),
            "freeze_amount": Decimal("199.50"),
        }
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        balance = checker.query_balance()
        assert balance == Decimal("1000.50")

    @patch("app.services.balance_checker.AlipayClient")
    def test_query_balance_resets_failure_count(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("500.00"),
        }
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        checker._consecutive_failures = 2
        checker.query_balance()
        assert checker._consecutive_failures == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_query_balance_failure_increments_count(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        with pytest.raises(AlipayClientError):
            checker.query_balance()
        assert checker._consecutive_failures == 1

    @patch("app.services.balance_checker.AlipayClient")
    def test_three_consecutive_failures_logs_warning(self, mock_cls, caplog):
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        import logging
        with caplog.at_level(logging.WARNING, logger="app.services.balance_checker"):
            for _ in range(3):
                with pytest.raises(AlipayClientError):
                    checker.query_balance()

        assert checker._consecutive_failures == 3
        assert "连续 3 次连接失败" in caplog.text


# ── check_payment 单订单匹配 ──────────────────────────────


class TestCheckPaymentSingle:
    """测试单订单余额匹配。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_single_order_match(self, mock_cls):
        """余额差值等于订单金额时，订单标记为已支付。"""
        mock_instance = MagicMock()
        # 基准余额 1000，当前余额 1010 → 差值 10
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1010.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is True
        assert _get_order_status("T001") == 1

    @patch("app.services.balance_checker.AlipayClient")
    def test_single_order_no_match(self, mock_cls):
        """余额差值不等于订单金额时，订单状态不变。"""
        mock_instance = MagicMock()
        # 基准余额 1000，当前余额 1005 → 差值 5，订单金额 10
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1005.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is False
        assert _get_order_status("T001") == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_already_paid_returns_true(self, mock_cls):
        """已支付订单直接返回 True，不查询余额。"""
        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00", status=1)

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is True
        mock_cls.return_value.query_balance.assert_not_called()

    @patch("app.services.balance_checker.AlipayClient")
    def test_expired_order_returns_false(self, mock_cls):
        """已超时订单返回 False，不查询余额。"""
        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00", status=2)

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is False
        mock_cls.return_value.query_balance.assert_not_called()

    def test_nonexistent_order_returns_false(self):
        """不存在的订单返回 False。"""
        checker = BalanceChecker()
        result = checker.check_payment("NONEXISTENT")
        assert result is False


# ── check_payment 多订单匹配 ──────────────────────────────


class TestCheckPaymentMultiple:
    """测试多订单余额匹配逻辑。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_two_orders_both_match(self, mock_cls):
        """差值等于前两笔订单金额之和，两笔都标记为已支付。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 1030 → 差值 30 = 10 + 20
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1030.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=10)
        t2 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "10.00", "1000.00",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "20.00", "1000.00",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        result = checker.check_payment("T002")

        assert result is True
        assert _get_order_status("T001") == 1
        assert _get_order_status("T002") == 1

    @patch("app.services.balance_checker.AlipayClient")
    def test_first_order_only_match(self, mock_cls):
        """差值只等于第一笔订单金额，只有第一笔标记为已支付。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 1010 → 差值 10 = 第一笔
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1010.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=10)
        t2 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "10.00", "1000.00",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "20.00", "1000.00",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        # 查询 T002，但只有 T001 匹配
        result = checker.check_payment("T002")

        assert result is False  # T002 不在匹配列表中
        assert _get_order_status("T001") == 1
        assert _get_order_status("T002") == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_three_orders_first_two_match(self, mock_cls):
        """差值等于前两笔之和，第三笔不受影响。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 1030 → 差值 30 = 10 + 20
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1030.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=15)
        t2 = datetime.now() - timedelta(minutes=10)
        t3 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "10.00", "1000.00",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "20.00", "1000.00",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T003", "15.00", "1000.00",
                      created_at=t3.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is True
        assert _get_order_status("T001") == 1
        assert _get_order_status("T002") == 1
        assert _get_order_status("T003") == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_no_prefix_sum_matches(self, mock_cls):
        """差值不等于任何前缀和，所有订单状态不变。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 1015 → 差值 15
        # 订单: 10, 20 → 前缀和: 10, 30 → 15 不匹配
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1015.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=10)
        t2 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "10.00", "1000.00",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "20.00", "1000.00",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is False
        assert _get_order_status("T001") == 0
        assert _get_order_status("T002") == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_second_order_only_match_subset_sum(self, mock_cls):
        """差值只等于第二笔订单金额（非前缀），子集和算法应匹配成功。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 1020 → 差值 20 = 第二笔
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1020.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=10)
        t2 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "10.00", "1000.00",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "20.00", "1000.00",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        result = checker.check_payment("T002")

        assert result is True
        assert _get_order_status("T001") == 0  # 第一笔未支付
        assert _get_order_status("T002") == 1  # 第二笔匹配成功

    @patch("app.services.balance_checker.AlipayClient")
    def test_middle_order_match_three_orders(self, mock_cls):
        """三笔订单中只有中间一笔被支付，子集和算法应匹配成功。"""
        mock_instance = MagicMock()
        # 基准 224，当前 325 → 差值 101 (1.01元)
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("3.25"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        t1 = datetime.now() - timedelta(minutes=15)
        t2 = datetime.now() - timedelta(minutes=10)
        t3 = datetime.now() - timedelta(minutes=5)
        _insert_order(pid, "T001", "1.00", "2.24",
                      created_at=t1.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T002", "1.01", "2.24",
                      created_at=t2.strftime("%Y-%m-%d %H:%M:%S"))
        _insert_order(pid, "T003", "0.50", "2.24",
                      created_at=t3.strftime("%Y-%m-%d %H:%M:%S"))

        checker = BalanceChecker()
        result = checker.check_payment("T002")

        assert result is True
        assert _get_order_status("T001") == 0
        assert _get_order_status("T002") == 1
        assert _get_order_status("T003") == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_negative_diff_no_match(self, mock_cls):
        """余额减少（差值为负），不匹配任何订单。"""
        mock_instance = MagicMock()
        # 基准 1000，当前 990 → 差值 -10
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("990.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        result = checker.check_payment("T001")

        assert result is False
        assert _get_order_status("T001") == 0


# ── 审计日志测试 ──────────────────────────────────────────


class TestBalanceLog:
    """测试余额查询审计日志记录。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_log_on_successful_match(self, mock_cls):
        """匹配成功时记录日志。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1010.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        checker.check_payment("T001")

        assert _get_balance_log_count() == 1
        log = _get_latest_balance_log()
        assert Decimal(log["available_amount"]) == Decimal("1010.00")
        assert "匹配成功" in log["match_result"]
        assert "T001" in log["matched_trade_nos"]

    @patch("app.services.balance_checker.AlipayClient")
    def test_log_on_no_match(self, mock_cls):
        """不匹配时也记录日志。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1005.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        checker.check_payment("T001")

        assert _get_balance_log_count() == 1
        log = _get_latest_balance_log()
        assert "未匹配" in log["match_result"]
        assert log["matched_trade_nos"] is None

    @patch("app.services.balance_checker.AlipayClient")
    def test_log_on_query_failure(self, mock_cls):
        """余额查询失败时也记录日志。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00")

        checker = BalanceChecker()
        checker.check_payment("T001")

        assert _get_balance_log_count() == 1
        log = _get_latest_balance_log()
        assert "查询失败" in log["match_result"]

    @patch("app.services.balance_checker.AlipayClient")
    def test_log_on_no_pending_orders(self, mock_cls):
        """无待支付订单时记录日志。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("1000.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        # 插入一个已支付订单（不是待支付）
        _insert_order(pid, "T001", "10.00", "1000.00", status=1)

        checker = BalanceChecker()
        checker.check_payment("T001")

        # 已支付订单直接返回 True，不查询余额，不记录日志
        assert _get_balance_log_count() == 0


# ── update_base_balances_after_expiry 测试 ────────────────


class TestUpdateBaseBalances:
    """测试订单超时后更新后续基准余额。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_updates_pending_orders_base_balance(self, mock_cls):
        """超时后更新所有待支付订单的基准余额。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("2000.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00", status=0)
        _insert_order(pid, "T002", "20.00", "1000.00", status=0)

        checker = BalanceChecker()
        checker.update_base_balances_after_expiry()

        db = get_db()
        try:
            rows = db.execute(
                "SELECT trade_no, base_balance FROM orders WHERE status = 0 ORDER BY trade_no"
            ).fetchall()
            for row in rows:
                assert Decimal(str(row["base_balance"])) == Decimal("2000.00")
        finally:
            db.close()

    @patch("app.services.balance_checker.AlipayClient")
    def test_does_not_update_non_pending_orders(self, mock_cls):
        """不更新非待支付订单的基准余额。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("2000.00"),
        }
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00", status=1)  # 已支付
        _insert_order(pid, "T002", "20.00", "1000.00", status=2)  # 已超时

        checker = BalanceChecker()
        checker.update_base_balances_after_expiry()

        db = get_db()
        try:
            for tn in ("T001", "T002"):
                row = db.execute(
                    "SELECT base_balance FROM orders WHERE trade_no = ?", (tn,)
                ).fetchone()
                assert Decimal(str(row["base_balance"])) == Decimal("1000.00")
        finally:
            db.close()

    @patch("app.services.balance_checker.AlipayClient")
    def test_query_failure_skips_update(self, mock_cls):
        """余额查询失败时不更新基准余额。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        pid = _create_merchant()
        _insert_order(pid, "T001", "10.00", "1000.00", status=0)

        checker = BalanceChecker()
        checker.update_base_balances_after_expiry()

        db = get_db()
        try:
            row = db.execute(
                "SELECT base_balance FROM orders WHERE trade_no = 'T001'"
            ).fetchone()
            assert Decimal(str(row["base_balance"])) == Decimal("1000.00")
        finally:
            db.close()


# ── 连续失败告警测试 ──────────────────────────────────────


class TestConsecutiveFailures:
    """测试连续连接失败告警。"""

    @patch("app.services.balance_checker.AlipayClient")
    def test_two_failures_no_warning(self, mock_cls, caplog):
        """连续 2 次失败不触发告警。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        import logging
        with caplog.at_level(logging.WARNING, logger="app.services.balance_checker"):
            for _ in range(2):
                with pytest.raises(AlipayClientError):
                    checker.query_balance()

        assert "连续 3 次连接失败" not in caplog.text

    @patch("app.services.balance_checker.AlipayClient")
    def test_success_resets_counter(self, mock_cls):
        """成功查询后重置失败计数。"""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()

        # 先失败 2 次
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        for _ in range(2):
            with pytest.raises(AlipayClientError):
                checker.query_balance()
        assert checker._consecutive_failures == 2

        # 成功一次
        mock_instance.query_balance.side_effect = None
        mock_instance.query_balance.return_value = {
            "available_amount": Decimal("100.00"),
        }
        checker.query_balance()
        assert checker._consecutive_failures == 0

    @patch("app.services.balance_checker.AlipayClient")
    def test_four_failures_still_warns(self, mock_cls, caplog):
        """连续 4 次失败也触发告警（第 3、4 次都告警）。"""
        mock_instance = MagicMock()
        mock_instance.query_balance.side_effect = AlipayClientError("连接失败")
        mock_cls.return_value = mock_instance

        checker = BalanceChecker()
        import logging
        with caplog.at_level(logging.WARNING, logger="app.services.balance_checker"):
            for _ in range(4):
                with pytest.raises(AlipayClientError):
                    checker.query_balance()

        assert checker._consecutive_failures == 4
        assert "连续" in caplog.text
