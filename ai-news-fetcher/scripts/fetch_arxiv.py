#!/usr/bin/env python3
"""
fetch_arxiv.py — 抓取 arXiv AI 论文

arXiv API 文档: https://arxiv.org/help/api/user-manual
分类: cs.AI (Artificial Intelligence)
"""

import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import (
    load_config,
    get_dedup_manager,
    save_article_to_wiki
)
from scripts.dedup_manager import DedupManager
from scripts.article_classifier import classify_article
from scripts.retry_handler import RetryHandler, ErrorType

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"

# arXiv API 配置
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_NS = {'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'}


def fetch_arxiv_papers(max_results: int = 10, category: str = "cs.AI") -> List[Dict]:
    """
    从 arXiv API 获取最新 AI 论文（带重试机制）

    Args:
        max_results: 最大返回数量
        category: arXiv 分类 (cs.AI, cs.LG, cs.CL 等)

    Returns:
        论文列表
    """
    # 构建查询参数
    query = f"cat:{category}"
    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }

    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    print(f"[信息] 请求 arXiv API: {url}")

    handler = RetryHandler(max_retries=3)
    max_retries = 3

    for retry_count in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'AI-News-Fetcher/1.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read().decode('utf-8')

            papers = parse_arxiv_response(xml_data)
            print(f"[成功] arXiv: 获取 {len(papers)} 篇论文")
            return papers

        except Exception as e:
            error_type = handler.classify_error(e)
            context = f"arXiv API 请求: {url}"

            if retry_count < max_retries and handler.should_retry(error_type):
                delay = handler.calculate_delay(retry_count + 1)
                handler.log_error(e, context, "arXiv", retry_count, final_failure=False)
                print(f"[重试] arXiv: {retry_count + 1}/{max_retries}, 等待 {delay:.1f}s")
                time.sleep(delay)
            else:
                handler.log_error(e, context, "arXiv", retry_count, final_failure=True)
                print(f"[失败] arXiv: {str(e)}")
                return []

    return []


def parse_arxiv_response(xml_data: str) -> List[Dict]:
    """
    解析 arXiv API 返回的 Atom XML

    Args:
        xml_data: XML 字符串

    Returns:
        论文列表
    """
    papers = []
    root = ET.fromstring(xml_data)

    entries = root.findall('atom:entry', ARXIV_NS)

    for entry in entries:
        paper = {}

        # 标题
        title_elem = entry.find('atom:title', ARXIV_NS)
        paper['title'] = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else 'Untitled'

        # 摘要
        summary_elem = entry.find('atom:summary', ARXIV_NS)
        paper['content'] = summary_elem.text.strip() if summary_elem is not None else ''
        paper['summary'] = paper['content'][:500] + '...' if len(paper['content']) > 500 else paper['content']

        # 作者列表
        authors = []
        for author in entry.findall('atom:author', ARXIV_NS):
            name_elem = author.find('atom:name', ARXIV_NS)
            if name_elem is not None:
                authors.append(name_elem.text)
        paper['author'] = ', '.join(authors[:3])
        if len(authors) > 3:
            paper['author'] += f' et al. ({len(authors)} authors)'

        # 发布日期
        published_elem = entry.find('atom:published', ARXIV_NS)
        if published_elem is not None:
            pub_date = published_elem.text[:10]  # YYYY-MM-DD
            paper['published'] = pub_date
        else:
            paper['published'] = datetime.now().strftime("%Y-%m-%d")

        # arXiv ID 和链接
        id_elem = entry.find('atom:id', ARXIV_NS)
        if id_elem is not None:
            paper['url'] = id_elem.text
            # 提取 arXiv ID
            arxiv_id = id_elem.text.split('/')[-1]
            paper['arxiv_id'] = arxiv_id
        else:
            paper['url'] = ''
            paper['arxiv_id'] = ''

        # PDF 链接
        paper['pdf_url'] = paper['url'].replace('abs', 'pdf') if paper['url'] else ''

        # 分类标签
        categories = []
        for cat in entry.findall('atom:category', ARXIV_NS):
            term = cat.get('term', '')
            if term:
                categories.append(term)
        paper['categories'] = categories
        paper['source'] = 'arXiv'

        papers.append(paper)

    return papers


def save_paper_to_wiki(paper: Dict, wiki_root: str) -> str:
    """
    将论文保存到知识库（自定义格式，更适合学术论文）

    Args:
        paper: 论文信息
        wiki_root: 知识库根路径

    Returns:
        保存的文件路径
    """
    from scripts.fetch_article import save_article_to_wiki

    # 添加额外信息到 content
    enhanced_content = f"""## 摘要

{paper.get('content', paper.get('summary', ''))}

## 论文信息

- **arXiv ID**: {paper.get('arxiv_id', 'N/A')}
- **作者**: {paper.get('author', 'Unknown')}
- **分类**: {', '.join(paper.get('categories', []))}
- **发布日期**: {paper.get('published', 'Unknown')}

## 链接

- [论文主页]({paper.get('url', '')})
- [PDF下载]({paper.get('pdf_url', '')})
"""

    paper['content'] = enhanced_content

    return save_article_to_wiki(
        paper,
        category='tech-articles',
        wiki_root=wiki_root
    )


def main():
    print("=" * 50)
    print("arXiv AI 论文抓取脚本")
    print("=" * 50)
    print()

    config = load_config()
    fetch_config = config.get('fetch_config', {})
    max_articles = fetch_config.get('max_articles_per_fetch', 10)

    # 从配置获取分类
    arxiv_config = config.get('tech_sources', {}).get('arxiv_ai', {})
    category = "cs.AI"  # 默认 AI 分类

    print(f"[信息] 抓取分类: {category}")
    print(f"[信息] 最大抓取数: {max_articles} 篇")
    print()

    # 获取论文
    papers = fetch_arxiv_papers(max_results=max_articles, category=category)

    if not papers:
        print("[警告] 未获取到任何论文")
        return

    print(f"[信息] 获取到 {len(papers)} 篇论文")
    print()

    # 使用 DedupManager 过滤已抓取的论文
    dedup = get_dedup_manager()
    new_papers = []

    for paper in papers:
        is_dup, dup_id = dedup.is_duplicate(paper['url'], paper['title'])

        if not is_dup:
            new_papers.append(paper)
        else:
            print(f"[跳过] 已缓存: {paper['title'][:50]}...")

    print(f"[信息] 其中 {len(new_papers)} 篇为新论文")
    print()

    # 保存新论文到知识库
    saved_files = []
    for paper in new_papers:
        # 使用分类器自动判断分类
        category = classify_article(paper)
        filepath = save_paper_to_wiki(paper, wiki_root=WIKI_ROOT)
        saved_files.append(filepath)
        print(f"[分类] {category} | [保存] {paper['title'][:60]}...")
        print(f"       -> {filepath}")

        # 添加到去重缓存
        dedup.add_article(
            url=paper['url'],
            title=paper['title'],
            source="arXiv",
            category=category,
            file_path=filepath
        )

    # 输出统计
    print()
    print("=" * 50)
    print(f"抓取完成: 新增 {len(saved_files)} 篇 AI 论文")
    print("=" * 50)

    if saved_files:
        print("\n[下一步] 请使用 /llm-wiki 消化这些论文:")
        for f in saved_files:
            print(f"  /llm-wiki 帮我消化 {f}")


if __name__ == "__main__":
    main()