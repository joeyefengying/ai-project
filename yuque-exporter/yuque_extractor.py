"""语雀知识库导出工具 (基于 Cookies 认证)

将语雀个人版知识库导出为 Markdown 格式，保留原有的目录层级结构。

使用方法:
1. 安装依赖: pip install httpx html2text pyyaml
2. 导出 cookies.txt 文件到当前目录
3. 运行: python yuque_extractor.py

Cookies 获取方法:
1. 在浏览器登录语雀 (https://www.yuque.com)
2. 安装 Cookie-Editor 扩展
3. 点击扩展 → Export → Netscape 格式
4. 保存为 cookies.txt
"""
from __future__ import annotations

import json
import os
import re
import tarfile
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import html2text
import httpx
import yaml


# ── 配置 ───────────────────────────────────────────────────

@dataclass
class ExportConfig:
    """导出配置"""
    cookie_file: str = "cookies.txt"
    output_dir: str = "yuque-export"
    target_dir: str = ""
    delay: float = 5.0
    generate_file_list: bool = True


# ── Cookie 解析 ─────────────────────────────────────────────

def load_cookie_from_file(cookie_file: str | Path) -> tuple[str, str]:
    """从 Netscape Cookie 文件中提取语雀 Cookie（加载所有 cookies）"""
    cookie_path = Path(cookie_file)
    if not cookie_path.exists():
        return "", ""

    # 加载所有 cookies（文档页面需要完整的 cookies 才能获取内容）
    # 不过滤域名，因为可能有一些辅助 cookies
    cookies: dict[str, str] = {}
    csrf_token = ""

    with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            name = parts[5].strip()
            value = parts[6].strip()

            cookies[name] = value
            if name == "yuque_ctoken":
                csrf_token = value

    return "; ".join(f"{k}={v}" for k, v in cookies.items()), csrf_token


# ── HTML 转 Markdown ─────────────────────────────────────────

def html_to_markdown(html_content: str) -> str:
    """将语雀 HTML 内容转换为 Markdown"""
    if not html_content or not html_content.strip():
        return ""

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0
    h.single_line_break = False

    html_content = re.sub(r'<!doctype[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<div[^>]*class="lake-content"[^>]*>', '', html_content)
    html_content = re.sub(r'</div>$', '', html_content.strip())

    markdown = h.handle(html_content)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    return markdown.strip()


# ── 数据模型 ────────────────────────────────────────────────

@dataclass
class YuqueDoc:
    """语雀文档"""
    id: int
    title: str
    slug: str
    content: str = ""
    markdown: str = ""
    uuid: str = ""
    parent_uuid: str = ""
    level: int = 0


@dataclass
class YuqueRepo:
    """语雀知识库"""
    id: int
    name: str
    slug: str
    public: int = 0
    items_count: int = 0


@dataclass
class TocItem:
    """目录项"""
    type: str  # META, TITLE, DOC
    title: str = ""
    uuid: str = ""
    url: str = ""
    doc_id: int = 0
    level: int = 0
    parent_uuid: str = ""
    visible: bool = True


# ── 语雀 API 客户端 ──────────────────────────────────────────

class YuqueClient:
    """语雀 API 客户端"""

    BASE_URL = "https://www.yuque.com"

    def __init__(self, cookie_str: str, csrf_token: str):
        self.cookie = cookie_str
        self.csrf_token = csrf_token
        self.headers = {
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.yuque.com/",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.client = httpx.Client(headers=self.headers, follow_redirects=True, timeout=60.0)
        self._user_login: str | None = None

    def get_user_login(self) -> str:
        """获取用户登录名"""
        if self._user_login:
            return self._user_login

        resp = self.client.get(f"{self.BASE_URL}/dashboard")
        resp.raise_for_status()
        html = resp.text

        patterns = [
            r'window\.appData = JSON\.parse\(decodeURIComponent\("([^"]*)"\)\)',
            r'appData = JSON\.parse\(decodeURIComponent\("([^"]*)"\)\)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                encoded = match.group(1)
                decoded = urllib.parse.unquote(encoded)
                try:
                    data = json.loads(decoded)
                    login = data.get("me", {}).get("login", "")
                    if login:
                        self._user_login = login
                        return login
                except json.JSONDecodeError:
                    continue

        return ""

    def list_repos(self) -> list[YuqueRepo]:
        """获取知识库列表"""
        resp = self.client.get(f"{self.BASE_URL}/api/mine/books")
        resp.raise_for_status()
        data = resp.json()
        repos = []
        for item in data.get("data", []):
            repos.append(YuqueRepo(
                id=item["id"],
                name=item["name"],
                slug=item["slug"],
                public=item.get("public", 0),
                items_count=item.get("items_count", 0),
            ))
        return repos

    def export_book(self, book_id: int, user_login: str, book_slug: str) -> bytes:
        """导出知识库为 lakebook"""
        referer = f"{self.BASE_URL}/{user_login}/{book_slug}"

        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        headers["X-CToken"] = self.csrf_token
        headers["Referer"] = referer

        resp = self.client.post(
            f"{self.BASE_URL}/api/books/{book_id}/export",
            headers=headers,
            json={"type": "lakebook"}
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("data", {}).get("state") != "success":
            raise ValueError(f"导出失败: {result}")

        download_url = result["data"]["url"]
        resp = self.client.get(download_url)
        resp.raise_for_status()
        return resp.content


# ── 目录结构解析 ───────────────────────────────────────────

def parse_toc_yml(toc_yml: str) -> list[TocItem]:
    """解析目录 YAML"""
    if not toc_yml:
        return []

    try:
        toc_list = yaml.safe_load(toc_yml)
    except yaml.YAMLError:
        return []

    items = []
    for item in toc_list:
        items.append(TocItem(
            type=item.get("type", ""),
            title=item.get("title", ""),
            uuid=item.get("uuid", ""),
            url=item.get("url", ""),
            doc_id=item.get("doc_id", 0) or 0,
            level=item.get("level", 0),
            parent_uuid=item.get("parent_uuid", ""),
            visible=item.get("visible", 1) == 1,
        ))
    return items


def build_directory_tree(toc_items: list[TocItem]) -> dict:
    """构建目录树，返回 doc_id -> 目录路径 的映射"""
    # 构建 uuid -> TocItem 映射
    uuid_map = {item.uuid: item for item in toc_items}

    # 构建 doc_id -> 目录路径 映射
    doc_paths: dict[int, str] = {}

    def get_parent_path(item: TocItem) -> str:
        """递归获取父级路径"""
        if not item.parent_uuid:
            return ""

        parent = uuid_map.get(item.parent_uuid)
        if not parent:
            return ""

        parent_path = get_parent_path(parent)
        if parent.type == "TITLE" and parent.title:
            # 清理文件夹名称
            clean_title = re.sub(r'[\/\\:*?"<>|]', "-", parent.title)
            if parent_path:
                return f"{parent_path}/{clean_title}"
            else:
                return clean_title
        return parent_path

    for item in toc_items:
        if item.type == "DOC" and item.doc_id and item.visible:
            parent_path = get_parent_path(item)
            doc_paths[item.doc_id] = parent_path

    return doc_paths


# ── Lakebook 解析 ───────────────────────────────────────────

def parse_lakebook(tar_content: bytes) -> tuple[list[YuqueDoc], dict]:
    """解析 lakebook tar 文件"""
    docs = []
    meta = {}

    with tempfile.NamedTemporaryFile(suffix=".lakebook", delete=False) as tmp:
        tmp.write(tar_content)
        tmp_path = tmp.name

    try:
        with tarfile.open(tmp_path, "r") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".json"):
                    f = tar.extractfile(member)
                    if f:
                        content = f.read().decode("utf-8")
                        data = json.loads(content)

                        if member.name.endswith("$meta.json"):
                            meta_raw = data.get("meta", "{}")
                            if isinstance(meta_raw, str):
                                meta = json.loads(meta_raw)
                            else:
                                meta = meta_raw
                        else:
                            doc_data = data.get("doc", {})
                            if doc_data:
                                html_content = doc_data.get("body", "")
                                docs.append(YuqueDoc(
                                    id=doc_data.get("id", 0) or 0,
                                    title=doc_data.get("title", ""),
                                    slug=doc_data.get("slug", ""),
                                    content=html_content,
                                    markdown=html_to_markdown(html_content) if html_content else "",
                                ))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return docs, meta


def fetch_doc_content(client: httpx.Client, user_login: str, book_slug: str, doc_slug: str) -> str:
    """单独获取文档内容（通过 /markdown 页面请求）

    用于 lakebook 导出内容为空的情况。
    需要访问 /markdown 页面才能获取完整内容。
    """
    if not doc_slug:
        return ""

    # 使用 /markdown 端点获取完整内容
    url = f"https://www.yuque.com/{user_login}/{book_slug}/{doc_slug}/markdown"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

        # 提取 appData
        pattern = r'window\.appData = JSON\.parse\(decodeURIComponent\("([^"]*)"\)\)'
        match = re.search(pattern, html)
        if match:
            encoded = match.group(1)
            decoded = urllib.parse.unquote(encoded)
            try:
                data = json.loads(decoded)
                doc = data.get("doc", {})

                # 从 _cachedContent 获取内容
                cached = doc.get("_cachedContent", {})
                body = cached.get("_cache_decrypted_body", "")
                if body and len(body) > 50:
                    return body

                # 尝试获取 ASL 格式内容（语雀内部格式）
                body_asl = cached.get("_cache_decrypted_body_asl", "")
                if body_asl and len(body_asl) > 50:
                    return body_asl

                # 备选：检查其他字段
                for key in ["body", "body_html", "body_asl", "body_draft", "body_draft_asl"]:
                    val = doc.get(key, "")
                    if val and len(val) > 50:
                        return val
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"    获取文档失败: {e}")

    return ""


# ── 导出器 ───────────────────────────────────────────────────

class YuqueExporter:
    """语雀知识库导出器"""

    def __init__(self, config: ExportConfig):
        self.config = config
        cookie_str, csrf_token = load_cookie_from_file(config.cookie_file)
        if not cookie_str:
            raise ValueError(f"无法加载 cookies: {config.cookie_file}")
        if not csrf_token:
            raise ValueError("cookies 中没有 yuque_ctoken")

        self.client = YuqueClient(cookie_str, csrf_token)
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.user_login = ""
        self.exported_files: list[str] = []

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        return re.sub(r'[\/\\:*?"<>|]', "-", name)

    def export_repo(self, repo: YuqueRepo) -> int:
        """导出知识库，保留目录层级"""
        print(f"\n{'='*50}")
        print(f"导出知识库: {repo.name} ({repo.slug})")
        print(f"文档数量: {repo.items_count}")
        print(f"{'='*50}")

        user_login = self.user_login or self.client.get_user_login()
        self.user_login = user_login

        # 创建知识库根目录
        repo_dir = self.output_path / repo.name
        repo_dir.mkdir(parents=True, exist_ok=True)

        print("正在导出 lakebook...")
        try:
            tar_content = self.client.export_book(repo.id, user_login, repo.slug)
        except Exception as e:
            print(f"导出失败: {e}")
            return 0

        print("正在解析目录结构...")
        docs, meta = parse_lakebook(tar_content)

        # 解析目录结构
        toc_yml = meta.get("book", {}).get("tocYml", "")
        toc_items = parse_toc_yml(toc_yml)
        doc_paths = build_directory_tree(toc_items)

        # 创建所有需要的子目录
        all_paths = set(doc_paths.values())
        for path in all_paths:
            if path:
                full_path = repo_dir / path
                full_path.mkdir(parents=True, exist_ok=True)

        # 写入文档
        count = 0
        for doc in docs:
            if not doc.title or not doc.id:
                continue

            # 获取文档的目录路径
            dir_path = doc_paths.get(doc.id, "")
            if dir_path:
                doc_dir = repo_dir / dir_path
            else:
                doc_dir = repo_dir

            # 确保目录存在
            doc_dir.mkdir(parents=True, exist_ok=True)

            print(f"  保存: {dir_path}/{doc.title}" if dir_path else f"  保存: {doc.title}")

            safe_title = self._sanitize_filename(doc.title)
            filepath = doc_dir / f"{safe_title}.md"

            content = doc.markdown if doc.markdown else doc.content
            url_slug = doc.slug or ""

            # 如果内容为空，单独获取文档内容
            if not content or len(content) < 50:
                print(f"    内容为空，单独获取...")
                html_content = fetch_doc_content(
                    self.client.client,
                    user_login,
                    repo.slug,
                    url_slug
                )
                if html_content:
                    content = html_to_markdown(html_content)
                    print(f"    获取成功: {len(content)} chars")
                    time.sleep(0.5)  # 避免请求过快
                else:
                    print(f"    获取失败: 无内容")

            # 检查内容是否已包含标题，避免重复
            has_title = content.strip().startswith('#') if content else False

            if has_title:
                body = content
            else:
                body = f"# {doc.title}\n\n{content}"

            file_content = f"""---
source_type: yuque
title: {doc.title}
yuque_repo: {repo.name}
yuque_path: {dir_path if dir_path else '/'}
yuque_url: https://www.yuque.com/{user_login}/{repo.slug}/{url_slug}
tags:
  - 语雀导入
---

{body}
"""
            filepath.write_text(file_content, encoding="utf-8")
            self.exported_files.append(str(filepath))
            count += 1

        print(f"\n知识库「{repo.name}」导出完成！共 {count} 篇文档")
        return count

    def copy_to_target(self) -> int:
        """复制到目标目录"""
        if not self.config.target_dir:
            return 0

        target_path = Path(self.config.target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        print(f"\n正在复制到: {target_path}")

        copied = 0
        for repo_dir in self.output_path.iterdir():
            if repo_dir.is_dir():
                target_repo = target_path / repo_dir.name
                if target_repo.exists():
                    # 合并，不删除已有内容
                    pass
                target_repo.mkdir(parents=True, exist_ok=True)

                for md_file in repo_dir.rglob("*.md"):
                    rel_path = md_file.relative_to(repo_dir)
                    target_file = target_repo / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(md_file.read_text(encoding="utf-8"), encoding="utf-8")
                    copied += 1

        print(f"复制完成！共 {copied} 个文件")
        return copied

    def generate_file_list(self) -> str:
        """生成文件列表"""
        if not self.config.target_dir:
            return ""

        target_path = Path(self.config.target_dir)
        list_file = target_path / "语雀文件列表.md"

        files = []
        for md_file in sorted(target_path.rglob("*.md")):
            if md_file.name != "语雀文件列表.md":
                files.append(str(md_file))

        list_content = f"""# 语雀导出文件列表

共 {len(files)} 个文件，生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 文件路径列表

{chr(10).join(files)}
"""
        list_file.write_text(list_content, encoding="utf-8")
        print(f"\n文件列表: {list_file}")
        return str(list_file)

    def export_all(self) -> tuple[int, str]:
        """导出所有知识库"""
        print("正在获取用户信息...")
        self.user_login = self.client.get_user_login()
        print(f"登录用户: @{self.user_login}")

        print("\n正在获取知识库列表...")
        repos = self.client.list_repos()
        print(f"共 {len(repos)} 个知识库")

        total = 0
        failed = []

        for i, repo in enumerate(repos, 1):
            print(f"\n[{i}/{len(repos)}]", end=" ")
            if repo.items_count == 0:
                print(f"跳过空知识库: {repo.name}")
                continue
            try:
                count = self.export_repo(repo)
                total += count
                time.sleep(self.config.delay)
            except Exception as e:
                print(f"失败: {e}")
                failed.append(repo.slug)
                time.sleep(15)

        print(f"\n{'='*50}")
        print(f"全部导出完成！共 {total} 篇文档")
        print(f"失败: {failed}")
        print(f"{'='*50}")

        if self.config.target_dir:
            self.copy_to_target()

        file_list = ""
        if self.config.generate_file_list and self.config.target_dir:
            file_list = self.generate_file_list()

        return total, file_list

    def list_repos(self) -> list[YuqueRepo]:
        """列出知识库"""
        self.user_login = self.client.get_user_login()
        print(f"登录用户: @{self.user_login}")

        repos = self.client.list_repos()
        print(f"\n知识库列表 ({len(repos)} 个):")
        print("-" * 60)
        for repo in repos:
            print(f"  [{repo.id}] {repo.name} ({repo.items_count} 篇)")
        return repos


# ── CLI ───────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="语雀知识库导出工具（保留目录层级）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python yuque_extractor.py --list
  python yuque_extractor.py --repo wu01e5 -t /path/to/语雀
  python yuque_extractor.py --all -t /path/to/语雀

然后运行:
  /llm-wiki 帮我消化这个文件：/path/to/语雀/语雀文件列表.md
"""
    )

    parser.add_argument("--list", action="store_true", help="列出知识库")
    parser.add_argument("--repo", type=str, help="导出指定知识库 (slug)")
    parser.add_argument("--all", action="store_true", help="导出所有知识库")
    parser.add_argument("-c", "--cookie", default="cookies.txt", help="Cookies 文件")
    parser.add_argument("-o", "--output", default="yuque-export", help="临时目录")
    parser.add_argument("-t", "--target", default="", help="目标笔记目录")
    parser.add_argument("--no-file-list", action="store_true", help="不生成文件列表")

    args = parser.parse_args()

    config = ExportConfig(
        cookie_file=args.cookie,
        output_dir=args.output,
        target_dir=args.target,
        delay=5.0,
        generate_file_list=not args.no_file_list,
    )

    try:
        exporter = YuqueExporter(config)

        if args.list:
            exporter.list_repos()
        elif args.repo:
            repos = exporter.list_repos()
            repo = next((r for r in repos if r.slug == args.repo), None)
            if repo:
                exporter.export_repo(repo)
                if config.target_dir:
                    exporter.copy_to_target()
                    if config.generate_file_list:
                        exporter.generate_file_list()
            else:
                print(f"错误：找不到知识库 '{args.repo}'")
                return 1
        else:
            total, file_list = exporter.export_all()
            if file_list:
                print(f"\n下一步: /llm-wiki 帮我消化这个文件：{file_list}")

    except ValueError as e:
        print(f"错误: {e}")
        return 1
    except httpx.HTTPStatusError as e:
        print(f"HTTP 错误: {e}")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())