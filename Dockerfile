# ── Stage 1: 构建前端 ─────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: 运行后端 ─────────────────────────────────────
FROM python:3.12-slim

# 安装 pyzbar 依赖的系统库（zbar）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libzbar0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY app/ ./app/

# 复制文档
COPY README.md ./
COPY docs/ ./docs/

# 从前端构建阶段复制 SPA 产物
COPY --from=frontend-builder /build/app/static/spa ./app/static/spa

# 创建数据目录和上传目录
RUN mkdir -p data app/static/uploads

# 环境变量默认值
ENV DB_PATH=data/qiupay.db \
    JWT_SECRET=change-me-to-a-random-secret-key \
    ADMIN_USERNAME=admin \
    ADMIN_PASSWORD=admin123 \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000

EXPOSE ${BACKEND_PORT}

VOLUME ["/app/data"]

CMD uvicorn app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}
