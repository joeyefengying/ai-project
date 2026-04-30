# AI 新闻与技术文章自动抓取系统

自动抓取全球 AI 新闻和技术文章，翻译成中文，沉淀到知识库。

## 功能概览

| 功能 | 状态 | 说明 |
|------|------|------|
| 多数据源抓取 | ✅ | Anthropic、OpenAI、HuggingFace、arXiv、36氪、机器之心 |
| 自动去重 | ✅ | 避免重复抓取同一文章 |
| 文章分类存储 | ✅ | 新闻存 `raw/news/`，技术文章存 `raw/tech-articles/` |
| 中文翻译 | ✅ | 标题和正文自动翻译，保留原文对照 |
| 定时任务调度 | ✅ | `cron-runner.sh` 支持定时执行 |
| llm-wiki 集成 | ✅ | 可调用 llm-wiki 消化文章 |
| 状态报告 | ✅ | 运行状态统计和报告生成 |

## 抓取的文章来源

### 新闻类 (raw/news/)

| 数据源 | 脚本 | 说明 |
|--------|------|------|
| Anthropic Blog | `fetch_anthropic.py` | Claude 相关产品和技术动态 |
| OpenAI Blog | `fetch_openai.py` | GPT、Codex 等 OpenAI 产品动态 |
| 36氪 AI | `fetch_36kr.py` | 中文 AI 行业新闻 |
| 机器之心 | `fetch_jiqizhixin.py` | 中文 AI 技术资讯 |

### 技术文章类 (raw/tech-articles/)

| 数据源 | 脚本 | 说明 |
|--------|------|------|
| Hugging Face Blog | `fetch_huggingface.py` | ML 模型、开源工具技术文章 |
| arXiv cs.AI | `fetch_arxiv.py` | AI 学术论文最新发布 |

## 文件说明

```
ai-news-fetcher/
├── scripts/
│   ├── fetch_anthropic.py    # Anthropic 博客抓取
│   ├── fetch_openai.py       # OpenAI 博客抓取
│   ├── fetch_huggingface.py  # Hugging Face 博客抓取
│   ├── fetch_arxiv.py        # arXiv 论文抓取
│   ├── fetch_36kr.py         # 36氪 AI 新闻抓取
│   ├── fetch_jiqizhixin.py   # 机器之心抓取
│   ├── translate_articles.py # 文章翻译脚本
│   ├── digest_articles.py    # llm-wiki 消化脚本
│   ├── dedup_manager.py      # 去重管理
│   ├── status_reporter.py    # 状态报告
│   └── cron-runner.sh        # 定时任务调度
├── config/
│   └── sources.yaml          # 数据源配置
├── cache/
│   ├── fetched_articles.json # 已抓取文章缓存
│   └── article_dedup.json    # 去重缓存
├── logs/
│   └ errors.log              # 错误日志
│   └ status_report.md        # 状态报告
├── feature_list.json         # 功能列表
└── claude-progress.txt       # 开发进度日志
```

## 使用方法

### 1. 单独抓取某个数据源

```bash
# 抓取 Anthropic 博客
python3 scripts/fetch_anthropic.py

# 抓取 OpenAI 博客
python3 scripts/fetch_openai.py

# 抓取 Hugging Face 博客
python3 scripts/fetch_huggingface.py

# 抓取 arXiv AI 论文
python3 scripts/fetch_arxiv.py

# 抓取 36氪 AI 新闻
python3 scripts/fetch_36kr.py

# 抓取机器之心
python3 scripts/fetch_jiqizhixin.py
```

### 2. 执行所有抓取

```bash
# 运行定时任务（默认抓取所有源）
bash scripts/cron-runner.sh
```

### 3. 翻译文章

```bash
# 翻译单篇文章
python3 scripts/translate_articles.py "/path/to/article.md" --service google

# 翻译所有新闻
python3 scripts/translate_articles.py --news --limit 20 --service google

# 翻译所有技术文章
python3 scripts/translate_articles.py --tech --limit 20 --service google

# 翻译所有文章
python3 scripts/translate_articles.py --all --limit 50 --service google
```

**翻译说明：**
- 使用 Google Translate (免费，无需 API key)
- 翻译后的文件以 `-zh.md` 结尾
- 包含中文标题、翻译正文、原文对照

### 4. 查看状态报告

```bash
# 文本报告
python3 scripts/status_reporter.py

# JSON 格式
python3 scripts/status_reporter.py -f json

# 简短摘要
python3 scripts/status_reporter.py --summary
```

### 5. 消化文章到 wiki

```bash
# 查看待消化文章
python3 scripts/digest_articles.py --status

# 列出待消化文章
python3 scripts/digest_articles.py --list

# 在 Claude Code 中执行消化
# /llm-wiki digest <文章路径>
```

## 知识库路径

文章保存到：
```
/Users/zhanghao/Downloads/笔记/笔记/raw/
├── news/           # AI 新闻（中文翻译）
│   └── xxx-zh.md   # 中文标题 + 翻译正文 + 原文对照
└── tech-articles/  # AI 技术文章（中文翻译）
    └── xxx-zh.md   # 中文标题 + 翻译正文 + 原文对照
```

## 当前已抓取文章

- **新闻**: 20 篇（全部已翻译为中文）
- **技术文章**: 20 篇（全部已翻译为中文）
- **总计**: 40 篇

> 每篇翻译文章包含中文标题、翻译正文和原文对照

## 注意事项

1. **完整内容抓取**：当前通过 RSS 抓取摘要，完整正文抓取需要网络稳定后优化
2. **翻译质量**：Google Translate 免费，专业术语翻译可能不如付费 API 准确
3. **请求频率**：脚本内置请求间隔，避免被数据源封禁
4. **API Key**：如需使用 OpenAI 翻译，设置 `OPENAI_API_KEY` 环境变量

## 后续优化计划

- [ ] 完整正文抓取（而非仅摘要）
- [ ] 更精准的技术术语翻译
- [ ] 支持更多数据源（Google AI、MIT TR 等）
- [ ] 自动消化到 llm-wiki