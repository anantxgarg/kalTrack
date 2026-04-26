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
        return {"target": 2000}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)