"""清空知识库并批量导入笔记."""
import os
import sys
import json
import shutil
import asyncio
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.retrieval.vector_store import get_vector_store
from rhizome.core.llm_processor import LLMProcessor
from rhizome.core.models import Node, Source, Processed

# 笔记文件映射
NOTES_MAPPING = {
    "AI发展路径/自主AI路径与系统设计.md": {
        "category": "AI发展路径",
        "title": "自主AI路径与系统设计"
    },
    "AI哲学与意识/自由意志与在线注意力记忆.md": {
        "category": "AI哲学与意识",
        "title": "自由意志与在线注意力记忆"
    },
    "AI理论架构/LLM性格解耦与训练目标.md": {
        "category": "AI理论架构",
        "title": "LLM性格解耦与训练目标"
    },
    "三层记忆框架/三层统一记忆框架.md": {
        "category": "三层记忆框架",
        "title": "三层统一记忆框架"
    },
    "个人思考与杂谈/信息过载杂念梳理.md": {
        "category": "个人思考与杂谈",
        "title": "信息过载杂念梳理"
    },
    "具身智能研究/具身智能哲学与学习能力.md": {
        "category": "具身智能研究",
        "title": "具身智能哲学与学习能力"
    },
    "时间感知理论/时间感知公式设想.md": {
        "category": "时间感知理论",
        "title": "时间感知公式设想"
    },
    "机器人风险思考/从蹦极到机器人风险.md": {
        "category": "机器人风险思考",
        "title": "从蹦极到机器人风险"
    },
    "自主Agent系统/流窜AI与OpenClaw改进.md": {
        "category": "自主Agent系统",
        "title": "流窜AI与OpenClaw改进"
    }
}

def clear_knowledge_base():
    """清空知识库的所有数据."""
    print("=" * 60)
    print("正在清空知识库...")
    print("=" * 60)
    
    # 1. 清空 ChromaDB 向量存储
    try:
        vector_store = get_vector_store()
        vector_store.clear()
        print("✅ 已清空向量存储")
    except Exception as e:
        print(f"⚠️ 清空向量存储时出错: {e}")
    
    # 2. 清空节点存储
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    
    # 清空 nodes 目录
    nodes_dir = storage_dir / "nodes"
    if nodes_dir.exists():
        count = len(list(nodes_dir.glob("*.md")))
        for file in nodes_dir.glob("*.md"):
            file.unlink()
        print(f"✅ 已清空节点文件 ({count} 个文件已删除)")
    
    # 清空 metadata/node_themes 目录
    node_themes_dir = storage_dir / "metadata" / "node_themes"
    if node_themes_dir.exists():
        for file in node_themes_dir.glob("*.json"):
            file.unlink()
        print("✅ 已清空节点主题关联")
    
    # 清空 themes 目录
    themes_dir = storage_dir / "metadata" / "themes"
    if themes_dir.exists():
        for file in themes_dir.glob("*.json"):
            file.unlink()
        print("✅ 已清空主题存储")
    
    # 3. 重置索引文件
    nodes_index = storage_dir / "metadata" / "nodes_index.json"
    if nodes_index.exists():
        with open(nodes_index, 'w', encoding='utf-8') as f:
            json.dump({"nodes": {}, "index": {}}, f, ensure_ascii=False, indent=2)
        print("✅ 已重置节点索引")
    
    themes_index = storage_dir / "metadata" / "themes_index.json"
    if themes_index.exists():
        with open(themes_index, 'w', encoding='utf-8') as f:
            json.dump({"themes": {}, "tag_index": {}}, f, ensure_ascii=False, indent=2)
        print("✅ 已重置主题索引")
    
    print("\n🎉 知识库清空完成!")
    print("=" * 60)

async def import_notes_async():
    """批量导入笔记 (异步版本)."""
    print("\n" + "=" * 60)
    print("开始批量导入笔记...")
    print("=" * 60)
    
    notes_base_path = Path("C:/Users/Administrator/Desktop/笔记整理")
    node_store = NodeStore()
    llm_processor = LLMProcessor()
    
    imported_count = 0
    failed_count = 0
    
    for note_path, info in NOTES_MAPPING.items():
        full_path = notes_base_path / note_path
        
        if not full_path.exists():
            print(f"❌ 文件不存在: {note_path}")
            failed_count += 1
            continue
        
        try:
            # 读取笔记内容
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"\n📄 正在导入: {info['title']}")
            print(f"   分类: {info['category']}")
            print(f"   字数: {len(content)} 字")
            
            # 创建来源信息
            source = Source(
                type="original",
                title=info['title'],
                location=info['category']
            )
            
            # 使用LLM处理器处理内容
            processed, tags, potential_links = await llm_processor.process(
                raw_input=content,
                source=source
            )
            
            # 创建节点
            node = Node(
                raw_input=content,
                source=source,
                processed=processed,
                tags=tags
            )
            
            # 保存节点
            stored_node = node_store.save(node)
            
            print(f"   ✅ 导入成功 - ID: {stored_node.id}")
            print(f"   📝 提取标题: {stored_node.processed.proposition}")
            print(f"   🏷️ 标签: {', '.join(stored_node.tags)}")
            if stored_node.processed.open_questions:
                print(f"   ❓ 问题 ({len(stored_node.processed.open_questions)} 个):")
                for q in stored_node.processed.open_questions[:3]:
                    print(f"      - {q[:60]}...")
            imported_count += 1
            
        except Exception as e:
            print(f"   ❌ 导入失败: {e}")
            import traceback
            traceback.print_exc()
            failed_count += 1
    
    print("\n" + "=" * 60)
    print("导入完成!")
    print(f"✅ 成功: {imported_count} 条")
    print(f"❌ 失败: {failed_count} 条")
    print("=" * 60)
    
    return imported_count, failed_count

def import_notes():
    """批量导入笔记 (同步包装)."""
    return asyncio.run(import_notes_async())

def main():
    """主函数."""
    print("\n" + "=" * 60)
    print("Rhizome Thinking - 知识库重置与导入工具")
    print("=" * 60 + "\n")
    
    # 确认操作 - 通过命令行参数或自动确认
    import sys
    auto_confirm = len(sys.argv) > 1 and sys.argv[1] == '--yes'
    if not auto_confirm:
        confirm = input("⚠️  此操作将清空所有现有数据! 是否继续? (yes/no): ")
        if confirm.lower() != "yes":
            print("操作已取消")
            return
    
    # 1. 清空知识库
    clear_knowledge_base()
    
    # 2. 导入笔记
    imported, failed = import_notes()
    
    # 3. 显示统计
    print("\n" + "=" * 60)
    print("操作完成!")
    print(f"导入笔记: {imported} 条")
    if failed > 0:
        print(f"失败: {failed} 条")
    print("\n现在可以访问 http://localhost:8084 查看导入的笔记")
    print("=" * 60)

if __name__ == "__main__":
    main()
