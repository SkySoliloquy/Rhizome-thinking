# Rhizome Thinking

个人知识库系统。输入笔记内容，自动完成标签分类、语义链接、主题提取，支持全文搜索、语义检索，以及 AI 精炼内容生成。

<!-- TEST_UPDATE_MARKER: 用于测试自动更新系统 -->
<!-- TEST_UPDATE_MARKER_2: 第二次测试自动更新系统 -->

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
# 节点操作
rhz add "笔记内容"           # 添加节点
rhz add -f note.txt          # 从文件添加
rhz list                     # 列出所有节点
rhz list -t needs_thinking   # 按标签筛选
rhz show <node-id>           # 查看节点详情
rhz stats                    # 知识库统计

# 搜索
rhz query "搜索内容"         # 语义搜索
rhz search "关键词"          # 全文搜索
rhz find --proposition "..." --tag needs_thinking  # 组合筛选

# 关系管理（新版独立关系系统）
rhz relationship add <source_id> <target_id> -t supports -s strong
rhz relationship list
rhz relationship show <id>
rhz relationship delete <id>
rhz relationship validate
rhz relationship stats

# 备份
rhz backup create            # 创建备份
rhz backup list              # 列出备份
rhz backup restore <name>    # 恢复备份
rhz backup delete <name>     # 删除备份

# 服务信息
rhz server info              # 查看服务访问地址
```

## 核心功能

### 1. 语义搜索

支持三种搜索模式：
- **严格模式**: 2-5 个最精确的结果
- **平衡模式**: 5-10 个结果（默认）
- **探索模式**: 8-15 个结果，包含弱关联

### 2. AI 精炼内容

每个节点可由 AI 生成精炼内容，保留核心观点并优化表达：
- 单节点重新生成
- **批量精炼**: 在精准查询结果中多选节点，一键并行生成
- 精炼内容支持收起/展开，便于快速浏览

### 3. 主题系统

- 自动提取跨节点主题
- 主题版本追踪与演进检测
- 主题冲突识别与建议

### 4. 关系网络

- 新版独立关系系统（Relationship）
- 关系类型：支持、矛盾、延伸、引用、类比
- 关系强度：强 / 中 / 弱
- AI 自动建议关系

### 5. 备份与兼容

- 完整 ZIP 备份（节点 + 元数据 + 主题 + 关系）
- 向后兼容：旧版本备份可正常导入
- 导入后可使用批量精炼功能生成精炼内容

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

## 技术栈

- **后端**: Python 3.12, FastAPI, Pydantic
- **向量检索**: ChromaDB + SiliconFlow Embedding
- **LLM**: MiniMax API (MiniMax-M2.7)
- **前端**: Vanilla JavaScript PWA
- **存储**: Markdown 文件 + JSON 索引
- **部署**: Docker Compose
