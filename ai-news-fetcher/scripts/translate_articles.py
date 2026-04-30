#!/usr/bin/env python3
"""
translate_articles.py — 翻译知识库中的文章为中文

支持多种翻译服务：Claude API、OpenAI、DeepL、Google Translate
"""

import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

# 知识库路径
WIKI_ROOT = "/Users/zhanghao/Downloads/笔记/笔记"

# 翻译服务选择
TRANSLATE_SERVICE = os.environ.get("TRANSLATE_SERVICE", "openai")  # openai, claude, deepl, google


def translate_with_openai(text: str, is_title: bool = False) -> str:
    """使用 OpenAI API 翻译"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[警告] 未设置 OPENAI_API_KEY")
        return text

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
    except ImportError:
        print("[警告] 未安装 openai 库")
        return text

    if is_title:
        prompt = f"将以下标题翻译成简洁的中文标题，保持技术术语准确，不要添加额外内容：\n\n{text}\n\n中文标题："
    else:
        prompt = f"""请将以下内容翻译成中文。要求：
1. 保持原文格式和结构
2. 技术术语保持准确，首次出现时可保留英文并在括号注明中文
3. 代码块保持原样不翻译
4. 保持专业、流畅的中文表达

内容：
{text}

翻译："""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 快速且便宜
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[失败] {str(e)}")
        return text


def translate_with_google(text: str, is_title: bool = False) -> str:
    """使用 Google Translate 翻译（免费）"""
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='zh-CN')

        # 分段翻译（Google Translator 有长度限制）
        if len(text) > 4500:
            chunks = []
            sentences = text.split('\n\n')
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < 4500:
                    current_chunk += sentence + '\n\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence + '\n\n'
            if current_chunk:
                chunks.append(current_chunk)

            translated_chunks = []
            for chunk in chunks:
                try:
                    translated = translator.translate(chunk)
                    translated_chunks.append(translated)
                    time.sleep(1)  # 避免请求过快
                except Exception as e:
                    print(f"[警告] 分段翻译失败: {str(e)}")
                    translated_chunks.append(chunk)

            return '\n\n'.join(translated_chunks)
        else:
            return translator.translate(text)
    except ImportError:
        print("[警告] 未安装 deep-translator 库，请运行: pip install deep-translator")
        return text
    except Exception as e:
        print(f"[失败] {str(e)}")
        return text


def translate_text(text: str, is_title: bool = False) -> str:
    """根据配置选择翻译服务"""
    if TRANSLATE_SERVICE == "openai":
        return translate_with_openai(text, is_title)
    elif TRANSLATE_SERVICE == "google":
        return translate_with_google(text, is_title)
    else:
        print(f"[警告] 未知的翻译服务: {TRANSLATE_SERVICE}")
        return text


def parse_markdown(filepath: str) -> dict:
    """解析 Markdown 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            front_matter = parts[1].strip()
            body = parts[2].strip()
        else:
            front_matter = ""
            body = content
    else:
        front_matter = ""
        body = content

    title_match = re.search(r'title:\s*["\']?(.+?)["\']?\n', front_matter)
    title = title_match.group(1) if title_match else "Untitled"

    return {
        "front_matter": front_matter,
        "body": body,
        "title": title,
        "raw": content
    }


def translate_article(filepath: str, keep_original: bool = True) -> str:
    """翻译单篇文章"""
    print(f"\n[处理] {filepath}")

    article = parse_markdown(filepath)

    # 翻译标题
    print("[翻译] 标题...")
    translated_title = translate_text(article["title"], is_title=True)
    print(f"[结果] {translated_title}")

    # 翻译正文
    print("[翻译] 正文...")
    translated_body = translate_text(article["body"])
    print(f"[结果] {len(translated_body)} 字符")

    # 更新 front matter
    new_front = article["front_matter"]
    new_front = re.sub(
        r'title:\s*["\']?.+?["\']?\n',
        f'title: "{translated_title}"\n',
        new_front
    )
    # 添加 original_title 和 translated
    if 'original_title:' not in new_front:
        new_front += f'original_title: "{article["title"]}"\n'
    if 'translated:' not in new_front:
        new_front += 'translated: true\n'

    # 组合新内容
    if keep_original:
        new_content = f"""---
{new_front}
---

# {translated_title}

> 原标题: {article["title"]}

{translated_body}

---

## 原文对照

{article["body"]}

---
"""
    else:
        new_content = f"""---
{new_front}
---

{translated_body}

---
"""

    # 保存
    translated_path = filepath.replace('.md', '-zh.md')
    with open(translated_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[保存] {translated_path}")
    return translated_path


def batch_translate(directory: str, limit: int = 10):
    """批量翻译"""
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"[错误] 目录不存在: {directory}")
        return

    md_files = list(dir_path.glob("*.md"))
    untranslated = [f for f in md_files if not f.name.endswith('-zh.md')]

    print(f"[信息] 找到 {len(untranslated)} 篇未翻译文章")

    for i, filepath in enumerate(untranslated[:limit]):
        print(f"\n{'='*50}")
        print(f"[{i+1}/{min(len(untranslated), limit)}]")
        print(f"{'='*50}")

        translate_article(str(filepath))
        time.sleep(2)  # 避免 API 限流


def main():
    import argparse

    parser = argparse.ArgumentParser(description="翻译知识库文章为中文")
    parser.add_argument("file", nargs="?", help="单个文件路径")
    parser.add_argument("--news", action="store_true", help="翻译 news 目录")
    parser.add_argument("--tech", action="store_true", help="翻译 tech-articles 目录")
    parser.add_argument("--all", action="store_true", help="翻译所有目录")
    parser.add_argument("--limit", type=int, default=10, help="限制处理数量")
    parser.add_argument("--service", choices=["openai", "google"], default="openai",
                        help="翻译服务 (需要设置对应的 API key)")
    parser.add_argument("--no-original", action="store_true", help="不保留原文对照")

    args = parser.parse_args()

    global TRANSLATE_SERVICE
    TRANSLATE_SERVICE = args.service

    keep_original = not args.no_original

    if args.file:
        translate_article(args.file, keep_original)
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