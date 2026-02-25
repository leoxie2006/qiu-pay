"""支付宝 API 客户端单元测试。"""

import base64
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from app.services.alipay_client import AlipayClient, AlipayClientError


# ── 测试用 RSA 密钥对 ────────────────────────────────────

def _generate_test_keypair():
    """生成测试用 RSA 2048 密钥对。"""
    key = RSA.generate(2048)
    private_pem = key.export_key("PEM").decode("utf-8")
    public_pem = key.publickey().export_key("PEM").decode("utf-8")
    return private_pem, public_pem


def _extract_bare_key(pem: str) -> str:
    """从 PEM 格式中提取裸 Base64 内容（去掉 header/footer 和换行）。"""
    lines = pem.strip().splitlines()
    return "".join(lines[1:-1])


PRIVATE_PEM, PUBLIC_PEM = _generate_test_keypair()
PRIVATE_BARE = _extract_bare_key(PRIVATE_PEM)
PUBLIC_BARE = _extract_bare_key(PUBLIC_PEM)
TEST_APP_ID = "2021000000000001"


# ── 初始化测试 ────────────────────────────────────────────


class TestAlipayClientInit:
    """AlipayClient 初始化测试。"""

    def test_init_with_pem_keys(self):
        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        assert client.app_id == TEST_APP_ID

    def test_init_with_bare_keys(self):
        client = AlipayClient(TEST_APP_ID, PRIVATE_BARE, PUBLIC_BARE)
        assert client.app_id == TEST_APP_ID

    def test_invalid_private_key_raises(self):
        with pytest.raises(AlipayClientError, match="无法加载应用私钥"):
            AlipayClient(TEST_APP_ID, "invalid-key", PUBLIC_PEM)

    def test_invalid_public_key_raises(self):
        with pytest.raises(AlipayClientError, match="无法加载支付宝公钥"):
            AlipayClient(TEST_APP_ID, PRIVATE_PEM, "invalid-key")


# ── 签名测试 ──────────────────────────────────────────────


class TestAlipayClientSign:
    """RSA2 签名测试。"""

    def test_sign_produces_valid_base64(self):
        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        params = {"app_id": TEST_APP_ID, "method": "test", "charset": "utf-8"}
        sig = client._sign(params)
        # 应为有效 Base64
        decoded = base64.b64decode(sig)
        assert len(decoded) > 0

    def test_sign_filters_empty_and_sign(self):
        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        params_base = {"a": "1", "b": "2"}
        params_extra = {"a": "1", "b": "2", "c": "", "sign": "old", "d": None}
        assert client._sign(params_base) == client._sign(params_extra)

    def test_sign_is_deterministic_for_same_params(self):
        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        params = {"x": "hello", "y": "world"}
        assert client._sign(params) == client._sign(params)


# ── 余额查询测试 ──────────────────────────────────────────


def _make_success_response():
    """构造支付宝余额查询成功响应。"""
    return {
        "alipay_data_bill_balance_query_response": {
            "code": "10000",
            "msg": "Success",
            "total_amount": "10000.50",
            "available_amount": "8000.25",
            "freeze_amount": "2000.25",
        },
        "sign": "mock_sign",
    }


def _make_error_response(code="40004", sub_msg="Insufficient Permissions"):
    """构造支付宝余额查询错误响应。"""
    return {
        "alipay_data_bill_balance_query_response": {
            "code": code,
            "msg": "Business Failed",
            "sub_msg": sub_msg,
        },
        "sign": "mock_sign",
    }


class TestQueryBalance:
    """query_balance 方法测试。"""

    @patch("app.services.alipay_client.httpx.Client")
    def test_success_returns_decimal_amounts(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_success_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        result = client.query_balance()

        assert result["total_amount"] == Decimal("10000.50")
        assert result["available_amount"] == Decimal("8000.25")
        assert result["freeze_amount"] == Decimal("2000.25")

    @patch("app.services.alipay_client.httpx.Client")
    def test_business_error_raises(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_error_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        with pytest.raises(AlipayClientError, match="Insufficient Permissions"):
            client.query_balance()

    @patch("app.services.alipay_client.httpx.Client")
    def test_http_error_raises(self, mock_client_cls):
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        with pytest.raises(AlipayClientError, match="请求支付宝接口失败"):
            client.query_balance()

    @patch("app.services.alipay_client.httpx.Client")
    def test_invalid_json_raises(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        with pytest.raises(AlipayClientError, match="解析支付宝响应失败"):
            client.query_balance()

    @patch("app.services.alipay_client.httpx.Client")
    def test_missing_response_key_raises(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "data"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        with pytest.raises(AlipayClientError, match="支付宝响应缺少"):
            client.query_balance()

    @patch("app.services.alipay_client.httpx.Client")
    def test_request_sends_correct_params(self, mock_client_cls):
        """验证请求包含正确的系统参数。"""
        mock_response = MagicMock()
        mock_response.json.return_value = _make_success_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        client.query_balance()

        call_args = mock_client.post.call_args
        sent_data = call_args.kwargs.get("data") or call_args[1].get("data")
        assert sent_data["app_id"] == TEST_APP_ID
        assert sent_data["method"] == "alipay.data.bill.balance.query"
        assert sent_data["charset"] == "utf-8"
        assert sent_data["sign_type"] == "RSA2"
        assert sent_data["version"] == "1.0"
        assert "sign" in sent_data
        assert "timestamp" in sent_data


# ── 连通性验证测试 ────────────────────────────────────────


class TestVerifyConnectivity:
    """verify_connectivity 方法测试。"""

    @patch("app.services.alipay_client.httpx.Client")
    def test_returns_true_on_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_success_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        assert client.verify_connectivity() is True

    @patch("app.services.alipay_client.httpx.Client")
    def test_returns_false_on_error(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_error_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        assert client.verify_connectivity() is False

    @patch("app.services.alipay_client.httpx.Client")
    def test_returns_false_on_connection_error(self, mock_client_cls):
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("timeout")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = AlipayClient(TEST_APP_ID, PRIVATE_PEM, PUBLIC_PEM)
        assert client.verify_connectivity() is False
