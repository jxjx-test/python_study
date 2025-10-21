from __future__ import annotations

import email.utils as eut
import json
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# 一些内置示例源，便于开箱即用。建议复制到项目根目录的 sources.json 后自行增删。
DEFAULT_SOURCES: Dict[str, list[str]] = {
    "deals": [
        # 什么值得买（好价/资讯综合）
        "https://www.smzdm.com/feed",
    ],
    "news": [
        # 综合新闻（部分为海外媒体，网络环境可能影响访问）
        "http://feeds.bbci.co.uk/zhongwen/simp/rss.xml",  # BBC 中文网
        "http://feeds.reuters.com/reuters/CHINAnews",  # 路透中文
        "https://cn.nytimes.com/rss/",  # 纽约时报中文网（可能涉及付费墙）
        "http://www.ftchinese.com/rss/news",  # FT 中文网（部分内容需订阅）
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
    guid: Optional[str] = None


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


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


# ------------- 抓取与解析 -------------

_UA = "litepy/0.2 (+https://example.com)"


def fetch_url(
    url: str,
    *,
    timeout: int = 20,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> Tuple[int, Optional[bytes], dict]:
    """抓取 URL，返回 (status, body, headers)。

    - 支持条件请求：If-None-Match/If-Modified-Since
    - status 200 返回 body，status 304 返回 None
    """
    headers = {
        "User-Agent": _UA,
        "Accept": "application/rss+xml, application/atom+xml, text/xml;q=0.9, */*;q=0.8",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    req = Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", 200)
            data = resp.read()
            hdrs = {k.title(): v for k, v in resp.headers.items()}
            return status, data, hdrs
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 抓取失败: {url} -> {exc}", file=sys.stderr)
        raise


def fetch_url_bytes(url: str, timeout: int = 15) -> bytes:
    # 兼容旧的简单抓取
    st, body, _ = fetch_url(url, timeout=timeout)
    if st == 304:
        return b""
    return body or b""


def parse_feed_meta(xml_bytes: bytes, feed_url: str) -> Tuple[Optional[str], Optional[str]]:
    """解析 feed 的标题与站点链接。"""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 解析 XML 失败: {feed_url} -> {exc}", file=sys.stderr)
        return None, None

    title: Optional[str] = None
    site_link: Optional[str] = None

    # RSS 2.0: <rss><channel><title>, <link>
    ch = next((c for c in root if _local(c.tag) == "channel"), None)
    if ch is not None:
        for c in ch:
            nm = _local(c.tag)
            if nm == "title" and not title:
                title = (c.text or "").strip() or None
            elif nm == "link" and not site_link:
                site_link = (c.text or "").strip() or None
    else:
        # Atom: <feed><title>, <link rel="alternate" href="...">
        for c in root:
            nm = _local(c.tag)
            if nm == "title" and not title:
                title = (c.text or "").strip() or None
            elif nm == "link":
                href = c.attrib.get("href")
                rel = c.attrib.get("rel", "alternate")
                if rel == "alternate" and href and not site_link:
                    site_link = href.strip()

    return title, site_link


def parse_feed(xml_bytes: bytes, feed_url: str) -> List[FeedItem]:
    """保留原有 API：仅返回条目列表。"""
    _, _, items = parse_feed_full(xml_bytes, feed_url)
    return items


def parse_feed_full(xml_bytes: bytes, feed_url: str) -> Tuple[Optional[str], Optional[str], List[FeedItem]]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 解析 XML 失败: {feed_url} -> {exc}", file=sys.stderr)
        return None, None, []

    items: List[FeedItem] = []
    nodes = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    src = urlparse(feed_url).netloc or feed_url

    for node in nodes:
        local = {(_local(c.tag)): c for c in list(node)}
        title = (_child_text(node, ("title",)) or "").strip()
        link = None
        guid = None
        # RSS: <guid> 或 Atom: <id>
        guid = _child_text(node, ("guid", "id"))
        # 链接：RSS <link>text</link>  Atom <link href>
        if "link" in local and local["link"].attrib.get("href"):
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
            continue
        items.append(
            FeedItem(
                title=title or link or "(无标题)",
                link=link or "",
                published=published,
                source=src,
                summary=summary,
                guid=guid,
            )
        )

    # 解析 feed 级别元数据
    feed_title, site_link = parse_feed_meta(xml_bytes, feed_url)
    return feed_title, site_link, items


# ------------- 旧版聚合（文件源） -------------

def aggregate(
    sources: Dict[str, list[str]],
    category: Optional[str] = None,
    since_hours: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[FeedItem]:
    # 选择要抓取的 URL 列表
    cats = [category] if category else list(sources.keys())
    urls: List[str] = []
    for c in cats:
        urls.extend(sources.get(c, []))

    seen: set[str] = set()
    items: List[FeedItem] = []

    for url in urls:
        try:
            data = fetch_url_bytes(url)
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


# ------------- 基于本地数据库的抓取与聚合 -------------

def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def crawl_into_db(db_conn) -> int:
    """抓取数据库中的所有活跃源，写入 items，返回新增或更新的条目数。"""
    from . import store  # 本地导入，避免循环依赖

    feeds = store.list_feeds(db_conn, active_only=True)
    total_updates = 0
    for f in feeds:
        try:
            status, body, hdrs = fetch_url(f.url, etag=f.etag, last_modified=f.last_modified)
        except Exception:
            continue
        # 304 Not Modified
        if status == 304:
            store.update_feed_meta(
                db_conn,
                f.id,
                last_checked_iso=_iso_now(),
            )
            continue
        if status != 200 or not body:
            store.update_feed_meta(db_conn, f.id, last_checked_iso=_iso_now())
            continue
        # 解析 feed
        feed_title, site_link, items = parse_feed_full(body, f.url)
        # 更新 feed 元信息与缓存
        store.update_feed_meta(
            db_conn,
            f.id,
            title=feed_title,
            site_link=site_link,
            etag=hdrs.get("Etag"),
            last_modified=hdrs.get("Last-Modified"),
            last_checked_iso=_iso_now(),
        )
        # 写入条目
        before = time.time()
        for it in items:
            pub_iso = it.published.replace(microsecond=0).isoformat() if it.published else None
            store.upsert_item(
                db_conn,
                f.id,
                link=it.link,
                title=it.title,
                summary=it.summary,
                published_iso=pub_iso,
                guid=it.guid,
            )
        total_updates += len(items)
    return total_updates


def export_items_from_db(
    db_conn,
    *,
    since_hours: Optional[int] = None,
    limit: Optional[int] = None,
    feed_ids: Optional[List[int]] = None,
) -> List[FeedItem]:
    from . import store

    feeds = store.list_feeds(db_conn, active_only=True)
    id_map = {f.id: f for f in feeds}
    results: List[FeedItem] = []
    for row in store.iter_items(db_conn, feed_ids=feed_ids, since_hours=since_hours, limit=limit):
        feed = id_map.get(row.feed_id)
        src = None
        if feed and feed.title:
            src = feed.title
        elif feed:
            src = urlparse(feed.url).netloc
        else:
            src = "unknown"
        dt = None
        if row.published:
            try:
                dt = datetime.fromisoformat(row.published)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                dt = None
        results.append(
            FeedItem(
                title=row.title or row.link,
                link=row.link,
                published=dt,
                source=src,
                summary=row.summary,
            )
        )
    return results
