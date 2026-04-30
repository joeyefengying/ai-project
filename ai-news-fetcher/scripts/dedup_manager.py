#!/usr/bin/env python3
"""
dedup_manager.py — 去重管理模块

提供完善的去重功能：
- 基于文章 URL + title 的唯一 ID 生成
- 缓存管理和清理
- 去重状态查询
- 支持多维度去重（URL、标题、内容哈希）
"""

import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ArticleRecord:
    """文章记录"""
    article_id: str
    url: str
    title: str
    source: str
    category: str  # news 或 tech-articles
    fetched_at: str
    file_path: Optional[str] = None
    content_hash: Optional[str] = None


class DedupManager:
    """去重管理器"""

    def __init__(self, cache_dir: str, retention_days: int = 90):
        """
        初始化去重管理器

        Args:
            cache_dir: 缓存目录路径
            retention_days: 记录保留天数（默认90天）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "article_dedup.json"
        self.retention_days = retention_days
        self._cache: Dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """加载缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self) -> None:
        """保存缓存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_id(url: str, title: str) -> str:
        """
        生成文章唯一 ID

        基于 URL + title 的 MD5 哈希，取前12位
        """
        content = f"{url}|{title}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """
        生成内容哈希

        用于检测内容重复（相同内容不同URL的情况）
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_duplicate(self, url: str, title: str, content: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        检查文章是否重复

        Args:
            url: 文章 URL
            title: 文章标题
            content: 可选的文章内容，用于内容哈希去重

        Returns:
            (是否重复, 重复文章的ID或None)
        """
        article_id = self.generate_id(url, title)

        # 检查 URL+标题 去重
        if article_id in self._cache:
            return True, article_id

        # 可选：检查内容哈希去重
        if content:
            content_hash = self.generate_content_hash(content)
            for cached_id, record in self._cache.items():
                if record.get('content_hash') == content_hash:
                    return True, cached_id

        return False, None

    def add_article(
        self,
        url: str,
        title: str,
        source: str,
        category: str,
        file_path: Optional[str] = None,
        content: Optional[str] = None
    ) -> str:
        """
        添加文章记录

        Args:
            url: 文章 URL
            title: 文章标题
            source: 来源
            category: 分类 (news/tech-articles)
            file_path: 保存的文件路径
            content: 可选的文章内容

        Returns:
            文章 ID
        """
        article_id = self.generate_id(url, title)
        content_hash = self.generate_content_hash(content) if content else None

        self._cache[article_id] = {
            'article_id': article_id,
            'url': url,
            'title': title,
            'source': source,
            'category': category,
            'fetched_at': datetime.now().isoformat(),
            'file_path': file_path,
            'content_hash': content_hash
        }

        self._save_cache()
        return article_id

    def remove_article(self, article_id: str) -> bool:
        """
        移除文章记录

        Args:
            article_id: 文章 ID

        Returns:
            是否成功移除
        """
        if article_id in self._cache:
            del self._cache[article_id]
            self._save_cache()
            return True
        return False

    def get_article(self, article_id: str) -> Optional[dict]:
        """获取文章记录"""
        return self._cache.get(article_id)

    def get_stats(self) -> Dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total = len(self._cache)

        # 按来源统计
        by_source = defaultdict(int)
        # 按分类统计
        by_category = defaultdict(int)
        # 按日期统计
        by_date = defaultdict(int)

        for record in self._cache.values():
            by_source[record.get('source', 'unknown')] += 1
            by_category[record.get('category', 'unknown')] += 1

            # 提取日期
            fetched_at = record.get('fetched_at', '')
            if fetched_at:
                date_str = fetched_at.split('T')[0]
                by_date[date_str] += 1

        # 计算缓存大小
        cache_size = 0
        if self.cache_file.exists():
            cache_size = self.cache_file.stat().st_size

        return {
            'total_articles': total,
            'by_source': dict(by_source),
            'by_category': dict(by_category),
            'by_date': dict(sorted(by_date.items(), reverse=True)[:30]),  # 最近30天
            'cache_file_size': cache_size,
            'retention_days': self.retention_days
        }

    def cleanup_old_records(self, days: Optional[int] = None) -> int:
        """
        清理旧记录

        Args:
            days: 保留天数，不指定则使用默认值

        Returns:
            清理的记录数量
        """
        retention = days or self.retention_days
        cutoff_date = datetime.now() - timedelta(days=retention)
        cutoff_str = cutoff_date.isoformat()

        to_remove = []
        for article_id, record in self._cache.items():
            fetched_at = record.get('fetched_at', '')
            if fetched_at < cutoff_str:
                to_remove.append(article_id)

        for article_id in to_remove:
            del self._cache[article_id]

        if to_remove:
            self._save_cache()

        return len(to_remove)

    def find_duplicates_by_url(self) -> List[List[str]]:
        """
        查找 URL 重复的文章

        Returns:
            重复文章组列表
        """
        url_to_ids = defaultdict(list)
        for article_id, record in self._cache.items():
            url = record.get('url', '')
            if url:
                url_to_ids[url].append(article_id)

        return [ids for ids in url_to_ids.values() if len(ids) > 1]

    def find_duplicates_by_title(self, similarity_threshold: float = 0.9) -> List[Tuple[str, str, float]]:
        """
        查找标题相似的文章

        Args:
            similarity_threshold: 相似度阈值

        Returns:
            相似文章对列表 [(id1, id2, similarity), ...]
        """
        # 简单实现：检查完全相同的标题
        title_to_ids = defaultdict(list)
        for article_id, record in self._cache.items():
            title = record.get('title', '').lower().strip()
            if title:
                title_to_ids[title].append(article_id)

        duplicates = []
        for ids in title_to_ids.values():
            if len(ids) > 1:
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        duplicates.append((ids[i], ids[j], 1.0))

        return duplicates

    def export_cache(self, output_path: str) -> None:
        """导出缓存到文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def import_cache(self, input_path: str, merge: bool = True) -> int:
        """
        从文件导入缓存

        Args:
            input_path: 输入文件路径
            merge: 是否合并现有缓存

        Returns:
            导入的记录数量
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            imported = json.load(f)

        if not merge:
            self._cache = imported
        else:
            self._cache.update(imported)

        self._save_cache()
        return len(imported)

    def migrate_from_old_cache(self, old_cache_path: str) -> int:
        """
        从旧的 fetched_articles.json 迁移数据

        Args:
            old_cache_path: 旧缓存文件路径

        Returns:
            迁移的记录数量
        """
        old_path = Path(old_cache_path)
        if not old_path.exists():
            return 0

        with open(old_path, 'r', encoding='utf-8') as f:
            old_cache = json.load(f)

        migrated = 0
        for article_id, record in old_cache.items():
            if article_id not in self._cache:
                # 补充缺失字段
                self._cache[article_id] = {
                    'article_id': article_id,
                    'url': record.get('url', ''),
                    'title': record.get('title', ''),
                    'source': record.get('source', 'unknown'),
                    'category': record.get('category', 'news'),
                    'fetched_at': record.get('fetched_at', datetime.now().isoformat()),
                    'file_path': record.get('file_path'),
                    'content_hash': record.get('content_hash')
                }
                migrated += 1

        if migrated > 0:
            self._save_cache()

        return migrated


def print_status(manager: DedupManager) -> None:
    """打印去重状态"""
    stats = manager.get_stats()

    print("=" * 50)
    print("去重缓存状态")
    print("=" * 50)
    print(f"总文章数: {stats['total_articles']}")
    print(f"缓存文件大小: {stats['cache_file_size']} bytes")
    print(f"保留天数: {stats['retention_days']}")
    print()

    print("按分类统计:")
    for cat, count in stats['by_category'].items():
        print(f"  {cat}: {count}")
    print()

    print("按来源统计:")
    for source, count in stats['by_source'].items():
        print(f"  {source}: {count}")
    print()

    print("最近抓取日期:")
    for date, count in list(stats['by_date'].items())[:10]:
        print(f"  {date}: {count}")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="文章去重管理工具")
    parser.add_argument('--status', action='store_true', help='显示缓存状态')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='清理 N 天前的记录')
    parser.add_argument('--find-duplicates', action='store_true', help='查找重复文章')
    parser.add_argument('--export', type=str, metavar='FILE', help='导出缓存到文件')
    parser.add_argument('--migrate', type=str, metavar='FILE', help='从旧缓存迁移')

    args = parser.parse_args()

    # 初始化管理器
    project_root = Path(__file__).parent.parent
    cache_dir = project_root / "cache"
    manager = DedupManager(str(cache_dir))

    if args.status:
        print_status(manager)
    elif args.cleanup is not None:
        removed = manager.cleanup_old_records(args.cleanup)
        print(f"已清理 {removed} 条记录")
    elif args.find_duplicates:
        url_dups = manager.find_duplicates_by_url()
        title_dups = manager.find_duplicates_by_title()

        print("URL 重复:")
        for group in url_dups:
            print(f"  {group}")

        print("\n标题重复:")
        for id1, id2, sim in title_dups:
            print(f"  {id1} <-> {id2} (相似度: {sim})")
    elif args.export:
        manager.export_cache(args.export)
        print(f"已导出到: {args.export}")
    elif args.migrate:
        migrated = manager.migrate_from_old_cache(args.migrate)
        print(f"已迁移 {migrated} 条记录")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()