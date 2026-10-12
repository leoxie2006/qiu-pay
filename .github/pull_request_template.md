## 变更目的
<!-- 说明修复/功能；安全修复不要附带真实订单、签名、密钥或可操作的生产攻击资料。 -->

## 范围与兼容性
- [ ] 后端 / 前端 / 配置 / 文档
- [ ] 数据库变更：无 / 有（附迁移及回滚方案）
- [ ] 无真实凭证、用户数据及测试数据库提交

## 验证证据
- [ ] `python -m pytest -q tests`
- [ ] `PYTHONPATH=. python scripts/smoke_issue14.py`
- [ ] `npm ci --prefix frontend && npm run build --prefix frontend`
- [ ] 实际容器镜像验证
- [ ] CI 全绿；关键路径已人工 review

## 发布与回滚
- 目标环境：
- 镜像 revision / digest：
- 备份路径 / SQLite integrity_check：
- 回滚命令（默认仅回退镜像，保留新订单）：
- 生产验证是否完成：
