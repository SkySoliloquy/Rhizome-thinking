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
