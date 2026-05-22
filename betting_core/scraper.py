"""Scraper: download CSV storici e quote live."""
import requests
from .config import PredictorConfig


def download_season(season: str, cfg: PredictorConfig) -> None:
    """Scarica il CSV di una stagione in data/raw/."""
    url = cfg.download_url.format(season=season)
    dest = cfg.data_raw / f"{cfg.csv_prefix}_{season}.csv"
    if dest.exists():
        print(f"[SKIP] {dest.name} già presente")
        return
    print(f"[DOWN] {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    cfg.data_raw.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    print(f"[OK]   Salvato {dest.name} ({len(r.content)//1024} KB)")


def download_all(cfg: PredictorConfig) -> None:
    """Scarica tutte le stagioni configurate."""
    for season in cfg.seasons:
        try:
            download_season(season, cfg)
        except requests.HTTPError as e:
            print(f"[ERR]  Stagione {season}: {e}")


def get_upcoming_odds(cfg: PredictorConfig) -> list[dict]:
    """Recupera le quote delle prossime partite via The Odds API."""
    if not cfg.odds_api_key:
        raise ValueError("ODDS_API_KEY non configurata nel file .env")

    resp = requests.get(
        cfg.odds_api_url,
        params={"apiKey": cfg.odds_api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
        timeout=15,
    )
    resp.raise_for_status()

    bk_map = {"bet365": "B365", "williamhill": "WH", "pinnacle": "PS", "interwetten": "IW"}
    matches = []
    for event in resp.json():
        match = {
            "home_team": event["home_team"],
            "away_team": event["away_team"],
            "commence_time": event["commence_time"],
            "odds": {},
        }
        for bookmaker in event.get("bookmakers", []):
            prefix = bk_map.get(bookmaker["key"])
            if not prefix:
                continue
            for market in bookmaker.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                home, away = event["home_team"], event["away_team"]
                if home in outcomes and away in outcomes and "Draw" in outcomes:
                    match["odds"][f"{prefix}H"] = outcomes[home]
                    match["odds"][f"{prefix}D"] = outcomes["Draw"]
                    match["odds"][f"{prefix}A"] = outcomes[away]
        if match["odds"]:
            matches.append(match)
    return matches
