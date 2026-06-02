"""收款码解析器：解析收款码图片，提取支付宝收款链接。"""

import os
import re
from pathlib import Path

from PIL import Image


class QRParseError(Exception):
    """收款码解析失败异常。"""
    pass


# 支付宝收款码 URL 模式
_ALIPAY_PATTERNS = [
    re.compile(r"https?://qr\.alipay\.com/", re.IGNORECASE),
    re.compile(r"alipays?://", re.IGNORECASE),
]


def parse_qrcode(image_path: str) -> str:
    """
    解析收款码图片，提取支付宝收款链接。

    使用 pyzbar 解码二维码，检查是否包含支付宝收款链接。

    Args:
        image_path: 图片文件路径。

    Returns:
        支付宝收款链接字符串。

    Raises:
        QRParseError: 图片无法解析或不包含有效的支付宝收款码。
    """
    try:
        img = Image.open(image_path)
    except Exception as e:
        raise QRParseError("无法打开图片文件") from e

    decode = _load_decoder()

    decoded_objects = decode(img)

    if not decoded_objects:
        raise QRParseError("无法识别收款码，请上传清晰的支付宝收款码图片")

    # 遍历所有解码结果，查找支付宝链接
    for obj in decoded_objects:
        data = obj.data.decode("utf-8", errors="ignore")
        for pattern in _ALIPAY_PATTERNS:
            if pattern.search(data):
                return data

    raise QRParseError("无法识别收款码，请上传清晰的支付宝收款码图片")


def _load_decoder():
    """Load pyzbar after adding common Homebrew zbar library paths."""
    _ensure_zbar_library_path()
    try:
        from pyzbar.pyzbar import decode
    except ImportError as e:
        raise QRParseError("二维码解析组件不可用，请安装 zbar 运行库") from e
    return decode


def _ensure_zbar_library_path() -> None:
    candidates = [
        Path("/opt/homebrew/opt/zbar/lib"),
        Path("/usr/local/opt/zbar/lib"),
    ]
    existing = [str(path) for path in candidates if path.exists()]
    if not existing:
        return

    current = os.environ.get("DYLD_LIBRARY_PATH", "")
    current_parts = [part for part in current.split(":") if part]
    for path in existing:
        if path not in current_parts:
            current_parts.insert(0, path)
    os.environ["DYLD_LIBRARY_PATH"] = ":".join(current_parts)
