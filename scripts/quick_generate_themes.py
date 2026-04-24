"""快速为主题生成（使用节点标题）."""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.models import Node
from rhizome.core.theme_models import Theme, NodeTheme

def main():
    print("=" * 60)
    print("快速主题生成")
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
            print(f"❌ 解析失败 {node_file.name}: {e}")
    
    print(f"\n共 {len(nodes)} 个节点")
    print("使用节点标题作为主题...\n")
    
    # 为每个节点创建主题（使用节点标题）
    all_themes_data = []
    
    for node in nodes:
        # 使用节点标题作为主题
        all_themes_data.append({
            "node_id": node.id,
            "summary": node.processed.proposition,
            "tag": node.tags[0] if node.tags else "vague",
            "keywords": node.tags
        })
        
        # 额外提取一些关键词作为子主题
        # 从 open_questions 中提取主题
        for question in node.processed.open_questions[:2]:  # 最多2个问题作为子主题
            if len(question) > 10:
                # 简化问题作为主题
                short_q = question[:30] + "..." if len(question) > 30 else question
                all_themes_data.append({
                    "node_id": node.id,
                    "summary": short_q,
                    "tag": "needs_thinking",
                    "keywords": ["问题"]
                })
    
    print(f"生成 {len(all_themes_data)} 个原始主题")
    
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
    
    print(f"合并后: {len(summary_map)} 个主题")
    
    # 保存主题
    print("\n保存主题...")
    saved_count = 0
    
    for theme_info in summary_map.values():
        try:
            theme = Theme(
                summary=theme_info["summary"],
                tag=theme_info["tag"],
                node_ids=list(set(theme_info["node_ids"])),
                keywords=list(theme_info["keywords"])
            )
            theme_store.save_theme(theme)
            
            # 保存 node-theme 关联
            for node_id in theme.node_ids:
                nt = NodeTheme(
                    node_id=node_id,
                    theme_id=theme.id,
                    relevance_score=0.8
                )
                theme_store.save_node_themes(nt)
            
            saved_count += 1
            print(f"✅ {theme.summary[:50]}... ({len(theme.node_ids)} 个节点)")
        except Exception as e:
            print(f"⚠️ 保存失败: {e}")
    
    print(f"\n✅ 成功保存 {saved_count} 个主题")
    
    # 重建索引
    print("\n重建主题索引...")
    import subprocess
    subprocess.run(["python", "scripts/rebuild_indexes.py"], cwd=Path(__file__).parent.parent)
    
    print("\n" + "=" * 60)
    print("主题生成完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
