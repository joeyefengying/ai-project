# AI Project Lab

探索 AI 能力的实验项目集合。这些种子项目用于测试各种 AI 技术的实际应用场景，后续可能演化为独立产品。

## 项目定位

本项目是一个 **AI 能力测试场**，核心目标：

1. **验证 AI 技术的边界** - 在真实场景中测试 LLM、语音识别、视频理解等能力
2. **积累工程经验** - 从原型到可用的完整开发流程
3. **孵化产品想法** - 好用的工具可能演化为独立产品

## 子项目概览

| 项目 | 核心能力 | 技术栈 | 产品化潜力 |
|------|----------|--------|------------|
| [yuque-exporter](yuque-exporter/) | 知识库迁移 | Python + HTML 解析 | 知识管理工具 |
| [douyin-extractor](douyin-extractor/) | 视频理解 | Whisper + FFmpeg | 短视频分析工具 |
| [bookmark-to-wiki](bookmark-to-wiki/) | 内容聚合 | 网页抓取 + LLM | 个人知识库 |
| [video-transcript-bilingual](video-transcript-bilingual/) | 多语言转录 | yt-dlp + Whisper | 视频学习工具 |
| [yp-dlp](yp-dlp/) | 视频下载 | yt-dlp | 通用下载器 |

---

### yuque-exporter

语雀知识库导出工具，将私有知识库批量导出为 Markdown。

**测试的 AI 能力：**
- HTML → Markdown 结构化转换
- 批量数据处理流程设计
- 知识库元数据管理

**产品化方向：**
- 多平台知识库迁移服务（语雀、Notion、飞书）
- 个人知识备份工具

```bash
# 快速使用
pip install httpx html2text
python3 yuque_extractor.py --all -t /path/to/output
```

---

### douyin-extractor

短视频分析工具，从视频中提取关键帧和语音转录。

**测试的 AI 能力：**
- Whisper 语音识别准确度
- 视频帧提取与时间轴对齐
- 截图 + 文案的结构化输出

**产品化方向：**
- 短视频内容分析平台
- 视频学习笔记生成器
- 视频搜索工具（基于转录文本）

```bash
# 分析本地视频
cp your_video.mp4 videos/
python3 scripts/analyze_local_video.py --whisper-model small
```

输出：每帧截图 + 对应时间段的文案，便于 AI 分析视频内容。

---

### bookmark-to-wiki

浏览器收藏夹批量导入知识库。

**测试的 AI 能力：**
- 网页内容智能提取
- 批量 URL 处理流程
- 与 llm-wiki 的集成

**产品化方向：**
- 个人知识库构建工具
- 信息聚合与整理服务

```bash
# 提取 Chrome 收藏夹的特定文件夹
python3 extract_bookmarks.py --browser chrome --folder "优秀系列文章"
# 批量抓取文章内容
python3 fetch_articles.py --input urls.txt --output ~/knowledge/raw/articles/
```

---

### video-transcript-bilingual

视频双语转录工具，自动下载视频并生成中英双语文稿。

**测试的 AI 能力：**
- 多语言语音识别
- 自动翻译质量
- 字幕 → 文稿转换

**产品化方向：**
- 视频学习笔记工具
- 多语言字幕生成服务
- 在线课程本地化

```bash
python3 scripts/video_to_transcript.py --url "<VIDEO_URL>"
```

---

### yp-dlp

基于 yt-dlp 的视频下载工具。

**测试的 AI 能力：**
- 多平台视频源适配
- 音视频分离与合并

---

## 技术栈

| 领域 | 技术 |
|------|------|
| 语言识别 | Whisper (faster-whisper) |
| 视频处理 | FFmpeg, yt-dlp |
| 网页抓取 | httpx, Chrome CDP |
| HTML 解析 | html2text, BeautifulSoup |
| LLM 集成 | Claude Code, llm-wiki |

## 后续规划

### 近期目标
- 完善 CLI 交互体验
- 添加错误处理和日志
- 统一配置管理

### 产品化方向
- **知识管理** - yuque-exporter + bookmark-to-wiki 整合为个人知识库构建工具
- **视频学习** - douyin-extractor + video-transcript 整合为视频笔记生成器
- **AI 编程** - 基于 claude code 经验开发定制化编程助手

### 技术探索
- 测试更多 LLM 模型（GPT-4、Gemini 等）
- 探索多模态 AI（视频理解、图像分析）
- 尝试 Agent 编程模式

## 快速开始

每个子项目有独立的依赖和运行方式，详见各目录的 README。

通用依赖：

```bash
# Python 项目
pip install -r requirements.txt

# FFmpeg（视频处理）
brew install ffmpeg

# yt-dlp（视频下载）
brew install yt-dlp
```

## 贡献

本项目为个人学习项目，暂不接受外部贡献。如有想法交流，欢迎提 Issue。

## License

MIT