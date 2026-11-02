"""API layer FastAPI per i predictor. Factory create_app(cfg).

Espone 4 endpoint standard, identici per tutti i predictor, interrogabili dal
betting-agent:

    GET /health       stato servizio (modello caricato, dataset, ultimo update)
    GET /predictions  predizioni della giornata corrente (richiede quote live)
    GET /signals      segnali strategia mista (safe + jolly) + stato stagione
    GET /roi          ROI stagionale corrente + flag stagione_calda

Autenticazione: se cfg.api_key e valorizzata, ogni endpoint (tranne /health)
richiede l'header  X-API-Key: <chiave>.  Se vuota, l'auth e disattivata.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException

from .config import PredictorConfig
from . import signals as signals_mod
from .prediction import predict_match
from .scraper import get_upcoming_odds
from .storage import (
    get_roi_strategia,
    init_db,
    save_strategia_mista,
)


def _api_key_dependency(cfg: PredictorConfig):
    """Costruisce la dependency di autenticazione legata a questa config."""

    def verify(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not cfg.api_key:
            return  # auth disattivata
        if x_api_key != cfg.api_key:
            raise HTTPException(status_code=401, detail="API key mancante o non valida")

    return verify


def _load_matches(cfg: PredictorConfig) -> list[dict]:
    """Recupera le quote live. Solleva HTTPException 503 se non disponibili."""
    try:
        return get_upcoming_odds(cfg)
    except Exception as exc:  # noqa: BLE001 - propagato come 503 leggibile
        raise HTTPException(status_code=503, detail=f"Quote non disponibili: {exc}") from exc


def create_app(cfg: PredictorConfig) -> FastAPI:
    """Crea l'app FastAPI per un predictor configurato."""
    init_db(cfg)
    app = FastAPI(
        title=f"{cfg.name} Predictor API",
        version="1.0.0",
        description=f"API di predizione e segnali per {cfg.name}.",
    )
    auth = Depends(_api_key_dependency(cfg))

    @app.get("/health")
    def health() -> dict:
        model_ok = (cfg.models_dir / "model.joblib").exists()
        data_ok = (cfg.data_processed / "dataset.csv").exists()
        return {
            "status": "ok",
            "sport": cfg.name,
            "model_loaded": model_ok,
            "dataset_present": data_ok,
            "auth_required": bool(cfg.api_key),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/predictions", dependencies=[auth])
    def predictions() -> dict:
        if not (cfg.models_dir / "model.joblib").exists():
            raise HTTPException(status_code=503, detail="Modello non addestrato.")
        matches = _load_matches(cfg)
        out = []
        for m in matches:
            try:
                pred = predict_match(m["home_team"], m["away_team"], m["odds"], cfg)
            except Exception:  # noqa: BLE001 - partita con quote incomplete, skip
                continue
            out.append({
                "home": pred["home"],
                "away": pred["away"],
                "match_date": m.get("commence_time", "")[:10],
                "prediction": pred["prediction"],
                "prediction_label": pred["prediction_label"],
                "prob_H": round(pred["probs"]["H"], 4),
                "prob_D": round(pred["probs"]["D"], 4),
                "prob_A": round(pred["probs"]["A"], 4),
                "confidence": round(pred["confidence"], 4),
                "value_bet": bool(pred.get("value_bet", False)),
            })
        return {"sport": cfg.name, "count": len(out), "predictions": out}

    @app.get("/signals", dependencies=[auth])
    def signals(persist: bool = True) -> dict:
        matches = _load_matches(cfg)
        sig = signals_mod.generate_signals(matches)
        if persist:
            save_strategia_mista(cfg, sig["safe"] + sig["jolly"])
        status = signals_mod.season_status(cfg)
        return {
            "sport": cfg.name,
            "n_safe": len(sig["safe"]),
            "n_jolly": len(sig["jolly"]),
            "safe": sig["safe"],
            "jolly": sig["jolly"],
            "stagione_calda": status["stagione_calda"],
        }

    @app.get("/roi", dependencies=[auth])
    def roi() -> dict:
        status = signals_mod.season_status(cfg)
        allt = get_roi_strategia(cfg)
        return {
            "sport": cfg.name,
            "roi": status["roi"],
            "n_scommesse": status["n_scommesse"],
            "pl": status["pl"],
            "n_safe": status["n_safe"],
            "n_jolly": status["n_jolly"],
            "stagione_calda": status["stagione_calda"],
            "season_start": status["season_start"],
            "n_scommesse_totali": allt["n"],
        }

    return app
