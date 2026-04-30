---
name: douyin-extractor
description: Analyze local video files - extract frames, transcribe speech, and generate frame-caption combinations for AI analysis.
---

# Douyin Extractor

Extract frames and transcribe subtitles from local video files.

## 功能

| 脚本 | 功能 | 状态 |
|------|------|------|
| `analyze_local_video.py` | 本地视频分析（截图+文案） | ✅ 推荐 |
| `douyin_to_transcript.py` | 抖音在线解析 | ⚠️ 受反爬限制 |

## 快速开始

### 1. 放置视频

将视频文件放到 `videos/` 目录：

```bash
cp your_video.mp4 douyin-extractor/videos/
```

### 2. 运行分析

```bash
python3 douyin-extractor/scripts/analyze_local_video.py
```

### 3. 查看结果

结果在 `results/<video_name>/` 目录：

```
results/<video_name>/
├── frames/                   # 截图
│   ├── frame_000_00-00.jpg
│   ├── frame_001_00-10.jpg
│   └── ...
├── transcript.original.txt   # 原始转录
├── transcript.with_timestamps.txt  # 带时间戳
├── transcript.zh-CN.txt      # 中文（如翻译）
├── video_analysis.md         # 截图+文案（阅读）
├── video_analysis.json       # 截图+文案（AI用）
└── metadata.json             # 元数据
```

## 参数说明

```bash
python3 scripts/analyze_local_video.py \
  --video "my_video.mp4"          # 单视频
  --frame-interval 10            # 截图间隔（秒）
  --whisper-model small          # 转录模型
  --context-before 5             # 截图前文案范围
  --context-after 5              # 截图后文案范围
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--frame-interval` | 10 | 截图间隔秒数 |
| `--whisper-model` | small | 模型：tiny/base/small/medium/large-v3 |
| `--context-before` | 5 | 每张截图关联前几秒文案 |
| `--context-after` | 5 | 每张截图关联后几秒文案 |

## 安装依赖

```bash
pip install -r requirements.txt
brew install ffmpeg  # 截图需要
```

## 输出格式

### video_analysis.json（AI 分析用）

```json
{
  "frames": [
    {
      "frame_path": "frames/frame_000_00-00.jpg",
      "timestamp": 0.0,
      "timestamp_str": "00:00",
      "captions": ["对应文案1", "对应文案2"]
    }
  ]
}
```

### video_analysis.md（阅读用）

```markdown
## 00:00

![截图](frame_000_00-00.jpg)

**对应文案:**
- 文案内容...
```

## 项目结构

```
douyin-extractor/
├── videos/              # 放视频的地方
├── results/             # 输出结果
├── scripts/             # 脚本
│   ├── analyze_local_video.py   # 本地视频分析
│   └── douyin_to_transcript.py  # 抖音在线（受限）
├── douyin_extractor/    # 核心模块
│   ├── video_analyzer.py
│   ├── transcriber.py
│   ├── parser.py
│   └── downloader.py
├── config.yaml
├── requirements.txt
└── SKILL.md
```