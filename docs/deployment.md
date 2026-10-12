# 版本核查、生产发布及 demo CI/CD

## 当前证据边界
仓库原 compose 使用 Docker Hub `qiusheng26/qiu-pay:latest`，映射后端端口并挂载 `./data`。
这只是仓库部署模板，不是生产服务器的实况。生产 host、目录、运行镜像 digest、反向代理、备份和权限需要先核查。
8001 本次检查没有监听；不把历史 PoC 当作当前生产验证。

## 生产发布前核查（在已确认的部署目录执行）
```bash
docker compose ps
docker compose images
# CID 取自实际服务；不猜服务名、不打印 env 中的凭证。
docker inspect --format '{{.Image}} {{json .Mounts}}' "$CID"
docker image inspect --format '{{.Id}} {{json .RepoDigests}} {{json .Config.Labels}}' "$IMAGE"
```
核对 commit 标签和实际源码哈希；记录 compose、持久化 data/uploads 路径、DB_PATH、代理入口和旧镜像 ID。

### 发布及回滚原则
1. 先测试候选不可变镜像，不挂载生产 data/env（下方 smoke 命令）。
2. 使用 SQLite backup API 做一致性备份并 `PRAGMA integrity_check`，不是直接拷贝运行中的 `.db`。
   以 URI `mode=ro` 打开源库；WAL 模式可能需要创建 SHM/WAL sidecar，因此源目录需可写。
   备份目标转换为 `journal_mode=DELETE`，确保是无 sidecar 依赖的独立文件。
   不用 `immutable=1` 绕过锁和 WAL，不将只读挂载失败误判为备份成功。
3. 备份 compose、env（0600）、上传文件和旧镜像 ID；备份存放在部署目录之外的受控路径。
4. 本补丁无 schema 迁移；替换镜像，保留数据卷，等待健康检查并核对运行 digest。
5. 默认故障回滚只切回旧镜像，**保留当前数据库**，避免覆盖发布后新增订单。
6. 仅在明确维护窗口与停止写入后人工恢复数据备份；不得自动覆盖生产数据。
7. 生产测试需要独立测试商户/订单，无真实通知地址、收款凭证和资金行为。
   超时状态用测试订单，已支付状态仅模拟测试订单，不改真实订单。
8. `smoke_issue14.py` 验证运行镜像的临时数据库，**不验证生产 HTTP 或生产订单库**。
   生产 HTTP 验证需先确认隔离测试入口/商户流程，不能以这个 smoke 替代。

```bash
docker run --rm --network none -v "$PWD/scripts/smoke_issue14.py:/smoke.py:ro" \
  -e PYTHONPATH=/app "$IMAGE" python /smoke.py
```
输出应为 state=0/2 签名 False、state=1 True，以及 external_callbacks=0。

## GitHub CI/CD
`.github/workflows/ci-demo.yml`：PR/main 测试、前端构建、实际镜像三状态验证；main 才发布 GHCR。
部署 job 仅当仓库变量 `DEMO_DEPLOY_ENABLED=true` 时运行，使用 `demo` Environment。
必须先配置，缺少服务器和 Secrets 时不会凭空部署：

| 类型 | 名称 | 含义 |
|---|---|---|
| Repository variable | DEMO_DEPLOY_ENABLED | 最后设为 true；缺省不开启 |
| demo Environment variable | DEMO_HOST | 独立 demo SSH 域名/IP |
| demo Environment variable | DEMO_USER | 部署用户，有 Docker 权限 |
| demo Environment variable | DEMO_DIR | 绝对路径，如 /opt/qiu-pay-demo |
| demo Environment secret | DEMO_SSH_KEY | 专用 SSH 私钥，不复用生产密钥 |
| demo Environment secret | DEMO_KNOWN_HOSTS | 带外确认的 SSH 主机公钥记录，不关闭主机校验 |

服务器需 Linux x86_64、bash、flock、Docker 和 Compose v2（支持 --wait）。
GHCR 包若为 private，服务器需要预先 `docker login ghcr.io` 的 read:packages 凭证；不要上传个人 token 到仓库。
创建包后核实可见性；公开仓库并不保证包默认公开。

### 首次准备 demo（仅专用 demo 目录）
```bash
mkdir -p /opt/qiu-pay-demo
cd /opt/qiu-pay-demo
touch .qiu-pay-demo
umask 077
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('.env.demo')
if path.exists():
    raise SystemExit('Existing configuration preserved')
path.write_text('ADMIN_USERNAME=demo_admin\nADMIN_PASSWORD=' + secrets.token_urlsafe(32)
                + '\nJWT_SECRET=' + secrets.token_hex(32) + '\nCORS_ENABLED=0\n')
path.chmod(0o600)
PY
```
随机管理员密码保存在服务器配置文件中，勿粘贴到 PR/log。端口默认 127.0.0.1:18001；反代需独立 demo 域名和认证访问。
此 demo 设置 TESTING=1，关闭后台支付/超时/通知扫描，不应配置真实收款凭证或接收真实支付。

### 部署及回滚
```bash
bash scripts/deploy/demo.sh /opt/qiu-pay-demo ghcr.io/OWNER/qiu-pay@sha256:DIGEST
bash scripts/deploy/rollback-demo.sh /opt/qiu-pay-demo /opt/qiu-pay-demo/releases/RELEASE
```
脚本锁定部署、拒绝无 marker 的目录、先隔离验证、在线备份 SQLite、保存上传文件和旧镜像、按 digest 部署。
健康检查或镜像验证失败自动回退；首次发布失败下线 demo。没有旧镜像时不伪造回滚成功。
备份包含敏感配置/数据，需要权限限制和外部备份/保留策略；不要提交到 Git。
