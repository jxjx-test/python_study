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

## 使用说明（TL;DR）
- 环境要求：Python 3.9+
- 安装与验证：
  - 创建虚拟环境并激活（见下方“快速开始”）
  - 安装：pip install -e .
  - 验证：litepy --help
- 常用命令：
  - litepy hello [name]
  - litepy slug "文本"
  - litepy hash path/to/file
- RSS/Atom 聚合器：
  - 推荐数据库模式（自动去重与缓存）
    - 初始化：litepy feed init
    - 列出源：litepy feed list
    - 抓取：litepy feed fetch --limit 30
    - 仅导出近 24 小时：litepy feed fetch --since 24 --limit 50
    - JSON 输出：litepy feed fetch --json > out.json
    - 指定数据库：litepy feed fetch --db /path/to/myfeeds.db
    - 添加自定义源：litepy feed add --url https://example.com/feed.xml --category tech
  - 文件源模式（无需数据库）：
    - 查看内置/文件源：litepy feed sources
    - 从文件源抓取：litepy feed fetch --use-file --limit 30
    - 指定文件：litepy feed fetch --use-file --sources ./sources.json --limit 50
- 默认数据库位置：data/feeds.db（自动创建）

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
  .venv\Scripts\Activate.ps1

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

## 内置示例：RSS/Atom 个人数据聚合器（开箱即用｜支持内置源与自定义源）

现在提供两种模式：
- 数据库模式（推荐）：自带内置源，支持自定义源写入 SQLite，自动去重与 ETag/Last-Modified 缓存，真正开箱即用。
- 文件源模式（兼容旧方式）：读取 sources.json 或内置示例，适合一次性拉取或脚本拼接。

内置源覆盖常见的资讯/科技/社区：
- deals: 什么值得买
- news: BBC 中文网、路透中文、纽约时报中文网、FT 中文网
- tech: V2EX、少数派、Solidot、阮一峰博客、爱范儿、OSChina、36 氪
- entertainment: 煎蛋、Engadget 中文

数据库模式使用方法：
- 初始化数据库并写入内置源
  litepy feed init
- 查看源列表
  litepy feed list
- 添加自定义源
  litepy feed add --url https://example.com/feed.xml --category tech
- 抓取并输出最新条目（默认使用 data/feeds.db）
  litepy feed fetch --limit 30
- 仅导出近 24 小时内内容
  litepy feed fetch --since 24 --limit 50
- 输出 JSON（便于后续处理/推送）
  litepy feed fetch --json > out.json
- 指定数据库位置（可选）
  litepy feed fetch --db /path/to/myfeeds.db

文件源模式（无需数据库）：
- 查看源分类及数量（自动寻找 ./sources.json 或 ./sources.example.json）
  litepy feed sources
- 从文件源抓取
  litepy feed fetch --use-file --limit 30
- 指定文件
  litepy feed fetch --use-file --sources ./sources.json --limit 50

实现要点：
- 解析：纯标准库 xml.etree + email.utils + ISO-8601，兼容 RSS 与 Atom。
- 去重：数据库模式按 feed_id + link 去重，重复条目会更新标题/摘要/时间。
- 缓存：支持 ETag/Last-Modified 条件请求，减少流量与站点压力。
- 内置源：首次使用数据库模式会自动写入内置源，可随时新增/删除自定义源。

扩展建议：
- 增加计划任务：crontab 或 APScheduler 定时抓取。
- 推送渠道：Webhook/企业微信/飞书/邮件等（可在 CLI 中新增子命令）。
- 规则过滤：按关键词/正则/黑白名单筛选条目。

## 开发计划（建议路线图）
- M1 最小可用版（已提供）
  - CLI: litepy feed fetch/sources，支持 sources.json、自带示例源。
  - 输出文本/JSON，按时间排序、简单去重。
- M2 持久化与去重（已实现）
  - 新增本地 SQLite（标准库 sqlite3），记录已抓取条目与源，避免重复。
  - 支持 ETag/Last-Modified 缓存，减少不必要的下载。
  - 新增 feed init/add/list/fetch 子命令；默认走数据库模式。
- M3 过滤与规则
  - 支持包含/排除关键词、正则；按来源/域名过滤。
  - 支持只输出标题命中或正文摘要命中的条目；高亮命中关键词（文本模式）。
- M4 输出形态与推送
  - 新增 --format markdown/html；支持生成日报/周报文件。
  - 推送集成：Webhook（如企业微信/飞书/钉钉），邮件发送（smtplib）。
- M5 计划任务与运行时
  - 提供轻量守护进程模式：定时抓取、过滤、推送。
  - 支持并发抓取与重试。
- M6 可扩展性
  - 插件化：每个分类/站点可定义自定义解析器（覆盖标准 RSS 字段）。
  - sources.json 支持标签与权重，便于个性化排序。
- M7 运维与发布
  - 增加日志与指标输出（简单计数/时延统计）。
  - 打包发布到 PyPI 或提供 Dockerfile。
- M8 安全与合规
  - 仅抓取公开 RSS/Atom；避免绕过认证与机器人限制。
  - 尊重 robots 与站点条款，控制抓取频率。

## 项目结构

- README.md                  项目说明（本文件）
- pyproject.toml             构建与打包配置（setuptools + PEP 621）
- .gitignore                 Git 忽略配置
- sources.example.json       聚合器示例源配置（复制为 sources.json 自定义）
- src/
  - litepy/                  示例包（可替换为你的包名）
    - __init__.py
    - cli.py                 命令行入口（argparse 实现）
    - feeds.py               RSS/Atom 抓取与解析（支持 DB 模式）
    - store.py               SQLite 存储与查询

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
- 为何尽量不引入第三方依赖？
  - 作为模板，尽量保持轻量，避免不必要的耦合。实际项目可按需添加。
- Windows 与 Linux/Mac 的兼容性？
  - 本模板不依赖平台特性，命令行逻辑均可跨平台运行。

——
如需更具体的功能建议或实现示例，可以直接在 issues 中提出需求，我会给出更贴近业务的落地方案。
