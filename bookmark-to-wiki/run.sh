#!/bin/bash
# run.sh - 一键运行收藏夹提取和文章抓取

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WIKI_ROOT="${1:-$HOME/Downloads/笔记/笔记}"

echo "=== Bookmark to Wiki ==="
echo ""
echo "Wiki 根目录: $WIKI_ROOT"
echo ""

# 第一步：提取收藏夹 URL
echo "[Step 1] 提取 Chrome 收藏夹 URL..."
python3 "$SCRIPT_DIR/extract_bookmarks.py" --browser chrome

# 显示统计
URL_COUNT=$(wc -l < "$SCRIPT_DIR/urls.txt" | tr -d ' ')
echo ""
echo "提取完成，共 $URL_COUNT 条可抓取 URL"
echo ""

# 询问是否继续
read -p "是否开始批量抓取？（y/n）: " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "已暂停。URL 列表保存在: $SCRIPT_DIR/urls.txt"
    echo "后续可运行："
    echo "  python3 fetch_articles.py --input urls.txt --output $WIKI_ROOT/raw/articles/"
    exit 0
fi

# 第二步：批量抓取
echo ""
echo "[Step 2] 批量抓取文章内容..."

# 询问抓取数量
read -p "抓取数量（默认全部，输入数字限制）: " limit
if [[ -n "$limit" && "$limit" =~ ^[0-9]+$ ]]; then
    python3 "$SCRIPT_DIR/fetch_articles.py" \
        --input "$SCRIPT_DIR/urls.txt" \
        --output "$WIKI_ROOT/raw/articles/" \
        --limit "$limit"
else
    python3 "$SCRIPT_DIR/fetch_articles.py" \
        --input "$SCRIPT_DIR/urls.txt" \
        --output "$WIKI_ROOT/raw/articles/"
fi

echo ""
echo "=== 完成 ==="
echo ""
echo "下一步：在 Claude Code 中运行"
echo "  /llm-wiki 批量消化 raw/articles/"