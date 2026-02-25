"""
SQLite 数据库连接管理和初始化。
使用同步 sqlite3，提供 get_db() 获取连接。
"""

import os
import sqlite3
from pathlib import Path

import bcrypt
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/qiupay.db")


def get_db() -> sqlite3.Connection:
    """获取 SQLite 数据库连接，启用 WAL 模式和外键约束。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── 建表 SQL ──────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS admin (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   VARCHAR(128) NOT NULL,
    login_fail_count INTEGER     DEFAULT 0,
    locked_until    DATETIME,
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      VARCHAR(64)  NOT NULL UNIQUE,
    config_value    TEXT,
    updated_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS merchants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    email           VARCHAR(128) NOT NULL,
    key             VARCHAR(32)  NOT NULL,
    active          INTEGER      DEFAULT 1,
    money           DECIMAL(10,2) DEFAULT 0,
    settle_type     INTEGER      DEFAULT 1,
    settle_account  VARCHAR(128),
    settle_username VARCHAR(64),
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now')),
    updated_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_no        VARCHAR(32)  NOT NULL UNIQUE,
    out_trade_no    VARCHAR(64)  NOT NULL,
    api_trade_no    VARCHAR(64),
    merchant_id     INTEGER      NOT NULL REFERENCES merchants(id),
    type            VARCHAR(16)  DEFAULT 'alipay',
    name            VARCHAR(256) NOT NULL,
    original_money  DECIMAL(10,2) NOT NULL,
    money           DECIMAL(10,2) NOT NULL,
    adjust_amount   DECIMAL(10,2) DEFAULT 0,
    status          INTEGER      DEFAULT 0,
    notify_url      TEXT,
    return_url      TEXT,
    param           TEXT,
    clientip        VARCHAR(64),
    device          VARCHAR(16)  DEFAULT 'pc',
    channel_id      INTEGER,
    base_balance    DECIMAL(12,2) NOT NULL,
    confirm_balance DECIMAL(12,2),
    credential_id   INTEGER      REFERENCES merchant_credentials(id),
    buyer           VARCHAR(128),
    callback_status INTEGER      DEFAULT 0,
    callback_attempts INTEGER    DEFAULT 0,
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now')),
    paid_at         DATETIME,
    expired_at      DATETIME
);

CREATE TABLE IF NOT EXISTS callback_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER      NOT NULL REFERENCES orders(id),
    attempt         INTEGER      NOT NULL,
    url             TEXT         NOT NULL,
    method          VARCHAR(8)   DEFAULT 'POST',
    http_status     INTEGER,
    response_body   TEXT,
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS balance_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    available_amount DECIMAL(12,2) NOT NULL,
    match_result    TEXT,
    matched_trade_nos TEXT,
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS merchant_credentials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id     INTEGER      NOT NULL REFERENCES merchants(id),
    qrcode_path     TEXT,
    qrcode_url      TEXT         NOT NULL,
    app_id          TEXT         NOT NULL,
    public_key      TEXT         NOT NULL,
    private_key     TEXT         NOT NULL,
    credential_status VARCHAR(16) DEFAULT 'configured',
    active          INTEGER      DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT (datetime('now')),
    updated_at      DATETIME     NOT NULL DEFAULT (datetime('now'))
);
"""

# ── 索引 SQL ──────────────────────────────────────────────

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_orders_status
    ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_merchant_status
    ON orders(merchant_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_trade_no
    ON orders(trade_no);
CREATE INDEX IF NOT EXISTS idx_orders_out_trade_no
    ON orders(merchant_id, out_trade_no);
CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_money_status
    ON orders(money, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_merchants_username
    ON merchants(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_config_key
    ON system_config(config_key);
CREATE INDEX IF NOT EXISTS idx_callback_logs_order_id
    ON callback_logs(order_id);
CREATE INDEX IF NOT EXISTS idx_balance_logs_created
    ON balance_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_merchant_credentials_merchant
    ON merchant_credentials(merchant_id);
"""


# ── 初始化 ────────────────────────────────────────────────

def init_db() -> None:
    """创建数据库目录、表、索引，并在首次启动时创建默认管理员。"""
    # 确保 data/ 目录存在
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = get_db()
    try:
        conn.executescript(_CREATE_TABLES)
        conn.executescript(_CREATE_INDEXES)

        # 迁移：为已有数据库添加新列
        _migrate_schema(conn)

        # 首次启动：通过环境变量创建默认管理员
        _create_default_admin(conn)

        conn.commit()
    finally:
        conn.close()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """为已有数据库添加新列（幂等操作）。"""
    # orders 表添加 credential_id 列
    try:
        conn.execute("SELECT credential_id FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE orders ADD COLUMN credential_id INTEGER REFERENCES merchant_credentials(id)")


def _create_default_admin(conn: sqlite3.Connection) -> None:
    """如果 admin 表为空，则根据环境变量创建默认管理员账号。"""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM admin").fetchone()
    if row["cnt"] > 0:
        return

    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    conn.execute(
        "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
