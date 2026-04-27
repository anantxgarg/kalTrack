"""SQLite cache layer for nutrition lookups.

Prevents repeat API calls for the same food item.
Cache persists across server restarts.
"""

import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "nutrition_cache.db")
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def _get_conn():
    """Get a SQLite connection, creating the table if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        # Check if resolved_name column exists
        conn.execute("SELECT resolved_name FROM nutrition_cache LIMIT 1")
    except sqlite3.OperationalError:
        # Recreate table if it's the old schema
        conn.execute("DROP TABLE IF EXISTS nutrition_cache")
        
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nutrition_cache (
            key TEXT PRIMARY KEY,
            calories_per_unit INTEGER NOT NULL,
            source TEXT NOT NULL,
            resolved_name TEXT,
            cached_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _make_key(name: str, route: str) -> str:
    """Generate a stable cache key from item name and route."""
    return f"{name.lower().strip()}::{route.lower().strip()}"


def get_cached(name: str, route: str) -> tuple[int, str, str] | None:
    """Look up cached calories. Returns (calories, source, resolved_name) if found, else None."""
    key = _make_key(name, route)
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT calories_per_unit, source, resolved_name, cached_at FROM nutrition_cache WHERE key = ?",
            (key,)
        ).fetchone()
        conn.close()

        if row is None:
            return None

        calories, source, resolved_name, cached_at = row
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            # Expired — delete and return None
            conn = _get_conn()
            conn.execute("DELETE FROM nutrition_cache WHERE key = ?", (key,))
            conn.commit()
            conn.close()
            return None

        return calories, source, resolved_name
    except Exception:
        return None


def set_cache(name: str, route: str, calories: int, source: str = "unknown", resolved_name: str = None):
    """Store a calorie lookup result in the cache."""
    key = _make_key(name, route)
    if resolved_name is None:
        resolved_name = name
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO nutrition_cache (key, calories_per_unit, source, resolved_name, cached_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, calories, source, resolved_name, time.time())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Cache failures should never break the app
