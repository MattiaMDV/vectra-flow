# vectra-flow
Vectra-Flow è un agente AI di nuova generazione progettato per operare come una "software house" composta da un unico individuo digitale. Il suo obiettivo è individuare, costruire soluzioni software di nicchia senza alcun intervento umano.

## Integrazione con Google Forms / Google Sheets

Vectra-Flow supporta l'aggiornamento automatico dei dati di input tramite un foglio Google (ad es. le risposte di un Google Form), senza alcun intervento manuale.

### Come configurare l'integrazione

1. **Crea un Google Form** con le seguenti domande (usa esattamente questi titoli per evitare il mapping delle colonne):

   | Titolo domanda | Tipo          | Note                         |
   |----------------|---------------|------------------------------|
   | `date`         | Risposta breve | Data del feedback (es. 2026-03-20) |
   | `text`         | Paragrafo      | Testo libero del feedback    |
   | `rating`       | Risposta breve | Numero da 1 a 5              |
   | `product`      | Risposta breve | Nome del prodotto/servizio   |

   > **Alternativa:** puoi usare titoli in italiano (es. "Valutazione") e configurare il mapping delle colonne (vedi sezione sotto).

2. **Collega il form a un foglio Google** (Risposte → icona Fogli Google).
3. **Pubblica il foglio come CSV**: nel foglio vai su *File → Condividi → Pubblica sul web*, seleziona il foglio delle risposte e il formato *Valori separati da virgola (.csv)*, poi clicca *Pubblica*. Copia l'URL generato.
4. **Aggiungi l'URL come segreto GitHub** con nome `SHEET_URL`:  
   *Settings → Secrets and variables → Actions → New repository secret*.
5. *(Opzionale)* Se usi titoli diversi da `date`, `text`, `rating`, `product`, aggiungi anche il segreto `COLUMN_MAP` (vedi sezione sotto).
6. **Fine.** Ad ogni esecuzione pianificata (o manuale) il workflow `vectra_flow.yml` scaricherà automaticamente i dati aggiornati dal foglio, eseguirà l'analisi e pubblicherà il report su GitHub Pages.

> **Nota:** se `SHEET_URL` non è configurato, il passo di fetch viene saltato silenziosamente e vengono utilizzati i file CSV presenti nella cartella `data/`.

---

### Mapping delle colonne (titoli personalizzati)

Google Forms esporta le risposte usando il **testo della domanda** come nome della colonna, e aggiunge automaticamente la colonna `Timestamp`. Se i tuoi titoli di domanda sono diversi dai nomi richiesti, configura il mapping tramite il segreto `COLUMN_MAP` (un oggetto JSON):

```json
{
  "Timestamp":           "date",
  "Il tuo feedback":     "text",
  "Valutazione (1-5)":   "rating",
  "Prodotto":            "product"
}
```

Aggiungi questo JSON come segreto GitHub con nome `COLUMN_MAP`.

#### Esempio di export reale

Il file [`data/google_form_example.csv`](data/google_form_example.csv) mostra come appare il CSV esportato da un Google Form con titoli italiani. Per usarlo:

```bash
vectra-flow \
  --sheet-url "https://docs.google.com/..." \
  --column-map '{"Timestamp":"date","Il tuo feedback":"text","Valutazione (1-5)":"rating","Prodotto":"product"}'
```

---

### Utilizzo locale con `--sheet-url`

```bash
# Colonne già nominate correttamente
vectra-flow --sheet-url "https://docs.google.com/spreadsheets/d/ID/pub?output=csv"

# Con mapping delle colonne
vectra-flow \
  --sheet-url "https://docs.google.com/spreadsheets/d/ID/pub?output=csv" \
  --column-map '{"Timestamp":"date","Feedback":"text","Score":"rating","Product":"product"}'
```

Il file viene scaricato in `data/sheet.csv` (con il mapping applicato, se specificato) e incluso automaticamente nell'analisi.

