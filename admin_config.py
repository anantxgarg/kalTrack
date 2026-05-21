import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data", "admin_config.json")

def get_admin_config() -> dict:
    """Read the admin settings from persistent file storage."""
    if not os.path.exists(CONFIG_FILE):
        return {"disable_ifct": False}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"disable_ifct": False}

def set_admin_config(config: dict):
    """Save the admin settings to persistent file storage."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def is_ifct_disabled() -> bool:
    """Check if the IFCT database lookup has been disabled globally."""
    return get_admin_config().get("disable_ifct", False)
