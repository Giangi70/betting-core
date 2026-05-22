# betting-core

Libreria Python condivisa per l'ecosistema di predictor sportivi.

Contiene tutta la logica comune: preprocessing, training, inferenza, storage SQLite, scraper, componenti UI Streamlit. Ogni predictor la installa come dipendenza e fornisce solo la propria configurazione.

## Installazione

```bash
pip install git+https://github.com/Giangi70/betting-core.git
```

Oppure aggiungendo al `requirements.txt`:
```
betting-core @ git+https://github.com/Giangi70/betting-core.git
```

## Utilizzo

```python
from betting_core import PredictorConfig

cfg = PredictorConfig(
    name="Il Mio Campionato",
    csv_prefix="mio_campionato",
    seasons=["2324", "2425"],
    download_url="https://www.football-data.co.uk/mmz4281/{season}/XX.csv",
    odds_api_url="https://api.the-odds-api.com/v4/sports/soccer_xxx/odds",
    odds_api_key="la-tua-api-key",
    base_dir=Path("."),
    streamlit_port=8505,
)

from betting_core.scraper import download_all
from betting_core.training import run as train
from betting_core.prediction import predict_match

download_all(cfg)
train(cfg)
pred = predict_match("Home", "Away", {"B365H": 2.1, "B365D": 3.4, "B365A": 3.2}, cfg)
```

## Moduli

| Modulo | Descrizione |
|---|---|
| `config.py` | `PredictorConfig` — configurazione parametrica |
| `preprocessing.py` | Carica CSV e costruisce feature (prob, std, divergence) |
| `training.py` | Training XGBoost con cross-validation 5-fold |
| `prediction.py` | Inferenza + filtro value bet |
| `scraper.py` | Download CSV storici + quote live The Odds API |
| `storage.py` | SQLite: predizioni, strategia mista, odds cache |
| `results_updater.py` | Match automatico predizioni → risultati CSV |
| `ui/components.py` | Tutti i tab Streamlit riusabili |

## Predictor che usano questa libreria

| Progetto | Campionato | Porta |
|---|---|---|
| [seriea-predictor](https://github.com/Giangi70/seriea-predictor) | Serie A Italia | 8501 |
| [serieb-predictor](https://github.com/Giangi70/serieb-predictor) | Serie B Italia | 8502 |
| [laliga2-predictor](https://github.com/Giangi70/laliga2-predictor) | La Liga 2 Spagna | 8503 |
| [bundesliga2-predictor](https://github.com/Giangi70/bundesliga2-predictor) | Bundesliga 2 Germania | 8504 |
