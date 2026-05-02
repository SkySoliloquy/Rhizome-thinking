#!/bin/bash
set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# 辅助函数
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 1. 检查是否在 git 仓库中
info "检查 Git 仓库..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    error "当前目录不是 Git 仓库，请在仓库根目录运行此脚本"
    exit 1
fi
success "Git 仓库检查通过"

# 2. 检查工作树是否干净
info "检查工作树状态..."
ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
info "当前分支: $ORIGINAL_BRANCH"

if ! git diff --quiet || ! git diff --cached --quiet; then
    warn "工作树不干净，存在未提交的更改"
    echo ""
    echo "未暂存的更改:"
    git diff --stat
    echo ""
    echo "已暂存的更改:"
    git diff --cached --stat
    echo ""
    read -p "是否继续发布? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        info "已取消发布"
        exit 0
    fi
    warn "继续发布，未提交的更改将不会被包含在 stable 分支中"
else
    success "工作树干净"
fi

# 3. 创建或切换到 stable 分支
info "准备 stable 分支..."
if git show-ref --verify --quiet refs/heads/stable; then
    info "stable 分支已存在，切换到该分支"
    git checkout stable
    # 清空当前分支内容（保留 .git）
    git rm -rf . > /dev/null 2>&1 || true
else
    info "创建新的 stable 分支"
    git checkout --orphan stable
    # 清空暂存区和工作区
    git rm -rf . > /dev/null 2>&1 || true
fi

# 4. 从原分支检出代码文件，排除开发产物
info "从 $ORIGINAL_BRANCH 检出代码文件..."

# 定义排除模式
EXCLUDE_PATTERNS=(
    "storage"
    ".env"
    ".env.*"
    "__pycache__"
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".git"
    ".gitignore"
    "*.log"
    "logs"
    ".vscode"
    ".idea"
    "*.swp"
    "*.swo"
    "*~"
    ".DS_Store"
    "Thumbs.db"
    "*.tmp"
    ".temp"
    "design-preview"
    ".trae"
    "venv"
    "ENV"
    "env"
    ".venv"
    "*.egg-info"
    ".eggs"
    "dist"
    "build"
    "develop-eggs"
    "downloads"
    "*.egg"
)

# 构建 git checkout 的排除参数
CHECKOUT_EXCLUDES=""
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    CHECKOUT_EXCLUDES="$CHECKOUT_EXCLUDES --exclude=$pattern"
done

# 从原分支检出所有文件（使用稀疏检出方式排除）
# 先获取原分支的所有文件列表
FILES=$(git ls-tree -r --name-only "$ORIGINAL_BRANCH" 2>/dev/null || true)

if [ -z "$FILES" ]; then
    error "无法从 $ORIGINAL_BRANCH 获取文件列表"
    git checkout "$ORIGINAL_BRANCH"
    exit 1
fi

# 逐个添加文件，跳过排除项
ADDED_COUNT=0
SKIPPED_COUNT=0

while IFS= read -r file; do
    # 检查是否匹配排除模式
    SKIP=false
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        # 使用通配符匹配
        case "$file" in
            $pattern|*/$pattern|$pattern/*|*/$pattern/*)
                SKIP=true
                break
                ;;
        esac
    done

    if [ "$SKIP" = true ]; then
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    # 检出单个文件
    if git show "$ORIGINAL_BRANCH:$file" > "$file" 2>/dev/null; then
        git add -- "$file" > /dev/null 2>&1
        ADDED_COUNT=$((ADDED_COUNT + 1))
    fi
done <<< "$FILES"

info "已添加 $ADDED_COUNT 个文件，跳过了 $SKIPPED_COUNT 个文件"

# 5. 检查是否有内容要提交
if git diff --cached --quiet; then
    warn "没有需要提交的更改，stable 分支内容未发生变化"
    info "切换回 $ORIGINAL_BRANCH 分支..."
    git checkout "$ORIGINAL_BRANCH"
    exit 0
fi

# 6. 提交
COMMIT_MSG="release: stable version $(date '+%Y-%m-%d %H:%M:%S')"
info "创建提交: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"
success "提交完成"

# 7. 推送到 origin
info "推送 stable 分支到 origin..."
if git push origin stable; then
    success "stable 分支已推送到 origin"
else
    error "推送失败"
    git checkout "$ORIGINAL_BRANCH"
    exit 1
fi

# 8. 切换回原分支
info "切换回 $ORIGINAL_BRANCH 分支..."
git checkout "$ORIGINAL_BRANCH"
success "已切换回 $ORIGINAL_BRANCH 分支"

echo ""
success "发布完成!"
echo ""
echo "发布摘要:"
echo "  原分支:    $ORIGINAL_BRANCH"
echo "  目标分支:  stable"
echo "  提交信息:  $COMMIT_MSG"
echo "  添加文件:  $ADDED_COUNT"
echo "  跳过文件:  $SKIPPED_COUNT"
