# AI 新闻与技术文章自动抓取系统

> 自动抓取全球 AI 新闻和技术文章，沉淀到知识库

## 项目目标

1. 定时抓取全球 AI 相关新闻（每日/每周）
2. 抓取 AI 技术文章（深度教程、论文解读等）
3. 自动调用 llm-wiki 消化文章，沉淀到知识库
4. 分类存储：`raw/news/` 和 `raw/tech-articles/`

## 技术栈

- Python 3.x — 主要抓取逻辑
- Shell scripts — 定时任务调度
- llm-wiki skill — 文章消化和知识沉淀
- RSS/API/Web scraping — 数据源

## 知识库路径

目标知识库：`/Users/zhanghao/Downloads/笔记/笔记`
- `raw/news/` — AI 新闻存储
- `raw/tech-articles/` — AI 技术文章存储
- 参考：`llm-wiki-guide.md` 使用指南

## 数据源规划

### AI 新闻源
- Anthropic Blog
- OpenAI Blog
- Google AI Blog
- MIT Technology Review AI
- VentureBeat AI
- The Verge AI
- 36氪 AI
- 机器之心

### AI 技术文章源
- arXiv CS.AI
- Hugging Face Blog
- Papers With Code
- Distill.pub
- GitHub Trending AI repos
- Stack Overflow AI tags

## 编码规范

- 每个 Python 脚本功能单一
- 配置文件使用 YAML 格式
- 日志记录每次抓取详情
- 错误处理完善，失败时记录原因

## 开发流程

1. 选择 feature_list.json 中未完成功能
2. 开发单个功能
3. 测试验证
4. git commit + 更新 claude-progress.txt

## 重要文件

- `feature_list.json` — 功能需求列表
- `claude-progress.txt` — 进度日志
- `config/sources.yaml` — 数据源配置
- `scripts/` — 各抓取脚本
- `agent-run.log` — 运行日志