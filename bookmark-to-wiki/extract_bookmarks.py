#!/usr/bin/env python3
"""
extract_bookmarks.py - 解析浏览器收藏夹，提取 URL 列表

支持：Chrome、Safari、Firefox

用法：
    python3 extract_bookmarks.py --browser chrome
    python3 extract_bookmarks.py --browser safari --output urls.txt
    python3 extract_bookmarks.py --browser chrome --file ~/path/to/Bookmarks
"""

import argparse
import json
import os
import plistlib
import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def find_chrome_bookmarks():
    """查找 Chrome 收藏夹默认位置"""
    paths = [
        "~/Library/Application Support/Google/Chrome/Default/Bookmarks",
        "~/Library/Application Support/Google/Chrome/Profile 1/Bookmarks",
        "~/.config/google-chrome/Default/Bookmarks",  # Linux
        "~/.config/chromium/Default/Bookmarks",  # Linux Chromium
        os.path.expandvars("%LOCALAPPDATA%/Google/Chrome/User Data/Default/Bookmarks"),  # Windows
    ]
    for p in paths:
        expanded = Path(p).expanduser()
        if expanded.exists():
            return expanded
    return None


def find_safari_bookmarks():
    """查找 Safari 收藏夹默认位置"""
    path = "~/Library/Safari/Bookmarks.plist"
    expanded = Path(path).expanduser()
    if expanded.exists():
        return expanded
    return None


def find_firefox_bookmarks():
    """查找 Firefox 收藏夹（places.sqlite）"""
    base_path = "~/Library/Application Support/Firefox/Profiles"
    expanded = Path(base_path).expanduser()
    if not expanded.exists():
        return None

    # 查找包含 places.sqlite 的 profile 目录
    for profile_dir in expanded.iterdir():
        places_db = profile_dir / "places.sqlite"
        if places_db.exists():
            return places_db
    return None


def parse_chrome_bookmarks(filepath, folder_filter=None):
    """解析 Chrome 收藏夹 JSON 文件

    Args:
        filepath: 收藏夹文件路径
        folder_filter: 只提取指定文件夹下的书签（支持子文件夹名，如 "优秀系列文章"）
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = []
    found_folders = []  # 记录找到的匹配文件夹

    def walk_bookmarks(node, current_folder="", in_target_folder=False):
        # 如果指定了文件夹过滤
        if folder_filter:
            # 检查当前节点是否是目标文件夹
            if node.get("type") == "folder":
                folder_name = node.get("name", "")
                # 如果文件夹名匹配，或已经在目标文件夹内
                if folder_name == folder_filter or in_target_folder:
                    if folder_name == folder_filter:
                        found_folders.append(folder_name)
                    for child in node.get("children", []):
                        walk_bookmarks(child, folder_name, True)
                else:
                    # 不在目标文件夹，继续搜索
                    for child in node.get("children", []):
                        walk_bookmarks(child, folder_name, False)
            elif node.get("type") == "url" and in_target_folder:
                url = node.get("url")
                name = node.get("name", "")
                if url and not url.startswith("chrome://"):
                    urls.append((url, name))
        else:
            # 无过滤，提取全部
            if node.get("type") == "url":
                url = node.get("url")
                name = node.get("name", "")
                if url and not url.startswith("chrome://"):
                    urls.append((url, name))
            elif node.get("type") == "folder":
                for child in node.get("children", []):
                    walk_bookmarks(child)

    # Chrome 书签根节点有 "bookmark_bar" 和 "other"
    root = data.get("roots", {})
    for key in ["bookmark_bar", "other", "synced"]:
        if key in root:
            walk_bookmarks(root[key])

    if folder_filter and not found_folders:
        print(f"WARNING: 未找到文件夹 '{folder_filter}'")

    return urls


def parse_safari_bookmarks(filepath):
    """解析 Safari 收藏夹 plist 文件"""
    with open(filepath, "rb") as f:
        data = plistlib.load(f)

    urls = []

    def walk_bookmarks(node):
        if isinstance(node, dict):
            children = node.get("Children", [])
            for child in children:
                walk_bookmarks(child)
            # 检查是否是书签条目
            url = node.get("URLString")
            title = node.get("URIDictionary", {}).get("title", "")
            if url and not url.startswith("file://"):
                urls.append((url, title))

    walk_bookmarks(data)
    return urls


def parse_firefox_bookmarks(filepath):
    """解析 Firefox places.sqlite 数据库"""
    urls = []
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()

    # Firefox 书签表结构
    query = """
        SELECT moz_places.url, moz_bookmarks.title
        FROM moz_bookmarks
        JOIN moz_places ON moz_bookmarks.fk = moz_places.id
        WHERE moz_bookmarks.type = 1
        AND moz_places.url NOT LIKE 'place:%'
        AND moz_places.url NOT LIKE 'about:%'
    """
    cursor.execute(query)
    urls = [(row[0], row[1] or "") for row in cursor.fetchall()]
    conn.close()
    return urls


def main():
    parser = argparse.ArgumentParser(description="解析浏览器收藏夹，提取 URL 列表")
    parser.add_argument("--browser", choices=["chrome", "safari", "firefox"], required=True, help="浏览器类型")
    parser.add_argument("--file", type=str, help="自定义收藏夹文件路径")
    parser.add_argument("--output", type=str, default="urls.txt", help="输出文件路径")
    parser.add_argument("--limit", type=int, help="限制提取数量（用于测试）")
    parser.add_argument("--folder", type=str, help="只提取指定文件夹下的书签（Chrome/Safari）")

    args = parser.parse_args()

    # 确定收藏夹文件路径
    if args.file:
        filepath = Path(args.file).expanduser()
    else:
        if args.browser == "chrome":
            filepath = find_chrome_bookmarks()
        elif args.browser == "safari":
            filepath = find_safari_bookmarks()
        elif args.browser == "firefox":
            filepath = find_firefox_bookmarks()

    if not filepath or not filepath.exists():
        print(f"ERROR: 未找到 {args.browser} 收藏夹文件")
        print(f"请手动指定路径：--file ~/path/to/Bookmarks")
        sys.exit(1)

    print(f"解析收藏夹：{filepath}")
    if args.folder:
        print(f"只提取文件夹：{args.folder}")

    # 解析收藏夹
    if args.browser == "chrome":
        urls = parse_chrome_bookmarks(filepath, args.folder)
    elif args.browser == "safari":
        urls = parse_safari_bookmarks(filepath)
    elif args.browser == "firefox":
        urls = parse_firefox_bookmarks(filepath)

    # 限制数量
    if args.limit:
        urls = urls[:args.limit]

    print(f"提取到 {len(urls)} 个 URL")

    # 过滤不需要抓取的 URL
    skip_patterns = [
        "chrome://",
        "file://",
        "about:",
        "place:",
        # AI 工具主页（不需要抓取）
        "chat.deepseek.com",
        "chat.openai.com",
        "claude.ai",
        "yuanbao.tencent.com/chat",
        "kimi.moonshot.cn",
        "tongyi.aliyun.com",
        # 搜索引擎
        "google.com/search",
        "bing.com/search",
        "baidu.com/s",
        # 需要登录的站点
        "x.com",  # Twitter 需要登录
        "twitter.com",
        # 实时数据页面
        "coinglass.com",
        "tradingview.com",
        "binance.com",
        # 内部页面
        "localhost",
        "127.0.0.1",
    ]

    filtered_urls = []
    for url, title in urls:
        skip = False
        for pattern in skip_patterns:
            if pattern in url.lower():
                skip = True
                break
        if not skip:
            filtered_urls.append((url, title))

    skipped_count = len(urls) - len(filtered_urls)
    print(f"过滤后 {len(filtered_urls)} 个可抓取 URL（跳过 {skipped_count} 个）")

    # 输出到文件
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        for url, title in filtered_urls:
            f.write(f"{url}\t{title}\n")

    print(f"已保存到：{output_path}")

    # 显示前 10 条
    print("\n前 10 条可抓取 URL：")
    for i, (url, title) in enumerate(filtered_urls[:10]):
        print(f"{i+1}. {title[:50]}... → {url[:60]}...")


if __name__ == "__main__":
    main()