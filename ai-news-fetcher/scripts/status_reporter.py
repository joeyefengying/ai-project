#!/usr/bin/env python3
"""
status_reporter.py — 运行状态报告生成器

功能：
1. 整合抓取状态、去重状态、错误状态
2. 生成综合运行报告
3. 支持多种输出格式（文本、JSON、Markdown）
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# 项目路径配置
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
LOGS_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"

# 缓存文件
DEDUP_CACHE = CACHE_DIR / "article_dedup.json"
FETCHED_CACHE = CACHE_DIR / "fetched_articles.json"

# 日志文件
ERROR_LOG = LOGS_DIR / "errors.log"
ERROR_STATS = LOGS_DIR / "error_stats.json"
RUN_LOG = PROJECT_ROOT / "agent-run.log"

# 知识库路径（从 CLAUDE.md 配置）
KB_BASE = Path("/Users/zhanghao/Downloads/笔记/笔记")
KB_NEWS_DIR = KB_BASE / "raw" / "news"
KB_TECH_DIR = KB_BASE / "raw" / "tech-articles"


class StatusReporter:
    """运行状态报告生成器"""

    def __init__(self):
        self.report_time = datetime.now()

    def load_json_file(self, file_path: Path) -> Dict:
        """加载 JSON 文件"""
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                return {"error": str(e)}
        return {}

    def get_dedup_stats(self) -> Dict:
        """获取去重状态统计"""
        dedup_data = self.load_json_file(DEDUP_CACHE)

        if "error" in dedup_data:
            return {"status": "error", "message": dedup_data["error"]}

        total = len(dedup_data)
        by_source = defaultdict(int)
        by_category = defaultdict(int)
        by_date = defaultdict(int)

        for article_id, article in dedup_data.items():
            source = article.get("source", "unknown")
            category = article.get("category", "unknown")
            fetched_at = article.get("fetched_at", "")

            by_source[source] += 1
            by_category[category] += 1

            if fetched_at:
                try:
                    dt = datetime.fromisoformat(fetched_at)
                    date_key = dt.strftime("%Y-%m-%d")
                    by_date[date_key] += 1
                except:
                    pass

        # 最近抓取时间
        latest_fetch = None
        for article in dedup_data.values():
            fetched_at = article.get("fetched_at")
            if fetched_at:
                try:
                    dt = datetime.fromisoformat(fetched_at)
                    if latest_fetch is None or dt > latest_fetch:
                        latest_fetch = dt
                except:
                    pass

        return {
            "total_articles": total,
            "by_source": dict(by_source),
            "by_category": dict(by_category),
            "by_date": dict(sorted(by_date.items(), reverse=True)[:7]),  # 最近7天
            "latest_fetch": latest_fetch.isoformat() if latest_fetch else None,
            "cache_file_size": DEDUP_CACHE.stat().st_size if DEDUP_CACHE.exists() else 0
        }

    def get_kb_stats(self) -> Dict:
        """获取知识库状态统计"""
        news_count = 0
        tech_count = 0
        news_files = []
        tech_files = []

        if KB_NEWS_DIR.exists():
            news_files = list(KB_NEWS_DIR.glob("*.md"))
            news_count = len(news_files)

        if KB_TECH_DIR.exists():
            tech_files = list(KB_TECH_DIR.glob("*.md"))
            tech_count = len(tech_files)

        # 计算最近文件
        recent_news = []
        for f in news_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > self.report_time - timedelta(days=7):
                recent_news.append({
                    "name": f.name,
                    "mtime": mtime.isoformat()
                })

        recent_news.sort(key=lambda x: x["mtime"], reverse=True)

        return {
            "news_count": news_count,
            "tech_articles_count": tech_count,
            "total_in_kb": news_count + tech_count,
            "recent_news_7days": len(recent_news),
            "kb_exists": KB_BASE.exists(),
            "news_dir_exists": KB_NEWS_DIR.exists(),
            "tech_dir_exists": KB_TECH_DIR.exists()
        }

    def get_error_stats(self) -> Dict:
        """获取错误状态统计"""
        error_stats = self.load_json_file(ERROR_STATS)

        if "error" in error_stats:
            return {"status": "error", "message": error_stats["error"]}

        total_errors = 0
        total_failures = 0
        by_source = defaultdict(lambda: {"count": 0, "failures": 0})
        by_type = defaultdict(int)

        for key, data in error_stats.items():
            if ':' in key:
                source, error_type = key.split(':')
                count = data.get("count", 0)
                failures = data.get("final_failures", 0)

                total_errors += count
                total_failures += failures
                by_source[source]["count"] += count
                by_source[source]["failures"] += failures
                by_type[error_type] += count

        # 检查错误日志文件大小
        log_size = 0
        log_lines = 0
        if ERROR_LOG.exists():
            log_size = ERROR_LOG.stat().st_size
            with open(ERROR_LOG, 'r', encoding='utf-8') as f:
                log_lines = len(f.readlines())

        return {
            "total_errors": total_errors,
            "total_final_failures": total_failures,
            "by_source": dict(by_source),
            "by_type": dict(by_type),
            "log_file_size": log_size,
            "log_lines": log_lines,
            "has_errors": total_errors > 0
        }

    def get_run_log_stats(self) -> Dict:
        """获取运行日志状态"""
        if not RUN_LOG.exists():
            return {"exists": False}

        try:
            with open(RUN_LOG, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 分析最近运行
            recent_runs = []
            for line in lines[-50:]:  # 最近50行
                line = line.strip()
                if line:
                    recent_runs.append(line)

            return {
                "exists": True,
                "file_size": RUN_LOG.stat().st_size,
                "total_lines": len(lines),
                "recent_activity": recent_runs[-10:]  # 最近10条
            }
        except Exception as e:
            return {"exists": True, "error": str(e)}

    def generate_report(self, format: str = "text") -> str:
        """
        生成综合状态报告

        Args:
            format: 输出格式 (text, json, markdown)

        Returns:
            报告内容
        """
        dedup_stats = self.get_dedup_stats()
        kb_stats = self.get_kb_stats()
        error_stats = self.get_error_stats()
        run_stats = self.get_run_log_stats()

        if format == "json":
            return json.dumps({
                "report_time": self.report_time.isoformat(),
                "dedup": dedup_stats,
                "knowledge_base": kb_stats,
                "errors": error_stats,
                "run_log": run_stats
            }, ensure_ascii=False, indent=2)

        if format == "markdown":
            return self._format_markdown(dedup_stats, kb_stats, error_stats, run_stats)

        return self._format_text(dedup_stats, kb_stats, error_stats, run_stats)

    def _format_text(
        self,
        dedup: Dict,
        kb: Dict,
        errors: Dict,
        run: Dict
    ) -> str:
        """格式化文本报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("AI 新闻抓取系统 - 运行状态报告")
        lines.append("=" * 60)
        lines.append(f"报告时间: {self.report_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 去重状态
        lines.append("-" * 40)
        lines.append("[去重缓存状态]")
        lines.append("-" * 40)

        if "error" in dedup:
            lines.append(f"  错误: {dedup['message']}")
        else:
            lines.append(f"  已抓取文章总数: {dedup['total_articles']}")
            lines.append(f"  缓存文件大小: {dedup['cache_file_size']} bytes")
            lines.append(f"  最近抓取时间: {dedup['latest_fetch'] or '未知'}")
            lines.append("")

            lines.append("  按来源统计:")
            for source, count in sorted(dedup['by_source'].items(), key=lambda x: -x[1]):
                lines.append(f"    - {source}: {count} 篇")

            lines.append("")
            lines.append("  按分类统计:")
            for cat, count in dedup['by_category'].items():
                lines.append(f"    - {cat}: {count} 篇")

            lines.append("")
            lines.append("  最近7天抓取:")
            for date, count in dedup['by_date'].items():
                lines.append(f"    - {date}: {count} 篇")

        lines.append("")

        # 知识库状态
        lines.append("-" * 40)
        lines.append("[知识库状态]")
        lines.append("-" * 40)

        if kb['kb_exists']:
            lines.append(f"  新闻文章: {kb['news_count']} 篇")
            lines.append(f"  技术文章: {kb['tech_articles_count']} 篇")
            lines.append(f"  知识库总数: {kb['total_in_kb']} 篇")
            lines.append(f"  近7天新增新闻: {kb['recent_news_7days']} 篇")
        else:
            lines.append("  知识库目录不存在!")

        lines.append("")

        # 错误状态
        lines.append("-" * 40)
        lines.append("[错误状态]")
        lines.append("-" * 40)

        if "error" in errors:
            lines.append(f"  错误: {errors['message']}")
        elif errors['has_errors']:
            lines.append(f"  总错误次数: {errors['total_errors']}")
            lines.append(f"  最终失败次数: {errors['total_final_failures']}")
            lines.append(f"  错误日志行数: {errors['log_lines']}")

            if errors['by_source']:
                lines.append("")
                lines.append("  按来源错误:")
                for source, data in errors['by_source'].items():
                    lines.append(f"    - {source}: {data['count']}次 ({data['failures']}失败)")

            if errors['by_type']:
                lines.append("")
                lines.append("  按类型错误:")
                for typ, count in errors['by_type'].items():
                    lines.append(f"    - {typ}: {count}次")
        else:
            lines.append("  无错误记录 ✓")

        lines.append("")

        # 运行日志
        lines.append("-" * 40)
        lines.append("[运行日志]")
        lines.append("-" * 40)

        if run.get('exists'):
            lines.append(f"  日志文件存在: ✓")
            lines.append(f"  总行数: {run.get('total_lines', 0)}")
            if run.get('recent_activity'):
                lines.append("")
                lines.append("  最近活动:")
                for activity in run['recent_activity'][:5]:
                    lines.append(f"    {activity[:80]}...")
        else:
            lines.append("  日志文件不存在")

        lines.append("")
        lines.append("=" * 60)
        lines.append("报告结束")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _format_markdown(
        self,
        dedup: Dict,
        kb: Dict,
        errors: Dict,
        run: Dict
    ) -> str:
        """格式化 Markdown 报告"""
        lines = []
        lines.append("# AI 新闻抓取系统 - 运行状态报告")
        lines.append("")
        lines.append(f"> 报告时间: {self.report_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 去重状态
        lines.append("## 去重缓存状态")
        lines.append("")

        if "error" in dedup:
            lines.append(f"**错误**: {dedup['message']}")
        else:
            lines.append(f"- 已抓取文章总数: **{dedup['total_articles']}**")
            lines.append(f"- 最近抓取时间: {dedup['latest_fetch'] or '未知'}")
            lines.append("")

            lines.append("### 按来源统计")
            lines.append("")
            lines.append("| 来源 | 文章数 |")
            lines.append("|------|--------|")
            for source, count in sorted(dedup['by_source'].items(), key=lambda x: -x[1]):
                lines.append(f"| {source} | {count} |")

            lines.append("")
            lines.append("### 按分类统计")
            lines.append("")
            for cat, count in dedup['by_category'].items():
                lines.append(f"- {cat}: {count} 篇")

        lines.append("")

        # 知识库状态
        lines.append("## 知识库状态")
        lines.append("")

        if kb['kb_exists']:
            lines.append(f"- 新闻文章: **{kb['news_count']}** 篇")
            lines.append(f"- 技术文章: **{kb['tech_articles_count']}** 篇")
            lines.append(f"- 知识库总数: **{kb['total_in_kb']}** 篇")
        else:
            lines.append("⚠️ 知识库目录不存在!")

        lines.append("")

        # 错误状态
        lines.append("## 错误状态")
        lines.append("")

        if errors['has_errors']:
            lines.append(f"- 总错误次数: {errors['total_errors']}")
            lines.append(f"- 最终失败次数: {errors['total_final_failures']}")
        else:
            lines.append("✅ 无错误记录")

        lines.append("")
        lines.append("---")
        lines.append("*报告由 status_reporter.py 生成*")

        return "\n".join(lines)

    def get_summary(self) -> str:
        """获取简短摘要"""
        dedup = self.get_dedup_stats()
        kb = self.get_kb_stats()
        errors = self.get_error_stats()

        total_fetched = dedup.get('total_articles', 0)
        total_kb = kb.get('total_in_kb', 0)
        has_errors = errors.get('has_errors', False)

        summary = f"已抓取 {total_fetched} 篇文章，知识库存储 {total_kb} 篇"
        if has_errors:
            summary += f"，存在 {errors['total_errors']} 个错误"
        else:
            summary += "，运行正常"

        return summary


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI 新闻抓取系统运行状态报告生成器"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="输出格式"
    )
    parser.add_argument(
        "--summary", "-s",
        action="store_true",
        help="只输出简短摘要"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="输出到文件"
    )

    args = parser.parse_args()

    reporter = StatusReporter()

    if args.summary:
        result = reporter.get_summary()
    else:
        result = reporter.generate_report(args.format)

    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"报告已保存到: {output_path}")
    else:
        print(result)


if __name__ == "__main__":
    main()