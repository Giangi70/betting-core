# Betting Ecosystem — Visione e Piano di Implementazione

Data concezione: 22/05/2026

---

## L'idea

Partendo dal progetto `seriea-predictor`, vogliamo costruire un ecosistema di predizione
sportiva multi-sport, dove ogni sport ha il suo modello dedicato e un agente centrale
aggrega i segnali per suggerire le scommesse con il miglior rapporto rischio/rendimento.

---

## Motivazione

### Perché multi-sport?
- Diversificazione: scommesse su sport diversi non sono correlate → riduce la varianza
  del portafoglio complessivo (principio del Kelly frazionato multi-asset)
- Edge diverso per sport: mercati di nicchia (Serie B, pallavolo) hanno bookmaker meno
  precisi → più inefficienze da sfruttare
- Stagioni "calde" non coincidono: quando la Serie A è efficiente, la Serie B potrebbe
  non esserlo, e viceversa

### Perché un agente centrale?
- Evita di guardare 3 app separate
- Normalizza il ROI atteso cross-sport
- Alloca il budget in modo ottimale (Kelly multi-sport)
- Un solo punto di decisione: "cosa scommetto questa settimana?"

---

## I tre predictor

### 1. seriea-predictor (esistente)
- **Repo**: https://github.com/Giangi70/seriea-predictor
- **Dati storici**: football-data.co.uk, file `I1.csv`, 9 stagioni (1617→2425)
- **Quote live**: The Odds API, endpoint `soccer_italy_serie_a`
- **Modello**: XGBoost, 3 esiti (H/D/A), CV accuracy ~51%
- **Strategia mista**: 9-safe + 1-jolly, filtro gap prob ≥ 15%, monitor ROI stagionale
- **Stato**: ✅ Completo e in produzione

### 2. serieb-predictor (da costruire)
- **Repo**: da creare su GitHub (Giangi70/serieb-predictor)
- **Directory**: `/home/egiabot/PROJECT/serieb-predictor`
- **Dati storici**: football-data.co.uk, file `I2.csv`, 9 stagioni disponibili (1617→2425)
- **Quote live**: The Odds API, endpoint `soccer_italy_serie_b`
- **Modello**: identico alla Serie A (stesso preprocessing, stesso XGBoost)
- **Motivazione edge**: mercato meno seguito → bookmaker meno precisi rispetto alla A
- **Stato**: 🔲 Da costruire — clone quasi identico di seriea-predictor
- **Effort stimato**: basso (2 parametri diversi: I2 invece di I1, endpoint API diverso)

### 3. volley-predictor (da costruire)
- **Repo**: da creare su GitHub (Giangi70/volley-predictor)
- **Directory**: `/home/egiabot/PROJECT/volley-predictor`
- **Sport**: Pallavolo Serie A1 italiana
- **Dati storici**: scraping da oddsportal.com o betexplorer.com (no fonte diretta disponibile)
- **Quote live**: da valutare (The Odds API non copre pallavolo italiana)
- **Modello**: binario (1/2, no pareggio) → problema più semplice del calcio
- **Motivazione edge**: nicchia, pochi scommettitori, bookmaker meno raffinati,
  struttura a set crea varianza che i modelli semplici faticano a catturare
- **Stato**: 🔲 Da costruire — richiede scraping, più complesso
- **Effort stimato**: alto (scraping + pulizia dati + nuovo modello)

---

## Il layer API (da aggiungere a tutti e 3)

Ogni predictor espone una REST API leggera (FastAPI) che il betting-agent può interrogare.

### Endpoint standard (identici per tutti e 3)

```
GET /predictions
  → predizioni giornata corrente
  → { home, away, prediction, prob_H, prob_D, prob_A, confidence }

GET /signals
  → segnali strategia mista (safe + jolly)
  → { tipo: "safe"|"jolly", home, away, esito, quota, prob_gap, match_date }

GET /roi
  → ROI stagionale corrente
  → { roi: float, n_scommesse: int, pl: float, stagione_calda: bool }

GET /health
  → stato del servizio
  → { status: "ok", model_loaded: bool, last_update: str }
```

### Stack
- **FastAPI** + **uvicorn**
- Ogni predictor gira su una porta diversa (es. 8001, 8002, 8003)
- Autenticazione: API key semplice in header (condivisa con il betting-agent)

---

## Il betting-agent (da costruire)

### Directory: `/home/egiabot/PROJECT/betting-agent`
### Repo: da creare su GitHub (Giangi70/betting-agent)

### Cosa fa
1. Interroga i 3 predictor via API (`/signals` e `/roi`)
2. Normalizza il ROI atteso per sport (pesi calibrati sui backtest storici)
3. Rankinga tutte le scommesse disponibili per Expected Value (EV)
4. Alloca il budget con Kelly criterion multi-sport
5. Genera il report settimanale: "cosa scommettere questa settimana"
6. Avvisa se uno sport è in "stagione calda" → aumenta il peso di quel predictor

### Logica di ranking
```
EV = prob_stimata × quota - 1
Score = EV × peso_sport × (1 + bonus_stagione_calda)

peso_sport:
  Serie A:  calibrato su ROI storico medio (~5%)
  Serie B:  da calibrare dopo backtest
  Volley:   da calibrare dopo backtest

bonus_stagione_calda: +0.5 se ROI stagionale > soglia
```

### Output
- Report testuale (CLI o Streamlit) con le scommesse consigliate
- Budget allocato per scommessa (Kelly frazionato)
- Alert visivo per stagioni calde

---

## Ordine di implementazione

| Step | Progetto | Effort | Dipendenze |
|---|---|---|---|
| 1 | `serieb-predictor` | Basso | Nessuna (clone Serie A) |
| 2 | API layer su `seriea-predictor` | Basso | Nessuna |
| 3 | API layer su `serieb-predictor` | Basso | Step 1 |
| 4 | `volley-predictor` (scraping + modello) | Alto | Nessuna |
| 5 | API layer su `volley-predictor` | Basso | Step 4 |
| 6 | `betting-agent` | Medio | Step 2, 3, 5 |

---

## Note tecniche

- Tutti i progetti usano Python 3.11+, virtualenv separati in `/home/egiabot/venvs/`
- Struttura directory coerente tra i progetti per facilitare il riuso
- Il betting-agent non ha modelli ML propri: si fida dei predictor e aggrega
- Le API dei predictor devono essere idempotenti (stessa chiamata = stesso risultato
  nella stessa giornata) per evitare scommesse duplicate

---

## Stato complessivo (22/05/2026)

| Progetto | Stato | Porta | CV accuracy | Note |
|---|---|---|---|---|
| betting-core | ✅ Completo | — | — | https://github.com/Giangi70/betting-core — libreria condivisa |
| seriea-predictor | ✅ Completo | 8501 | 51.1% | https://github.com/Giangi70/seriea-predictor |
| serieb-predictor | ✅ Completo | 8502 | 43.2% | https://github.com/Giangi70/serieb-predictor |
| laliga2-predictor | ✅ Completo | 8503 | 44.4% | https://github.com/Giangi70/laliga2-predictor |
| bundesliga2-predictor | ✅ Completo | 8504 | 41.1% | https://github.com/Giangi70/bundesliga2-predictor |
| volley-predictor | ⏸ Sospeso | — | — | Nessuna fonte dati gratuita accessibile |
| API layer (FastAPI) | ✅ Completo | 8001-8004 | — | Endpoint /health /predictions /signals /roi su tutti e 4. Logica in betting-core (create_app). Auth via header X-API-Key. |
| betting-agent | ✅ Completo | — | — | Python puro (httpx+pydantic). Fetch concorrente, EV, ranking per score, Kelly frazionato, report rich. Commento LLM opzionale isolato. |

## App online (Streamlit Community Cloud)

Le 4 UI sono pubblicate e consultabili da browser (anche mobile). Deploy documentato in
`docs/deploy_streamlit.md` di ogni predictor; guida d'uso in `GUIDA_APP_PREDICTOR.md`.

| App | URL |
|---|---|
| Serie A | https://seriea-predictor-app.streamlit.app/ |
| Serie B | https://serieb-predictor-app.streamlit.app/ |
| La Liga 2 | https://laliga2-predictor-app.streamlit.app/ |
| Bundesliga 2 | https://bundesliga2-predictor-app.streamlit.app/ |

Note: i 4 repo predictor + betting-core sono **pubblici** (richiesto da Streamlit Cloud free).
Python fissato a 3.11 via `.python-version`. ODDS_API_KEY nei Secrets di Streamlit (non nel repo).
Lo storico ROI (SQLite) non persiste su cloud: funzione da usare in locale.

## Architettura attuale

Ogni predictor contiene solo:
- `config/config.py` — parametri specifici del campionato (CSV, API endpoint, porte, api_key)
- `src/ui/app.py` — entry point Streamlit (10 righe)
- `src/api.py` — entry point API FastAPI (`create_app(cfg)`)
- `start.sh` — avvia la UI Streamlit
- `start_api.sh` — avvia l'API FastAPI

Tutto il codice condiviso sta in `betting-core` (installato come pacchetto pip).
Per aggiornare la logica su tutti e 4 i predictor basta modificare `betting-core`.
L'API layer vive in `betting_core/api.py` (factory `create_app`) e `betting_core/signals.py`
(logica pura della strategia mista, riusata sia da UI che da API).

## Come avviare le API

Ogni predictor espone 4 endpoint REST identici: `/health`, `/predictions`, `/signals`, `/roi`.
Documentazione interattiva (Swagger) su `http://localhost:<porta>/docs`.

```bash
# avvia una singola API
cd /home/egiabot/PROJECT/seriea-predictor      && ./start_api.sh   # porta 8001
cd /home/egiabot/PROJECT/serieb-predictor      && ./start_api.sh   # porta 8002
cd /home/egiabot/PROJECT/laliga2-predictor     && ./start_api.sh   # porta 8003
cd /home/egiabot/PROJECT/bundesliga2-predictor && ./start_api.sh   # porta 8004

# avvia tutte e 4 in background
for p in seriea serieb laliga2 bundesliga2; do
  (cd /home/egiabot/PROJECT/${p}-predictor && ./start_api.sh &)
done
```

| Predictor | UI (Streamlit) | API (FastAPI) |
|---|---|---|
| seriea-predictor | 8501 | 8001 |
| serieb-predictor | 8502 | 8002 |
| laliga2-predictor | 8503 | 8003 |
| bundesliga2-predictor | 8504 | 8004 |

**Autenticazione**: opzionale, via header `X-API-Key`. Attiva solo se `API_KEY` è impostata
nel `.env` del predictor; altrimenti l'API è aperta (comodo in locale). `/health` è sempre libero.

**Nota quote live**: `/predictions` e `/signals` richiedono `ODDS_API_KEY` (The Odds API).
Senza, rispondono 503. `/health` e `/roi` funzionano comunque.

**Nota deploy**: `fastapi` e `uvicorn` sono stati aggiunti a `betting-core/setup.py`. In locale
sono già installati nei 4 venv. Su un clone fresco da GitHub verranno installati automaticamente
da `pip install -r requirements.txt` **solo dopo aver pushato betting-core aggiornato**.

## Prossimo step

Ecosistema completo: 4 predictor + API layer + betting-agent + 4 UI online. Sviluppi futuri:
- **DB persistente online** (Supabase condiviso con colonna `sport`) → vedi `TODO_DB_PERSISTENTE.md`.
  Risolve il limite attuale: su Streamlit Cloud lo storico ROI non persiste tra i riavvii.
- calibrare i `peso` per sport sui backtest reali (ora valori iniziali di buon senso)
- commento LLM del report (gancio gia predisposto in betting_agent/llm_comment.py, disattivo)
- storicizzare i report settimanali dell'agent per monitorarne le performance

Tutti i repo (betting-core, 4 predictor, betting-agent, lotto_analyzer) sono pubblicati su
GitHub (Giangi70) e pubblici. Le 4 UI sono online su Streamlit Cloud (vedi sezione "App online").

---

## Sessione 22/05/2026 — Riepilogo lavoro svolto

### Mattina
- Analisi strategia mista (9-safe + 1-jolly) su dati Serie A
- Esteso a 9 stagioni (1617→2425) scaricando i CSV extra
- Analisi ciclicità del segnale: edge forte 2019-2022, quasi zero nelle ultime 3 stagioni
- Ottimizzazione threshold gap probabilità
- Implementato Tab "🎯 Strategia Mista" nell'app Serie A con monitor ROI e alert stagione calda

### Pomeriggio
- Creato `serieb-predictor` (Serie B, porta 8502, CV 43.2%)
- Creato `laliga2-predictor` (La Liga 2, porta 8503, CV 44.4%)
- Creato `bundesliga2-predictor` (Bundesliga 2, porta 8504, CV 41.1%)
- Creato `betting-core`: libreria condivisa installabile via pip
  - Tutti i predictor ora contengono solo config (10 righe) + entry point
  - `betting-core` installato nei virtualenv locali con `pip install -e`
  - Nei requirements.txt dei predictor: `betting-core @ git+https://github.com/Giangi70/betting-core.git`
- README aggiornati su tutti i repo con Quick Start per nuovi utenti
- Tutti i repo pubblicati su GitHub (Giangi70)

### Come riprendere la prossima sessione

```bash
# Avvia un predictor (betting-core già installato localmente)
cd /home/egiabot/PROJECT/seriea-predictor && ./start.sh   # porta 8501
cd /home/egiabot/PROJECT/serieb-predictor && ./start.sh   # porta 8502
cd /home/egiabot/PROJECT/laliga2-predictor && ./start.sh  # porta 8503
cd /home/egiabot/PROJECT/bundesliga2-predictor && ./start.sh  # porta 8504
```

**Prossimo step**: API layer FastAPI in `betting-core` (endpoint `/predictions`, `/signals`, `/roi`, `/health`),
poi costruire il `betting-agent` che interroga tutti e 4 e produce il report settimanale.
