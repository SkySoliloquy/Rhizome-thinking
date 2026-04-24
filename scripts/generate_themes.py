"""为现有节点生成主题."""
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.config import settings
from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.models import Node
from rhizome.core.theme_models import Theme, NodeTheme

SYSTEM_PROMPT = """你是一个主题提取专家。从给定的笔记内容中提取1-3个核心主题。

每个主题应该：
1. 概括笔记的核心观点或概念
2. 适合作为知识聚合的锚点
3. 简洁明了（10-20字）

主题分类：
- definitive: 明确结论类主题
- inferred: 推断分析类主题
- vague: 模糊探索类主题
- needs_thinking: 待解决问题类主题
- cross-domain: 跨领域连接类主题

请以JSON格式返回：
{
  "themes": [
    {
      "summary": "主题摘要（10-20字）",
      "tag": "主题分类",
      "keywords": ["关键词1", "关键词2"]
    }
  ]
}"""

def extract_themes(content: str, title: str) -> list:
    """调用LLM提取主题."""
    url = f"{settings.minimax_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json"
    }
    
    user_prompt = f"""笔记标题: {title}

内容:
{content[:2000]}

请提取1-3个核心主题。"""
    
    payload = {
        "model": settings.minimax_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        
        content_text = data.get("reply", "")
        if not content_text and "choices" in data:
            content_text = data["choices"][0].get("message", {}).get("content", "")
        
        # 提取JSON
        if "```json" in content_text:
            json_str = content_text.split("```json")[1].split("```")[0].strip()
        elif "```" in content_text:
            json_str = content_text.split("```")[1].split("```")[0].strip()
        else:
            start = content_text.find("{")
            end = content_text.rfind("}")
            if start != -1 and end != -1:
                json_str = content_text[start:end+1]
            else:
                json_str = content_text.strip()
        
        result = json.loads(json_str)
        return result.get("themes", [])

def main():
    print("=" * 60)
    print("为主题提取")
    print("=" * 60)
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    nodes_dir = storage_dir / "nodes"
    
    node_store = NodeStore()
    theme_store = ThemeStore()
    
    # 加载所有节点
    nodes = []
    for node_file in nodes_dir.glob("*.md"):
        try:
            with open(node_file, 'r', encoding='utf-8') as f:
                content = f.read()
            node = Node.from_markdown(content)
            nodes.append(node)
        except Exception as e:
            print(f"❌ 解析失败: {e}")
    
    print(f"\n共 {len(nodes)} 个节点")
    print("开始提取主题...\n")
    
    all_themes_data = []
    
    for i, node in enumerate(nodes, 1):
        print(f"[{i}/{len(nodes)}] {node.processed.proposition[:40]}...")
        
        try:
            themes = extract_themes(node.raw_input, node.processed.proposition)
            print(f"   提取到 {len(themes)} 个主题")
            
            for theme in themes:
                all_themes_data.append({
                    "node_id": node.id,
                    "summary": theme.get("summary", ""),
                    "tag": theme.get("tag", "vague"),
                    "keywords": theme.get("keywords", [])
                })
                
        except Exception as e:
            print(f"   ❌ 提取失败: {e}")
    
    # 合并相同主题
    print("\n合并相似主题...")
    summary_map = {}
    for t in all_themes_data:
        key = (t["summary"], t["tag"])
        if key not in summary_map:
            summary_map[key] = {
                "summary": t["summary"],
                "tag": t["tag"],
                "node_ids": [],
                "keywords": set()
            }
        summary_map[key]["node_ids"].append(t["node_id"])
        summary_map[key]["keywords"].update(t.get("keywords", []))
    
    # 保存主题
    print(f"保存 {len(summary_map)} 个主题...")
    
    saved_count = 0
    for theme_info in summary_map.values():
        try:
            theme = Theme(
                summary=theme_info["summary"],
                tag=theme_info["tag"],
                node_ids=list(set(theme_info["node_ids"])),
                keywords=list(theme_info["keywords"])
            )
            saved = theme_store.save(theme)
            
            for node_id in theme.node_ids:
                nt = NodeTheme(node_id=node_id, theme_id=saved.id, relevance_score=0.8)
                theme_store.save_node_theme(nt)
            
            saved_count += 1
            print(f"✅ {theme.summary[:40]}...")
        except Exception as e:
            print(f"⚠️ 保存失败: {e}")
    
    print(f"\n✅ 共保存 {saved_count} 个主题")
    
    # 重建索引
    print("\n重建主题索引...")
    from scripts.rebuild_indexes import rebuild_theme_index
    rebuild_theme_index()
    
    print("\n" + "=" * 60)
    print("主题提取完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
