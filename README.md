<p align="center">
  <img src="frontend/src/assets/qiu-pay-logo.png" alt="Qiu-Pay Logo" width="180" />
</p>

<h1 align="center">Qiu-Pay</h1>

<p align="center">
无需营业执照的开源支付方案  
适用于个人开发者 / 小团队 / 独立站
</p>

<p align="center">
🚫 不需要企业资质  
🚫 不需要签约支付接口  
🚫 不需要手续费平台
</p>

<p align="center">
通过支付宝账单检测实现自动确认支付，Qiu-Pay 不是支付接口，而是支付确认方案。
</p>

[![license](https://img.shields.io/github/license/leoxie2006/qiu-pay)](https://github.com/leoxie2006/qiu-pay/blob/main/LICENSE.md)
[![release](https://img.shields.io/github/v/release/leoxie2006/qiu-pay)](https://github.com/leoxie2006/qiu-pay/releases)
[![docker](https://img.shields.io/docker/pulls/qiusheng26/qiu-pay)](https://hub.docker.com/r/qiusheng26/qiu-pay)
[![stars](https://img.shields.io/github/stars/leoxie2006/qiu-pay)](https://github.com/leoxie2006/qiu-pay)
[![issues](https://img.shields.io/github/issues/leoxie2006/qiu-pay)](https://github.com/leoxie2006/qiu-pay/issues)

## 🖼️ 界面展示

演示网站：[qiupay.cn](https://qiupay.cn)

![仪表盘](/docs/public/23.png)
![仪表盘统计](/docs/public/24.png)
![订单管理](/docs/public/25.png)

---
# Qiu-Pay
## ❓ 为什么不用传统聚合支付？

| 对比项 | 传统聚合支付 | Qiu-Pay |
|--------|-------------|---------|
| 需要营业执照 | ✅ 必须 | ❌ 不需要 |
| 需要签约支付接口 | ✅ | ❌ |
| 手续费 | 有 | 无 |
| 适合个人开发者 | ❌ | ✅ |
| 部署复杂度 | 高 | 低 |
| 成本 | 高 | 几乎 0 |

## 👨‍💻 适用场景

- 独立开发者收款
- 小程序收款
- SaaS 项目内购
- 个人网站支付
- 无法申请商户号的项目

## ✨ 功能特性

- 🔍 支付宝账单检测，自动确认支付状态
- 👥 多商户管理，独立凭证和密钥
- 💲 订单金额尾数自动调整，避免同金额冲突
- 🔔 异步回调通知，支持自动重试（最多 5 次）
- 📊 管理后台：仪表盘、商户管理、订单管理、系统设置、使用文档

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python / FastAPI / SQLite |
| 前端 | Vue 3 / Element Plus / TypeScript |
| 部署 | Docker / Docker Compose |

## ⚡ 5分钟搭建支付系统

1. Docker 启动
2. 上传收款码
3. 创建商户
4. 开始收款

## 🚀 Docker 部署（推荐）

1. 创建项目目录：

```bash
mkdir qiupay && cd qiupay
```

2. 创建 `.env` 文件：

```env
# 管理员账号（务必修改默认密码）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# JWT 密钥（务必修改为随机字符串）
JWT_SECRET=your-random-secret-key

# 后端配置
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

3. 创建 `docker-compose.yml`：

```yaml
services:
  qiupay:
    image: qiusheng26/qiu-pay:latest
    container_name: qiupay
    restart: unless-stopped
    ports:
      - "${BACKEND_PORT:-8000}:${BACKEND_PORT:-8000}"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
```

4. 启动服务：

```bash
docker compose up -d
```

5. 访问 `http://你的服务器IP:8000` 进入管理后台。

## 🔧 开发部署

1. 克隆项目：

```bash
git clone https://github.com/leoxie2006/qiu-pay.git
cd qiupay
```

2. 安装后端依赖（需要 Python 3.12+）：

```bash
pip install -r requirements.txt
```

> pyzbar 依赖系统库 zbar，Linux 下需先安装：`apt install libzbar0`

3. 复制并编辑环境变量：

```bash
cp .env.example .env
```

将 `CORS_ENABLED` 设为 `1` 以支持前后端分离开发。

4. 启动后端：

```bash
uvicorn app.main:app --reload --host localhost --port 8000
```

5. 安装并启动前端（需要 Node.js 20+）：

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，API 请求会自动代理到后端。

6. 运行测试：

```bash
pytest
```

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DB_PATH | data/qiupay.db | 数据库文件路径 |
| ADMIN_USERNAME | admin | 管理员用户名 |
| ADMIN_PASSWORD | admin123 | 管理员密码 |
| JWT_SECRET | - | JWT 签名密钥 |
| BACKEND_HOST | localhost | 后端监听地址 |
| BACKEND_PORT | 8000 | 后端监听端口 |
| CORS_ENABLED | 0 | 是否启用 CORS |
| CORS_ORIGINS | http://localhost:5173 | 允许的跨域来源 |
| FRONTEND_HOST | localhost | 前端开发服务器地址 |
| FRONTEND_PORT | 5173 | 前端开发服务器端口 |

## 📖 快速开始

1. 使用管理员账号登录后台
2. 在「商户管理 → 凭证配置」中配置支付宝凭证
3. 上传商家收款二维码
4. 创建商户，获取商户 ID（pid）和密钥（key）
5. 商户通过 API 发起支付请求

详细操作步骤请查看管理后台的「使用文档」页面。

## 📄 许可证

[MIT License](https://github.com/leoxie2006/qiu-pay/blob/main/LICENSE.md)

## ⭐ Star History

<p align="center">
  <a href="https://star-history.com/#leoxie2006/qiu-pay&Date">
    <img src="https://api.star-history.com/svg?repos=leoxie2006/qiu-pay&type=Date" alt="Star History Chart" />
  </a>
</p>

## ☕ 赞赏支持

如果觉得项目对你有帮助，欢迎赞赏支持

<div align="center">
  <img src="https://raw.githubusercontent.com/leoxie2006/qiu-pay/main/docs/public/0.jpg" width="300" />
</div>

## ⚠️ 合规声明

本项目仅用于个人技术研究或收款确认场景，不提供资金清算、代收代付等支付服务。

用户需遵守当地法律法规及支付宝相关协议，因不当使用产生的风险由使用者自行承担。
