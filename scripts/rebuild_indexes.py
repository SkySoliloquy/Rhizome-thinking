"""重建节点和主题索引."""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.models import Node
from rhizome.core.theme_models import Theme

def rebuild_node_index():
    """重建节点索引."""
    print("正在重建节点索引...")
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    nodes_dir = storage_dir / "nodes"
    index_path = storage_dir / "metadata" / "nodes_index.json"
    
    index = {"nodes": {}, "last_updated": datetime.now().isoformat()}
    
    if not nodes_dir.exists():
        print("  节点目录不存在")
        return
    
    count = 0
    for node_file in nodes_dir.glob("*.md"):
        try:
            with open(node_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            node = Node.from_markdown(content)
            index["nodes"][node.id] = {
                "id": node.id,
                "timestamp": node.timestamp.isoformat(),
                "proposition": node.processed.proposition,
                "tags": node.tags,
                "link_count": len(node.links),
                "confirmed_link_count": sum(1 for link in node.links if link.confirmed),
            }
            count += 1
        except Exception as e:
            print(f"  解析失败 {node_file.name}: {e}")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ 重建完成，共 {count} 个节点")

def rebuild_theme_index():
    """重建主题索引."""
    print("\n正在重建主题索引...")
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    themes_dir = storage_dir / "themes"  # 正确的路径
    index_path = storage_dir / "metadata" / "themes_index.json"
    
    index = {"themes": {}, "node_themes": {}, "last_updated": datetime.now().isoformat()}
    
    if not themes_dir.exists():
        print(f"  主题目录不存在: {themes_dir}")
        return
    
    count = 0
    for theme_file in themes_dir.glob("*.json"):
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            theme = Theme(**data)
            index["themes"][theme.id] = {
                "id": theme.id,
                "summary": theme.summary[:100] if len(theme.summary) > 100 else theme.summary,
                "tag": theme.tag,
                "node_count": len(theme.node_ids),
                "updated_at": theme.updated_at.isoformat()
            }
            
            # 同时建立 node_id -> theme_ids 的映射
            for node_id in theme.node_ids:
                if node_id not in index["node_themes"]:
                    index["node_themes"][node_id] = []
                index["node_themes"][node_id].append(theme.id)
            
            count += 1
        except Exception as e:
            print(f"  解析失败 {theme_file.name}: {e}")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ 重建完成，共 {count} 个主题")

if __name__ == "__main__":
    print("=" * 60)
    print("重建索引工具")
    print("=" * 60)
    
    rebuild_node_index()
    rebuild_theme_index()
    
    print("\n" + "=" * 60)
    print("索引重建完成！")
    print("=" * 60)
