# API 接入指南

## 签名规则

所有 API 请求需要按照以下规则生成签名：

1. 将所有请求参数（排除 `sign` 和 `sign_type`，排除空值）按参数名 ASCII 码从小到大排序
2. 拼接为 `key1=value1&key2=value2` 格式
3. 在末尾直接追加商户密钥（key），**注意不是** `&key=密钥`
4. 对拼接字符串进行 MD5 加密，转为小写 32 位

**Python 示例：**

```python
import hashlib

def generate_sign(params: dict, key: str) -> str:
    filtered = {
        k: v for k, v in params.items()
        if k not in ("sign", "sign_type") and v is not None and str(v) != ""
    }
    query = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))
    return hashlib.md5((query + key).encode("utf-8")).hexdigest()
```

## 发起支付

```
POST /xpay/epay/mapi.php
Content-Type: application/x-www-form-urlencoded
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pid | int | 是 | 商户ID |
| type | string | 是 | 支付类型，固定 `alipay` |
| out_trade_no | string | 是 | 商户订单号（需唯一） |
| name | string | 是 | 商品名称 |
| money | string | 是 | 金额（元，保留两位小数） |
| notify_url | string | 是 | 异步通知地址 |
| return_url | string | 否 | 支付完成后跳转地址 |
| sign | string | 是 | MD5 签名 |
| sign_type | string | 是 | 固定 `MD5` |

**成功响应：**

```json
{
  "code": 1,
  "trade_no": "20250225143000123456789012",
  "qrcode": "https://你的域名/static/uploads/qrcode_xxx.png",
  "money": "10.00"
}
```

> 注意：返回的 `money` 可能与请求金额略有不同（尾数调整 +0.01~0.99），这是为了区分同时段的多笔同金额订单。

## 查询订单

```
GET /xpay/epay/api.php?act=order&pid={pid}&key={key}&trade_no={trade_no}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| act | string | 是 | 固定 `order` |
| pid | int | 是 | 商户ID |
| key | string | 是 | 商户密钥 |
| trade_no | string | 否 | 平台订单号（与 out_trade_no 二选一） |
| out_trade_no | string | 否 | 商户订单号（与 trade_no 二选一） |

**成功响应：**

```json
{
  "code": 1,
  "msg": "success",
  "trade_no": "20250225143000123456789012",
  "out_trade_no": "merchant_order_001",
  "type": "alipay",
  "pid": 1,
  "money": "10.00",
  "status": 1,
  "name": "测试商品"
}
```

`status` 说明：`0` = 待支付，`1` = 已支付

## 查询商户信息

```
GET /xpay/epay/api.php?act=query&pid={pid}&key={key}
```

返回商户的基本信息和统计数据。

## 异步回调通知

支付成功后，系统会向商户的 `notify_url` 发送 POST 请求：

| 参数 | 说明 |
|------|------|
| pid | 商户ID |
| trade_no | 平台订单号 |
| out_trade_no | 商户订单号 |
| type | 支付类型 |
| name | 商品名称 |
| money | 实付金额 |
| trade_status | 固定 `TRADE_SUCCESS` |
| param | 自定义参数（创建订单时传入） |
| sign | MD5 签名 |
| sign_type | 固定 `MD5` |

**商户处理要求：**

- 收到通知后需验证签名
- 验证通过后返回纯文本 `success`（不含引号、空格等）
- 未返回 `success` 时系统会按 5秒、30秒、1分钟、5分钟、30分钟 的间隔重试，最多 5 次

## 订单状态轮询

前端支付页面可通过以下接口轮询订单状态：

```
GET /v1/api/order/status/{trade_no}
```

**响应：**

```json
{
  "code": 1,
  "trade_no": "xxx",
  "status": 0,
  "status_text": "待支付"
}
```

`status`：`0` 待支付、`1` 已支付、`2` 已超时
