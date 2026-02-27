"""
支付接口路由：POST /xpay/epay/mapi.php

接收商户支付请求，校验参数和签名，创建订单并返回支付信息。
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.services.sign import verify_sign
from app.services.order_service import OrderService, AmountConflictError, OrderCreateError
from app.services.callback_service import CallbackService

logger = logging.getLogger(__name__)

router = APIRouter()

# 必填参数列表
REQUIRED_PARAMS = ["pid", "type", "out_trade_no", "name", "money", "sign", "sign_type"]


@router.post("/xpay/epay/mapi.php")
async def create_payment(request: Request):
    """
    创建支付订单接口。

    流程：校验必填参数 → 查找商户获取 KEY → 验证签名 → 创建订单 → 返回结果
    """
    form_data = await request.form()
    params = {k: v for k, v in form_data.items() if isinstance(v, str)}

    # 1. 校验必填参数
    missing = [k for k in REQUIRED_PARAMS if not params.get(k)]
    if missing:
        return JSONResponse(content={
            "code": -1,
            "msg": f"缺少必填参数: {', '.join(missing)}",
        })

    pid = params["pid"]
    sign = params["sign"]

    # 2. 查找商户获取 KEY
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return JSONResponse(content={"code": -1, "msg": "商户ID无效"})

    db = get_db()
    try:
        merchant_row = db.execute(
            "SELECT * FROM merchants WHERE id = ?", (pid_int,)
        ).fetchone()
    finally:
        db.close()

    if not merchant_row:
        return JSONResponse(content={"code": -1, "msg": "商户不存在"})
    if merchant_row["active"] != 1:
        return JSONResponse(content={"code": -1, "msg": "商户已被封禁"})

    merchant_key = merchant_row["key"]

    # 3. 验证签名（generate_sign 会自动过滤 sign/sign_type 和空值）
    if not verify_sign(params, merchant_key, sign):
        return JSONResponse(content={"code": -1, "msg": "签名错误"})

    # 4. 调用 OrderService 创建订单
    device = params.get("device", "pc")
    order_params = {
        "pid": pid,
        "type": params.get("type", "alipay"),
        "out_trade_no": params["out_trade_no"],
        "name": params["name"],
        "money": params["money"],
        "notify_url": params.get("notify_url"),
        "return_url": params.get("return_url"),
        "clientip": params.get("clientip"),
        "device": device,
        "param": params.get("param"),
        "channel_id": params.get("channel_id"),
    }

    try:
        order_svc = OrderService()
        logger.info("开始创建订单: pid=%s, out_trade_no=%s, money=%s",
                     params.get("pid"), params.get("out_trade_no"), params.get("money"))
        order, qrcode_url = order_svc.create_order(order_params)
        logger.info("订单创建成功: trade_no=%s, money=%s, base_balance 已记录",
                     order.trade_no, order.money)
    except AmountConflictError:
        return JSONResponse(content={"code": -1, "msg": "当前下单繁忙，请稍后重试"})
    except OrderCreateError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})

    # 启动后台支付轮询
    from app.services.payment_poller import start_payment_polling
    start_payment_polling(order.trade_no)

    # 5. 构建响应 - 只返回 qrcode（收款码链接）
    response = {
        "code": 1,
        "trade_no": order.trade_no,
        "qrcode": qrcode_url,
        "money": str(order.money),
    }

    return JSONResponse(content=response)


# 状态文本映射
_STATUS_TEXT = {0: "待支付", 1: "已支付", 2: "已超时"}


@router.get("/v1/api/order/status/{trade_no}")
async def get_order_status(trade_no: str):
    """
    订单状态轮询接口（公开，无需认证）。

    前端支付页面调用，仅返回数据库中的当前状态，不触发余额检测。
    余额检测由商户查询接口（act=order）驱动。
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT trade_no, status FROM orders WHERE trade_no = ?",
            (trade_no,),
        ).fetchone()
    finally:
        db.close()

    if not row:
        return JSONResponse(content={"code": -1, "msg": "订单不存在"})

    status = row["status"]

    return JSONResponse(content={
        "code": 1,
        "trade_no": trade_no,
        "status": status,
        "status_text": _STATUS_TEXT.get(status, "未知"),
    })


@router.get("/v1/pay/{trade_no}")
async def pay_page(trade_no: str):
    """
    支付页面数据接口（公开，无需认证）。

    返回订单信息、收款码 URL 和 return_url 的 JSON 数据，
    供前端 Vue SPA 渲染支付页面。
    """
    db = get_db()
    try:
        row = db.execute(
            """SELECT id, trade_no, name, money, status, return_url,
                      created_at, credential_id, merchant_id
               FROM orders WHERE trade_no = ?""",
            (trade_no,),
        ).fetchone()
    finally:
        db.close()

    if not row:
        return JSONResponse(content={"code": -1, "msg": "订单不存在"})

    order = dict(row)

    # Format money to always show 2 decimal places
    try:
        order["money"] = f"{float(order['money']):.2f}"
    except (TypeError, ValueError):
        pass

    # 获取收款码 URL：从订单绑定的凭证获取
    qrcode_url = ""
    if order.get("credential_id"):
        from app.services.platform_config import get_credential_by_id
        cred = get_credential_by_id(order["credential_id"])
        if cred:
            qrcode_url = cred.get("qrcode_url", "")

    # 构建 return_url（已支付时用于前端跳转）
    return_url = ""
    if order["return_url"]:
        try:
            svc = CallbackService()
            return_url = svc.build_return_url(order["id"])
        except Exception:
            return_url = order["return_url"]

    # Build clean order dict for response (exclude internal fields)
    order_data = {
        "trade_no": order["trade_no"],
        "name": order["name"],
        "money": order["money"],
        "status": order["status"],
        "created_at": order["created_at"],
    }

    return JSONResponse(content={
        "code": 1,
        "order": order_data,
        "qrcode_url": qrcode_url,
        "return_url": return_url,
    })
