"""禁言事件存储：记录群禁言事件的 operator，供解禁决策查询。

设计动机：自动解禁前需要知道「是谁禁言的」——群主禁言管理员时 bot
（同为管理员）无权解禁，且应尊重群主决定；而 bot 自身或普通管理员
造成的禁言（如 poke 惩罚）应自动恢复。事件驱动通道把每次禁言事件
落库，轮询兜底时查询最近一次 operator 做角色判断。

使用标准库 sqlite3，数据文件位于 localstore 数据目录
（nonebot_plugin_localstore），无需额外依赖。
"""

from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING

from nonebot import logger, require

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as localstore

if TYPE_CHECKING:
    from pathlib import Path

_DB_FILENAME = "auto_unmute_superuser.db"
_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ban_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    operator_id INTEGER NOT NULL,
    duration INTEGER NOT NULL DEFAULT 0,
    banned_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ban_events_group_user
    ON ban_events (group_id, user_id, banned_at);
"""

_lock = threading.Lock()
_db_path: Path | None = None


def _get_db_path() -> Path:
    """返回数据库文件路径（首次调用时创建目录与表）。"""
    global _db_path
    if _db_path is None:
        data_dir = localstore.get_plugin_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        _db_path = data_dir / _DB_FILENAME
        with _lock:
            conn = sqlite3.connect(_db_path)
            try:
                conn.executescript(_TABLE_SQL)
                conn.commit()
            finally:
                conn.close()
        logger.debug("超管自动解禁事件库初始化: {}", _db_path)
    return _db_path


def record_ban_event(
    *,
    group_id: int,
    user_id: int,
    operator_id: int,
    duration: int,
    banned_at: int,
) -> None:
    """记录一条群禁言事件。失败仅记日志，不影响主流程。"""
    try:
        path = _get_db_path()
        with _lock:
            conn = sqlite3.connect(path)
            try:
                conn.execute(
                    "INSERT INTO ban_events"
                    " (group_id, user_id, operator_id, duration, banned_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (group_id, user_id, operator_id, duration, banned_at),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("记录禁言事件失败 group={} user={}", group_id, user_id)


def latest_operator(
    *,
    group_id: int,
    user_id: int,
) -> int | None:
    """返回该群成员最近一次禁言事件的 operator_id；无记录返回 None。"""
    try:
        path = _get_db_path()
        with _lock:
            conn = sqlite3.connect(path)
            try:
                row = conn.execute(
                    "SELECT operator_id FROM ban_events"
                    " WHERE group_id = ? AND user_id = ?"
                    " ORDER BY banned_at DESC, id DESC LIMIT 1",
                    (group_id, user_id),
                ).fetchone()
                return int(row[0]) if row else None
            finally:
                conn.close()
    except Exception:
        logger.exception("查询禁言 operator 失败 group={} user={}", group_id, user_id)
        return None


def prune_events(*, keep_per_pair: int = 5) -> None:
    """清理旧事件：每个 (group, user) 仅保留最近 keep_per_pair 条。"""
    try:
        path = _get_db_path()
        with _lock:
            conn = sqlite3.connect(path)
            try:
                conn.execute(
                    """
                    DELETE FROM ban_events WHERE id IN (
                        SELECT id FROM ban_events b
                        WHERE (
                            SELECT COUNT(*) FROM ban_events b2
                            WHERE b2.group_id = b.group_id
                              AND b2.user_id = b.user_id
                              AND (b2.banned_at > b.banned_at
                                   OR (b2.banned_at = b.banned_at
                                       AND b2.id > b.id))
                        ) >= ?
                    )
                    """,
                    (keep_per_pair,),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("清理禁言事件失败")


__all__ = [
    "latest_operator",
    "prune_events",
    "record_ban_event",
]
