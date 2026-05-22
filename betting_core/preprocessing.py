"""Preprocessing: carica CSV storici e costruisce le feature per il training."""
import pandas as pd
import numpy as np
from pathlib import Path
from .config import PredictorConfig


def load_raw(cfg: PredictorConfig) -> pd.DataFrame:
    """Carica e concatena tutti i CSV storici disponibili."""
    frames = []
    for season in cfg.seasons:
        path = cfg.data_raw / f"{cfg.csv_prefix}_{season}.csv"
        if not path.exists():
            print(f"[WARN] {path.name} non trovato, skip")
            continue
        df = pd.read_csv(path, encoding="latin-1")
        df["season"] = season
        frames.append(df)
    if not frames:
        raise ValueError(f"Nessun CSV trovato in {cfg.data_raw}")
    return pd.concat(frames, ignore_index=True)


def build_features(df: pd.DataFrame, cfg: PredictorConfig) -> pd.DataFrame:
    """Costruisce le feature dal DataFrame grezzo.

    Feature per partita:
    - Quote H/D/A di ogni bookmaker disponibile
    - Probabilità implicite normalizzate (vig rimosso)
    - Std e divergenza tra bookmaker
    - Numero bookmaker disponibili
    """
    odds_cols = {bk: [f"{bk}H", f"{bk}D", f"{bk}A"] for bk in cfg.bookmakers}
    rows = []

    for _, row in df.iterrows():
        feat: dict = {}
        odds_h, odds_d, odds_a = [], [], []

        for bk, (ch, cd, ca) in odds_cols.items():
            h, d, a = row.get(ch), row.get(cd), row.get(ca)
            if pd.notna(h) and pd.notna(d) and pd.notna(a) and h > 1 and d > 1 and a > 1:
                feat[f"{bk}_H"] = h
                feat[f"{bk}_D"] = d
                feat[f"{bk}_A"] = a
                odds_h.append(h); odds_d.append(d); odds_a.append(a)

        if len(odds_h) < 2:
            continue

        def implied_prob(ol: list) -> float:
            raw = np.mean([1 / o for o in ol])
            total = np.mean([1/h + 1/d + 1/a for h, d, a in zip(odds_h, odds_d, odds_a)])
            return raw / total

        feat["prob_H"] = implied_prob(odds_h)
        feat["prob_D"] = implied_prob(odds_d)
        feat["prob_A"] = implied_prob(odds_a)
        feat["std_H"]  = np.std(odds_h)
        feat["std_D"]  = np.std(odds_d)
        feat["std_A"]  = np.std(odds_a)
        feat["divergence"]    = max(max(odds_h)-min(odds_h), max(odds_d)-min(odds_d), max(odds_a)-min(odds_a))
        feat["n_bookmakers"]  = len(odds_h)
        feat["result"]        = row.get("FTR")
        feat["season"]        = row.get("season")
        feat["date"]          = row.get("Date")
        feat["home_team"]     = row.get("HomeTeam")
        feat["away_team"]     = row.get("AwayTeam")
        rows.append(feat)

    result_df = pd.DataFrame(rows).dropna(subset=["result"])
    return result_df[result_df["result"].isin(["H", "D", "A"])].reset_index(drop=True)


def run(cfg: PredictorConfig) -> pd.DataFrame:
    """Pipeline completa: carica → trasforma → salva."""
    raw = load_raw(cfg)
    print(f"[INFO] Righe grezze: {len(raw)}")
    processed = build_features(raw, cfg)
    print(f"[INFO] Righe dopo preprocessing: {len(processed)}")
    print(f"[INFO] Distribuzione risultati:\n{processed['result'].value_counts()}")
    cfg.data_processed.mkdir(parents=True, exist_ok=True)
    out = cfg.data_processed / "dataset.csv"
    processed.to_csv(out, index=False)
    print(f"[OK] Dataset salvato: {out} ({len(processed)} righe)")
    return processed
