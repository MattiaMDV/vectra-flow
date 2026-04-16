"""CLI entry point for RisolvoProb.

Commands
--------
    risolvo-prob user add    --name <name>
    risolvo-prob user list

    risolvo-prob group create  --name <name> --admin <user-id>
    risolvo-prob group show    --id <group-id>
    risolvo-prob group members --id <group-id>
    risolvo-prob group add-member --id <group-id> --user-id <user-id>

    risolvo-prob period start  --group-id <id> --duration <1|2|3|6>
    risolvo-prob period show   --group-id <id>

    risolvo-prob item add   --group-id <id> --name <name> --category <cat>
                            --owner <user-id> --fee <amount>
    risolvo-prob item list  --group-id <id>
    risolvo-prob item edit  --id <item-id> --fee <amount>

    risolvo-prob take  --group-id <id> --item-id <id> --taker <user-id>
                       [--note <text>]

    risolvo-prob pay  --movement-id <id>

    risolvo-prob due  --group-id <id> --user-id <user-id>

    risolvo-prob balances --group-id <id>

    risolvo-prob close  --group-id <id> --admin <user-id>

    risolvo-prob notifications --group-id <id>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .domain import apply_pending_penalties, close_period, compute_balances, compute_due_amount
from .models import Group, Item, Movement, Period, User, VALID_DURATIONS
from .notifications import overdue_notifications, reminder_notifications
from .store import Store, _DEFAULT_PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(args: argparse.Namespace) -> Store:
    db_path = Path(getattr(args, "db", None) or _DEFAULT_PATH)
    return Store(db_path)


def _require(obj: object | None, name: str) -> object:
    if obj is None:
        print(f"Error: {name} not found.", file=sys.stderr)
        sys.exit(1)
    return obj


def _parse_decimal(value: str, name: str = "value") -> Decimal:
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation:
        print(f"Error: {name} must be a valid decimal number (e.g. 2.50).", file=sys.stderr)
        sys.exit(1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_map(store: Store) -> dict[str, str]:
    return {u.id: u.name for u in store.list_users()}


def _item_map(store: Store) -> dict[str, str]:
    return {it.id: it.name for it in store.list_items()}


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _cmd_user_add(args: argparse.Namespace) -> int:
    store = _store(args)
    user = User.create(args.name)
    store.save_user(user)
    print(f"Utente creato: {user.name}  (id: {user.id})")
    return 0


def _cmd_user_list(args: argparse.Namespace) -> int:
    store = _store(args)
    users = store.list_users()
    if not users:
        print("Nessun utente registrato.")
        return 0
    for u in users:
        print(f"  {u.id}  {u.name}")
    return 0


def _cmd_group_create(args: argparse.Namespace) -> int:
    store = _store(args)
    admin = _require(store.get_user(args.admin), f"Utente admin '{args.admin}'")
    assert isinstance(admin, User)
    group = Group.create(args.name, admin.id)
    store.save_group(group)
    print(f"Gruppo creato: '{group.name}'  (id: {group.id})")
    print(f"  Admin: {admin.name}")
    return 0


def _cmd_group_show(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.id), f"Gruppo '{args.id}'")
    assert isinstance(group, Group)
    users = _user_map(store)
    print(f"Gruppo: {group.name}  (id: {group.id})")
    print(f"  Admin: {users.get(group.admin_id, group.admin_id)}")
    print(f"  Membri: {', '.join(users.get(uid, uid) for uid in group.member_ids)}")
    active = store.get_active_period(group.id)
    if active:
        now = _now()
        print(
            f"  Periodo attivo: {active.start_date.date()} → {active.end_date.date()} "
            f"({active.days_remaining(now)} giorni rimanenti)"
        )
    else:
        print("  Nessun periodo attivo.")
    return 0


def _cmd_group_members(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.id), f"Gruppo '{args.id}'")
    assert isinstance(group, Group)
    users = _user_map(store)
    print(f"Membri di '{group.name}':")
    for uid in group.member_ids:
        role = " [admin]" if uid == group.admin_id else ""
        print(f"  {uid}  {users.get(uid, uid)}{role}")
    return 0


def _cmd_group_add_member(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.id), f"Gruppo '{args.id}'")
    user = _require(store.get_user(args.user_id), f"Utente '{args.user_id}'")
    assert isinstance(group, Group)
    assert isinstance(user, User)
    if group.has_member(user.id):
        print(f"{user.name} è già membro del gruppo.")
        return 0
    group.add_member(user.id)
    store.save_group(group)
    print(f"{user.name} aggiunto al gruppo '{group.name}'.")
    return 0


def _cmd_period_start(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    existing = store.get_active_period(group.id)
    if existing:
        print(
            f"Errore: esiste già un periodo attivo per questo gruppo "
            f"(id: {existing.id}, scade: {existing.end_date.date()}).",
            file=sys.stderr,
        )
        return 1
    duration = args.duration
    if duration not in VALID_DURATIONS:
        print(f"Errore: durata deve essere una di {VALID_DURATIONS}.", file=sys.stderr)
        return 1
    period = Period.create(group.id, duration)
    store.save_period(period)
    print(
        f"Periodo avviato: {period.start_date.date()} → {period.end_date.date()} "
        f"({duration} mese/i)  id: {period.id}"
    )
    return 0


def _cmd_period_show(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    period = store.get_active_period(group.id)
    if not period:
        print("Nessun periodo attivo per questo gruppo.")
        return 0
    now = _now()
    print(f"Periodo attivo ({group.name}):")
    print(f"  Inizio  : {period.start_date.date()}")
    print(f"  Fine    : {period.end_date.date()}")
    print(f"  Durata  : {period.duration_months} mese/i")
    print(f"  Rimasti : {period.days_remaining(now)} giorni")
    return 0


def _cmd_item_add(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    owner = _require(store.get_user(args.owner), f"Utente owner '{args.owner}'")
    assert isinstance(owner, User)
    if not group.has_member(owner.id):
        print(f"Errore: {owner.name} non è membro del gruppo.", file=sys.stderr)
        return 1
    fee = _parse_decimal(args.fee, "--fee")
    item = Item.create(
        group_id=group.id,
        name=args.name,
        category=args.category,
        owner_id=owner.id,
        base_fee=fee,
    )
    store.save_item(item)
    print(f"Articolo aggiunto: '{item.name}' ({item.category})")
    print(f"  Proprietario: {owner.name}  Quota: {item.base_fee:.2f} €  id: {item.id}")
    return 0


def _cmd_item_list(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    items = store.list_items(group_id=group.id)
    if not items:
        print("Nessun articolo registrato per questo gruppo.")
        return 0
    users = _user_map(store)
    print(f"Articoli del gruppo '{group.name}':")
    for it in items:
        owner_name = users.get(it.owner_id, it.owner_id)
        print(
            f"  [{it.category}] {it.name}  —  quota {it.base_fee:.2f} €  "
            f"(proprietario: {owner_name})  id: {it.id}"
        )
    return 0


def _cmd_item_edit(args: argparse.Namespace) -> int:
    store = _store(args)
    item = _require(store.get_item(args.id), f"Articolo '{args.id}'")
    assert isinstance(item, Item)
    fee = _parse_decimal(args.fee, "--fee")
    updated = Item(
        id=item.id,
        group_id=item.group_id,
        name=item.name,
        category=item.category,
        owner_id=item.owner_id,
        base_fee=fee,
    )
    store.save_item(updated)
    print(f"Quota di '{item.name}' aggiornata a {fee:.2f} €.")
    return 0


def _cmd_take(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    item = _require(store.get_item(args.item_id), f"Articolo '{args.item_id}'")
    assert isinstance(item, Item)
    taker = _require(store.get_user(args.taker), f"Utente taker '{args.taker}'")
    assert isinstance(taker, User)
    if not group.has_member(taker.id):
        print(f"Errore: {taker.name} non è membro del gruppo.", file=sys.stderr)
        return 1
    period = store.get_active_period(group.id)
    if not period:
        print("Errore: nessun periodo attivo per questo gruppo.", file=sys.stderr)
        return 1
    note = getattr(args, "note", "") or ""
    try:
        movement = Movement.create(
            group_id=group.id,
            period_id=period.id,
            item=item,
            taker_id=taker.id,
            note=note,
        )
    except ValueError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    store.save_movement(movement)
    print(f"Presa registrata: {taker.name} ha preso '{item.name}'")
    print(f"  Quota: {movement.base_fee:.2f} €  —  Scadenza pagamento: {movement.due_at.date()}")
    print(f"  Movimento id: {movement.id}")
    return 0


def _cmd_pay(args: argparse.Namespace) -> int:
    store = _store(args)
    movement = _require(store.get_movement(args.movement_id), f"Movimento '{args.movement_id}'")
    assert isinstance(movement, Movement)
    if movement.is_paid:
        print("Questo movimento è già stato pagato.")
        return 0
    updated = movement.mark_paid()
    store.save_movement(updated)
    users = _user_map(store)
    items = _item_map(store)
    taker = users.get(movement.taker_id, movement.taker_id)
    item_name = items.get(movement.item_id, movement.item_id)
    print(f"✅  Pagamento registrato: {taker} ha versato per '{item_name}'.")
    return 0


def _cmd_due(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    taker = _require(store.get_user(args.user_id), f"Utente '{args.user_id}'")
    assert isinstance(taker, User)
    period = store.get_active_period(group.id)
    if not period:
        print("Nessun periodo attivo per questo gruppo.")
        return 0
    movements = store.list_movements(group_id=group.id, period_id=period.id, taker_id=taker.id)
    unpaid = [m for m in movements if not m.is_paid]
    if not unpaid:
        print(f"{taker.name} non ha movimenti in sospeso. 🎉")
        return 0
    now = _now()
    items = _item_map(store)
    print(f"Movimenti da versare — {taker.name}:")
    total = Decimal("0.00")
    for m in unpaid:
        item_name = items.get(m.item_id, m.item_id)
        due_amount = compute_due_amount(m, now=now)
        overdue = now > m.due_at
        status = "⚠️  SCADUTO" if overdue else f"scade {m.due_at.date()}"
        penalty_note = f"  (quota {m.base_fee:.2f} € + multa 5.00 €)" if overdue else ""
        print(f"  [{m.id[:8]}…] '{item_name}'  {due_amount:.2f} €  {status}{penalty_note}")
        total += due_amount
    print(f"  ─────────────────────────────────")
    print(f"  Totale da versare: {total:.2f} €")
    return 0


def _cmd_balances(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    period = store.get_active_period(group.id)
    if not period:
        # Fall back to the most recent closed period.
        periods = sorted(
            store.list_periods(group_id=group.id),
            key=lambda p: p.end_date,
            reverse=True,
        )
        period = periods[0] if periods else None
    if not period:
        print("Nessun periodo trovato per questo gruppo.")
        return 0
    movements = store.list_movements(group_id=group.id, period_id=period.id)
    now = _now()
    penalised = apply_pending_penalties(movements, now=now)
    report = compute_balances(penalised)
    users = _user_map(store)
    print(f"Saldi periodo: {period.start_date.date()} → {period.end_date.date()}")
    print(f"  Stato: {period.status.upper()}")
    print()
    members: dict = report["members"]
    if not members:
        print("  Nessun movimento registrato.")
    else:
        print(f"  {'Membro':<20} {'Credito':>10} {'Debito':>10} {'Netto':>10}")
        print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10}")
        for uid, bal in members.items():
            name = users.get(uid, uid)
            credit = bal["credit"]
            debit = bal["debit"]
            net = bal["net"]
            sign = "+" if net >= 0 else ""
            print(f"  {name:<20} {credit:>9.2f}€ {debit:>9.2f}€ {sign}{net:>8.2f}€")
    print()
    print(f"  Salvadanaio multe comune: {report['common_fund_penalties']:.2f} €")
    return 0


def _cmd_close(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    admin_user = _require(store.get_user(args.admin), f"Utente admin '{args.admin}'")
    assert isinstance(admin_user, User)
    period = store.get_active_period(group.id)
    if not period:
        print("Errore: nessun periodo attivo da chiudere.", file=sys.stderr)
        return 1
    movements = store.list_movements(group_id=group.id, period_id=period.id)
    try:
        closed_period, balances = close_period(
            period=period,
            movements=movements,
            requesting_user_id=admin_user.id,
            group_admin_id=group.admin_id,
        )
    except PermissionError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1

    # Persist closed period and any newly penalised movements.
    store.save_period(closed_period)
    # Re-fetch movements after penalties applied inside close_period.
    penalised_movements = apply_pending_penalties(movements)
    for m in penalised_movements:
        store.save_movement(m)

    print(f"✅  Periodo chiuso: {closed_period.start_date.date()} → {closed_period.end_date.date()}")
    print()
    users = _user_map(store)
    members: dict = balances["members"]
    print(f"  {'Membro':<20} {'Credito':>10} {'Debito':>10} {'Netto':>10}")
    print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10}")
    for uid, bal in members.items():
        name = users.get(uid, uid)
        credit = bal["credit"]
        debit = bal["debit"]
        net = bal["net"]
        sign = "+" if net >= 0 else ""
        print(f"  {name:<20} {credit:>9.2f}€ {debit:>9.2f}€ {sign}{net:>8.2f}€")
    print()
    print(f"  Salvadanaio multe comune: {balances['common_fund_penalties']:.2f} €")
    return 0


def _cmd_notifications(args: argparse.Namespace) -> int:
    store = _store(args)
    group = _require(store.get_group(args.group_id), f"Gruppo '{args.group_id}'")
    assert isinstance(group, Group)
    period = store.get_active_period(group.id)
    if not period:
        print("Nessun periodo attivo — nessuna notifica da mostrare.")
        return 0
    movements = store.list_movements(group_id=group.id, period_id=period.id)
    now = _now()
    users = _user_map(store)
    items = _item_map(store)
    overdue = overdue_notifications(movements, users=users, items=items, now=now)
    reminders = reminder_notifications(movements, users=users, items=items, now=now)
    if not overdue and not reminders:
        print("Nessuna notifica attiva. ✅")
        return 0
    for msg in overdue:
        print(msg)
    for msg in reminders:
        print(msg)
    return 0


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="risolvo-prob",
        description="RisolvoProb — risolvi i conflitti sugli articoli condivisi tra amici/fratelli.",
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_PATH),
        metavar="PATH",
        help=f"Percorso del database JSON (default: {_DEFAULT_PATH}).",
    )

    sub = parser.add_subparsers(dest="entity", metavar="<entità>")
    sub.required = True

    # ------------------------------------------------------------------
    # user
    # ------------------------------------------------------------------
    user_p = sub.add_parser("user", help="Gestione utenti")
    user_sub = user_p.add_subparsers(dest="action", metavar="<azione>")
    user_sub.required = True

    u_add = user_sub.add_parser("add", help="Aggiungi un utente")
    u_add.add_argument("--name", required=True, help="Nome dell'utente")
    u_add.set_defaults(func=_cmd_user_add)

    u_list = user_sub.add_parser("list", help="Elenca gli utenti")
    u_list.set_defaults(func=_cmd_user_list)

    # ------------------------------------------------------------------
    # group
    # ------------------------------------------------------------------
    group_p = sub.add_parser("group", help="Gestione gruppi")
    group_sub = group_p.add_subparsers(dest="action", metavar="<azione>")
    group_sub.required = True

    g_create = group_sub.add_parser("create", help="Crea un gruppo")
    g_create.add_argument("--name", required=True)
    g_create.add_argument("--admin", required=True, metavar="USER-ID")
    g_create.set_defaults(func=_cmd_group_create)

    g_show = group_sub.add_parser("show", help="Mostra dettagli gruppo")
    g_show.add_argument("--id", required=True, metavar="GROUP-ID")
    g_show.set_defaults(func=_cmd_group_show)

    g_members = group_sub.add_parser("members", help="Elenca i membri")
    g_members.add_argument("--id", required=True, metavar="GROUP-ID")
    g_members.set_defaults(func=_cmd_group_members)

    g_addmember = group_sub.add_parser("add-member", help="Aggiungi un membro al gruppo")
    g_addmember.add_argument("--id", required=True, metavar="GROUP-ID")
    g_addmember.add_argument("--user-id", required=True, metavar="USER-ID")
    g_addmember.set_defaults(func=_cmd_group_add_member)

    # ------------------------------------------------------------------
    # period
    # ------------------------------------------------------------------
    period_p = sub.add_parser("period", help="Gestione periodi")
    period_sub = period_p.add_subparsers(dest="action", metavar="<azione>")
    period_sub.required = True

    p_start = period_sub.add_parser("start", help="Avvia un nuovo periodo")
    p_start.add_argument("--group-id", required=True, metavar="GROUP-ID")
    p_start.add_argument("--duration", required=True, type=int, choices=VALID_DURATIONS,
                         metavar="MESI", help="Durata in mesi (1, 2, 3 o 6)")
    p_start.set_defaults(func=_cmd_period_start)

    p_show = period_sub.add_parser("show", help="Mostra il periodo attivo")
    p_show.add_argument("--group-id", required=True, metavar="GROUP-ID")
    p_show.set_defaults(func=_cmd_period_show)

    # ------------------------------------------------------------------
    # item
    # ------------------------------------------------------------------
    item_p = sub.add_parser("item", help="Gestione articoli condivisi")
    item_sub = item_p.add_subparsers(dest="action", metavar="<azione>")
    item_sub.required = True

    i_add = item_sub.add_parser("add", help="Aggiungi un articolo")
    i_add.add_argument("--group-id", required=True, metavar="GROUP-ID")
    i_add.add_argument("--name", required=True)
    i_add.add_argument("--category", required=True)
    i_add.add_argument("--owner", required=True, metavar="USER-ID")
    i_add.add_argument("--fee", required=True, metavar="EURO")
    i_add.set_defaults(func=_cmd_item_add)

    i_list = item_sub.add_parser("list", help="Elenca gli articoli del gruppo")
    i_list.add_argument("--group-id", required=True, metavar="GROUP-ID")
    i_list.set_defaults(func=_cmd_item_list)

    i_edit = item_sub.add_parser("edit", help="Modifica la quota di un articolo")
    i_edit.add_argument("--id", required=True, metavar="ITEM-ID")
    i_edit.add_argument("--fee", required=True, metavar="EURO")
    i_edit.set_defaults(func=_cmd_item_edit)

    # ------------------------------------------------------------------
    # take
    # ------------------------------------------------------------------
    take_p = sub.add_parser("take", help="Registra una presa")
    take_p.add_argument("--group-id", required=True, metavar="GROUP-ID")
    take_p.add_argument("--item-id", required=True, metavar="ITEM-ID")
    take_p.add_argument("--taker", required=True, metavar="USER-ID")
    take_p.add_argument("--note", default="", metavar="TESTO")
    take_p.set_defaults(func=_cmd_take)

    # ------------------------------------------------------------------
    # pay
    # ------------------------------------------------------------------
    pay_p = sub.add_parser("pay", help="Registra un versamento ('Ho versato')")
    pay_p.add_argument("--movement-id", required=True, metavar="MOVEMENT-ID")
    pay_p.set_defaults(func=_cmd_pay)

    # ------------------------------------------------------------------
    # due
    # ------------------------------------------------------------------
    due_p = sub.add_parser("due", help="Mostra movimenti da versare per un utente")
    due_p.add_argument("--group-id", required=True, metavar="GROUP-ID")
    due_p.add_argument("--user-id", required=True, metavar="USER-ID")
    due_p.set_defaults(func=_cmd_due)

    # ------------------------------------------------------------------
    # balances
    # ------------------------------------------------------------------
    bal_p = sub.add_parser("balances", help="Mostra saldi e ripartizione")
    bal_p.add_argument("--group-id", required=True, metavar="GROUP-ID")
    bal_p.set_defaults(func=_cmd_balances)

    # ------------------------------------------------------------------
    # close
    # ------------------------------------------------------------------
    close_p = sub.add_parser("close", help="Chiudi il periodo attivo (solo admin)")
    close_p.add_argument("--group-id", required=True, metavar="GROUP-ID")
    close_p.add_argument("--admin", required=True, metavar="USER-ID")
    close_p.set_defaults(func=_cmd_close)

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    notif_p = sub.add_parser("notifications", help="Mostra notifiche e reminder")
    notif_p.add_argument("--group-id", required=True, metavar="GROUP-ID")
    notif_p.set_defaults(func=_cmd_notifications)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
