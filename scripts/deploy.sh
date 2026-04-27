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
