"""Logica pura della strategia mista (safe + jolly) e stato 'stagione calda'.

Estratto da ui/components.py per essere riusabile sia dalla UI Streamlit sia
dall'API FastAPI, senza dipendenze da streamlit.

Strategia mista (calibrata su analisi storica):
  - SAFE:  partite con gap di probabilita tra 1o e 2o esito >= MIN_GAP, si punta
           sull'esito piu probabile. Si prendono le prime N_SAFE per probabilita.
  - JOLLY: partite con una quota massima >= MIN_Q_JOLLY, si punta sull'esito ad
           alta quota. Si prende la prima N_JOLLY per quota.
"""
from __future__ import annotations

from .config import PredictorConfig
from .storage import get_roi_strategia

# Parametri strategia mista (identici a quelli usati nella UI).
N_SAFE = 9
N_JOLLY = 1
MIN_GAP = 0.15
MIN_Q_JOLLY = 5.0
ROI_ALERT_THRESHOLD = 0.08
SEASON_START = "2025-08-01"
MIN_BETS_FOR_SIGNAL = 20  # scommesse minime per valutare la stagione calda


# ── Helper puri sulle quote ─────────────────────────────────────────────────

def quota_media(odds: dict[str, float], esito: str) -> float | None:
    """Media delle quote dei bookmaker per un dato esito (H/D/A)."""
    vals = [v for k, v in odds.items() if k.endswith(esito) and v > 1]
    return round(sum(vals) / len(vals), 2) if vals else None


def prob_gap(probs: dict[str, float]) -> float:
    """Differenza tra probabilita del 1o e del 2o esito piu probabile."""
    s = sorted(probs.values(), reverse=True)
    return s[0] - s[1]


def max_quota(odds: dict[str, float]) -> tuple[str, float]:
    """Esito con la quota massima tra i bookmaker e il suo valore."""
    best_e, best_q = "H", 0.0
    for e in ("H", "D", "A"):
        vals = [v for k, v in odds.items() if k.endswith(e) and v > 1]
        if vals and max(vals) > best_q:
            best_q = max(vals)
            best_e = e
    return best_e, best_q


def enrich_match(match: dict) -> dict | None:
    """Arricchisce una partita (home/away/odds) con probabilita e metriche.

    Restituisce None se le quote sono incomplete.
    """
    odds = match.get("odds", {})
    qh, qd, qa = quota_media(odds, "H"), quota_media(odds, "D"), quota_media(odds, "A")
    if not all([qh, qd, qa]):
        return None
    raw = {"H": 1 / qh, "D": 1 / qd, "A": 1 / qa}
    tot = sum(raw.values())
    probs = {k: v / tot for k, v in raw.items()}
    best_e = max(probs, key=probs.get)
    jolly_e, jolly_q = max_quota(odds)
    return {
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "match_date": match.get("commence_time", "")[:10],
        "probs": probs,
        "gap": prob_gap(probs),
        "best_esito": best_e,
        "best_quota": quota_media(odds, best_e),
        "jolly_esito": jolly_e,
        "jolly_quota": jolly_q,
    }


def generate_signals(matches: list[dict]) -> dict:
    """Genera i segnali della strategia mista da una lista di partite con quote.

    Restituisce un dict con liste 'safe' e 'jolly' di scommesse (formato DB:
    match_date, home_team, away_team, tipo, esito, quota, prob_gap).
    """
    enriched = [e for e in (enrich_match(m) for m in matches) if e is not None]

    pool_safe = sorted(
        [e for e in enriched if e["gap"] >= MIN_GAP],
        key=lambda x: x["probs"][x["best_esito"]],
        reverse=True,
    )[:N_SAFE]

    pool_jolly = sorted(
        [e for e in enriched if e["jolly_quota"] >= MIN_Q_JOLLY],
        key=lambda x: x["jolly_quota"],
        reverse=True,
    )[:N_JOLLY]

    safe = [
        {"match_date": e["match_date"], "home_team": e["home_team"], "away_team": e["away_team"],
         "tipo": "safe", "esito": e["best_esito"], "quota": e["best_quota"], "prob_gap": round(e["gap"], 4)}
        for e in pool_safe
    ]
    jolly = [
        {"match_date": e["match_date"], "home_team": e["home_team"], "away_team": e["away_team"],
         "tipo": "jolly", "esito": e["jolly_esito"], "quota": e["jolly_quota"], "prob_gap": round(e["gap"], 4)}
        for e in pool_jolly
    ]
    return {"safe": safe, "jolly": jolly}


# ── Stagione calda ──────────────────────────────────────────────────────────

def season_status(cfg: PredictorConfig) -> dict:
    """Stato ROI stagionale corrente + flag 'stagione calda'.

    Stagione calda = ROI >= ROI_ALERT_THRESHOLD con almeno MIN_BETS_FOR_SIGNAL
    scommesse chiuse nella stagione corrente.
    """
    stats = get_roi_strategia(cfg, season_start=SEASON_START)
    roi = stats.get("roi")
    n = stats.get("n", 0)
    stagione_calda = bool(
        roi is not None and roi >= ROI_ALERT_THRESHOLD and n >= MIN_BETS_FOR_SIGNAL
    )
    return {
        "roi": roi,
        "n_scommesse": n,
        "n_safe": stats.get("n_safe", 0),
        "n_jolly": stats.get("n_jolly", 0),
        "pl": stats.get("pl", 0.0),
        "stagione_calda": stagione_calda,
        "season_start": SEASON_START,
        "roi_alert_threshold": ROI_ALERT_THRESHOLD,
    }
