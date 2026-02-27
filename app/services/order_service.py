"""
订单服务模块：创建订单、金额尾数调整、订单过期处理。
"""

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal

from app.database import get_db
from app.models.schemas import Order
from app.services.merchant_service import MerchantService
from app.services.platform_config import resolve_credential_for_merchant

logger = logging.getLogger(__name__)


class AmountConflictError(Exception):
    """同金额待支付订单超过上限（累加尾数已达 0.99）。"""
    pass


class OrderCreateError(Exception):
    """订单创建失败通用异常。"""
    pass


class OrderService:
    """订单服务：创建订单、金额调整、过期处理。"""

    def generate_trade_no(self) -> str:
        """
        生成唯一平台订单号：时间戳 + 随机数。
        格式：YYYYMMDDHHMMSSffffff + 6位随机数字，确保唯一。
        """
        db = get_db()
        try:
            for _ in range(10):
                ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
                rand = f"{random.randint(0, 999999):06d}"
                trade_no = ts + rand
                # 确保唯一
                row = db.execute(
                    "SELECT 1 FROM orders WHERE trade_no = ?", (trade_no,)
                ).fetchone()
                if not row:
                    return trade_no
            raise OrderCreateError("无法生成唯一订单号，请重试")
        finally:
            db.close()

    def adjust_amount(self, original_amount: Decimal) -> Decimal:
        """
        检查当前待支付订单中是否有相同金额，
        若有则累加 0.01 直到找到未占用的金额。
        最多调整 0.99，超出则抛出 AmountConflictError。

        Args:
            original_amount: 原始订单金额。

        Returns:
            调整后的实付金额。

        Raises:
            AmountConflictError: 同金额待支付订单超过 100 笔。
        """
        db = get_db()
        try:
            # 查询所有同原始金额范围内的待支付订单的实付金额
            # 范围：original_amount ~ original_amount + 0.99
            min_amount = original_amount
            max_amount = original_amount + Decimal("0.99")
            rows = db.execute(
                """SELECT money FROM orders
                   WHERE status = 0
                   AND money >= ? AND money <= ?""",
                (str(min_amount), str(max_amount)),
            ).fetchall()

            occupied = {Decimal(str(row["money"])) for row in rows}

            # 从原始金额开始，累加 0.01 寻找未占用金额
            for i in range(100):
                candidate = original_amount + Decimal("0.01") * i
                # 保留两位小数
                candidate = candidate.quantize(Decimal("0.01"))
                if candidate not in occupied:
                    return candidate

            raise AmountConflictError("当前下单繁忙，请稍后重试")
        finally:
            db.close()

    def create_order(self, params: dict) -> Order:
        """
        创建支付订单：
        1. 验证商户状态、平台收款码和凭证配置
        2. 计算金额尾数调整(避免同金额冲突)
        3. 查询基准余额快照
        4. 持久化订单记录
        5. 生成 trade_no 和 payurl/qrcode

        Args:
            params: 包含 pid, type, out_trade_no, name, money 等参数的字典。

        Returns:
            创建成功的 Order 对象。

        Raises:
            OrderCreateError: 商户无效、配置缺失等。
            AmountConflictError: 同金额订单超限。
        """
        pid = params.get("pid")
        pay_type = params.get("type", "alipay")
        out_trade_no = params.get("out_trade_no")
        name = params.get("name")
        money_str = params.get("money")
        notify_url = params.get("notify_url")
        return_url = params.get("return_url")
        clientip = params.get("clientip")
        device = params.get("device", "pc")
        param = params.get("param")
        channel_id = params.get("channel_id")

        # 1. 验证商户状态
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            raise OrderCreateError("商户ID无效")

        merchant_svc = MerchantService()
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM merchants WHERE id = ?", (pid_int,)
            ).fetchone()
        finally:
            db.close()

        if not row:
            raise OrderCreateError("商户不存在")
        if row["active"] != 1:
            raise OrderCreateError("商户已被封禁")

        merchant_key = row["key"]

        # 2. 解析凭证（商户自有配置）
        resolved = resolve_credential_for_merchant(pid_int)
        if not resolved:
            raise OrderCreateError("商户尚未配置收款码和支付宝凭证")

        qrcode_url = resolved["qrcode_url"]
        credential_id = resolved.get("credential_id")

        # 3. 金额尾数调整
        try:
            original_money = Decimal(money_str).quantize(Decimal("0.01"))
        except Exception:
            raise OrderCreateError("金额格式无效")

        adjusted_money = self.adjust_amount(original_money)
        adjust_diff = adjusted_money - original_money

        # 4. 查询基准余额
        base_balance = Decimal("0")
        try:
            from app.services.alipay_client import AlipayClient
            client = AlipayClient(
                resolved["app_id"],
                resolved["private_key"],
                resolved["public_key"],
            )
            balance_result = client.query_balance()
            base_balance = balance_result.get("available_amount", Decimal("0"))
            logger.info(
                "创建订单记录基准余额: out_trade_no=%s, base_balance=%s",
                out_trade_no, base_balance,
            )
        except Exception as e:
            logger.warning("查询基准余额失败，使用默认值 0: %s", e)

        # 5. 生成 trade_no
        trade_no = self.generate_trade_no()

        # 6. 持久化订单
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO orders
                   (trade_no, out_trade_no, merchant_id, type, name,
                    original_money, money, adjust_amount, status,
                    notify_url, return_url, param, clientip, device,
                    channel_id, base_balance, credential_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade_no, out_trade_no, pid_int, pay_type, name,
                    str(original_money), str(adjusted_money), str(adjust_diff),
                    notify_url, return_url, param, clientip, device,
                    channel_id, str(base_balance), credential_id, now,
                ),
            )
            db.commit()
            order_id = cursor.lastrowid
        except Exception as e:
            db.rollback()
            raise OrderCreateError(f"订单创建失败: {e}")
        finally:
            db.close()

        return Order(
            id=order_id,
            trade_no=trade_no,
            out_trade_no=out_trade_no,
            merchant_id=pid_int,
            name=name,
            original_money=original_money,
            money=adjusted_money,
            base_balance=base_balance,
            type=pay_type,
            adjust_amount=adjust_diff,
            status=0,
            notify_url=notify_url,
            return_url=return_url,
            param=param,
            clientip=clientip,
            device=device,
            channel_id=int(channel_id) if channel_id else None,
            credential_id=credential_id,
            created_at=now,
        ), qrcode_url

    def expire_orders(self) -> None:
        """
        将超过 10 分钟未支付的订单标记为超时（status=2），释放金额尾数。
        """
        cutoff = (datetime.now() - timedelta(minutes=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        try:
            db.execute(
                """UPDATE orders
                   SET status = 2, expired_at = ?
                   WHERE status = 0 AND created_at < ?""",
                (now, cutoff),
            )
            db.commit()
        finally:
            db.close()
