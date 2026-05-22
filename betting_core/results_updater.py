"""Aggiornamento automatico risultati dai CSV storici."""
import pandas as pd
from .config import PredictorConfig
from .storage import get_pending_predictions, set_result


def auto_update_results(cfg: PredictorConfig, team_name_map: dict | None = None) -> dict:
    """Cerca i risultati mancanti nei CSV e li aggiorna nel DB.

    Args:
        cfg: Configurazione del predictor.
        team_name_map: Mapping opzionale nomi squadra API → nomi nei CSV.
    """
    team_name_map = team_name_map or {}

    def normalize(name: str) -> str:
        return team_name_map.get(name, name).lower().strip()

    pending = get_pending_predictions(cfg)
    if not pending:
        return {"updated": 0, "still_missing": 0, "details": []}

    frames = []
    for season in cfg.seasons:
        path = cfg.data_raw / f"{cfg.csv_prefix}_{season}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="latin-1", usecols=["Date", "HomeTeam", "AwayTeam", "FTR"])
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        frames.append(df)

    if not frames:
        return {"updated": 0, "still_missing": len(pending), "details": ["CSV non trovati"]}

    csv_df = pd.concat(frames, ignore_index=True).dropna(subset=["FTR"])
    updated, still_missing, details = 0, 0, []

    for pred in pending:
        mask = (
            csv_df["HomeTeam"].str.lower().str.strip() == normalize(pred["home_team"])
        ) & (
            csv_df["AwayTeam"].str.lower().str.strip() == normalize(pred["away_team"])
        )
        match = csv_df[mask]
        if match.empty:
            still_missing += 1
            details.append(f"⏳ {pred['home_team']} vs {pred['away_team']}")
        else:
            result = match.iloc[-1]["FTR"]
            set_result(cfg, pred["id"], result)
            updated += 1
            details.append(f"✅ {pred['home_team']} vs {pred['away_team']} → {result}")

    return {"updated": updated, "still_missing": still_missing, "details": details}
