# Rhizome Thinking 一键部署方案

## 需求分析

### 1. 核心需求

* **一键部署**: 在新服务器上执行一条命令即可完成完整部署

* **SSH远程管理**: 支持通过SSH连接服务器后使用命令行管理

* **局域网访问**: 部署后可通过局域网内其他设备访问前端界面

### 2. 当前项目状态

* Python项目，使用 `pyproject.toml` 管理依赖

* FastAPI后端 + 原生JS前端(PWA)

* ChromaDB向量数据库

* CLI已基于Click构建，功能较完善

* 无Docker配置

* 依赖MiniMax API和SiliconFlow API

***

## 部署架构设计

### 部署方式对比

| 方式                 | 优点             | 缺点         | 适用场景 |
| ------------------ | -------------- | ---------- | ---- |
| **Docker Compose** | 环境隔离、依赖完整、易于迁移 | 需要Docker环境 | 推荐方案 |
| **Conda + 脚本**     | 轻量、无需Docker    | 环境可能受系统影响  | 备选方案 |
| **Systemd服务**      | 原生系统集成、自动启动    | Linux专用    | 生产环境 |

**推荐方案**: Docker Compose + Systemd服务

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        服务器                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Docker Compose Stack                      │  │
│  │  ┌─────────────┐         ┌─────────────────────────┐  │  │
│  │  │  rhizome    │────────▶│    ChromaDB (向量库)     │  │  │
│  │  │  (主服务)    │         │                         │  │  │
│  │  │  :8000      │         └─────────────────────────┘  │  │
│  │  └─────────────┘                                    │  │
│  │         │                                            │  │
│  │         ▼                                            │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │  挂载卷:                                      │   │  │
│  │  │  - ./storage:/app/storage (数据持久化)        │   │  │
│  │  │  - ./.env:/app/.env (配置文件)                │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                 │
│                    ┌──────▼──────┐                          │
│                    │  Systemd    │                          │
│                    │  rhizome    │ (开机自启、进程守护)       │
│                    │  .service   │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 局域网访问
                              ▼
                    ┌─────────────────┐
                    │   用户浏览器      │
                    │  http://服务器IP:8000 │
                    └─────────────────┘
```

***

## 实施计划

### Phase 1: Docker化部署

#### 1.1 创建 Dockerfile

* 基于 `python:3.11-slim` 镜像

* 安装系统依赖 (gcc, etc.)

* 安装Python依赖

* 设置工作目录和环境变量

* 暴露8000端口

* 启动命令使用uvicorn

#### 1.2 创建 docker-compose.yml

* 主服务配置

* ChromaDB服务配置

* 数据卷挂载

* 网络配置

* 健康检查

#### 1.3 创建部署脚本 `deploy.sh`

功能：

* 检查Docker和Docker Compose安装

* 自动安装缺失的依赖

* 生成.env配置文件

* 拉取/构建镜像

* 启动服务

* 显示访问地址

### Phase 2: CLI增强 (SSH管理)

#### 2.1 添加服务器管理命令

新增CLI子命令 `rhz server`:

* `rhz server start` - 启动服务

* `rhz server stop` - 停止服务

* `rhz server restart` - 重启服务

* `rhz server status` - 查看服务状态

* `rhz server logs` - 查看日志

* `rhz server config` - 查看/修改配置

#### 2.2 添加系统健康检查

* API连通性检查

* 数据库状态检查

* 磁盘空间检查

* 配置验证

#### 2.3 添加远程访问信息

* `rhz server info` - 显示局域网访问地址

* 自动检测IP地址

### Phase 3: Systemd集成

#### 3.1 创建 systemd 服务文件

* 开机自启配置

* 进程守护

* 日志管理

* 环境变量设置

#### 3.2 创建安装脚本

* 自动安装systemd服务

* 启用开机自启

### Phase 4: 一键安装脚本

#### 4.1 创建 `install.sh`

* 系统要求检查 (Linux, Docker)

* 自动安装Docker (如未安装)

* 克隆/解压项目

* 执行部署

* 显示完成信息和访问地址

#### 4.2 支持参数

* `--port` - 自定义端口

* `--data-dir` - 自定义数据目录

* `--api-key` - 设置API Key

***

## 详细实施步骤

### 任务清单

1. **创建 Dockerfile**

   * 路径: `docker/Dockerfile`

   * 内容: Python 3.11基础镜像，安装所有依赖

2. **创建 docker-compose.yml**

   * 路径: `docker/docker-compose.yml`

   * 服务: rhizome-app, chromadb

   * 卷: storage持久化

3. **创建部署脚本 deploy.sh**

   * 路径: `scripts/deploy.sh`

   * 功能: 一键启动Docker环境

4. **增强CLI - 添加server命令组**

   * 文件: `src/rhizome/cli.py`

   * 新增: server子命令组

   * 功能: start, stop, restart, status, logs

5. **创建CLI安装命令**

   * 新增: `rhz install` 命令

   * 功能: 安装systemd服务

6. **创建systemd服务模板**

   * 路径: `scripts/rhizome.service.template`

7. **创建一键安装脚本 install.sh**

   * 路径: `install.sh` (项目根目录)

   * 功能: 完整的一键部署

8. **更新README.md**

   * 添加部署说明

***

## 使用示例

### 方案A: 最快部署 (Docker方式)

```bash
# 在服务器上执行一行命令
curl -fsSL https://raw.githubusercontent.com/user/rhizome-thinking/main/install.sh | bash

# 或者本地执行
wget https://raw.githubusercontent.com/user/rhizome-thinking/main/install.sh
chmod +x install.sh
./install.sh
```

### 方案B: 通过SSH管理

```bash
# SSH连接到服务器
ssh user@server-ip

# 进入项目目录
cd rhizome-thinking

# 管理服务
rhz server start    # 启动
rhz server status   # 查看状态
rhz server logs     # 查看日志
rhz server stop     # 停止

# 查看访问地址
rhz server info
# 输出: 访问地址: http://192.168.1.100:8000
```

### 方案C: 通过CLI直接操作数据

```bash
# SSH连接到服务器后，使用CLI管理数据
rhz add -f note.txt --type original
rhz list
rhz stats
rhz query "搜索内容"
```

***

## 网络访问

### 局域网访问

* 默认绑定 `0.0.0.0:8000`

* 自动检测并显示服务器IP地址

* 用户可在局域网内通过 `http://服务器IP:8000` 访问

### 安全建议 (生产环境)

* 使用Nginx反向代理

* 配置HTTPS

* 添加访问控制

* 配置防火墙规则

***

## 目录结构变更

```
rhizome-thinking/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── scripts/
│   ├── deploy.sh          # 部署脚本
│   ├── rhizome.service.template  # systemd模板
│   └── install-docker.sh  # Docker安装辅助
├── install.sh             # 一键安装脚本(根目录)
└── ...现有文件...
```

***

## 技术细节

### Docker配置要点

* 使用 `python:3.11-slim` 减小镜像体积

* 多阶段构建优化

* 非root用户运行

* 健康检查配置

### Systemd配置要点

* `Restart=always` 确保服务持续运行

* `Type=simple` 适用于容器化应用

* 日志输出到journald

### CLI server命令实现

* 使用 `subprocess` 调用docker/docker-compose命令

* 状态检测通过HTTP请求 `/health` 端点

* 日志读取docker日志输出

***

## 风险控制

1. **Docker未安装**: 安装脚本自动检测并安装
2. **端口冲突**: 支持自定义端口配置
3. **数据丢失**: 使用Docker卷持久化存储
4. **权限问题**: 脚本自动处理目录权限
5. **API Key缺失**: 部署时交互式提示输入

