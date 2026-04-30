#!/usr/bin/env python3
"""
fetch_full_and_translate.py — 抓取完整文章内容并翻译成中文

使用 requests + html2text 抓取完整内容，然后翻译标题和正文为中文。
"""

import os
import re
import json
import sys
import time
import requests
import html2text
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# Claude API 翻译配置
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# 知识库路径
WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"


def fetch_full_content(url: str, timeout: int = 30) -> tuple[str, str, str]:
    """
    抓取网页完整内容并转换为 Markdown

    Returns:
        (title, content_md, html) 或 (None, None, None) 如果失败
    """
    print(f"[抓取] {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        html = resp.text

        # 解析 HTML
        soup = BeautifulSoup(html, 'html.parser')

        # 提取标题
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else "Untitled"

        # 清理标题（去除网站名称后缀）
        title = re.sub(r'\s*[|\-–]\s*[^|\-–]+$', '', title)

        # 提取主要内容区域
        content_areas = [
            soup.find('article'),
            soup.find('main'),
            soup.find('div', class_=re.compile(r'(content|post|article|entry|body)', re.I)),
            soup.find('div', id=re.compile(r'(content|post|article|entry)', re.I)),
        ]

        main_content = None
        for area in content_areas:
            if area:
                main_content = area
                break

        if not main_content:
            main_content = soup.find('body') or soup

        # 移除不需要的元素
        for tag in main_content.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style', 'form', 'iframe']):
            tag.decompose()

        for tag in main_content.find_all(class_=re.compile(r'(sidebar|comment|footer|nav|menu|ads)', re.I)):
            tag.decompose()

        # 转换为 Markdown
        h2t = html2text.HTML2Text()
        h2t.ignore_links = False
        h2t.ignore_images = False
        h2t.ignore_emphasis = False
        h2t.body_width = 0  # 不换行

        content_md = h2t.handle(str(main_content))

        # 清理多余空白
        content_md = re.sub(r'\n{3,}', '\n\n', content_md)
        content_md = content_md.strip()

        print(f"[成功] 获取 {len(content_md)} 字符")
        return title, content_md, html

    except requests.RequestException as e:
        print(f"[失败] 请求错误: {str(e)}")
        return None, None, None
    except Exception as e:
        print(f"[失败] {str(e)}")
        return None, None, None


def translate_with_claude(text: str, target_lang: str = "中文", is_title: bool = False) -> str:
    """
    使用 Claude API 翻译文本
    """
    if not CLAUDE_API_KEY:
        print("[警告] 未设置 ANTHROPIC_API_KEY，跳过翻译")
        return text

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    except ImportError:
        print("[警告] 未安装 anthropic 库，跳过翻译。请运行: pip install anthropic")
        return text

    if is_title:
        prompt = f"""将以下标题翻译成简洁的中文标题，不要添加额外内容，保持技术术语准确：

"{text}"

中文标题："""
    else:
        prompt = f"""请将以下文章内容翻译成中文。要求：
1. 保持原文的格式和结构（标题、段落、列表等）
2. 技术术语保持准确性，首次出现时可保留英文并在括号注明中文
3. 代码块和技术示例保持原样不翻译
4. 保持专业、流畅的中文表达

内容：
{text}

翻译后的内容："""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        translated = message.content[0].text.strip()
        print(f"[成功] 翻译完成 ({len(translated)} 字符)")
        return translated

    except Exception as e:
        print(f"[失败] 翻译错误: {str(e)}")
        return text


def save_article(
    original_title: str,
    translated_title: str,
    original_content: str,
    translated_content: str,
    url: str,
    category: str,
    author: str = "Unknown",
    published: str = None
) -> str:
    """
    保存文章到知识库
    """
    wiki_path = Path(WIKI_ROOT)

    if category == "news":
        target_dir = wiki_path / "raw" / "news"
    else:
        target_dir = wiki_path / "raw" / "tech-articles"

    target_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    date_str = datetime.now().strftime("%Y-%m-%d")
    title_slug = re.sub(r'[^\w\s-]', '', translated_title)
    title_slug = re.sub(r'[\s]+', '-', title_slug).lower()[:60]
    filename = f"{date_str}-{title_slug}.md"

    filepath = target_dir / filename

    # 写入文件
    published_str = published or date_str

    content = f"""---
title: "{translated_title}"
original_title: "{original_title}"
source: "{url}"
author: "{author}"
published: "{published_str}"
created: "{date_str}"
tags:
  - "{category}"
  - "AI"
  - "translated"
---

# {translated_title}

> 原标题: {original_title} | 来源: {url}

{translated_content}

---

## 原文对照

{original_content}

---

**原文链接**: {url}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[保存] {filepath}")
    return str(filepath)


def process_article(url: str, category: str = "news", skip_translate: bool = False) -> dict:
    """
    处理单篇文章：抓取 + 翻译 + 保存
    """
    # 抓取完整内容
    original_title, original_content, html = fetch_full_content(url)

    if not original_content:
        return {"success": False, "error": "抓取失败"}

    # 翻译
    if skip_translate or not CLAUDE_API_KEY:
        translated_title = original_title
        translated_content = original_content
    else:
        print("[翻译] 正在翻译标题...")
        translated_title = translate_with_claude(original_title, "中文", is_title=True)

        print("[翻译] 正在翻译正文...")
        translated_content = translate_with_claude(original_content, "中文")

    # 保存
    filepath = save_article(
        original_title=original_title,
        translated_title=translated_title,
        original_content=original_content,
        translated_content=translated_content,
        url=url,
        category=category
    )

    return {
        "success": True,
        "filepath": filepath,
        "title": translated_title,
        "original_title": original_title
    }


def batch_process_from_cache():
    """
    从缓存中获取未翻译的文章 URL 并批量处理
    """
    cache_file = Path("/Users/zhanghao/Downloads/learning/ai project/ai-news-fetcher/cache/fetched_articles.json")

    if not cache_file.exists():
        print("[错误] 缓存文件不存在")
        return

    with open(cache_file, 'r') as f:
        cache = json.load(f)

    urls = [item['url'] for item in cache.values() if 'url' in item]

    print(f"[信息] 从缓存获取 {len(urls)} 个 URL")

    results = []
    for i, url in enumerate(urls[:10]):  # 先处理前 10 个测试
        print(f"\n{'='*50}")
        print(f"[{i+1}/{min(len(urls), 10)}] {url}")
        print(f"{'='*50}")

        # 根据来源判断类别
        if 'arxiv' in url or 'huggingface' in url:
            category = "tech-articles"
        else:
            category = "news"

        result = process_article(url, category)
        results.append(result)

        time.sleep(2)  # 避免请求过快

    success = sum(1 for r in results if r["success"])
    print(f"\n{'='*50}")
    print(f"完成: {success}/{len(results)} 成功")
    print(f"{'='*50}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="抓取完整文章并翻译成中文")
    parser.add_argument("url", nargs="?", help="文章 URL")
    parser.add_argument("--category", default="news", choices=["news", "tech-articles"],
                        help="文章类别")
    parser.add_argument("--batch", action="store_true", help="从缓存批量处理")
    parser.add_argument("--skip-translate", action="store_true", help="跳过翻译")

    args = parser.parse_args()

    if args.batch:
        batch_process_from_cache()
    elif args.url:
        result = process_article(args.url, args.category, args.skip_translate)
        if result["success"]:
            print(f"\n✅ 处理成功")
            print(f"标题: {result['title']}")
            print(f"原文: {result['original_title']}")
            print(f"文件: {result['filepath']}")
        else:
            print(f"\n❌ 处理失败: {result['error']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()