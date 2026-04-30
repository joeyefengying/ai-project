#!/usr/bin/env python3
"""
fetch_huggingface.py — 抓取 Hugging Face 博客文章

Hugging Face Blog: https://huggingface.co/blog
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    save_article_to_wiki,
    safe_fetch_rss_feed
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"


def fetch_huggingface_blog():
    """抓取 Hugging Face 博客"""
    config = load_config()

    if not config or 'tech_sources' not in config:
        print("[错误] 配置文件无效或缺失")
        return []

    hf_config = config['tech_sources'].get('huggingface_blog', {})
    fetch_config = config.get('fetch_config', {})
    max_articles = fetch_config.get('max_articles_per_fetch', 10)

    print(f"[信息] 开始抓取: {hf_config.get('name', 'Hugging Face Blog')}")
    print(f"[信息] 最大抓取数: {max_articles} 篇")

    # Hugging Face 有 RSS feed
    rss_url = "https://huggingface.co/blog/feed.xml"

    # 使用 safe_fetch_rss_feed 带重试机制
    articles = safe_fetch_rss_feed(rss_url, source="Hugging Face Blog", max_retries=3)

    if not articles:
        print("[警告] RSS feed 解析失败或为空（已重试 3 次）")
        return []

    # 限制文章数量
    articles = articles[:max_articles]

    # 使用 DedupManager 过滤已抓取的文章
    dedup = get_dedup_manager()
    new_articles = []

    for article in articles:
        is_dup, dup_id = dedup.is_duplicate(article['url'], article['title'])

        if not is_dup:
            new_articles.append(article)

    print(f"[信息] 发现 {len(articles)} 篇文章，其中 {len(new_articles)} 篇为新文章")

    # 保存新文章到知识库
    saved_files = []
    for article in new_articles:
        # 使用分类器自动判断分类
        category = classify_article(article)
        filepath = save_article_to_wiki(
            article,
            category=category,
            wiki_root=WIKI_ROOT
        )
        saved_files.append(filepath)
        print(f"[分类] {category} | [保存] {filepath}")

        # 添加到去重缓存
        dedup.add_article(
            url=article['url'],
            title=article['title'],
            source="Hugging Face Blog",
            category=category,
            file_path=filepath
        )

    return saved_files


def main():
    print("=" * 50)
    print("Hugging Face Blog 抓取脚本")
    print("=" * 50)
    print()

    saved = fetch_huggingface_blog()

    print()
    print("=" * 50)
    print(f"抓取完成: 新增 {len(saved)} 篇技术文章")
    print("=" * 50)

    if saved:
        print("\n[下一步] 请使用 /llm-wiki 消化这些文章:")
        for f in saved:
            print(f"  /llm-wiki 帮我消化 {f}")


if __name__ == "__main__":
    main()