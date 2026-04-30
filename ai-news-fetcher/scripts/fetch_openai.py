#!/usr/bin/env python3
"""
fetch_openai.py — 抓取 OpenAI 官方博客文章

OpenAI 官方博客 RSS: https://openai.com/blog/rss.xml
使用 feedparser 解析 RSS feed
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    save_article_to_wiki,
    safe_fetch_rss_feed,
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"
RSS_URL = "https://openai.com/blog/rss.xml"


def fetch_openai_blog():
    """抓取 OpenAI 博客（带重试机制）"""
    config = load_config()
    fetch_config = config.get("fetch_config", {})
    max_articles = fetch_config.get("max_articles_per_fetch", 10)

    print("[信息] 开始抓取: OpenAI Blog (RSS)")

    # 使用 safe_fetch_rss_feed 带重试机制
    articles = safe_fetch_rss_feed(RSS_URL, source="OpenAI Blog", max_retries=3)

    if not articles:
        print("[警告] RSS 解析失败或无文章（已重试 3 次）")
        return []

    print(f"[信息] 发现 {len(articles)} 篇文章")

    # 使用 DedupManager 过滤已抓取的文章
    dedup = get_dedup_manager()
    new_articles = []

    for article in articles:
        is_dup, dup_id = dedup.is_duplicate(article["url"], article["title"])

        if not is_dup:
            new_articles.append(article)

    print(f"[信息] 其中 {len(new_articles)} 篇为新文章")

    # 限制数量
    new_articles = new_articles[:max_articles]

    # 保存新文章到知识库
    saved_files = []
    for article in new_articles:
        # 使用分类器自动判断分类
        category = classify_article(article)
        filepath = save_article_to_wiki(
            article,
            category=category,
            wiki_root=WIKI_ROOT,
        )
        saved_files.append(filepath)
        print(f"[分类] {category} | [保存] {filepath}")

        # 添加到去重缓存
        dedup.add_article(
            url=article["url"],
            title=article["title"],
            source="OpenAI Blog",
            category=category,
            file_path=filepath
        )

    return saved_files


def main():
    """主入口"""
    print("=" * 50)
    print("OpenAI Blog 抓取脚本")
    print("=" * 50)
    print()

    saved = fetch_openai_blog()

    print()
    print("=" * 50)
    print(f"抓取完成: 新增 {len(saved)} 篇文章")
    print("=" * 50)

    if saved:
        print("\n[下一步] 请使用 /llm-wiki 消化这些文章:")
        for f in saved:
            print(f"  /llm-wiki 帮我消化 {f}")


if __name__ == "__main__":
    main()