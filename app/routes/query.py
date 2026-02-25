"""
查询接口路由：GET /xpay/epay/api.php

支持两种查询：
- act=order: 订单查询（通过 trade_no 或 out_trade_no）
- act=query: 商户信息查询
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.database import get_db
from app.services.merchant_service import MerchantService

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_merchant(pid: Optional[str], key: Optional[str]) -> tuple:
    """
    验证商户 pid 和 key。

    Returns:
        (merchant_row, error_response) — 成功时 error_response 为 None。
    """
    if not pid or not key:
        return None, JSONResponse(content={"code": -1, "msg": "缺少必填参数pid或key"})

    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None, JSONResponse(content={"code": -1, "msg": "商户ID无效"})

    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM merchants WHERE id = ?", (pid_int,)
        ).fetchone()
    finally:
        db.close()

    if not row:
        return None, JSONResponse(content={"code": -1, "msg": "商户不存在"})

    if row["key"] != key:
        return None, JSONResponse(content={"code": -1, "msg": "商户密钥错误"})

    return row, None


@router.get("/xpay/epay/api.php")
async def query_api(
    act: Optional[str] = Query(None),
    pid: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    trade_no: Optional[str] = Query(None),
    out_trade_no: Optional[str] = Query(None),
):
    """
    查询接口入口。

    - act=order: 订单查询
    - act=query: 商户信息查询
    """
    if not act:
        return JSONResponse(content={"code": -1, "msg": "缺少act参数"})

    if act == "order":
        return _handle_order_query(pid, key, trade_no, out_trade_no)
    elif act == "query":
        return _handle_merchant_query(pid, key)
    else:
        return JSONResponse(content={"code": -1, "msg": f"不支持的操作: {act}"})


def _handle_order_query(
    pid: Optional[str],
    key: Optional[str],
    trade_no: Optional[str],
    out_trade_no: Optional[str],
) -> JSONResponse:
    """act=order 订单查询处理。"""
    merchant_row, err = _validate_merchant(pid, key)
    if err:
        return err

    pid_int = merchant_row["id"]

    # trade_no 优先
    if not trade_no and not out_trade_no:
        return JSONResponse(content={"code": -1, "msg": "缺少trade_no或out_trade_no参数"})

    db = get_db()
    try:
        if trade_no:
            order = db.execute(
                "SELECT * FROM orders WHERE trade_no = ? AND merchant_id = ?",
                (trade_no, pid_int),
            ).fetchone()
        else:
            order = db.execute(
                "SELECT * FROM orders WHERE out_trade_no = ? AND merchant_id = ?",
                (out_trade_no, pid_int),
            ).fetchone()
    finally:
        db.close()

    if not order:
        return JSONResponse(content={"code": -1, "msg": "订单不存在"})

    status = order["status"]

    # 待支付订单：触发余额检测判断是否到账
    if status == 0:
        try:
            from app.services.balance_checker import BalanceChecker
            checker = BalanceChecker()
            paid = checker.check_payment(order["trade_no"])
            if paid:
                status = 1
                logger.info(
                    "订单查询触发余额检测: trade_no=%s, 结果=已支付",
                    order["trade_no"],
                )
            else:
                logger.info(
                    "订单查询触发余额检测: trade_no=%s, 结果=未匹配",
                    order["trade_no"],
                )
        except Exception as e:
            logger.warning(
                "订单查询余额检测异常 (trade_no=%s): %s",
                order["trade_no"], e,
            )

    return JSONResponse(content={
        "code": 1,
        "msg": "success",
        "trade_no": order["trade_no"],
        "out_trade_no": order["out_trade_no"],
        "api_trade_no": order["api_trade_no"] or "",
        "type": order["type"],
        "pid": order["merchant_id"],
        "addtime": order["created_at"] or "",
        "endtime": order["paid_at"] or "",
        "name": order["name"],
        "money": f'{float(order["money"]):.2f}',
        "status": 1 if status == 1 else 0,
        "param": order["param"] or "",
        "buyer": order["buyer"] or "",
    })


def _handle_merchant_query(
    pid: Optional[str],
    key: Optional[str],
) -> JSONResponse:
    """act=query 商户信息查询处理。"""
    merchant_row, err = _validate_merchant(pid, key)
    if err:
        return err

    pid_int = merchant_row["id"]

    svc = MerchantService()
    try:
        info = svc.get_merchant_info(pid_int)
    except ValueError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})

    return JSONResponse(content=info)
