# Rhizome Thinking - 阶段二实现文档

## 概述

阶段二实现了语义检索与跨设备访问能力，主要包括：

1. **向量存储** - ChromaDB + MiniMax Embedding API
2. **两段式查询引擎** - 语义锚点 + 查询修饰符
3. **FastAPI 后端服务** - RESTful API
4. **PWA 前端应用** - 手机/电脑访问
5. **聚合视图** - 按标签分组展示

## 新增模块

### 1. 检索模块 (`src/rhizome/retrieval/`)

#### `vector_store.py`
- `EmbeddingGenerator` - MiniMax Embedding API 封装
- `VectorStore` - ChromaDB 向量存储管理
- 支持批量向量化和增量更新

#### `query_engine.py`
- `QueryEngine` - 两段式查询引擎
- `QueryModifiers` - 查询修饰符（时间、标签、限制）
- `QueryResult` - 查询结果封装
- 支持按标签/时间分组

### 2. API 模块 (`src/rhizome/api/`)

#### `main.py`
- FastAPI 应用创建和配置
- CORS 中间件
- 静态文件服务

#### `routes/`
- `nodes.py` - 节点 CRUD 操作
- `query.py` - 语义查询接口
- `links.py` - 连接管理
- `stats.py` - 统计信息

### 3. Web 前端 (`src/rhizome/web/`)

#### PWA 特性
- Service Worker 离线支持
- Web App Manifest
- 响应式设计

#### 功能
- 语义搜索 + 标签过滤
- 添加节点表单
- 聚合视图展示
- 节点详情弹窗
- 统计信息面板

## API 接口

### 节点管理
```
POST   /api/v1/nodes              # 创建节点
GET    /api/v1/nodes              # 列出节点
GET    /api/v1/nodes/{id}         # 获取节点详情
DELETE /api/v1/nodes/{id}         # 删除节点
```

### 查询
```
POST   /api/v1/query              # 语义查询
POST   /api/v1/query/cluster      # 聚合视图查询
GET    /api/v1/search             # 关键词搜索
GET    /api/v1/nodes/{id}/related # 获取相关节点
```

### 连接管理
```
GET    /api/v1/nodes/{id}/links   # 获取节点连接
POST   /api/v1/links              # 创建连接
POST   /api/v1/nodes/{id}/links/{target_id}/confirm  # 确认连接
```

### 统计
```
GET    /api/v1/stats               # 总体统计
GET    /api/v1/stats/recent        # 最近活动
GET    /api/v1/tags                # 标签列表
```

## CLI 新增命令

```bash
# 启动 Web 服务器
rhz serve [--host 0.0.0.0] [--port 8000] [--reload]

# 批量向量化存量节点
rhz vectorize [--batch-size 5] [--mock]

# 语义查询
rhz query "查询内容" [--limit 10] [--tag definitive] [--time-range last_month]
```

## 快速开始

### 1. 安装阶段二依赖

```bash
pip install -e ".[stage2]"
```

### 2. 向量化存量节点

```bash
# 查看有多少节点需要向量化
rhz stats

# 批量向量化
rhz vectorize

# 或使用模拟模式（不调用API）
rhz vectorize --mock
```

### 3. 启动服务器

```bash
# 开发模式（热重载）
rhz serve --reload

# 生产模式
rhz serve --host 0.0.0.0 --port 8000
```

### 4. 访问应用

- **Web 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

### 5. 添加到手机主屏幕

1. 用手机浏览器访问服务器地址
2. 点击"添加到主屏幕"
3. 享受原生应用体验

## 部署建议

### 使用 Cloudflare Tunnel

1. 安装 cloudflared
```bash
# Windows (PowerShell)
winget install Cloudflare.cloudflared

# 或使用 scoop
scoop install cloudflared
```

2. 登录并创建隧道
```bash
cloudflared tunnel login
cloudflared tunnel create rhizome
```

3. 配置并运行
```bash
cloudflared tunnel route dns rhizome your-domain.example.com
cloudflared tunnel run rhizome
```

### 使用 systemd (Linux)

```ini
# /etc/systemd/system/rhizome.service
[Unit]
Description=Rhizome Thinking Knowledge Base
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/rhizome-thinking
Environment=PATH=/path/to/rhizome-thinking/venv/bin
Environment=MINIMAX_API_KEY=your-api-key
ExecStart=/path/to/rhizome-thinking/venv/bin/uvicorn rhizome.api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable rhizome
sudo systemctl start rhizome
```

## 完成标准

✅ **阶段二完成检查清单：**

- [ ] 已有 50+ 个节点
- [ ] 所有节点已完成向量化
- [ ] 能在手机上通过 PWA 访问
- [ ] 能通过语义查询找到已遗忘的相关节点
- [ ] 聚合视图正常工作

## 注意事项

1. **API Key 安全** - 不要将 MINIMAX_API_KEY 提交到版本控制
2. **备份** - 定期备份 `storage/` 目录
3. **内存使用** - ChromaDB 大约占用 200-500MB 内存
4. **首次启动** - 首次启动可能需要一些时间来加载 ChromaDB

## 故障排除

### ChromaDB 启动失败
```bash
# 删除旧的向量库
rm -rf storage/chroma
# 重新向量化
rhz vectorize
```

### 找不到节点
```bash
# 检查向量库状态
python -c "from rhizome.retrieval.vector_store import VectorStore; print(VectorStore().get_stats())"
```

### API 返回空结果
- 确认节点已完成向量化
- 检查 MINIMAX_API_KEY 是否有效
- 查看服务器日志获取详细错误
