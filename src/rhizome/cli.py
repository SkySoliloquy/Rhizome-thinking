"""Command-line interface for Rhizome Thinking."""

# Fix Windows encoding BEFORE any rich imports
import sys
if sys.platform == 'win32':
    import io
    import os
    # Reconfigure stdout/stderr to UTF-8 early, before any library imports
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from rhizome.config import settings
from rhizome.core.llm_processor import LLMProcessor, MockLLMProcessor
from rhizome.core.models import Node, Source
from rhizome.core.node_store import NodeStore

console = Console(force_terminal=True)

# 关系类型中文映射
RELATION_TYPE_CN = {
    "support": "支持",
    "contradict": "矛盾",
    "extend": "延伸",
    "source": "来源",
    "analogy": "类比",
    "related": "相关"
}


def get_store() -> NodeStore:
    """Get initialized node store."""
    return NodeStore()


def get_processor(use_mock: bool = False) -> LLMProcessor:
    """Get LLM processor instance."""
    if use_mock:
        return MockLLMProcessor()
    return LLMProcessor()


@click.group()
@click.option("--debug/--no-debug", default=False, help="启用调试模式")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Rhizome Thinking - 基于标签连接的个人知识库"""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """初始化存储目录"""
    try:
        settings.ensure_directories()
        console.print("[green]✓[/green] 存储目录初始化成功！")
        console.print(f"  节点目录: {settings.nodes_dir}")
        console.print(f"  元数据目录: {settings.metadata_dir}")
    except Exception as e:
        console.print(f"[red]✗[/red] 初始化失败: {e}")
        sys.exit(1)


def _interactive_link_confirm(node_id: str, potential_links: list, existing_nodes: list) -> None:
    """交互式确认潜在链接"""
    if not potential_links:
        return
    
    # 检查是否为交互式终端
    import os
    if not sys.stdin.isatty() or os.environ.get('CI') or os.environ.get('NON_INTERACTIVE'):
        return
    
    store = get_store()
    confirmed_count = 0
    
    console.print()
    console.print("[bold cyan]🔗 链接确认[/bold cyan]")
    console.print("[dim]输入数字选择要确认的链接，多个用逗号分隔，'a'确认全部，直接回车跳过[/dim]")
    console.print()
    
    # 显示所有潜在链接
    for i, link in enumerate(potential_links, 1):
        relation = RELATION_TYPE_CN.get(link.get('relation_type', 'related'), link.get('relation_type', '相关'))
        summary = link.get('target_node_summary', '未知')[:45]
        reasoning = link.get('reasoning', '')[:55]
        
        console.print(f"  [cyan]{i}.[/cyan] [{relation}] {summary}...")
        console.print(f"     [dim]理由: {reasoning}...[/dim]")
        console.print()
    
    # 获取用户输入 - 使用普通 input 避免与 Rich status 冲突
    console.print("[bold yellow]请输入选择:[/bold yellow] ", end="")
    try:
        choice = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]跳过链接确认[/yellow]")
        return
    
    if choice == 'n' or not choice:
        console.print("[dim]未确认任何链接[/dim]")
        return
    
    # 解析选择
    indices_to_confirm = []
    if choice == 'a':
        indices_to_confirm = list(range(len(potential_links)))
    else:
        try:
            for part in choice.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    indices_to_confirm.extend(range(int(start) - 1, int(end)))
                else:
                    indices_to_confirm.append(int(part) - 1)
        except ValueError:
            console.print("[yellow]⚠ 输入无效，未确认任何链接[/yellow]")
            return
    
    # 验证索引
    indices_to_confirm = [i for i in indices_to_confirm if 0 <= i < len(potential_links)]
    
    if not indices_to_confirm:
        console.print("[dim]未选择有效链接[/dim]")
        return
    
    # 确认选中的链接
    for idx in indices_to_confirm:
        link = potential_links[idx]
        relation_type = link.get('relation_type', 'support')
        strength = link.get('strength', 0.7)
        
        # 从摘要查找目标节点ID
        target_id = None
        target_summary = link.get('target_node_summary', '')
        for node in existing_nodes:
            if target_summary[:50] in node.processed.proposition or node.processed.proposition[:50] in target_summary:
                target_id = node.id
                break
        
        if target_id:
            if store.add_link(node_id, target_id, relation_type, strength, confirmed=True):
                confirmed_count += 1
                relation_cn = RELATION_TYPE_CN.get(relation_type, relation_type)
                console.print(f"  [green]✓[/green] 已确认: {relation_cn} -> {target_id[:8]}")
    
    console.print()
    console.print(f"[green]✓ 已确认 {confirmed_count} 个链接[/green]")


@cli.command()
@click.argument("content", required=False)
@click.option("-f", "--file", type=click.Path(exists=True), help="从文件读取输入")
@click.option("-t", "--type", "source_type", default="original", 
              type=click.Choice(["book", "paper", "article", "original"]),
              help="来源类型")
@click.option("--title", help="来源标题")
@click.option("--location", help="来源位置（章节、页码等）")
@click.option("--mock", is_flag=True, help="使用模拟处理器（不调用API）")
@click.option("--no-interactive", is_flag=True, help="跳过交互式链接确认")
@click.pass_context
def add(
    ctx: click.Context,
    content: Optional[str],
    file: Optional[str],
    source_type: str,
    title: Optional[str],
    location: Optional[str],
    mock: bool,
    no_interactive: bool
) -> None:
    """向知识库添加新节点"""
    
    # 获取输入内容
    if file:
        with open(file, "r", encoding="utf-8") as f:
            raw_input = f.read()
    elif content:
        raw_input = content
    else:
        # 从标准输入读取
        console.print("请输入笔记内容（粘贴后按 Ctrl+Z 然后回车结束）:")
        raw_input = sys.stdin.read().strip()
    
    if not raw_input:
        console.print("[yellow]⚠[/yellow] 未提供内容")
        sys.exit(1)
    
    # 处理变量
    processed = None
    tags = []
    potential_links = []
    node = None
    existing_nodes = []
    
    # 显示处理中消息
    with console.status("[bold green]正在使用LLM处理...") as status:
        try:
            # 初始化组件
            store = get_store()
            processor = get_processor(use_mock=mock)
            
            # 获取现有节点用于链接建议
            existing_nodes = store.list_all(limit=20)
            
            # 创建来源
            source = Source(
                type=source_type,  # type: ignore
                title=title,
                location=location
            )
            
            # 使用LLM处理
            async def process():
                return await processor.process(
                    raw_input=raw_input,
                    source=source,
                    existing_nodes=existing_nodes
                )
            
            processed, tags, potential_links = asyncio.run(process())
            
            # 创建节点
            node = Node(
                source=source,
                raw_input=raw_input,
                processed=processed,
                tags=tags  # type: ignore
            )
            
            # 保存节点
            store.save(node)
            
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            console.print(f"[red]✗[/red] 处理失败: {e}")
            sys.exit(1)
    
    # 显示结果（在 status 上下文之外）
    if node and processed:
        console.print()
        console.print(Panel(
            f"[bold green]节点创建成功！[/bold green]\n"
            f"ID: [cyan]{node.id}[/cyan]\n"
            f"标签: [yellow]{', '.join(tags)}[/yellow]",
            title="✓ 成功",
            border_style="green"
        ))
        
        console.print()
        console.print("[bold]核心命题:[/bold]")
        console.print(processed.proposition)
        
        if processed.open_questions:
            console.print()
            console.print("[bold]开放问题:[/bold]")
            for i, q in enumerate(processed.open_questions, 1):
                console.print(f"  {i}. {q}")
        
        if potential_links:
            console.print()
            console.print("[bold]潜在链接（待确认）:[/bold]")
            for i, link in enumerate(potential_links[:3], 1):
                relation_cn = RELATION_TYPE_CN.get(link['relation_type'], link['relation_type'])
                console.print(f"  {i}. [{relation_cn}] {link['target_node_summary'][:50]}...")
                console.print(f"     理由: {link['reasoning'][:60]}...")
            
            # 交互式链接确认（在 status 上下文之外）
            if not no_interactive and sys.stdin.isatty():
                _interactive_link_confirm(node.id, potential_links, existing_nodes)


@cli.command(name="list")
@click.option("-l", "--limit", default=10, help="显示的最大节点数")
@click.option("-t", "--tag", help="按标签筛选")
@click.pass_context
def list_nodes(ctx: click.Context, limit: int, tag: Optional[str]) -> None:
    """列出知识库中的节点"""
    try:
        store = get_store()
        
        if tag:
            nodes = store.list_by_tag(tag, limit=limit)
        else:
            nodes = store.list_all(limit=limit)
        
        if not nodes:
            console.print("[yellow]未找到节点[/yellow]")
            return
        
        # 创建表格
        table = Table(title=f"节点列表（显示 {len(nodes)} 个）")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("日期", style="dim", no_wrap=True)
        table.add_column("标签", style="yellow")
        table.add_column("核心命题", style="green")
        table.add_column("链接", justify="right")
        
        for node in nodes:
            date_str = node.timestamp.strftime("%Y-%m-%d")
            tags_str = ", ".join(node.tags) if node.tags else "-"
            prop_str = node.processed.proposition[:40] + "..." if len(node.processed.proposition) > 40 else node.processed.proposition
            links_str = str(len(node.links)) if node.links else "-"
            
            table.add_row(
                node.id[:8],
                date_str,
                tags_str,
                prop_str,
                links_str
            )
        
        console.print(table)
        
        # 显示统计
        stats = store.get_stats()
        console.print()
        console.print(f"[dim]总计: {stats['total_nodes']} 个节点, {stats['total_links']} 个链接 ({stats['confirmed_links']} 个已确认)[/dim]")
        
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 列出节点失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument("node_id")
@click.pass_context
def show(ctx: click.Context, node_id: str) -> None:
    """显示节点详细信息"""
    try:
        store = get_store()
        
        # 尝试通过部分ID查找
        if len(node_id) < 36:
            # 搜索匹配的前缀
            all_nodes = store.list_all()
            matching = [n for n in all_nodes if n.id.startswith(node_id)]
            if len(matching) == 1:
                node = matching[0]
            elif len(matching) > 1:
                console.print(f"[yellow]多个节点匹配 '{node_id}':[/yellow]")
                for n in matching:
                    console.print(f"  - {n.id}: {n.processed.proposition[:50]}...")
                return
            else:
                node = None
        else:
            node = store.get(node_id)
        
        if not node:
            console.print(f"[red]✗[/red] 未找到节点: {node_id}")
            sys.exit(1)
        
        # 显示节点详情
        console.print(Panel(
            f"[bold]ID:[/bold] {node.id}\n"
            f"[bold]创建时间:[/bold] {node.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[bold]来源:[/bold] {node.source}\n"
            f"[bold]标签:[/bold] [yellow]{', '.join(node.tags)}[/yellow]",
            title="节点详情",
            border_style="blue"
        ))
        
        console.print()
        console.print("[bold]核心命题:[/bold]")
        console.print(node.processed.proposition)
        
        if node.processed.open_questions:
            console.print()
            console.print("[bold]开放问题:[/bold]")
            for i, q in enumerate(node.processed.open_questions, 1):
                console.print(f"  {i}. {q}")
        
        if node.links:
            console.print()
            console.print("[bold]链接:[/bold]")
            for link in node.links:
                status = "✓" if link.confirmed else "?"
                relation_cn = RELATION_TYPE_CN.get(link.relation_type, link.relation_type)
                console.print(f"  [{status}] {relation_cn} -> {link.target_id[:8]} (强度: {link.strength:.2f})")
        
        console.print()
        console.print("[bold]原始输入:[/bold]")
        console.print(Panel(node.raw_input, border_style="dim"))
        
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 显示节点失败: {e}")
        sys.exit(1)


@cli.group()
def link() -> None:
    """管理节点间的链接"""
    pass


@link.command("confirm")
@click.argument("node_id")
@click.argument("target_id")
@click.pass_context
def link_confirm(ctx: click.Context, node_id: str, target_id: str) -> None:
    """确认待处理的链接"""
    try:
        store = get_store()
        
        if store.update_link(node_id, target_id, confirmed=True):
            console.print(f"[green]✓[/green] 链接已确认: {node_id[:8]} -> {target_id[:8]}")
        else:
            console.print(f"[yellow]⚠[/yellow] 未找到链接")
            sys.exit(1)
            
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 确认链接失败: {e}")
        sys.exit(1)


@link.command("reject")
@click.argument("node_id")
@click.argument("target_id")
@click.pass_context
def link_reject(ctx: click.Context, node_id: str, target_id: str) -> None:
    """拒绝并移除待处理的链接"""
    try:
        store = get_store()
        
        # 目前拒绝只是标记为未确认
        if store.update_link(node_id, target_id, confirmed=False):
            console.print(f"[yellow]✓[/yellow] 链接已拒绝: {node_id[:8]} -> {target_id[:8]}")
        else:
            console.print(f"[yellow]⚠[/yellow] 未找到链接")
            sys.exit(1)
            
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 拒绝链接失败: {e}")
        sys.exit(1)


@link.command("add")
@click.argument("node_id")
@click.argument("target_id")
@click.option("-t", "--type", "relation_type", default="support",
              type=click.Choice(["support", "contradict", "extend", "source", "analogy"]),
              help="关系类型")
@click.option("-s", "--strength", default=0.7, type=click.FloatRange(0.0, 1.0),
              help="连接强度 (0.0 - 1.0)")
@click.pass_context
def link_add(
    ctx: click.Context,
    node_id: str,
    target_id: str,
    relation_type: str,
    strength: float
) -> None:
    """手动添加节点间的链接"""
    try:
        store = get_store()
        
        if store.add_link(node_id, target_id, relation_type, strength, confirmed=True):
            relation_cn = RELATION_TYPE_CN.get(relation_type, relation_type)
            console.print(f"[green]✓[/green] 链接已添加: {node_id[:8]} -> {target_id[:8]} [{relation_cn}]")
        else:
            console.print(f"[yellow]⚠[/yellow] 添加链接失败（可能已存在）")
            sys.exit(1)
            
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 添加链接失败: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """显示知识库统计信息"""
    try:
        store = get_store()
        stats = store.get_stats()
        
        console.print(Panel(
            f"[bold]节点总数:[/bold] {stats['total_nodes']}\n"
            f"[bold]链接总数:[/bold] {stats['total_links']}\n"
            f"[bold]已确认链接:[/bold] {stats['confirmed_links']}\n"
            f"[bold]待处理链接:[/bold] {stats['pending_links']}",
            title="知识库统计",
            border_style="blue"
        ))
        
        if stats['tag_counts']:
            console.print()
            console.print("[bold]标签分布:[/bold]")
            for tag, count in sorted(stats['tag_counts'].items(), key=lambda x: x[1], reverse=True):
                bar = "█" * count
                console.print(f"  {tag:20s} {bar} {count}")
        
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 获取统计失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("-l", "--limit", default=10, help="最大结果数")
@click.pass_context
def search(ctx: click.Context, query: str, limit: int) -> None:
    """按命题关键词搜索节点（阶段1使用）"""
    try:
        store = get_store()
        results = store.search_by_proposition(query, limit=limit)
        
        if not results:
            console.print("[yellow]未找到结果[/yellow]")
            return
        
        console.print(f"找到 {len(results)} 个 '[bold]{query}[/bold]' 的结果:")
        console.print()
        
        for node, score in results:
            title = node.processed.proposition[:60] + "..." if len(node.processed.proposition) > 60 else node.processed.proposition
            console.print(Panel(
                f"[bold]{title}[/bold]\n"
                f"[dim]ID: {node.id[:8]} | 标签: {', '.join(node.tags)} | 相关度: {score:.2f}[/dim]",
                border_style="blue"
            ))
        
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 搜索失败: {e}")
        sys.exit(1)


@cli.command()
@click.option("-h", "--host", default="0.0.0.0", help="服务器地址")
@click.option("-p", "--port", default=8000, help="服务器端口")
@click.option("--reload/--no-reload", default=False, help="启用热重载（开发模式）")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int, reload: bool) -> None:
    """启动Web服务器（阶段2）"""
    try:
        import uvicorn
        
        console.print(Panel(
            f"[bold green]启动 Rhizome Thinking 服务器[/bold green]\n"
            f"地址: [cyan]{host}:{port}[/cyan]\n"
            f"热重载: [yellow]{'启用' if reload else '禁用'}[/yellow]",
            title="🚀 服务器",
            border_style="green"
        ))
        
        uvicorn.run(
            "rhizome.api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
    except ImportError:
        console.print("[red]✗[/red] 缺少依赖，请安装: pip install uvicorn")
        sys.exit(1)
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 启动服务器失败: {e}")
        sys.exit(1)


@cli.command()
@click.option("--batch-size", default=5, help="批处理大小")
@click.option("--mock", is_flag=True, help="使用模拟处理器（不调用API）")
@click.pass_context
def vectorize(ctx: click.Context, batch_size: int, mock: bool) -> None:
    """批量向量化现有节点（阶段2）"""
    try:
        from rhizome.retrieval.vector_store import VectorStore
        
        store = get_store()
        vector_store = VectorStore()
        
        # 获取所有节点
        all_nodes = store.list_all()
        
        if not all_nodes:
            console.print("[yellow]⚠[/yellow] 知识库中没有节点")
            return
        
        # 筛选出没有embedding的节点
        nodes_to_vectorize = [n for n in all_nodes if not n.embedding]
        
        if not nodes_to_vectorize:
            console.print("[green]✓[/green] 所有节点已完成向量化")
            return
        
        console.print(f"找到 {len(nodes_to_vectorize)} 个待向量化节点（共 {len(all_nodes)} 个）")
        console.print()
        
        if mock:
            console.print("[yellow]使用模拟模式（不调用真实API）[/yellow]")
            for node in nodes_to_vectorize:
                node.embedding = [0.0] * 1536  # 模拟embedding
        else:
            # 使用真实API进行向量化
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                task = progress.add_task(
                    f"向量化节点 (批大小: {batch_size})...",
                    total=len(nodes_to_vectorize)
                )
                
                for i in range(0, len(nodes_to_vectorize), batch_size):
                    batch = nodes_to_vectorize[i:i + batch_size]
                    
                    async def process_batch():
                        await vector_store.add_nodes_batch(batch, batch_size=batch_size)
                    
                    asyncio.run(process_batch())
                    progress.update(task, advance=len(batch))
        
        console.print()
        console.print(f"[green]✓[/green] 成功向量化 {len(nodes_to_vectorize)} 个节点")
        
        # 显示统计
        stats = vector_store.get_stats()
        console.print(f"[dim]向量库中共有 {stats['total_vectors']} 个向量[/dim]")
        
    except ImportError as e:
        console.print(f"[red]✗[/red] 缺少依赖: {e}")
        console.print("[dim]请安装阶段2依赖: pip install chromadb sentence-transformers[/dim]")
        sys.exit(1)
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 向量化失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("-l", "--limit", default=10, help="最大结果数")
@click.option("-t", "--tag", multiple=True, help="按标签筛选")
@click.option("--time-range", type=click.Choice(["last_week", "last_month", "last_3_months", "all"]),
              default="all", help="时间范围")
@click.pass_context
def query(
    ctx: click.Context,
    query: str,
    limit: int,
    tag: tuple,
    time_range: str
) -> None:
    """语义查询（阶段2）"""
    try:
        from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers
        
        engine = QueryEngine()
        
        modifiers = QueryModifiers(
            limit=limit,
            time_range=time_range,
            tags=list(tag) if tag else []
        )
        
        console.print(f"[dim]正在查询: [cyan]{query}[/cyan][/dim]")
        console.print()
        
        async def do_query():
            return await engine.search(anchor=query, modifiers=modifiers)
        
        results = asyncio.run(do_query())
        
        if not results:
            console.print("[yellow]未找到相关节点[/yellow]")
            return
        
        # 按标签分组显示
        grouped = engine.group_by_tags(results)
        
        for group_name, group_results in grouped.items():
            console.print(f"\n[bold cyan]【{group_name}】[/bold cyan] ({len(group_results)}个)")
            
            for result in group_results[:5]:  # 每组最多显示5个
                similarity_pct = int(result.similarity * 100)
                prop = result.node.processed.proposition[:60]
                if len(result.node.processed.proposition) > 60:
                    prop += "..."
                
                console.print(f"  [green]{similarity_pct}%[/green] {prop}")
                console.print(f"      [dim]ID: {result.node.id[:8]} | {result.node.timestamp.strftime('%Y-%m-%d')}[/dim]")
        
        console.print()
        console.print(f"[dim]共找到 {len(results)} 个相关节点[/dim]")
        
    except ImportError as e:
        console.print(f"[red]✗[/red] 缺少依赖: {e}")
        console.print("[dim]请安装阶段2依赖: pip install chromadb[/dim]")
        sys.exit(1)
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 查询失败: {e}")
        sys.exit(1)


@cli.group()
def server() -> None:
    """服务器管理命令"""
    pass


@server.command("start")
@click.pass_context
def server_start(ctx: click.Context) -> None:
    """启动服务"""
    import subprocess
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    try:
        subprocess.run(
            ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "up", "-d"],
            check=True,
            capture_output=True
        )
        console.print("[green]服务已启动[/green]")
    except subprocess.CalledProcessError as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]启动失败: {e}[/red]")
        sys.exit(1)


@server.command("stop")
@click.pass_context
def server_stop(ctx: click.Context) -> None:
    """停止服务"""
    import subprocess
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    try:
        subprocess.run(
            ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "down"],
            check=True,
            capture_output=True
        )
        console.print("[green]服务已停止[/green]")
    except subprocess.CalledProcessError as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]停止失败: {e}[/red]")
        sys.exit(1)


@server.command("restart")
@click.pass_context
def server_restart(ctx: click.Context) -> None:
    """重启服务"""
    import subprocess
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    try:
        subprocess.run(
            ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "restart"],
            check=True,
            capture_output=True
        )
        console.print("[green]服务已重启[/green]")
    except subprocess.CalledProcessError as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]重启失败: {e}[/red]")
        sys.exit(1)


@server.command("status")
@click.pass_context
def server_status(ctx: click.Context) -> None:
    """查看服务状态"""
    import subprocess
    import urllib.request
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    
    try:
        # 检查容器状态
        result = subprocess.run(
            ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "ps", "--format", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            console.print("[yellow]服务未运行[/yellow]")
            return
        
        # 健康检查
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
                health_data = response.read().decode()
                console.print(f"[green]服务运行中[/green]")
                console.print(f"健康检查: {health_data}")
        except Exception:
            console.print("[yellow]服务启动中或异常[/yellow]")
            
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]检查状态失败: {e}[/red]")


@server.command("logs")
@click.option("-f", "--follow", is_flag=True, help="持续跟踪输出")
@click.option("-n", "--lines", default=100, help="显示最近N行")
@click.pass_context
def server_logs(ctx: click.Context, follow: bool, lines: int) -> None:
    """查看服务日志"""
    import subprocess
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    
    cmd = ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "logs", "--tail", str(lines)]
    if follow:
        cmd.append("-f")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]查看日志失败: {e}[/red]")
        sys.exit(1)


@server.command("info")
def server_info() -> None:
    """显示服务访问信息"""
    import subprocess
    import re
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    
    # 获取本机IP
    try:
        result = subprocess.run(
            ["ip", "route", "get", "1"],
            capture_output=True,
            text=True
        )
        ip_match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', result.stdout)
        server_ip = ip_match.group(1) if ip_match else "localhost"
    except Exception:
        server_ip = "localhost"
    
    # 从 docker-compose.yml 读取端口
    port = "8000"
    try:
        with open(f"{project_dir}/docker-compose.yml", "r") as f:
            content = f.read()
            port_match = re.search(r'"\$\{PORT:-(\d+)\}:8000"', content)
            if port_match:
                port = port_match.group(1)
    except Exception:
        pass
    
    console.print(f"访问地址: http://{server_ip}:{port}")
    console.print(f"API文档:  http://{server_ip}:{port}/docs")


@server.command("config")
def server_config() -> None:
    """显示服务配置"""
    import subprocess
    import re
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    
    # 读取 .env 文件
    env_file = Path(project_dir) / ".env"
    if env_file.exists():
        console.print("[bold]配置项:[/bold]")
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        # 隐藏 API Key
                        if "API_KEY" in key and value:
                            if len(value) > 8:
                                hidden_value = value[:4] + "****" + value[-4:]
                            else:
                                hidden_value = "****"
                            console.print(f"  {key}={hidden_value}")
                        else:
                            console.print(f"  {line}")
    else:
        console.print("[yellow].env 文件不存在[/yellow]")
    
    # 显示容器镜像版本
    console.print("\n[bold]容器镜像:[/bold]")
    try:
        subprocess.run(
            ["docker", "compose", "-f", f"{project_dir}/docker-compose.yml", "images"],
            check=False
        )
    except Exception as e:
        console.print(f"[dim]无法获取镜像信息: {e}[/dim]")


@cli.command()
def install() -> None:
    """安装 Systemd 服务"""
    import subprocess
    project_dir = os.environ.get("RHIZOME_PROJECT_DIR", "/opt/rhizome-thinking")
    try:
        subprocess.run(
            ["bash", f"{project_dir}/scripts/install-service.sh"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[red]安装失败: {e}[/red]")
        sys.exit(1)


@cli.command()
def uninstall() -> None:
    """卸载 Systemd 服务"""
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "stop", "rhizome"], check=False)
        subprocess.run(["sudo", "systemctl", "disable", "rhizome"], check=False)
        subprocess.run(["sudo", "rm", "-f", "/etc/systemd/system/rhizome.service"], check=False)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
        console.print("[green]Systemd 服务已卸载[/green]")
    except Exception as e:
        console.print(f"[red]卸载失败: {e}[/red]")
        sys.exit(1)


@cli.group()
def backup() -> None:
    """备份管理命令"""
    pass


@backup.command("create")
@click.option("--name", help="备份名称（可选）")
@click.pass_context
def backup_create(ctx: click.Context, name: Optional[str]) -> None:
    """创建数据备份"""
    try:
        from rhizome.core.backup_manager import BackupManager

        manager = BackupManager()
        backup_path = manager.backup(output_path=name)
        info = manager.get_backup_info(str(backup_path))

        console.print(f"[green]✓[/green] 备份创建成功！")
        console.print(f"  文件名: {info['name']}")
        console.print(f"  节点数: {info['node_count']}")
        console.print(f"  大小: {info['size_mb']} MB")
        console.print(f"  时间: {info['created_at']}")
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 创建备份失败: {e}")
        sys.exit(1)


@backup.command("list")
def backup_list() -> None:
    """列出所有备份"""
    try:
        from rhizome.core.backup_manager import BackupManager

        manager = BackupManager()
        backups = manager.list_backups()

        if not backups:
            console.print("[yellow]暂无备份[/yellow]")
            return

        table = Table(title="备份列表")
        table.add_column("名称", style="cyan")
        table.add_column("创建时间", style="dim")
        table.add_column("节点数", justify="right")
        table.add_column("大小", justify="right")

        for backup in backups:
            table.add_row(
                backup["name"],
                backup["created_at"],
                str(backup["node_count"]),
                f"{backup['size_mb']} MB"
            )

        console.print(table)
    except Exception as e:
        console.print(f"[red]✗[/red] 获取备份列表失败: {e}")
        sys.exit(1)


@backup.command("restore")
@click.argument("backup_name")
@click.option("--force", is_flag=True, help="清空现有数据后恢复")
@click.pass_context
def backup_restore(ctx: click.Context, backup_name: str, force: bool) -> None:
    """从备份恢复数据"""
    try:
        from rhizome.core.backup_manager import BackupManager

        if not force:
            console.print("[yellow]⚠ 警告: 恢复备份将覆盖现有数据[/yellow]")
            console.print("[dim]使用 --force 参数确认覆盖[/dim]")
            sys.exit(1)

        manager = BackupManager()
        backup_path = manager.backups_dir / backup_name

        if not backup_path.exists():
            console.print(f"[red]✗[/red] 备份文件不存在: {backup_name}")
            sys.exit(1)

        result = manager.restore(str(backup_path), confirm=True)
        console.print(f"[green]✓[/green] {result['message']}")
        console.print(f"  恢复节点数: {result['restored_nodes']}")
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 恢复备份失败: {e}")
        sys.exit(1)


@backup.command("delete")
@click.argument("backup_name")
@click.pass_context
def backup_delete(ctx: click.Context, backup_name: str) -> None:
    """删除备份文件"""
    try:
        from rhizome.core.backup_manager import BackupManager

        manager = BackupManager()
        if manager.delete_backup(backup_name):
            console.print(f"[green]✓[/green] 备份已删除: {backup_name}")
        else:
            console.print(f"[red]✗[/red] 备份不存在: {backup_name}")
            sys.exit(1)
    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 删除备份失败: {e}")
        sys.exit(1)


@cli.command()
@click.option("--proposition", help="命题关键字")
@click.option("--raw-content", help="原始内容关键字")
@click.option("--tag", multiple=True, help="标签筛选")
@click.option("--from-date", help="开始日期 (YYYY-MM-DD)")
@click.option("--to-date", help="结束日期 (YYYY-MM-DD)")
@click.option("-l", "--limit", default=50, help="最大结果数")
@click.option("--sort-by", type=click.Choice(["time", "proposition"]), default="time", help="排序方式")
@click.pass_context
def find(
    ctx: click.Context,
    proposition: Optional[str],
    raw_content: Optional[str],
    tag: tuple,
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
    sort_by: str
) -> None:
    """精准查询节点"""
    try:
        from rhizome.core.node_store import NodeStore
        from datetime import datetime

        store = NodeStore()

        # Parse dates
        start_date = None
        end_date = None
        if from_date:
            start_date = datetime.strptime(from_date, "%Y-%m-%d")
        if to_date:
            end_date = datetime.strptime(to_date, "%Y-%m-%d")

        results = store.precise_search(
            proposition_query=proposition,
            raw_content_query=raw_content,
            tags=list(tag) if tag else None,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            limit=limit
        )

        if not results:
            console.print("[yellow]未找到匹配的节点[/yellow]")
            return

        console.print(f"[dim]找到 {len(results)} 个节点:[/dim]")
        console.print()

        for node in results:
            console.print(f"[bold]{node.processed.proposition[:80]}{'...' if len(node.processed.proposition) > 80 else ''}[/bold]")
            console.print(f"  [dim]ID: {node.id[:8]} | 时间: {node.timestamp.strftime('%Y-%m-%d %H:%M')} | 标签: {', '.join(node.tags)}[/dim]")
            console.print()

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 查询失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument("node_id")
@click.option("--proposition", help="新命题")
@click.option("--raw-input", help="新原始内容")
@click.option("--tags", help="标签（逗号分隔）")
@click.option("--source-title", help="来源标题")
@click.option("--source-location", help="来源位置")
@click.pass_context
def edit(
    ctx: click.Context,
    node_id: str,
    proposition: Optional[str],
    raw_input: Optional[str],
    tags: Optional[str],
    source_title: Optional[str],
    source_location: Optional[str]
) -> None:
    """编辑节点"""
    try:
        store = get_store()

        if not store.exists(node_id):
            console.print(f"[red]✗[/red] 节点不存在: {node_id}")
            sys.exit(1)

        tag_list = tags.split(",") if tags else None

        updated = store.update_node(
            node_id=node_id,
            proposition=proposition,
            raw_input=raw_input,
            tags=tag_list,
            source_title=source_title,
            source_location=source_location
        )

        if updated:
            console.print(f"[green]✓[/green] 节点已更新: {node_id[:8]}")
        else:
            console.print(f"[red]✗[/red] 更新失败")
            sys.exit(1)

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 编辑失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument("node_id")
@click.option("--force", is_flag=True, help="强制删除，不提示")
@click.pass_context
def delete(
    ctx: click.Context,
    node_id: str,
    force: bool
) -> None:
    """删除节点"""
    try:
        store = get_store()

        if not store.exists(node_id):
            console.print(f"[red]✗[/red] 节点不存在: {node_id}")
            sys.exit(1)

        node = store.get(node_id)
        if not force:
            console.print(f"[yellow]即将删除节点:[/yellow]")
            console.print(f"  {node.processed.proposition[:80]}{'...' if len(node.processed.proposition) > 80 else ''}")
            console.print("[dim]使用 --force 参数确认删除[/dim]")
            sys.exit(1)

        store.delete(node_id)
        console.print(f"[green]✓[/green] 节点已删除: {node_id[:8]}")

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        console.print(f"[red]✗[/red] 删除失败: {e}")
        sys.exit(1)


def main() -> None:
    """CLI入口点"""
    cli()


if __name__ == "__main__":
    main()
