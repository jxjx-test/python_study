from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl
import email.utils as eut


# 一些内置示例源，便于开箱即用。建议复制到项目根目录的 sources.json 后自行增删。
DEFAULT_SOURCES: Dict[str, list[str]] = {
    "deals": [
        # 什么值得买（好价/资讯综合）
        "https://www.smzdm.com/feed",
    ],
    "news": [
        # 综合新闻（部分为海外媒体，网络环境可能影响访问）
        "http://feeds.bbci.co.uk/zhongwen/simp/rss.xml",  # BBC 中文网
        "http://feeds.reuters.com/reuters/CHINAnews",     # 路透中文
        "https://cn.nytimes.com/rss/",                    # 纽约时报中文网（可能涉及付费墙）
        "http://www.ftchinese.com/rss/news",              # FT 中文网（部分内容需订阅）
    ],
    "tech": [
        # 科技/社区/技术博客
        "https://www.v2ex.com/index.xml",
        "https://sspai.com/feed",
        "https://www.solidot.org/index.rss",
        "http://www.ruanyifeng.com/blog/atom.xml",
        "https://www.ifanr.com/feed",
        "https://www.oschina.net/news/rss",
        "https://36kr.com/feed",
    ],
    "entertainment": [
        # 娱乐/数码/热点（可替换为你的关注来源）
        "https://jandan.net/feed",
        "https://chinese.engadget.com/rss.xml",
    ],
}


@dataclass
class FeedItem:
    title: str
    link: str
    published: Optional[datetime]
    source: str  # 域名或来源名
    summary: Optional[str] = None


def _local(tag: str) -> str:
    return tag.split('}', 1)[-1]


def _child_text(el: ET.Element, names: Iterable[str]) -> Optional[str]:
    for child in el:
        name = _local(child.tag)
        if name in names:
            text = (child.text or "").strip()
            # Atom 的 link 在属性里
            if name == "link":
                href = child.attrib.get("href")
                if href:
                    return href.strip()
            return text or None
    return None


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # RSS: RFC 822/1123（email.utils）; Atom: ISO-8601
    try:
        dt = eut.parsedate_to_datetime(value)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        s = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_url(url: str, timeout: int = 15) -> bytes:
    # 一些站点需要 UA 才返回内容
    req = Request(
        url,
        headers={
            "User-Agent": "litepy/0.1 (+https://example.com)",
            "Accept": "application/rss+xml, application/atom+xml, text/xml;q=0.9, */*;q=0.8",
        },
        method="GET",
    )
    # 宽松的 SSL 上下文，避免极少数站点证书问题导致失败
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def parse_feed(xml_bytes: bytes, feed_url: str) -> List[FeedItem]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 解析 XML 失败: {feed_url} -> {exc}", file=sys.stderr)
        return []

    items: List[FeedItem] = []
    # 收集所有 item/entry 节点
    nodes = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]

    src = urlparse(feed_url).netloc or feed_url

    for node in nodes:
        local = {(_local(c.tag)): c for c in list(node)}
        title = (_child_text(node, ("title",)) or "").strip()
        link = None
        # RSS: <link>text</link>  Atom: <link href="..." rel="alternate"/>
        if "link" in local and local["link"].attrib.get("href"):
            # Atom
            # 按 rel 选一个最合适的链接
            links = [c for c in node if _local(c.tag) == "link"]
            alt = next((c for c in links if c.attrib.get("rel", "alternate") == "alternate" and c.attrib.get("href")), None)
            link = (alt.attrib.get("href") if alt is not None else local["link"].attrib.get("href"))
        else:
            link = _child_text(node, ("link",))

        summary = _child_text(node, ("summary", "description", "content", "encoded"))
        pub = (
            _child_text(node, ("published",))
            or _child_text(node, ("updated",))
            or _child_text(node, ("pubDate",))
        )
        published = _parse_date(pub)

        if not title and not link:
            # 无有效信息，跳过
            continue
        items.append(FeedItem(title=title or link or "(无标题)", link=link or "", published=published, source=src, summary=summary))

    return items


def aggregate(sources: Dict[str, list[str]], category: Optional[str] = None, since_hours: Optional[int] = None, limit: Optional[int] = None) -> List[FeedItem]:
    # 选择要抓取的 URL 列表
    cats = [category] if category else list(sources.keys())
    urls: List[str] = []
    for c in cats:
        urls.extend(sources.get(c, []))

    seen: set[str] = set()
    items: List[FeedItem] = []

    for url in urls:
        try:
            data = fetch_url(url)
            parsed = parse_feed(data, url)
            for it in parsed:
                key = it.link or f"{it.title}|{it.published}"
                if key in seen:
                    continue
                seen.add(key)
                items.append(it)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 抓取失败: {url} -> {exc}", file=sys.stderr)
            continue

    # 过滤时间窗口
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        items = [i for i in items if (i.published is None or i.published >= cutoff)]

    # 排序：有发布时间的倒序，无发布时间的置后
    def sort_key(it: FeedItem):
        ts = it.published.timestamp() if (it.published and it.published.tzinfo) else (
            it.published.replace(tzinfo=timezone.utc).timestamp() if it.published else -1
        )
        return (0 if it.published else 1, -ts)

    items.sort(key=sort_key)

    if limit:
        items = items[:limit]

    return items


def load_sources_file(path: str | None) -> Dict[str, list[str]]:
    if not path:
        return DEFAULT_SOURCES
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 简单校验
        if not isinstance(data, dict):
            raise ValueError("sources 文件应为 {category: [urls]} 的字典")
        fixed: Dict[str, list[str]] = {}
        for k, v in data.items():
            if isinstance(v, list):
                fixed[k] = [str(x) for x in v]
        return fixed or DEFAULT_SOURCES
    except FileNotFoundError:
        print(f"[info] 未找到 sources 文件: {path}，使用内置示例源", file=sys.stderr)
        return DEFAULT_SOURCES
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 解析 sources 失败: {path} -> {exc}，使用内置示例源", file=sys.stderr)
        return DEFAULT_SOURCES


def format_items_text(items: Iterable[FeedItem]) -> str:
    lines: List[str] = []
    for it in items:
        dt = it.published.isoformat() if it.published else ""
        title = it.title.replace("\n", " ").strip()
        lines.append(f"- [{it.source}] {title}\n  {it.link} {('('+dt+')') if dt else ''}")
    return "\n".join(lines)
