"""JSON-based persistence store for RisolvoProb.

All data is kept in a single JSON file (default: ``data/risolvo_prob/db.json``).
Each top-level key holds a dict of entity-id → serialised entity.

Usage
-----
    store = Store()
    user = User.create("Alice")
    store.save_user(user)
    alice = store.get_user(user.id)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .models import Group, Item, Movement, Period, User

_DEFAULT_PATH = Path("data/risolvo_prob/db.json")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _decimal_to_str(v: Decimal) -> str:
    return str(v)


def _str_to_decimal(v: str) -> Decimal:
    return Decimal(v)


def _dt_to_str(v: Optional[datetime]) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat()


def _str_to_dt(v: Optional[str]) -> Optional[datetime]:
    if v is None:
        return None
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _str_to_dt_required(v: str) -> datetime:
    """Like _str_to_dt but asserts the value is present (raises if None/empty)."""
    if not v:
        raise ValueError("Expected a non-empty datetime string.")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Serialisers / deserialisers
# ---------------------------------------------------------------------------


def _user_to_dict(u: User) -> dict:
    return {"id": u.id, "name": u.name}


def _user_from_dict(d: dict) -> User:
    return User(id=d["id"], name=d["name"])


def _group_to_dict(g: Group) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "admin_id": g.admin_id,
        "member_ids": g.member_ids,
    }


def _group_from_dict(d: dict) -> Group:
    return Group(
        id=d["id"],
        name=d["name"],
        admin_id=d["admin_id"],
        member_ids=d.get("member_ids", []),
    )


def _period_to_dict(p: Period) -> dict:
    return {
        "id": p.id,
        "group_id": p.group_id,
        "duration_months": p.duration_months,
        "start_date": _dt_to_str(p.start_date),
        "end_date": _dt_to_str(p.end_date),
        "status": p.status,
    }


def _period_from_dict(d: dict) -> Period:
    return Period(
        id=d["id"],
        group_id=d["group_id"],
        duration_months=d["duration_months"],
        start_date=_str_to_dt_required(d["start_date"]),
        end_date=_str_to_dt_required(d["end_date"]),
        status=d.get("status", "active"),
    )


def _item_to_dict(it: Item) -> dict:
    return {
        "id": it.id,
        "group_id": it.group_id,
        "name": it.name,
        "category": it.category,
        "owner_id": it.owner_id,
        "base_fee": _decimal_to_str(it.base_fee),
    }


def _item_from_dict(d: dict) -> Item:
    return Item(
        id=d["id"],
        group_id=d["group_id"],
        name=d["name"],
        category=d["category"],
        owner_id=d["owner_id"],
        base_fee=_str_to_decimal(d["base_fee"]),
    )


def _movement_to_dict(m: Movement) -> dict:
    return {
        "id": m.id,
        "group_id": m.group_id,
        "period_id": m.period_id,
        "item_id": m.item_id,
        "taker_id": m.taker_id,
        "owner_id": m.owner_id,
        "base_fee": _decimal_to_str(m.base_fee),
        "created_at": _dt_to_str(m.created_at),
        "due_at": _dt_to_str(m.due_at),
        "paid_at": _dt_to_str(m.paid_at),
        "penalty_applied": m.penalty_applied,
        "penalty_fee": _decimal_to_str(m.penalty_fee),
        "note": m.note,
    }


def _movement_from_dict(d: dict) -> Movement:
    return Movement(
        id=d["id"],
        group_id=d["group_id"],
        period_id=d["period_id"],
        item_id=d["item_id"],
        taker_id=d["taker_id"],
        owner_id=d["owner_id"],
        base_fee=_str_to_decimal(d["base_fee"]),
        created_at=_str_to_dt_required(d["created_at"]),
        due_at=_str_to_dt_required(d["due_at"]),
        paid_at=_str_to_dt(d.get("paid_at")),
        penalty_applied=d.get("penalty_applied", False),
        penalty_fee=_str_to_decimal(d.get("penalty_fee", "0.00")),
        note=d.get("note", ""),
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class Store:
    """Simple JSON-backed store for all RisolvoProb entities."""

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._data: dict = {
            "users": {},
            "groups": {},
            "periods": {},
            "items": {},
            "movements": {},
        }
        if self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        with self._path.open(encoding="utf-8") as fh:
            self._data = json.load(fh)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def save_user(self, user: User) -> None:
        self._data["users"][user.id] = _user_to_dict(user)
        self._save()

    def get_user(self, user_id: str) -> Optional[User]:
        d = self._data["users"].get(user_id)
        return _user_from_dict(d) if d else None

    def list_users(self) -> list[User]:
        return [_user_from_dict(d) for d in self._data["users"].values()]

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def save_group(self, group: Group) -> None:
        self._data["groups"][group.id] = _group_to_dict(group)
        self._save()

    def get_group(self, group_id: str) -> Optional[Group]:
        d = self._data["groups"].get(group_id)
        return _group_from_dict(d) if d else None

    def list_groups(self) -> list[Group]:
        return [_group_from_dict(d) for d in self._data["groups"].values()]

    # ------------------------------------------------------------------
    # Periods
    # ------------------------------------------------------------------

    def save_period(self, period: Period) -> None:
        self._data["periods"][period.id] = _period_to_dict(period)
        self._save()

    def get_period(self, period_id: str) -> Optional[Period]:
        d = self._data["periods"].get(period_id)
        return _period_from_dict(d) if d else None

    def get_active_period(self, group_id: str) -> Optional[Period]:
        """Return the single active period for *group_id*, or None."""
        for d in self._data["periods"].values():
            if d["group_id"] == group_id and d.get("status") == "active":
                return _period_from_dict(d)
        return None

    def list_periods(self, group_id: Optional[str] = None) -> list[Period]:
        periods = [_period_from_dict(d) for d in self._data["periods"].values()]
        if group_id:
            periods = [p for p in periods if p.group_id == group_id]
        return periods

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def save_item(self, item: Item) -> None:
        self._data["items"][item.id] = _item_to_dict(item)
        self._save()

    def get_item(self, item_id: str) -> Optional[Item]:
        d = self._data["items"].get(item_id)
        return _item_from_dict(d) if d else None

    def list_items(self, group_id: Optional[str] = None) -> list[Item]:
        items = [_item_from_dict(d) for d in self._data["items"].values()]
        if group_id:
            items = [it for it in items if it.group_id == group_id]
        return items

    # ------------------------------------------------------------------
    # Movements
    # ------------------------------------------------------------------

    def save_movement(self, movement: Movement) -> None:
        self._data["movements"][movement.id] = _movement_to_dict(movement)
        self._save()

    def get_movement(self, movement_id: str) -> Optional[Movement]:
        d = self._data["movements"].get(movement_id)
        return _movement_from_dict(d) if d else None

    def list_movements(
        self,
        group_id: Optional[str] = None,
        period_id: Optional[str] = None,
        taker_id: Optional[str] = None,
    ) -> list[Movement]:
        movements = [_movement_from_dict(d) for d in self._data["movements"].values()]
        if group_id:
            movements = [m for m in movements if m.group_id == group_id]
        if period_id:
            movements = [m for m in movements if m.period_id == period_id]
        if taker_id:
            movements = [m for m in movements if m.taker_id == taker_id]
        return movements
