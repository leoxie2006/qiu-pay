"""MD5 签名生成与验证模块。"""

import hashlib


def generate_sign(params: dict, key: str) -> str:
    """
    生成 MD5 签名。

    1. 过滤空值和 sign、sign_type 参数
    2. 按参数名 ASCII 码从小到大排序
    3. 拼接 URL 键值对（参数值不 URL 编码）
    4. 拼接商户密钥 KEY 后 MD5 加密

    返回小写 32 位十六进制签名字符串。
    """
    # 过滤空值和 sign/sign_type
    filtered = {
        k: v
        for k, v in params.items()
        if k not in ("sign", "sign_type") and v is not None and str(v) != ""
    }

    # 按参数名 ASCII 排序
    sorted_keys = sorted(filtered.keys())

    # 拼接 URL 键值对
    query_string = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)

    # 拼接 KEY 后 MD5
    sign_str = query_string + key
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def verify_sign(params: dict, key: str, sign: str) -> bool:
    """验证请求签名是否正确。"""
    expected = generate_sign(params, key)
    return expected == sign
