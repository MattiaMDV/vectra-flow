"""Domain models for RisolvoProb.

Entities
--------
User      — participant (name).
Group     — collection of users with one admin.
Period    — time window (1/2/3/6 months) for a group; one active at a time.
Item      — shared article with a fixed fee and a designated owner.
Movement  — record of a "take" event; tracks payment and penalty state.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

PENALTY_FEE: Decimal = Decimal("5.00")
PAYMENT_DAYS: int = 7
VALID_DURATIONS: tuple[int, ...] = (1, 2, 3, 6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _add_months(dt: datetime, months: int) -> datetime:
    """Return *dt* shifted forward by *months* calendar months.

    If the resulting month has fewer days than *dt.day*, the date is clamped
    to the last valid day of that month (e.g. Jan 31 + 1 month → Feb 28/29).
    """
    target_month = dt.month + months
    years_over, month = divmod(target_month - 1, 12)
    year = dt.year + years_over
    month += 1  # divmod gives 0-based month
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


@dataclass
class User:
    """A participant in one or more groups."""

    id: str
    name: str

    @classmethod
    def create(cls, name: str) -> "User":
        if not name or not name.strip():
            raise ValueError("User name must not be empty.")
        return cls(id=_new_id(), name=name.strip())


@dataclass
class Group:
    """A named group of users with a designated admin."""

    id: str
    name: str
    admin_id: str
    member_ids: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, name: str, admin_id: str) -> "Group":
        if not name or not name.strip():
            raise ValueError("Group name must not be empty.")
        return cls(
            id=_new_id(),
            name=name.strip(),
            admin_id=admin_id,
            member_ids=[admin_id],
        )

    def add_member(self, user_id: str) -> None:
        if user_id not in self.member_ids:
            self.member_ids.append(user_id)

    def is_admin(self, user_id: str) -> bool:
        return self.admin_id == user_id

    def has_member(self, user_id: str) -> bool:
        return user_id in self.member_ids


@dataclass
class Period:
    """A time window in which movements are tracked for a group."""

    id: str
    group_id: str
    duration_months: int
    start_date: datetime
    end_date: datetime
    status: str = "active"  # "active" | "closed"

    @classmethod
    def create(
        cls,
        group_id: str,
        duration_months: int,
        start_date: Optional[datetime] = None,
    ) -> "Period":
        if duration_months not in VALID_DURATIONS:
            raise ValueError(
                f"duration_months must be one of {VALID_DURATIONS}, got {duration_months}."
            )
        start = start_date or _now_utc()
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = _add_months(start, duration_months)
        return cls(
            id=_new_id(),
            group_id=group_id,
            duration_months=duration_months,
            start_date=start,
            end_date=end,
            status="active",
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def days_remaining(self, now: Optional[datetime] = None) -> int:
        ts = now or _now_utc()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = self.end_date - ts
        return max(0, delta.days)


@dataclass
class Item:
    """A shared article with a fixed fee and a designated owner."""

    id: str
    group_id: str
    name: str
    category: str
    owner_id: str
    base_fee: Decimal

    @classmethod
    def create(
        cls,
        group_id: str,
        name: str,
        category: str,
        owner_id: str,
        base_fee: Decimal,
    ) -> "Item":
        if not name or not name.strip():
            raise ValueError("Item name must not be empty.")
        if base_fee < Decimal("0"):
            raise ValueError("base_fee must be >= 0.")
        return cls(
            id=_new_id(),
            group_id=group_id,
            name=name.strip(),
            category=category.strip(),
            owner_id=owner_id,
            base_fee=base_fee.quantize(Decimal("0.01")),
        )


@dataclass
class Movement:
    """Record of a 'take' event: who took which item, and payment state."""

    id: str
    group_id: str
    period_id: str
    item_id: str
    taker_id: str
    owner_id: str
    base_fee: Decimal
    created_at: datetime
    due_at: datetime
    paid_at: Optional[datetime] = None
    penalty_applied: bool = False
    penalty_fee: Decimal = field(default_factory=lambda: Decimal("0.00"))
    note: str = ""

    @classmethod
    def create(
        cls,
        group_id: str,
        period_id: str,
        item: Item,
        taker_id: str,
        note: str = "",
        now: Optional[datetime] = None,
    ) -> "Movement":
        if taker_id == item.owner_id:
            raise ValueError("Taker and owner must be different users.")
        ts = now or _now_utc()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        due = ts + timedelta(days=PAYMENT_DAYS)
        return cls(
            id=_new_id(),
            group_id=group_id,
            period_id=period_id,
            item_id=item.id,
            taker_id=taker_id,
            owner_id=item.owner_id,
            base_fee=item.base_fee,
            created_at=ts,
            due_at=due,
            note=note,
        )

    @property
    def is_paid(self) -> bool:
        return self.paid_at is not None

    def mark_paid(self, now: Optional[datetime] = None) -> "Movement":
        if self.is_paid:
            raise ValueError("Movement is already paid.")
        ts = now or _now_utc()
        return Movement(
            id=self.id,
            group_id=self.group_id,
            period_id=self.period_id,
            item_id=self.item_id,
            taker_id=self.taker_id,
            owner_id=self.owner_id,
            base_fee=self.base_fee,
            created_at=self.created_at,
            due_at=self.due_at,
            paid_at=ts,
            penalty_applied=self.penalty_applied,
            penalty_fee=self.penalty_fee,
            note=self.note,
        )
