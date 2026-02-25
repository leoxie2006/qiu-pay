"""
支付宝 API 客户端：使用 RSA2 签名调用支付宝开放平台接口。

主要功能：
- 调用 alipay.data.bill.balance.query 查询运营方支付宝账户余额
- 连通性验证（用于凭证配置时测试）
"""

import base64
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

import httpx
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

logger = logging.getLogger(__name__)

ALIPAY_GATEWAY = "https://openapi.alipay.com/gateway.do"


class AlipayClientError(Exception):
    """支付宝客户端异常。"""
    pass


class AlipayClient:
    """支付宝开放平台 API 客户端，使用 RSA2 (SHA256withRSA) 签名。"""

    def __init__(self, app_id: str, private_key: str, public_key: str):
        """
        使用运营方的支付宝凭证初始化客户端。

        Args:
            app_id: 支付宝应用 ID。
            private_key: 应用私钥（PEM 格式或裸 Base64）。
            public_key: 支付宝公钥（PEM 格式或裸 Base64）。
        """
        self.app_id = app_id
        self._private_key = self._load_private_key(private_key)
        self._public_key = self._load_public_key(public_key)

    @staticmethod
    def _load_private_key(key_str: str) -> RSA.RsaKey:
        """加载 RSA 私钥，支持 PEM 格式和裸 Base64。"""
        key_str = key_str.strip()
        if not key_str.startswith("-----"):
            key_str = (
                "-----BEGIN PRIVATE KEY-----\n"
                + key_str
                + "\n-----END PRIVATE KEY-----"
            )
        try:
            return RSA.import_key(key_str)
        except (ValueError, IndexError) as e:
            raise AlipayClientError(f"无法加载应用私钥: {e}")

    @staticmethod
    def _load_public_key(key_str: str) -> RSA.RsaKey:
        """加载 RSA 公钥，支持 PEM 格式和裸 Base64。"""
        key_str = key_str.strip()
        if not key_str.startswith("-----"):
            key_str = (
                "-----BEGIN PUBLIC KEY-----\n"
                + key_str
                + "\n-----END PUBLIC KEY-----"
            )
        try:
            return RSA.import_key(key_str)
        except (ValueError, IndexError) as e:
            raise AlipayClientError(f"无法加载支付宝公钥: {e}")

    def _sign(self, params: dict) -> str:
        """
        对参数进行 RSA2 (SHA256withRSA) 签名。

        1. 过滤空值和 sign 参数
        2. 按参数名 ASCII 排序
        3. 拼接 URL 键值对（值不 URL 编码）
        4. 使用应用私钥进行 SHA256withRSA 签名
        5. 返回 Base64 编码的签名字符串
        """
        # 过滤空值和 sign
        filtered = {
            k: v for k, v in params.items()
            if v is not None and v != "" and k != "sign"
        }
        # 按 ASCII 排序拼接
        sorted_keys = sorted(filtered.keys())
        unsigned_str = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)

        # SHA256withRSA 签名
        h = SHA256.new(unsigned_str.encode("utf-8"))
        signature = pkcs1_15.new(self._private_key).sign(h)
        return base64.b64encode(signature).decode("utf-8")

    def _verify(self, params: dict, sign: str) -> bool:
        """
        使用支付宝公钥验证响应签名。

        Args:
            params: 待验签的参数字典或 JSON 字符串内容。
            sign: Base64 编码的签名。

        Returns:
            True 验签通过，False 验签失败。
        """
        if isinstance(params, dict):
            content = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
        else:
            content = params

        h = SHA256.new(content.encode("utf-8"))
        try:
            pkcs1_15.new(self._public_key).verify(h, base64.b64decode(sign))
            return True
        except (ValueError, TypeError):
            return False

    def _build_common_params(self, method: str) -> dict:
        """构建支付宝 API 公共请求参数。"""
        return {
            "app_id": self.app_id,
            "method": method,
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
        }

    def query_balance(self) -> dict:
        """
        调用 alipay.data.bill.balance.query 接口查询余额。

        Returns:
            dict: {
                "total_amount": Decimal,
                "available_amount": Decimal,
                "freeze_amount": Decimal,
            }

        Raises:
            AlipayClientError: 接口调用失败或响应异常。
        """
        method = "alipay.data.bill.balance.query"
        params = self._build_common_params(method)
        # 该接口无业务参数，biz_content 为空 JSON
        params["biz_content"] = "{}"
        params["sign"] = self._sign(params)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    ALIPAY_GATEWAY,
                    data=params,
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise AlipayClientError(f"请求支付宝接口失败: {e}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise AlipayClientError(f"解析支付宝响应失败: {e}")

        # 支付宝响应格式：{"alipay_data_bill_balance_query_response": {...}, "sign": "..."}
        response_key = method.replace(".", "_") + "_response"
        result = data.get(response_key)
        if not result:
            raise AlipayClientError(f"支付宝响应缺少 {response_key} 字段")

        # 检查业务错误
        code = result.get("code")
        if code != "10000":
            sub_msg = result.get("sub_msg", result.get("msg", "未知错误"))
            raise AlipayClientError(f"支付宝接口返回错误: [{code}] {sub_msg}")

        # 解析金额
        try:
            return {
                "total_amount": Decimal(result.get("total_amount", "0")),
                "available_amount": Decimal(result.get("available_amount", "0")),
                "freeze_amount": Decimal(result.get("freeze_amount", "0")),
            }
        except (InvalidOperation, TypeError) as e:
            raise AlipayClientError(f"解析余额金额失败: {e}")

    def verify_connectivity(self) -> bool:
        """
        连通性验证：调用余额查询接口测试凭证是否有效。

        Returns:
            True 连通成功，False 连通失败。
        """
        try:
            self.query_balance()
            return True
        except AlipayClientError as e:
            logger.warning("支付宝连通性验证失败: %s", e)
            return False
