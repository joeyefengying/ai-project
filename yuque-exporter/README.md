# 语雀知识库导出工具

将语雀知识库导出为 Markdown 格式，支持 HTML 自动转换为纯 Markdown。

## 特性

- ✅ 基于 Cookies 认证，支持个人版用户
- ✅ HTML 自动转换为 Markdown
- ✅ 知识库名称作为文件夹名
- ✅ 生成文件列表供 LLM 消化
- ✅ 支持自定义目标目录

## 安装依赖

```bash
pip install httpx html2text
```

## 获取 Cookies

1. 在浏览器登录语雀：https://www.yuque.com
2. 安装 **Cookie-Editor** 扩展
3. 点击扩展 → **Export** → 选择 **Netscape** 格式
4. 保存为 `cookies.txt` 放到本项目目录

## 使用方法

### 1. 列出知识库

```bash
python3 yuque_extractor.py --list
```

### 2. 导出单个知识库

```bash
python3 yuque_extractor.py --repo <slug> -t /path/to/notes/语雀
```

### 3. 导出所有知识库（推荐）

```bash
# 导出到笔记目录
python3 yuque_extractor.py --all -t "/Users/zhanghao/Downloads/笔记/笔记/语雀"

# 导出完成后，使用 llm-wiki 消化
/llm-wiki 帮我消化这个文件：/Users/zhanghao/Downloads/笔记/笔记/语雀/语雀文件列表.md
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--list` | 列出所有知识库 |
| `--repo <slug>` | 导出指定知识库 |
| `--all` | 导出所有知识库 |
| `-c/--cookie` | Cookies 文件路径（默认 cookies.txt） |
| `-o/--output` | 临时导出目录（默认 yuque-export） |
| `-t/--target` | 目标笔记目录 |
| `--no-file-list` | 不生成文件列表 |

## 导出结果

导出的 Markdown 文件包含 frontmatter 元数据：

```markdown
---
source_type: yuque
title: 文档标题
yuque_repo: 知识库名称
yuque_url: https://www.yuque.com/user/repo/doc
tags:
  - 语雀导入
---

# 文档标题

正文内容（已转换为 Markdown 格式）
```

## 文件结构

```
目标目录/语雀/
├── 知识库1/
│   ├── 文档1.md
│   ├── 文档2.md
│   └── ...
├── 知识库2/
│   └── ...
├── 语雀文件列表.md  # 供 llm-wiki 使用
```

## 注意事项

- 导出间隔默认 10 秒，避免触发语雀 429 限制
- 如遇到 429 错误，等待几分钟后重新运行即可
- 图片链接保留原始 URL，可后续批量下载

## 后续使用

导出完成后，在 Claude Code 中运行：

```
/llm-wiki 帮我消化这个文件：目标目录/语雀/语雀文件列表.md
```

LLM Wiki 会自动读取并处理所有导出的文档。