"""Business logic for RisolvoProb.

Rules
-----
* compute_due_amount  — amount currently owed for a single movement.
* apply_pending_penalties — flag overdue, unpaid movements with a 5 € penalty.
* compute_balances    — credit / debit / net per member + common penalty fund.
* close_period        — validate admin rights, close period, return balances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .models import Movement, PENALTY_FEE, Period


# ---------------------------------------------------------------------------
# Per-movement amount
# ---------------------------------------------------------------------------


def compute_due_amount(movement: Movement, now: Optional[datetime] = None) -> Decimal:
    """Return the amount currently owed for *movement*.

    * 0.00  if already paid.
    * base_fee if within the 7-day window.
    * base_fee + 5.00 if the deadline has passed (regardless of whether
      penalty_applied has been set yet — this gives a real-time view).
    """
    if movement.paid_at is not None:
        return Decimal("0.00")
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts <= movement.due_at:
        return movement.base_fee
    return movement.base_fee + PENALTY_FEE


# ---------------------------------------------------------------------------
# Penalty application
# ---------------------------------------------------------------------------


def apply_pending_penalties(
    movements: list[Movement], now: Optional[datetime] = None
) -> list[Movement]:
    """Return a new list with overdue unpaid movements flagged as penalised.

    A penalty is applied once: if *penalty_applied* is already ``True``, the
    movement is left unchanged.
    """
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    result: list[Movement] = []
    for m in movements:
        if m.paid_at is None and not m.penalty_applied and ts > m.due_at:
            m = Movement(
                id=m.id,
                group_id=m.group_id,
                period_id=m.period_id,
                item_id=m.item_id,
                taker_id=m.taker_id,
                owner_id=m.owner_id,
                base_fee=m.base_fee,
                created_at=m.created_at,
                due_at=m.due_at,
                paid_at=m.paid_at,
                penalty_applied=True,
                penalty_fee=PENALTY_FEE,
                note=m.note,
            )
        result.append(m)
    return result


# ---------------------------------------------------------------------------
# Balance computation
# ---------------------------------------------------------------------------


def compute_balances(movements: list[Movement]) -> dict:
    """Compute credit / debit / net balances for all participants.

    Returns a dict::

        {
            "members": {
                "<user_id>": {
                    "credit": Decimal,   # sum of base_fee where owner_id == user
                    "debit":  Decimal,   # sum of base_fee where taker_id == user
                    "net":    Decimal,   # credit - debit
                },
                …
            },
            "common_fund_penalties": Decimal,  # total penalty euros (informational)
        }

    Penalties go into the *common fund* and are **not** added to any owner's
    credit (per specification).
    """
    balances: dict[str, dict[str, Decimal]] = {}

    def _ensure(uid: str) -> None:
        if uid not in balances:
            balances[uid] = {
                "credit": Decimal("0.00"),
                "debit": Decimal("0.00"),
                "net": Decimal("0.00"),
            }

    total_penalties = Decimal("0.00")

    for m in movements:
        _ensure(m.owner_id)
        _ensure(m.taker_id)
        balances[m.owner_id]["credit"] += m.base_fee
        balances[m.taker_id]["debit"] += m.base_fee
        if m.penalty_applied:
            total_penalties += m.penalty_fee

    for uid in balances:
        balances[uid]["net"] = balances[uid]["credit"] - balances[uid]["debit"]

    return {
        "members": balances,
        "common_fund_penalties": total_penalties,
    }


# ---------------------------------------------------------------------------
# Period close
# ---------------------------------------------------------------------------


def close_period(
    period: Period,
    movements: list[Movement],
    requesting_user_id: str,
    group_admin_id: str,
    now: Optional[datetime] = None,
) -> tuple[Period, dict]:
    """Close *period* and return the final balance report.

    Only the group admin may close a period.  Returns the updated (closed)
    Period object and the balance dict from :func:`compute_balances`.

    Raises
    ------
    PermissionError
        If *requesting_user_id* is not the group admin.
    ValueError
        If the period is already closed.
    """
    if requesting_user_id != group_admin_id:
        raise PermissionError("Only the group admin may close a period.")
    if not period.is_active:
        raise ValueError("Period is already closed.")

    ts = now or datetime.now(timezone.utc)

    # Apply any outstanding penalties before closing.
    penalised = apply_pending_penalties(movements, now=ts)
    balances = compute_balances(penalised)

    closed_period = Period(
        id=period.id,
        group_id=period.group_id,
        duration_months=period.duration_months,
        start_date=period.start_date,
        end_date=period.end_date,
        status="closed",
    )
    return closed_period, balances
