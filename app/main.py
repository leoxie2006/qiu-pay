"""
Qiu-Pay 应用入口：FastAPI 应用实例、路由注册、生命周期和后台任务。
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


# ── 后台任务 ──────────────────────────────────────────────

async def _order_expiry_task() -> None:
    """定期检查并过期超时订单（每 60 秒）。"""
    from app.services.order_service import OrderService

    svc = OrderService()
    while True:
        try:
            svc.expire_orders()
            logger.debug("订单过期检查完成")
        except Exception as e:
            logger.error("订单过期检查异常: %s", e)
        await asyncio.sleep(60)


async def _callback_retry_task() -> None:
    """定期重试失败的回调通知（每 30 秒扫描一次）。

    查询 callback_status IN (2,3) 且 callback_attempts <= max 的已支付订单，
    根据重试间隔决定是否重试。
    重试间隔：[5, 30, 60, 300, 1800] 秒。
    """
    from app.services.callback_service import CallbackService
    from app.database import get_db

    svc = CallbackService()
    retry_intervals = CallbackService.RETRY_INTERVALS

    while True:
        try:
            db = get_db()
            try:
                rows = db.execute(
                    """SELECT id, callback_attempts, callback_status,
                              paid_at, created_at
                       FROM orders
                       WHERE callback_status IN (2, 3)
                         AND callback_attempts >= 1
                         AND callback_attempts <= ?
                         AND status = 1
                         AND notify_url IS NOT NULL
                         AND notify_url != ''""",
                    (len(retry_intervals),),
                ).fetchall()
            finally:
                db.close()

            now = datetime.now()
            for row in rows:
                order_id = row["id"]
                attempts = row["callback_attempts"]
                retry_index = attempts - 1

                if retry_index >= len(retry_intervals):
                    continue

                paid_at_str = row["paid_at"] or row["created_at"]
                try:
                    base_time = datetime.strptime(
                        paid_at_str, "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    continue

                total_wait = sum(retry_intervals[:retry_index + 1])
                if (now - base_time).total_seconds() >= total_wait:
                    try:
                        svc.retry_notify(order_id, retry_index + 1)
                        logger.info(
                            "回调重试完成 (order_id=%d, attempt=%d)",
                            order_id, retry_index + 1,
                        )
                    except Exception as e:
                        logger.error(
                            "回调重试异常 (order_id=%d): %s", order_id, e
                        )
        except Exception as e:
            logger.error("回调重试任务异常: %s", e)

        await asyncio.sleep(30)


# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库并启动后台任务。"""
    from app.database import init_db

    init_db()
    logger.info("数据库初始化完成")

    tasks = []
    if os.environ.get("TESTING") != "1":
        tasks.append(asyncio.create_task(_order_expiry_task()))
        tasks.append(asyncio.create_task(_callback_retry_task()))
        logger.info("后台任务已启动：订单过期检查、回调通知重试")

    yield

    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Qiu-Pay", description="支付中间平台", lifespan=lifespan)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 挂载文档图片目录
_docs_public = BASE_DIR.parent / "docs" / "public"
if _docs_public.exists():
    app.mount("/docs/public", StaticFiles(directory=str(_docs_public)), name="docs-public")

# ── CORS 中间件（开发环境跨域） ────────────────────────────

if os.environ.get("CORS_ENABLED", "0") == "1":
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── 路由注册 ──────────────────────────────────────────────

from app.routes.payment import router as payment_router
from app.routes.query import router as query_router
from app.routes.admin import router as admin_router
from app.routes.docs import router as docs_router

app.include_router(payment_router)
app.include_router(query_router)
app.include_router(admin_router)
app.include_router(docs_router)


# ── 健康检查 ──────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ── SPA 静态文件服务与 Fallback ───────────────────────────

SPA_DIR = BASE_DIR / "static" / "spa"

if SPA_DIR.exists():
    # 挂载 Vue 构建产物的 assets 目录
    _spa_assets = SPA_DIR / "assets"
    if _spa_assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_spa_assets)), name="spa-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """非 API 路径返回 index.html，实现 SPA 路由 fallback。"""
        index_file = SPA_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
