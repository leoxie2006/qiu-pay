"""
管理后台路由：认证（登录）、仪表盘、商户管理、订单管理、系统设置。
"""

import csv
import io
import math
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.database import get_db
from app.services.auth import authenticate, get_current_admin, hash_password, verify_password
from app.services.callback_service import CallbackService
from app.services.merchant_service import MerchantService
from app.services.platform_config import (
    PlatformConfigError,
    get_credential_status,
    get_qrcode_status,
    save_credentials,
    upload_qrcode,
    get_merchant_credentials,
    save_merchant_credential,
    toggle_merchant_credential,
    delete_merchant_credential,
)

router = APIRouter(prefix="/v1/admin")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    """
    管理员登录。

    接收 JSON {username, password}，
    成功返回 {code: 1, token: "..."}，
    失败返回 {code: -1, msg: "..."}。
    """
    try:
        result = authenticate(body.username, body.password)
        return JSONResponse(content=result)
    except ValueError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})


# ── 仪表盘 ────────────────────────────────────────────────


def _query_day_stats(db, day_str: str) -> dict:
    """查询某天的订单统计（总数、成功数、成功金额），金额用整数分计算避免浮点精度问题。"""
    row = db.execute(
        """
        SELECT
            COUNT(*)                                          AS total,
            SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END)      AS success,
            COALESCE(SUM(CASE WHEN status = 1 THEN CAST(ROUND(money * 100, 0) AS INTEGER) ELSE 0 END), 0) AS amount_cents
        FROM orders
        WHERE date(created_at) = ?
        """,
        (day_str,),
    ).fetchone()
    return {
        "total": row["total"] or 0,
        "success": row["success"] or 0,
        "amount": round((row["amount_cents"] or 0) / 100, 2),
    }


@router.get("/dashboard")
async def dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    """管理后台仪表盘：统计数据 + 趋势图 + 最近订单 + 平台状态。"""
    db = get_db()
    try:
        return _render_dashboard(db)
    finally:
        db.close()



def _render_dashboard(db):
    """Build dashboard JSON response with stats, chart, recent orders, and platform info."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    # 今日 / 昨日统计
    today_stats = _query_day_stats(db, today.isoformat())
    yesterday_stats = _query_day_stats(db, yesterday.isoformat())

    # 总计统计
    total_row = db.execute(
        """
        SELECT
            COUNT(*)                                          AS total,
            SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END)      AS success,
            COALESCE(SUM(CASE WHEN status = 1 THEN CAST(ROUND(money * 100, 0) AS INTEGER) ELSE 0 END), 0) AS amount_cents
        FROM orders
        """
    ).fetchone()

    total_stats = {
        "total": total_row["total"] or 0,
        "success": total_row["success"] or 0,
        "amount": round((total_row["amount_cents"] or 0) / 100, 2),
    }

    # 近 7 天趋势
    chart_labels = []
    chart_order_counts = []
    chart_amounts = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        chart_labels.append(d.strftime("%m-%d"))
        row = db.execute(
            """
            SELECT
                COUNT(*)                                          AS cnt,
                COALESCE(SUM(CASE WHEN status = 1 THEN CAST(ROUND(money * 100, 0) AS INTEGER) ELSE 0 END), 0) AS amt_cents
            FROM orders WHERE date(created_at) = ?
            """,
            (d_str,),
        ).fetchone()
        chart_order_counts.append(row["cnt"] or 0)
        chart_amounts.append(round((row["amt_cents"] or 0) / 100, 2))

    # 最近 10 笔订单
    recent_rows = db.execute(
        "SELECT trade_no, merchant_id, name, money, status, created_at FROM orders ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    recent_orders = [
        {
            "trade_no": r["trade_no"],
            "merchant_id": r["merchant_id"],
            "name": r["name"],
            "money": str(r["money"]),
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in recent_rows
    ]

    # 平台状态
    merchant_count = db.execute("SELECT COUNT(*) AS cnt FROM merchants").fetchone()["cnt"]

    qr_row = db.execute(
        "SELECT config_value FROM system_config WHERE config_key = 'qrcode_url'"
    ).fetchone()
    qrcode_status = "已配置" if (qr_row and qr_row["config_value"]) else "未配置"

    cred_row = db.execute(
        "SELECT config_value FROM system_config WHERE config_key = 'credential_status'"
    ).fetchone()
    cred_val = cred_row["config_value"] if cred_row else None
    credential_map = {
        "unconfigured": "未配置",
        "configured": "已配置",
        "verified": "验证通过",
        "failed": "验证失败",
    }
    credential_status = credential_map.get(cred_val, "未配置")

    return JSONResponse(content={
        "code": 1,
        "today_stats": today_stats,
        "yesterday_stats": yesterday_stats,
        "total_stats": total_stats,
        "chart": {
            "labels": chart_labels,
            "order_counts": chart_order_counts,
            "amounts": chart_amounts,
        },
        "recent_orders": recent_orders,
        "platform": {
            "merchant_count": merchant_count,
            "qrcode_status": qrcode_status,
            "credential_status": credential_status,
        },
    })


# ── 商户管理 ────────────────────────────────────────────────


class CreateMerchantRequest(BaseModel):
    username: str
    email: str


class UpdateMerchantRequest(BaseModel):
    action: str  # "toggle" or "reset_key"
    active: int | None = None  # 0 or 1, required when action="toggle"



@router.get("/merchants")
async def merchant_list(admin: dict = Depends(get_current_admin)):
    """商户列表，返回 JSON。"""
    svc = MerchantService()
    merchants = svc.list_merchants()
    return JSONResponse(content={"code": 1, "merchants": merchants})




@router.post("/merchants")
async def create_merchant(body: CreateMerchantRequest, admin: dict = Depends(get_current_admin)):
    """创建商户，返回 JSON。"""
    svc = MerchantService()
    try:
        m = svc.create_merchant(body.username, body.email)
        return JSONResponse(content={
            "code": 1,
            "merchant": {
                "pid": m.id,
                "username": m.username,
                "email": m.email,
                "key": m.key,
                "active": m.active,
                "created_at": m.created_at,
            },
        })
    except ValueError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})


@router.put("/merchants/{pid}")
async def update_merchant(pid: int, body: UpdateMerchantRequest, admin: dict = Depends(get_current_admin)):
    """更新商户：封禁/解封 或 重置密钥。"""
    svc = MerchantService()
    try:
        if body.action == "toggle":
            if body.active is None:
                return JSONResponse(content={"code": -1, "msg": "缺少 active 参数"})
            svc.toggle_status(pid, bool(body.active))
            status_text = "解封" if body.active else "封禁"
            return JSONResponse(content={"code": 1, "msg": f"商户已{status_text}"})
        elif body.action == "reset_key":
            new_key = svc.reset_key(pid)
            return JSONResponse(content={"code": 1, "msg": "密钥已重置", "key": new_key})
        else:
            return JSONResponse(content={"code": -1, "msg": f"未知操作: {body.action}"})
    except ValueError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})


# ── 订单管理 ────────────────────────────────────────────────

STATUS_MAP = {0: "待支付", 1: "已支付", 2: "已超时"}
CALLBACK_STATUS_MAP = {0: "未通知", 1: "成功", 2: "失败", 3: "通知中"}


def _build_order_filters(
    pid: str | None,
    status: str | None,
    trade_no: str | None,
    start_date: str | None,
    end_date: str | None,
):
    """构建订单筛选 SQL 条件和参数。"""
    conditions = []
    params = []
    if pid:
        conditions.append("o.merchant_id = ?")
        params.append(int(pid))
    if status is not None and status != "":
        conditions.append("o.status = ?")
        params.append(int(status))
    if trade_no:
        conditions.append("(o.trade_no LIKE ? OR o.out_trade_no LIKE ?)")
        params.extend([f"%{trade_no}%", f"%{trade_no}%"])
    if start_date:
        conditions.append("o.created_at >= ?")
        params.append(f"{start_date} 00:00:00")
    if end_date:
        conditions.append("o.created_at <= ?")
        params.append(f"{end_date} 23:59:59")
    return conditions, params


@router.get("/orders/export")
async def export_orders(
    request: Request,
    admin: dict = Depends(get_current_admin),
    pid: str | None = Query(None),
    status: str | None = Query(None),
    trade_no: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    """导出订单列表为 CSV 文件。"""
    db = get_db()
    try:
        conditions, params = _build_order_filters(pid, status, trade_no, start_date, end_date)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = db.execute(
            f"""SELECT o.trade_no, o.out_trade_no, o.merchant_id, o.type, o.name,
                       o.original_money, o.money, o.status, o.callback_status,
                       o.created_at, o.paid_at
                FROM orders o
                WHERE {where_clause}
                ORDER BY o.created_at DESC""",
            params,
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "平台订单号", "商户订单号", "商户ID", "支付方式", "商品名称",
            "原始金额", "实付金额", "支付状态", "回调状态", "创建时间", "支付时间",
        ])
        for r in rows:
            writer.writerow([
                r["trade_no"], r["out_trade_no"], r["merchant_id"], r["type"], r["name"],
                r["original_money"], r["money"],
                STATUS_MAP.get(r["status"], str(r["status"])),
                CALLBACK_STATUS_MAP.get(r["callback_status"], str(r["callback_status"])),
                r["created_at"], r["paid_at"] or "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=orders.csv"},
        )
    finally:
        db.close()



@router.get("/orders/{trade_no}")
async def order_detail(trade_no: str, admin: dict = Depends(get_current_admin)):
    """订单详情，返回 JSON。"""
    db = get_db()
    try:
        order = db.execute(
            "SELECT * FROM orders WHERE trade_no = ?", (trade_no,)
        ).fetchone()
        if not order:
            return JSONResponse(status_code=404, content={"code": -1, "msg": "订单不存在"})

        callback_logs = db.execute(
            "SELECT * FROM callback_logs WHERE order_id = ? ORDER BY created_at DESC",
            (order["id"],),
        ).fetchall()

        order_dict = {
            "trade_no": order["trade_no"],
            "out_trade_no": order["out_trade_no"],
            "merchant_id": order["merchant_id"],
            "type": order["type"],
            "name": order["name"],
            "original_money": str(order["original_money"]),
            "money": str(order["money"]),
            "status": order["status"],
            "status_text": STATUS_MAP.get(order["status"], str(order["status"])),
            "callback_status": order["callback_status"],
            "callback_status_text": CALLBACK_STATUS_MAP.get(
                order["callback_status"], str(order["callback_status"])
            ),
            "notify_url": order["notify_url"] or "",
            "return_url": order["return_url"] or "",
            "created_at": order["created_at"],
            "paid_at": order["paid_at"],
        }

        logs_list = [
            {
                "id": log["id"],
                "status_code": log["http_status"],
                "response_body": log["response_body"],
                "created_at": log["created_at"],
            }
            for log in callback_logs
        ]

        return JSONResponse(content={
            "code": 1,
            "order": order_dict,
            "callback_logs": logs_list,
        })
    finally:
        db.close()




@router.post("/orders/{trade_no}/renotify")
async def renotify_order(trade_no: str, admin: dict = Depends(get_current_admin)):
    """重新发送回调通知（已支付订单重发，待支付订单手动触发）。"""
    db = get_db()
    try:
        order = db.execute(
            "SELECT id, status, notify_url FROM orders WHERE trade_no = ?", (trade_no,)
        ).fetchone()
        if not order:
            return JSONResponse(status_code=404, content={"code": -1, "msg": "订单不存在"})
        if order["status"] not in (0, 1):
            return JSONResponse(content={"code": -1, "msg": "仅待支付或已支付订单可发送通知"})
        if not order["notify_url"]:
            return JSONResponse(content={"code": -1, "msg": "该订单未配置通知地址"})

        svc = CallbackService()
        success = svc.send_notify(order["id"])
        if success:
            return JSONResponse(content={"code": 1, "msg": "通知发送成功"})
        else:
            return JSONResponse(content={"code": -1, "msg": "通知发送失败，请查看回调日志"})
    finally:
        db.close()


@router.post("/orders/{trade_no}/cancel")
async def cancel_order(trade_no: str, admin: dict = Depends(get_current_admin)):
    """取消订单（仅待支付订单可取消）。"""
    from datetime import datetime as dt
    db = get_db()
    try:
        order = db.execute(
            "SELECT id, status FROM orders WHERE trade_no = ?", (trade_no,)
        ).fetchone()
        if not order:
            return JSONResponse(status_code=404, content={"code": -1, "msg": "订单不存在"})
        if order["status"] != 0:
            return JSONResponse(content={"code": -1, "msg": "仅待支付订单可取消"})

        now = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE orders SET status = 2, expired_at = ? WHERE id = ?",
            (now, order["id"]),
        )
        db.commit()

        # 取消轮询任务
        from app.services.payment_poller import cancel_payment_polling
        cancel_payment_polling(trade_no)

        return JSONResponse(content={"code": 1, "msg": "订单已取消"})
    finally:
        db.close()



@router.get("/orders")
async def order_list(
    admin: dict = Depends(get_current_admin),
    pid: str | None = Query(None),
    status: str | None = Query(None),
    trade_no: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """订单列表接口（支持筛选和分页），返回 JSON。"""
    db = get_db()
    try:
        conditions, params = _build_order_filters(pid, status, trade_no, start_date, end_date)
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 总数
        count_row = db.execute(
            f"SELECT COUNT(*) AS cnt FROM orders o WHERE {where_clause}", params
        ).fetchone()
        total = count_row["cnt"]
        total_pages = max(1, math.ceil(total / per_page))

        # 分页数据
        offset = (page - 1) * per_page
        rows = db.execute(
            f"""SELECT o.trade_no, o.out_trade_no, o.merchant_id, o.type, o.name,
                       o.original_money, o.money, o.status, o.callback_status,
                       o.created_at, o.paid_at
                FROM orders o
                WHERE {where_clause}
                ORDER BY o.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

        orders = [dict(r) for r in rows]

        return JSONResponse(content={
            "code": 1,
            "orders": orders,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        })
    finally:
        db.close()




# ── 系统设置 ────────────────────────────────────────────────


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class AlipayCredentialsRequest(BaseModel):
    app_id: str
    public_key: str
    private_key: str


@router.get("/settings")
async def settings_page(admin: dict = Depends(get_current_admin)):
    """系统设置页面：返回收款码和凭证配置状态 JSON。"""
    qrcode_status = get_qrcode_status()
    credential_status = get_credential_status()

    # 如果凭证已配置，附加 app_id（脱敏）
    if credential_status["status"] != "unconfigured":
        from app.services.platform_config import get_credentials
        creds = get_credentials()
        if creds:
            credential_status["app_id"] = creds["app_id"]

    return JSONResponse(content={
        "code": 1,
        "qrcode_status": qrcode_status,
        "credential_status": credential_status,
    })



@router.post("/settings/qrcode")
async def upload_qrcode_route(
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin),
):
    """上传收款码图片。"""
    try:
        content = await file.read()
        result = upload_qrcode(content, file.filename or "upload.png")
        return JSONResponse(content={"code": 1, "msg": "收款码上传成功", **result})
    except PlatformConfigError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(content={"code": -1, "msg": f"上传失败: {e}"})


@router.post("/settings/alipay-credentials")
async def save_alipay_credentials_route(
    body: AlipayCredentialsRequest,
    admin: dict = Depends(get_current_admin),
):
    """配置支付宝应用凭证。"""
    try:
        result = save_credentials(body.app_id, body.public_key, body.private_key)
        return JSONResponse(content={"code": 1, **result})
    except PlatformConfigError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(content={"code": -1, "msg": f"保存失败: {e}"})


@router.post("/settings/change-password")
async def change_password_route(
    body: ChangePasswordRequest,
    admin: dict = Depends(get_current_admin),
):
    """修改管理员密码。"""
    username = admin.get("sub")
    if not username:
        return JSONResponse(content={"code": -1, "msg": "无法识别当前用户"})

    db = get_db()
    try:
        row = db.execute(
            "SELECT id, password_hash FROM admin WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return JSONResponse(content={"code": -1, "msg": "用户不存在"})

        if not verify_password(body.old_password, row["password_hash"]):
            return JSONResponse(content={"code": -1, "msg": "原密码错误"})

        if len(body.new_password) < 6:
            return JSONResponse(content={"code": -1, "msg": "新密码长度不能少于6位"})

        new_hash = hash_password(body.new_password)
        db.execute(
            "UPDATE admin SET password_hash = ? WHERE id = ?",
            (new_hash, row["id"]),
        )
        db.commit()
        return JSONResponse(content={"code": 1, "msg": "密码修改成功"})
    finally:
        db.close()


# ── 商户凭证管理 ────────────────────────────────────────────


@router.get("/merchants/{pid}/credentials")
async def list_merchant_credentials(pid: int, admin: dict = Depends(get_current_admin)):
    """获取商户的凭证配置列表。"""
    credentials = get_merchant_credentials(pid)
    return JSONResponse(content={"code": 1, "credentials": credentials})


@router.post("/merchants/{pid}/credentials")
async def create_merchant_credential(
    pid: int,
    request: Request,
    admin: dict = Depends(get_current_admin),
):
    """新增商户凭证配置（收款码+支付宝凭证绑定）。"""
    form = await request.form()
    app_id = form.get("app_id", "")
    public_key = form.get("public_key", "")
    private_key = form.get("private_key", "")
    file = form.get("file")

    qrcode_content = None
    qrcode_filename = None
    if file and hasattr(file, "read"):
        qrcode_content = await file.read()
        qrcode_filename = getattr(file, "filename", "upload.png")

    try:
        result = save_merchant_credential(
            merchant_id=pid,
            qrcode_content=qrcode_content,
            qrcode_filename=qrcode_filename,
            app_id=app_id,
            public_key=public_key,
            private_key=private_key,
        )
        return JSONResponse(content={"code": 1, "msg": "凭证配置保存成功", **result})
    except PlatformConfigError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(content={"code": -1, "msg": f"保存失败: {e}"})


@router.put("/merchants/{pid}/credentials/{cred_id}")
async def update_merchant_credential(
    pid: int,
    cred_id: int,
    request: Request,
    admin: dict = Depends(get_current_admin),
):
    """更新商户凭证配置。"""
    form = await request.form()
    app_id = form.get("app_id", "")
    public_key = form.get("public_key", "")
    private_key = form.get("private_key", "")
    file = form.get("file")

    qrcode_content = None
    qrcode_filename = None
    if file and hasattr(file, "read"):
        qrcode_content = await file.read()
        qrcode_filename = getattr(file, "filename", "upload.png")

    try:
        result = save_merchant_credential(
            merchant_id=pid,
            qrcode_content=qrcode_content,
            qrcode_filename=qrcode_filename,
            app_id=app_id,
            public_key=public_key,
            private_key=private_key,
            credential_id=cred_id,
        )
        return JSONResponse(content={"code": 1, "msg": "凭证配置更新成功", **result})
    except PlatformConfigError as e:
        return JSONResponse(content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(content={"code": -1, "msg": f"更新失败: {e}"})


@router.post("/merchants/{pid}/credentials/{cred_id}/toggle")
async def toggle_credential(
    pid: int, cred_id: int, admin: dict = Depends(get_current_admin)
):
    """启用/禁用商户凭证。"""
    from app.services.platform_config import get_credential_by_id
    cred = get_credential_by_id(cred_id)
    if not cred:
        return JSONResponse(content={"code": -1, "msg": "凭证不存在"})
    new_active = not bool(cred.get("active", 1))
    toggle_merchant_credential(cred_id, new_active)
    return JSONResponse(content={
        "code": 1,
        "msg": "已启用" if new_active else "已禁用",
    })


@router.delete("/merchants/{pid}/credentials/{cred_id}")
async def remove_credential(
    pid: int, cred_id: int, admin: dict = Depends(get_current_admin)
):
    """删除商户凭证配置。"""
    delete_merchant_credential(cred_id)
    return JSONResponse(content={"code": 1, "msg": "凭证配置已删除"})
