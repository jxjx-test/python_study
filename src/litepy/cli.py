from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict
from typing import Iterable

from .feeds import (
    DEFAULT_SOURCES,
    aggregate as aggregate_feeds,
    format_items_text as format_feed_items,
    load_sources_file,
    crawl_into_db,
    export_items_from_db,
)
from . import store


def slugify(text: str) -> str:
    """Convert text to a simple ASCII slug suitable for filenames/urls.

    - Lowercase
    - Replace non-alphanumeric with single dash
    - Strip leading/trailing dashes
    - Collapse multiple dashes
    """
    text = text.lower()
    # Replace non-letter/digit with dashes
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Collapse multiple dashes
    text = re.sub(r"-+", "-", text)
    # Trim dashes
    return text.strip("-")


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Return hex sha256 of a file.

    Reads in chunks to support large files without high memory use.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_existing_paths(paths: Iterable[str]) -> Iterable[str]:
    for p in paths:
        if os.path.exists(p):
            yield p
        else:
            print(f"[warn] 文件不存在: {p}", file=sys.stderr)


def cmd_hello(args: argparse.Namespace) -> int:
    name = args.name or "世界"
    print(f"你好，{name}！")
    return 0


def cmd_slug(args: argparse.Namespace) -> int:
    print(slugify(args.text))
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    code = 0
    for path in iter_existing_paths(args.paths):
        try:
            digest = sha256_file(path)
            print(f"{digest}  {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"[error] 计算失败: {path} -> {exc}", file=sys.stderr)
            code = 2
    return code


# ------------------ Feed 聚合子命令 ------------------

def _auto_sources_path() -> str | None:
    for candidate in ("sources.json", "sources.example.json"):
        if os.path.exists(candidate):
            return candidate
    return None


def _default_db_path() -> str:
    return store.DEFAULT_DB_PATH


def _ensure_db_ready(db_path: str) -> store.sqlite3.Connection:
    conn = store.get_conn(db_path)
    store.init_db(conn)
    store.ensure_seed_builtin(conn, DEFAULT_SOURCES)
    return conn


def cmd_feed_fetch(args: argparse.Namespace) -> int:
    # 优先：显式使用文件源
    if args.use_file or args.sources:
        path = args.sources or _auto_sources_path()
        sources = load_sources_file(path)
        items = aggregate_feeds(
            sources,
            category=args.category,
            since_hours=args.since,
            limit=args.limit,
        )
        if args.json:
            payload = [asdict(i) | {"published": (i.published.isoformat() if i.published else None)} for i in items]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(format_feed_items(items))
        if not path:
            print("\n[info] 未找到 sources.json，已使用内置示例源。你也可以使用数据库模式持久化并自动去重。", file=sys.stderr)
        return 0

    # 默认：数据库模式（开箱即用，自动初始化并注入内置源）
    db_path = args.db or _default_db_path()
    conn = _ensure_db_ready(db_path)
    # 抓取更新
    crawl_into_db(conn)
    # 按分类过滤（如有）
    feed_ids = None
    if args.category:
        feed_ids = [f.id for f in store.list_feeds(conn, active_only=True) if f.category == args.category]
    # 导出
    items = export_items_from_db(conn, since_hours=args.since, limit=args.limit, feed_ids=feed_ids)
    if args.json:
        payload = [asdict(i) | {"published": (i.published.isoformat() if i.published else None)} for i in items]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_feed_items(items))
    return 0


def cmd_feed_sources(args: argparse.Namespace) -> int:
    path = args.sources or _auto_sources_path()
    sources = load_sources_file(path)
    print("当前源分类及数量：")
    for k, v in sources.items():
        print(f"- {k}: {len(v)} 条源")
    if not path:
        print("\n提示：在项目根目录创建 sources.json 覆盖内置示例，或复制 sources.example.json 自定义。")
    else:
        print(f"\n已使用配置文件: {path}")
    return 0


def cmd_feed_init(args: argparse.Namespace) -> int:
    db_path = args.db or _default_db_path()
    conn = store.get_conn(db_path)
    store.init_db(conn)
    store.ensure_seed_builtin(conn, DEFAULT_SOURCES)
    print(f"已初始化数据库，并写入内置源: {db_path}")
    return 0


def cmd_feed_add(args: argparse.Namespace) -> int:
    db_path = args.db or _default_db_path()
    conn = _ensure_db_ready(db_path)
    feed_id = store.add_feed(conn, args.url, args.category, is_builtin=False)
    print(f"已添加源: id={feed_id} url={args.url} category={args.category or ''}")
    # 立即抓取一次
    crawl_into_db(conn)
    print("已完成一次抓取。")
    return 0


def cmd_feed_list(args: argparse.Namespace) -> int:
    db_path = args.db or _default_db_path()
    conn = _ensure_db_ready(db_path)
    feeds = store.list_feeds(conn, active_only=not args.all)
    print(f"共 {len(feeds)} 个源：")
    for f in feeds:
        flag = "*" if f.is_builtin else "-"
        cat = f.category or ""
        title = f.title or "(未知)"
        print(f"{flag} [{cat}] {title}  -> {f.url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="litepy",
        description="轻量级实用 Python 项目示例 CLI。可按需扩展为你的项目。",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_hello = sub.add_parser("hello", help="打印问候语")
    p_hello.add_argument("name", nargs="?", help="可选名字，默认‘世界’")
    p_hello.set_defaults(func=cmd_hello)

    p_slug = sub.add_parser("slug", help="将文本转为 slug")
    p_slug.add_argument("text", help="要转换的文本")
    p_slug.set_defaults(func=cmd_slug)

    p_hash = sub.add_parser("hash", help="输出文件的 SHA256 哈希")
    p_hash.add_argument("paths", nargs="+", help="一个或多个文件路径")
    p_hash.set_defaults(func=cmd_hash)

    # feed 子命令
    p_feed = sub.add_parser("feed", help="RSS/Atom 聚合工具")
    sub_feed = p_feed.add_subparsers(dest="feed_cmd", required=True)

    p_fetch = sub_feed.add_parser("fetch", help="抓取并输出最新条目")
    p_fetch.add_argument("--sources", help="sources.json 路径（默认使用数据库模式；若提供则使用文件源模式）")
    p_fetch.add_argument("--db", help="SQLite 数据库路径（默认 data/feeds.db）")
    p_fetch.add_argument("--use-file", action="store_true", help="强制使用文件源（忽略数据库）")
    p_fetch.add_argument("--category", help="仅抓取某一分类（文件源模式下有效；数据库模式下按此过滤输出）")
    p_fetch.add_argument("--since", type=int, help="仅保留近 N 小时内的内容")
    p_fetch.add_argument("--limit", type=int, help="限制输出条目数量")
    p_fetch.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    p_fetch.set_defaults(func=cmd_feed_fetch)

    p_sources = sub_feed.add_parser("sources", help="查看内置/文件源配置")
    p_sources.add_argument("--sources", help="sources.json 路径")
    p_sources.set_defaults(func=cmd_feed_sources)

    p_init = sub_feed.add_parser("init", help="初始化数据库并写入内置源")
    p_init.add_argument("--db", help="SQLite 数据库路径（默认 data/feeds.db）")
    p_init.set_defaults(func=cmd_feed_init)

    p_add = sub_feed.add_parser("add", help="添加自定义源到数据库")
    p_add.add_argument("--db", help="SQLite 数据库路径（默认 data/feeds.db）")
    p_add.add_argument("--url", required=True, help="RSS/Atom 源 URL")
    p_add.add_argument("--category", help="可选分类名")
    p_add.set_defaults(func=cmd_feed_add)

    p_list = sub_feed.add_parser("list", help="列出数据库中的源")
    p_list.add_argument("--db", help="SQLite 数据库路径（默认 data/feeds.db）")
    p_list.add_argument("--all", action="store_true", help="包含未激活的源")
    p_list.set_defaults(func=cmd_feed_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
