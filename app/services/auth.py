"""
管理员认证模块：JWT 令牌生成/验证、密码 bcrypt 哈希、登录认证、FastAPI 依赖项。
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Request, HTTPException
from jose import jwt, JWTError

from app.database import get_db

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-to-a-random-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    """使用 bcrypt 对密码进行哈希。"""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """验证密码是否与 bcrypt 哈希匹配。"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(username: str) -> str:
    """生成 JWT 令牌，有效期 24 小时。"""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """
    解码并验证 JWT 令牌。

    Returns:
        解码后的 payload 字典。

    Raises:
        ValueError: 令牌无效或已过期。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if "sub" not in payload:
            raise ValueError("令牌缺少用户信息")
        return payload
    except JWTError as e:
        raise ValueError(f"令牌无效: {e}")


def authenticate(username: str, password: str) -> dict:
    """
    验证管理员用户名和密码。

    - 检查账号是否被锁定（连续 5 次失败锁定 15 分钟）
    - 验证密码
    - 成功：重置失败计数，返回 JWT 令牌
    - 失败：递增失败计数，达到 5 次则设置锁定时间

    Returns:
        {"code": 1, "token": "..."} 成功
        {"code": -1, "msg": "..."} 失败

    Raises:
        ValueError: 认证失败时抛出，msg 包含错误原因。
    """
    db = get_db()
    try:
        admin = db.execute(
            "SELECT * FROM admin WHERE username = ?", (username,)
        ).fetchone()

        if not admin:
            raise ValueError("用户名或密码错误")

        # 检查锁定状态
        if admin["locked_until"]:
            locked_until = datetime.strptime(admin["locked_until"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < locked_until:
                raise ValueError("账号已锁定，请稍后再试")
            # 锁定已过期，重置
            db.execute(
                "UPDATE admin SET login_fail_count = 0, locked_until = NULL WHERE id = ?",
                (admin["id"],),
            )
            db.commit()
            # 重新查询
            admin = db.execute(
                "SELECT * FROM admin WHERE id = ?", (admin["id"],)
            ).fetchone()

        # 验证密码
        if not verify_password(password, admin["password_hash"]):
            fail_count = admin["login_fail_count"] + 1
            if fail_count >= MAX_LOGIN_FAILURES:
                locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                db.execute(
                    "UPDATE admin SET login_fail_count = ?, locked_until = ? WHERE id = ?",
                    (fail_count, locked_until, admin["id"]),
                )
            else:
                db.execute(
                    "UPDATE admin SET login_fail_count = ? WHERE id = ?",
                    (fail_count, admin["id"]),
                )
            db.commit()
            raise ValueError("用户名或密码错误")

        # 登录成功：重置失败计数
        db.execute(
            "UPDATE admin SET login_fail_count = 0, locked_until = NULL WHERE id = ?",
            (admin["id"],),
        )
        db.commit()

        token = create_token(username)
        return {"code": 1, "token": token}
    finally:
        db.close()


def get_current_admin(request: Request) -> dict:
    """
    FastAPI 依赖项：从 Authorization header (Bearer) 或 cookie 中提取并验证 JWT。

    Returns:
        解码后的 payload 字典（包含 sub 等字段）。

    Raises:
        HTTPException(401): 令牌缺失或无效。
    """
    token = None

    # 优先从 Authorization header 获取
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 其次从 cookie 获取
    if not token:
        token = request.cookies.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    try:
        payload = verify_token(token)
        return payload
    except ValueError:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
