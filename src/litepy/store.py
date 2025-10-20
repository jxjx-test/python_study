from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence


@dataclass
class FeedRow:
    id: int
    url: str
    category: Optional[str]
    title: Optional[str]
    site_link: Optional[str]
    is_builtin: int
    active: int
    etag: Optional[str]
    last_modified: Optional[str]
    last_checked_at: Optional[str]


@dataclass
class ItemRow:
    id: int
    feed_id: int
    title: Optional[str]
    link: str
    summary: Optional[str]
    published: Optional[str]
    guid: Optional[str]


DEFAULT_DB_PATH = os.path.join("data", "feeds.db")


def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def get_conn(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    ensure_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            category TEXT,
            title TEXT,
            site_link TEXT,
            is_builtin INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            etag TEXT,
            last_modified TEXT,
            last_checked_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            feed_id INTEGER NOT NULL,
            guid TEXT,
            title TEXT,
            link TEXT NOT NULL,
            summary TEXT,
            published TEXT,
            fetched_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%SZ', 'now')),
            UNIQUE(feed_id, link),
            FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_published ON items(published DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_feed ON items(feed_id)")
    conn.commit()


def ensure_seed_builtin(conn: sqlite3.Connection, sources: dict[str, list[str]]) -> None:
    cur = conn.cursor()
    # Check if any feeds exist
    cur.execute("SELECT COUNT(*) FROM feeds")
    count = cur.fetchone()[0]
    if count and count > 0:
        return
    # Seed builtins
    for category, urls in sources.items():
        for url in urls:
            cur.execute(
                "INSERT OR IGNORE INTO feeds(url, category, is_builtin, active) VALUES (?, ?, 1, 1)",
                (url, category),
            )
    conn.commit()


def add_feed(conn: sqlite3.Connection, url: str, category: Optional[str] = None, is_builtin: bool = False) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO feeds(url, category, is_builtin, active) VALUES (?, ?, ?, 1)",
        (url, category, 1 if is_builtin else 0),
    )
    # If existed, update category if provided
    if cur.rowcount == 0 and category is not None:
        cur.execute("UPDATE feeds SET category=? WHERE url=?", (category, url))
    conn.commit()
    cur.execute("SELECT id FROM feeds WHERE url=?", (url,))
    row = cur.fetchone()
    return int(row[0])


def list_feeds(conn: sqlite3.Connection, active_only: bool = True) -> list[FeedRow]:
    cur = conn.cursor()
    sql = "SELECT id, url, category, title, site_link, is_builtin, active, etag, last_modified, last_checked_at FROM feeds"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY COALESCE(category, '') ASC, url ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    return [FeedRow(**dict(r)) for r in rows]


def update_feed_meta(
    conn: sqlite3.Connection,
    feed_id: int,
    *,
    title: Optional[str] = None,
    site_link: Optional[str] = None,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    last_checked_iso: Optional[str] = None,
) -> None:
    sets: list[str] = []
    vals: list[object] = []
    if title is not None:
        sets.append("title=?")
        vals.append(title)
    if site_link is not None:
        sets.append("site_link=?")
        vals.append(site_link)
    if etag is not None:
        sets.append("etag=?")
        vals.append(etag)
    if last_modified is not None:
        sets.append("last_modified=?")
        vals.append(last_modified)
    if last_checked_iso is not None:
        sets.append("last_checked_at=?")
        vals.append(last_checked_iso)
    if not sets:
        return
    vals.extend([feed_id])
    sql = f"UPDATE feeds SET {', '.join(sets)} WHERE id=?"
    cur = conn.cursor()
    cur.execute(sql, tuple(vals))
    conn.commit()


def upsert_item(
    conn: sqlite3.Connection,
    feed_id: int,
    *,
    link: str,
    title: Optional[str],
    summary: Optional[str],
    published_iso: Optional[str],
    guid: Optional[str] = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO items(feed_id, guid, title, link, summary, published)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(feed_id, link) DO UPDATE SET
            title=excluded.title,
            summary=excluded.summary,
            published=excluded.published
        """,
        (feed_id, guid, title, link, summary, published_iso),
    )
    conn.commit()


def iter_items(
    conn: sqlite3.Connection,
    *,
    feed_ids: Optional[Sequence[int]] = None,
    since_hours: Optional[int] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None,
) -> Iterable[ItemRow]:
    where: list[str] = []
    vals: list[object] = []
    if feed_ids:
        where.append(f"feed_id IN ({','.join('?' for _ in feed_ids)})")
        vals.extend(feed_ids)
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        where.append("(published IS NULL OR published >= ?)")
        vals.append(cutoff.replace(microsecond=0).isoformat())
    if search:
        where.append("(title LIKE ? OR summary LIKE ?)")
        vals.extend([f"%{search}%", f"%{search}%"])

    sql = "SELECT id, feed_id, title, link, summary, published, guid FROM items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(published, '0000-01-01T00:00:00Z') DESC, id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    cur = conn.cursor()
    cur.execute(sql, tuple(vals))
    for r in cur.fetchall():
        yield ItemRow(**dict(r))
