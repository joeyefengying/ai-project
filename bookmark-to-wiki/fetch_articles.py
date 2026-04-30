#!/usr/bin/env python3
"""
fetch_articles.py - 批量抓取 URL 内容并转换为 Markdown

依赖 baoyu-url-to-markdown skill，通过 bun/npx 调用。

用法：
    python3 fetch_articles.py --input urls.txt --output ~/Downloads/笔记/笔记/raw/articles/
    python3 fetch_articles.py --input urls.txt --output ./articles/ --limit 10
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
import re


def sanitize_filename(title):
    """将标题转换为安全的文件名"""
    # 移除特殊字符
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    # 限制长度
    if len(title) > 80:
        title = title[:80]
    # 空标题用日期替代
    if not title.strip():
        title = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return title.strip()


def find_bun_runtime():
    """查找 bun 运行时"""
    # 尝试 bun
    try:
        subprocess.run(["bun", "--version"], capture_output=True, check=True)
        return "bun"
    except:
        pass

    # 尝试 npx
    try:
        subprocess.run(["npx", "--version"], capture_output=True, check=True)
        return "npx -y bun"
    except:
        pass

    return None


def find_skill_dir():
    """查找 baoyu-url-to-markdown skill 目录"""
    skill_path = Path.home() / ".claude" / "skills" / "baoyu-url-to-markdown"
    if skill_path.exists():
        return skill_path
    return None


def fetch_url(url, output_path, skill_dir, bun_runtime):
    """抓取单个 URL"""
    main_script = skill_dir / "scripts" / "main.ts"

    # 构建命令
    cmd = f"{bun_runtime} {main_script} '{url}' -o '{output_path}'"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return True, output_path
        else:
            return False, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        return False, "Timeout (>60s)"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="批量抓取 URL 内容")
    parser.add_argument("--input", type=str, required=True, help="URL 列表文件（每行一个 URL）")
    parser.add_argument("--output", type=str, required=True, help="输出目录")
    parser.add_argument("--limit", type=int, help="限制抓取数量（用于测试）")
    parser.add_argument("--delay", type=float, default=2.0, help="每次抓取间隔（秒）")
    parser.add_argument("--concurrency", type=int, default=1, help="并发数（暂不支持）")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已存在的文件")

    args = parser.parse_args()

    # 检查依赖
    bun_runtime = find_bun_runtime()
    if not bun_runtime:
        print("ERROR: 未找到 bun 或 npx，请先安装")
        print("  brew install bun")
        sys.exit(1)

    skill_dir = find_skill_dir()
    if not skill_dir:
        print("ERROR: 未找到 baoyu-url-to-markdown skill")
        sys.exit(1)

    print(f"运行时: {bun_runtime}")
    print(f"Skill 目录: {skill_dir}")

    # 读取 URL 列表
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: 输入文件不存在: {input_path}")
        sys.exit(1)

    urls = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # 支持 URL\tTitle 格式
                parts = line.split("\t")
                url = parts[0]
                title = parts[1] if len(parts) > 1 else ""
                urls.append((url, title))

    if args.limit:
        urls = urls[:args.limit]

    print(f"待抓取 URL 数量: {len(urls)}")

    # 创建输出目录
    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}")

    # 批量抓取
    success_count = 0
    fail_count = 0
    skip_count = 0
    failed_urls = []

    for i, (url, title) in enumerate(urls):
        print(f"\n[{i+1}/{len(urls)}] {url}")

        # 生成文件名
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        safe_title = sanitize_filename(title)
        filename = f"{date_prefix}-{safe_title}.md"
        output_path = output_dir / filename

        # 跳过已存在的文件
        if args.skip_existing and output_path.exists():
            print(f"  ⊘ 跳过: 已存在")
            skip_count += 1
            continue

        # 抓取
        success, result = fetch_url(url, str(output_path), skill_dir, bun_runtime)

        if success:
            print(f"  ✓ 成功: {output_path.name}")
            success_count += 1
        else:
            print(f"  ✗ 失败: {result}")
            fail_count += 1
            failed_urls.append((url, result))

        # 延迟
        if i < len(urls) - 1:
            time.sleep(args.delay)

    # 输出统计
    print(f"\n{'='*50}")
    print(f"完成！成功: {success_count}, 失败: {fail_count}, 跳过: {skip_count}")

    if failed_urls:
        print("\n失败列表：")
        for url, reason in failed_urls:
            print(f"  - {url}: {reason}")

        # 保存失败列表
        fail_file = output_dir / "failed_urls.txt"
        with open(fail_file, "w", encoding="utf-8") as f:
            for url, reason in failed_urls:
                f.write(f"{url}\t{reason}\n")
        print(f"\n失败列表已保存: {fail_file}")

    # 生成下一步提示
    print(f"\n下一步：在 Claude Code 中运行")
    print(f"  /llm-wiki 批量消化 {output_dir}")


if __name__ == "__main__":
    main()