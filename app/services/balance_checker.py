"""
余额检测器：通过支付宝余额查询接口检测余额变化，确认支付状态。

核心逻辑：
- 查询当前余额，与每笔待支付订单自身的基准余额比较
- 当前余额 - 订单基准余额 >= 订单金额，则判定该订单已支付
- 匹配成功则更新订单状态为已支付，触发回调通知
- 记录每次余额查询的审计日志
- 连续 3 次连接失败记录告警日志
"""

import logging
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.services.alipay_client import AlipayClient, AlipayClientError
from app.services.platform_config import get_credentials, get_credential_by_id

logger = logging.getLogger(__name__)



class BalanceChecker:
    """余额检测器：检测支付宝账户余额变化以确认支付。"""

    def __init__(self):
        self._consecutive_failures = 0

    def _get_alipay_client(self, credential_id: int | None = None) -> AlipayClient:
        """
        获取支付宝客户端实例。
        如果指定了 credential_id，使用商户凭证；否则使用系统凭证。
        """
        if credential_id:
            cred = get_credential_by_id(credential_id)
            if cred:
                return AlipayClient(
                    cred["app_id"],
                    cred["private_key"],
                    cred["public_key"],
                )
        # 回退到系统凭证
        credentials = get_credentials()
        if not credentials:
            raise AlipayClientError("平台尚未配置支付宝凭证")
        return AlipayClient(
            credentials["app_id"],
            credentials["private_key"],
            credentials["public_key"],
        )

    def query_balance(self, credential_id: int | None = None) -> Decimal:
        """
        查询当前可用余额。

        连续 3 次连接失败时记录告警日志。

        Args:
            credential_id: 可选的商户凭证 ID，为 None 时使用系统凭证。

        Returns:
            当前可用余额。

        Raises:
            AlipayClientError: 查询失败。
        """
        client = self._get_alipay_client(credential_id)
        try:
            result = client.query_balance()
            self._consecutive_failures = 0
            amount = result["available_amount"]
            logger.info("余额查询成功: 当前可用余额=%s, credential_id=%s", amount, credential_id)
            return amount
        except AlipayClientError:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                logger.warning(
                    "支付宝余额查询接口连续 %d 次连接失败，请检查网络或凭证配置",
                    self._consecutive_failures,
                )
            raise

    def _log_balance_query(
        self,
        available_amount: Decimal,
        match_result: str,
        matched_trade_nos: str | None = None,
    ) -> None:
        """记录余额查询审计日志到 balance_logs 表。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        try:
            db.execute(
                """INSERT INTO balance_logs
                   (available_amount, match_result, matched_trade_nos, created_at)
                   VALUES (?, ?, ?, ?)""",
                (str(available_amount), match_result, matched_trade_nos, now),
            )
            db.commit()
        finally:
            db.close()

    def _get_pending_orders(self) -> list[dict]:
        """获取所有待支付订单，按创建时间升序排列。"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, trade_no, out_trade_no, merchant_id, money,
                          base_balance, notify_url, return_url, name, type,
                          param, original_money, credential_id
                   FROM orders
                   WHERE status = 0
                   ORDER BY created_at ASC"""
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            db.close()

    def _mark_orders_paid(
        self, order_ids: list[int], confirm_balance: Decimal
    ) -> None:
        """将指定订单标记为已支付，并更新商户余额。"""
        if not order_ids:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        try:
            placeholders = ",".join("?" for _ in order_ids)
            db.execute(
                f"""UPDATE orders
                    SET status = 1, confirm_balance = ?, paid_at = ?
                    WHERE id IN ({placeholders})""",
                [str(confirm_balance), now] + order_ids,
            )
            # 更新商户余额：给每个商户加上对应订单的金额
            rows = db.execute(
                f"""SELECT merchant_id, money FROM orders WHERE id IN ({placeholders})""",
                order_ids,
            ).fetchall()
            merchant_amounts: dict[int, Decimal] = {}
            for row in rows:
                mid = row["merchant_id"]
                amt = Decimal(str(row["money"]))
                merchant_amounts[mid] = merchant_amounts.get(mid, Decimal("0")) + amt
            for mid, total_amt in merchant_amounts.items():
                db.execute(
                    "UPDATE merchants SET money = money + ? WHERE id = ?",
                    (str(total_amt), mid),
                )
            db.commit()
        finally:
            db.close()

    def _trigger_callbacks(self, order_ids: list[int]) -> None:
        """触发已支付订单的回调通知（尽力而为）。"""
        try:
            from app.services.callback_service import CallbackService
            cb = CallbackService()
            for oid in order_ids:
                try:
                    cb.send_notify(oid)
                except Exception as e:
                    logger.warning("触发回调通知失败 (order_id=%d): %s", oid, e)
        except ImportError:
            logger.debug("callback_service 模块尚未实现，跳过回调触发")

    def _subset_sum_dfs(
        self, amounts: list[int], target: int
    ) -> list[int] | None:
        """
        子集和求解（DFS回溯）：在 amounts 中找到一个子集，使其和等于 target。
        所有金额均为整数（分），避免浮点精度问题。

        优先返回元素最少的匹配组合（单笔优先），减少误匹配风险。

        Args:
            amounts: 各订单金额（分）列表。
            target: 目标差值（分）。

        Returns:
            匹配的订单索引列表，无匹配返回 None。
        """
        n = len(amounts)
        best_result: list[int] | None = None

        def dfs(start: int, remaining: int, path: list[int]) -> None:
            nonlocal best_result
            if remaining == 0:
                if best_result is None or len(path) < len(best_result):
                    best_result = path[:]
                return
            if remaining < 0:
                return
            # 如果已找到单笔匹配，无需继续搜索
            if best_result is not None and len(best_result) == 1:
                return
            for i in range(start, n):
                # 剪枝：如果当前金额已超过剩余目标，跳过
                if amounts[i] > remaining:
                    continue
                # 剪枝：如果已有结果且当前路径长度已不可能更优，跳过
                if best_result is not None and len(path) + 1 >= len(best_result):
                    return
                path.append(i)
                dfs(i + 1, remaining - amounts[i], path)
                path.pop()

        dfs(0, target, [])
        return best_result

    def check_payment(self, trade_no: str) -> bool:
        """
        对指定订单执行余额检测：
        1. 查询当前余额（使用订单绑定的凭证）
        2. 获取同凭证下的所有待支付订单
        3. 计算余额差值，使用子集和算法(DFS)匹配订单组合
        4. 匹配成功则更新订单状态、商户余额并触发回调

        Returns:
            该订单是否已支付。
        """
        logger.info("开始余额检测: trade_no=%s", trade_no)

        # 先检查订单当前状态
        db = get_db()
        try:
            order_row = db.execute(
                "SELECT id, status, base_balance, credential_id FROM orders WHERE trade_no = ?",
                (trade_no,),
            ).fetchone()
        finally:
            db.close()

        if not order_row:
            logger.info("余额检测: 订单不存在 trade_no=%s", trade_no)
            return False

        # 已支付直接返回
        if order_row["status"] == 1:
            logger.info("余额检测: 订单已支付 trade_no=%s", trade_no)
            return True

        # 非待支付状态（超时/取消）不检测
        if order_row["status"] != 0:
            logger.info(
                "余额检测: 订单非待支付状态 trade_no=%s, status=%d",
                trade_no, order_row["status"],
            )
            return False

        # 使用订单绑定的凭证查询余额
        credential_id = order_row["credential_id"]

        try:
            current_balance = self.query_balance(credential_id)
        except AlipayClientError as e:
            logger.warning("余额查询失败，跳过本次检测: %s", e)
            self._log_balance_query(
                Decimal("0"), f"查询失败: {e}", None
            )
            return False

        # 获取所有待支付订单，按凭证分组只取同凭证的订单
        all_pending = self._get_pending_orders()
        if not all_pending:
            logger.info("余额检测: 无待支付订单")
            self._log_balance_query(current_balance, "无待支付订单", None)
            return False

        # 筛选同凭证的订单（credential_id 相同的才能一起匹配）
        pending_orders = [
            o for o in all_pending if o.get("credential_id") == credential_id
        ]
        if not pending_orders:
            logger.info("余额检测: 无同凭证待支付订单 credential_id=%s", credential_id)
            self._log_balance_query(current_balance, "无同凭证待支付订单", None)
            return False

        # 计算差值：当前余额 - 最早订单的基准余额
        earliest_base = Decimal(str(pending_orders[0]["base_balance"]))
        diff = current_balance - earliest_base

        logger.info(
            "余额检测: 当前余额=%s, 基准余额=%s, 差值=%s, 待支付订单数=%d, credential_id=%s",
            current_balance, earliest_base, diff, len(pending_orders), credential_id,
        )

        if diff <= 0:
            logger.info(
                "余额检测未匹配: trade_no=%s, 差值=%s (无正向变化)",
                trade_no, diff,
            )
            self._log_balance_query(
                current_balance,
                f"未匹配: 差值={diff} (无正向变化)",
                None,
            )
            return False

        # 转换为整数（分）避免浮点精度问题
        diff_cents = int((diff * 100).to_integral_value())
        order_cents = []
        for order in pending_orders:
            order_cents.append(int((Decimal(str(order["money"])) * 100).to_integral_value()))

        # 子集和匹配（DFS回溯）：找到金额之和等于差值的订单组合
        matched_indices = self._subset_sum_dfs(order_cents, diff_cents)

        if matched_indices is not None:
            matched_ids = [pending_orders[i]["id"] for i in matched_indices]
            matched_trade_nos_list = [
                pending_orders[i]["trade_no"] for i in matched_indices
            ]
            matched_amounts = [
                Decimal(str(pending_orders[i]["money"])) for i in matched_indices
            ]

            self._mark_orders_paid(matched_ids, current_balance)
            trade_nos_str = ",".join(matched_trade_nos_list)
            accumulated = sum(matched_amounts)
            logger.info(
                "余额检测匹配成功: 差值=%s, 累计=%s, 匹配订单=%s",
                diff, accumulated, trade_nos_str,
            )
            self._log_balance_query(
                current_balance,
                f"匹配成功: 差值={diff}, 累计={accumulated}",
                trade_nos_str,
            )
            self._trigger_callbacks(matched_ids)

            return trade_no in matched_trade_nos_list

        # 无任何子集组合匹配
        total = sum(Decimal(str(o["money"])) for o in pending_orders)
        logger.info(
            "余额检测未匹配: trade_no=%s, 差值=%s, 订单总额=%s",
            trade_no, diff, total,
        )
        self._log_balance_query(
            current_balance,
            f"未匹配: 差值={diff}, 订单总额={total}",
            None,
        )
        return False

    def update_base_balances_after_expiry(self) -> None:
        """
        订单超时/取消后，更新后续待支付订单的基准余额为当前实际余额。
        避免已失效订单的基准值干扰后续匹配。
        按凭证分组更新，每组使用对应凭证查询余额。
        """
        pending = self._get_pending_orders()
        if not pending:
            return

        # 按 credential_id 分组
        groups: dict[int | None, list[dict]] = {}
        for o in pending:
            cid = o.get("credential_id")
            groups.setdefault(cid, []).append(o)

        db = get_db()
        try:
            for cid, orders in groups.items():
                try:
                    balance = self.query_balance(cid)
                except AlipayClientError as e:
                    logger.warning("更新基准余额失败(credential_id=%s): %s", cid, e)
                    continue
                ids = [o["id"] for o in orders]
                placeholders = ",".join("?" for _ in ids)
                db.execute(
                    f"UPDATE orders SET base_balance = ? WHERE id IN ({placeholders})",
                    [str(balance)] + ids,
                )
                logger.info("已更新凭证 %s 下 %d 笔待支付订单的基准余额为 %s", cid, len(ids), balance)
            db.commit()
        finally:
            db.close()


