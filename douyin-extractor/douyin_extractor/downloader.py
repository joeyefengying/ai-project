"""抖音无水印视频下载模块"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from .parser import DouyinVideo


def download_video(
    video: DouyinVideo,
    output_dir: Path,
    filename: Optional[str] = None,
    cookie: str = "",
    user_agent: str = "",
    timeout: float = 60.0,
    max_retries: int = 3,
) -> Path:
    """下载抖音无水印视频

    Args:
        video: DouyinVideo 对象（需包含 video_url）
        output_dir: 输出目录
        filename: 输出文件名（不含扩展名），默认用 aweme_id
        cookie: 抖音Cookie
        user_agent: User-Agent
        timeout: 下载超时
        max_retries: 最大重试次数

    Returns:
        下载后的视频文件路径
    """
    if not video.video_url:
        raise RuntimeError("视频URL为空，无法下载")

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = filename or video.aweme_id or "douyin_video"
    output_path = output_dir / f"{base_name}.mp4"

    if output_path.exists():
        print(f"[INFO] 视频已存在: {output_path}")
        return output_path

    headers = {
        "User-Agent": user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
        "Accept": "*/*",
    }
    if cookie:
        headers["Cookie"] = cookie

    # 抖音视频URL可能需要处理协议
    video_url = video.video_url
    # 确保使用https
    if video_url.startswith("//"):
        video_url = f"https:{video_url}"
    elif video_url.startswith("http://"):
        video_url = video_url.replace("http://", "https://", 1)

    # 尝试多种URL（无水印 → 有水印）
    urls_to_try = [video_url]
    if video.video_url_watermark and video.video_url_watermark != video_url:
        urls_to_try.append(video.video_url_watermark)

    last_error = None
    for attempt_url in urls_to_try:
        for retry in range(max_retries):
            try:
                print(f"[INFO] 正在下载视频 (尝试 {retry + 1}/{max_retries})...")
                _do_download(attempt_url, output_path, headers, timeout)
                print(f"[INFO] 视频下载完成: {output_path}")
                return output_path
            except Exception as e:
                last_error = e
                print(f"[WARN] 下载失败: {e}")
                if retry < max_retries - 1:
                    import time
                    time.sleep(2)

    raise RuntimeError(f"视频下载失败（已重试{max_retries}次）: {last_error}")


def _do_download(
    url: str,
    output_path: Path,
    headers: dict,
    timeout: float,
) -> None:
    """执行实际下载"""
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
        http2=True,
    ) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = resp.headers.get("content-length")
            if total:
                total = int(total)
                print(f"[INFO] 视频大小: {total / 1024 / 1024:.1f} MB")

            with open(output_path, "wb") as f:
                downloaded = 0
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and downloaded % (5 * 1024 * 1024) < 65536:
                        pct = downloaded / total * 100
                        print(f"  下载进度: {pct:.0f}% ({downloaded / 1024 / 1024:.1f} MB)")

    if not output_path.exists() or output_path.stat().st_size < 1024:
        raise RuntimeError("下载的文件过小，可能下载失败")


def download_video_ytdlp_fallback(
    url: str,
    output_dir: Path,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """使用 yt-dlp 作为备用下载方式

    Args:
        url: 抖音视频URL
        output_dir: 输出目录
        video_id: 视频ID

    Returns:
        下载后的文件路径，失败返回None
    """
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = video_id or "douyin_video"
    output_tpl = str(output_dir / f"{base_name}.%(ext)s")

    try:
        cmd = [
            "yt-dlp",
            "-f", "best",
            "--no-warnings",
            "-o", output_tpl,
            url,
        ]
        print(f"[INFO] 使用yt-dlp备用下载...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"[WARN] yt-dlp下载失败: {result.stderr}")
            return None

        # 查找下载的文件
        for ext in ("mp4", "mkv", "webm", "mov"):
            candidate = output_dir / f"{base_name}.{ext}"
            if candidate.exists():
                print(f"[INFO] yt-dlp下载完成: {candidate}")
                return candidate

        # 宽泛搜索
        matches = sorted(output_dir.glob(f"{base_name}.*"))
        if matches:
            return matches[0]

        return None
    except FileNotFoundError:
        print("[WARN] yt-dlp未安装，跳过备用下载")
        return None
    except Exception as e:
        print(f"[WARN] yt-dlp下载异常: {e}")
        return None
