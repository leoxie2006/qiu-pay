"""平台配置服务单元测试。"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 在导入 app 模块之前设置测试数据库路径
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="platform_cfg_")
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests"

import app.database as _db_mod

from app.database import init_db
from app.services.platform_config import (
    PlatformConfigError,
    get_config,
    get_credential_status,
    get_credentials,
    get_qrcode_status,
    save_credentials,
    set_config,
    upload_qrcode,
    _encrypt,
    _decrypt,
    UPLOAD_DIR,
)
from app.services.qr_parser import QRParseError, parse_qrcode


@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前重建数据库并清理上传目录。"""
    # 确保 database 模块使用正确的路径
    os.environ["DB_PATH"] = _tmp.name
    _db_mod.DB_PATH = _tmp.name

    conn = sqlite3.connect(_tmp.name)
    conn.executescript("""
        DROP TABLE IF EXISTS callback_logs;
        DROP TABLE IF EXISTS balance_logs;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS merchants;
        DROP TABLE IF EXISTS system_config;
        DROP TABLE IF EXISTS admin;
    """)
    conn.close()
    init_db()

    # 清理上传目录
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                f.unlink()

    yield

    # 测试后清理上传目录
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                f.unlink()


# ── 通用配置读写测试 ──────────────────────────────────────


class TestConfigReadWrite:
    """get_config / set_config 单元测试。"""

    def test_get_nonexistent_key_returns_none(self):
        assert get_config("nonexistent_key") is None

    def test_set_and_get_config(self):
        set_config("test_key", "test_value")
        assert get_config("test_key") == "test_value"

    def test_update_existing_config(self):
        set_config("update_key", "old_value")
        set_config("update_key", "new_value")
        assert get_config("update_key") == "new_value"

    def test_set_none_value(self):
        set_config("null_key", None)
        assert get_config("null_key") is None


# ── 加密解密测试 ──────────────────────────────────────────


class TestEncryption:
    """Fernet 加密/解密测试。"""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-secret-app-id-12345"
        encrypted = _encrypt(plaintext)
        assert encrypted != plaintext
        assert _decrypt(encrypted) == plaintext

    def test_encrypted_value_differs_from_plaintext(self):
        plaintext = "test-value"
        encrypted = _encrypt(plaintext)
        assert encrypted != plaintext

    def test_encrypt_long_key(self):
        """测试加密较长的 RSA 密钥。"""
        long_key = "MIIEvgIBADANBgkqhkiG9w0BAQEFAASC" + "A" * 1000
        encrypted = _encrypt(long_key)
        assert _decrypt(encrypted) == long_key


# ── QR 解析器测试 ─────────────────────────────────────────


class TestQRParser:
    """收款码解析器单元测试。"""

    def test_parse_valid_alipay_qrcode(self, tmp_path):
        """使用 qrcode 库生成包含支付宝链接的二维码并解析。"""
        import qrcode

        alipay_url = "https://qr.alipay.com/fkx12345abcde"
        img = qrcode.make(alipay_url)
        img_path = tmp_path / "alipay_qr.png"
        img.save(str(img_path))

        result = parse_qrcode(str(img_path))
        assert result == alipay_url

    def test_parse_non_alipay_qrcode_raises(self, tmp_path):
        """非支付宝链接的二维码应抛出 QRParseError。"""
        import qrcode

        img = qrcode.make("https://example.com/not-alipay")
        img_path = tmp_path / "other_qr.png"
        img.save(str(img_path))

        with pytest.raises(QRParseError, match="无法识别收款码"):
            parse_qrcode(str(img_path))

    def test_parse_invalid_image_raises(self, tmp_path):
        """无法打开的文件应抛出 QRParseError。"""
        bad_path = tmp_path / "not_an_image.txt"
        bad_path.write_text("this is not an image")

        with pytest.raises(QRParseError):
            parse_qrcode(str(bad_path))

    def test_parse_blank_image_raises(self, tmp_path):
        """空白图片（无二维码）应抛出 QRParseError。"""
        from PIL import Image

        blank = Image.new("RGB", (100, 100), "white")
        img_path = tmp_path / "blank.png"
        blank.save(str(img_path))

        with pytest.raises(QRParseError, match="无法识别收款码"):
            parse_qrcode(str(img_path))


# ── 收款码上传测试 ────────────────────────────────────────


class TestUploadQRCode:
    """upload_qrcode 单元测试。"""

    def _make_alipay_qr_bytes(self, url="https://qr.alipay.com/fkx00001") -> bytes:
        """生成包含支付宝链接的二维码图片字节。"""
        import io
        import qrcode

        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_upload_valid_png(self):
        content = self._make_alipay_qr_bytes()
        result = upload_qrcode(content, "test.png")
        assert "qrcode_path" in result
        assert "qrcode_url" in result
        assert "qr.alipay.com" in result["qrcode_url"]

    def test_upload_valid_jpg(self):
        content = self._make_alipay_qr_bytes()
        result = upload_qrcode(content, "test.jpg")
        assert "qrcode_url" in result

    def test_upload_saves_config(self):
        content = self._make_alipay_qr_bytes()
        upload_qrcode(content, "test.png")
        assert get_config("qrcode_url") is not None
        assert get_config("qrcode_path") is not None

    def test_reject_invalid_format(self):
        with pytest.raises(PlatformConfigError, match="仅支持 PNG 和 JPG 格式"):
            upload_qrcode(b"data", "test.gif")

    def test_reject_bmp_format(self):
        with pytest.raises(PlatformConfigError, match="仅支持 PNG 和 JPG 格式"):
            upload_qrcode(b"data", "test.bmp")

    def test_reject_oversized_file(self):
        big_content = b"x" * (5 * 1024 * 1024 + 1)
        with pytest.raises(PlatformConfigError, match="5MB"):
            upload_qrcode(big_content, "big.png")

    def test_reject_empty_file(self):
        with pytest.raises(PlatformConfigError, match="文件内容为空"):
            upload_qrcode(b"", "empty.png")

    def test_reupload_deletes_old_file(self):
        content = self._make_alipay_qr_bytes()
        result1 = upload_qrcode(content, "first.png")
        old_path = Path(result1["qrcode_path"])
        assert old_path.exists()

        content2 = self._make_alipay_qr_bytes("https://qr.alipay.com/fkx00002")
        upload_qrcode(content2, "second.png")
        assert not old_path.exists()

    def test_reupload_updates_config(self):
        url1 = "https://qr.alipay.com/fkx11111"
        url2 = "https://qr.alipay.com/fkx22222"
        content1 = self._make_alipay_qr_bytes(url1)
        content2 = self._make_alipay_qr_bytes(url2)

        upload_qrcode(content1, "first.png")
        assert get_config("qrcode_url") == url1

        upload_qrcode(content2, "second.png")
        assert get_config("qrcode_url") == url2

    def test_upload_non_alipay_qr_fails(self):
        """上传非支付宝二维码应失败。"""
        import io
        import qrcode

        img = qrcode.make("https://example.com/not-alipay")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        with pytest.raises(PlatformConfigError, match="无法识别收款码"):
            upload_qrcode(buf.getvalue(), "bad_qr.png")


# ── 凭证管理测试 ──────────────────────────────────────────


class TestCredentials:
    """save_credentials / get_credentials 单元测试。"""

    def test_save_and_get_credentials(self):
        save_credentials("app123", "pub_key_data", "priv_key_data")
        creds = get_credentials()
        assert creds is not None
        assert creds["app_id"] == "app123"
        assert creds["public_key"] == "pub_key_data"
        assert creds["private_key"] == "priv_key_data"

    def test_credentials_stored_encrypted(self):
        save_credentials("app456", "pub_key", "priv_key")
        # 直接读取数据库中的原始值，应与明文不同
        raw_app_id = get_config("alipay_app_id")
        raw_pub_key = get_config("alipay_public_key")
        raw_priv_key = get_config("alipay_private_key")
        assert raw_app_id != "app456"
        assert raw_pub_key != "pub_key"
        assert raw_priv_key != "priv_key"

    def test_save_empty_credentials_raises(self):
        with pytest.raises(PlatformConfigError, match="不能为空"):
            save_credentials("", "pub", "priv")

    def test_save_none_credentials_raises(self):
        with pytest.raises(PlatformConfigError, match="不能为空"):
            save_credentials("app", "", "priv")

    def test_get_credentials_when_not_configured(self):
        assert get_credentials() is None

    def test_save_credentials_sets_status(self):
        save_credentials("app789", "pub", "priv")
        status = get_config("credential_status")
        assert status in ("verified", "failed")

    def test_overwrite_credentials(self):
        save_credentials("old_app", "old_pub", "old_priv")
        save_credentials("new_app", "new_pub", "new_priv")
        creds = get_credentials()
        assert creds["app_id"] == "new_app"


# ── 状态查询测试 ──────────────────────────────────────────


class TestStatusQueries:
    """get_qrcode_status / get_credential_status 单元测试。"""

    def test_qrcode_status_unconfigured(self):
        status = get_qrcode_status()
        assert status["configured"] is False
        assert status["qrcode_url"] is None

    def test_qrcode_status_after_upload(self):
        import io
        import qrcode

        url = "https://qr.alipay.com/fkxstatus"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        upload_qrcode(buf.getvalue(), "status_test.png")
        status = get_qrcode_status()
        assert status["configured"] is True
        assert status["qrcode_url"] == url

    def test_credential_status_unconfigured(self):
        status = get_credential_status()
        assert status["status"] == "unconfigured"

    def test_credential_status_after_save(self):
        save_credentials("app_status", "pub", "priv")
        status = get_credential_status()
        assert status["status"] in ("verified", "failed", "configured")
