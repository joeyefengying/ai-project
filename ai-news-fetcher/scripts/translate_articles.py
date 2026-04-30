#!/usr/bin/env python3
"""
translate_articles.py — 翻译文章为中文

翻译标题和内容为中文，原文只用链接引用。
"""

import os
import re
import time
from pathlib import Path
from datetime import datetime

# 知识库路径
WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"

# 翻译服务选择
TRANSLATE_SERVICE = os.environ.get("TRANSLATE_SERVICE", "google")


def translate_with_google(text: str) -> str:
    """使用 Google Translate 翻译"""
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='zh-CN')

        # 分段翻译长文本
        if len(text) > 4500:
            chunks = []
            paragraphs = text.split('\n\n')
            current = ""
            for p in paragraphs:
                if len(current) + len(p) < 4500:
                    current += p + '\n\n'
                else:
                    if current:
                        chunks.append(current)
                    current = p + '\n\n'
            if current:
                chunks.append(current)

            results = []
            for chunk in chunks:
                try:
                    results.append(translator.translate(chunk))
                    time.sleep(1)
                except:
                    results.append(chunk)
            return '\n\n'.join(results)
        else:
            return translator.translate(text)
    except ImportError:
        print("[警告] 未安装 deep-translator")
        return text
    except Exception as e:
        print(f"[失败] {str(e)}")
        return text


def translate_text(text: str) -> str:
    """翻译文本"""
    return translate_with_google(text)


def parse_markdown(filepath: str) -> dict:
    """解析 Markdown 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 front matter
    if content.startswith('---'):
        parts = content.split('---', 2)
        front_matter = parts[1].strip() if len(parts) >= 3 else ""
        body = parts[2].strip() if len(parts) >= 3 else content
    else:
        front_matter = ""
        body = content

    # 提取属性
    title = ""
    original_title = ""
    source = ""
    author = ""
    published = ""

    for line in front_matter.split('\n'):
        if line.startswith('title:'):
            title = re.sub(r'title:\s*["\']?', '', line).strip().rstrip('"\'')
        elif line.startswith('original_title:'):
            original_title = re.sub(r'original_title:\s*["\']?', '', line).strip().rstrip('"\'')
        elif line.startswith('source:'):
            source = re.sub(r'source:\s*["\']?', '', line).strip().rstrip('"\'')
        elif line.startswith('author:'):
            author = re.sub(r'author:\s*["\']?', '', line).strip().rstrip('"\'')
        elif line.startswith('published:'):
            published = re.sub(r'published:\s*["\']?', '', line).strip().rstrip('"\'')

    # 如果没有 original_title，用当前 title 作为原标题
    if not original_title:
        original_title = title

    # 提取正文（去除原文对照部分）
    if '## 原文对照' in body:
        body = body.split('## 原文对照')[0].strip()

    # 去除重复标题和原标题行
    lines = body.split('\n')
    clean_lines = []

    for i, line in enumerate(lines):
        # 跳过所有标题行（正文开头）
        if line.startswith('# ') and i < 10:
            continue
        # 跳过 "> 原标题:" 行
        if line.startswith('> 原标题'):
            continue
        # 跳过 "> 来源:" 行（会有重复）
        if line.startswith('> 来源：') and i < 10:
            continue
        # 跳过 "---" 分隔符（正文中的）
        if line.strip() == '---':
            continue
        # 跳过原文链接行（正文中的）
        if '**原文链接**' in line:
            continue
        # 跳过错误的原文引用行
        if "article['source']" in line:
            continue
        # 跳过旧的原文引用行（重复的）
        if line.startswith('> 原文：') and i > 5:
            continue
        # 跳过空标题行后的空行
        if line.strip() == '' and i < 15:
            continue
        clean_lines.append(line)

    body = '\n'.join(clean_lines).strip()

    return {
        "title": title,
        "original_title": original_title,
        "source": source,
        "author": author,
        "published": published,
        "body": body,
        "front_matter": front_matter
    }


def format_date(date_str: str) -> str:
    """格式化日期为中文格式"""
    # 尝试解析各种日期格式
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",  # Wed, 29 Apr 2026 04:00:00 GMT
        "%a, %d %b %Y %H:%M:%S",     # Wed, 29 Apr 2026 04:00:00
        "%Y-%m-%d",                   # 2026-04-29
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y年%m月%d日")
        except:
            continue

    return date_str


def translate_article(filepath: str) -> str:
    """翻译单篇文章"""
    print(f"\n[处理] {filepath}")

    article = parse_markdown(filepath)

    # 翻译标题
    print("[翻译] 标题...")
    translated_title = translate_text(article["title"])
    print(f"[结果] {translated_title}")

    # 翻译正文
    print("[翻译] 正文...")
    translated_body = translate_text(article["body"])
    print(f"[结果] {len(translated_body)} 字符")

    # 格式化日期
    date_str = format_date(article["published"])

    # 提取来源名称
    source_name = ""
    if "openai.com" in article["source"]:
        source_name = "OpenAI"
    elif "anthropic.com" in article["source"]:
        source_name = "Anthropic"
    elif "arxiv.org" in article["source"]:
        source_name = "arXiv"
    elif "huggingface.co" in article["source"]:
        source_name = "Hugging Face"
    elif "36kr.com" in article["source"]:
        source_name = "36氪"
    elif "jiqizhixin.com" in article["source"]:
        source_name = "机器之心"
    else:
        source_name = "AI新闻"

    # 生成新内容（纯中文，原文只用链接引用）
    new_content = f"""---
title: "{translated_title}"
source: "{article['source']}"
author: "{article['author']}"
published: "{article['published']}"
created: "{datetime.now().strftime('%Y-%m-%d')}"
tags:
  - "AI"
translated: true
---

# {translated_title}

> 来源：{source_name} | {date_str}

{translated_body}

> [查看原文]({article['source']})
"""

    # 保存
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[保存] {filepath}")
    return filepath


def batch_translate(directory: str, limit: int = 100):
    """批量翻译"""
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"[错误] 目录不存在: {directory}")
        return

    md_files = list(dir_path.glob("*.md"))
    print(f"[信息] 找到 {len(md_files)} 篇文章")

    for i, filepath in enumerate(md_files[:limit]):
        print(f"\n{'='*50}")
        print(f"[{i+1}/{min(len(md_files), limit)}]")
        print(f"{'='*50}")

        translate_article(str(filepath))
        time.sleep(2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="翻译文章为中文")
    parser.add_argument("file", nargs="?", help="单个文件路径")
    parser.add_argument("--news", action="store_true", help="翻译 news 目录")
    parser.add_argument("--tech", action="store_true", help="翻译 tech-articles 目录")
    parser.add_argument("--all", action="store_true", help="翻译所有目录")
    parser.add_argument("--limit", type=int, default=100, help="限制处理数量")

    args = parser.parse_args()

    if args.file:
        translate_article(args.file)
    elif args.news:
        batch_translate(f"{WIKI_ROOT}/raw/news", args.limit)
    elif args.tech:
        batch_translate(f"{WIKI_ROOT}/raw/tech-articles", args.limit)
    elif args.all:
        batch_translate(f"{WIKI_ROOT}/raw/news", args.limit)
        batch_translate(f"{WIKI_ROOT}/raw/tech-articles", args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()