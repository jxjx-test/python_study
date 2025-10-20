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
)


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


def cmd_feed_fetch(args: argparse.Namespace) -> int:
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
    p_fetch.add_argument("--sources", help="sources.json 路径（默认自动寻找或使用内置示例）")
    p_fetch.add_argument("--category", help="仅抓取某一分类（类别名来自 sources.json 或内置示例）")
    p_fetch.add_argument("--since", type=int, help="仅保留近 N 小时内的内容")
    p_fetch.add_argument("--limit", type=int, help="限制输出条目数量")
    p_fetch.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    p_fetch.set_defaults(func=cmd_feed_fetch)

    p_sources = sub_feed.add_parser("sources", help="查看源配置")
    p_sources.add_argument("--sources", help="sources.json 路径")
    p_sources.set_defaults(func=cmd_feed_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
