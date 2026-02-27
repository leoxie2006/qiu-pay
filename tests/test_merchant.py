"""商户管理服务单元测试。"""

import os
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

import app.database as _db_mod
from app.database import get_db, init_db
from app.services.merchant_service import MerchantService


@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前重建数据库。"""
    os.environ["DB_PATH"] = _tmp.name
    _db_mod.DB_PATH = _tmp.name
    # 清空数据库文件
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
    return MerchantService()


class TestCreateMerchant:
    """create_merchant 单元测试。"""

    def test_creates_merchant_with_valid_fields(self, svc):
        m = svc.create_merchant("shop1", "shop1@example.com")
        assert m.username == "shop1"
        assert m.email == "shop1@example.com"
        assert m.active == 1
        assert m.id is not None and m.id > 0

    def test_key_is_32_hex_chars(self, svc):
        m = svc.create_merchant("shop2", "shop2@example.com")
        assert re.fullmatch(r"[0-9a-f]{32}", m.key)

    def test_pid_auto_increments(self, svc):
        m1 = svc.create_merchant("a", "a@x.com")
        m2 = svc.create_merchant("b", "b@x.com")
        assert m2.id > m1.id

    def test_duplicate_username_raises(self, svc):
        svc.create_merchant("dup", "dup@x.com")
        with pytest.raises(ValueError, match="已存在"):
            svc.create_merchant("dup", "dup2@x.com")

    def test_merchant_persisted_in_db(self, svc):
        m = svc.create_merchant("persist", "p@x.com")
        db = get_db()
        try:
            row = db.execute("SELECT * FROM merchants WHERE id = ?", (m.id,)).fetchone()
            assert row is not None
            assert row["username"] == "persist"
            assert row["key"] == m.key
            assert row["active"] == 1
        finally:
            db.close()


class TestToggleStatus:
    """toggle_status 单元测试。"""

    def test_ban_merchant(self, svc):
        m = svc.create_merchant("ban_me", "b@x.com")
        svc.toggle_status(m.id, False)
        db = get_db()
        try:
            row = db.execute("SELECT active FROM merchants WHERE id = ?", (m.id,)).fetchone()
            assert row["active"] == 0
        finally:
            db.close()

    def test_unban_merchant(self, svc):
        m = svc.create_merchant("unban_me", "u@x.com")
        svc.toggle_status(m.id, False)
        svc.toggle_status(m.id, True)
        db = get_db()
        try:
            row = db.execute("SELECT active FROM merchants WHERE id = ?", (m.id,)).fetchone()
            assert row["active"] == 1
        finally:
            db.close()

    def test_nonexistent_pid_raises(self, svc):
        with pytest.raises(ValueError, match="不存在"):
            svc.toggle_status(99999, False)


class TestResetKey:
    """reset_key 单元测试。"""

    def test_returns_new_32_hex_key(self, svc):
        m = svc.create_merchant("reset_me", "r@x.com")
        new_key = svc.reset_key(m.id)
        assert re.fullmatch(r"[0-9a-f]{32}", new_key)

    def test_new_key_differs_from_old(self, svc):
        m = svc.create_merchant("diff_key", "d@x.com")
        old_key = m.key
        new_key = svc.reset_key(m.id)
        assert new_key != old_key

    def test_new_key_persisted(self, svc):
        m = svc.create_merchant("persist_key", "pk@x.com")
        new_key = svc.reset_key(m.id)
        db = get_db()
        try:
            row = db.execute("SELECT key FROM merchants WHERE id = ?", (m.id,)).fetchone()
            assert row["key"] == new_key
        finally:
            db.close()

    def test_nonexistent_pid_raises(self, svc):
        with pytest.raises(ValueError, match="不存在"):
            svc.reset_key(99999)


class TestGetMerchantInfo:
    """get_merchant_info 单元测试。"""

    def test_returns_all_required_fields(self, svc):
        m = svc.create_merchant("info_test", "i@x.com")
        info = svc.get_merchant_info(m.id)
        required_keys = {"code", "pid", "key", "active", "money", "type",
                         "account", "username", "orders", "order_today", "order_lastday"}
        assert required_keys.issubset(info.keys())

    def test_correct_values(self, svc):
        m = svc.create_merchant("val_test", "v@x.com")
        info = svc.get_merchant_info(m.id)
        assert info["code"] == 1
        assert info["pid"] == m.id
        assert info["key"] == m.key
        assert info["active"] == 1
        assert info["orders"] == 0
        assert info["order_today"] == 0
        assert info["order_lastday"] == 0

    def test_order_statistics(self, svc):
        """验证订单统计包含正确的计数。"""
        m = svc.create_merchant("stats", "s@x.com")
        db = get_db()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            # 插入今日订单
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("T001", "OT001", m.id, "item1", 10.0, 10.0, 100.0, now),
            )
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("T002", "OT002", m.id, "item2", 20.0, 20.0, 100.0, now),
            )
            # 插入昨日订单
            db.execute(
                """INSERT INTO orders (trade_no, out_trade_no, merchant_id, name,
                   original_money, money, base_balance, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("T003", "OT003", m.id, "item3", 30.0, 30.0, 100.0, yesterday),
            )
            db.commit()
        finally:
            db.close()

        info = svc.get_merchant_info(m.id)
        assert info["orders"] == 3
        assert info["order_today"] == 2
        assert info["order_lastday"] == 1

    def test_nonexistent_pid_raises(self, svc):
        with pytest.raises(ValueError, match="不存在"):
            svc.get_merchant_info(99999)


class TestListMerchants:
    """list_merchants 单元测试。"""

    def test_empty_list(self, svc):
        result = svc.list_merchants()
        assert result == []

    def test_returns_all_merchants(self, svc):
        svc.create_merchant("m1", "m1@x.com")
        svc.create_merchant("m2", "m2@x.com")
        result = svc.list_merchants()
        assert len(result) == 2

    def test_merchant_fields(self, svc):
        svc.create_merchant("fields_test", "f@x.com")
        result = svc.list_merchants()
        m = result[0]
        assert "pid" in m
        assert "username" in m
        assert "email" in m
        assert "active" in m
        assert "money" in m
        assert "orders" in m
        assert "order_today" in m

    def test_ordered_by_pid(self, svc):
        svc.create_merchant("first", "f@x.com")
        svc.create_merchant("second", "s@x.com")
        result = svc.list_merchants()
        assert result[0]["pid"] < result[1]["pid"]
