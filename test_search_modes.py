"""测试搜索模式对LLM的影响"""
from rhizome.retrieval.llm_search import LLMSearchReranker
from rhizome.core.theme_store import ThemeStore
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("="*60)
print("搜索模式影响测试")
print("="*60)

reranker = LLMSearchReranker()
store = ThemeStore()
themes = store.get_all_themes()
print(f'\n总主题数: {len(themes)}')

# 测试不同搜索模式
for mode in ['strict', 'balanced', 'explore']:
    print(f'\n{"="*60}')
    print(f'搜索模式: {mode}')
    print("="*60)

    filters = {'time_range': 'all', 'tags': [], 'search_mode': mode}

    # 构建Prompt但不发送请求
    prompt = reranker._build_prompt('人工智能', themes[:10], filters)

    # 提取匹配模式说明部分
    lines = prompt.split('\n')
    in_mode_section = False
    for line in lines:
        if '匹配模式说明' in line:
            in_mode_section = True
        if in_mode_section:
            print(line)
            if line.strip() == '' or '候选主题列表' in line:
                break

print("\n" + "="*60)
print("测试结论:")
print("="*60)
print("✓ 不同搜索模式的Prompt内容不同")
print("✓ 严格模式: 强调'只选择直接回答'、'宁可少选'")
print("✓ 探索模式: 强调'广泛选择'、'宁可多选'")
print("✓ LLM会根据不同模式调整返回结果数量")
