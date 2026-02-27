"""
平台配置服务：管理 system_config 表的读写。

提供收款码上传、凭证加密存储、配置状态查询等功能。
使用 Fernet 对称加密保护敏感凭证，密钥由 JWT_SECRET 通过 PBKDF2 派生。
"""

import base64
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.database import get_db
from app.services.qr_parser import QRParseError, parse_qrcode

logger = logging.getLogger(__name__)

# 允许的图片格式和最大文件大小
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# 上传目录
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads"


class PlatformConfigError(Exception):
    """平台配置操作异常。"""
    pass


def _get_fernet() -> Fernet:
    """从 JWT_SECRET 环境变量派生 Fernet 加密密钥。"""
    secret = os.getenv("JWT_SECRET", "default-secret-key")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"qiu-pay-salt",
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    """加密明文字符串，返回密文。"""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def _decrypt(ciphertext: str) -> str:
    """解密密文字符串，返回明文。"""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# ── 通用配置读写 ──────────────────────────────────────────


def get_config(key: str) -> str | None:
    """读取 system_config 表中指定 key 的值。"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT config_value FROM system_config WHERE config_key = ?",
            (key,),
        ).fetchone()
        return row["config_value"] if row else None
    finally:
        db.close()


def set_config(key: str, value: str | None) -> None:
    """写入 system_config 表，存在则更新，不存在则插入。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM system_config WHERE config_key = ?", (key,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE system_config SET config_value = ?, updated_at = ? WHERE config_key = ?",
                (value, now, key),
            )
        else:
            db.execute(
                "INSERT INTO system_config (config_key, config_value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
        db.commit()
    finally:
        db.close()


# ── 收款码上传 ────────────────────────────────────────────


def upload_qrcode(file_content: bytes, filename: str) -> dict:
    """
    上传收款码图片：校验格式和大小 → 保存至本地 → 解析二维码 → 保存配置。

    重新上传时自动删除旧图片。

    Args:
        file_content: 图片文件二进制内容。
        filename: 原始文件名。

    Returns:
        dict: {"qrcode_path": 本地路径, "qrcode_url": 支付宝链接}

    Raises:
        PlatformConfigError: 文件格式不支持、大小超限、解析失败等。
    """
    # 1. 校验文件格式
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise PlatformConfigError("仅支持 PNG 和 JPG 格式")

    # 2. 校验文件大小
    if len(file_content) > MAX_FILE_SIZE:
        raise PlatformConfigError("文件大小不能超过 5MB")

    if len(file_content) == 0:
        raise PlatformConfigError("文件内容为空")

    # 3. 确保上传目录存在
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 4. 删除旧图片（如果存在）
    old_path = get_config("qrcode_path")
    if old_path:
        old_file = Path(old_path)
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                logger.warning("删除旧收款码图片失败: %s", old_path)

    # 5. 保存新图片（使用 UUID 避免文件名冲突）
    new_filename = f"qrcode_{uuid.uuid4().hex[:8]}{ext}"
    save_path = UPLOAD_DIR / new_filename

    save_path.write_bytes(file_content)

    # 6. 解析二维码
    try:
        qrcode_url = parse_qrcode(str(save_path))
    except QRParseError:
        # 解析失败，删除已保存的文件
        save_path.unlink(missing_ok=True)
        raise PlatformConfigError("无法识别收款码，请上传清晰的支付宝收款码图片")

    # 7. 保存配置
    set_config("qrcode_path", str(save_path))
    set_config("qrcode_url", qrcode_url)

    return {"qrcode_path": str(save_path), "qrcode_url": qrcode_url}


# ── 凭证管理 ──────────────────────────────────────────────


def save_credentials(app_id: str, public_key: str, private_key: str) -> dict:
    """
    保存支付宝应用凭证（加密存储），并尝试连通性验证。

    Args:
        app_id: 支付宝应用 ID。
        public_key: 支付宝公钥。
        private_key: 应用私钥。

    Returns:
        dict: {"status": "verified"/"failed", "message": 描述信息}
    """
    if not app_id or not public_key or not private_key:
        raise PlatformConfigError("应用ID、公钥和私钥不能为空")

    # 加密存储
    set_config("alipay_app_id", _encrypt(app_id))
    set_config("alipay_public_key", _encrypt(public_key))
    set_config("alipay_private_key", _encrypt(private_key))

    # 尝试连通性验证
    verified = False
    message = ""
    try:
        from app.services.alipay_client import AlipayClient
        client = AlipayClient(app_id, private_key, public_key)
        client.query_balance()
        verified = True
        message = "凭证验证通过"
    except ImportError:
        # AlipayClient 尚未实现，跳过验证
        message = "凭证已保存（支付宝客户端模块尚未就绪，跳过连通性验证）"
    except Exception as e:
        message = f"凭证验证失败，请检查应用ID和密钥是否正确: {e}"

    status = "verified" if verified else "failed"
    set_config("credential_status", status)

    return {"status": status, "message": message}


def get_credentials() -> dict | None:
    """
    获取解密后的支付宝应用凭证。

    Returns:
        dict: {"app_id", "public_key", "private_key"} 或 None（未配置时）。
    """
    encrypted_app_id = get_config("alipay_app_id")
    encrypted_public_key = get_config("alipay_public_key")
    encrypted_private_key = get_config("alipay_private_key")

    if not encrypted_app_id or not encrypted_public_key or not encrypted_private_key:
        return None

    try:
        return {
            "app_id": _decrypt(encrypted_app_id),
            "public_key": _decrypt(encrypted_public_key),
            "private_key": _decrypt(encrypted_private_key),
        }
    except Exception:
        logger.error("解密凭证失败")
        return None


# ── 状态查询 ──────────────────────────────────────────────


def get_qrcode_status() -> dict:
    """
    获取收款码绑定状态。

    Returns:
        dict: {"configured": bool, "qrcode_url": str|None, "qrcode_path": str|None, "qrcode_image": str|None}
    """
    qrcode_url = get_config("qrcode_url")
    qrcode_path = get_config("qrcode_path")
    # 生成可访问的图片 URL
    qrcode_image = None
    if qrcode_path:
        filename = Path(qrcode_path).name
        qrcode_image = f"/static/uploads/{filename}"
    return {
        "configured": bool(qrcode_url),
        "qrcode_url": qrcode_url,
        "qrcode_path": qrcode_path,
        "qrcode_image": qrcode_image,
    }


def get_credential_status() -> dict:
    """
    获取凭证配置状态。

    Returns:
        dict: {"status": "unconfigured"/"configured"/"verified"/"failed"}
    """
    status = get_config("credential_status")
    has_credentials = get_config("alipay_app_id") is not None

    if not has_credentials:
        return {"status": "unconfigured"}

    return {"status": status or "configured"}


# ── 商户凭证管理 ──────────────────────────────────────────


def save_merchant_credential(
    merchant_id: int,
    qrcode_content: bytes | None,
    qrcode_filename: str | None,
    app_id: str,
    public_key: str,
    private_key: str,
    credential_id: int | None = None,
) -> dict:
    """
    保存或更新商户收款码+凭证绑定配置。

    Args:
        merchant_id: 商户 ID。
        qrcode_content: 收款码图片二进制（新增时必填，更新时可选）。
        qrcode_filename: 收款码图片文件名。
        app_id: 支付宝应用 ID。
        public_key: 支付宝公钥。
        private_key: 应用私钥。
        credential_id: 更新时传入已有记录 ID。

    Returns:
        dict: {"id": int, "status": str, "message": str}
    """
    import uuid
    from pathlib import Path

    if not app_id or not public_key or not private_key:
        raise PlatformConfigError("应用ID、公钥和私钥不能为空")

    qrcode_url = None
    qrcode_path = None

    if qrcode_content and qrcode_filename:
        ext = Path(qrcode_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise PlatformConfigError("仅支持 PNG 和 JPG 格式")
        if len(qrcode_content) > MAX_FILE_SIZE:
            raise PlatformConfigError("文件大小不能超过 5MB")
        if len(qrcode_content) == 0:
            raise PlatformConfigError("文件内容为空")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        new_filename = f"merchant_{merchant_id}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = UPLOAD_DIR / new_filename
        save_path.write_bytes(qrcode_content)

        try:
            qrcode_url = parse_qrcode(str(save_path))
        except QRParseError:
            save_path.unlink(missing_ok=True)
            raise PlatformConfigError("无法识别收款码，请上传清晰的支付宝收款码图片")

        qrcode_path = str(save_path)

    # 加密凭证
    enc_app_id = _encrypt(app_id)
    enc_public_key = _encrypt(public_key)
    enc_private_key = _encrypt(private_key)

    # 连通性验证
    verified = False
    message = ""
    try:
        from app.services.alipay_client import AlipayClient
        client = AlipayClient(app_id, private_key, public_key)
        client.query_balance()
        verified = True
        message = "凭证验证通过"
    except ImportError:
        message = "凭证已保存（跳过连通性验证）"
    except Exception as e:
        message = f"凭证验证失败: {e}"

    status = "verified" if verified else "failed"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    try:
        if credential_id:
            # 更新
            if qrcode_url:
                # 删除旧图片
                old_row = db.execute(
                    "SELECT qrcode_path FROM merchant_credentials WHERE id = ?",
                    (credential_id,),
                ).fetchone()
                if old_row and old_row["qrcode_path"]:
                    old_file = Path(old_row["qrcode_path"])
                    if old_file.exists():
                        try:
                            old_file.unlink()
                        except OSError:
                            pass
                db.execute(
                    """UPDATE merchant_credentials
                       SET qrcode_path = ?, qrcode_url = ?, app_id = ?,
                           public_key = ?, private_key = ?,
                           credential_status = ?, updated_at = ?
                       WHERE id = ?""",
                    (qrcode_path, qrcode_url, enc_app_id,
                     enc_public_key, enc_private_key, status, now, credential_id),
                )
            else:
                db.execute(
                    """UPDATE merchant_credentials
                       SET app_id = ?, public_key = ?, private_key = ?,
                           credential_status = ?, updated_at = ?
                       WHERE id = ?""",
                    (enc_app_id, enc_public_key, enc_private_key,
                     status, now, credential_id),
                )
            db.commit()
            return {"id": credential_id, "status": status, "message": message}
        else:
            # 新增
            if not qrcode_url:
                raise PlatformConfigError("新增凭证配置时必须上传收款码")
            cursor = db.execute(
                """INSERT INTO merchant_credentials
                   (merchant_id, qrcode_path, qrcode_url, app_id,
                    public_key, private_key, credential_status,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (merchant_id, qrcode_path, qrcode_url, enc_app_id,
                 enc_public_key, enc_private_key, status, now, now),
            )
            db.commit()
            return {"id": cursor.lastrowid, "status": status, "message": message}
    finally:
        db.close()


def get_merchant_credentials(merchant_id: int) -> list[dict]:
    """获取商户的所有凭证配置列表。"""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT id, merchant_id, qrcode_path, qrcode_url,
                      app_id, credential_status, active, created_at, updated_at
               FROM merchant_credentials
               WHERE merchant_id = ?
               ORDER BY created_at DESC""",
            (merchant_id,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # 解密 app_id 用于展示
            try:
                d["app_id"] = _decrypt(d["app_id"])
            except Exception:
                d["app_id"] = "解密失败"
            # 生成可访问的图片 URL
            if d.get("qrcode_path"):
                d["qrcode_image"] = f"/static/uploads/{Path(d['qrcode_path']).name}"
            else:
                d["qrcode_image"] = None
            result.append(d)
        return result
    finally:
        db.close()


def get_credential_by_id(credential_id: int) -> dict | None:
    """获取指定凭证的完整解密信息（含私钥公钥）。"""
    db = get_db()
    try:
        row = db.execute(
            """SELECT * FROM merchant_credentials WHERE id = ?""",
            (credential_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["app_id"] = _decrypt(d["app_id"])
            d["public_key"] = _decrypt(d["public_key"])
            d["private_key"] = _decrypt(d["private_key"])
        except Exception:
            return None
        return d
    finally:
        db.close()


def toggle_merchant_credential(credential_id: int, active: bool) -> None:
    """启用/禁用商户凭证配置。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    try:
        db.execute(
            "UPDATE merchant_credentials SET active = ?, updated_at = ? WHERE id = ?",
            (1 if active else 0, now, credential_id),
        )
        db.commit()
    finally:
        db.close()


def delete_merchant_credential(credential_id: int) -> None:
    """删除商户凭证配置及其收款码图片。"""
    from pathlib import Path
    db = get_db()
    try:
        row = db.execute(
            "SELECT qrcode_path FROM merchant_credentials WHERE id = ?",
            (credential_id,),
        ).fetchone()
        if row and row["qrcode_path"]:
            p = Path(row["qrcode_path"])
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        db.execute("DELETE FROM merchant_credentials WHERE id = ?", (credential_id,))
        db.commit()
    finally:
        db.close()


def resolve_credential_for_merchant(merchant_id: int) -> dict | None:
    """
    解析商户应使用的凭证：仅使用商户自己的活跃凭证。

    Returns:
        dict: {"app_id", "public_key", "private_key", "qrcode_url", "credential_id"} 或 None
    """
    db = get_db()
    try:
        row = db.execute(
            """SELECT id FROM merchant_credentials
               WHERE merchant_id = ? AND active = 1
               ORDER BY created_at DESC LIMIT 1""",
            (merchant_id,),
        ).fetchone()
    finally:
        db.close()

    if row:
        cred = get_credential_by_id(row["id"])
        if cred:
            return {
                "app_id": cred["app_id"],
                "public_key": cred["public_key"],
                "private_key": cred["private_key"],
                "qrcode_url": cred["qrcode_url"],
                "credential_id": cred["id"],
            }

    return None
