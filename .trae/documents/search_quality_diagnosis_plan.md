# 搜索质量问题诊断报告（已更新）

## 问题描述
项目搜索功能出现严重质量下降：
- 高相关度阈值时完全找不到内容
- 即使查询文字非常明确也不行
- 降低相关度阈值后会突然检索到几乎所有内容
- 不同相关度阈值下的表现差异巨大

**重要说明**：系统主要使用 **LLM 检索**（智能语义匹配），向量检索仅作为备用。用户反馈的问题与 LLM 检索逻辑相关。

---

## 根本原因分析

### 问题核心：LLM 检索结果被相似度阈值错误过滤

**位置1** - LLM 分数分配逻辑：`llm_search.py:168`

```python
# 根据位置分配分数，越靠前分数越高
score = max(0.9 - (len(ranked_themes) * 0.05), 0.3)
```

这导致 LLM 返回的分数是**基于排名的固定递减值**，而非真实语义相似度：

| LLM 排名 | 分配分数 | 能否通过 0.8 阈值 | 能否通过 0.5 阈值 | 能否通过 0.3 阈值 |
|---------|---------|-----------------|-----------------|-----------------|
| 1       | 0.90    | ✅               | ✅               | ✅               |
| 2       | 0.85    | ✅               | ✅               | ✅               |
| 3       | 0.80    | ✅               | ✅               | ✅               |
| 4       | 0.75    | ❌ **被过滤**     | ✅               | ✅               |
| 5       | 0.70    | ❌ **被过滤**     | ✅               | ✅               |
| ...     | ...     | ❌               | ✅               | ✅               |
| 10      | 0.45    | ❌               | ✅               | ✅               |
| 11      | 0.30    | ❌               | ❌ **被过滤**     | ✅               |
| 12+     | 0.30    | ❌               | ❌               | ✅               |
| 未排名   | 0.00    | ❌               | ❌               | ❌ **被过滤**     |

**位置2** - 错误过滤逻辑：`search_optimized.py:130`

```python
# Filter by minimum similarity
matched_themes = [(t, s) for t, s in matched_themes if s >= min_similarity]
```

### 为什么这是错误的？

1. **LLM 已经做了相关性判断**：LLM 只返回真正相关的主题编号，未返回的就是不相关的
2. **LLM 排名不应被阈值二次过滤**：排名第4的主题（分数0.75）可能比排名第1的主题（分数0.9）在某些场景下同样有用
3. **阈值断崖效应**：当阈值从0.79降到0.75，结果数量会从3个突然变成4个，差异巨大

### 用户描述的现现象解释

**现象1**："高相关度完全找不到内容"
- 原因：设置 0.8 阈值时，只有 LLM 排名前3能通过
- 如果 LLM 判断只有2个相关主题，结果就是空或很少

**现象2**："即使查询文字非常明确也不行"
- 原因：LLM 分数与查询明确程度无关，只与排名位置有关

**现象3**："降低到一定程度就会突然几乎全部都检索到"
- 原因：当阈值降到 0.3，所有 LLM 排名的主题（最多约12个）都通过了
- 从3个突然变成12个，用户感知是"几乎全部"

---

## 修复方案

### 方案1：移除 LLM 结果的相似度过滤（推荐）

**文件**：`search_optimized.py:129-131`

**原理**：LLM 已经筛选过相关主题，不应该再用阈值过滤

```python
# 修改前
# Filter by minimum similarity
matched_themes = [(t, s) for t, s in matched_themes if s >= min_similarity]
matched_themes = matched_themes[:limit]

# 修改后 - LLM 结果不进行相似度过滤，只限制数量
# LLM 已经返回了相关主题，未返回的就是不相关的
# 按 LLM 排名顺序取前 limit 个
matched_themes = matched_themes[:limit]
```

### 方案2：改进 LLM 分数计算

**文件**：`llm_search.py:145-184`

**原理**：让 LLM 为每个主题分配真实的相关性分数（高/中/低），而非基于排名的递减值

**修改 LLM Prompt**（第67-77行）：
```python
# 修改前
"只返回JSON格式：{\"ranking\": [编号1, 编号2, ...]}"

# 修改后 - 要求 LLM 为每个主题打分
"""请为每个相关主题分配相关性分数：
- 0.9-1.0: 极高相关（直接回答搜索问题）
- 0.7-0.89: 高度相关（紧密相关的内容）
- 0.5-0.69: 中度相关（有一定关联）
- 0.3-0.49: 低度相关（背景信息）
- 不相关主题不要包含

只返回JSON格式：{\"ranking\": [{\"id\": 编号, \"score\": 分数}, ...]}"""
```

**修改分数解析逻辑**：
```python
def _parse_ranking(self, content: str, themes: list[Theme]) -> list[tuple[Theme, float]]:
    # ... 解析 JSON ...
    
    # 修改后 - 直接使用 LLM 提供的分数
    for item in ranking:
        theme_idx = int(item.get("id"))
        score = float(item.get("score", 0.5))
        if theme_idx in theme_by_index:
            theme = theme_by_index[theme_idx]
            ranked_themes.append((theme, score))
    
    # 未排名的主题不返回（LLM 已判断为不相关）
    return ranked_themes
```

### 方案3：区分 LLM 检索和向量检索的阈值处理

**文件**：`search_optimized.py:68-130`

**原理**：LLM 检索和向量检索使用不同的过滤策略

```python
# 在 search 方法中区分处理方式
if cache_status in ["miss", "hit"]:  # LLM 检索成功
    # LLM 已经筛选过，只取前 limit 个，不过滤
    matched_themes = matched_themes[:limit]
else:  # 传统搜索或向量搜索
    # 使用相似度阈值过滤
    matched_themes = [(t, s) for t, s in matched_themes if s >= min_similarity]
    matched_themes = matched_themes[:limit]
```

### 方案4：前端优化 - 区分 LLM 和向量模式

**文件**：`app.js`

**原理**：让用户知道当前是 LLM 模式还是向量模式，调整阈值说明

```javascript
// 添加模式切换或提示
const searchMode = 'llm'; // 或 'vector'

if (searchMode === 'llm') {
    // LLM 模式下，阈值只对向量补充结果有效
    similaritySlider.disabled = true;
    similarityHelpText = "LLM 模式下，相似度阈值仅影响向量补充结果";
} else {
    similaritySlider.disabled = false;
    similarityHelpText = "向量模式下，相似度阈值影响所有结果";
}
```

---

## 推荐修复优先级

| 优先级 | 方案 | 影响 | 工作量 |
|-------|------|------|--------|
| P0 | 方案1：移除 LLM 过滤 | 立即解决高阈值无结果问题 | 2行代码 |
| P1 | 方案2：改进 LLM 分数 | 提供更好的相关性区分 | 修改 prompt + 解析逻辑 |
| P2 | 方案3：区分处理 | 更精细的控制逻辑 | 中等 |
| P3 | 方案4：前端优化 | 更好的用户体验 | 前端修改 |

---

## 验证方法

修复后验证步骤：

1. **使用相同查询词，设置 0.8 阈值测试**
   - 预期：LLM 返回的相关主题都能显示（不再被过滤）

2. **对比不同阈值的结果数量**
   - 0.3, 0.5, 0.8 阈值的结果数量应该相近（只有向量补充部分有差异）

3. **检查 LLM 排名完整性**
   - LLM 判断为相关的主题应该全部显示
   - 未排名的主题应该不显示

---

## 总结

**真正的问题**：LLM 检索结果被基于排名的固定分数错误地过滤了。

- 高阈值（0.8）只允许前3个结果通过
- 低阈值（0.3）允许前12个结果通过
- 用户感知是"从几乎没有突然变成几乎全部"

**最简修复**：移除 `search_optimized.py:130` 的相似度过滤逻辑，让 LLM 的结果直接展示。
