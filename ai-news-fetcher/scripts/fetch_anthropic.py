#!/usr/bin/env python3
"""
fetch_anthropic.py — 抓取 Anthropic 官方博客文章

Anthropic 官方博客: https://www.anthropic.com/news
使用 BeautifulSoup 网页抓取，因为 Anthropic 没有 RSS feed
"""

import sys
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    generate_article_id,
    save_article_to_wiki,
    safe_request,
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article
from scripts.retry_handler import RetryHandler

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"


def scrape_anthropic_news(max_articles: int = 10) -> list:
    """抓取 Anthropic 新闻页面（带重试机制）"""
    url = "https://www.anthropic.com/news"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # 使用 safe_request 带重试机制
    resp = safe_request(
        url,
        headers=headers,
        timeout=30,
        max_retries=3,
        source="Anthropic Blog"
    )

    if resp is None:
        print("[错误] 请求失败，已重试 3 次")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # 查找新闻文章链接 - Anthropic 使用 Next.js，结构可能变化
    # 尝试多种选择器
    selectors = [
        "a[href*='/news/']",
        "article a",
        ".news-item a",
        "[class*='card'] a",
    ]

    links = []
    for selector in selectors:
        found = soup.select(selector)
        if found:
            links.extend(found)

    # 去重并提取文章信息
    seen_urls = set()
    for link in links:
        href = link.get("href", "")
        if not href:
            continue

        # 构建完整 URL
        if href.startswith("/"):
            full_url = f"https://www.anthropic.com{href}"
        elif href.startswith("https://"):
            full_url = href
        else:
            continue

        # 过滤非新闻链接
        if "/news/" not in full_url and "anthropic.com" in full_url:
            continue

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 提取标题
        title = link.get_text(strip=True)
        if not title:
            # 尝试从父元素或子元素获取标题
            parent = link.parent
            if parent:
                title_elem = parent.find(["h1", "h2", "h3", "h4", "span"])
                if title_elem:
                    title = title_elem.get_text(strip=True)

        if not title:
            title = "Untitled"

        articles.append({
            "title": title,
            "url": full_url,
            "source": "Anthropic Blog",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "author": "Anthropic",
            "summary": "",
        })

    # 限制数量
    return articles[:max_articles]


def fetch_anthropic_blog():
    """抓取 Anthropic 博客"""
    config = load_config()
    fetch_config = config.get("fetch_config", {})
    max_articles = fetch_config.get("max_articles_per_fetch", 10)

    print("[信息] 开始抓取: Anthropic Blog (网页抓取)")

    articles = scrape_anthropic_news(max_articles)

    if not articles:
        print("[警告] 未找到任何文章")
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
            source="Anthropic Blog",
            category=category,
            file_path=filepath
        )

    return saved_files


def main():
    """主入口"""
    print("=" * 50)
    print("Anthropic Blog 抓取脚本")
    print("=" * 50)
    print()

    saved = fetch_anthropic_blog()

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