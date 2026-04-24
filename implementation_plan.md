# Rhizome-thinking 实现文档

> 版本: v1.0 | 基于设计文档 v1.1 的完整实现方案

---

## 目录

1. [项目架构概览](#一项目架构概览)
2. [目录结构](#二目录结构)
3. [阶段一：管道验证](#三阶段一管道验证)
4. [阶段二：语义检索与跨设备访问](#四阶段二语义检索与跨设备访问)
5. [阶段三：图形化视图与认知地图](#五阶段三图形化视图与认知地图)
6. [部署与运维](#六部署与运维)
7. [测试策略](#七测试策略)

---

## 一、项目架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户层                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐  │
│  │  CLI 工具   │    │  PWA 前端   │    │      Obsidian (只读)         │  │
│  │  (阶段一)   │    │  (阶段二+)  │    │                              │  │
│  └──────┬──────┘    └──────┬──────┘    └─────────────────────────────┘  │
└─────────┼──────────────────┼────────────────────────────────────────────┘
          │                  │
          │                  ▼
          │           ┌─────────────────┐
          │           │   FastAPI 服务   │
          │           │   (阶段二+)      │
          │           └────────┬────────┘
          │                    │
          ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           核心处理层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Input Handler│  │ LLM Processor│  │ Link Manager │  │ Node Store  │  │
│  │   输入处理    │  │  LLM 处理    │  │   连接管理    │  │   节点存储   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            存储层                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  Markdown 文件   │  │  Metadata JSON   │  │    ChromaDB (阶段二+)    │  │
│  │  (人类可读)      │  │  (节点元数据)     │  │    (向量数据库)          │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心模块说明

| 模块 | 职责 | 技术实现 |
|------|------|----------|
| `Input Handler` | 接收、验证用户输入 | Python Click (CLI) / FastAPI (Web) |
| `LLM Processor` | 调用 MiniMax API 处理内容 | 异步 HTTP 客户端 (httpx/aiohttp) |
| `Link Manager` | 管理节点间连接关系 | 本地图算法实现 |
| `Node Store` | 节点的 CRUD 操作 | 文件系统 + JSON |
| `Vector Store` | 语义检索 (阶段二) | ChromaDB |

---

## 二、目录结构

```
rhizome-thinking/
├── README.md                          # 项目说明
├── knowledge_base_design.md           # 设计文档
├── implementation_plan.md             # 本文档
├── pyproject.toml                     # Python 项目配置
├── requirements/                      # 依赖管理
│   ├── base.txt                       # 基础依赖
│   ├── stage1.txt                     # 阶段一依赖
│   ├── stage2.txt                     # 阶段二依赖
│   └── stage3.txt                     # 阶段三依赖
├── src/                               # 源代码
│   └── rhizome/
│       ├── __init__.py
│       ├── cli.py                     # CLI 入口 (阶段一)
│       ├── config.py                  # 配置管理
│       ├── api/                       # FastAPI 服务 (阶段二)
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── nodes.py
│       │   │   ├── query.py
│       │   │   └── links.py
│       │   └── dependencies.py
│       ├── core/                      # 核心逻辑
│       │   ├── __init__.py
│       │   ├── models.py              # Pydantic 模型
│       │   ├── node_store.py          # 节点存储
│       │   ├── llm_processor.py       # LLM 处理
│       │   ├── link_manager.py        # 连接管理
│       │   └── input_handler.py       # 输入处理
│       ├── retrieval/                 # 检索模块 (阶段二)
│       │   ├── __init__.py
│       │   ├── vector_store.py        # ChromaDB 封装
│       │   └── query_engine.py        # 查询引擎
│       └── web/                       # PWA 前端 (阶段二)
│           ├── static/
│           │   ├── css/
│           │   ├── js/
│           │   └── images/
│           └── templates/
│               └── index.html
├── storage/                           # 数据存储 (gitignore)
│   ├── nodes/                         # Markdown 节点文件
│   │   └── README.md
│   ├── metadata/                      # 节点元数据 JSON
│   │   └── nodes_index.json
│   └── chroma/                        # ChromaDB 数据 (阶段二)
├── scripts/                           # 工具脚本
│   ├── setup.sh                       # 环境初始化
│   ├── dev_server.py                  # 开发服务器
│   └── deploy.sh                      # 部署脚本
├── tests/                             # 测试代码
│   ├── __init__.py
│   ├── test_node_store.py
│   ├── test_llm_processor.py
│   └── conftest.py
└── docs/                              # 其他文档
    ├── api_reference.md
    └── deployment_guide.md
```

---

## 三、阶段一：管道验证

### 3.1 阶段目标

跑通最小化流程，验证"核心命题"格式是否真正适合使用习惯。

**完成标准**: 积累 20-30 个节点，主观感受格式是否有价值

### 3.2 功能范围

```
┌─────────────────────────────────────────────────────────┐
│                    阶段一功能范围                         │
├─────────────────────────────────────────────────────────┤
│  ✅ CLI 输入工具                                          │
│  ✅ LLM 处理流程 (MiniMax API)                            │
│  ✅ 节点存储 (Markdown + JSON)                            │
│  ✅ 连接推荐 (文本展示，用户手动确认)                       │
│  ✅ Obsidian 兼容的文件格式                               │
├─────────────────────────────────────────────────────────┤
│  ❌ 向量检索 (使用 Obsidian 搜索替代)                      │
│  ❌ Web 界面                                             │
│  ❌ 语义查询                                             │
└─────────────────────────────────────────────────────────┘
```

### 3.3 核心数据结构

#### Node 模型 (Pydantic)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Source(BaseModel):
    type: Literal["book", "paper", "article", "original"]
    title: Optional[str] = None
    location: Optional[str] = None

class Processed(BaseModel):
    proposition: str
    open_questions: list[str] = Field(default_factory=list)

class Link(BaseModel):
    target_id: str
    relation_type: Literal["support", "contradict", "extend", "source", "analogy"]
    strength: float = Field(ge=0.0, le=1.0)
    confirmed: bool = False

class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    source: Source
    raw_input: str
    processed: Processed
    tags: list[Literal["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]]
    links: list[Link] = Field(default_factory=list)
    embedding: Optional[list[float]] = None  # 阶段二填充
```

#### Markdown 文件格式

```markdown
---
id: "550e8400-e29b-41d4-a716-446655440000"
timestamp: "2026-04-20T10:30:00"
source:
  type: "paper"
  title: "Attention Is All You Need"
  location: "Section 3.2"
tags:
  - "definitive"
  - "cross-domain"
links:
  - target_id: "660e8400-e29b-41d4-a716-446655440001"
    relation_type: "support"
    strength: 0.85
    confirmed: true
---

# 核心命题

Transformer 的自注意力机制使序列建模不再需要递归结构，可并行计算。

# 开放问题

- 自注意力的时间复杂度在极长序列上是否会成为瓶颈？
- 这种"注意力即一切"的范式如何迁移到其他认知任务？

---

# 原始输入

刚刚读 Transformer 论文，发现 self-attention 可以完全替代 RNN 的递归结构，
这样整个模型可以并行训练，速度应该会快很多。但不知道长序列会不会有问题。
```

### 3.4 LLM Prompt 设计

#### 系统 Prompt

```
你是一个个人知识库的智能助手。你的任务是将用户的输入整理成结构化的知识节点。

核心原则：
1. 保留原始输入，不做过度修改
2. 命题的表述方式由输入的确定性决定
3. 提取明确的开放问题
4. 分配准确的内容性质标签

内容性质标签定义：
- definitive: 有依据的明确结论或陈述
- inferred: 基于已有内容推断出的结论  
- vague: 模糊感知，尚未能清晰表达
- needs_thinking: 明确需要进一步思考的问题
- cross-domain: 跨越多个主题领域的想法

关系类型定义：
- support: 支持/证实
- contradict: 矛盾/反驳
- extend: 延伸/发展
- source: 来源/基础
- analogy: 类比/相似
```

#### 用户 Prompt

```
请处理以下输入，生成知识节点：

<raw_input>
{{user_input}}
</raw_input>

请返回以下 JSON 格式：
{
  "proposition": "核心命题，根据输入确定性选择表述方式",
  "open_questions": ["提取的开放问题列表"],
  "tags": ["definitive|inferred|vague|needs_thinking|cross-domain"],
  "potential_links": [
    {
      "target_node_summary": "可能相关的已有节点摘要",
      "relation_type": "support|contradict|extend|source|analogy",
      "reasoning": "为什么认为它们相关"
    }
  ]
}
```

### 3.5 CLI 命令设计

```bash
# 添加新节点
rhz add "刚刚读 Transformer 论文..."

# 从文件添加
rhz add -f ./note.txt --source paper --title "Attention Is All You Need"

# 列出最近节点
rhz list --limit 10

# 查看节点详情
rhz show <node_id>

# 确认连接
rhz link confirm <node_id> <target_id>

# 拒绝连接
rhz link reject <node_id> <target_id>

# 手动添加连接
rhz link add <node_id> <target_id> --type support --strength 0.8

# 初始化存储目录
rhz init
```

### 3.6 实现步骤

#### Step 1: 项目初始化

```bash
# 创建项目结构
mkdir -p rhizome-thinking/src/rhizome/{core,api,retrieval,web}
mkdir -p rhizome-thinking/storage/{nodes,metadata,chroma}
mkdir -p rhizome-thinking/{scripts,tests,docs}

# 初始化 Python 项目
cd rhizome-thinking
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 创建 pyproject.toml
```

#### Step 2: 核心模块实现

1. **config.py** - 配置管理
   - 环境变量读取
   - MiniMax API Key 管理
   - 存储路径配置

2. **models.py** - Pydantic 模型
   - Node、Source、Processed、Link 等模型定义
   - 验证逻辑

3. **node_store.py** - 节点存储
   - Markdown 文件读写
   - JSON 元数据管理
   - 节点 CRUD 操作

4. **llm_processor.py** - LLM 处理
   - MiniMax API 调用封装
   - 异步请求处理
   - 响应解析

5. **cli.py** - CLI 入口
   - Click 命令定义
   - 命令实现

#### Step 3: 验证测试

- 手动输入 20-30 条不同类型的内容
- 验证命题格式是否适合个人习惯
- 收集反馈，调整 Prompt 和流程

### 3.7 阶段一交付物

| 交付物 | 说明 |
|--------|------|
| `src/rhizome/cli.py` | 完整功能的 CLI 工具 |
| `src/rhizome/core/` | 核心模块 (models, node_store, llm_processor) |
| `storage/nodes/` | 20-30 个验证用的节点文件 |
| 使用反馈文档 | 记录使用感受和改进建议 |

---

## 四、阶段二：语义检索与跨设备访问

### 4.1 阶段目标

实现语义检索能力，支持通过手机和电脑访问系统。

**前提**: 50 个节点以上
**完成标准**: 能在手机上通过语义查询找到自己已经忘记存在的相关节点

### 4.2 功能范围

```
┌─────────────────────────────────────────────────────────┐
│                    阶段二新增功能                         │
├─────────────────────────────────────────────────────────┤
│  ✅ 节点向量化 (MiniMax Embedding API)                    │
│  ✅ ChromaDB 向量数据库                                   │
│  ✅ 两段式查询接口                                        │
│  ✅ FastAPI 后端服务                                      │
│  ✅ PWA 前端应用                                          │
│  ✅ 聚合视图 (Cluster View)                               │
│  ✅ Cloudflare Tunnel 部署                                │
├─────────────────────────────────────────────────────────┤
│  ❌ 认知地图视图 (阶段三)                                  │
│  ❌ LLM 自动确认连接 (阶段三)                              │
└─────────────────────────────────────────────────────────┘
```

### 4.3 系统架构升级

```
┌─────────────────────────────────────────────────────────┐
│                       用户层                             │
│  ┌─────────────────┐  ┌───────────────────────────────┐ │
│  │   PWA 前端      │  │     CLI (保留)                │ │
│  │   (手机/电脑)    │  │                               │ │
│  └────────┬────────┘  └───────────────┬───────────────┘ │
└───────────┼───────────────────────────┼─────────────────┘
            │                           │
            ▼                           │
┌───────────────────────────────────────┼─────────────────┐
│              FastAPI 服务层            │                 │
│  ┌─────────────┐  ┌──────────────────┐│  ┌────────────┐ │
│  │  API Routes │  │  Query Engine    ││  │ CLI Router │ │
│  │             │  │                  ││  │            │ │
│  │  POST /nodes│  │  - Semantic      ││  │ (保留)     │ │
│  │  GET /query │  │    Search        ││  │            │ │
│  │  GET /links │  │  - Filter        ││  └────────────┘ │
│  │             │  │    Processing    ││                 │
│  └─────────────┘  └──────────────────┘│                 │
└───────────────────────────────────────┴─────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│                      存储层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │   Markdown   │  │  Metadata    │  │   ChromaDB     │ │
│  │   (文件)      │  │  (JSON)      │  │   (向量)        │ │
│  └──────────────┘  └──────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 4.4 API 设计

#### RESTful API 规范

```yaml
# 节点管理
POST   /api/v1/nodes              # 创建节点
GET    /api/v1/nodes              # 列出节点
GET    /api/v1/nodes/{id}         # 获取节点详情
PUT    /api/v1/nodes/{id}         # 更新节点
DELETE /api/v1/nodes/{id}         # 删除节点

# 查询
POST   /api/v1/query              # 语义查询
GET    /api/v1/search             # 关键词搜索

# 连接管理
GET    /api/v1/nodes/{id}/links   # 获取节点连接
POST   /api/v1/links              # 创建连接
PUT    /api/v1/links/{id}         # 更新连接 (确认/修改)
DELETE /api/v1/links/{id}         # 删除连接

# 标签和元数据
GET    /api/v1/tags               # 获取所有标签
GET    /api/v1/stats              # 统计信息
```

#### 查询接口详细设计

**请求**: `POST /api/v1/query`

```json
{
  "anchor": "agent 的自我模型如何涌现",
  "modifiers": {
    "time_range": "last_month",
    "tags": ["definitive", "needs_thinking"],
    "relation_type": null,
    "limit": 20
  }
}
```

**响应**:

```json
{
  "results": [
    {
      "node": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "proposition": "自我模型可从记忆检索模式中涌现",
        "tags": ["definitive"],
        "timestamp": "2026-04-15T10:30:00"
      },
      "similarity": 0.89,
      "highlight": "与查询的匹配片段"
    }
  ],
  "grouped_by_tag": {
    "definitive": [...],
    "needs_thinking": [...]
  }
}
```

### 4.5 PWA 前端设计

#### 页面结构

```
┌─────────────────────────────────────────────────────────┐
│  Rhizome Thinking                    [🔍] [⚙️]          │  ← Header
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🔍 输入查询...                                  │   │  ← Search Box
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [全部] [明确结论] [开放问题] [模糊感知] [待思考]          │  ← Tag Filters
│                                                         │
│  ┌─ 明确结论 ─────────────────┐                        │
│  │  · 节点 A（89% 相关）       │                        │  ← Cluster View
│  │  · 节点 B（76% 相关）       │                        │
│  └────────────────────────────┘                        │
│                                                         │
│  ┌─ 开放问题 ─────────────────┐                        │
│  │  · 节点 D                   │                        │
│  └────────────────────────────┘                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
│  [🏠]    [➕]    [📊]                                  │  ← Bottom Nav
└─────────────────────────────────────────────────────────┘
```

#### 组件清单

| 组件 | 功能 |
|------|------|
| `SearchBar` | 语义锚点输入 + 修饰符选择 |
| `TagFilter` | 标签筛选按钮组 |
| `ClusterView` | 聚合视图展示 |
| `NodeCard` | 节点卡片组件 |
| `NodeDetail` | 节点详情弹窗/页面 |
| `AddNodeForm` | 添加节点表单 |
| `LinkViewer` | 连接关系展示 |

### 4.6 ChromaDB 集成

#### 集合设计

```python
# collection: nodes
{
    "ids": ["node_id_1", "node_id_2", ...],
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...], ...],
    "metadatas": [
        {
            "proposition": "核心命题",
            "tags": ["definitive", "cross-domain"],
            "timestamp": "2026-04-20T10:30:00",
            "source_type": "paper"
        },
        ...
    ],
    "documents": ["原始输入文本", ...]
}
```

#### 检索流程

```python
async def semantic_search(anchor: str, modifiers: dict) -> list[Node]:
    # 1. 将锚点向量化
    anchor_embedding = await get_embedding(anchor)
    
    # 2. 构建过滤条件
    where_clause = build_where_clause(modifiers)
    
    # 3. 向量检索
    results = collection.query(
        query_embeddings=[anchor_embedding],
        n_results=modifiers.get("limit", 20),
        where=where_clause
    )
    
    # 4. 后处理：按标签分组
    grouped = group_by_tags(results)
    
    return grouped
```

### 4.7 实现步骤

#### Step 1: 向量存储实现

1. 集成 ChromaDB
2. 实现 embedding 生成 (MiniMax API)
3. 存量节点批量向量化脚本

#### Step 2: FastAPI 服务搭建

1. 创建 FastAPI 应用结构
2. 实现 API 路由
3. 添加 CORS、认证中间件
4. 集成核心模块

#### Step 3: PWA 开发

1. 基础 HTML/CSS/JS 框架
2. 实现查询页面
3. 实现节点详情页面
4. 实现添加节点页面
5. 添加 Service Worker
6. 添加 manifest.json

#### Step 4: 部署配置

1. Cloudflare Tunnel 配置
2. 生产环境部署脚本
3. HTTPS 证书配置

### 4.8 阶段二交付物

| 交付物 | 说明 |
|--------|------|
| `src/rhizome/api/` | FastAPI 完整服务 |
| `src/rhizome/retrieval/` | 向量检索模块 |
| `src/rhizome/web/` | PWA 前端代码 |
| `scripts/deploy.sh` | 部署脚本 |
| 可访问的 Web 服务 | 通过 Cloudflare Tunnel |

---

## 五、阶段三：图形化视图与认知地图

### 5.1 阶段目标

实现聚合视图的完整图形化呈现，以及认知地图视图。

**前提**: 100 个节点以上，查询已成为常规习惯
**完成标准**: 能通过认知地图视图发现跨域连接

### 5.2 功能范围

```
┌─────────────────────────────────────────────────────────┐
│                    阶段三新增功能                         │
├─────────────────────────────────────────────────────────┤
│  ✅ 聚合视图完整图形化                                     │
│  ✅ 认知地图视图 (Epistemic Map)                          │
│  ✅ 动态主题聚类 (LLM 生成主题标签)                         │
│  ✅ 连接自动确认授权机制                                   │
│  ✅ 节点关联可视化交互                                     │
├─────────────────────────────────────────────────────────┤
│  ⚪ 高级功能 (可选)                                        │
│     - 时间轴视图                                          │
│     - 导出功能 (PDF, 图片)                                 │
│     - 导入功能 (Obsidian, Notion)                          │
└─────────────────────────────────────────────────────────┘
```

### 5.3 认知地图视图设计

#### 可视化规格

```
确定 │
  1.0│
     │    [AI 研究]           [哲学]              [科幻]
  0.8│     · A   · B──· C      · G                 · K──· L
     │           └──· D        · H──· I
  0.6│     · E                                · M
     │
  0.4│
     │           · F           · J
  0.2│                                      · N──· O
  0.0├──────────────────────────────────────────────────→ 主题
     │         · P                                    └──· Q
-0.2│
模糊 │
```

#### 坐标计算逻辑

```python
class EpistemicMapLayout:
    """
    Y 轴：认知确定性（固定）
    - 根据标签映射到 0-1 区间
    - definitive: 0.8-1.0
    - inferred: 0.6-0.8
    - vague: 0.2-0.6
    - needs_thinking: 0.0-0.2
    
    X 轴：主题分布（动态聚类）
    - 使用 LLM 对节点进行主题聚类
    - t-SNE 或 UMAP 降维到 2D
    - 主题区域标签由 LLM 自动生成
    """
    
    async def calculate_layout(self, nodes: list[Node]) -> dict:
        # 1. LLM 主题聚类
        clusters = await self.llm_cluster(nodes)
        
        # 2. 提取节点特征
        features = self.extract_features(nodes)
        
        # 3. t-SNE 降维
        embeddings_2d = TSNE(n_components=2).fit_transform(features)
        
        # 4. 计算 Y 坐标（确定性）
        y_coords = [self.certainty_to_y(node) for node in nodes]
        
        # 5. 生成主题标签
        cluster_labels = await self.generate_cluster_labels(clusters)
        
        return {
            "nodes": [
                {
                    "id": node.id,
                    "x": float(embeddings_2d[i][0]),
                    "y": y_coords[i],
                    "cluster": clusters[i],
                    ...
                }
                for i, node in enumerate(nodes)
            ],
            "clusters": cluster_labels
        }
```

### 5.4 主题聚类实现

```python
async def llm_cluster(nodes: list[Node], n_clusters: int = 5) -> list[int]:
    """
    使用 LLM 进行主题聚类
    """
    # 构建 prompt
    node_descriptions = [
        f"Node {i}: {node.processed.proposition}"
        for i, node in enumerate(nodes)
    ]
    
    prompt = f"""
    请将以下节点聚类成 {n_clusters} 个主题群组：
    
    {'\n'.join(node_descriptions)}
    
    请返回 JSON 格式：
    {{
      "clusters": [
        {{"cluster_id": 0, "node_indices": [0, 3, 5], "theme": "主题名称"}},
        ...
      ]
    }}
    """
    
    response = await llm.complete(prompt)
    return parse_clusters(response)
```

### 5.5 连接自动确认机制

```python
class AutoLinkConfig(BaseModel):
    """自动连接配置"""
    enabled: bool = False
    min_strength_threshold: float = 0.85
    max_auto_links_per_node: int = 3
    excluded_relation_types: list[str] = ["contradict"]

class LinkManager:
    async def process_new_node(self, node: Node) -> list[Link]:
        # 1. 生成潜在连接
        potential_links = await self.find_potential_links(node)
        
        # 2. 过滤和排序
        filtered = self.filter_links(potential_links)
        
        # 3. 自动确认决策
        if self.auto_link_config.enabled:
            for link in filtered:
                if self.should_auto_confirm(link):
                    link.confirmed = True
                    link.auto_confirmed = True
        
        return filtered
    
    def should_auto_confirm(self, link: Link) -> bool:
        cfg = self.auto_link_config
        return (
            link.strength >= cfg.min_strength_threshold and
            link.relation_type not in cfg.excluded_relation_types
        )
```

### 5.6 前端可视化库选择

| 方案 | 库 | 优点 | 缺点 |
|------|-----|------|------|
| A | D3.js | 灵活度高 | 学习曲线陡峭 |
| B | **Cytoscape.js** | 图可视化专业，性能好 | 需要额外学习 |
| C | vis-network | 简单易用 | 自定义受限 |

**推荐**: Cytoscape.js
- 专为图可视化设计
- 支持力导向布局
- 性能优秀，支持大量节点
- 丰富的交互功能

### 5.7 实现步骤

#### Step 1: 后端增强

1. 实现主题聚类 API
2. 实现布局计算 API
3. 添加自动连接配置

#### Step 2: 前端可视化

1. 集成 Cytoscape.js
2. 实现认知地图视图
3. 实现节点交互功能
4. 优化大量节点渲染性能

#### Step 3: 交互优化

1. 视图切换功能
2. 缩放和导航
3. 节点选择和详情展示
4. 连接探索功能

### 5.8 阶段三交付物

| 交付物 | 说明 |
|--------|------|
| 认知地图视图 | 完整的二维可视化界面 |
| 主题聚类服务 | LLM 驱动的动态聚类 |
| 自动连接机制 | 可配置的自动确认系统 |
| 性能优化 | 支持 100+ 节点的流畅交互 |

---

## 六、部署与运维

### 6.1 环境要求

#### 开发环境

```
Python: 3.11+
Node.js: 18+ (前端开发)
OS: Linux/macOS/Windows
```

#### 生产环境（小主机）

```
CPU: Intel i5-8400
RAM: 4GB
Storage: 512GB SSD
OS: Ubuntu Server 22.04 LTS
Network: 稳定的互联网连接
```

### 6.2 依赖管理

#### 基础依赖 (requirements/base.txt)

```
# 核心框架
pydantic>=2.0.0
pydantic-settings>=2.0.0

# 配置
python-dotenv>=1.0.0
pyyaml>=6.0

# 工具
python-dateutil>=2.8.0
uuid6>=2023.5.2
```

#### 阶段一依赖 (requirements/stage1.txt)

```
-r base.txt

# CLI
click>=8.1.0
rich>=13.0.0

# LLM
httpx>=0.25.0
tenacity>=8.2.0

# 存储
markdown>=3.5.0
frontmatter>=3.8.0
```

#### 阶段二依赖 (requirements/stage2.txt)

```
-r stage1.txt

# Web 框架
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6

# 向量数据库
chromadb>=0.4.18
sentence-transformers>=2.2.0

# 前端（可选，用于模板）
jinja2>=3.1.0
```

### 6.3 部署流程

#### 初始部署

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "🚀 开始部署 Rhizome Thinking..."

# 1. 克隆代码
git clone https://github.com/yourusername/rhizome-thinking.git
cd rhizome-thinking

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements/stage2.txt

# 4. 配置环境变量
cp .env.example .env
# 用户需要编辑 .env 文件

# 5. 初始化存储
python -m rhizome init

# 6. 安装 Cloudflare Tunnel
# 参考: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

# 7. 创建 systemd 服务
sudo tee /etc/systemd/system/rhizome.service > /dev/null <<EOF
[Unit]
Description=Rhizome Thinking Knowledge Base
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/uvicorn rhizome.api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable rhizome
sudo systemctl start rhizome

# 8. 启动 Cloudflare Tunnel
# cloudflared tunnel --config ~/.cloudflared/config.yml run

echo "✅ 部署完成！"
echo "访问地址: https://your-domain.cloudflareaccess.com"
```

#### 更新部署

```bash
#!/bin/bash
# scripts/update.sh

set -e

cd ~/rhizome-thinking

# 1. 拉取最新代码
git pull origin main

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 更新依赖
pip install -r requirements/stage2.txt --upgrade

# 4. 运行数据库迁移（如有）
python -m rhizome migrate

# 5. 重启服务
sudo systemctl restart rhizome

echo "✅ 更新完成！"
```

### 6.4 环境变量配置

```bash
# .env

# MiniMax API
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.chat/v1
MINIMAX_MODEL=minimax-text-01
MINIMAX_EMBEDDING_MODEL=embedding-01

# 应用配置
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your_random_secret_key

# 存储路径
STORAGE_DIR=/home/user/rhizome-thinking/storage

# ChromaDB
CHROMA_PERSIST_DIR=/home/user/rhizome-thinking/storage/chroma

# 可选：Sentry 错误追踪
# SENTRY_DSN=your_sentry_dsn
```

### 6.5 监控与日志

```python
# src/rhizome/monitoring.py

import logging
from functools import wraps
from time import perf_counter

logger = logging.getLogger("rhizome")

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('storage/logs/rhizome.log'),
            logging.StreamHandler()
        ]
    )

def timed(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = perf_counter() - start
            logger.info(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            raise
    return wrapper
```

### 6.6 备份策略

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backup/rhizome"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份 Markdown 文件和元数据
tar -czf "$BACKUP_DIR/nodes_$DATE.tar.gz" storage/nodes storage/metadata

# 备份 ChromaDB（阶段二）
if [ -d "storage/chroma" ]; then
    tar -czf "$BACKUP_DIR/chroma_$DATE.tar.gz" storage/chroma
fi

# 保留最近 30 天的备份
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "✅ 备份完成: $DATE"
```

---

## 七、测试策略

### 7.1 测试分层

```
┌─────────────────────────────────────────────────────────┐
│  E2E 测试                                                │
│  - 完整用户流程测试                                        │
│  - Playwright / Selenium                                  │
├─────────────────────────────────────────────────────────┤
│  集成测试                                                │
│  - API 接口测试                                           │
│  - 数据库集成测试                                          │
│  - LLM 调用测试                                           │
├─────────────────────────────────────────────────────────┤
│  单元测试                                                │
│  - 核心逻辑测试                                           │
│  - 模型验证测试                                           │
│  - 工具函数测试                                           │
└─────────────────────────────────────────────────────────┘
```

### 7.2 关键测试用例

#### 阶段一测试

```python
# tests/test_node_store.py

import pytest
from rhizome.core.node_store import NodeStore
from rhizome.core.models import Node, Source, Processed

class TestNodeStore:
    def test_create_node(self, tmp_path):
        store = NodeStore(storage_dir=tmp_path)
        node = Node(
            source=Source(type="original"),
            raw_input="测试输入",
            processed=Processed(proposition="测试命题"),
            tags=["definitive"]
        )
        
        store.save(node)
        
        # 验证 Markdown 文件创建
        md_file = tmp_path / "nodes" / f"{node.id}.md"
        assert md_file.exists()
        
        # 验证元数据更新
        loaded = store.get(node.id)
        assert loaded.processed.proposition == "测试命题"
```

#### 阶段二测试

```python
# tests/test_query_engine.py

import pytest
from rhizome.retrieval.query_engine import QueryEngine

class TestQueryEngine:
    async def test_semantic_search(self, engine: QueryEngine):
        results = await engine.search(
            anchor="人工智能的自我意识",
            modifiers={"limit": 5}
        )
        
        assert len(results) <= 5
        assert all(r.similarity > 0.5 for r in results)
    
    async def test_tag_filter(self, engine: QueryEngine):
        results = await engine.search(
            anchor="测试查询",
            modifiers={"tags": ["definitive"]}
        )
        
        assert all("definitive" in r.node.tags for r in results)
```

### 7.3 测试运行

```bash
# 运行所有测试
pytest

# 运行特定阶段测试
pytest -m stage1
pytest -m stage2

# 覆盖率报告
pytest --cov=rhizome --cov-report=html
```

---

## 附录

### A. 项目时间线（预估）

| 阶段 | 工作量 | 预估时间 |
|------|--------|----------|
| 阶段一 | 核心开发 | 2-3 周 |
| 阶段一 | 验证使用 | 2-4 周 |
| 阶段二 | 核心开发 | 3-4 周 |
| 阶段二 | 验证使用 | 4-8 周 |
| 阶段三 | 核心开发 | 4-6 周 |
| 阶段三 | 优化迭代 | 持续 |

### B. 风险与应对

| 风险 | 可能性 | 影响 | 应对策略 |
|------|--------|------|----------|
| MiniMax API 不稳定 | 中 | 高 | 实现重试机制，准备备用方案 |
| 小主机性能不足 | 低 | 中 | 监控内存使用，必要时升级硬件 |
| ChromaDB 数据丢失 | 低 | 高 | 定期备份，导出为可读格式 |
| Prompt 效果不佳 | 中 | 中 | 持续调优，A/B 测试 |

### C. 参考资源

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Cytoscape.js Documentation](https://js.cytoscape.org/)
- [MiniMax API Documentation](https://www.minimaxi.com/)

---

*本文档基于 design.md v1.1 编写，实现过程中可能需要根据实际使用反馈进行调整。*
