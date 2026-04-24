"""为现有笔记提取主题."""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.theme_extractor import ThemeExtractor
from rhizome.core.models import Node
from rhizome.core.theme_models import Theme, NodeTheme

async def extract_themes_for_all_nodes():
    """为所有节点提取主题."""
    print("=" * 60)
    print("开始为主题提取...")
    print("=" * 60)
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    nodes_dir = storage_dir / "nodes"
    
    node_store = NodeStore()
    theme_store = ThemeStore()
    extractor = ThemeExtractor()
    
    if not nodes_dir.exists():
        print("节点目录不存在")
        return
    
    # 加载所有节点
    nodes = []
    for node_file in nodes_dir.glob("*.md"):
        try:
            with open(node_file, 'r', encoding='utf-8') as f:
                content = f.read()
            node = Node.from_markdown(content)
            nodes.append(node)
        except Exception as e:
            print(f"  解析失败 {node_file.name}: {e}")
    
    print(f"\n共加载 {len(nodes)} 个节点")
    
    # 清空现有主题
    themes_dir = storage_dir / "themes"
    if themes_dir.exists():
        for f in themes_dir.glob("*.json"):
            f.unlink()
        print("✅ 已清空现有主题")
    
    # 为每个节点提取主题
    all_extracted_themes = []
    
    for i, node in enumerate(nodes, 1):
        print(f"\n[{i}/{len(nodes)}] 处理节点: {node.processed.proposition[:40]}...")
        
        try:
            # 提取主题
            themes_data = await extractor.extract_themes_from_node(node)
            
            for theme_data in themes_data:
                all_extracted_themes.append({
                    "node_id": node.id,
                    "summary": theme_data["summary"],
                    "tag": theme_data["tag"],
                    "keywords": theme_data.get("keywords", [])
                })
            
            print(f"   ✅ 提取 {len(themes_data)} 个主题")
            
        except Exception as e:
            print(f"   ❌ 提取失败: {e}")
    
    print(f"\n共提取 {len(all_extracted_themes)} 个原始主题")
    
    # 合并相似主题
    print("\n正在合并相似主题...")
    merged_themes = await _merge_similar_themes(all_extracted_themes, extractor)
    print(f"合并后剩余 {len(merged_themes)} 个主题")
    
    # 保存主题
    print("\n正在保存主题...")
    theme_id_map = {}  # original_summary -> theme_id
    
    for theme_info in merged_themes:
        try:
            theme = Theme(
                summary=theme_info["summary"],
                tag=theme_info["tag"],
                node_ids=theme_info["node_ids"],
                keywords=theme_info.get("keywords", [])
            )
            
            saved_theme = theme_store.save(theme)
            theme_id_map[theme_info["summary"]] = saved_theme.id
            
            # 保存 node-theme 关联
            for node_id in theme_info["node_ids"]:
                node_theme = NodeTheme(
                    node_id=node_id,
                    theme_id=saved_theme.id,
                    relevance_score=0.8
                )
                theme_store.save_node_theme(node_theme)
            
        except Exception as e:
            print(f"   保存失败: {e}")
    
    print(f"\n✅ 成功保存 {len(merged_themes)} 个主题")
    
    # 重建索引
    print("\n重建主题索引...")
    from scripts.rebuild_indexes import rebuild_theme_index
    rebuild_theme_index()
    
    print("\n" + "=" * 60)
    print("主题提取完成！")
    print("=" * 60)

async def _merge_similar_themes(themes, extractor):
    """合并相似主题."""
    if not themes:
        return []
    
    # 按标签分组
    tag_groups = {}
    for t in themes:
        tag = t["tag"]
        if tag not in tag_groups:
            tag_groups[tag] = []
        tag_groups[tag].append(t)
    
    merged = []
    
    for tag, group in tag_groups.items():
        print(f"  处理标签 '{tag}': {len(group)} 个主题")
        
        # 简单合并：相同summary的合并
        summary_map = {}
        for t in group:
            summary = t["summary"]
            if summary not in summary_map:
                summary_map[summary] = {
                    "summary": summary,
                    "tag": tag,
                    "node_ids": [],
                    "keywords": set()
                }
            summary_map[summary]["node_ids"].append(t["node_id"])
            summary_map[summary]["keywords"].update(t.get("keywords", []))
        
        # 转换为列表
        for item in summary_map.values():
            item["keywords"] = list(item["keywords"])
            merged.append(item)
    
    return merged

if __name__ == "__main__":
    asyncio.run(extract_themes_for_all_nodes())
