# TODO — Database persistente online (Supabase, DB condiviso con colonna `sport`)

**Stato:** 🔲 Da fare (rimandato — deciso il 02/11/2026)
**Obiettivo:** rendere persistente lo storico predizioni/risultati/ROI anche sulle app online.
Oggi su Streamlit Cloud il DB SQLite si azzera a ogni riavvio → lo storico vive solo in locale.

---

## Decisione presa

- **Provider:** Supabase (Postgres gestito, free tier permanente ~500 MB).
- **Architettura:** **UN SOLO database condiviso** tra le 4 app (1 progetto Supabase, sta nel free tier).
  - Motivo: "un DB per app" richiederebbe 4 progetti Supabase, ma il free tier ne regge ~2 → scomodo.
  - Il DB unico è anche più elegante: 1 connection string, 1 pannello, e il betting-agent
    potrebbe leggere direttamente dal DB invece di interrogare 4 API.
- **Distinzione sport:** aggiungere una colonna **`sport`** a tutte le tabelle; ogni query filtra
  `WHERE sport = <nome>` così un campionato non legge i dati di un altro.

---

## Piano di implementazione

### 1. Setup Supabase (lato utente)
- [ ] Creare account Supabase gratuito (login GitHub, come Streamlit)
- [ ] Creare 1 progetto → ottenere la **connection string** Postgres (`DATABASE_URL`)
- [ ] NON mettere la stringa in chiaro nel repo: va nei Secrets Streamlit + `.env` locale

### 2. Refactor `betting-core/betting_core/storage.py` (lato codice)
- [ ] Portare da `sqlite3` a **SQLAlchemy** (già nei requirements dei predictor)
- [ ] Backend selezionabile da env:
      - se `DATABASE_URL` presente → Postgres (Supabase)
      - altrimenti → SQLite locale (fallback, sviluppo offline)
- [ ] Aggiungere colonna `sport` a: `predictions`, `strategia_mista`, `odds_cache`
- [ ] Aggiungere il filtro `sport` a TUTTE le funzioni di lettura:
      `get_all_predictions`, `get_pending_predictions`, `get_roi_stats`,
      `get_strategia_mista`, `get_roi_strategia`, `load_odds_cache`
- [ ] Passare `cfg.name` come valore di `sport` nelle funzioni di scrittura
      (`save_prediction`, `save_strategia_mista`, `save_odds_cache`)
- [ ] `init_db`: creare le tabelle con schema compatibile Postgres+SQLite
      (attenzione a `AUTOINCREMENT` SQLite vs `SERIAL`/IDENTITY Postgres → usare SQLAlchemy)

### 3. Config
- [ ] Aggiungere `database_url` a `PredictorConfig` (da env `DATABASE_URL`, default "" = SQLite)

### 4. Test (critico — storage.py è usato da TUTTE le app + agent)
- [ ] Test locale con SQLite (comportamento invariato, nessuna regressione)
- [ ] Test locale puntando a Supabase (scrittura/lettura con filtro sport)
- [ ] Verificare isolamento: Serie A non vede le righe di Serie B
- [ ] Verificare che il betting-agent continui a funzionare

### 5. Deploy
- [ ] Mettere `DATABASE_URL` nei Secrets delle 4 app Streamlit
- [ ] Ripushare betting-core (le app lo tirano da git)
- [ ] Verificare che lo storico PERSISTA tra due riavvii dell'app online

### 6. Documentazione
- [ ] Aggiornare `GUIDA_APP_PREDICTOR.md`: rimuovere l'avvertenza "storico solo in locale"
      (una volta che online persiste)
- [ ] Aggiornare `docs/deploy_streamlit.md` con il setup del DATABASE_URL

---

## Rischi / note

- **Regressione:** `storage.py` è condiviso da 4 app + agent. Il refactor va testato su entrambi
  i backend prima di pushare. È il rischio maggiore, non il costo (che è 0 €).
- **Sleep del free tier:** i Postgres gratuiti vanno in sleep dopo inattività prolungata
  (Supabase ~1 settimana) con wake-up di qualche secondo. Accettabile per uso personale.
- **Migrazione dati esistenti:** lo storico locale attuale (SQLite) NON viene migrato in automatico.
  Se si vuole conservarlo, prevedere uno script di import una-tantum (opzionale).
- **Effort stimato:** medio (~mezza giornata: refactor mirato + test su 2 backend + deploy).
- **Vantaggio collaterale:** con il DB condiviso, il betting-agent potrà leggere ROI/segnali
  direttamente dal DB invece che via le 4 API — semplificazione futura.
