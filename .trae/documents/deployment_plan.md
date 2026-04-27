# Rhizome Thinking 部署方案

## 目标

在新 Linux 服务器上通过一条命令完成部署。部署后可通过局域网 HTTP 访问 PWA 界面，可通过 SSH 用 CLI 管理。

## 前提

- 目标服务器: Linux x86_64 或 arm64，已安装 Docker (含 Docker Compose v2 插件，即 `docker compose` 子命令可用)
- 部署机可 SSH 到目标服务器
- 项目源码已存在于目标服务器的 `/opt/rhizome-thinking` 目录
- 用户已获取 MiniMax API Key 和 SiliconFlow API Key

## 架构

单容器运行全部服务:

- 容器名: `rhizome-thinking`
- 基础镜像: `python:3.11-slim`
- 进程: `uvicorn rhizome.api.main:app --host 0.0.0.0 --port 8000`
- ChromaDB 使用嵌入式 PersistentClient，运行在同一进程内，数据写入 `/app/storage/chroma/`
- 所有用户数据持久化到宿主机 `./storage/` 目录，通过 Docker volume 挂载
- 配置文件 `.env` 以只读方式挂载到容器内 `/app/.env`

## 需要创建的文件

以下文件目前不存在，需要按此规格逐一创建。

### 文件 1: `Dockerfile`

项目根目录，与 `pyproject.toml` 同级。

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir ".[stage2]"

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

RUN mkdir -p /app/storage && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

ENV STORAGE_DIR=/app/storage
ENV CHROMA_PERSIST_DIR=/app/storage/chroma

CMD ["uvicorn", "rhizome.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建依赖 `build-essential` 是 chromadb 编译所需。`hatchling` 是 pyproject.toml 的构建后端，slim 镜像不含此包，必须在 `pip install .[stage2]` 之前单独安装。健康检查用 Python 标准库而不用 curl，避免额外系统依赖。

### 文件 2: `docker-compose.yml`

项目根目录，与 `pyproject.toml` 同级。

```yaml
services:
  rhizome:
    build: .
    container_name: rhizome-thinking
    ports:
      - "${PORT:-8000}:8000"
    volumes:
      - ./storage:/app/storage
      - ./.env:/app/.env:ro
    environment:
      - STORAGE_DIR=/app/storage
      - CHROMA_PERSIST_DIR=/app/storage/chroma
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health')
      interval: 30s
      timeout: 10s
      start_period: 15s
      retries: 3
```

`restart: unless-stopped` 由 Docker daemon 处理容器异常退出后的自动重启。宿主机 `./storage/` 目录挂载到容器内 `/app/storage/`，数据与容器生命周期分离。`${PORT:-8000}` 允许通过环境变量改变宿主机映射端口。

### 文件 3: `.dockerignore`

项目根目录，与 `pyproject.toml` 同级。

```
.git
.gitignore
venv
.venv
storage
.env
.env.*
__pycache__
*.pyc
.eggs
*.egg-info
dist
build
.pytest_cache
.mypy_cache
.ruff_cache
design-preview
.trae
```

### 文件 4: `scripts/rhizome.service`

Systemd 服务定义文件。

```ini
[Unit]
Description=Rhizome Thinking Knowledge Base
After=network-online.target docker.service
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/rhizome-thinking
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

`Type=oneshot` 加 `RemainAfterExit=yes` 是因为 `docker compose up -d` 命令本身在启动容器后会立即退出（容器继续在后台运行）。如果用 `Type=simple`，systemd 会误以为进程已退出并触发失败处理。

`ExecStart` 路径 `/usr/bin/docker compose` 对应 Docker Compose v2 插件。创建此文件时，先执行 `which docker` 确认 docker 的实际路径，如果系统上 docker 在 `/usr/local/bin/docker`，则将 ExecStart 等行中的 `/usr/bin/docker` 替换为该路径。

### 文件 5: `scripts/install-service.sh`

安装 systemd 服务的脚本。

```bash
#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/rhizome.service"

sed "s|/opt/rhizome-thinking|${PROJECT_DIR}|g" \
    "$PROJECT_DIR/scripts/rhizome.service" | sudo tee "$SERVICE_FILE"

sudo systemctl daemon-reload
sudo systemctl enable rhizome
sudo systemctl start rhizome

echo "done: systemctl status rhizome"
```

此脚本将服务模板中的 `/opt/rhizome-thinking` 替换为实际项目路径，然后安装并启用服务。

### 文件 6: `scripts/deploy.sh`

Linux 部署辅助脚本。不包含 Docker 安装逻辑（Docker 应在服务器初始化时已安装）。

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# 1. 生成 .env
if [ ! -f .env ]; then
    echo "生成 .env 配置文件..."

    read -p "MiniMax API Key: " MINIMAX_KEY
    read -p "SiliconFlow API Key: " SILICONFLOW_KEY

    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > .env << EOF
MINIMAX_API_KEY=${MINIMAX_KEY}
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
SILICONFLOW_API_KEY=${SILICONFLOW_KEY}
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
USE_MOCK_EMBEDDING=false
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=${SECRET_KEY}
STORAGE_DIR=./storage
CHROMA_PERSIST_DIR=./storage/chroma
EOF

    chmod 600 .env
    echo ".env 已创建"
else
    echo ".env 已存在，跳过"
fi

# 2. 创建数据目录
mkdir -p storage/nodes storage/metadata storage/chroma storage/themes storage/backups

# 3. 构建并启动
docker compose up -d --build

# 4. 等待健康检查通过
echo "等待服务就绪..."
for i in $(seq 1 30); do
    if curl -s http://localhost:${PORT:-8000}/health > /dev/null 2>&1; then
        echo "服务已就绪"
        break
    fi
    sleep 2
done

# 5. 显示访问信息
SERVER_IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
echo ""
echo "部署完成"
echo "访问地址: http://${SERVER_IP}:${PORT:-8000}"
echo "API文档:  http://${SERVER_IP}:${PORT:-8000}/docs"
```

环境变量命名使用全大写加下划线，因为 pydantic-settings 默认将类字段名 `minimax_api_key` 映射到环境变量 `MINIMAX_API_KEY`。`SECRET_KEY` 由脚本随机生成并固定写入 `.env`，如果每次容器重启都重新生成，将来引入 session 或 JWT 后所有已签发的 token 会全部失效。

### 文件 7: `install.sh`

项目根目录的一键安装入口脚本。假定 Docker 已安装，项目源码已放在 `/opt/rhizome-thinking`。

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/rhizome-thinking"
cd "$PROJECT_DIR"

bash scripts/deploy.sh
bash scripts/install-service.sh

echo "=== Rhizome Thinking 已部署 ==="
echo "docker compose logs -f   # 查看日志"
echo "docker compose restart   # 重启服务"
echo "docker compose down      # 停止服务"
echo "docker compose up -d     # 启动服务"
```

## CLI server 命令组

在 `src/rhizome/cli.py` 中新增 `server` 命令组，使用 Click 的 `@click.group()` 定义。以下为每个子命令的规格描述。

所有命令在调用前需先 `cd /opt/rhizome-thinking`（或读取环境变量 `RHIZOME_PROJECT_DIR` 获取项目路径）。调用 `docker compose` 命令时需指定项目目录。

### `rhz server start`

```
执行: docker compose -f /opt/rhizome-thinking/docker-compose.yml up -d
输出: "服务已启动"
```

无额外参数。不考虑 `--port` 参数（端口在 docker-compose.yml 中通过 PORT 环境变量控制）。

### `rhz server stop`

```
执行: docker compose -f /opt/rhizome-thinking/docker-compose.yml down
输出: "服务已停止"
```

### `rhz server restart`

```
执行: docker compose -f /opt/rhizome-thinking/docker-compose.yml restart
输出: "服务已重启"
```

### `rhz server status`

```
步骤1: 执行 docker compose -f /opt/rhizome-thinking/docker-compose.yml ps
步骤2: HTTP GET http://localhost:8000/health
输出: 容器运行状态 + 健康检查结果 + 版本号
```

如果容器未运行，只输出"服务未运行"。如果容器运行但 /health 不可达，输出"服务启动中或异常"。

### `rhz server logs`

```
参数:
  --follow, -f: bool, 持续跟踪输出 (传给 docker compose logs -f)
  --lines, -n: int, 显示最近N行, 默认100

执行: docker compose -f /opt/rhizome-thinking/docker-compose.yml logs [--follow] [--tail N]
```

### `rhz server info`

```
步骤1: ip route get 1 | awk '{print $7}' | head -1  # 获取本机IP
步骤2: 从 docker-compose.yml 读取 ports 配置获取端口
输出:
  访问地址: http://{IP}:{PORT}
  API文档:  http://{IP}:{PORT}/docs
```

### `rhz server config`

```
步骤1: 读取 /opt/rhizome-thinking/.env 文件
步骤2: 输出所有配置项，隐藏 API Key 值（只显示前4位和后4位，中间用****替代）
步骤3: 输出容器镜像版本 (docker compose images)
```

### `rhz install`

```
执行: bash /opt/rhizome-thinking/scripts/install-service.sh
```

### `rhz uninstall`

```
执行:
  sudo systemctl stop rhizome
  sudo systemctl disable rhizome
  sudo rm /etc/systemd/system/rhizome.service
  sudo systemctl daemon-reload
输出: "Systemd 服务已卸载"
```

## 数据持久化

以下宿主机目录通过 docker-compose.yml 的 volumes 挂载到容器内:

| 宿主机路径 | 容器内路径 | 内容 |
| --- | --- | --- |
| `./storage/nodes/` | `/app/storage/nodes/` | 节点 Markdown 文件 |
| `./storage/metadata/` | `/app/storage/metadata/` | 索引 JSON 文件 |
| `./storage/chroma/` | `/app/storage/chroma/` | ChromaDB 嵌入式数据 |
| `./storage/themes/` | `/app/storage/themes/` | 主题数据 |
| `./storage/backups/` | `/app/storage/backups/` | 备份 ZIP 归档 |
| `./.env` | `/app/.env` (只读) | API Key 等配置 |

路径 `./` 相对于 `/opt/rhizome-thinking`（docker-compose.yml 所在目录）。

备份整个知识库的命令: `cp -r /opt/rhizome-thinking/storage /backup/location/`

## 更新流程

```
cd /opt/rhizome-thinking
git pull
docker compose up -d --build
```

`docker compose down` 停止旧容器，`up -d --build` 重建镜像并启动新容器。`storage/` 目录在宿主机上不受容器重建影响。

## 环境变量参考

`.env` 文件中所有变量名使用全大写加下划线（pydantic-settings 的默认映射规则）:

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `MINIMAX_API_KEY` | 是 | MiniMax API 密钥 |
| `MINIMAX_BASE_URL` | 否 | MiniMax API 地址，默认 `https://api.minimaxi.com/v1` |
| `MINIMAX_MODEL` | 否 | 使用的模型，默认 `minimax-text-01` |
| `SILICONFLOW_API_KEY` | 是 | SiliconFlow API 密钥 |
| `SILICONFLOW_BASE_URL` | 否 | SiliconFlow API 地址，默认 `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_EMBEDDING_MODEL` | 否 | Embedding 模型，默认 `BAAI/bge-large-zh-v1.5` |
| `USE_MOCK_EMBEDDING` | 否 | 设为 `true` 使用模拟 embedding，用于离线测试 |
| `ENVIRONMENT` | 否 | `development` / `production` / `testing` |
| `DEBUG` | 否 | 设为 `true` 启用调试模式 |
| `SECRET_KEY` | 否 | 应用密钥，未设置时每次启动随机生成 |
| `STORAGE_DIR` | 否 | 数据存储根目录，默认 `./storage` |
| `CHROMA_PERSIST_DIR` | 否 | ChromaDB 持久化目录，默认 `./storage/chroma` |

Docker 容器内 `STORAGE_DIR` 和 `CHROMA_PERSIST_DIR` 通过 docker-compose.yml 的 environment 注入，不依赖 .env 文件中的值。

## 容器内端口

容器内部固定监听 `8000` 端口。`docker-compose.yml` 中 `${PORT:-8000}:8000` 只改变宿主机映射端口。如果通过环境变量 `PORT=8080` 启动，则宿主机 8080 映射到容器内 8000，局域网访问地址为 `http://服务器IP:8080`。

## 健康检查端点

`GET /health` 返回:

```json
{"status": "healthy", "version": "0.2.0"}
```

此端点在 `src/rhizome/api/main.py` 中已定义，无需额外开发。

## ChromaDB

项目使用 `chromadb.PersistentClient` 嵌入式模式，数据直接写入 `/app/storage/chroma/` 的 SQLite3 和 Parquet 文件。不需要独立的 ChromaDB 服务进程或容器。不需要额外的网络配置。

如果在 Docker 之外运行过 `rhz serve` 或 `rhz vectorize`，确保 `storage/chroma/` 目录属于当前用户可写，否则 PersistentClient 在 SQLite 上加锁时会失败。

## PWA 限制

index.html 中的 Service Worker 注册需要 HTTPS 上下文才能生效。在局域网 `http://服务器IP:8000` 环境下，Service Worker 不会注册。表现为:
- 浏览器不会弹出"添加到桌面"提示
- 离线缓存功能不可用
- 搜索、浏览、添加节点等所有在线功能正常工作

如果需要 PWA 完整功能，需在容器前加 Nginx 反向代理并配置自签名证书或通过 Tailscale HTTPS 访问。

## Google Fonts

index.html 从 `fonts.googleapis.com` 和 `fonts.gstatic.com` 加载 Oswald 和 Noto Sans SC 字体。如果服务器不能访问外网，字体请求会超时，浏览器降级使用系统默认字体。不影响页面功能。

如需完全离线使用，将字体文件下载到 `src/rhizome/web/static/fonts/` 并在 index.html 的 CSS 中改用本地 `@font-face` 引用，移除 Google Fonts 的 `<link>` 标签。
