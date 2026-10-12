# Docker 跟随主机时间 / 时区

容器通常共享宿主内核（Docker Desktop 为 Linux VM）的时钟，但默认 UTC 与主机时区不同，会让 `datetime.now()`、日志与订单时间看起来相差数小时。时区调整不是修改系统时钟；不授予 SYS_TIME，也不在容器执行 date -s。

## 默认行为
根 compose、demo compose 和 README 示例都只读挂载 `${HOST_TIMEZONE_FILE:-/etc/localtime}` 到 `/etc/localtime`。
- Linux 主机通常直接使用 `/etc/localtime`。
- 不硬编码 `TZ=Asia/Shanghai`；未设置 TZ 时，Python/glibc 使用挂载的主机时区。
- 如 env 文件里已有 TZ，它会覆盖系统时区文件；要跟随主机应移除该项。
- Dockerfile 安装 tzdata，支持用户确有需求时设置显式 TZ。
- `create_host_path: false` 防止不存在的主机时区文件被创建成目录；要求现代 Compose v2。

Docker Desktop/macOS/Windows 如没有可挂载的 `/etc/localtime`，请用 HOST_TIMEZONE_FILE 指向 Docker 能访问的有效 TZif 时区文件。Windows 需准备对应 IANA 时区文件。不要把宿主的文本时区名称文件当作 /etc/localtime。

```bash
HOST_TIMEZONE_FILE=/path/to/valid/timezone-file docker compose up -d
# 查看容器偏移和 UNIX 时间；主机应启用 NTP。
docker compose exec qiu-pay python -c 'import datetime,time; print(datetime.datetime.now().astimezone().isoformat(), time.time())'
```

## 注意
- 修改主机时区后重新创建容器；文件型 bind mount可能保留旧 inode，不能保证运行中自动切换时区。
- 既有数据库使用无时区的时间字符串；不会改写历史时间或真实订单。
- 对已经按 UTC 写入历史数据的部署，切换前需要评估跨时区比较，建议维护窗口切换；这不是历史数据迁移方案。
- 本 PR 不重启生产、远端demo或现有本机demo。
