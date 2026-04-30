#!/bin/bash
# 语雀知识库批量导出脚本
# 用法：./yuque-export.sh [命令]
# 命令：list-repos | list-docs <repo_id> | export-doc <repo_id> <doc_id> | export-repo <repo_id> | export-all

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

# 检查配置文件
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "错误：配置文件不存在"
  echo "请复制 config.example.json 为 config.json 并填写你的 API Token"
  exit 1
fi

# 读取配置
API_TOKEN=$(jq -r '.api_token' "$CONFIG_FILE")
USER_ID=$(jq -r '.user_id' "$CONFIG_FILE")
OUTPUT_DIR=$(jq -r '.output_dir' "$CONFIG_FILE")
TARGET_WIKI_ROOT=$(jq -r '.target_wiki_root' "$CONFIG_FILE")

# 语雀 API 基础 URL
API_BASE="https://www.yuque.com/api/v2"

# 请求头
HEADER_AUTH="X-Auth-Token: $API_TOKEN"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# API 请求函数
api_get() {
  local url="$1"
  curl -s -H "$HEADER_AUTH" "$url"
}

# 获取所有知识库列表
list_repos() {
  echo "获取用户 $USER_ID 的知识库列表..."
  api_get "$API_BASE/users/$USER_ID/repos" | jq '.data[] | {id: .id, name: .name, slug: .slug, public: .public, docs_count: .docs_count}'
}

# 获取知识库内的文档列表
list_docs() {
  local repo_id="$1"
  echo "获取知识库 $repo_id 的文档列表..."
  api_get "$API_BASE/repos/$repo_id/docs" | jq '.data[] | {id: .id, title: .title, slug: .slug, word_count: .word_count}'
}

# 导出单个文档
export_doc() {
  local repo_id="$1"
  local doc_id="$2"
  local repo_name="$3"
  local doc_title="$4"

  echo "导出文档：$doc_title"

  # 获取文档内容
  local doc_content
  doc_content=$(api_get "$API_BASE/repos/$repo_id/docs/$doc_id")

  # 提取标题和正文
  local title=$(echo "$doc_content" | jq -r '.data.title')
  local body=$(echo "$doc_content" | jq -r '.data.body')
  local created_at=$(echo "$doc_content" | jq -r '.data.created_at')
  local updated_at=$(echo "$doc_content" | jq -r '.data.updated_at')

  # 格式化日期
  local created_date=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$created_at" "+%Y-%m-%d" 2>/dev/null || echo "$created_at" | cut -dT -f1)

  # 创建知识库子目录
  local repo_dir="$OUTPUT_DIR/$repo_name"
  mkdir -p "$repo_dir"

  # 生成文件名
  local safe_title=$(echo "$title" | sed 's/[\/\\:*?"<>|]/-/g' | sed 's/ /-/g')
  local filename="$repo_dir/${created_date}-${safe_title}.md"

  # 写入文件（带 frontmatter）
  {
    echo "---"
    echo "source_id: yuque-${repo_id}-${doc_id}"
    echo "source_type: yuque"
    echo "title: $title"
    echo "created: $created_date"
    echo "yuque_repo: $repo_name"
    echo "yuque_url: https://www.yuque.com/$USER_ID/$repo_name/$safe_title"
    echo "tags:"
    echo "  - 语雀导入"
    echo "---"
    echo ""
    echo "# $title"
    echo ""
    echo "> 来源：语雀知识库「$repo_name」"
    echo ""
    echo "$body"
  } > "$filename"

  echo "已保存：$filename"
}

# 导出整个知识库
export_repo() {
  local repo_id="$1"

  # 获取知识库信息
  local repo_info
  repo_info=$(api_get "$API_BASE/repos/$repo_id")
  local repo_name=$(echo "$repo_info" | jq -r '.data.slug')
  local repo_title=$(echo "$repo_info" | jq -r '.data.name')

  echo "=========================================="
  echo "导出知识库：$repo_title ($repo_name)"
  echo "=========================================="

  # 获取文档列表
  local docs
  docs=$(api_get "$API_BASE/repos/$repo_id/docs")

  # 统计文档数量
  local doc_count=$(echo "$docs" | jq '.data | length')
  echo "共有 $doc_count 篇文档"

  # 逐个导出
  local index=0
  echo "$docs" | jq -c '.data[]' | while read doc; do
    index=$((index + 1))
    local doc_id=$(echo "$doc" | jq -r '.id')
    local doc_title=$(echo "$doc" | jq -r '.title')

    echo "[$index/$doc_count] 导出：$doc_title"
    export_doc "$repo_id" "$doc_id" "$repo_name" "$doc_title"

    # 避免请求过快
    sleep 0.5
  done

  echo "知识库「$repo_title」导出完成！"
  echo "文件保存在：$OUTPUT_DIR/$repo_name/"
}

# 导出所有知识库
export_all() {
  echo "=========================================="
  echo "批量导出所有知识库"
  echo "=========================================="

  # 获取知识库列表
  local repos
  repos=$(api_get "$API_BASE/users/$USER_ID/repos")

  # 统计数量
  local repo_count=$(echo "$repos" | jq '.data | length')
  echo "共有 $repo_count 个知识库"

  # 逐个导出
  local index=0
  echo "$repos" | jq -c '.data[]' | while read repo; do
    index=$((index + 1))
    local repo_id=$(echo "$repo" | jq -r '.id')
    local repo_name=$(echo "$repo" | jq -r '.data.slug')

    echo ""
    echo "[$index/$repo_count] 处理知识库..."
    export_repo "$repo_id"

    # 避免请求过快
    sleep 1
  done

  echo ""
  echo "=========================================="
  echo "全部导出完成！"
  echo "=========================================="
  echo "文件保存在：$OUTPUT_DIR/"
  echo ""
  echo "下一步：在 Claude Code 中运行"
  echo "  /llm-wiki 帮我批量消化 $OUTPUT_DIR/"
}

# 主命令路由
case "$1" in
  list-repos)
    list_repos
    ;;
  list-docs)
    if [[ -z "$2" ]]; then
      echo "用法：$0 list-docs <repo_id>"
      exit 1
    fi
    list_docs "$2"
    ;;
  export-doc)
    if [[ -z "$2" || -z "$3" ]]; then
      echo "用法：$0 export-doc <repo_id> <doc_id>"
      exit 1
    fi
    export_doc "$2" "$3" "unknown" "unknown"
    ;;
  export-repo)
    if [[ -z "$2" ]]; then
      echo "用法：$0 export-repo <repo_id>"
      exit 1
    fi
    export_repo "$2"
    ;;
  export-all)
    export_all
    ;;
  *)
    echo "语雀知识库批量导出脚本"
    echo ""
    echo "用法："
    echo "  $0 list-repos              查看所有知识库"
    echo "  $0 list-docs <repo_id>     查看知识库内的文档"
    echo "  $0 export-repo <repo_id>   导出单个知识库"
    echo "  $0 export-all              导出所有知识库"
    echo ""
    echo "前置条件："
    echo "  1. 复制 config.example.json 为 config.json"
    echo "  2. 在 config.json 中填写 API Token 和用户 ID"
    ;;
esac