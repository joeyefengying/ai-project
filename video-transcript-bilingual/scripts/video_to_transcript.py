#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


def run_cmd(cmd: list[str], cwd: Optional[Path] = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def load_video_info(url: str) -> dict:
    proc = subprocess.run(
        ["yt-dlp", "--dump-single-json", "--no-warnings", url],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to fetch video info:\n{proc.stderr}")
    return json.loads(proc.stdout)


def sanitize_video_id(video_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", video_id.strip())
    return clean or "video"


def try_download_subtitles(url: str, workdir: Path, video_id: str) -> Optional[Path]:
    output_tpl = f"{video_id}.%(ext)s"
    run_cmd(
        [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "all",
            "--sub-format",
            "vtt/srt",
            "-o",
            output_tpl,
            url,
        ],
        cwd=workdir,
    )

    candidates = sorted(
        list(workdir.glob(f"{video_id}*.vtt")) + list(workdir.glob(f"{video_id}*.srt"))
    )
    return candidates[0] if candidates else None


def subtitle_language_from_filename(path: Path) -> Optional[str]:
    # Typical names: <id>.en.vtt or <id>.zh-Hans.vtt
    parts = path.name.split(".")
    if len(parts) >= 3:
        return parts[-2]
    return None


def subtitle_to_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper() == "WEBVTT":
            continue
        if line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def download_audio(url: str, workdir: Path, video_id: str) -> Path:
    run_cmd(
        [
            "yt-dlp",
            "-f",
            "bestaudio",
            "-o",
            f"{video_id}.%(ext)s",
            url,
        ],
        cwd=workdir,
    )
    audio_candidates = []
    for ext in ("webm", "m4a", "mp3", "opus", "aac", "wav"):
        candidate = workdir / f"{video_id}.{ext}"
        if candidate.exists():
            audio_candidates.append(candidate)
    if audio_candidates:
        return audio_candidates[0]
    matches = sorted(
        [
            p
            for p in workdir.glob(f"{video_id}.*")
            if p.suffix.lower() in {".webm", ".m4a", ".mp3", ".opus", ".aac", ".wav"}
        ]
    )
    if matches:
        return matches[0]
    raise RuntimeError("Audio download succeeded but no audio file found.")


def download_video(url: str, workdir: Path, video_id: str) -> Path:
    run_cmd(
        [
            "yt-dlp",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "-o",
            f"{video_id}.%(ext)s",
            url,
        ],
        cwd=workdir,
    )
    for ext in ("mp4", "mkv", "webm", "mov"):
        candidate = workdir / f"{video_id}.{ext}"
        if candidate.exists():
            return candidate
    matches = sorted(
        [p for p in workdir.glob(f"{video_id}.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    )
    if matches:
        return matches[0]
    raise RuntimeError("Video download succeeded but no video file found.")


def whisper_transcribe(audio_path: Path, model_name: str) -> Tuple[str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency faster-whisper. Install requirements first."
        ) from exc

    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segments, info = model.transcribe(str(audio_path), vad_filter=True)
    chunks = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    transcript = "\n".join(chunks).strip()
    language = info.language or "unknown"
    return transcript, language


def detect_language(text: str, fallback: str = "unknown") -> str:
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
    lang = (lang or "").lower()
    return lang.startswith("zh") or lang in {"cn", "chinese"}


def translate_to_zh(text: str) -> str:
    if not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency deep-translator. Install requirements first."
        ) from exc

    translator = GoogleTranslator(source="auto", target="zh-CN")
    max_chunk = 3000
    pieces: list[str] = []
    for i in range(0, len(text), max_chunk):
        chunk = text[i : i + max_chunk]
        pieces.append(translator.translate(chunk))
    return "\n".join(pieces)


def write_outputs(
    result_dir: Path,
    original_text: str,
    zh_text: str,
    metadata: dict,
) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "transcript.original.txt").write_text(original_text, encoding="utf-8")
    (result_dir / "transcript.zh-CN.txt").write_text(zh_text, encoding="utf-8")
    (result_dir / "speech.original.md").write_text(
        build_speech_markdown(
            title=metadata.get("title", ""),
            source_language=metadata.get("source_language", "unknown"),
            text=original_text,
            translated=False,
        ),
        encoding="utf-8",
    )
    (result_dir / "speech.zh-CN.md").write_text(
        build_speech_markdown(
            title=metadata.get("title", ""),
            source_language=metadata.get("source_language", "unknown"),
            text=zh_text,
            translated=True,
        ),
        encoding="utf-8",
    )
    (result_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_speech_markdown(
    title: str,
    source_language: str,
    text: str,
    translated: bool,
) -> str:
    doc_title = title.strip() or "Untitled Video"
    lang_line = "zh-CN" if translated else (source_language or "unknown")
    trans_line = "Yes" if translated else "No"
    body = text.strip()
    return (
        f"# {doc_title}\n\n"
        "## Speech Document\n\n"
        f"- Source language: {source_language or 'unknown'}\n"
        f"- Document language: {lang_line}\n"
        f"- Translated: {trans_line}\n\n"
        "## Full Script\n\n"
        f"{body}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create original and Chinese transcript files from a video URL."
    )
    parser.add_argument("--url", required=True, help="Video URL")
    parser.add_argument(
        "--output-root",
        default="yp-dlp/results",
        help="Output root directory. Default: yp-dlp/results",
    )
    parser.add_argument(
        "--whisper-model",
        default="small",
        help="Whisper model name used when subtitles are unavailable. Default: small",
    )
    parser.add_argument(
        "--no-download-video",
        action="store_true",
        help="Skip downloading the full video file; only produce transcripts/documents.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    info = load_video_info(args.url)
    video_id = sanitize_video_id(str(info.get("id") or "video"))
    title = str(info.get("title") or "")

    result_dir = output_root / video_id
    workdir = result_dir / "_work"
    workdir.mkdir(parents=True, exist_ok=True)

    source_method = "subtitle"
    source_language = "unknown"
    original_text = ""
    downloaded_video_path: Optional[Path] = None

    if not args.no_download_video:
        downloaded_video_path = download_video(args.url, workdir, video_id)

    subtitle_path = None
    try:
        subtitle_path = try_download_subtitles(args.url, workdir, video_id)
    except Exception:
        subtitle_path = None

    if subtitle_path and subtitle_path.exists():
        original_text = subtitle_to_text(subtitle_path)
        source_language = subtitle_language_from_filename(subtitle_path) or detect_language(
            original_text, fallback="unknown"
        )
    else:
        source_method = "whisper"
        audio_path = download_audio(args.url, workdir, video_id)
        original_text, whisper_lang = whisper_transcribe(audio_path, args.whisper_model)
        source_language = detect_language(original_text, fallback=whisper_lang)

    if not original_text.strip():
        raise RuntimeError("No transcript text generated.")

    if is_chinese_language(source_language):
        zh_text = original_text
    else:
        zh_text = translate_to_zh(original_text)

    metadata = {
        "url": args.url,
        "video_id": video_id,
        "title": title,
        "source_language": source_language,
        "source_method": source_method,
        "video_path": str(downloaded_video_path) if downloaded_video_path else None,
        "whisper_model": args.whisper_model if source_method == "whisper" else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(result_dir),
    }

    write_outputs(result_dir, original_text, zh_text, metadata)

    print("Done")
    print(f"- transcript.original.txt: {result_dir / 'transcript.original.txt'}")
    print(f"- transcript.zh-CN.txt: {result_dir / 'transcript.zh-CN.txt'}")
    print(f"- speech.original.md: {result_dir / 'speech.original.md'}")
    print(f"- speech.zh-CN.md: {result_dir / 'speech.zh-CN.md'}")
    print(f"- metadata.json: {result_dir / 'metadata.json'}")
    if downloaded_video_path:
        print(f"- video: {downloaded_video_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
