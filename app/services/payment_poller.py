"""
支付轮询调度器：订单创建后自动启动后台余额检测任务。

轮询策略：
- 有未完成订单时：每1秒查询一次
- 10分钟后：订单过期，停止轮询
"""

import asyncio
import logging
from datetime import datetime

from app.database import get_db

logger = logging.getLogger(__name__)

# 活跃的轮询任务 {trade_no: asyncio.Task}
_active_tasks: dict[str, asyncio.Task] = {}


def _get_poll_interval(elapsed_seconds: float) -> float | None:
    """
    根据已过时间返回轮询间隔（秒）。
    有未完成订单时固定每秒查询一次。
    超过 10 分钟返回 None 表示停止轮询。
    """
    if elapsed_seconds < 600:
        return 1.0
    else:
        return None



async def _poll_order_payment(trade_no: str) -> None:
    """
    对指定订单执行递减频率的余额轮询。

    检测到支付成功或订单不再是待支付状态时停止。
    """
    from app.services.balance_checker import BalanceChecker

    logger.info("启动支付轮询: trade_no=%s", trade_no)
    start_time = datetime.now()
    checker = BalanceChecker()
    poll_count = 0

    try:
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            interval = _get_poll_interval(elapsed)

            if interval is None:
                logger.info(
                    "轮询超时(10分钟), 停止轮询: trade_no=%s, 共轮询%d次",
                    trade_no, poll_count,
                )
                # 标记订单过期
                _expire_order(trade_no)
                break

            # 检查订单当前状态
            db = get_db()
            try:
                row = db.execute(
                    "SELECT status FROM orders WHERE trade_no = ?",
                    (trade_no,),
                ).fetchone()
            finally:
                db.close()

            if not row:
                logger.warning("轮询中订单不存在: trade_no=%s", trade_no)
                break

            if row["status"] != 0:
                logger.info(
                    "订单已非待支付状态, 停止轮询: trade_no=%s, status=%d",
                    trade_no, row["status"],
                )
                break

            # 执行余额检测
            poll_count += 1
            try:
                paid = checker.check_payment(trade_no)
                if paid:
                    logger.info(
                        "轮询检测到支付成功: trade_no=%s, 耗时%.1f秒, 共轮询%d次",
                        trade_no, elapsed, poll_count,
                    )
                    break
            except Exception as e:
                logger.warning(
                    "轮询余额检测异常: trade_no=%s, error=%s",
                    trade_no, e,
                )

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        logger.info("轮询任务被取消: trade_no=%s", trade_no)
    finally:
        _active_tasks.pop(trade_no, None)


def _expire_order(trade_no: str) -> None:
    """将订单标记为超时。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        db.execute(
            """UPDATE orders SET status = 2, expired_at = ?
               WHERE trade_no = ? AND status = 0""",
            (now, trade_no),
        )
        db.commit()
        logger.info("订单已过期: trade_no=%s", trade_no)
    finally:
        db.close()


def start_payment_polling(trade_no: str) -> None:
    """
    为指定订单启动后台支付轮询任务。

    如果该订单已有轮询任务在运行，则跳过。
    """
    if trade_no in _active_tasks:
        logger.debug("轮询任务已存在: trade_no=%s", trade_no)
        return

    try:
        loop = asyncio.get_event_loop()
        task = loop.create_task(_poll_order_payment(trade_no))
        _active_tasks[trade_no] = task
    except RuntimeError:
        logger.warning("无法启动轮询任务(无事件循环): trade_no=%s", trade_no)


def cancel_payment_polling(trade_no: str) -> None:
    """取消指定订单的轮询任务。"""
    task = _active_tasks.pop(trade_no, None)
    if task and not task.done():
        task.cancel()


def get_active_polling_count() -> int:
    """返回当前活跃的轮询任务数量。"""
    return len(_active_tasks)
