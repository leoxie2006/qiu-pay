# Qiu-Pay

Qiu-Pay 是一个支付宝账单检测平台，支持商户管理、订单管理、异步回调通知等功能。

## 功能特性

- 支付宝账单检测，自动确认支付状态
- 多商户管理，独立凭证和密钥
- 订单金额尾数自动调整，避免同金额冲突
- 异步回调通知，支持自动重试（最多 5 次）
- 管理后台：仪表盘、商户管理、订单管理、系统设置、使用文档

## 部署安装

### Docker 部署（推荐）

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
    image: qiusheng26/qiupay:latest
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

### 开发部署

1. 克隆项目：

```bash
git clone https://github.com/qiusheng26/qiupay.git
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

### 构建 Docker 镜像

```bash
docker build -t qiusheng26/qiupay:latest .
docker push qiusheng26/qiupay:latest
```

### 环境变量说明

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

## 快速开始

1. 使用管理员账号登录后台
2. 在「系统设置」或「商户管理 → 凭证配置」中配置支付宝凭证
3. 上传商家收款二维码
4. 创建商户，获取商户 ID（pid）和密钥（key）
5. 商户通过 API 发起支付请求

详细操作步骤请查看管理后台的「使用文档」页面。

## 技术栈

- 后端：Python / FastAPI / SQLite
- 前端：Vue 3 / Element Plus / TypeScript
- 部署：Docker

## 许可证

MIT
