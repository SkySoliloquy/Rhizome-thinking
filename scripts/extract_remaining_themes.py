#!/usr/bin/env python
"""继续提取剩余笔记的主题.

使用方法:
    python scripts/extract_remaining_themes.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.config import settings
from rhizome.core.models import Node
from rhizome.core.theme_store import ThemeStore
from rhizome.core.theme_extractor import ThemeExtractor
from batch_extract_themes import load_node_from_file, process_node


async def extract_remaining_themes():
    """提取剩余笔记的主题."""
    print("=" * 60)
    print("继续提取剩余笔记的主题")
    print("=" * 60)

    # Initialize components
    store = ThemeStore()
    extractor = ThemeExtractor()

    # Load all nodes
    nodes_dir = settings.storage_dir / "nodes"
    node_files = list(nodes_dir.glob("*.md"))
    print(f"\n找到 {len(node_files)} 个笔记文件")

    # Get current stats
    stats = store.get_stats()
    print(f"当前主题统计: {stats['total_themes']} 个主题, {stats['total_node_associations']} 个节点关联")

    # Process only nodes without themes
    total_themes = 0
    processed_count = 0
    skipped_count = 0
    error_count = 0

    print("\n开始处理...")
    print("-" * 60)

    for i, node_file in enumerate(node_files, 1):
        # Check if node already has themes
        node_id = node_file.stem
        existing_themes = store.get_node_themes(node_id)
        if existing_themes and existing_themes.theme_ids:
            skipped_count += 1
            continue

        print(f"\n[{processed_count + 1}] 处理: {node_id}")

        node = load_node_from_file(node_file)
        if not node:
            print(f"  - 跳过: 无法加载节点")
            error_count += 1
            continue

        print(f"  - 节点标题: {node.processed.proposition[:50]}...")
        print(f"  - 标签: {', '.join(node.tags)}")

        # Process node
        theme_count = await process_node(extractor, store, node)
        total_themes += theme_count
        processed_count += 1

        if theme_count > 0:
            print(f"  - 成功提取 {theme_count} 个主题")

    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"  处理节点: {processed_count}")
    print(f"  跳过节点: {skipped_count} (已有主题)")
    print(f"  提取主题: {total_themes}")
    print(f"  错误: {error_count}")

    # Final stats
    stats = store.get_stats()
    print(f"\n最终主题统计:")
    print(f"  总主题数: {stats['total_themes']}")
    print(f"  总节点关联: {stats['total_node_associations']}")
    print(f"  标签分布: {stats['tag_distribution']}")
    print("=" * 60)


if __name__ == "__main__":
    if not settings.minimax_api_key:
        print("错误: 未配置MiniMax API密钥")
        sys.exit(1)

    asyncio.run(extract_remaining_themes())
