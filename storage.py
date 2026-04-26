import json, os
from datetime import date

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"


def today_key():
    return str(date.today())


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_device_data(device_id: str):
    """Get data for a specific device"""
    data = load_data()
    return data.get(device_id, {})


def save_device_data(device_id: str, device_data):
    """Save data for a specific device"""
    data = load_data()
    data[device_id] = device_data
    save_data(data)


def get_device_config(device_id: str):
    """Get config for a specific device"""
    config = load_config()
    return config.get(device_id, {"target": 2000})


def save_device_config(device_id: str, device_config):
    """Save config for a specific device"""
    config = load_config()
    config[device_id] = device_config
    save_config(config)