#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# 1. 安装 Docker（如未安装）
if ! command -v docker &>/dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
    echo "Docker 已安装，请重新登录使 docker 组权限生效，然后再次运行此脚本"
    exit 0
fi

# 检查 docker compose 插件
if ! docker compose version &>/dev/null; then
    echo "需要 Docker Compose v2 插件，但未找到"
    exit 1
fi

# 2. 生成 .env
if [ ! -f .env ]; then
    echo "=== 配置 API Key ==="
    read -rp "MiniMax API Key: " MINIMAX_KEY
    read -rp "SiliconFlow API Key: " SILICONFLOW_KEY

    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || \
                 openssl rand -base64 32)

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
    echo ".env 已生成"
fi

# 3. 创建数据目录
mkdir -p storage/nodes storage/metadata storage/chroma storage/themes storage/backups

# 4. 构建并启动
echo "构建镜像并启动..."
docker compose up -d --build 2>&1

# 5. 等待健康检查
echo "等待服务就绪..."
PORT="${PORT:-8000}"
for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "服务已就绪"
        break
    fi
    if [ "$i" -eq 5 ]; then
        echo "首次启动较慢（需拉取镜像并编译依赖），请耐心等待..."
    fi
    sleep 3
done

# 6. 显示结果
SERVER_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
echo ""
echo "=== 部署完成 ==="
echo "访问地址: http://${SERVER_IP}:${PORT}"
echo "API文档:  http://${SERVER_IP}:${PORT}/docs"
echo ""
echo "管理命令:"
echo "  docker compose logs -f    # 查看日志"
echo "  docker compose restart    # 重启"
echo "  docker compose down       # 停止"
