#!/usr/bin/env python3
"""本地视频分析脚本

用法:
    python analyze_local_video.py --video "视频文件路径"
    python analyze_local_video.py --video "视频文件夹" --batch
    python analyze_local_video.py --video-dir "videos" --output-root "results"
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

from douyin_extractor.video_analyzer import analyze_local_video


def find_video_files(directory: Path) -> list[Path]:
    """查找目录中的视频文件"""
    video_extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv"}
    videos = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in video_extensions:
            videos.append(f)
    return sorted(videos)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="本地视频分析工具：提取截图 + 语音转文字 + 组合输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析单个视频
  %(prog)s --video "my_video.mp4"

  # 分析指定目录中的所有视频
  %(prog)s --video-dir "videos" --batch

  # 自定义参数
  %(prog)s --video "my_video.mp4" --frame-interval 5 --whisper-model medium

输出:
  results/<video_name>/
    - frames/          (截图文件夹)
    - transcript.*.txt (转录文本)
    - video_analysis.md (截图+文案 Markdown)
    - video_analysis.json (截图+文案 JSON)
    - metadata.json    (元数据)
        """,
    )

    # 输入参数
    parser.add_argument("--video", default="", help="单个视频文件路径")
    parser.add_argument("--video-dir", default="", help="视频文件夹路径（配合 --batch 使用）")
    parser.add_argument("--batch", action="store_true", help="批量处理视频文件夹中的所有视频")

    # 输出参数
    parser.add_argument(
        "--output-root",
        default="results",
        help="输出根目录 (默认: results)",
    )
    parser.add_argument("--output-name", default="", help="自定义输出目录名称（仅单视频模式）")

    # 分析参数
    parser.add_argument("--whisper-model", default="small", help="Whisper模型 (tiny/base/small/medium/large-v3)")
    parser.add_argument("--frame-interval", type=float, default=10.0, help="截图间隔（秒），默认 10 秒")
    parser.add_argument("--context-before", type=float, default=5.0, help="截图前文案范围（秒）")
    parser.add_argument("--context-after", type=float, default=5.0, help="截图后文案范围（秒）")
    parser.add_argument("--title", default="", help="视频标题")
    parser.add_argument("--skip-transcribe", action="store_true", help="跳过语音转文字")
    parser.add_argument("--skip-frames", action="store_true", help="跳过截图提取")

    args = parser.parse_args()

    # 输出目录相对于项目根目录
    if Path(args.output_root).is_absolute():
        output_root = Path(args.output_root)
    else:
        output_root = _PROJECT_ROOT / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    # 确定要处理的视频列表
    videos_to_process: list[tuple[Path, str]] = []

    if args.video:
        video_path = Path(args.video).resolve()
        if not video_path.exists():
            print(f"[ERROR] 视频文件不存在: {video_path}")
            return 1
        output_name = args.output_name or video_path.stem
        videos_to_process.append((video_path, output_name))

    elif args.video_dir and args.batch:
        video_dir = Path(args.video_dir).resolve()
        if not video_dir.exists():
            print(f"[ERROR] 视频目录不存在: {video_dir}")
            return 1
        videos = find_video_files(video_dir)
        if not videos:
            print(f"[WARN] 目录中没有找到视频文件: {video_dir}")
            return 0
        print(f"[INFO] 找到 {len(videos)} 个视频文件")
        for v in videos:
            videos_to_process.append((v, v.stem))

    else:
        # 默认：查找预设的视频目录
        default_video_dir = _PROJECT_ROOT / "videos"
        if default_video_dir.exists():
            videos = find_video_files(default_video_dir)
            if videos:
                print(f"[INFO] 在 {default_video_dir} 找到 {len(videos)} 个视频文件")
                for v in videos:
                    videos_to_process.append((v, v.stem))
            else:
                print(f"[INFO] {default_video_dir} 目录中没有视频文件")
                print("使用方式:")
                print("  1) 将视频文件放到 douyin-extractor/videos/ 目录")
                print("  2) 或使用 --video 参数指定视频路径")
                print("  3) 或使用 --video-dir + --batch 批量处理")
                return 0
        else:
            # 创建默认视频目录
            default_video_dir.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] 已创建视频目录: {default_video_dir}")
            print("将视频文件放到此目录后再次运行，或使用 --video 参数指定视频路径")
            return 0

    # 处理每个视频
    for i, (video_path, output_name) in enumerate(videos_to_process):
        print(f"\n{'='*60}")
        print(f"处理视频 {i+1}/{len(videos_to_process)}: {video_path.name}")
        print(f"{'='*60}")

        output_dir = output_root / output_name

        try:
            metadata = analyze_local_video(
                video_path=video_path,
                output_dir=output_dir,
                whisper_model=args.whisper_model,
                frame_interval=args.frame_interval,
                context_before=args.context_before,
                context_after=args.context_after,
                title=args.title or video_path.stem,
            )
        except Exception as e:
            print(f"[ERROR] 分析失败: {e}")
            continue

    print("\n" + "=" * 60)
    print("全部处理完成!")
    print("=" * 60)
    print(f"输出根目录: {output_root}")
    for item in sorted(output_root.iterdir()):
        if item.is_dir():
            print(f"  - {item.name}/")

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