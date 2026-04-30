#!/usr/bin/env python3
"""抖音视频提取与字幕生成 - 主入口脚本

用法:
    python douyin_to_transcript.py --url "抖音分享链接"
    python douyin_to_transcript.py --url "7.43 pda:/ 让你记住我 https://v.douyin.com/xxx/"
    python douyin_to_transcript.py --url "https://www.douyin.com/video/6914948781100338440"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 将项目根目录加入 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from douyin_extractor.parser import parse_douyin_url, load_cookie_from_file, parse_and_download_via_selenium
from douyin_extractor.downloader import download_video, download_video_ytdlp_fallback
from douyin_extractor.transcriber import (
    whisper_transcribe,
    detect_language,
    is_chinese_language,
    translate_to_zh,
)


def load_config(config_path: Optional[Path] = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        print("[WARN] pyyaml未安装，使用默认配置")
        return {}
    except Exception as e:
        print(f"[WARN] 读取配置文件失败: {e}")
        return {}


def write_outputs(
    result_dir: Path,
    original_text: str,
    zh_text: str,
    metadata: dict,
) -> None:
    """输出结果文件"""
    result_dir.mkdir(parents=True, exist_ok=True)

    (result_dir / "transcript.original.txt").write_text(original_text, encoding="utf-8")
    (result_dir / "transcript.zh-CN.txt").write_text(zh_text, encoding="utf-8")
    (result_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_speech_markdown(
    title: str,
    source_language: str,
    text: str,
    translated: bool,
) -> str:
    """生成演讲稿Markdown"""
    doc_title = title.strip() or "抖音视频"
    lang_line = "zh-CN" if translated else (source_language or "unknown")
    trans_line = "Yes" if translated else "No"
    body = text.strip()
    return (
        f"# {doc_title}\n\n"
        "## 演讲稿\n\n"
        f"- 来源语言: {source_language or 'unknown'}\n"
        f"- 文档语言: {lang_line}\n"
        f"- 已翻译: {trans_line}\n\n"
        "## 完整文稿\n\n"
        f"{body}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="抖音视频提取与字幕生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --url "7.43 pda:/ 让你记住我 https://v.douyin.com/L5pbfdP/"
  %(prog)s --url "https://www.douyin.com/video/6914948781100338440"
  %(prog)s --url "https://v.douyin.com/L4FJNR3/" --cookie "your_cookie_here"
        """,
    )
    parser.add_argument("--url", required=True, help="抖音分享链接/口令/URL")
    parser.add_argument(
        "--output-root",
        default="douyin-extractor/results",
        help="输出根目录 (默认: douyin-extractor/results)",
    )
    parser.add_argument("--cookie", default="", help="抖音网页Cookie（覆盖config.yaml）")
    parser.add_argument("--whisper-model", default="small", help="Whisper模型 (tiny/base/small/medium/large-v2)")
    parser.add_argument("--no-download-video", action="store_true", help="跳过视频下载，仅生成字幕")
    parser.add_argument("--no-transcribe", action="store_true", help="跳过语音转文字（仅使用视频描述）")
    parser.add_argument("--config", default="", help="配置文件路径")
    args = parser.parse_args()

    # 加载配置
    config = load_config(Path(args.config) if args.config else None)
    cookie = (
        args.cookie
        or os.environ.get("DOUYIN_COOKIE", "")
        or config.get("douyin_cookie", "")
    )
    # 如果 Cookie 仍为空，尝试从 cookies.txt 文件读取
    if not cookie:
        cookie_file = config.get("cookie_file", "")
        if cookie_file:
            cookie_path = Path(cookie_file)
            if not cookie_path.is_absolute():
                cookie_path = _PROJECT_ROOT / cookie_path
            if cookie_path.exists():
                print(f"[INFO] 从 {cookie_path} 加载抖音Cookie...")
                cookie = load_cookie_from_file(cookie_path)
                if cookie:
                    print(f"[INFO] 成功加载Cookie ({len(cookie)} 字符)")
                else:
                    print(f"[WARN] cookies.txt 中未找到抖音相关Cookie")
    if not cookie:
        print("[WARN] 未提供Cookie，可能导致解析失败。")
        print("  提供Cookie的方式：")
        print("  1) --cookie '你的Cookie'")
        print("  2) 环境变量: export DOUYIN_COOKIE='你的Cookie'")
        print("  3) 编辑 config.yaml 的 douyin_cookie 字段")
        print("  4) 导出 cookies.txt 到项目目录（config.yaml 中配置 cookie_file）")
        print()
    user_agent = config.get("user_agent", "")
    whisper_model = args.whisper_model or config.get("whisper_model", "small")

    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    # ── Step 1: 解析抖音链接 ──
    print("=" * 60)
    print("Step 1: 解析抖音链接")
    print("=" * 60)
    try:
        video = parse_douyin_url(
            args.url,
            cookie=cookie,
            user_agent=user_agent,
        )
    except (ValueError, RuntimeError) as e:
        print(f"[ERROR] {e}")
        return 1

    # ── Step 2: 下载视频 ──
    video_path: Optional[Path] = None
    if not args.no_download_video:
        print("\n" + "=" * 60)
        print("Step 2: 下载视频")
        print("=" * 60)

        result_dir = output_root / video.aweme_id
        result_dir.mkdir(parents=True, exist_ok=True)

        if video.video_url:
            try:
                video_path = download_video(
                    video,
                    output_dir=result_dir,
                    cookie=cookie,
                    user_agent=user_agent,
                    timeout=config.get("download_timeout", 60),
                    max_retries=config.get("max_retries", 3),
                )
            except RuntimeError as e:
                print(f"[WARN] 直接下载失败: {e}")

        # 如果直接下载失败，尝试 Selenium 下载
        if not video_path:
            print("[INFO] 尝试使用 Selenium 浏览器下载...")
            selenium_video = parse_and_download_via_selenium(
                aweme_id=video.aweme_id,
                cookie=cookie,
                download_dir=str(result_dir),
                timeout=config.get("download_timeout", 60),
            )
            if selenium_video and selenium_video.video_path:
                video_path = Path(selenium_video.video_path)
                # 更新视频信息
                if selenium_video.title:
                    video.title = selenium_video.title
                if selenium_video.desc:
                    video.desc = selenium_video.desc
                    video.text_content = selenium_video.text_content

        # 如果 Selenium 也失败，尝试 yt-dlp
        if not video_path:
            resolved_url = f"https://www.douyin.com/video/{video.aweme_id}"
            video_path = download_video_ytdlp_fallback(
                resolved_url,
                output_dir=result_dir,
                video_id=video.aweme_id,
            )

        if not video_path and not args.no_transcribe:
            print("[ERROR] 视频下载失败，无法进行语音转文字")
            return 1

    # ── Step 3: 生成字幕 ──
    print("\n" + "=" * 60)
    print("Step 3: 生成字幕")
    print("=" * 60)

    source_method = "whisper"
    source_language = "unknown"

    # 视频描述/文案作为基础文字
    desc_text = video.text_content or video.desc or ""
    original_text = ""
    whisper_text = ""

    if not args.no_transcribe and video_path:
        try:
            whisper_text, whisper_lang = whisper_transcribe(
                video_path, model_name=whisper_model
            )
            source_language = detect_language(whisper_text, fallback=whisper_lang)
        except RuntimeError as e:
            print(f"[WARN] Whisper转录失败: {e}")
            whisper_text = ""

    # 合并文字：优先Whisper转录，描述作为补充
    if whisper_text:
        source_method = "whisper"
        original_text = whisper_text
        if desc_text and desc_text not in whisper_text:
            original_text = f"[视频描述]\n{desc_text}\n\n[语音转录]\n{whisper_text}"
    elif desc_text:
        source_method = "description"
        original_text = desc_text
        source_language = detect_language(desc_text, fallback="zh")
        print(f"[INFO] 使用视频描述作为字幕 (语言: {source_language})")
    else:
        print("[WARN] 没有可用的字幕文本")
        original_text = "(无字幕内容)"
        source_method = "none"

    # ── Step 4: 翻译 ──
    print("\n" + "=" * 60)
    print("Step 4: 翻译")
    print("=" * 60)

    if is_chinese_language(source_language):
        zh_text = original_text
        print("[INFO] 源语言为中文，无需翻译")
    else:
        try:
            zh_text = translate_to_zh(original_text)
        except RuntimeError as e:
            print(f"[WARN] 翻译失败: {e}")
            zh_text = original_text

    # ── Step 5: 输出文件 ──
    print("\n" + "=" * 60)
    print("Step 5: 输出文件")
    print("=" * 60)

    result_dir = output_root / video.aweme_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # 如果视频在工作子目录，移动到结果目录
    if video_path and video_path.parent != result_dir:
        import shutil
        dest = result_dir / video_path.name
        if not dest.exists():
            shutil.move(str(video_path), str(dest))
            video_path = dest

    metadata = {
        "url": args.url,
        "aweme_id": video.aweme_id,
        "title": video.title or video.desc,
        "author": video.author,
        "author_id": video.author_id,
        "source_language": source_language,
        "source_method": source_method,
        "whisper_model": whisper_model if source_method == "whisper" else None,
        "digg_count": video.digg_count,
        "comment_count": video.comment_count,
        "share_count": video.share_count,
        "video_path": str(video_path) if video_path else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(result_dir),
    }

    # 写入文件
    write_outputs(result_dir, original_text, zh_text, metadata)

    # 写入演讲稿
    (result_dir / "speech.original.md").write_text(
        build_speech_markdown(
            title=video.title or video.desc,
            source_language=source_language,
            text=original_text,
            translated=False,
        ),
        encoding="utf-8",
    )
    (result_dir / "speech.zh-CN.md").write_text(
        build_speech_markdown(
            title=video.title or video.desc,
            source_language=source_language,
            text=zh_text,
            translated=True,
        ),
        encoding="utf-8",
    )

    # 清理工作目录
    work_dir = result_dir / "_work"
    if work_dir.exists():
        import shutil
        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass

    # ── 完成 ──
    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)
    print(f"输出目录: {result_dir}")
    for f in sorted(result_dir.iterdir()):
        if f.is_file():
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            print(f"  - {f.name} ({size_str})")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[INFO] 用户中断")
        raise SystemExit(1)
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
