#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""digest_articles.py - llm-wiki integration script

Manage article digestion status and integrate with llm-wiki skill.

Features:
1. Scan raw/news/ and raw/tech-articles/ directories
2. Check undigested articles against .wiki-cache.json
3. Generate digest commands for batch processing
4. Track digestion status

Usage:
  python digest_articles.py --list          # List pending articles
  python digest_articles.py --digest        # Prepare batch digest
  python digest_articles.py --status        # Show digest statistics
"""

import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List

WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"
WIKI_CACHE_FILE = Path(WIKI_ROOT) / ".wiki-cache.json"
DIGEST_TRACK_FILE = Path(__file__).parent.parent / "cache" / "digest_status.json"


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file"""
    content = filepath.read_bytes()
    hash_value = hashlib.sha256(content).hexdigest()
    return f"sha256:{hash_value}"


def load_wiki_cache() -> Dict:
    """Load llm-wiki cache file"""
    if not WIKI_CACHE_FILE.exists():
        return {"version": 1, "entries": {}}
    with open(WIKI_CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_digest_status() -> Dict:
    """Load digest status tracking file"""
    if not DIGEST_TRACK_FILE.exists():
        return {"tracked": {}}
    with open(DIGEST_TRACK_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_digest_status(status: Dict) -> None:
    """Save digest status tracking file"""
    DIGEST_TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DIGEST_TRACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def scan_raw_directories() -> List[Path]:
    """Scan markdown files in raw/news/ and raw/tech-articles/"""
    wiki_path = Path(WIKI_ROOT)
    raw_path = wiki_path / "raw"
    articles = []
    
    news_dir = raw_path / "news"
    if news_dir.exists():
        articles.extend(news_dir.glob("*.md"))
    
    tech_dir = raw_path / "tech-articles"
    if tech_dir.exists():
        articles.extend(tech_dir.glob("*.md"))
    
    return articles


def get_relative_path(filepath: Path) -> str:
    """Get path relative to wiki root"""
    wiki_path = Path(WIKI_ROOT)
    try:
        return str(filepath.relative_to(wiki_path))
    except ValueError:
        return str(filepath)


def is_digested(filepath: Path, wiki_cache: Dict) -> bool:
    """Check if article has been digested"""
    relative_path = get_relative_path(filepath)
    return relative_path in wiki_cache.get("entries", {})


def find_pending_articles() -> List[Dict]:
    """Find pending articles to digest"""
    wiki_cache = load_wiki_cache()
    articles = scan_raw_directories()
    pending = []
    
    for article_path in articles:
        if not is_digested(article_path, wiki_cache):
            relative_path = get_relative_path(article_path)
            hash_value = compute_file_hash(article_path)
            pending.append({
                "path": str(article_path),
                "relative_path": relative_path,
                "hash": hash_value,
                "filename": article_path.name,
            })
    
    return pending


def list_pending_articles() -> None:
    """List pending articles"""
    pending = find_pending_articles()
    
    print("=" * 60)
    print("Pending Articles List")
    print("=" * 60)
    print()
    
    if not pending:
        print("All articles have been digested!")
        return
    
    print(f"Found {len(pending)} pending articles:")
    print()
    
    for i, article in enumerate(pending, 1):
        print(f"{i}. {article['filename']}")
        print(f"   Path: {article['relative_path']}")
    
    print()
    print("-" * 60)
    print("Digest commands (run in Claude Code):")
    print("-" * 60)
    print()
    for article in pending:
        print(f"/llm-wiki digest {article['path']}")


def show_digest_status() -> None:
    """Show digest status statistics"""
    wiki_cache = load_wiki_cache()
    articles = scan_raw_directories()
    
    total = len(articles)
    digested = len(wiki_cache.get("entries", {}))
    pending = total - digested
    
    news_count = 0
    tech_count = 0
    for article_path in articles:
        relative = get_relative_path(article_path)
        if "news" in relative:
            news_count += 1
        elif "tech-articles" in relative:
            tech_count += 1
    
    print("=" * 60)
    print("Digest Status Statistics")
    print("=" * 60)
    print()
    print(f"Wiki Root: {WIKI_ROOT}")
    print(f"Total Articles: {total}")
    print(f"Digested: {digested}")
    print(f"Pending: {pending}")
    print()
    print(f"News Articles (raw/news/): {news_count}")
    print(f"Tech Articles (raw/tech-articles/): {tech_count}")
    print()
    
    if total > 0:
        progress = 100 * digested // total
        print(f"Progress: {digested}/{total} ({progress}%)")
    
    entries = wiki_cache.get("entries", {})
    if entries:
        print()
        print("-" * 60)
        print("Recent Digests:")
        print("-" * 60)
        recent = sorted(
            entries.items(),
            key=lambda x: x[1].get("ingested_at", ""),
            reverse=True
        )[:5]
        for path, info in recent:
            ingested_at = info.get("ingested_at", "unknown")
            print(f"  {Path(path).name} - {ingested_at}")


def digest_articles_interactive() -> None:
    """Prepare batch digest in interactive mode"""
    pending = find_pending_articles()
    
    if not pending:
        print("All articles have been digested!")
        return
    
    print("=" * 60)
    print(f"Preparing to digest {len(pending)} articles")
    print("=" * 60)
    print()
    
    print("Run the following commands in Claude Code:")
    print()
    for i, article in enumerate(pending, 1):
        print(f"[{i}] /llm-wiki digest {article['path']}")
    
    print()
    print("-" * 60)
    print("Tip: Digest all articles in a directory:")
    print(f"  /llm-wiki digest {WIKI_ROOT}/raw/news/")
    print("-" * 60)


def auto_digest_check() -> Dict:
    """Auto check for pending articles (for other scripts)"""
    pending = find_pending_articles()
    return {
        "pending_count": len(pending),
        "pending_paths": [a["path"] for a in pending],
        "digest_command": "/llm-wiki digest",
    }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="llm-wiki integration script - Manage article digestion"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all pending articles"
    )
    
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Prepare batch digest"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show digest status statistics"
    )
    
    parser.add_argument(
        "--auto-check",
        action="store_true",
        help="Auto check mode (JSON output)"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_pending_articles()
    elif args.digest:
        digest_articles_interactive()
    elif args.status:
        show_digest_status()
    elif args.auto_check:
        result = auto_digest_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        show_digest_status()


if __name__ == "__main__":
    main()
