"""Inferenza: predizione esito e filtro value betting."""
import numpy as np
import joblib
from .config import PredictorConfig

_caches: dict = {}  # cache per progetto (keyed by cfg.name)


def load_model(cfg: PredictorConfig) -> dict:
    if cfg.name not in _caches:
        path = cfg.models_dir / "model.joblib"
        if not path.exists():
            raise FileNotFoundError(f"Modello non trovato: {path}. Esegui prima train.")
        _caches[cfg.name] = joblib.load(path)
    return _caches[cfg.name]


def build_features_from_odds(odds: dict[str, float], cfg: PredictorConfig) -> dict[str, float]:
    """Converte quote raw nelle feature attese dal modello."""
    bk_suffixes = {bk: (f"{bk}H", f"{bk}D", f"{bk}A") for bk in cfg.bookmakers}
    feat: dict[str, float] = {}
    odds_h, odds_d, odds_a = [], [], []

    for bk, (ch, cd, ca) in bk_suffixes.items():
        h, d, a = odds.get(ch), odds.get(cd), odds.get(ca)
        if h and d and a and h > 1 and d > 1 and a > 1:
            feat[f"{bk}_H"] = h; feat[f"{bk}_D"] = d; feat[f"{bk}_A"] = a
            odds_h.append(h); odds_d.append(d); odds_a.append(a)

    if not odds_h:
        return feat

    def implied_prob(ol):
        raw = np.mean([1/o for o in ol])
        total = np.mean([1/h+1/d+1/a for h,d,a in zip(odds_h,odds_d,odds_a)])
        return raw / total

    feat["prob_H"] = implied_prob(odds_h)
    feat["prob_D"] = implied_prob(odds_d)
    feat["prob_A"] = implied_prob(odds_a)
    feat["std_H"]  = float(np.std(odds_h))
    feat["std_D"]  = float(np.std(odds_d))
    feat["std_A"]  = float(np.std(odds_a))
    feat["divergence"]   = max(max(odds_h)-min(odds_h), max(odds_d)-min(odds_d), max(odds_a)-min(odds_a))
    feat["n_bookmakers"] = len(odds_h)
    return feat


# Filtro value betting calibrato sui dati storici (5 stagioni Serie A)
VALUE_BET_FILTERS = {
    "A": {"prob_min": 0.45, "std_max": 0.0417},
}


def predict(odds: dict[str, float], cfg: PredictorConfig) -> dict:
    """Predice le probabilità 1/X/2 per una partita."""
    bundle = load_model(cfg)
    features = build_features_from_odds(odds, cfg)
    X = np.array([features.get(col, 0.0) for col in bundle["features"]]).reshape(1, -1)
    proba = bundle["model"].predict_proba(X)[0]
    probs = {cls: float(p) for cls, p in zip(bundle["encoder"].classes_, proba)}
    best = max(probs, key=probs.__getitem__)
    return {"probs": probs, "prediction": best, "confidence": probs[best]}


def predict_match(home: str, away: str, odds: dict[str, float], cfg: PredictorConfig) -> dict:
    """Wrapper con metadati partita e flag value_bet."""
    result = predict(odds, cfg)
    result["home"] = home
    result["away"] = away
    result["prediction_label"] = {"H": home, "D": "Pareggio", "A": away}[result["prediction"]]
    # Value bet
    pred = result["prediction"]
    if pred in VALUE_BET_FILTERS:
        f = VALUE_BET_FILTERS[pred]
        features = build_features_from_odds(odds, cfg)
        result["value_bet"] = (
            result["probs"][pred] >= f["prob_min"] and
            features.get(f"std_{pred}", 999) <= f["std_max"]
        )
    else:
        result["value_bet"] = False
    return result
