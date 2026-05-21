from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from schemas import LogRequest, TargetRequest
from services import parse_food_service
from db import supabase

router = APIRouter()

_ensured_users = set()

def _ensure_user(user_id: str):
    """Ensure the anonymous user and their settings row exist."""
    if user_id in _ensured_users:
        return
        
    user_res = supabase.table("users").select("id").eq("id", user_id).execute()
    if not user_res.data:
        supabase.table("users").insert({"id": user_id}).execute()
        
    settings_res = supabase.table("user_settings").select("user_id").eq("user_id", user_id).execute()
    if not settings_res.data:
        supabase.table("user_settings").insert(
            {"user_id": user_id, "daily_target": 2000}
        ).execute()
        
    _ensured_users.add(user_id)


# ── Static ──────────────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse("static/index.html")

@router.head("/")
def head_root():
    return {}

@router.get("/sw.js")
def get_sw():
    return FileResponse("static/sw.js")

@router.get("/manifest.json")
def get_manifest():
    return FileResponse("static/manifest.json")


# ── State ───────────────────────────────────────────────────────────────────

@router.get("/api/state")
def get_state(x_user_id: str = Header(...)):
    """Return today's log, 30-day history totals, and the daily target."""
    _ensure_user(x_user_id)

    # Daily target
    settings = (
        supabase.table("user_settings")
        .select("daily_target")
        .eq("user_id", x_user_id)
        .single()
        .execute()
    )
    target = settings.data["daily_target"]

    # Today's log entries
    today_str = date.today().isoformat()
    log_rows = (
        supabase.table("food_logs")
        .select("id, food_name, count, calories_per_unit, source")
        .eq("user_id", x_user_id)
        .eq("log_date", today_str)
        .execute()
    )

    log = [
        {
            "id": r["id"],
            "name": r["food_name"],
            "count": r["count"],
            "calories": r["calories_per_unit"],
            "source": r["source"],
        }
        for r in log_rows.data
    ]

    # 30-day history — sum per day, excluding today (live)
    since = (date.today() - timedelta(days=29)).isoformat()
    history_rows = (
        supabase.table("food_logs")
        .select("log_date, count, calories_per_unit")
        .eq("user_id", x_user_id)
        .gte("log_date", since)
        .lt("log_date", today_str)
        .execute()
    )

    history: dict[str, int] = {}
    for r in history_rows.data:
        d = r["log_date"]
        history[d] = history.get(d, 0) + r["count"] * r["calories_per_unit"]

    return {"target": target, "log": log, "history": history}


# ── Target ──────────────────────────────────────────────────────────────────

@router.post("/api/target")
def update_target(req: TargetRequest, x_user_id: str = Header(...)):
    """Persist the user's daily calorie target."""
    _ensure_user(x_user_id)
    supabase.table("user_settings").update({"daily_target": req.target}).eq(
        "user_id", x_user_id
    ).execute()
    return {"target": req.target}


# ── Log food ─────────────────────────────────────────────────────────────────

@router.post("/log")
def log_food(req: LogRequest, x_user_id: str = Header(...)):
    """Parse food text, resolve calories, and persist rows to food_logs."""
    _ensure_user(x_user_id)
    try:
        result = parse_food_service(req.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"Internal Error: {e}")
        raise HTTPException(status_code=500, detail="An internal service error occurred. Please try again later.")

    today_str = date.today().isoformat()
    
    # Fetch existing logs for today
    existing_logs = supabase.table("food_logs").select("id, food_name, count").eq("user_id", x_user_id).eq("log_date", today_str).execute()
    existing_map = {row["food_name"].lower(): row for row in existing_logs.data}
    
    for item in result["items"]:
        food_name_lower = item["item"].lower()
        if food_name_lower in existing_map:
            # Update existing row
            existing_row = existing_map[food_name_lower]
            new_count = existing_row["count"] + item["qty"]
            supabase.table("food_logs").update({"count": new_count}).eq("id", existing_row["id"]).execute()
            
            item["id"] = existing_row["id"]
            item["action"] = "updated"
            item["new_count"] = new_count
            existing_row["count"] = new_count
        else:
            # Insert new row
            inserted = supabase.table("food_logs").insert({
                "user_id": x_user_id,
                "log_date": today_str,
                "food_name": item["item"],
                "count": item["qty"],
                "calories_per_unit": item["calories_per_unit"],
                "source": item.get("source"),
            }).execute()
            
            item["id"] = inserted.data[0]["id"]
            item["action"] = "inserted"
            existing_map[food_name_lower] = {"id": item["id"], "count": item["qty"], "food_name": item["item"]}

    return result


# ── Delete log entry ─────────────────────────────────────────────────────────

@router.delete("/api/log/{log_id}")
def delete_log(log_id: str, x_user_id: str = Header(...)):
    """Delete a single food_logs row by UUID."""
    supabase.table("food_logs").delete().eq("id", log_id).eq(
        "user_id", x_user_id
    ).execute()
    return {"deleted": log_id}


# ── Admin Settings ──────────────────────────────────────────────────────────

@router.get("/api/admin/settings")
def get_admin_settings(x_admin_password: str = Header(...)):
    """Retrieve the current admin/system configuration settings."""
    import os
    from admin_config import get_admin_config
    
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        raise HTTPException(status_code=500, detail="Admin password not configured on server")
    import secrets
    if not secrets.compare_digest(x_admin_password, admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    
    return get_admin_config()


@router.post("/api/admin/settings")
def update_admin_settings(settings: dict, x_admin_password: str = Header(...)):
    """Update global system configurations (e.g. toggle IFCT)."""
    import os
    from admin_config import get_admin_config, set_admin_config
    
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        raise HTTPException(status_code=500, detail="Admin password not configured on server")
    import secrets
    if not secrets.compare_digest(x_admin_password, admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    
    current_config = get_admin_config()
    current_config["disable_ifct"] = settings.get("disable_ifct", False)
    set_admin_config(current_config)
    return current_config


@router.post("/api/admin/clear-cache")
def clear_cache(x_admin_password: str = Header(...)):
    """Clear all records from the nutrition cache table in Supabase."""
    import os
    
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        raise HTTPException(status_code=500, detail="Admin password not configured on server")
    import secrets
    if not secrets.compare_digest(x_admin_password, admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    
    try:
        supabase.table("nutrition_cache").delete().neq("key", "").execute()
        return {"success": True, "message": "Nutrition cache cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")