"""Tests for vectra_flow.risolvo_prob — domain models, business logic, store, notifications."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from vectra_flow.risolvo_prob.domain import (
    apply_pending_penalties,
    close_period,
    compute_balances,
    compute_due_amount,
)
from vectra_flow.risolvo_prob.models import (
    PAYMENT_DAYS,
    PENALTY_FEE,
    Group,
    Item,
    Movement,
    Period,
    User,
    _add_months,
)
from vectra_flow.risolvo_prob.notifications import overdue_notifications, reminder_notifications
from vectra_flow.risolvo_prob.store import Store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_UTC = timezone.utc


def _dt(s: str) -> datetime:
    """Parse an ISO-8601 string and attach UTC."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt


@pytest.fixture()
def alice() -> User:
    return User(id="u-alice", name="Alice")


@pytest.fixture()
def bob() -> User:
    return User(id="u-bob", name="Bob")


@pytest.fixture()
def group(alice: User) -> Group:
    return Group(
        id="g-1",
        name="Sorelle",
        admin_id=alice.id,
        member_ids=[alice.id, "u-bob"],
    )


@pytest.fixture()
def period(group: Group) -> Period:
    start = _dt("2026-01-01T00:00:00")
    return Period.create(group.id, duration_months=1, start_date=start)


@pytest.fixture()
def item(group: Group, alice: User) -> Item:
    return Item.create(
        group_id=group.id,
        name="Felpa",
        category="Vestiti",
        owner_id=alice.id,
        base_fee=Decimal("2.00"),
    )


@pytest.fixture()
def movement(group: Group, period: Period, item: Item) -> Movement:
    now = _dt("2026-01-10T12:00:00")
    return Movement.create(
        group_id=group.id,
        period_id=period.id,
        item=item,
        taker_id="u-bob",
        now=now,
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestUserCreate:
    def test_creates_user(self) -> None:
        u = User.create("Mario")
        assert u.name == "Mario"
        assert u.id

    def test_strips_whitespace(self) -> None:
        u = User.create("  Anna  ")
        assert u.name == "Anna"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            User.create("")

    def test_whitespace_only_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            User.create("   ")


class TestGroupCreate:
    def test_admin_auto_added_as_member(self) -> None:
        g = Group.create("Test", "u-1")
        assert "u-1" in g.member_ids

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Group.create("", "u-1")

    def test_add_member(self) -> None:
        g = Group.create("Test", "u-1")
        g.add_member("u-2")
        assert "u-2" in g.member_ids

    def test_add_duplicate_member_is_idempotent(self) -> None:
        g = Group.create("Test", "u-1")
        g.add_member("u-1")
        assert g.member_ids.count("u-1") == 1

    def test_is_admin(self, group: Group, alice: User) -> None:
        assert group.is_admin(alice.id)
        assert not group.is_admin("u-bob")


class TestAddMonths:
    def test_simple(self) -> None:
        dt = _dt("2026-01-15")
        assert _add_months(dt, 1) == _dt("2026-02-15")

    def test_year_boundary(self) -> None:
        dt = _dt("2026-11-01")
        assert _add_months(dt, 3) == _dt("2027-02-01")

    def test_end_of_month_clamp(self) -> None:
        # Jan 31 + 1 month → Feb 28 (non-leap 2026)
        dt = _dt("2026-01-31")
        result = _add_months(dt, 1)
        assert result == _dt("2026-02-28")

    def test_leap_year(self) -> None:
        dt = _dt("2024-01-31")
        result = _add_months(dt, 1)
        assert result == _dt("2024-02-29")


class TestPeriodCreate:
    def test_valid_duration(self) -> None:
        for d in (1, 2, 3, 6):
            p = Period.create("g-1", d, start_date=_dt("2026-01-01"))
            assert p.duration_months == d

    def test_invalid_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="duration_months"):
            Period.create("g-1", 4)

    def test_end_date_one_month(self) -> None:
        start = _dt("2026-03-01T10:00:00")
        p = Period.create("g-1", 1, start_date=start)
        assert p.end_date == _dt("2026-04-01T10:00:00")

    def test_end_date_six_months(self) -> None:
        start = _dt("2026-01-01T00:00:00")
        p = Period.create("g-1", 6, start_date=start)
        assert p.end_date == _dt("2026-07-01T00:00:00")

    def test_status_default_active(self) -> None:
        p = Period.create("g-1", 1)
        assert p.status == "active"
        assert p.is_active

    def test_days_remaining(self) -> None:
        start = _dt("2026-01-01T00:00:00")
        p = Period.create("g-1", 1, start_date=start)
        now = _dt("2026-01-20T00:00:00")
        # end is 2026-02-01, so remaining = 12 days
        assert p.days_remaining(now) == 12

    def test_days_remaining_past_end(self) -> None:
        start = _dt("2026-01-01T00:00:00")
        p = Period.create("g-1", 1, start_date=start)
        now = _dt("2026-03-01T00:00:00")
        assert p.days_remaining(now) == 0


class TestItemCreate:
    def test_creates_item(self) -> None:
        it = Item.create("g-1", "Cintura", "Accessori", "u-1", Decimal("0.50"))
        assert it.base_fee == Decimal("0.50")
        assert it.name == "Cintura"

    def test_zero_fee_allowed(self) -> None:
        it = Item.create("g-1", "X", "Y", "u-1", Decimal("0"))
        assert it.base_fee == Decimal("0.00")

    def test_negative_fee_raises(self) -> None:
        with pytest.raises(ValueError, match="base_fee"):
            Item.create("g-1", "X", "Y", "u-1", Decimal("-1.00"))

    def test_fee_rounded_to_cents(self) -> None:
        it = Item.create("g-1", "X", "Y", "u-1", Decimal("2.999"))
        assert it.base_fee == Decimal("3.00")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Item.create("g-1", "", "Y", "u-1", Decimal("1.00"))


class TestMovementCreate:
    def test_taker_equals_owner_raises(self, group: Group, period: Period, item: Item) -> None:
        with pytest.raises(ValueError, match="Taker and owner"):
            Movement.create(
                group_id=group.id,
                period_id=period.id,
                item=item,
                taker_id=item.owner_id,  # same as owner
            )

    def test_due_at_is_7_days_after_creation(self, movement: Movement) -> None:
        delta = movement.due_at - movement.created_at
        assert delta == timedelta(days=PAYMENT_DAYS)

    def test_mark_paid(self, movement: Movement) -> None:
        paid = movement.mark_paid()
        assert paid.is_paid
        assert paid.paid_at is not None

    def test_mark_paid_twice_raises(self, movement: Movement) -> None:
        paid = movement.mark_paid()
        with pytest.raises(ValueError, match="already paid"):
            paid.mark_paid()

    def test_note_stored(self, group: Group, period: Period, item: Item) -> None:
        m = Movement.create(
            group_id=group.id,
            period_id=period.id,
            item=item,
            taker_id="u-bob",
            note="per la festa",
        )
        assert m.note == "per la festa"


# ---------------------------------------------------------------------------
# Domain logic tests
# ---------------------------------------------------------------------------


class TestComputeDueAmount:
    def test_paid_returns_zero(self, movement: Movement) -> None:
        paid = movement.mark_paid()
        assert compute_due_amount(paid) == Decimal("0.00")

    def test_within_deadline_returns_base_fee(self, movement: Movement) -> None:
        # due_at = created_at + 7 days; check at created_at + 3 days
        now = movement.created_at + timedelta(days=3)
        assert compute_due_amount(movement, now=now) == movement.base_fee

    def test_at_exact_deadline_returns_base_fee(self, movement: Movement) -> None:
        assert compute_due_amount(movement, now=movement.due_at) == movement.base_fee

    def test_past_deadline_returns_base_plus_penalty(self, movement: Movement) -> None:
        now = movement.due_at + timedelta(seconds=1)
        expected = movement.base_fee + PENALTY_FEE
        assert compute_due_amount(movement, now=now) == expected

    def test_zero_fee_item_past_deadline(self, group: Group, period: Period) -> None:
        zero_item = Item.create("g-1", "Gratis", "Test", "u-alice", Decimal("0.00"))
        m = Movement.create(
            group_id=group.id,
            period_id=period.id,
            item=zero_item,
            taker_id="u-bob",
        )
        now = m.due_at + timedelta(days=1)
        assert compute_due_amount(m, now=now) == PENALTY_FEE


class TestApplyPendingPenalties:
    def test_overdue_unpaid_gets_penalty(self, movement: Movement) -> None:
        now = movement.due_at + timedelta(hours=1)
        result = apply_pending_penalties([movement], now=now)
        assert result[0].penalty_applied
        assert result[0].penalty_fee == PENALTY_FEE

    def test_within_deadline_no_penalty(self, movement: Movement) -> None:
        now = movement.due_at - timedelta(hours=1)
        result = apply_pending_penalties([movement], now=now)
        assert not result[0].penalty_applied

    def test_already_penalised_not_doubled(self, movement: Movement) -> None:
        now = movement.due_at + timedelta(hours=1)
        once = apply_pending_penalties([movement], now=now)
        twice = apply_pending_penalties(once, now=now + timedelta(days=1))
        assert twice[0].penalty_fee == PENALTY_FEE  # unchanged

    def test_paid_movement_not_penalised(self, movement: Movement) -> None:
        paid = movement.mark_paid()
        now = paid.due_at + timedelta(days=10)
        result = apply_pending_penalties([paid], now=now)
        assert not result[0].penalty_applied


class TestComputeBalances:
    def _make_movement(
        self,
        group_id: str,
        period_id: str,
        owner_id: str,
        taker_id: str,
        base_fee: Decimal,
        penalty_applied: bool = False,
    ) -> Movement:
        now = _dt("2026-01-10T12:00:00")
        item = Item(
            id="it-tmp",
            group_id=group_id,
            name="X",
            category="Y",
            owner_id=owner_id,
            base_fee=base_fee,
        )
        m = Movement.create(
            group_id=group_id,
            period_id=period_id,
            item=item,
            taker_id=taker_id,
            now=now,
        )
        if penalty_applied:
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
        return m

    def test_simple_two_movements(self) -> None:
        m1 = self._make_movement("g", "p", "u-alice", "u-bob", Decimal("2.00"))
        m2 = self._make_movement("g", "p", "u-alice", "u-bob", Decimal("1.00"))
        report = compute_balances([m1, m2])
        members = report["members"]
        assert members["u-alice"]["credit"] == Decimal("3.00")
        assert members["u-bob"]["debit"] == Decimal("3.00")
        assert members["u-alice"]["net"] == Decimal("3.00")

    def test_penalties_in_common_fund(self) -> None:
        m = self._make_movement("g", "p", "u-alice", "u-bob", Decimal("2.00"), penalty_applied=True)
        report = compute_balances([m])
        assert report["common_fund_penalties"] == PENALTY_FEE
        # Penalty does NOT increase owner's credit
        assert report["members"]["u-alice"]["credit"] == Decimal("2.00")

    def test_empty_movements(self) -> None:
        report = compute_balances([])
        assert report["members"] == {}
        assert report["common_fund_penalties"] == Decimal("0.00")

    def test_net_balance_symmetric(self) -> None:
        # Alice takes from Bob, Bob takes from Alice
        item_alice = Item(id="ia", group_id="g", name="A", category="C", owner_id="u-alice", base_fee=Decimal("2.00"))
        item_bob = Item(id="ib", group_id="g", name="B", category="C", owner_id="u-bob", base_fee=Decimal("2.00"))
        now = _dt("2026-01-10")
        m1 = Movement.create("g", "p", item_alice, "u-bob", now=now)
        m2 = Movement.create("g", "p", item_bob, "u-alice", now=now)
        report = compute_balances([m1, m2])
        assert report["members"]["u-alice"]["net"] == Decimal("0.00")
        assert report["members"]["u-bob"]["net"] == Decimal("0.00")


class TestClosePeriod:
    def test_closes_period(self, group: Group, period: Period) -> None:
        closed, _ = close_period(
            period=period,
            movements=[],
            requesting_user_id=group.admin_id,
            group_admin_id=group.admin_id,
        )
        assert closed.status == "closed"
        assert not closed.is_active

    def test_non_admin_raises_permission_error(self, group: Group, period: Period) -> None:
        with pytest.raises(PermissionError):
            close_period(
                period=period,
                movements=[],
                requesting_user_id="u-bob",
                group_admin_id=group.admin_id,
            )

    def test_already_closed_raises_value_error(self, group: Group, period: Period) -> None:
        closed_period = Period(
            id=period.id,
            group_id=period.group_id,
            duration_months=period.duration_months,
            start_date=period.start_date,
            end_date=period.end_date,
            status="closed",
        )
        with pytest.raises(ValueError, match="already closed"):
            close_period(
                period=closed_period,
                movements=[],
                requesting_user_id=group.admin_id,
                group_admin_id=group.admin_id,
            )

    def test_penalties_applied_on_close(self, group: Group, period: Period, movement: Movement) -> None:
        # movement due_at = created_at + 7 days; close well past deadline
        past_due = movement.due_at + timedelta(days=5)
        closed, balances = close_period(
            period=period,
            movements=[movement],
            requesting_user_id=group.admin_id,
            group_admin_id=group.admin_id,
            now=past_due,
        )
        assert balances["common_fund_penalties"] == PENALTY_FEE


# ---------------------------------------------------------------------------
# Notifications tests
# ---------------------------------------------------------------------------


class TestNotifications:
    def _overdue_movement(self) -> Movement:
        now = _dt("2026-01-01T00:00:00")
        item = Item(id="it", group_id="g", name="Felpa", category="Vestiti", owner_id="u-alice", base_fee=Decimal("2.00"))
        m = Movement.create("g", "p", item, "u-bob", now=now)
        return m

    def test_overdue_notification_generated(self) -> None:
        m = self._overdue_movement()
        past = m.due_at + timedelta(days=2)
        msgs = overdue_notifications([m], now=past)
        assert len(msgs) == 1
        assert "SCADUTO" in msgs[0]
        assert "u-bob" in msgs[0]

    def test_no_overdue_for_paid_movement(self) -> None:
        m = self._overdue_movement()
        paid = m.mark_paid()
        past = m.due_at + timedelta(days=2)
        msgs = overdue_notifications([paid], now=past)
        assert msgs == []

    def test_no_overdue_within_deadline(self) -> None:
        m = self._overdue_movement()
        still_within = m.due_at - timedelta(hours=1)
        msgs = overdue_notifications([m], now=still_within)
        assert msgs == []

    def test_overdue_uses_display_names(self) -> None:
        m = self._overdue_movement()
        past = m.due_at + timedelta(days=1)
        users = {"u-bob": "Roberto"}
        items = {"it": "Felpa Rossa"}
        msgs = overdue_notifications([m], users=users, items=items, now=past)
        assert "Roberto" in msgs[0]
        assert "Felpa Rossa" in msgs[0]

    def test_reminder_generated(self) -> None:
        m = self._overdue_movement()
        # 1 day before due
        one_day_before = m.due_at - timedelta(days=1)
        msgs = reminder_notifications([m], now=one_day_before, days_before=2)
        assert len(msgs) == 1
        assert "PROMEMORIA" in msgs[0]

    def test_no_reminder_for_paid(self) -> None:
        m = self._overdue_movement()
        paid = m.mark_paid()
        one_day_before = m.due_at - timedelta(days=1)
        msgs = reminder_notifications([paid], now=one_day_before, days_before=2)
        assert msgs == []

    def test_no_reminder_far_in_future(self) -> None:
        m = self._overdue_movement()
        far_before = m.due_at - timedelta(days=10)
        msgs = reminder_notifications([m], now=far_before, days_before=2)
        assert msgs == []

    def test_no_reminder_for_overdue(self) -> None:
        m = self._overdue_movement()
        past = m.due_at + timedelta(days=1)
        msgs = reminder_notifications([m], now=past)
        assert msgs == []


# ---------------------------------------------------------------------------
# Store tests
# ---------------------------------------------------------------------------


class TestStore:
    def test_save_and_retrieve_user(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        user = User.create("Luca")
        store.save_user(user)
        retrieved = store.get_user(user.id)
        assert retrieved is not None
        assert retrieved.name == "Luca"

    def test_save_and_retrieve_group(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        g = Group.create("Famiglia", "u-1")
        store.save_group(g)
        retrieved = store.get_group(g.id)
        assert retrieved is not None
        assert retrieved.name == "Famiglia"

    def test_get_active_period(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        p = Period.create("g-1", 1)
        store.save_period(p)
        active = store.get_active_period("g-1")
        assert active is not None
        assert active.id == p.id

    def test_no_active_period_after_close(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        p = Period.create("g-1", 1)
        store.save_period(p)
        closed = Period(
            id=p.id,
            group_id=p.group_id,
            duration_months=p.duration_months,
            start_date=p.start_date,
            end_date=p.end_date,
            status="closed",
        )
        store.save_period(closed)
        assert store.get_active_period("g-1") is None

    def test_save_and_retrieve_item(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        it = Item.create("g-1", "Cintura", "Accessori", "u-1", Decimal("0.50"))
        store.save_item(it)
        retrieved = store.get_item(it.id)
        assert retrieved is not None
        assert retrieved.base_fee == Decimal("0.50")

    def test_save_and_retrieve_movement(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        item = Item.create("g-1", "Felpa", "Vestiti", "u-alice", Decimal("2.00"))
        m = Movement.create("g-1", "p-1", item, "u-bob")
        store.save_movement(m)
        retrieved = store.get_movement(m.id)
        assert retrieved is not None
        assert retrieved.taker_id == "u-bob"
        assert retrieved.base_fee == Decimal("2.00")

    def test_decimal_survives_round_trip(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        it = Item.create("g-1", "X", "Y", "u-1", Decimal("1.99"))
        store.save_item(it)
        # Reload from disk
        store2 = Store(tmp_path / "db.json")
        retrieved = store2.get_item(it.id)
        assert retrieved is not None
        assert retrieved.base_fee == Decimal("1.99")

    def test_datetime_timezone_survives_round_trip(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        item = Item.create("g-1", "X", "Y", "u-alice", Decimal("2.00"))
        m = Movement.create("g-1", "p-1", item, "u-bob")
        store.save_movement(m)
        store2 = Store(tmp_path / "db.json")
        retrieved = store2.get_movement(m.id)
        assert retrieved is not None
        assert retrieved.created_at.tzinfo is not None
        assert retrieved.due_at.tzinfo is not None

    def test_list_movements_filter_by_taker(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        item = Item.create("g-1", "X", "Y", "u-alice", Decimal("2.00"))
        item2 = Item(id="it2", group_id="g-1", name="Y", category="Z", owner_id="u-charlie", base_fee=Decimal("1.00"))
        m1 = Movement.create("g-1", "p-1", item, "u-bob")
        m2 = Movement.create("g-1", "p-1", item2, "u-bob")
        m3 = Movement.create("g-1", "p-1", item, "u-diana")
        # m3: taker=u-diana, owner=u-alice — valid (different)
        store.save_movement(m1)
        store.save_movement(m2)
        store.save_movement(m3)
        bobs = store.list_movements(taker_id="u-bob")
        assert len(bobs) == 2
        assert all(m.taker_id == "u-bob" for m in bobs)

    def test_list_users(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")
        store.save_user(User.create("Alice"))
        store.save_user(User.create("Bob"))
        assert len(store.list_users()) == 2


# ---------------------------------------------------------------------------
# Integration test: full flow take → pay → close
# ---------------------------------------------------------------------------


class TestIntegrationFlow:
    def test_take_pay_close(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")

        # Setup
        alice = User.create("Alice")
        bob = User.create("Bob")
        store.save_user(alice)
        store.save_user(bob)

        group = Group.create("Sorelle", alice.id)
        group.add_member(bob.id)
        store.save_group(group)

        period = Period.create(group.id, 1, start_date=_dt("2026-01-01"))
        store.save_period(period)

        felpa = Item.create(group.id, "Felpa", "Vestiti", alice.id, Decimal("2.00"))
        store.save_item(felpa)

        # Bob takes the felpa
        now_take = _dt("2026-01-10T10:00:00")
        movement = Movement.create(
            group_id=group.id,
            period_id=period.id,
            item=felpa,
            taker_id=bob.id,
            note="per la serata",
            now=now_take,
        )
        store.save_movement(movement)

        # Check due amount within deadline
        within = now_take + timedelta(days=3)
        assert compute_due_amount(movement, now=within) == Decimal("2.00")

        # Bob marks as paid
        paid_movement = movement.mark_paid(now=within)
        store.save_movement(paid_movement)
        assert compute_due_amount(paid_movement, now=within) == Decimal("0.00")

        # Close period
        all_movements = store.list_movements(group_id=group.id, period_id=period.id)
        closed, balances = close_period(
            period=period,
            movements=all_movements,
            requesting_user_id=alice.id,
            group_admin_id=group.admin_id,
        )
        store.save_period(closed)

        assert closed.status == "closed"
        members = balances["members"]
        assert members[alice.id]["credit"] == Decimal("2.00")
        assert members[bob.id]["debit"] == Decimal("2.00")
        assert balances["common_fund_penalties"] == Decimal("0.00")

    def test_overdue_penalty_flow(self, tmp_path: Path) -> None:
        store = Store(tmp_path / "db.json")

        alice = User.create("Alice")
        bob = User.create("Bob")
        store.save_user(alice)
        store.save_user(bob)

        group = Group.create("Sorelle", alice.id)
        group.add_member(bob.id)
        store.save_group(group)

        period = Period.create(group.id, 1, start_date=_dt("2026-01-01"))
        store.save_period(period)

        felpa = Item.create(group.id, "Felpa", "Vestiti", alice.id, Decimal("2.00"))
        store.save_item(felpa)

        now_take = _dt("2026-01-10T10:00:00")
        movement = Movement.create(
            group_id=group.id,
            period_id=period.id,
            item=felpa,
            taker_id=bob.id,
            now=now_take,
        )
        store.save_movement(movement)

        # 8 days later — overdue — still unpaid
        overdue_now = now_take + timedelta(days=8)
        due_amount = compute_due_amount(movement, now=overdue_now)
        assert due_amount == Decimal("7.00")  # 2.00 + 5.00

        # Verify overdue notification
        notifs = overdue_notifications(
            [movement],
            users={alice.id: "Alice", bob.id: "Bob"},
            items={felpa.id: "Felpa"},
            now=overdue_now,
        )
        assert len(notifs) == 1
        assert "Bob" in notifs[0]
        assert "7.00" in notifs[0]

        # Close period with penalty applied
        closed, balances = close_period(
            period=period,
            movements=[movement],
            requesting_user_id=alice.id,
            group_admin_id=group.admin_id,
            now=overdue_now,
        )
        assert balances["common_fund_penalties"] == PENALTY_FEE
