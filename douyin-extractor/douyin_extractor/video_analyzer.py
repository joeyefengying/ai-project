"""视频分析模块：截图提取 + 文案组合"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .transcriber import TranscriptSegment, format_time


# ffmpeg 路径（优先使用 Homebrew 安装的版本）
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "")
if not FFMPEG_PATH:
    # 尝试常见路径
    for p in ["/usr/local/bin", "/usr/local/Cellar/ffmpeg/8.1_1/bin", "/opt/homebrew/bin"]:
        if Path(p).joinpath("ffprobe").exists():
            FFMPEG_PATH = p
            break


@dataclass
class FrameCaption:
    """截图+文案组合"""
    frame_path: str           # 截图文件路径
    timestamp: float          # 时间点（秒）
    timestamp_str: str        # 时间字符串 (MM:SS)
    captions: List[str]       # 对应的文案列表
    duration_before: float    # 截图前多少秒的内容
    duration_after: float     # 截图后多少秒的内容


def _get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径"""
    if FFMPEG_PATH:
        return str(Path(FFMPEG_PATH) / "ffprobe")
    return "ffprobe"


def _get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径"""
    if FFMPEG_PATH:
        return str(Path(FFMPEG_PATH) / "ffmpeg")
    return "ffmpeg"


def get_video_duration(video_path: Path) -> float:
    """获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                _get_ffprobe_path(),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[WARN] 无法获取视频时长: {e}")
        return 0.0


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    interval: float = 10.0,
    max_frames: int = 50,
) -> List[tuple]:
    """提取视频关键帧截图

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        interval: 截图间隔（秒），默认 10 秒
        max_frames: 最大截图数量

    Returns:
        [(截图路径, 时间点), ...] 列表
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(video_path)
    if duration <= 0:
        print("[WARN] 视频时长为 0，无法提取截图")
        return []

    # 计算截图时间点
    num_frames = min(int(duration / interval) + 1, max_frames)
    timestamps = [i * interval for i in range(num_frames) if i * interval < duration]

    print(f"[INFO] 视频时长: {duration:.1f}秒，计划提取 {len(timestamps)} 张截图")

    frames = []
    for i, ts in enumerate(timestamps):
        frame_name = f"frame_{i:03d}_{format_time(ts).replace(':', '-')}.jpg"
        frame_path = output_dir / frame_name

        try:
            subprocess.run(
                [
                    _get_ffmpeg_path(),
                    "-y",  # 覆盖已存在文件
                    "-ss", str(ts),  # 时间点
                    "-i", str(video_path),
                    "-vframes", "1",  # 提取 1 帧
                    "-q:v", "2",  # 高质量
                    str(frame_path)
                ],
                capture_output=True,
                check=True
            )
            if frame_path.exists():
                frames.append((str(frame_path), ts))
                print(f"[INFO] 提取截图 {i+1}/{len(timestamps)}: {format_time(ts)}")
        except subprocess.CalledProcessError as e:
            print(f"[WARN] 提取截图失败 ({format_time(ts)}): {e.stderr}")
        except FileNotFoundError:
            print("[ERROR] ffmpeg 未安装，无法提取截图。请运行: brew install ffmpeg")
            return []

    return frames


def match_captions_to_frames(
    frames: List[tuple],
    segments: List[TranscriptSegment],
    context_before: float = 5.0,
    context_after: float = 5.0,
) -> List[FrameCaption]:
    """将截图与对应的文案匹配

    Args:
        frames: [(截图路径, 时间点), ...] 列表
        segments: TranscriptSegment 列表（带时间戳的转录片段）
        context_before: 截图前多少秒的文案
        context_after: 截图后多少秒的文案

    Returns:
        FrameCaption 列表
    """
    results = []

    for frame_path, timestamp in frames:
        # 找到时间范围内的文案片段
        start_range = timestamp - context_before
        end_range = timestamp + context_after

        matched_captions = []
        for seg in segments:
            # 片段在截图时间范围内
            if seg.end >= start_range and seg.start <= end_range:
                matched_captions.append(seg.text)

        # 如果没有匹配到，取最近的文案
        if not matched_captions and segments:
            # 找最近的片段
            closest_seg = min(segments, key=lambda s: abs(s.start - timestamp))
            matched_captions = [closest_seg.text]

        results.append(FrameCaption(
            frame_path=frame_path,
            timestamp=timestamp,
            timestamp_str=format_time(timestamp),
            captions=matched_captions,
            duration_before=context_before,
            duration_after=context_after,
        ))

    return results


def generate_frame_caption_markdown(
    frame_captions: List[FrameCaption],
    output_path: Path,
    title: str = "视频内容分析",
) -> None:
    """生成截图+文案的 Markdown 文档"""

    lines = [
        f"# {title}",
        "",
        "## 截图与文案对照",
        "",
    ]

    for fc in frame_captions:
        # 相对路径（假设 markdown 在同一目录）
        frame_rel_path = Path(fc.frame_path).name
        lines.append(f"### {fc.timestamp_str}")
        lines.append("")
        lines.append(f"![截图]({frame_rel_path})")
        lines.append("")
        if fc.captions:
            lines.append("**对应文案:**")
            lines.append("")
            for cap in fc.captions:
                lines.append(f"- {cap}")
            lines.append("")
        else:
            lines.append("**对应文案:** (无)")
            lines.append("")
        lines.append("---")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[INFO] 已生成 Markdown 文档: {output_path}")


def generate_frame_caption_json(
    frame_captions: List[FrameCaption],
    output_path: Path,
) -> None:
    """生成截图+文案的 JSON 文档"""

    data = {
        "frames": [
            {
                "frame_path": fc.frame_path,
                "timestamp": fc.timestamp,
                "timestamp_str": fc.timestamp_str,
                "captions": fc.captions,
                "context_range": {
                    "before": fc.duration_before,
                    "after": fc.duration_after,
                }
            }
            for fc in frame_captions
        ]
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[INFO] 已生成 JSON 文档: {output_path}")


def analyze_local_video(
    video_path: Path,
    output_dir: Path,
    whisper_model: str = "small",
    frame_interval: float = 10.0,
    context_before: float = 5.0,
    context_after: float = 5.0,
    title: str = "",
) -> dict:
    """分析本地视频：提取截图 + 语音转文字 + 组合输出

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        whisper_model: Whisper 模型名称
        frame_interval: 截图间隔（秒）
        context_before: 截图前文案范围
        context_after: 截图后文案范围
        title: 视频标题

    Returns:
        分析结果元数据
    """
    from .transcriber import (
        whisper_transcribe_with_timestamps,
        format_transcript_with_timestamps,
        detect_language,
        is_chinese_language,
        translate_to_zh,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("[INFO] 开始分析本地视频")
    print("=" * 60)
    print(f"[INFO] 视频文件: {video_path}")
    print(f"[INFO] 输出目录: {output_dir}")

    # 1. 提取截图
    print("\n[Step 1] 提取视频截图...")
    frames = extract_keyframes(video_path, frames_dir, interval=frame_interval)

    # 2. 语音转文字（带时间戳）
    print("\n[Step 2] 语音转文字...")
    segments, language = whisper_transcribe_with_timestamps(video_path, whisper_model)

    # 生成完整转录文本
    full_transcript = format_transcript_with_timestamps(segments)
    (output_dir / "transcript.with_timestamps.txt").write_text(full_transcript, encoding="utf-8")

    # 纯文本转录
    plain_transcript = "\n".join([s.text for s in segments])
    (output_dir / "transcript.original.txt").write_text(plain_transcript, encoding="utf-8")

    # 3. 翻译（如果不是中文）
    if not is_chinese_language(language) and plain_transcript:
        print("\n[Step 3] 翻译为中文...")
        try:
            zh_transcript = translate_to_zh(plain_transcript)
            (output_dir / "transcript.zh-CN.txt").write_text(zh_transcript, encoding="utf-8")
        except Exception as e:
            print(f"[WARN] 翻译失败: {e}")
            zh_transcript = plain_transcript
    else:
        zh_transcript = plain_transcript
        (output_dir / "transcript.zh-CN.txt").write_text(zh_transcript, encoding="utf-8")
        print("[INFO] 源语言为中文，无需翻译")

    # 4. 截图+文案组合
    print("\n[Step 4] 生成截图+文案组合...")
    frame_captions = match_captions_to_frames(
        frames, segments,
        context_before=context_before,
        context_after=context_after,
    )

    # 生成 Markdown
    generate_frame_caption_markdown(
        frame_captions,
        output_dir / "video_analysis.md",
        title=title or video_path.stem,
    )

    # 生成 JSON
    generate_frame_caption_json(
        frame_captions,
        output_dir / "video_analysis.json",
    )

    # 5. 生成元数据
    duration = get_video_duration(video_path)
    metadata = {
        "video_path": str(video_path),
        "title": title or video_path.stem,
        "duration": duration,
        "duration_str": format_time(duration),
        "language": language,
        "frame_count": len(frames),
        "segment_count": len(segments),
        "frame_interval": frame_interval,
        "whisper_model": whisper_model,
        "output_dir": str(output_dir),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("[INFO] 分析完成!")
    print("=" * 60)
    print(f"输出目录: {output_dir}")
    print(f"  - 截图: {len(frames)} 张 (frames/)")
    print(f"  - 转录: {len(segments)} 个片段")
    print(f"  - 组合文档: video_analysis.md, video_analysis.json")

    return metadata