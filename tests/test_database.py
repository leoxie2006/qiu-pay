"""app/database.py 的单元测试。"""

import os
import sqlite3
import tempfile

import bcrypt
import pytest

# 在导入 database 之前设置临时 DB_PATH
_tmp = tempfile.mkdtemp()
_test_db = os.path.join(_tmp, "test.db")
os.environ["DB_PATH"] = _test_db

import app.database as _db_mod
from app.database import get_db, init_db, DB_PATH


class TestInitDB:
    """数据库初始化测试。"""

    def setup_method(self):
        # 确保 DB_PATH 指向测试数据库（其他测试文件的 fixture 可能修改了它）
        os.environ["DB_PATH"] = _test_db
        _db_mod.DB_PATH = _test_db
        # 每个测试用新数据库
        if os.path.exists(_test_db):
            os.remove(_test_db)

    def test_creates_all_tables(self):
        init_db()
        conn = get_db()
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        expected = {"admin", "system_config", "merchants", "orders",
                    "callback_logs", "balance_logs"}
        assert expected.issubset(tables)

    def test_creates_indexes(self):
        init_db()
        conn = get_db()
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        }
        conn.close()
        expected = {
            "idx_orders_status",
            "idx_orders_merchant_status",
            "idx_orders_trade_no",
            "idx_orders_out_trade_no",
            "idx_orders_created_at",
            "idx_orders_money_status",
            "idx_merchants_username",
            "idx_system_config_key",
            "idx_callback_logs_order_id",
            "idx_balance_logs_created",
        }
        assert expected.issubset(indexes)

    def test_default_admin_created(self):
        old_username = os.environ.get("ADMIN_USERNAME")
        old_password = os.environ.get("ADMIN_PASSWORD")
        try:
            os.environ["ADMIN_USERNAME"] = "testadmin"
            os.environ["ADMIN_PASSWORD"] = "secret123"
            init_db()
            conn = get_db()
            row = conn.execute(
                "SELECT username, password_hash FROM admin WHERE username = ?",
                ("testadmin",),
            ).fetchone()
            conn.close()
            assert row is not None
            assert row["username"] == "testadmin"
            assert bcrypt.checkpw(b"secret123", row["password_hash"].encode("utf-8"))
        finally:
            # Restore original env vars to avoid polluting other tests
            if old_username is not None:
                os.environ["ADMIN_USERNAME"] = old_username
            elif "ADMIN_USERNAME" in os.environ:
                del os.environ["ADMIN_USERNAME"]
            if old_password is not None:
                os.environ["ADMIN_PASSWORD"] = old_password
            elif "ADMIN_PASSWORD" in os.environ:
                del os.environ["ADMIN_PASSWORD"]

    def test_default_admin_not_duplicated(self):
        """多次 init_db 不会重复创建管理员。"""
        init_db()
        init_db()
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) AS cnt FROM admin").fetchone()["cnt"]
        conn.close()
        assert count == 1

    def test_get_db_returns_row_factory(self):
        init_db()
        conn = get_db()
        row = conn.execute("SELECT 1 AS val").fetchone()
        conn.close()
        assert row["val"] == 1

    def test_foreign_keys_enabled(self):
        init_db()
        conn = get_db()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()
        conn.close()
        assert fk[0] == 1

    def test_idempotent_init(self):
        """init_db 可以安全地多次调用。"""
        init_db()
        init_db()
        init_db()
        conn = get_db()
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "orders" in tables
