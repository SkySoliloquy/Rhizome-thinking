"""同步方式使用LLM导入笔记."""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
from rhizome.config import settings
from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.models import Node, Source, Processed
from rhizome.core.theme_models import Theme, NodeTheme
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

SYSTEM_PROMPT = """你是一个个人知识库的智能助手。将用户输入整理成结构化知识节点。

核心原则：
1. 标题必须极其简洁，5-10个字概括核心内容
2. 从用户输入中识别并提取用户明确提出的问题
3. 分配准确的内容性质标签

标题生成规则（非常重要）：
- 必须简短精炼，5-10个字，像新闻标题一样
- 示例好标题："记忆的本质"、"AI意识探讨"、"注意力机制"
- 不要加"关于"、"论"等前缀，直接给出核心概念
- 技术内容用专业术语

内容性质标签：
- definitive: 有依据的明确结论
- inferred: 基于已有内容推断的结论
- vague: 模糊感知，尚未能清晰表达
- needs_thinking: 明确需要进一步思考的问题
- cross-domain: 跨越多个主题领域的想法

请以JSON格式返回：
{
  "title": "5-10字的简短标题",
  "questions": ["用户提出的问题"],
  "tags": ["标签名"]
}"""

def call_llm(content: str, title: str, category: str) -> dict:
    """调用MiniMax API处理内容."""
    url = f"{settings.minimax_base_url}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json"
    }
    
    user_prompt = f"""请处理以下笔记内容：

来源：{category} / {title}

内容：
{content[:3000]}

请提取标题（5-10字）、识别用户提出的问题、分配标签。"""
    
    payload = {
        "model": settings.minimax_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }
    
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # 解析响应
        content_text = data.get("reply", "")
        if not content_text and "choices" in data:
            content_text = data["choices"][0].get("message", {}).get("content", "")
        
        # 提取JSON
        if "```json" in content_text:
            json_str = content_text.split("```json")[1].split("```")[0].strip()
        elif "```" in content_text:
            json_str = content_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = content_text.strip()
        
        result = json.loads(json_str)
        return result

def clear_all():
    """清空所有数据."""
    print("=" * 60)
    print("正在清空知识库...")
    print("=" * 60)
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    
    try:
        vector_store = get_vector_store()
        vector_store.clear()
        print("✅ 已清空向量存储")
    except:
        pass
    
    for dir_name in ["nodes", "themes"]:
        dir_path = storage_dir / dir_name
        if dir_path.exists():
            for f in dir_path.glob("*"):
                f.unlink()
    
    node_themes_dir = storage_dir / "metadata" / "node_themes"
    if node_themes_dir.exists():
        for f in node_themes_dir.glob("*.json"):
            f.unlink()
    
    for idx_file in ["nodes_index.json", "themes_index.json"]:
        path = storage_dir / "metadata" / idx_file
        if path.exists():
            with open(path, 'w') as f:
                json.dump({} if "themes" in idx_file else {"nodes": {}}, f)
    
    print("✅ 已清空所有数据")

def import_notes():
    """导入笔记."""
    print("\n" + "=" * 60)
    print("开始LLM处理并导入...")
    print("=" * 60)
    
    node_store = NodeStore()
    vector_store = get_vector_store()
    
    success = 0
    failed = 0
    all_nodes = []
    
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
            
            # 调用LLM处理
            print("   🤖 LLM处理中...", end=" ", flush=True)
            start = time.time()
            llm_result = call_llm(content, title, category)
            elapsed = time.time() - start
            print(f"完成 ({elapsed:.1f}s)")
            
            # 创建节点
            processed = Processed(
                proposition=llm_result.get("title", title),
                open_questions=llm_result.get("questions", [])
            )
            
            # 验证标签
            valid_tags = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
            tags = [t for t in llm_result.get("tags", []) if t in valid_tags]
            if not tags:
                tags = ["vague"]
            
            node = Node(
                raw_input=content,
                source=Source(type="original", title=title, location=category),
                processed=processed,
                tags=tags
            )
            
            # 保存
            stored = node_store.save(node)
            
            # 添加到向量存储
            vector_text = f"{processed.proposition}\n{content[:500]}"
            vector_store.add_node(stored.id, vector_text, {
                "title": processed.proposition,
                "tags": tags
            })
            
            all_nodes.append(stored)
            success += 1
            
            print(f"   ✅ 已保存")
            print(f"   📝 标题: {processed.proposition}")
            print(f"   🏷️ 标签: {', '.join(tags)}")
            if processed.open_questions:
                print(f"   ❓ 问题: {len(processed.open_questions)} 个")
            
        except Exception as e:
            print(f"\n   ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 提取主题
    print("\n" + "=" * 60)
    print("提取主题...")
    print("=" * 60)
    
    theme_store = ThemeStore()
    all_themes = []
    
    for node in all_nodes:
        # 简单主题提取：基于标题和标签
        theme_summary = node.processed.proposition
        theme_tag = node.tags[0] if node.tags else "vague"
        
        all_themes.append({
            "node_id": node.id,
            "summary": theme_summary,
            "tag": theme_tag,
            "keywords": []
        })
    
    # 合并相同主题
    summary_map = {}
    for t in all_themes:
        key = (t["summary"], t["tag"])
        if key not in summary_map:
            summary_map[key] = {
                "summary": t["summary"],
                "tag": t["tag"],
                "node_ids": [],
                "keywords": set()
            }
        summary_map[key]["node_ids"].append(t["node_id"])
    
    # 保存主题
    saved_themes = 0
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
            
            saved_themes += 1
        except:
            pass
    
    print(f"✅ 保存 {saved_themes} 个主题")
    
    # 重建索引
    print("\n" + "=" * 60)
    print("重建索引...")
    print("=" * 60)
    
    from scripts.rebuild_indexes import rebuild_node_index, rebuild_theme_index
    rebuild_node_index()
    rebuild_theme_index()
    
    print("\n" + "=" * 60)
    print("导入完成!")
    print(f"✅ 笔记: {success} 条")
    print(f"🎨 主题: {saved_themes} 个")
    if failed > 0:
        print(f"❌ 失败: {failed} 条")
    print("=" * 60)

def main():
    print("\n" + "=" * 70)
    print(" Rhizome Thinking - LLM同步导入工具 ")
    print("=" * 70)
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--yes':
        pass
    else:
        confirm = input("\n⚠️  此操作将清空所有数据! 是否继续? (yes/no): ")
        if confirm.lower() != "yes":
            print("操作已取消")
            return
    
    clear_all()
    import_notes()
    
    print("\n" + "=" * 70)
    print("🎉 全部完成！访问 http://localhost:8084")
    print("=" * 70)

if __name__ == "__main__":
    main()
