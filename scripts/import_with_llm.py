"""使用LLM处理批量导入笔记."""
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.llm_processor import LLMProcessor
from rhizome.core.theme_extractor import ThemeExtractor
from rhizome.core.models import Node, Source, Processed
from rhizome.retrieval.vector_store import get_vector_store

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
    print("=" * 60)
    print("正在清空知识库...")
    print("=" * 60)
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    
    # 清空向量存储
    try:
        vector_store = get_vector_store()
        vector_store.clear()
        print("✅ 已清空向量存储")
    except Exception as e:
        print(f"⚠️ 向量存储: {e}")
    
    # 删除节点文件
    nodes_dir = storage_dir / "nodes"
    if nodes_dir.exists():
        count = len(list(nodes_dir.glob("*.md")))
        for f in nodes_dir.glob("*.md"):
            f.unlink()
        print(f"✅ 已清空节点文件 ({count} 个)")
    
    # 删除主题文件
    themes_dir = storage_dir / "themes"
    if themes_dir.exists():
        count = len(list(themes_dir.glob("*.json")))
        for f in themes_dir.glob("*.json"):
            f.unlink()
        print(f"✅ 已清空主题文件 ({count} 个)")
    
    # 删除 node_themes
    node_themes_dir = storage_dir / "metadata" / "node_themes"
    if node_themes_dir.exists():
        for f in node_themes_dir.glob("*.json"):
            f.unlink()
        print("✅ 已清空节点主题关联")
    
    # 重置索引
    for idx_file in ["nodes_index.json", "themes_index.json"]:
        path = storage_dir / "metadata" / idx_file
        if path.exists():
            with open(path, 'w') as f:
                json.dump({} if "themes" in idx_file else {"nodes": {}}, f)
    print("✅ 已重置索引")
    
    print("\n🎉 知识库清空完成!")

async def process_and_import():
    """使用LLM处理并导入笔记."""
    print("\n" + "=" * 60)
    print("开始LLM处理并导入笔记...")
    print("=" * 60)
    
    node_store = NodeStore()
    theme_store = ThemeStore()
    llm_processor = LLMProcessor()
    theme_extractor = ThemeExtractor()
    vector_store = get_vector_store()
    
    success = 0
    failed = 0
    all_nodes = []
    
    # 第一步：处理所有节点
    print("\n【第一步】LLM处理笔记内容...")
    print("-" * 60)
    
    for i, (filepath, category, title) in enumerate(NOTES, 1):
        path = Path(filepath)
        if not path.exists():
            print(f"\n❌ [{i}/{len(NOTES)}] 文件不存在: {filepath}")
            failed += 1
            continue
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"\n[{i}/{len(NOTES)}] 📄 {title}")
            print(f"   字数: {len(content)}")
            
            # 创建来源
            source = Source(
                type="original",
                title=title,
                location=category
            )
            
            # 使用LLM处理内容
            print("   🤖 LLM处理中...")
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
            
            all_nodes.append(node)
            print(f"   ✅ 处理完成")
            print(f"   📝 标题: {processed.proposition}")
            print(f"   🏷️ 标签: {', '.join(tags)}")
            if processed.open_questions:
                print(f"   ❓ 问题: {len(processed.open_questions)} 个")
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 第二步：保存节点到存储
    print("\n" + "=" * 60)
    print("【第二步】保存节点到存储...")
    print("-" * 60)
    
    stored_nodes = []
    for node in all_nodes:
        try:
            stored = node_store.save(node)
            stored_nodes.append(stored)
            
            # 添加到向量存储
            vector_text = f"{stored.processed.proposition}\n{stored.raw_input[:500]}"
            vector_store.add_node(stored.id, vector_text, {
                "title": stored.processed.proposition,
                "tags": stored.tags
            })
            
            print(f"✅ 已保存: {stored.processed.proposition[:40]}...")
            success += 1
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            failed += 1
    
    # 第三步：提取主题
    print("\n" + "=" * 60)
    print("【第三步】提取主题...")
    print("-" * 60)
    
    all_themes_data = []
    for node in stored_nodes:
        try:
            themes = await theme_extractor.extract_themes_from_node(node)
            for theme_data in themes:
                all_themes_data.append({
                    "node_id": node.id,
                    **theme_data
                })
            print(f"✅ {node.processed.proposition[:30]}... -> {len(themes)} 个主题")
        except Exception as e:
            print(f"⚠️ 主题提取失败: {e}")
    
    # 第四步：合并相似主题并保存
    print("\n" + "=" * 60)
    print("【第四步】合并并保存主题...")
    print("-" * 60)
    
    # 简单合并：相同summary的主题合并
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
    from rhizome.core.theme_models import Theme, NodeTheme
    
    saved_count = 0
    for theme_info in summary_map.values():
        try:
            theme = Theme(
                summary=theme_info["summary"],
                tag=theme_info["tag"],
                node_ids=list(set(theme_info["node_ids"])),  # 去重
                keywords=list(theme_info["keywords"])
            )
            saved_theme = theme_store.save(theme)
            
            # 保存关联
            for node_id in theme.node_ids:
                node_theme = NodeTheme(
                    node_id=node_id,
                    theme_id=saved_theme.id,
                    relevance_score=0.8
                )
                theme_store.save_node_theme(node_theme)
            
            saved_count += 1
        except Exception as e:
            print(f"⚠️ 保存主题失败: {e}")
    
    print(f"✅ 共保存 {saved_count} 个主题")
    
    # 第五步：重建索引
    print("\n" + "=" * 60)
    print("【第五步】重建索引...")
    print("-" * 60)
    
    from scripts.rebuild_indexes import rebuild_node_index, rebuild_theme_index
    rebuild_node_index()
    rebuild_theme_index()
    
    print("\n" + "=" * 60)
    print("导入完成!")
    print(f"✅ 成功处理: {success} 条笔记")
    print(f"📝 提取标题: {success} 个")
    print(f"🏷️ 分配标签: {success} 个")
    print(f"🎨 生成主题: {saved_count} 个")
    if failed > 0:
        print(f"❌ 失败: {failed} 条")
    print("=" * 60)
    
    return success, failed, saved_count

def main():
    """主函数."""
    print("\n" + "=" * 70)
    print(" Rhizome Thinking - 完整LLM处理导入工具 ")
    print("=" * 70)
    print("\n此工具将:")
    print("  1. 清空现有知识库")
    print("  2. 使用LLM提取标题、标签、问题")
    print("  3. 自动提取主题并合并")
    print("  4. 重建索引\n")
    
    import sys
    auto_confirm = len(sys.argv) > 1 and sys.argv[1] == '--yes'
    if not auto_confirm:
        confirm = input("⚠️  此操作将清空所有现有数据! 是否继续? (yes/no): ")
        if confirm.lower() != "yes":
            print("操作已取消")
            return
    
    # 1. 清空
    clear_all()
    
    # 2. 导入
    success, failed, themes = asyncio.run(process_and_import())
    
    # 3. 完成
    print("\n" + "=" * 70)
    print("🎉 全部完成！")
    print(f"   笔记: {success} 条")
    print(f"   主题: {themes} 个")
    print("\n现在可以访问 http://localhost:8084 查看完整功能")
    print("=" * 70)

if __name__ == "__main__":
    main()
