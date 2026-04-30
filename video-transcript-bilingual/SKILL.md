---
name: video-transcript-bilingual
description: Convert a video URL into downloadable video + readable transcript documents. Use this skill whenever the user provides a YouTube/video link and asks to download video, extract transcript text, subtitles, notes, script, or a bilingual transcript. Always produce output files under yp-dlp/, and when source language is not Chinese, provide both source-language and Chinese transcript files.
---

# Video Transcript Bilingual

Generate downloadable video and transcript documents from a video URL and save outputs under `yp-dlp/`.

## When to use

Use this skill when the user asks for any of these:
- "把视频转成讲稿/文字稿"
- "提取字幕/文稿"
- "给我 transcript"
- "顺便翻译成中文"

## Inputs

- `video_url`: Video link
- Optional:
  - `output_root` (default `yp-dlp/results`)
  - `whisper_model` (default `small`)

## Output contract

Always create one result folder per video:

`yp-dlp/results/<video_id>/`

Expected files:
- downloaded video file (for example `video_id.mp4`)
- `transcript.original.txt` (source-language transcript)
- `transcript.zh-CN.txt` (Chinese transcript, if source is non-Chinese; if source is Chinese, copy original)
- `speech.original.md` (source-language speech document)
- `speech.zh-CN.md` (Chinese speech document)
- `metadata.json` (url/title/language/model/timestamps)

## Workflow

1. Download video file with `yt-dlp` (`bv*+ba/b`, merged to mp4 when possible).
2. Prefer existing subtitles:
   - Use `yt-dlp` to fetch subtitles (`--write-subs --write-auto-subs`).
   - Convert `.vtt`/`.srt` subtitle text into plain paragraph transcript.
3. If subtitles are unavailable:
   - Download audio via `yt-dlp`.
   - Run local Whisper (`faster-whisper`) to transcribe.
4. Detect source language.
5. If source language is non-Chinese, translate transcript to `zh-CN`.
6. Save all generated files under `yp-dlp/results/<video_id>/`.

## Run

```bash
python video-transcript-bilingual/scripts/video_to_transcript.py \
  --url "<VIDEO_URL>" \
  --output-root "yp-dlp/results"
```

Install dependencies first:

```bash
pip install -r video-transcript-bilingual/requirements.txt
```

## Notes

- This skill uses subtitle-first strategy for speed and quality.
- If translation service is rate-limited, retry once with smaller chunk size.
- Keep the final answer concise and include output file paths.
