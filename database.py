"""
database.py — MongoDB persistence for SUDO users and their bandwidth quota.

A single collection ("sudo_users") stores one document per SUDO user with
both their permission record and their monthly bandwidth-usage counters,
so everything survives bot restarts.
"""

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, DATABASE_NAME, SUDO_MONTHLY_LIMIT_BYTES

logger = logging.getLogger(__name__)

_client = None
_db = None
_sudo_col = None


def init_db() -> None:
    """Initialize the MongoDB client/collection. Safe to call multiple times."""
    global _client, _db, _sudo_col
    if _client is not None:
        return
    if not MONGO_URI:
        logger.warning("MONGO_URI is not set; SUDO_USERS persistence is disabled.")
        return
    _client = AsyncIOMotorClient(MONGO_URI)
    _db = _client[DATABASE_NAME]
    _sudo_col = _db["sudo_users"]


def is_configured() -> bool:
    return _sudo_col is not None


def _current_month_str(dt: datetime = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def add_sudo_user(user_id: int) -> bool:
    """Add a SUDO user with fresh quota fields. Returns False if already exists."""
    if _sudo_col is None:
        raise RuntimeError("Database is not initialized. Set the MONGO_URI environment variable.")
    existing = await _sudo_col.find_one({"user_id": user_id})
    if existing:
        return False
    doc = {
        "user_id": user_id,
        "monthly_limit_bytes": SUDO_MONTHLY_LIMIT_BYTES,
        "used_bytes": 0,
        "last_used_date": None,
        "current_month": _current_month_str(),
        "created_at": _now(),
    }
    await _sudo_col.insert_one(doc)
    return True


async def remove_sudo_user(user_id: int) -> bool:
    """Remove a SUDO user. Returns False if the user was not found."""
    if _sudo_col is None:
        raise RuntimeError("Database is not initialized. Set the MONGO_URI environment variable.")
    result = await _sudo_col.delete_one({"user_id": user_id})
    return result.deleted_count > 0


async def get_all_sudo_ids() -> list:
    """Return every stored SUDO user id, used to warm the in-memory cache on startup."""
    if _sudo_col is None:
        return []
    ids = []
    async for doc in _sudo_col.find({}, {"user_id": 1}):
        ids.append(doc["user_id"])
    return ids


async def _reset_if_new_month(doc: dict) -> dict:
    """Reset a single SUDO user's quota doc in-place if the billing month rolled over."""
    month_now = _current_month_str()
    if doc.get("current_month") != month_now:
        await _sudo_col.update_one(
            {"user_id": doc["user_id"]},
            {"$set": {"used_bytes": 0, "current_month": month_now}},
        )
        doc["used_bytes"] = 0
        doc["current_month"] = month_now
    return doc


async def reset_all_if_new_month() -> int:
    """
    Reset every SUDO user whose stored billing month is stale. Called on
    startup and periodically, so the monthly reset applies automatically
    even if the bot was offline when the month actually changed.
    """
    if _sudo_col is None:
        return 0
    month_now = _current_month_str()
    result = await _sudo_col.update_many(
        {"current_month": {"$ne": month_now}},
        {"$set": {"used_bytes": 0, "current_month": month_now}},
    )
    if result.modified_count:
        logger.info(f"Monthly quota reset applied to {result.modified_count} SUDO user(s).")
    return result.modified_count


async def get_sudo_doc(user_id: int) -> dict:
    """Fetch (and lazily reset) a SUDO user's quota doc. Returns None if not a SUDO user."""
    if _sudo_col is None:
        return None
    doc = await _sudo_col.find_one({"user_id": user_id})
    if not doc:
        return None
    doc = await _reset_if_new_month(doc)
    return doc


async def has_quota(user_id: int) -> bool:
    """True if the SUDO user still has remaining bandwidth this month (or isn't a SUDO user)."""
    doc = await get_sudo_doc(user_id)
    if doc is None:
        return True
    return doc.get("used_bytes", 0) < doc.get("monthly_limit_bytes", SUDO_MONTHLY_LIMIT_BYTES)


async def add_usage(user_id: int, num_bytes: int) -> None:
    """Increase used_bytes for a SUDO user and stamp last_used_date. No-op for non-SUDO users."""
    if _sudo_col is None or num_bytes <= 0:
        return
    doc = await get_sudo_doc(user_id)
    if doc is None:
        return
    await _sudo_col.update_one(
        {"user_id": user_id},
        {
            "$inc": {"used_bytes": num_bytes},
            "$set": {"last_used_date": _now()},
        },
    )
