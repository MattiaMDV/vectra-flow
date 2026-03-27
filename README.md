# vectra-flow
Vectra-Flow è un agente AI di nuova generazione progettato per operare come una "software house" composta da un unico individuo digitale. Il suo obiettivo è individuare, costruire soluzioni software di nicchia senza alcun intervento umano.

## Integrazione con Google Forms / Google Sheets

Vectra-Flow supporta l'aggiornamento automatico dei dati di input tramite un foglio Google (ad es. le risposte di un Google Form), senza alcun intervento manuale.

### Come configurare l'integrazione

1. **Crea un Google Form** con i campi: `date`, `text`, `rating`, `product`.
2. **Collega il form a un foglio Google** (Risposte → icona Fogli Google).
3. **Pubblica il foglio come CSV**: nel foglio vai su *File → Condividi → Pubblica sul web*, seleziona il foglio delle risposte e il formato *Valori separati da virgola (.csv)*, poi clicca *Pubblica*. Copia l'URL generato.
4. **Aggiungi l'URL come segreto GitHub** con nome `SHEET_URL`:  
   *Settings → Secrets and variables → Actions → New repository secret*.
5. **Fine.** Ad ogni esecuzione pianificata (o manuale) il workflow `vectra_flow.yml` scaricherà automaticamente i dati aggiornati dal foglio, eseguirà l'analisi e pubblicherà il report su GitHub Pages.

> **Nota:** se `SHEET_URL` non è configurato, il passo di fetch viene saltato silenziosamente e vengono utilizzati i file CSV presenti nella cartella `data/`.

### Utilizzo locale con `--sheet-url`

```bash
vectra-flow --sheet-url "https://docs.google.com/spreadsheets/d/ID/pub?output=csv"
```

Il file viene scaricato in `data/sheet.csv` e incluso automaticamente nell'analisi.

