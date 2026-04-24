#!/usr/bin/env python
"""批量提取所有现有笔记的主题.

使用方法:
    python scripts/batch_extract_themes.py
"""

import asyncio
import os
import sys
import yaml
import traceback
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhizome.config import settings
from rhizome.core.models import Node, Source, Processed
from rhizome.core.theme_models import Theme, NodeTheme
from rhizome.core.theme_store import ThemeStore
from rhizome.core.theme_extractor import ThemeExtractor
from datetime import datetime


def load_node_from_file(file_path: Path) -> Node | None:
    """从Markdown文件加载节点."""
    try:
        content = file_path.read_text(encoding="utf-8")

        # Split frontmatter and content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                md_content = parts[2].strip()
            else:
                return None
        else:
            return None

        # Parse markdown content to extract sections
        # Support both old format (核心命题/开放问题/原始输入) and new format (标题/问题/原始文件)
        lines = md_content.split("\n")
        current_section = None
        sections = {
            "title": "",
            "proposition": "",
            "questions": [],
            "raw_input": ""
        }

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check for section headers - support both old and new formats
            if stripped.startswith("# ") and not sections["title"]:
                sections["title"] = stripped[2:].strip()
            elif stripped in ["## 核心命题", "## 标题"]:
                current_section = "proposition"
            elif stripped in ["## 开放问题", "## 问题"]:
                current_section = "questions"
            elif stripped in ["## 原始输入", "## 原始文件"]:
                current_section = "raw_input"
            elif stripped.startswith("---"):
                current_section = None
            elif current_section == "proposition":
                sections["proposition"] += stripped + "\n"
            elif current_section == "questions":
                # Parse questions (numbered or bulleted)
                if stripped[0].isdigit() and "." in stripped[:3]:
                    q = stripped.split(".", 1)[1].strip()
                    if q:
                        sections["questions"].append(q)
                elif stripped.startswith("-"):
                    q = stripped[1:].strip()
                    if q:
                        sections["questions"].append(q)
            elif current_section == "raw_input":
                sections["raw_input"] += line + "\n"

        # Create Node object
        proposition = sections["proposition"].strip() or sections["title"]
        if not proposition:
            print(f"  - 警告: 无法提取标题/核心命题")
            return None

        node = Node(
            id=frontmatter.get("id", ""),
            timestamp=datetime.fromisoformat(frontmatter.get("timestamp", datetime.now().isoformat())),
            source=Source(**frontmatter.get("source", {"type": "original"})),
            tags=frontmatter.get("tags", []),
            links=[],  # Skip loading links for theme extraction
            raw_input=sections["raw_input"].strip(),
            processed=Processed(
                proposition=proposition,
                open_questions=sections["questions"]
            )
        )

        return node

    except Exception as e:
        print(f"Error loading node from {file_path}: {e}")
        traceback.print_exc()
        return None


async def process_node(extractor: ThemeExtractor, store: ThemeStore, node: Node) -> int:
    """处理单个节点，提取并保存主题.

    Returns:
        Number of themes extracted
    """
    try:
        # Extract themes from node
        extracted_themes = await extractor.extract_themes_from_node(node)

        # Create NodeTheme record
        node_themes = NodeTheme(node_id=node.id)
        theme_count = 0

        for theme_data in extracted_themes:
            # Create new theme
            theme = Theme(
                summary=theme_data["summary"],
                tag=theme_data["tag"],
                keywords=theme_data.get("keywords", [])
            )
            theme.add_node(node.id)

            # Save theme
            store.save_theme(theme)

            # Add to node themes
            node_themes.theme_ids.append(theme.id)
            theme_count += 1

            print(f"  - Created theme: {theme.summary[:50]}... (tag: {theme.tag})")

        # Save node themes association
        if node_themes.theme_ids:
            store.save_node_themes(node_themes)

        return theme_count

    except Exception as e:
        print(f"Error processing node {node.id}: {e}")
        traceback.print_exc()
        return 0


async def batch_extract_themes():
    """批量提取所有笔记的主题."""
    print("=" * 60)
    print("批量主题提取")
    print("=" * 60)

    # Initialize components
    store = ThemeStore()
    extractor = ThemeExtractor()

    # Load all nodes
    nodes_dir = settings.storage_dir / "nodes"
    if not nodes_dir.exists():
        print(f"Error: Nodes directory not found: {nodes_dir}")
        return

    node_files = list(nodes_dir.glob("*.md"))
    print(f"\n找到 {len(node_files)} 个笔记文件")

    # Get existing stats
    stats = store.get_stats()
    print(f"当前主题统计: {stats['total_themes']} 个主题, {stats['total_node_associations']} 个节点关联")

    # Process each node
    total_themes = 0
    processed_count = 0
    error_count = 0

    print("\n开始处理...")
    print("-" * 60)

    for i, node_file in enumerate(node_files, 1):
        print(f"\n[{i}/{len(node_files)}] 处理: {node_file.stem}")

        node = load_node_from_file(node_file)
        if not node:
            print(f"  - 跳过: 无法加载节点")
            error_count += 1
            continue

        # Check if node already has themes
        existing_themes = store.get_node_themes(node.id)
        if existing_themes and existing_themes.theme_ids:
            print(f"  - 跳过: 已有 {len(existing_themes.theme_ids)} 个主题")
            continue

        print(f"  - 节点标题: {node.processed.proposition[:60]}...")
        print(f"  - 标签: {', '.join(node.tags)}")

        # Process node
        theme_count = await process_node(extractor, store, node)
        total_themes += theme_count
        processed_count += 1

        if theme_count > 0:
            print(f"  - 成功提取 {theme_count} 个主题")

    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"  处理节点: {processed_count}/{len(node_files)}")
    print(f"  提取主题: {total_themes}")
    print(f"  错误/跳过: {error_count}")

    # Final stats
    stats = store.get_stats()
    print(f"\n最终主题统计:")
    print(f"  总主题数: {stats['total_themes']}")
    print(f"  总节点关联: {stats['total_node_associations']}")
    print(f"  标签分布: {stats['tag_distribution']}")
    print("=" * 60)


if __name__ == "__main__":
    # Check for API key
    if not settings.minimax_api_key:
        print("错误: 未配置MiniMax API密钥")
        print("请检查环境变量或配置文件")
        sys.exit(1)

    asyncio.run(batch_extract_themes())
