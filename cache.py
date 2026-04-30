"""Supabase cache layer for nutrition lookups.

Prevents repeat API calls for the same food item.
Cache persists in Supabase DB.
"""

import time
from db import supabase

CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def _make_key(name: str, route: str) -> str:
    """Generate a stable cache key from item name and route."""
    return f"{name.lower().strip()}::{route.lower().strip()}"


def get_cached(name: str, route: str) -> tuple[int, str, str] | None:
    """Look up cached calories. Returns (calories, source, resolved_name) if found, else None."""
    key = _make_key(name, route)
    try:
        response = supabase.table("nutrition_cache").select("*").eq("key", key).execute()
        
        if not response.data:
            return None
            
        row = response.data[0]
        calories = row["calories_per_unit"]
        source = row["source"]
        resolved_name = row["resolved_name"]
        cached_at = row["cached_at"]
        
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            # Expired — delete and return None
            supabase.table("nutrition_cache").delete().eq("key", key).execute()
            return None

        return calories, source, resolved_name
    except Exception as e:
        print(f"Cache read error: {e}")
        return None


def set_cache(name: str, route: str, calories: int, source: str = "unknown", resolved_name: str = None):
    """Store a calorie lookup result in the cache."""
    key = _make_key(name, route)
    if resolved_name is None:
        resolved_name = name
    try:
        supabase.table("nutrition_cache").upsert({
            "key": key,
            "calories_per_unit": calories,
            "source": source,
            "resolved_name": resolved_name,
            "cached_at": time.time()
        }).execute()
    except Exception as e:
        print(f"Cache write error: {e}")
        pass  # Cache failures should never break the app
