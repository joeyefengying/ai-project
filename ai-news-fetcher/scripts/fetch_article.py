#!/usr/bin/env python3
"""
fetch_article.py — 通用文章抓取模块

提供基础的文章抓取功能，支持 RSS 和网页抓取。
"""

import json
import yaml
import hashlib
import os
import re
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import subprocess

# 配置路径
CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"
CACHE_PATH = Path(__file__).parent.parent / "cache"

# 导入 DedupManager 和 RetryHandler
sys.path.insert(0, str(Path(__file__).parent))
from dedup_manager import DedupManager
from retry_handler import safe_request, RetryHandler, ErrorType


def load_config() -> Dict:
    """加载数据源配置"""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_dedup_manager() -> DedupManager:
    """获取去重管理器实例"""
    return DedupManager(str(CACHE_PATH))


def get_retry_handler() -> RetryHandler:
    """获取重试处理器实例"""
    return RetryHandler()


# 保留旧函数以兼容现有脚本
def load_cache() -> Dict[str, str]:
    """加载已抓取文章的缓存（用于去重）- 旧版本兼容"""
    cache_file = CACHE_PATH / "fetched_articles.json"
    if not cache_file.exists():
        return {}
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cache(cache: Dict[str, str]) -> None:
    """保存抓取缓存 - 旧版本兼容"""
    cache_file = CACHE_PATH / "fetched_articles.json"
    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate_article_id(url: str, title: str) -> str:
    """生成文章唯一 ID"""
    return DedupManager.generate_id(url, title)


def is_already_fetched(article_id: str, cache: Dict) -> bool:
    """检查文章是否已抓取"""
    return article_id in cache


def save_article_to_wiki(article: Dict, category: str, wiki_root: str) -> str:
    """
    将文章保存到知识库

    Args:
        article: 文章信息 {title, url, content, author, published, source}
        category: 'news' 或 'tech-articles'
        wiki_root: 知识库根路径

    Returns:
        保存的文件路径
    """
    wiki_path = Path(wiki_root)

    if category == "news":
        target_dir = wiki_path / "raw" / "news"
    else:
        target_dir = wiki_path / "raw" / "tech-articles"

    target_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    date_str = datetime.now().strftime("%Y-%m-%d")
    title_slug = re.sub(r'[^\w\s-]', '', article['title'])
    title_slug = re.sub(r'[\s]+', '-', title_slug).lower()[:50]
    filename = f"{date_str}-{title_slug}.md"

    filepath = target_dir / filename

    # 写入文件
    content = f"""---
title: "{article['title']}"
source: "{article['url']}"
author: "{article.get('author', 'Unknown')}"
published: "{article.get('published', date_str)}"
created: "{date_str}"
tags:
  - "{category}"
  - "AI"
  - "{article.get('source', 'unknown')}"
---

# {article['title']}

> 来源: {article['source']} | {article.get('published', '未知日期')}

{article.get('content', article.get('summary', '待补充内容'))}

---

**原文链接**: {article['url']}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return str(filepath)


def digest_with_llm_wiki(filepath: str, wiki_root: str) -> bool:
    """
    调用 llm-wiki skill 消化文章

    注意：需要在 Claude Code 环境中执行
    """
    # 这只是一个标记，实际消化需要手动调用 /llm-wiki
    # 或者在 Claude Code 中执行
    print(f"[提示] 请使用 /llm-wiki 帮我消化: {filepath}")
    return True


def fetch_rss_feed(url: str) -> List[Dict]:
    """
    抓取 RSS feed

    注意：需要安装 feedparser
    pip install feedparser
    """
    try:
        import feedparser
    except ImportError:
        print("[错误] 请先安装 feedparser: pip install feedparser")
        return []

    feed = feedparser.parse(url)
    articles = []

    for entry in feed.entries:
        article = {
            'title': entry.get('title', 'Untitled'),
            'url': entry.get('link', ''),
            'summary': entry.get('summary', ''),
            'author': entry.get('author', 'Unknown'),
            'published': entry.get('published', datetime.now().strftime("%Y-%m-%d")),
            'source': feed.feed.get('title', 'Unknown')
        }
        articles.append(article)

    return articles


def safe_fetch_rss_feed(
    url: str,
    source: str = "unknown",
    max_retries: int = 3
) -> List[Dict]:
    """
    安全的 RSS 抓取（带重试）

    Args:
        url: RSS feed URL
        source: 数据源名称
        max_retries: 最大重试次数

    Returns:
        文章列表
    """
    try:
        import feedparser
    except ImportError:
        print("[错误] 请先安装 feedparser: pip install feedparser")
        return []

    handler = RetryHandler(max_retries=max_retries)

    for retry_count in range(max_retries + 1):
        try:
            # 使用 safe_request 先获取内容
            resp = safe_request(
                url,
                source=source,
                max_retries=0,  # 不在这里重试，使用外层重试逻辑
                timeout=30
            )

            if resp is None:
                raise requests.RequestException("请求失败")

            # 解析 RSS
            feed = feedparser.parse(resp.text)

            # 检查解析是否成功
            if feed.bozo and feed.bozo_exception:
                raise feed.bozo_exception

            articles = []
            for entry in feed.entries:
                article = {
                    'title': entry.get('title', 'Untitled'),
                    'url': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'author': entry.get('author', 'Unknown'),
                    'published': entry.get('published', datetime.now().strftime("%Y-%m-%d")),
                    'source': feed.feed.get('title', source)
                }
                articles.append(article)

            print(f"[成功] {source}: 获取 {len(articles)} 篇文章")
            return articles

        except Exception as e:
            error_type = handler.classify_error(e)
            context = f"RSS 抓取: {url}"

            if retry_count < max_retries and handler.should_retry(error_type):
                delay = handler.calculate_delay(retry_count + 1)
                handler.log_error(e, context, source, retry_count, final_failure=False)
                print(f"[重试] {source}: {retry_count + 1}/{max_retries}, 等待 {delay:.1f}s")
                time.sleep(delay)
            else:
                handler.log_error(e, context, source, retry_count, final_failure=True)
                print(f"[失败] {source}: {str(e)}")
                return []

    return []


def main():
    """测试入口"""
    config = load_config()
    print("配置加载成功:", config.keys())

    # 测试缓存
    cache = load_cache()
    print(f"已缓存文章: {len(cache)} 篇")


if __name__ == "__main__":
    main()