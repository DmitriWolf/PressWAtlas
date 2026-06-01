"""Local per-user memory: equipment + food preferences.

Design constraints from the brief:
- Marcus: continuity is the product ("if I said shellfish allergy last week, don't
  suggest shrimp this week"). So we DO persist equipment and food avoidances.
- Diane (legal): do not store medical conditions or give dietary/medical advice.
  So we store avoidances as *food preferences* ("avoid shellfish", "vegetarian"),
  and we explicitly never persist medical conditions (diabetes, pregnancy, etc.).
- A deletion path exists (clear_user) to support the right-to-delete story.

Storage is a single local SQLite file — no external database.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .config import DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id     TEXT PRIMARY KEY,
                equipment   TEXT NOT NULL DEFAULT '[]',
                preferences TEXT NOT NULL DEFAULT '{}',
                updated_at  TEXT
            )
            """
        )
        _conn.commit()
    return _conn


_EMPTY_PREFS = {"likes": [], "dislikes": [], "avoid": []}


def get_memory(user_id: str) -> dict[str, Any]:
    with _lock:
        cur = _connect().execute(
            "SELECT equipment, preferences FROM user_memory WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return {"equipment": [], "preferences": dict(_EMPTY_PREFS)}
    equipment = json.loads(row[0])
    prefs = {**_EMPTY_PREFS, **json.loads(row[1])}
    return {"equipment": equipment, "preferences": prefs}


def _dedup_extend(existing: list[str], new: list[str]) -> list[str]:
    seen = {x.lower() for x in existing}
    out = list(existing)
    for item in new:
        item = item.strip()
        if item and item.lower() not in seen:
            out.append(item)
            seen.add(item.lower())
    return out


def update_memory(
    user_id: str,
    *,
    equipment_add: list[str] | None = None,
    equipment_remove: list[str] | None = None,
    likes: list[str] | None = None,
    dislikes: list[str] | None = None,
    avoid: list[str] | None = None,
) -> dict[str, Any]:
    """Merge new facts into a user's memory. Lists are additive (deduped)."""
    current = get_memory(user_id)
    equipment = current["equipment"]
    if equipment_add:
        equipment = _dedup_extend(equipment, equipment_add)
    if equipment_remove:
        remove = {x.lower() for x in equipment_remove}
        equipment = [e for e in equipment if e.lower() not in remove]

    prefs = current["preferences"]
    if likes:
        prefs["likes"] = _dedup_extend(prefs["likes"], likes)
    if dislikes:
        prefs["dislikes"] = _dedup_extend(prefs["dislikes"], dislikes)
    if avoid:
        prefs["avoid"] = _dedup_extend(prefs["avoid"], avoid)

    with _lock:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO user_memory (user_id, equipment, preferences, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                equipment=excluded.equipment,
                preferences=excluded.preferences,
                updated_at=excluded.updated_at
            """,
            (user_id, json.dumps(equipment), json.dumps(prefs)),
        )
        conn.commit()
    return {"equipment": equipment, "preferences": prefs}


def clear_user(user_id: str) -> None:
    """Right-to-delete: wipe everything we hold for a user."""
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM user_memory WHERE user_id = ?", (user_id,))
        conn.commit()


def purge_stale(retention_days: int) -> int:
    """Retention policy: delete memory not updated within the retention window.

    Stored preferences are food-related, but Diane asked for a retention story;
    this enforces a hard TTL. Returns the number of users purged.
    """
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "DELETE FROM user_memory WHERE updated_at IS NOT NULL "
            "AND updated_at < datetime('now', ?)",
            (f"-{int(retention_days)} days",),
        )
        conn.commit()
        return cur.rowcount
