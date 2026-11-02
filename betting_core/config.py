"""Configurazione base per un predictor. Ogni progetto la estende."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PredictorConfig:
    """Configurazione completa di un predictor.

    Attributes:
        name: Nome del campionato (es. 'Serie A').
        csv_prefix: Prefisso dei file CSV storici (es. 'serie_a').
        seasons: Lista stagioni da scaricare (es. ['2021', '2122']).
        download_url: URL template con {season} per football-data.co.uk.
        odds_api_url: URL The Odds API per le quote live.
        odds_api_key: API key The Odds API.
        base_dir: Directory radice del progetto.
        streamlit_port: Porta Streamlit.
        api_port: Porta del server API FastAPI.
        api_key: API key richiesta nell'header X-API-Key (vuota = auth disattivata).
        bookmakers: Dizionario prefisso → nome bookmaker.
    """
    name: str
    csv_prefix: str
    seasons: list[str]
    download_url: str
    odds_api_url: str
    odds_api_key: str
    base_dir: Path
    streamlit_port: int = 8501
    api_port: int = 8001
    api_key: str = ""
    bookmakers: dict[str, str] = field(default_factory=lambda: {
        "B365": "Bet365",
        "WH":   "William Hill",
        "IW":   "Interwetten",
        "PS":   "Pinnacle",
        "VC":   "VC Bet",
    })

    @property
    def data_raw(self) -> Path:
        return self.base_dir / "data" / "raw"

    @property
    def data_processed(self) -> Path:
        return self.base_dir / "data" / "processed"

    @property
    def data_exports(self) -> Path:
        return self.base_dir / "data" / "exports"

    @property
    def models_dir(self) -> Path:
        return self.base_dir / "models"

    @property
    def db_path(self) -> Path:
        return self.base_dir / "data" / f"{self.csv_prefix}.db"
