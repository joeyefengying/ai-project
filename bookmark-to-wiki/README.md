# Bookmark to Wiki

批量将浏览器收藏夹中的文章提取并导入 llm-wiki 知识库。

## 功能

- 解析 Chrome/Safari/Firefox 浏览器收藏夹
- **支持按文件夹提取**（如只提取"优秀系列文章"）
- 批量调用 `baoyu-url-to-markdown` 抓取文章内容
- 输出到指定目录供 llm-wiki 批量消化

## 使用方式

### 第一步：提取收藏夹 URL 列表

```bash
# 提取特定文件夹（推荐）
python3 extract_bookmarks.py --browser chrome --folder "优秀系列文章"

# Chrome 全部收藏夹
python3 extract_bookmarks.py --browser chrome

# Safari 收藏夹
python3 extract_bookmarks.py --browser safari

# 自定义收藏夹文件路径
python3 extract_bookmarks.py --browser chrome --file ~/path/to/Bookmarks --folder "文件夹名"

# 限制数量（用于测试）
python3 extract_bookmarks.py --browser chrome --folder "优秀系列文章" --limit 20
```

输出：`urls.txt`（URL 列表）

### 第二步：批量抓取文章内容

```bash
# 抓取所有 URL，输出到知识库 raw/articles/
python3 fetch_articles.py --input urls.txt --output ~/Downloads/笔记/笔记/raw/articles/

# 限制抓取数量（用于测试）
python3 fetch_articles.py --input urls.txt --output ~/Downloads/笔记/笔记/raw/articles/ --limit 10
```

### 第三步：批量消化到知识库

在 Claude Code 中运行：

```
/llm-wiki 批量消化 raw/articles/
```

### 一键运行

```bash
bash run.sh ~/Downloads/笔记/笔记
````

## 支持的浏览器

| 浏览器 | 默认收藏夹位置 |
|--------|----------------|
| Chrome | `~/Library/Application Support/Google/Chrome/Default/Bookmarks` |
| Safari | `~/Library/Safari/Bookmarks.plist` |
| Firefox | `~/Library/Application Support/Firefox/Profiles/*/places.sqlite` |

## 依赖

- Python 3.10+
- `baoyu-url-to-markdown` skill（已安装在 Claude Code）

## 项目结构

```
bookmark-to-wiki/
├── README.md
├── extract_bookmarks.py   # 解析收藏夹，提取 URL
├── fetch_articles.py      # 批量抓取文章内容
├── requirements.txt
└── urls.txt               # 输出的 URL 列表
```