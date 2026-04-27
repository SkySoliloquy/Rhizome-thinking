# Rhizome Thinking

个人知识库系统。输入笔记内容，自动完成标签分类、语义链接、主题提取，支持全文搜索和语义检索。

## 前置条件

- Linux 服务器 (x86_64 或 arm64)
- MiniMax API Key (LLM 处理)
- SiliconFlow API Key (向量嵌入)

## 一键部署

```bash
# 1. 把项目放到服务器
sudo mkdir -p /opt/rhizome-thinking
cd /opt/rhizome-thinking
git clone <仓库地址> rhizome-thinking
cd rhizome-thinking

# 2. 一行部署
bash scripts/deploy.sh
```

脚本会自动安装 Docker（如未安装）、提示输入 API Key、构建镜像、启动服务。

部署完成后访问: `http://服务器IP:8000`

## 日常更新

```bash
cd /opt/rhizome-thinking/rhizome-thinking
git pull
docker compose up -d --build
```

数据存储在 `./storage/` 目录（通过 Docker volume 挂载在宿主机），重建容器不会影响数据。

## 服务管理

```bash
docker compose up -d      # 启动
docker compose down       # 停止
docker compose restart    # 重启
docker compose logs -f    # 查看日志
docker compose ps         # 查看状态
```

## 命令行管理

```bash
rhz add "笔记内容"           # 添加节点
rhz list                    # 列出所有节点
rhz show <node-id>          # 查看节点详情
rhz query "搜索内容"         # 语义搜索
rhz stats                   # 知识库统计
rhz backup create           # 创建备份
rhz server info             # 查看服务访问地址
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `MINIMAX_API_KEY` | MiniMax API 密钥 | 必填 |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 | 必填 |
| `PORT` | 宿主机端口 | 8000 |
| `STORAGE_DIR` | 数据存储目录 | ./storage |
| `ENVIRONMENT` | 运行环境 | production |

## 架构

单容器 Docker 部署。FastAPI + uvicorn 提供 HTTP 服务，ChromaDB 以嵌入式 PersistentClient 运行在同一进程内，PWA 前端由 FastAPI 直接托管静态文件。

```
容器内:
  uvicorn (0.0.0.0:8000)
    ├── FastAPI API (/api/v1/*)
    ├── ChromaDB (嵌入式, /app/storage/chroma/)
    └── PWA 前端 (/)

宿主机挂载:
  ./storage/ → /app/storage/   (数据持久化)
  ./.env     → /app/.env       (配置只读)
```
