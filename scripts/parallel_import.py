"""并行LLM导入笔记，带进度条."""
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
1. 标题必须极其简洁，5-10个字概括核心内容，像新闻标题一样
2. 从用户输入中识别并提取用户明确提出的问题
3. 分配准确的内容性质标签

标题生成规则：
- 必须简短精炼，5-10个字
- 示例："记忆的本质"、"AI意识探讨"、"注意力机制"
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
  "questions": ["用户提出的问题，如果没有则返回空数组"],
  "tags": ["definitive", "inferred", "vague", "needs_thinking", "cross-domain" 中的1-3个"]
}"""

class ProgressBar:
    """进度条显示."""
    def __init__(self, total, desc="进度"):
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
        
    def update(self, n=1):
        self.current += n
        self._print()
        
    def _print(self):
        percent = self.current / self.total * 100
        elapsed = time.time() - self.start_time
        avg_time = elapsed / self.current if self.current > 0 else 0
        eta = avg_time * (self.total - self.current)
        
        bar_length = 40
        filled = int(bar_length * self.current / self.total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"\r{self.desc}: [{bar}] {self.current}/{self.total} ({percent:.1f}%) | 已用: {elapsed:.0f}s | 预计剩余: {eta:.0f}s", end="", flush=True)
        
    def finish(self):
        self.current = self.total
        self._print()
        print()

def call_llm_sync(content: str, title: str, category: str) -> dict:
    """同步调用LLM（用于线程池）."""
    url = f"{settings.minimax_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json"
    }
    
    user_prompt = f"""请处理以下笔记内容：

来源：{category} / {title}

内容：
{content[:2500]}

请提取标题（5-10字）、识别用户提出的问题、分配标签。"""
    
    payload = {
        "model": settings.minimax_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1500
    }
    
    with httpx.Client(timeout=180.0) as client:
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
            # 尝试直接解析
            start = content_text.find("{")
            end = content_text.rfind("}")
            if start != -1 and end != -1:
                json_str = content_text[start:end+1]
            else:
                json_str = content_text.strip()
        
        result = json.loads(json_str)
        return result

def clear_all():
    """清空所有数据."""
    print("=" * 70)
    print("正在清空知识库...")
    print("=" * 70)
    
    storage_dir = Path(r"d:\Project\Rhizome_thinking\Rhizome-thinking\storage")
    
    # 清空向量存储
    try:
        vector_store = get_vector_store()
        vector_store.clear()
        print("✅ 已清空向量存储")
    except Exception as e:
        print(f"⚠️ 向量存储: {e}")
    
    # 清空文件
    for dir_name in ["nodes", "themes"]:
        dir_path = storage_dir / dir_name
        if dir_path.exists():
            count = len(list(dir_path.glob("*")))
            for f in dir_path.glob("*"):
                f.unlink()
            print(f"✅ 已清空 {dir_name} ({count} 个文件)")
    
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

def process_note(args):
    """处理单个笔记（用于并行）."""
    idx, filepath, category, title = args
    path = Path(filepath)
    
    if not path.exists():
        return (idx, "error", f"文件不存在: {filepath}", None)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 调用LLM
        llm_result = call_llm_sync(content, title, category)
        
        return (idx, "success", {
            "title": title,
            "category": category,
            "content": content,
            "llm_result": llm_result
        }, None)
        
    except Exception as e:
        return (idx, "error", str(e), None)

def import_parallel():
    """并行导入笔记."""
    print("\n" + "=" * 70)
    print("开始并行LLM导入...")
    print("=" * 70)
    print(f"共 {len(NOTES)} 个笔记，使用并行处理\n")
    
    # 第一步：并行LLM处理
    print("【第一步】并行LLM处理笔记...")
    print("-" * 70)
    
    results = [None] * len(NOTES)
    progress = ProgressBar(len(NOTES), "LLM处理")
    
    # 使用线程池并行处理（最大3个并发）
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_note, (i, filepath, category, title)): i 
            for i, (filepath, category, title) in enumerate(NOTES)
        }
        
        for future in as_completed(futures):
            idx, status, data, error = future.result()
            results[idx] = (status, data, error)
            progress.update(1)
    
    progress.finish()
    
    # 统计结果
    success_count = sum(1 for r in results if r[0] == "success")
    error_count = len(results) - success_count
    
    print(f"\n✅ LLM处理完成: {success_count} 成功, {error_count} 失败")
    
    if error_count > 0:
        print("\n失败详情:")
        for i, (status, data, error) in enumerate(results):
            if status == "error":
                print(f"  [{i+1}] {NOTES[i][2]}: {data}")
    
    # 第二步：保存到存储
    print("\n" + "=" * 70)
    print("【第二步】保存到存储...")
    print("-" * 70)
    
    node_store = NodeStore()
    vector_store = get_vector_store()
    
    saved_nodes = []
    save_progress = ProgressBar(success_count, "保存节点")
    
    for i, (status, data, error) in enumerate(results):
        if status != "success":
            continue
            
        try:
            llm_result = data["llm_result"]
            content = data["content"]
            title = data["title"]
            category = data["category"]
            
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
            
            saved_nodes.append(stored)
            save_progress.update(1)
            
        except Exception as e:
            print(f"\n❌ 保存失败 [{i+1}]: {e}")
    
    save_progress.finish()
    print(f"✅ 成功保存 {len(saved_nodes)} 个节点")
    
    # 第三步：提取主题
    print("\n" + "=" * 70)
    print("【第三步】提取并保存主题...")
    print("-" * 70)
    
    theme_store = ThemeStore()
    all_themes = []
    
    for node in saved_nodes:
        all_themes.append({
            "node_id": node.id,
            "summary": node.processed.proposition,
            "tag": node.tags[0] if node.tags else "vague",
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
    
    # 第四步：重建索引
    print("\n" + "=" * 70)
    print("【第四步】重建索引...")
    print("-" * 70)
    
    from scripts.rebuild_indexes import rebuild_node_index, rebuild_theme_index
    rebuild_node_index()
    rebuild_theme_index()
    
    # 完成统计
    print("\n" + "=" * 70)
    print("🎉 导入完成!")
    print("=" * 70)
    print(f"📄 笔记: {len(saved_nodes)} 条")
    print(f"🎨 主题: {saved_themes} 个")
    print(f"⏱️  总用时: {time.time() - start_time:.0f} 秒")
    print("=" * 70)

def main():
    global start_time
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print(" Rhizome Thinking - 并行LLM导入工具 ")
    print("=" * 70)
    print("\n配置：")
    print(f"  - 笔记数量: {len(NOTES)}")
    print(f"  - 并发数: 3")
    print(f"  - API: MiniMax")
    print()
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--yes':
        pass
    else:
        confirm = input("⚠️  此操作将清空所有数据! 是否继续? (yes/no): ")
        if confirm.lower() != "yes":
            print("操作已取消")
            return
    
    clear_all()
    import_parallel()
    
    print("\n" + "=" * 70)
    print("✅ 全部完成！访问 http://localhost:8084")
    print("=" * 70)

if __name__ == "__main__":
    main()
