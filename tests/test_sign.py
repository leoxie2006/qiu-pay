"""MD5 签名模块单元测试。"""

import re

from app.services.sign import generate_sign, verify_sign


class TestGenerateSign:
    """generate_sign 单元测试。"""

    def test_basic_sign(self):
        params = {"a": "1", "b": "2", "c": "3"}
        key = "mykey"
        sign = generate_sign(params, key)
        # 应为小写 32 位十六进制
        assert re.fullmatch(r"[0-9a-f]{32}", sign)

    def test_ascii_sort_order(self):
        """参数按 ASCII 排序，不同顺序输入应产生相同签名。"""
        key = "testkey"
        params_a = {"z": "1", "a": "2", "m": "3"}
        params_b = {"a": "2", "m": "3", "z": "1"}
        assert generate_sign(params_a, key) == generate_sign(params_b, key)

    def test_filters_empty_values(self):
        """空值参数不参与签名。"""
        key = "k"
        base = {"a": "1", "b": "2"}
        with_empty = {"a": "1", "b": "2", "c": "", "d": None}
        assert generate_sign(base, key) == generate_sign(with_empty, key)

    def test_filters_sign_and_sign_type(self):
        """sign 和 sign_type 参数不参与签名。"""
        key = "k"
        base = {"a": "1", "b": "2"}
        with_sign = {"a": "1", "b": "2", "sign": "abc", "sign_type": "MD5"}
        assert generate_sign(base, key) == generate_sign(with_sign, key)

    def test_no_url_encoding(self):
        """参数值不进行 URL 编码。"""
        key = "k"
        params = {"url": "https://example.com?foo=bar&baz=1"}
        sign = generate_sign(params, key)
        assert re.fullmatch(r"[0-9a-f]{32}", sign)

    def test_known_value(self):
        """已知输入验证签名正确性。"""
        # a=1&b=2&c=3 + key => MD5
        import hashlib
        params = {"a": "1", "b": "2", "c": "3"}
        key = "KEY"
        expected = hashlib.md5("a=1&b=2&c=3KEY".encode("utf-8")).hexdigest()
        assert generate_sign(params, key) == expected


class TestVerifySign:
    """verify_sign 单元测试。"""

    def test_valid_sign(self):
        params = {"pid": "1001", "money": "10.00", "name": "test"}
        key = "secret"
        sign = generate_sign(params, key)
        assert verify_sign(params, key, sign) is True

    def test_invalid_sign(self):
        params = {"pid": "1001", "money": "10.00"}
        key = "secret"
        assert verify_sign(params, key, "0" * 32) is False

    def test_wrong_key_fails(self):
        params = {"a": "1"}
        sign = generate_sign(params, "correct_key")
        assert verify_sign(params, "wrong_key", sign) is False

    def test_tampered_params_fail(self):
        params = {"a": "1", "b": "2"}
        key = "k"
        sign = generate_sign(params, key)
        tampered = {"a": "1", "b": "3"}
        assert verify_sign(tampered, key, sign) is False
