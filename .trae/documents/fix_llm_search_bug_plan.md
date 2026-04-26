# LLM 检索 Bug 修复计划

## 项目概述

Rhizome Thinking 是一个基于 LLM 语义检索的知识库系统。前端 LLM 检索存在多个 bug，导致搜索功能无法按预期工作。

## 当前架构流程

```
前端 (app.js)
    ↓ POST /api/v1/query/themes/stream/fast
search_optimized.py (OptimizedStreamingSearch)
    ↓ 调用
search_optimizer.py (OptimizedSearch.search_with_timeout)
    ↓ 调用
llm_search.py (LLMSearchReranker.rerank_themes)
    ↓ HTTP POST
MiniMax API
```

## 已识别的问题

### 问题 1: 标签筛选条件未传递给 LLM（高优先级）

**位置**: `search_optimizer.py:267-281`

**问题描述**:
- 用户在前端选择标签筛选（如"明确结论"、"待思考问题"等）
- 这些筛选条件在 `_async_rerank` 方法中被硬编码为空列表
- LLM 看到的 Prompt 中筛选条件始终为"无额外筛选条件"

**代码证据**:
```python
# search_optimizer.py:278
filters = {"time_range": time_range, "tags": [], "search_mode": search_mode}
#                                          ^^^ 硬编码为空列表
```

**预期行为**:
- 用户选择的标签应该被传递给 LLM
- LLM 应该根据标签筛选候选主题
- Prompt 中应该显示正确的筛选条件

---

### 问题 2: 时间范围筛选未正确应用（中优先级）

**位置**: `search_optimizer.py:206-212`

**问题描述**:
- 主题数据 `Theme` 对象似乎没有 `timestamp` 或 `created_at` 字段用于时间筛选
- 当前代码仅从 `modifiers_data` 中提取 `time_range`，但没有实际过滤主题
- 时间范围筛选只在向量搜索中生效

**代码证据**:
```python
# search_optimizer.py:206-212
if selected_tags:
    filtered_themes = [t for t in all_themes if t.tag in selected_tags]
else:
    filtered_themes = all_themes
# 注意：这里没有 time_range 的过滤逻辑
```

**需要调查**:
- `Theme` 模型是否有时间字段？
- 时间筛选应该在哪个阶段应用？

---

### 问题 3: 搜索模式可能未正确生效（待验证）

**背景**: 根据 `search_fix_v2_summary.md`，之前已修复过缓存键未包含 `search_mode` 的问题

**需要验证**:
- 检查缓存键是否包含 `search_mode`
- 测试同一关键词在不同模式下的结果是否不同
- 确认 LLM Prompt 是否正确根据模式调整

**代码检查点**:
```python
# search_optimizer.py:46
key_string = f"{query.lower().strip()}|{tags_str}|{time_range}|{search_mode}"
# 看起来已包含 search_mode
```

---

### 问题 4: 主题结果排序可能不一致（低优先级）

**位置**: `search_optimized.py:151-168`

**问题描述**:
- LLM 已经返回了按相关性排序的主题
- 但在 `search_optimized.py` 中，结果被重新组织成分类
- 分类内的排序使用了 `match_score`，但跨分类的顺序可能被打乱

**需要确认**:
- 是否应该保持 LLM 的全局排序？
- 还是按分类分组更符合用户习惯？

---

## 修复方案

### 修复 1: 传递标签筛选条件给 LLM

**文件**: `search_optimizer.py`

**修改点**:
1. 修改 `_async_rerank` 方法签名，接收 `selected_tags` 参数
2. 将 `selected_tags` 传递给 `filters` 字典

```python
# 修改前
async def _async_rerank(
    self,
    anchor: str,
    themes: List[Theme],
    time_range: str,
    search_mode: str = "balanced"
) -> List[Tuple[Theme, float]]:
    def _rerank():
        filters = {"time_range": time_range, "tags": [], "search_mode": search_mode}
        return self.reranker.rerank_themes(anchor, themes, filters)

# 修改后
async def _async_rerank(
    self,
    anchor: str,
    themes: List[Theme],
    time_range: str,
    search_mode: str = "balanced",
    selected_tags: List[str] = None
) -> List[Tuple[Theme, float]]:
    def _rerank():
        filters = {
            "time_range": time_range, 
            "tags": selected_tags or [], 
            "search_mode": search_mode
        }
        return self.reranker.rerank_themes(anchor, themes, filters)
```

3. 更新调用点 `search_with_timeout:225`:

```python
# 修改前
matched_themes = await asyncio.wait_for(
    self._async_rerank(anchor, filtered_themes, time_range, search_mode),
    timeout=llm_timeout
)

# 修改后
matched_themes = await asyncio.wait_for(
    self._async_rerank(anchor, filtered_themes, time_range, search_mode, selected_tags),
    timeout=llm_timeout
)
```

---

### 修复 2: 修复时间范围筛选（需先调查）

**待调查问题**:
1. 查看 `Theme` 模型定义，确认是否有时间字段
2. 确定时间筛选的合理实现方式：
   - 选项 A: 在传递给 LLM 前，先按主题的时间属性过滤
   - 选项 B: 让 LLM 在 Prompt 中考虑时间条件
   - 选项 C: 时间筛选只影响向量搜索部分

**调查步骤**:
```bash
# 查看 Theme 模型
head -50 src/rhizome/core/theme_models.py
```

---

### 修复 3: 验证搜索模式缓存

**验证步骤**:
1. 检查缓存键是否包含 `search_mode`
2. 手动测试：
   - 搜索同一关键词，严格模式
   - 搜索同一关键词，探索模式
   - 确认结果数量不同

---

## 实施步骤

### 步骤 1: 修复标签筛选传递（预计 30 分钟）

- [ ] 修改 `_async_rerank` 方法
- [ ] 更新调用点
- [ ] 添加调试日志验证参数传递

### 步骤 2: 调查时间范围筛选（预计 30 分钟）

- [ ] 查看 Theme 模型字段
- [ ] 确定实现方案
- [ ] 如需修复，实施修复

### 步骤 3: 验证搜索模式（预计 20 分钟）

- [ ] 检查缓存键配置
- [ ] 手动测试验证

### 步骤 4: 集成测试（预计 30 分钟）

- [ ] 重启后端服务
- [ ] 清除浏览器缓存
- [ ] 测试完整搜索流程：
  - 带标签筛选的搜索
  - 带时间范围的搜索
  - 不同搜索模式
  - 验证 LLM Prompt 正确性（查看日志）

## 调试方法

### 启用详细日志

在 `search_optimizer.py` 中添加更多日志：

```python
logger.info(f"[LLM Search] Selected tags: {selected_tags}")
logger.info(f"[LLM Search] Time range: {time_range}")
logger.info(f"[LLM Search] Search mode: {search_mode}")
logger.info(f"[LLM Search] Filters passed to LLM: {filters}")
```

### 查看 LLM Prompt

在 `llm_search.py:121` 附近添加：

```python
logger.info(f"[LLM Reranker] Prompt:\n{prompt}")
```

### 测试 API

使用 curl 测试：

```bash
curl -X POST http://localhost:8000/api/v1/query/themes/stream/fast \
  -H "Content-Type: application/json" \
  -d '{
    "anchor": "人工智能",
    "modifiers": {
      "time_range": "all",
      "tags": ["definitive", "inferred"],
      "limit": 20,
      "search_mode": "balanced",
      "min_similarity": 0.3
    }
  }'
```

## 预期结果

修复后：

1. **标签筛选生效**: 用户选择的标签会传递给 LLM，Prompt 中显示正确的筛选条件
2. **时间范围生效**: 如果 Theme 有时间字段，应该被正确筛选
3. **搜索模式稳定**: 不同模式返回不同数量的结果
4. **整体体验改善**: 搜索结果更符合用户预期

## 风险与注意事项

1. **API 调用成本**: 修复后 LLM 调用次数不变，但需要确保 Prompt 长度合理
2. **缓存失效**: 修改缓存键逻辑可能导致短期缓存命中率下降
3. **向后兼容**: 确保现有搜索功能不受影响
