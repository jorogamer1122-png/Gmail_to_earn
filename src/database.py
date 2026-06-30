"""
database.py
Lightweight JSON-backed data layer for the Task Reward Bot.
Swap this out for SQLite/Postgres later if you need concurrency at scale.
"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOCK = threading.Lock()


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")


def _load(name: str) -> dict:
    path = _path(name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(name: str, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _path(name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


class DB:
    """Simple thread-safe accessor for users, tasks, submissions, rewards."""

    # ---------- Users ----------
    @staticmethod
    def get_user(user_id: int) -> Optional[dict]:
        with LOCK:
            return _load("users").get(str(user_id))

    @staticmethod
    def upsert_user(user_id: int, **fields) -> dict:
        with LOCK:
            users = _load("users")
            uid = str(user_id)
            record = users.get(uid, {
                "id": user_id,
                "balance": 0,
                "joined_at": datetime.utcnow().isoformat(),
                "completed_tasks": [],
                "referrals": [],
                "referred_by": None,
                "language": "en",
            })
            record.update(fields)
            users[uid] = record
            _save("users", users)
            return record

    @staticmethod
    def adjust_balance(user_id: int, delta: float) -> float:
        with LOCK:
            users = _load("users")
            uid = str(user_id)
            if uid not in users:
                raise KeyError(f"User {user_id} not found")
            users[uid]["balance"] = round(users[uid].get("balance", 0) + delta, 2)
            _save("users", users)
            return users[uid]["balance"]

    @staticmethod
    def all_users() -> dict:
        with LOCK:
            return _load("users")

    # ---------- Tasks ----------
    @staticmethod
    def create_task(task_id: str, title: str, description: str, reward: float,
                     created_by: int, max_completions: int = 0) -> dict:
        with LOCK:
            tasks = _load("tasks")
            tasks[task_id] = {
                "id": task_id,
                "title": title,
                "description": description,
                "reward": reward,
                "created_by": created_by,
                "created_at": datetime.utcnow().isoformat(),
                "active": True,
                "max_completions": max_completions,  # 0 = unlimited
                "completions": 0,
            }
            _save("tasks", tasks)
            return tasks[task_id]

    @staticmethod
    def get_task(task_id: str) -> Optional[dict]:
        with LOCK:
            return _load("tasks").get(task_id)

    @staticmethod
    def list_active_tasks() -> list:
        with LOCK:
            tasks = _load("tasks")
            return [t for t in tasks.values() if t.get("active")]

    @staticmethod
    def set_task_active(task_id: str, active: bool) -> bool:
        with LOCK:
            tasks = _load("tasks")
            if task_id not in tasks:
                return False
            tasks[task_id]["active"] = active
            _save("tasks", tasks)
            return True

    @staticmethod
    def increment_task_completion(task_id: str) -> None:
        with LOCK:
            tasks = _load("tasks")
            if task_id in tasks:
                tasks[task_id]["completions"] = tasks[task_id].get("completions", 0) + 1
                _save("tasks", tasks)

    # ---------- Submissions ----------
    @staticmethod
    def create_submission(submission_id: str, task_id: str, user_id: int,
                           proof_text: str = "", proof_file_id: str = "") -> dict:
        with LOCK:
            subs = _load("submissions")
            subs[submission_id] = {
                "id": submission_id,
                "task_id": task_id,
                "user_id": user_id,
                "proof_text": proof_text,
                "proof_file_id": proof_file_id,
                "status": "pending",  # pending | approved | rejected
                "submitted_at": datetime.utcnow().isoformat(),
                "reviewed_at": None,
                "reviewed_by": None,
            }
            _save("submissions", subs)
            return subs[submission_id]

    @staticmethod
    def get_submission(submission_id: str) -> Optional[dict]:
        with LOCK:
            return _load("submissions").get(submission_id)

    @staticmethod
    def list_pending_submissions() -> list:
        with LOCK:
            subs = _load("submissions")
            return [s for s in subs.values() if s["status"] == "pending"]

    @staticmethod
    def review_submission(submission_id: str, approve: bool, reviewer_id: int) -> Optional[dict]:
        with LOCK:
            subs = _load("submissions")
            if submission_id not in subs:
                return None
            subs[submission_id]["status"] = "approved" if approve else "rejected"
            subs[submission_id]["reviewed_at"] = datetime.utcnow().isoformat()
            subs[submission_id]["reviewed_by"] = reviewer_id
            _save("submissions", subs)
            return subs[submission_id]

    # ---------- Rewards log ----------
    @staticmethod
    def log_reward(user_id: int, task_id: str, amount: float) -> None:
        with LOCK:
            rewards = _load("rewards")
            log = rewards.setdefault("log", [])
            log.append({
                "user_id": user_id,
                "task_id": task_id,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat(),
            })
            _save("rewards", rewards)
