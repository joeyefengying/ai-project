#!/usr/bin/env python3
"""
fetch_jiqizhixin.py — 抓取机器之心 AI 新闻

机器之心: https://www.jiqizhixin.com/

注意：机器之心网站使用 React 动态渲染，有反爬机制。
RSS feed 不可用，网页抓取受限。

建议使用 baoyu-url-to-markdown skill 抓取特定文章：
  /baoyu-url-to-markdown https://www.jiqizhixin.com/articles/...

或者手动访问机器之心文章库页面获取文章 URL：
  https://www.jiqizhixin.com/articles
"""

import sys
import re
import json
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    save_article_to_wiki,
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"

# AI 相关关键词
AI_KEYWORDS = [
    "AI", "人工智能", "机器学习", "深度学习", "大模型", "LLM",
    "ChatGPT", "GPT", "OpenAI", "Claude", "Gemini", "DeepSeek",
    "神经网络", "自然语言处理", "计算机视觉", "NLP",
    "自动驾驶", "机器人", "AGI", "生成式", "AIGC",
]


def fetch_jiqizhixin_articles(max_articles: int = 10) -> list:
    """
    尝试从机器之心获取 AI 文章

    由于网站有反爬机制，此函数可能无法正常工作。
    建议用户手动使用 baoyu-url-to-markdown skill 抓取特定文章。
    """
    # 尝试文章库页面
    url = "https://www.jiqizhixin.com/articles"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    session = requests.Session()

    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[错误] 请求失败: {e}")
        print("[提示] 请使用 /baoyu-url-to-markdown skill 抓取特定文章")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # 查找文章链接
    # 机器之心文章库可能有静态部分
    selectors = [
        "a[href*='/articles/']",
        "a[href*='/content/']",
        ".article-link",
        ".post-link",
        "article a",
    ]

    links = []
    for selector in selectors:
        found = soup.select(selector)
        if found:
            links.extend(found)

    seen_urls = set()
    for link in links:
        href = link.get("href", "")
        if not href:
            continue

        if href.startswith("/"):
            full_url = f"https://www.jiqizhixin.com{href}"
        elif href.startswith("http"):
            full_url = href
        else:
            continue

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        articles.append({
            "title": title,
            "url": full_url,
            "source": "机器之心",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "author": "机器之心",
            "summary": "",
        })

        if len(articles) >= max_articles:
            break

    if not articles:
        print("[提示] 网页解析未找到文章，机器之心使用动态渲染")
        print("[建议] 请手动访问 https://www.jiqizhixin.com/articles 获取文章 URL")
        print("[建议] 然后使用 /baoyu-url-to-markdown 抓取特定文章")

    return articles


def fetch_jiqizhixin():
    """抓取机器之心新闻"""
    config = load_config()
    fetch_config = config.get("fetch_config", {})
    max_articles = fetch_config.get("max_articles_per_fetch", 10)

    print("[信息] 开始抓取: 机器之心 (中文)")
    print("[注意] 机器之心使用 React 动态渲染，抓取可能受限")

    articles = fetch_jiqizhixin_articles(max_articles)

    if not articles:
        print("[提示] 建议使用 baoyu-url-to-markdown skill 抓取特定文章")
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
            source="机器之心",
            category=category,
            file_path=filepath
        )

    return saved_files


def main():
    """主入口"""
    print("=" * 50)
    print("机器之心新闻抓取脚本")
    print("=" * 50)
    print()
    print("注意：机器之心网站使用 React 动态渲染")
    print("建议使用 /baoyu-url-to-markdown skill 抓取特定文章")
    print()

    saved = fetch_jiqizhixin()

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