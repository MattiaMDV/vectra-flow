"""Notification helpers for RisolvoProb.

Two kinds of messages are generated:

* **Overdue** — movements that are past their 7-day window and not yet paid.
  These carry a 5 € penalty on top of the base fee.
* **Reminder** — movements that will expire within *days_before* days (default 2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import Movement, PENALTY_FEE


def overdue_notifications(
    movements: list[Movement],
    users: Optional[dict[str, str]] = None,
    items: Optional[dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> list[str]:
    """Return a list of notification strings for unpaid, overdue movements.

    Parameters
    ----------
    movements:
        Full list of movements to inspect.
    users:
        Optional mapping ``{user_id: display_name}`` for friendlier messages.
    items:
        Optional mapping ``{item_id: item_name}`` for friendlier messages.
    now:
        Reference timestamp (defaults to UTC now).
    """
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    messages: list[str] = []
    for m in movements:
        if m.paid_at is not None:
            continue
        if ts <= m.due_at:
            continue
        taker = users.get(m.taker_id, m.taker_id) if users else m.taker_id
        item_name = items.get(m.item_id, m.item_id) if items else m.item_id
        total = m.base_fee + (m.penalty_fee if m.penalty_applied else PENALTY_FEE)
        days_late = (ts - m.due_at).days
        messages.append(
            f"⚠️  SCADUTO — {taker} deve versare {total:.2f} € "
            f"per '{item_name}' "
            f"(quota {m.base_fee:.2f} € + multa 5.00 €, "
            f"scaduto da {days_late} giorno/i)."
        )
    return messages


def reminder_notifications(
    movements: list[Movement],
    users: Optional[dict[str, str]] = None,
    items: Optional[dict[str, str]] = None,
    now: Optional[datetime] = None,
    days_before: int = 2,
) -> list[str]:
    """Return reminder strings for movements whose deadline is approaching.

    Only unpaid movements due within *days_before* days (exclusive of already
    overdue ones) are included.
    """
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    threshold = ts + timedelta(days=days_before)
    messages: list[str] = []
    for m in movements:
        if m.paid_at is not None:
            continue
        if ts > m.due_at:
            continue  # already overdue — handled by overdue_notifications
        if m.due_at > threshold:
            continue
        taker = users.get(m.taker_id, m.taker_id) if users else m.taker_id
        item_name = items.get(m.item_id, m.item_id) if items else m.item_id
        days_left = (m.due_at - ts).days
        messages.append(
            f"🔔  PROMEMORIA — {taker} deve ancora versare {m.base_fee:.2f} € "
            f"per '{item_name}' "
            f"(scadenza tra {days_left} giorno/i)."
        )
    return messages
