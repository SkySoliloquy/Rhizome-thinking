"""简化的笔记导入脚本."""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.node_store import NodeStore
from rhizome.core.models import Node, Source, Processed

# 笔记文件映射
NOTES = [
    ("C:/Users/Administrator/Desktop/笔记整理/AI发展路径/自主AI路径与系统设计.md", 
     "AI发展路径", "自主AI路径与系统设计"),
    ("C:/Users/Administrator/Desktop/笔记整理/AI哲学与意识/自由意志与在线注意力记忆.md",
     "AI哲学与意识", "自由意志与在线注意力记忆"),
    ("C:/Users/Administrator/Desktop/笔记整理/AI理论架构/LLM性格解耦与训练目标.md",
     "AI理论架构", "LLM性格解耦与训练目标"),
    ("C:/Users/Administrator/Desktop/笔记整理/三层记忆框架/三层统一记忆框架.md",
     "三层记忆框架", "三层统一记忆框架"),
    ("C:/Users/Administrator/Desktop/笔记整理/个人思考与杂谈/信息过载杂念梳理.md",
     "个人思考与杂谈", "信息过载杂念梳理"),
    ("C:/Users/Administrator/Desktop/笔记整理/具身智能研究/具身智能哲学与学习能力.md",
     "具身智能研究", "具身智能哲学与学习能力"),
    ("C:/Users/Administrator/Desktop/笔记整理/时间感知理论/时间感知公式设想.md",
     "时间感知理论", "时间感知公式设想"),
    ("C:/Users/Administrator/Desktop/笔记整理/机器人风险思考/从蹦极到机器人风险.md",
     "机器人风险思考", "从蹦极到机器人风险"),
    ("C:/Users/Administrator/Desktop/笔记整理/自主Agent系统/流窜AI与OpenClaw改进.md",
     "自主Agent系统", "流窜AI与OpenClaw改进"),
]

def clear_all():
    """清空所有数据."""
    print("正在清空数据...")
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    
    # 删除节点文件
    nodes_dir = storage_dir / "nodes"
    if nodes_dir.exists():
        for f in nodes_dir.glob("*.md"):
            f.unlink()
    
    # 删除主题文件
    for d in ["node_themes", "themes"]:
        dir_path = storage_dir / "metadata" / d
        if dir_path.exists():
            for f in dir_path.glob("*.json"):
                f.unlink()
    
    # 重置索引
    for idx_file in ["nodes_index.json", "themes_index.json"]:
        path = storage_dir / "metadata" / idx_file
        if path.exists():
            with open(path, 'w') as f:
                json.dump({} if "themes" in idx_file else {"nodes": {}}, f)
    
    print("✅ 数据已清空")

def simple_import():
    """简单导入 - 不调用LLM，直接保存原始内容."""
    print("\n开始导入笔记...\n")
    node_store = NodeStore()
    
    success = 0
    failed = 0
    
    for filepath, category, title in NOTES:
        path = Path(filepath)
        if not path.exists():
            print(f"❌ 文件不存在: {filepath}")
            failed += 1
            continue
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"📄 {title} ({len(content)} 字)")
            
            # 创建简单节点（不使用LLM处理）
            node = Node(
                raw_input=content,
                source=Source(
                    type="original",
                    title=title,
                    location=category
                ),
                processed=Processed(
                    proposition=title,  # 使用文件名作为标题
                    open_questions=[]
                ),
                tags=["vague"]  # 默认标签
            )
            
            node_store.save(node)
            print(f"   ✅ 已保存: {node.id}")
            success += 1
            
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            failed += 1
    
    print(f"\n✅ 成功: {success}, ❌ 失败: {failed}")
    return success, failed

if __name__ == "__main__":
    print("=" * 60)
    print("Rhizome Thinking - 简化导入工具")
    print("=" * 60)
    
    clear_all()
    simple_import()
    
    print("\n" + "=" * 60)
    print("导入完成！访问 http://localhost:8084 查看")
    print("=" * 60)
