"""
utils.py
Shared helpers: config loading, ID generation, admin checks.
"""
import json
import os
import uuid

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


def load_json_config(name: str) -> dict:
    path = os.path.join(CONFIG_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def is_admin(user_id: int) -> bool:
    env_admins = os.getenv("ADMIN_IDS", "")
    if env_admins.strip():
        ids = [int(x.strip()) for x in env_admins.split(",") if x.strip().isdigit()]
        return user_id in ids
    admins = load_json_config("admins").get("admin_ids", [])
    return user_id in admins


def format_balance(amount: float) -> str:
    return f"{amount:,.2f}"
