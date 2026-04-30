#!/bin/bash
# init.sh — AI 新闻抓取系统启动脚本

echo "========================================="
echo "AI 新闻与技术文章自动抓取系统"
echo "========================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
  echo "❌ Python3 未安装"
  exit 1
fi

echo "Python 版本: $(python3 --version)"

# 检查配置文件
if [ ! -f "config/sources.yaml" ]; then
  echo "⚠️ 数据源配置文件不存在，需要先创建"
fi

# 检查知识库路径
WIKI_PATH="/Users/zhanghao/Downloads/笔记/笔记"
if [ ! -d "$WIKI_PATH/raw" ]; then
  echo "❌ 知识库 raw 目录不存在"
  exit 1
fi

echo "知识库路径: $WIKI_PATH"
echo ""
echo "✅ 环境检查完成"
echo ""
echo "使用方式:"
echo "  python3 scripts/fetch_anthropic.py   # 抓取 Anthropic 博客"
echo "  python3 scripts/fetch_openai.py      # 抓取 OpenAI 博客"
echo "  bash scripts/cron-runner.sh          # 定时任务调度"
echo ""