# Vectra-Flow – Piano Beta 2 Settimane

## Obiettivo
Portare `vectra-flow` dallo stato di progetto zero a una **pipeline funzionante** capace di ingerire dati di opportunità, analizzarli con un punteggio composito e produrre un report HTML, il tutto eseguibile sia manualmente che in modo automatico tramite GitHub Actions.

---

## Settimana 1 – Fondamenta del progetto

| Giorno | Task | Stato |
|--------|------|-------|
| 1 | Scaffold struttura pacchetto (`vectra_flow/`, `data/`, `reports/`) | ✅ |
| 1 | Creazione `requirements.txt` con dipendenze minime | ✅ |
| 2 | Implementazione `config.py` (variabili d'ambiente, path default) | ✅ |
| 2 | Implementazione `ingest.py` (lettura CSV con `csv.DictReader`) | ✅ |
| 3 | Implementazione `analyze.py` (scoring composito, filtro, ranking) | ✅ |
| 3 | Implementazione `report.py` (generazione HTML da template) | ✅ |
| 4 | Implementazione `cli.py` (`run` e `version` subcommand) | ✅ |
| 4 | Creazione `data/sample.csv` con 10 opportunità di esempio | ✅ |
| 5 | Creazione workflow `.github/workflows/vectra_flow.yml` | ✅ |
| 5 | Test manuale end-to-end: `python -m vectra_flow.cli run` | ✅ |

---

## Settimana 2 – Qualità, estensibilità e prime automazioni

| Giorno | Task | Stato |
|--------|------|-------|
| 6 | Aggiunta test unitari (`tests/test_ingest.py`, `tests/test_analyze.py`) | ⬜ |
| 6 | Aggiunta test per `report.py` e `cli.py` | ⬜ |
| 7 | Integrazione `flake8` / `ruff` nel workflow CI | ⬜ |
| 8 | Supporto formato output aggiuntivo: CSV (`--format csv`) | ⬜ |
| 8 | Aggiunta campo `tags` al CSV di esempio e all'analisi | ⬜ |
| 9 | Invio report via email o webhook (opzionale, configurabile) | ⬜ |
| 9 | Aggiornamento `README.md` con istruzioni di utilizzo complete | ⬜ |
| 10 | Verifica copertura test ≥ 80% con `pytest-cov` | ⬜ |
| 10 | Tag release `v0.1.0` e pubblicazione su GitHub | ⬜ |

---

## Criteri di Accettazione Beta

- [ ] Il comando `python -m vectra_flow.cli run` completa senza errori su Python 3.12.
- [ ] Il report HTML generato contiene almeno una riga di risultati.
- [ ] Il workflow GitHub Actions esegue la pipeline su ogni push a `main`.
- [ ] La copertura dei test è ≥ 80%.
- [ ] Nessuna dipendenza con vulnerabilità note nel `requirements.txt`.

---

## Note Tecniche

- **Scoring**: `score = (market_size × feasibility) / (1 + competition)` con valori in `[0, 1]`.
- **Soglia default**: `MIN_SCORE = 0.3` (sovrascrivibile con `VECTRA_MIN_SCORE`).
- **Top-N default**: `TOP_N = 10` (sovrascrivibile con `VECTRA_TOP_N`).
- Il workflow giornaliero alle 06:00 UTC garantisce aggiornamenti automatici.
