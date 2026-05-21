"""Service layer — orchestrates the LLM router + nutrition database pipeline.

Flow: User text → LLM Router → Database Lookups (with cache) → Response
The public interface (parse_food_service) returns the same schema as before:
  {"items": [...], "total_added": N}
"""

from llm import route_items
from nutrition import resolve_calories
from cache import get_cached, set_cache


def parse_food_service(text: str):
    """Parse food input and return calorie data.

    Returns the same schema as before:
    {
        "items": [{"item": str, "qty": int, "calories_per_unit": int}, ...],
        "total_added": int
    }
    """
    # Step 1: LLM parses and routes items
    try:
        routed_items = route_items(text)
    except Exception as e:
        raise Exception(f"LLM error: {str(e)}")

    if not routed_items:
        raise ValueError("Could not identify any food items. Please try again.")

    # Step 2: Resolve calories per item (cache → DB → LLM fallback)
    result_items = []
    for item in routed_items:
        original_name = item.normalized
        
        # Check cache first
        cached = get_cached(original_name, item.route)
        if cached is not None:
            cal, cache_source, resolved_name = cached
            from admin_config import is_ifct_disabled
            if is_ifct_disabled() and "IFCT" in cache_source:
                cached = None
                
        if cached is not None:
            cal, cache_source, resolved_name = cached
            source = f"{cache_source} (Cached)"
            item.normalized = resolved_name
        else:
            # Look up from the appropriate database
            cal, source = resolve_calories(item)
            # Cache the result for future lookups using original name as key
            if cal > 0:
                set_cache(original_name, item.route, cal, source=source, resolved_name=item.normalized)

        result_items.append({
            "item": item.normalized,
            "qty": item.qty,
            "calories_per_unit": cal,
            "source": source
        })

    total_added = sum(e["calories_per_unit"] * e["qty"] for e in result_items)

    return {
        "items": result_items,
        "total_added": round(total_added)
    }