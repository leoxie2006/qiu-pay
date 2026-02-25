"""
数据模型 / 类型定义，供各模块引用。
使用 dataclass 保持轻量，不引入 ORM。
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Admin:
    id: int
    username: str
    password_hash: str
    login_fail_count: int = 0
    locked_until: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class SystemConfig:
    id: int
    config_key: str
    config_value: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class Merchant:
    id: int  # 即 pid
    username: str
    email: str
    key: str
    active: int = 1
    money: Decimal = Decimal("0")
    settle_type: int = 1
    settle_account: Optional[str] = None
    settle_username: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Order:
    id: int
    trade_no: str
    out_trade_no: str
    merchant_id: int
    name: str
    original_money: Decimal
    money: Decimal
    base_balance: Decimal
    api_trade_no: Optional[str] = None
    type: str = "alipay"
    adjust_amount: Decimal = Decimal("0")
    status: int = 0
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    param: Optional[str] = None
    clientip: Optional[str] = None
    device: str = "pc"
    channel_id: Optional[int] = None
    credential_id: Optional[int] = None
    confirm_balance: Optional[Decimal] = None
    buyer: Optional[str] = None
    callback_status: int = 0
    callback_attempts: int = 0
    created_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None


@dataclass
class MerchantCredential:
    id: int
    merchant_id: int
    qrcode_url: str
    app_id: str
    public_key: str
    private_key: str
    qrcode_path: Optional[str] = None
    credential_status: str = "configured"
    active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CallbackLog:
    id: int
    order_id: int
    attempt: int
    url: str
    method: str = "POST"
    http_status: Optional[int] = None
    response_body: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class BalanceLog:
    id: int
    available_amount: Decimal
    match_result: Optional[str] = None
    matched_trade_nos: Optional[str] = None
    created_at: Optional[datetime] = None
