"""
回调通知服务：向商户发送支付结果异步通知，支持重试和 return_url 构建。

核心功能：
- send_notify: POST 通知到商户 notify_url，商户返回 "success" 则标记成功
- retry_notify: 按 [5, 30, 60, 300, 1800] 秒间隔重试，最多 5 次
- build_return_url: 将通知参数以 GET 方式拼接到 return_url
- 每次通知记录到 callback_logs 表
"""

import logging
from datetime import datetime
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, urljoin

import httpx

from app.database import get_db
from app.services.sign import generate_sign

logger = logging.getLogger(__name__)


class CallbackService:
    """回调通知服务。"""

    RETRY_INTERVALS = [5, 30, 60, 300, 1800]  # 秒

    def _get_order_with_merchant(self, order_id: int) -> dict | None:
        """获取订单及其商户信息。"""
        db = get_db()
        try:
            row = db.execute(
                """SELECT o.id, o.trade_no, o.out_trade_no, o.merchant_id,
                          o.type, o.name, o.money, o.param,
                          o.notify_url, o.return_url,
                          o.callback_status, o.callback_attempts,
                          m.key AS merchant_key, m.id AS pid
                   FROM orders o
                   JOIN merchants m ON o.merchant_id = m.id
                   WHERE o.id = ?""",
                (order_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def _build_notify_params(self, order: dict) -> dict:
        """构建回调通知参数（不含 sign 和 sign_type）。"""
        params = {
            "pid": order["pid"],
            "trade_no": order["trade_no"],
            "out_trade_no": order["out_trade_no"],
            "type": order["type"],
            "name": order["name"],
            "money": str(order["money"]),
            "trade_status": "TRADE_SUCCESS",
            "param": order["param"] or "",
            "sign_type": "MD5",
        }
        return params

    def _sign_params(self, params: dict, merchant_key: str) -> dict:
        """对参数进行签名，返回包含 sign 的完整参数字典。"""
        sign = generate_sign(params, merchant_key)
        signed = dict(params)
        signed["sign"] = sign
        return signed

    def _log_callback(
        self,
        order_id: int,
        attempt: int,
        url: str,
        method: str = "POST",
        http_status: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """记录回调通知日志到 callback_logs 表。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        try:
            db.execute(
                """INSERT INTO callback_logs
                   (order_id, attempt, url, method, http_status, response_body, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, attempt, url, method, http_status, response_body, now),
            )
            db.commit()
        finally:
            db.close()

    def _update_callback_status(
        self, order_id: int, status: int, attempts: int
    ) -> None:
        """更新订单的回调状态和尝试次数。"""
        db = get_db()
        try:
            db.execute(
                """UPDATE orders
                   SET callback_status = ?, callback_attempts = ?
                   WHERE id = ?""",
                (status, attempts, order_id),
            )
            db.commit()
        finally:
            db.close()

    def send_notify(self, order_id: int) -> bool:
        """
        向商户 notify_url 发送异步通知（POST）。

        构建通知参数（pid, trade_no, out_trade_no, type, name, money,
        trade_status, param, sign, sign_type）→ POST 到 notify_url →
        检查响应是否为 "success"。

        Args:
            order_id: 订单 ID。

        Returns:
            True 表示商户返回 "success"，通知成功。
        """
        order = self._get_order_with_merchant(order_id)
        if not order:
            logger.warning("回调通知失败：订单不存在 (order_id=%d)", order_id)
            return False

        notify_url = order.get("notify_url")
        if not notify_url:
            logger.info("订单无 notify_url，跳过回调 (order_id=%d)", order_id)
            return False

        # 标记为通知中
        current_attempts = order["callback_attempts"] + 1
        self._update_callback_status(order_id, 3, current_attempts)

        # 构建签名参数
        params = self._build_notify_params(order)
        signed_params = self._sign_params(params, order["merchant_key"])

        # 发送 POST 请求
        http_status = None
        response_body = None
        success = False

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(notify_url, data=signed_params)
                http_status = resp.status_code
                response_body = resp.text.strip()
                success = response_body == "success"
        except Exception as e:
            response_body = str(e)
            logger.warning(
                "回调通知请求异常 (order_id=%d, url=%s): %s",
                order_id, notify_url, e,
            )

        # 记录日志
        self._log_callback(
            order_id, current_attempts, notify_url, "POST",
            http_status, response_body,
        )

        # 更新状态
        if success:
            self._update_callback_status(order_id, 1, current_attempts)
            logger.info("回调通知成功 (order_id=%d)", order_id)
        else:
            # 未成功，检查是否需要重试
            if current_attempts >= len(self.RETRY_INTERVALS) + 1:
                # 已达最大重试次数（首次 + 5 次重试），标记失败
                self._update_callback_status(order_id, 2, current_attempts)
                logger.warning(
                    "回调通知全部失败 (order_id=%d, attempts=%d)",
                    order_id, current_attempts,
                )
            else:
                # 保持通知中状态，等待重试
                self._update_callback_status(order_id, 3, current_attempts)

        return success

    def retry_notify(self, order_id: int, attempt: int) -> None:
        """
        按重试策略重新发送通知，最多 5 次。

        重试间隔：[5, 30, 60, 300, 1800] 秒。
        实际的延迟调度由外部任务调度器负责（task 19.1），
        此方法仅执行重试发送逻辑。

        Args:
            order_id: 订单 ID。
            attempt: 当前重试次数（1-5）。
        """
        if attempt < 1 or attempt > len(self.RETRY_INTERVALS):
            logger.warning(
                "无效的重试次数 (order_id=%d, attempt=%d)", order_id, attempt
            )
            return

        order = self._get_order_with_merchant(order_id)
        if not order:
            logger.warning("重试通知失败：订单不存在 (order_id=%d)", order_id)
            return

        # 如果已经成功，不再重试
        if order["callback_status"] == 1:
            logger.info(
                "回调已成功，跳过重试 (order_id=%d)", order_id
            )
            return

        notify_url = order.get("notify_url")
        if not notify_url:
            return

        # 构建签名参数
        params = self._build_notify_params(order)
        signed_params = self._sign_params(params, order["merchant_key"])

        # 更新尝试次数（首次发送算第 1 次，重试从第 2 次开始）
        total_attempts = attempt + 1
        self._update_callback_status(order_id, 3, total_attempts)

        # 发送 POST 请求
        http_status = None
        response_body = None
        success = False

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(notify_url, data=signed_params)
                http_status = resp.status_code
                response_body = resp.text.strip()
                success = response_body == "success"
        except Exception as e:
            response_body = str(e)
            logger.warning(
                "重试通知请求异常 (order_id=%d, attempt=%d): %s",
                order_id, attempt, e,
            )

        # 记录日志
        self._log_callback(
            order_id, total_attempts, notify_url, "POST",
            http_status, response_body,
        )

        # 更新状态
        if success:
            self._update_callback_status(order_id, 1, total_attempts)
            logger.info(
                "重试通知成功 (order_id=%d, attempt=%d)", order_id, attempt
            )
        elif attempt >= len(self.RETRY_INTERVALS):
            # 最后一次重试也失败，标记为失败
            self._update_callback_status(order_id, 2, total_attempts)
            logger.warning(
                "回调通知全部重试失败 (order_id=%d, total_attempts=%d)",
                order_id, total_attempts,
            )
        else:
            # 保持通知中状态，等待下一次重试
            self._update_callback_status(order_id, 3, total_attempts)

    def build_return_url(self, order_id: int) -> str:
        """
        构建 return_url 跳转链接，将通知参数以 GET 方式拼接到 return_url。

        Args:
            order_id: 订单 ID。

        Returns:
            拼接了通知参数的完整 return_url，若无 return_url 则返回空字符串。
        """
        order = self._get_order_with_merchant(order_id)
        if not order:
            return ""

        return_url = order.get("return_url")
        if not return_url:
            return ""

        # 构建签名参数
        params = self._build_notify_params(order)
        signed_params = self._sign_params(params, order["merchant_key"])

        # 将参数拼接到 return_url
        parsed = urlparse(return_url)
        # 保留原有查询参数
        existing_params = parse_qs(parsed.query, keep_blank_values=True)
        # 将现有参数展平为单值
        flat_existing = {k: v[0] for k, v in existing_params.items()}
        # 合并通知参数（通知参数优先）
        merged = {**flat_existing, **signed_params}
        # URL 编码
        query_string = urlencode(merged)
        # 重建 URL
        new_parsed = parsed._replace(query=query_string)
        return urlunparse(new_parsed)
