#!/usr/bin/env python3
"""
article_classifier.py — 文章分类模块

根据数据源配置自动判断文章应存储到 news 还是 tech-articles 目录。
支持自定义分类规则和关键词匹配。
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_article import load_config

# 分类类型
class ArticleCategory(Enum):
    NEWS = "news"
    TECH_ARTICLE = "tech-articles"
    UNKNOWN = "unknown"


# 默认分类规则
DEFAULT_RULES = {
    # 新闻源 -> news
    "news_sources": [
        "anthropic", "openai", "google_ai", "mit_tr", "venturebeat",
        "36kr", "jiqizhixin", "the_verge", "techcrunch", "wired",
        "anthropic blog", "openai blog", "google ai blog"
    ],
    # 技术文章源 -> tech-articles
    "tech_sources": [
        "huggingface", "arxiv", "papers_with_code", "distill",
        "github", "hugging face blog", "arxiv", "distill.pub"
    ],
    # 内容关键词规则
    "news_keywords": [
        "发布", "announce", "launch", "release", "更新", "update",
        "融资", "funding", "收购", "acquisition", "产品", "product",
        "公司", "company", "市场", "market", "新闻", "news"
    ],
    "tech_keywords": [
        "论文", "paper", "研究", "research", "模型", "model",
        "算法", "algorithm", "架构", "architecture", "训练", "training",
        "推理", "inference", "优化", "optimization", "技术", "technical",
        "教程", "tutorial", "实现", "implementation", "benchmark"
    ]
}


class ArticleClassifier:
    """文章分类器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化分类器

        Args:
            config_path: 配置文件路径（可选）
        """
        self.config = load_config()
        self.rules = self._load_rules()
        self.stats = {
            "total_classified": 0,
            "news_count": 0,
            "tech_count": 0,
            "unknown_count": 0,
            "by_source": {}
        }
        self.stats_file = Path(__file__).parent.parent / "cache" / "classifier_stats.json"

    def _load_rules(self) -> Dict:
        """加载分类规则（合并配置和默认规则）"""
        rules = DEFAULT_RULES.copy()

        # 从配置文件扩展规则
        if self.config:
            # 从配置中提取源名称
            news_sources = self.config.get("news_sources", {})
            tech_sources = self.config.get("tech_sources", {})

            for source_id, source_info in news_sources.items():
                name = source_info.get("name", "").lower()
                if name and name not in rules["news_sources"]:
                    rules["news_sources"].append(name)

            for source_id, source_info in tech_sources.items():
                name = source_info.get("name", "").lower()
                if name and name not in rules["tech_sources"]:
                    rules["tech_sources"].append(name)

        return rules

    def classify_by_source(self, source: str) -> ArticleCategory:
        """
        根据来源名称分类

        Args:
            source: 来源名称（如 "Anthropic Blog", "arXiv"）

        Returns:
            分类结果
        """
        source_lower = source.lower()

        # 检查是否是新闻源
        for news_source in self.rules["news_sources"]:
            if news_source in source_lower:
                return ArticleCategory.NEWS

        # 检查是否是技术文章源
        for tech_source in self.rules["tech_sources"]:
            if tech_source in source_lower:
                return ArticleCategory.TECH_ARTICLE

        return ArticleCategory.UNKNOWN

    def classify_by_content(self, title: str, content: str = "") -> ArticleCategory:
        """
        根据标题和内容关键词分类

        Args:
            title: 文章标题
            content: 文章内容（可选）

        Returns:
            分类结果
        """
        text = (title + " " + content).lower()

        # 计算关键词匹配得分
        news_score = 0
        tech_score = 0

        for keyword in self.rules["news_keywords"]:
            if keyword in text:
                news_score += 1

        for keyword in self.rules["tech_keywords"]:
            if keyword in text:
                tech_score += 1

        # 根据得分判断
        if tech_score > news_score:
            return ArticleCategory.TECH_ARTICLE
        elif news_score > tech_score:
            return ArticleCategory.NEWS

        return ArticleCategory.UNKNOWN

    def classify(self, article: Dict) -> Tuple[ArticleCategory, str]:
        """
        综合分类文章

        优先根据来源分类，如果无法确定则根据内容关键词分类。

        Args:
            article: 文章信息 {title, url, source, content/summary}

        Returns:
            (分类结果, 分类依据说明)
        """
        source = article.get("source", "")
        title = article.get("title", "")
        content = article.get("content", article.get("summary", ""))

        # 1. 首先根据来源分类
        source_category = self.classify_by_source(source)
        if source_category != ArticleCategory.UNKNOWN:
            reason = f"来源匹配: '{source}' -> {source_category.value}"
            self._update_stats(source, source_category)
            return source_category, reason

        # 2. 如果来源无法确定，根据内容分类
        content_category = self.classify_by_content(title, content)
        if content_category != ArticleCategory.UNKNOWN:
            reason = f"内容关键词匹配 -> {content_category.value}"
            self._update_stats(source, content_category)
            return content_category, reason

        # 3. 默认为 news（保守策略）
        reason = "无法确定分类，默认为 news"
        self._update_stats(source, ArticleCategory.NEWS)
        return ArticleCategory.NEWS, reason

    def _update_stats(self, source: str, category: ArticleCategory):
        """更新分类统计"""
        self.stats["total_classified"] += 1

        if category == ArticleCategory.NEWS:
            self.stats["news_count"] += 1
        elif category == ArticleCategory.TECH_ARTICLE:
            self.stats["tech_count"] += 1
        else:
            self.stats["unknown_count"] += 1

        # 按来源统计
        if source:
            if source not in self.stats["by_source"]:
                self.stats["by_source"][source] = {
                    "news": 0, "tech-articles": 0, "unknown": 0
                }
            self.stats["by_source"][source][category.value] += 1

    def get_category_for_article(self, article: Dict) -> str:
        """
        获取文章应存储的目录名称

        Args:
            article: 文章信息

        Returns:
            目录名称: "news" 或 "tech-articles"
        """
        category, reason = self.classify(article)
        return category.value

    def get_stats(self) -> Dict:
        """获取分类统计"""
        return self.stats.copy()

    def save_stats(self):
        """保存统计到文件"""
        cache_dir = Path(__file__).parent.parent / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def load_stats(self) -> Dict:
        """加载历史统计"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def print_stats(self):
        """打印分类统计"""
        stats = self.get_stats()
        print("=" * 50)
        print("文章分类统计")
        print("=" * 50)
        print(f"总分类文章数: {stats['total_classified']}")
        print(f"  - 新闻 (news): {stats['news_count']}")
        print(f"  - 技术文章 (tech-articles): {stats['tech_count']}")
        print(f"  - 未确定: {stats['unknown_count']}")
        print()

        if stats['by_source']:
            print("按来源统计:")
            for source, counts in stats['by_source'].items():
                total = sum(counts.values())
                print(f"  {source}: {total} 篇")
                if counts['news']:
                    print(f"    - news: {counts['news']}")
                if counts['tech-articles']:
                    print(f"    - tech-articles: {counts['tech-articles']}")

    def add_custom_rule(self, source_pattern: str, category: str):
        """
        添加自定义分类规则

        Args:
            source_pattern: 来源名称匹配模式
            category: "news" 或 "tech-articles"
        """
        if category == "news":
            if source_pattern.lower() not in self.rules["news_sources"]:
                self.rules["news_sources"].append(source_pattern.lower())
        elif category == "tech-articles":
            if source_pattern.lower() not in self.rules["tech_sources"]:
                self.rules["tech_sources"].append(source_pattern.lower())


# 全局分类器实例
_classifier_instance: Optional[ArticleClassifier] = None


def get_classifier() -> ArticleClassifier:
    """获取全局分类器实例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ArticleClassifier()
    return _classifier_instance


def classify_article(article: Dict) -> str:
    """
    快捷函数：分类文章并返回目录名称

    Args:
        article: 文章信息

    Returns:
        目录名称: "news" 或 "tech-articles"
    """
    classifier = get_classifier()
    return classifier.get_category_for_article(article)


def main():
    """测试和命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="文章分类器")
    parser.add_argument("--status", action="store_true", help="显示分类统计")
    parser.add_argument("--test", nargs="+", help="测试分类（输入来源名称）")
    parser.add_argument("--add-rule", nargs=2, metavar=("SOURCE", "CATEGORY"),
                        help="添加自定义规则")

    args = parser.parse_args()

    classifier = ArticleClassifier()

    if args.status:
        classifier.print_stats()
        return

    if args.test:
        print("\n分类测试:")
        for source in args.test:
            category = classifier.classify_by_source(source)
            print(f"  '{source}' -> {category.value}")
        return

    if args.add_rule:
        source, category = args.add_rule
        classifier.add_custom_rule(source, category)
        print(f"[添加规则] '{source}' -> {category}")
        return

    # 默认：显示规则
    print("=" * 50)
    print("当前分类规则")
    print("=" * 50)
    print("\n新闻源 (news):")
    for s in classifier.rules["news_sources"]:
        print(f"  - {s}")
    print("\n技术文章源 (tech-articles):")
    for s in classifier.rules["tech_sources"]:
        print(f"  - {s}")
    print("\n新闻关键词:")
    print(f"  {', '.join(classifier.rules['news_keywords'][:6])}...")
    print("\n技术关键词:")
    print(f"  {', '.join(classifier.rules['tech_keywords'][:6])}...")

    # 测试示例
    print("\n" + "=" * 50)
    print("示例分类测试")
    print("=" * 50)

    test_articles = [
        {"title": "Claude 3.5 Sonnet 发布", "source": "Anthropic Blog"},
        {"title": "新研究：Transformer 架构优化", "source": "arXiv"},
        {"title": "OpenAI 发布 GPT-5", "source": "OpenAI Blog"},
        {"title": "Fine-tuning LLMs 教程", "source": "Hugging Face Blog"},
    ]

    for article in test_articles:
        category, reason = classifier.classify(article)
        print(f"\n{article['title']}")
        print(f"  来源: {article['source']}")
        print(f"  分类: {category.value}")
        print(f"  依据: {reason}")


if __name__ == "__main__":
    main()