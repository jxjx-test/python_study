# 轻量级实用 Python 项目模板（中文）

这是一个开箱即用的轻量级 Python 项目模板，适合快速启动实用型的小工具或服务。模板包含：
- 标准化的 src 布局与打包配置（pyproject.toml，基于 setuptools）
- 一个可运行的命令行工具示例（litepy）
- 基础的 .gitignore
- 清晰的开发与发布指引

如果你还没有最终的项目方向，可以先用本模板跑通开发流程，再逐步替换/扩展为自己的业务功能。

## 为什么选“轻量 + 实用”
- 轻量：尽量零依赖或少依赖，降低维护成本与打包复杂度。
- 实用：聚焦实际需求，沉淀可复用的小工具或组件。

## 推荐的项目选题（可直接基于本模板实现）
以下都是能在短时间内上线的小而美工具，便于渐进式迭代：
1. 本地文件整理器
   - 按扩展名/时间/规则自动归类下载目录或照片目录。
   - 可添加“预览模式”和“回滚/回收站”机制，保证安全。
2. 命令行待办清单（Todo CLI）
   - 本地 JSON/YAML 存储，提供 add/list/done/search 等子命令。
   - 进一步可加入提醒、优先级和标签。
3. 轻量 URL/服务可用性探测
   - 定时请求一组 URL，记录响应时间与状态，输出报告。
   - 可选加入 Webhook/邮件通知（失败或延迟过高时）。
4. 图片/文档批处理工具
   - 批量重命名、压缩、转换格式或提取文本（Tesseract 可选）。
   - 可扩展为插件体系：每个命令一个插件。
5. Markdown 小助手
   - 将标题自动生成目录、slug，或批量补充 Front Matter。
   - 结合静态站点工作流，提升写作与发布效率。
6. 小型个人数据聚合器（内置示例，见下文）
   - 抓取/合并常用数据（RSS/Atom），导出统一 JSON 或文本。
   - 命令行 + 可嵌入脚本的库函数，两用。

更多选题灵感：
- 日志裁剪/敏感信息脱敏工具
- 目录图片批量压缩/转 WebP（可选调用系统工具）
- 简易短链接批量生成器（本地维护映射）
- Markdown/笔记索引器：给笔记库生成索引与反向链接
- 轻量 API Mock Server（内置几条路由，读取 JSON 响应）
- 网页快照归档（定期拉取页面保存 HTML/PDF 哈希）

你可以先挑一个最小可用场景（MVP）开始，后续逐步演进。

## 快速开始

前置要求：
- Python 3.9+

步骤：
1) 创建并激活虚拟环境
- macOS/Linux
  python3 -m venv .venv
  source .venv/bin/activate
- Windows（PowerShell）
  python -m venv .venv
  .venv\\Scripts\\Activate.ps1

2) 安装（开发模式）
  pip install -e .

3) 运行命令行工具
  litepy --help

示例：
- 问候
  litepy hello
  litepy hello 小明
- 生成 slug
  litepy slug "你好，世界! Python 3.11"
- 计算文件 SHA256 哈希
  litepy hash path/to/file

## 内置示例：RSS/Atom 个人数据聚合器

已提供轻量级聚合实现（不依赖第三方库，纯标准库）。用于聚合“薅羊毛福利”“新闻热点”“八卦/娱乐”等信息源。

- 查看源分类及数量
  litepy feed sources

- 抓取并输出最新条目（自动寻找 ./sources.json 或 ./sources.example.json）
  litepy feed fetch --limit 30

- 仅抓取某一分类（deals/news/entertainment）
  litepy feed fetch --category news --limit 20

- 仅保留近 24 小时内的内容
  litepy feed fetch --since 24 --limit 50

- 输出 JSON 供后续处理
  litepy feed fetch --json > out.json

自定义源：
- 在项目根目录复制一份 sources.example.json 为 sources.json，并按需增删 URL。
- 也可用 --sources 指定任意路径。

内置解析策略：
- 支持 RSS/Atom 常见字段（title/link/published/updated/description/summary/content）。
- 自动按发布时间倒序、简单去重（以链接为主）。
- 非常规源可能需要你替换为其它可用 RSS（如官方/第三方 RSSHub 等）。

扩展建议：
- 增加本地存储与去重：将已读链接写入 SQLite/JSON，避免重复推送。
- 加入计划任务：crontab 或 APScheduler 定时抓取。
- 推送渠道：Webhook/企业微信/飞书/邮件等（可在 CLI 中新增子命令）。
- 规则过滤：按关键词/正则/黑白名单筛选条目。

## 项目结构

- README.md                  项目说明（本文件）
- pyproject.toml             构建与打包配置（setuptools + PEP 621）
- .gitignore                 Git 忽略配置
- sources.example.json       聚合器示例源配置（复制为 sources.json 自定义）
- src/
  - litepy/                  示例包（可替换为你的包名）
    - __init__.py
    - cli.py                 命令行入口（argparse 实现）
    - feeds.py               RSS/Atom 抓取与解析

建议保持 src 布局（隔离包导入路径，避免测试/脚本误导入）。

## 代码风格与质量（建议）
- 命名遵循 PEP 8，必要时写最小必要注释。
- 可以后续接入：
  - ruff/flake8：静态检查
  - black：代码格式化
  - mypy：类型检查
  - pytest：单元测试

## 发布与分发（可选）
- 构建轮子
  python -m build
- 本地安装测试
  pip install dist/*.whl
- 上传 PyPI（需配置凭据）
  python -m twine upload dist/*

若当前仅作为内部工具使用，保留 editable 安装即可。

## 自定义与下一步
- 将包名 litepy 替换为你的实际项目名（例如 mytool）。
  - 重命名 src/litepy 目录
  - 更新 pyproject.toml 的 project.name 与入口点
- 在 cli.py 中添加/替换你需要的子命令和逻辑。
- 若计划发布到 PyPI，完善作者、版权、LICENSE、版本策略等信息。

## 常见问题（FAQ）
- 为何没有引入第三方依赖？
  - 作为模板，尽量保持轻量，避免不必要的耦合。实际项目可按需添加。
- Windows 与 Linux/Mac 的兼容性？
  - 本模板不依赖平台特性，命令行逻辑均可跨平台运行。

——
如需更具体的功能建议或实现示例，可以直接在 issues 中提出需求，我会给出更贴近业务的落地方案。
