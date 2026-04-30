#!/bin/bash
# cron-runner.sh — 定时任务调度脚本
# 用法: bash scripts/cron-runner.sh [daily|weekly|test]

MODE=${1:-"daily"}
LOG_DIR="logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/run-$DATE.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

echo "=========================================="  | tee "$LOG_FILE"
echo "AI 新闻抓取系统 - 定时任务"                 | tee -a "$LOG_FILE"
echo "模式: $MODE"                                | tee -a "$LOG_FILE"
echo "时间: $(date)"                              | tee -a "$LOG_FILE"
echo "=========================================="  | tee -a "$LOG_FILE"
echo ""                                           | tee -a "$LOG_FILE"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
  echo "❌ Python3 未安装"                        | tee -a "$LOG_FILE"
  exit 1
fi

# 检查依赖
pip3 show feedparser &> /dev/null || pip3 install feedparser

case $MODE in
  daily)
    echo "[执行] 每日抓取任务..."                  | tee -a "$LOG_FILE"

    # 抓取 AI 新闻
    echo ""                                       | tee -a "$LOG_FILE"
    echo "--- Anthropic Blog ---"                  | tee -a "$LOG_FILE"
    python3 scripts/fetch_anthropic.py             | tee -a "$LOG_FILE"

    echo ""                                       | tee -a "$LOG_FILE"
    echo "--- OpenAI Blog ---"                     | tee -a "$LOG_FILE"
    python3 scripts/fetch_openai.py                | tee -a "$LOG_FILE"

    # 抓取技术文章
    echo ""                                       | tee -a "$LOG_FILE"
    echo "--- Hugging Face Blog ---"               | tee -a "$LOG_FILE"
    python3 scripts/fetch_huggingface.py           | tee -a "$LOG_FILE"
    ;;

  weekly)
    echo "[执行] 每周深度抓取任务..."              | tee -a "$LOG_FILE"

    # 执行所有抓取脚本
    for script in scripts/fetch_*.py; do
      echo ""                                     | tee -a "$LOG_FILE"
      echo "--- $script ---"                       | tee -a "$LOG_FILE"
      python3 "$script"                            | tee -a "$LOG_FILE"
    done
    ;;

  test)
    echo "[执行] 测试模式（仅抓取一篇）..."        | tee -a "$LOG_FILE"
    python3 scripts/fetch_anthropic.py             | tee -a "$LOG_FILE"
    ;;

  *)
    echo "❌ 未知模式: $MODE"                      | tee -a "$LOG_FILE"
    echo "用法: bash cron-runner.sh [daily|weekly|test]"
    exit 1
    ;;
esac

echo ""                                           | tee -a "$LOG_FILE"
echo "=========================================="  | tee -a "$LOG_FILE"
echo "执行完成: $(date)"                          | tee -a "$LOG_FILE"
echo "日志文件: $LOG_FILE"                        | tee -a "$LOG_FILE"
echo "=========================================="  | tee -a "$LOG_FILE"