"""语音转文字与翻译模块"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, List


@dataclass
class TranscriptSegment:
    """带时间戳的转录片段"""
    start: float  # 开始时间（秒）
    end: float    # 结束时间（秒）
    text: str     # 文字内容


def whisper_transcribe(
    video_path: Path,
    model_name: str = "small",
) -> Tuple[str, str]:
    """使用 faster-whisper 对视频进行语音转文字

    Args:
        video_path: 视频文件路径
        model_name: Whisper模型名称

    Returns:
        (转录文本, 检测到的语言)
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "缺少依赖 faster-whisper，请先运行: pip install -r requirements.txt"
        ) from exc

    print(f"[INFO] 加载Whisper模型: {model_name}...")
    model = WhisperModel(model_name, device="auto", compute_type="auto")

    print("[INFO] 开始语音转文字...")
    segments, info = model.transcribe(str(video_path), vad_filter=True)

    chunks = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    transcript = "\n".join(chunks).strip()
    language = info.language or "unknown"

    print(f"[INFO] 转录完成，检测语言: {language}，文本长度: {len(transcript)} 字符")
    return transcript, language


def whisper_transcribe_with_timestamps(
    video_path: Path,
    model_name: str = "small",
) -> Tuple[List[TranscriptSegment], str]:
    """使用 faster-whisper 对视频进行语音转文字，返回带时间戳的片段

    Args:
        video_path: 视频文件路径
        model_name: Whisper模型名称

    Returns:
        (转录片段列表, 检测到的语言)
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "缺少依赖 faster-whisper，请先运行: pip install -r requirements.txt"
        ) from exc

    print(f"[INFO] 加载Whisper模型: {model_name}...")
    model = WhisperModel(model_name, device="auto", compute_type="auto")

    print("[INFO] 开始语音转文字（带时间戳）...")
    segments, info = model.transcribe(str(video_path), vad_filter=True)

    result: List[TranscriptSegment] = []
    for seg in segments:
        if seg.text and seg.text.strip():
            result.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip()
            ))

    language = info.language or "unknown"
    print(f"[INFO] 转录完成，检测语言: {language}，共 {len(result)} 个片段")

    return result, language


def format_transcript_with_timestamps(segments: List[TranscriptSegment]) -> str:
    """将带时间戳的片段格式化为文本

    格式: [00:01:23] 文字内容
    """
    lines = []
    for seg in segments:
        start_time = format_time(seg.start)
        lines.append(f"[{start_time}] {seg.text}")
    return "\n".join(lines)


def format_time(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS 或 MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def detect_language(text: str, fallback: str = "unknown") -> str:
    """检测文本语言"""
    if not text.strip():
        return fallback
    try:
        from langdetect import detect
    except ImportError:
        return fallback
    try:
        return detect(text[:5000])
    except Exception:
        return fallback


def is_chinese_language(lang: str) -> bool:
    """判断是否为中文"""
    lang = (lang or "").lower()
    return lang.startswith("zh") or lang in {"cn", "chinese"}


def translate_to_zh(text: str) -> str:
    """翻译文本为中文"""
    if not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError(
            "缺少依赖 deep-translator，请先运行: pip install -r requirements.txt"
        ) from exc

    print("[INFO] 正在翻译为中文...")
    translator = GoogleTranslator(source="auto", target="zh-CN")
    max_chunk = 3000
    pieces: list[str] = []
    for i in range(0, len(text), max_chunk):
        chunk = text[i : i + max_chunk]
        pieces.append(translator.translate(chunk))
    result = "\n".join(pieces)
    print(f"[INFO] 翻译完成，文本长度: {len(result)} 字符")
    return result
