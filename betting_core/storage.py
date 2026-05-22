"""Persistenza SQLite: predizioni, risultati, strategia mista."""
import sqlite3
import json
from contextlib import contextmanager
from .config import PredictorConfig


@contextmanager
def _conn(cfg: PredictorConfig):
    con = sqlite3.connect(cfg.db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(cfg: PredictorConfig) -> None:
    with _conn(cfg) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date TEXT, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
                prediction TEXT NOT NULL, prob_h REAL, prob_d REAL, prob_a REAL,
                value_bet INTEGER, avg_odds REAL, result TEXT,
                created_at TEXT DEFAULT (date('now'))
            )""")
        con.execute("""
            CREATE TABLE IF NOT EXISTS strategia_mista (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
                tipo TEXT NOT NULL, esito TEXT NOT NULL, quota REAL, prob_gap REAL,
                result TEXT, created_at TEXT DEFAULT (date('now'))
            )""")
        con.execute("CREATE TABLE IF NOT EXISTS odds_cache (fetched_at TEXT, data TEXT)")


# ── Predictions ───────────────────────────────────────────────────────────────

def save_prediction(cfg, home_team, away_team, prediction, prob_h, prob_d, prob_a,
                    value_bet, avg_odds=None, match_date=None) -> int:
    init_db(cfg)
    with _conn(cfg) as con:
        cur = con.execute(
            "INSERT INTO predictions (match_date,home_team,away_team,prediction,prob_h,prob_d,prob_a,value_bet,avg_odds) VALUES (?,?,?,?,?,?,?,?,?)",
            (match_date, home_team, away_team, prediction, prob_h, prob_d, prob_a, int(value_bet), avg_odds),
        )
        return cur.lastrowid


def set_result(cfg, prediction_id: int, result: str) -> None:
    with _conn(cfg) as con:
        con.execute("UPDATE predictions SET result=? WHERE id=?", (result, prediction_id))


def get_all_predictions(cfg) -> list[dict]:
    init_db(cfg)
    with _conn(cfg) as con:
        return [dict(r) for r in con.execute("SELECT * FROM predictions ORDER BY created_at DESC, id DESC").fetchall()]


def get_pending_predictions(cfg) -> list[dict]:
    init_db(cfg)
    with _conn(cfg) as con:
        return [dict(r) for r in con.execute("SELECT * FROM predictions WHERE result IS NULL ORDER BY match_date").fetchall()]


def get_roi_stats(cfg) -> dict:
    init_db(cfg)
    with _conn(cfg) as con:
        rows = con.execute("SELECT prediction,result,avg_odds FROM predictions WHERE result IS NOT NULL AND value_bet=1").fetchall()
    if not rows:
        return {"n": 0, "win_rate": None, "roi": None}
    wins = sum(1 for r in rows if r["prediction"] == r["result"])
    pl = sum((r["avg_odds"]-1) if r["prediction"]==r["result"] else -1 for r in rows if r["avg_odds"])
    n = len(rows)
    return {"n": n, "win_rate": wins/n, "roi": pl/n}


# ── Odds cache ────────────────────────────────────────────────────────────────

def save_odds_cache(cfg, matches: list[dict]) -> None:
    init_db(cfg)
    with _conn(cfg) as con:
        con.execute("DELETE FROM odds_cache")
        con.execute("INSERT INTO odds_cache VALUES (datetime('now'),?)", (json.dumps(matches),))


def load_odds_cache(cfg, max_age_hours: int = 6):
    init_db(cfg)
    with _conn(cfg) as con:
        row = con.execute(
            "SELECT data,fetched_at FROM odds_cache WHERE fetched_at >= datetime('now',?)",
            (f"-{max_age_hours} hours",)
        ).fetchone()
    return (json.loads(row["data"]), row["fetched_at"]) if row else (None, None)


# ── Strategia mista ───────────────────────────────────────────────────────────

def save_strategia_mista(cfg, scommesse: list[dict]) -> None:
    init_db(cfg)
    with _conn(cfg) as con:
        for s in scommesse:
            exists = con.execute(
                "SELECT id FROM strategia_mista WHERE match_date=? AND home_team=? AND away_team=? AND tipo=?",
                (s["match_date"], s["home_team"], s["away_team"], s["tipo"])
            ).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO strategia_mista (match_date,home_team,away_team,tipo,esito,quota,prob_gap) VALUES (?,?,?,?,?,?,?)",
                    (s["match_date"], s["home_team"], s["away_team"], s["tipo"], s["esito"], s["quota"], s["prob_gap"]),
                )


def get_strategia_mista(cfg) -> list[dict]:
    init_db(cfg)
    with _conn(cfg) as con:
        return [dict(r) for r in con.execute("SELECT * FROM strategia_mista ORDER BY match_date DESC, tipo, id").fetchall()]


def set_result_strategia(cfg, record_id: int, result: str) -> None:
    with _conn(cfg) as con:
        con.execute("UPDATE strategia_mista SET result=? WHERE id=?", (result, record_id))


def get_roi_strategia(cfg, season_start: str | None = None) -> dict:
    init_db(cfg)
    with _conn(cfg) as con:
        if season_start:
            rows = con.execute(
                "SELECT tipo,esito,quota,result FROM strategia_mista WHERE result IS NOT NULL AND match_date>=?",
                (season_start,)
            ).fetchall()
        else:
            rows = con.execute("SELECT tipo,esito,quota,result FROM strategia_mista WHERE result IS NOT NULL").fetchall()
    if not rows:
        return {"n": 0, "n_safe": 0, "n_jolly": 0, "roi": None, "pl": 0.0}
    pl = sum((r["quota"]-1) if r["esito"]==r["result"] else -1 for r in rows)
    n = len(rows)
    return {
        "n": n,
        "n_safe":  sum(1 for r in rows if r["tipo"]=="safe"),
        "n_jolly": sum(1 for r in rows if r["tipo"]=="jolly"),
        "roi": pl/n, "pl": round(pl, 2),
    }
