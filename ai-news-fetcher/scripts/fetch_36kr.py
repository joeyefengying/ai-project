#!/usr/bin/env python3
"""
fetch_36kr.py — 抓取 36氪 AI 新闻

36氪: https://36kr.com/
使用 RSS feed (https://36kr.com/feed)，过滤 AI 相关文章
"""

import sys
import re
import json
from datetime import datetime
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    save_article_to_wiki,
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"

# AI 相关关键词（用于过滤）
AI_KEYWORDS = [
    "AI", "人工智能", "机器学习", "深度学习", "大模型", "LLM",
    "ChatGPT", "GPT", "OpenAI", "Claude", "Gemini",
    "神经网络", "自然语言处理", "计算机视觉", "NLP",
    "自动驾驶", "机器人", "AGI", "生成式", "AIGC",
    "智能", "算法", "模型", "Transformer", "RAG",
]


def fetch_36kr_rss(max_articles: int = 10) -> list:
    """
    通过 36kr RSS feed 获取文章，过滤 AI 相关内容
    """
    rss_url = "https://36kr.com/feed"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    try:
        resp = requests.get(rss_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[错误] RSS 请求失败: {e}")
        return []

    articles = []

    # 解析 RSS XML
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"[错误] XML 解析失败: {e}")
        return []

    # RSS 2.0 格式：channel -> item
    channel = root.find("channel")
    if channel is None:
        print("[错误] 未找到 RSS channel")
        return []

    items = channel.findall("item")

    for item in items:
        title_elem = item.find("title")
        link_elem = item.find("link")
        pubdate_elem = item.find("pubDate")
        desc_elem = item.find("description")
        author_elem = item.find("author")

        if title_elem is None or link_elem is None:
            continue

        title = title_elem.text or ""
        url = link_elem.text or ""

        # 检查是否是 AI 相关文章
        is_ai_related = False
        title_lower = title.lower()

        for keyword in AI_KEYWORDS:
            if keyword.lower() in title_lower:
                is_ai_related = True
                break

        # 也检查 description
        if not is_ai_related and desc_elem is not None and desc_elem.text:
            desc_lower = desc_elem.text.lower()
            for keyword in AI_KEYWORDS:
                if keyword.lower() in desc_lower:
                    is_ai_related = True
                    break

        if not is_ai_related:
            continue

        # 解析日期
        published = datetime.now().strftime("%Y-%m-%d")
        if pubdate_elem is not None and pubdate_elem.text:
            try:
                # RSS pubDate 格式: "Wed, 30 Apr 2026 08:00:00 GMT"
                dt = datetime.strptime(pubdate_elem.text[:25], "%a, %d %b %Y %H:%M:%S")
                published = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        author = "36氪"
        if author_elem is not None and author_elem.text:
            author = author_elem.text

        summary = ""
        if desc_elem is not None and desc_elem.text:
            # 清理 HTML 标签
            summary = re.sub(r'<[^>]+>', '', desc_elem.text)
            summary = summary[:500]  # 截断

        articles.append({
            "title": title,
            "url": url,
            "source": "36氪 AI",
            "published": published,
            "author": author,
            "summary": summary,
        })

        if len(articles) >= max_articles:
            break

    return articles


def fetch_36kr():
    """抓取 36氪 AI 新闻"""
    config = load_config()
    fetch_config = config.get("fetch_config", {})
    max_articles = fetch_config.get("max_articles_per_fetch", 10)

    print("[信息] 开始抓取: 36氪 AI (中文，RSS feed)")

    # 使用 RSS feed
    articles = fetch_36kr_rss(max_articles)

    if not articles:
        print("[警告] 未找到 AI 相关文章")
        return []

    print(f"[信息] 发现 {len(articles)} 篇 AI 相关文章")

    # 使用 DedupManager 过滤已抓取的文章
    dedup = get_dedup_manager()
    new_articles = []

    for article in articles:
        is_dup, dup_id = dedup.is_duplicate(article["url"], article["title"])

        if not is_dup:
            new_articles.append(article)

    print(f"[信息] 其中 {len(new_articles)} 篇为新文章")

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
            source="36氪 AI",
            category=category,
            file_path=filepath
        )

    return saved_files


def main():
    """主入口"""
    print("=" * 50)
    print("36氪 AI 新闻抓取脚本")
    print("=" * 50)
    print()

    saved = fetch_36kr()

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