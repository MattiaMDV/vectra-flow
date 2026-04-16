# RisolvoProb

**RisolvoProb** risolve i conflitti sugli articoli condivisi tra amici e fratelli.

Quando qualcuno prende un articolo altrui (felpa, cintura, occhiali…) deve versare
una quota fissa nel "salvadanaio" del proprietario.
Se non paga entro 7 giorni, scatta una multa di 5 €.
A fine periodo l'app mostra chi deve quanto a chi.

---

## Setup

```bash
pip install -e .
```

---

## Modello di calcolo

### Movimento

| Campo            | Descrizione                                         |
|------------------|-----------------------------------------------------|
| `taker_id`       | Chi prende l'articolo                               |
| `owner_id`       | Proprietario dell'articolo                          |
| `item_id`        | Articolo preso                                      |
| `base_fee`       | Quota fissa (es. 2.00 €)                            |
| `created_at`     | Data/ora della presa                                |
| `due_at`         | `created_at` + 7 giorni                             |
| `paid_at`        | Data di pagamento (null = non pagato)               |
| `penalty_applied`| True se la multa è già stata registrata             |
| `penalty_fee`    | Importo multa (5.00 €)                              |

### Importo dovuto

```
se paid_at != null → 0 €
se now <= due_at   → base_fee
se now > due_at    → base_fee + 5.00 €
```

### Ripartizione di fine periodo

Per ogni persona P:

```
credit(P) = Σ base_fee  dove owner_id == P
debit(P)  = Σ base_fee  dove taker_id == P
net(P)    = credit(P) - debit(P)
```

Le multe **non** aumentano il credito di nessun proprietario:
vanno nel *salvadanaio comune* (dato informativo separato).

---

## Comandi CLI

### Utenti

```bash
risolvo-prob user add   --name "Alice"
risolvo-prob user list
```

### Gruppi

```bash
risolvo-prob group create     --name "Sorelle" --admin <user-id>
risolvo-prob group show       --id <group-id>
risolvo-prob group members    --id <group-id>
risolvo-prob group add-member --id <group-id> --user-id <user-id>
```

### Periodi

Durate disponibili: **1, 2, 3, 6** mesi.

```bash
risolvo-prob period start --group-id <id> --duration 1
risolvo-prob period show  --group-id <id>
```

### Articoli

```bash
risolvo-prob item add  --group-id <id> \
                       --name "Felpa" \
                       --category "Vestiti" \
                       --owner <user-id> \
                       --fee 2.00

risolvo-prob item list --group-id <id>
risolvo-prob item edit --id <item-id> --fee 1.50
```

### Registra una presa

```bash
risolvo-prob take --group-id <id> \
                  --item-id  <id> \
                  --taker    <user-id> \
                  --note     "per la festa"   # opzionale
```

### Pagamento ("Ho versato")

```bash
risolvo-prob pay --movement-id <id>
```

### Movimenti da versare

```bash
risolvo-prob due --group-id <id> --user-id <user-id>
```

### Saldi e ripartizione

```bash
risolvo-prob balances --group-id <id>
```

### Chiudi il periodo (solo admin)

```bash
risolvo-prob close --group-id <id> --admin <user-id>
```

### Notifiche e reminder

```bash
risolvo-prob notifications --group-id <id>
```

---

## Opzioni globali

| Opzione | Default                      | Descrizione              |
|---------|------------------------------|--------------------------|
| `--db`  | `data/risolvo_prob/db.json`  | Percorso del database JSON |

---

## Esempio completo

```bash
# 1. Crea utenti
risolvo-prob user add --name "Alice"    # → id: <alice-id>
risolvo-prob user add --name "Beatrice" # → id: <bea-id>

# 2. Crea gruppo
risolvo-prob group create --name "Sorelle" --admin <alice-id>
risolvo-prob group add-member --id <group-id> --user-id <bea-id>

# 3. Avvia periodo di 1 mese
risolvo-prob period start --group-id <group-id> --duration 1

# 4. Aggiungi articoli
risolvo-prob item add --group-id <group-id> \
  --name "Jeans blu" --category "Vestiti" --owner <alice-id> --fee 2.00

# 5. Beatrice prende i jeans
risolvo-prob take --group-id <group-id> \
  --item-id <item-id> --taker <bea-id>

# 6. Beatrice paga
risolvo-prob pay --movement-id <movement-id>

# 7. Visualizza saldi
risolvo-prob balances --group-id <group-id>

# 8. Chiudi il periodo
risolvo-prob close --group-id <group-id> --admin <alice-id>
```

---

## Struttura del modulo

```
vectra_flow/risolvo_prob/
├── __init__.py        — API pubblica
├── models.py          — Entità dominio (User, Group, Period, Item, Movement)
├── domain.py          — Regole applicative (calcolo importo, penali, ripartizione)
├── store.py           — Persistenza JSON
├── notifications.py   — Notifiche e reminder
└── cli.py             — Entrypoint CLI (risolvo-prob)
```

---

## Test

```bash
pytest tests/test_risolvo_prob.py -v
```
