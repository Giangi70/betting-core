"""Training XGBoost con cross-validation."""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
from .config import PredictorConfig
from .preprocessing import run as preprocess_run

NON_FEATURE_COLS = {"result", "season", "date", "home_team", "away_team"}


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def load_dataset(cfg: PredictorConfig) -> pd.DataFrame:
    path = cfg.data_processed / "dataset.csv"
    if not path.exists():
        print("[INFO] Dataset non trovato, eseguo preprocessing...")
        return preprocess_run(cfg)
    return pd.read_csv(path)


def train(df: pd.DataFrame) -> tuple:
    """Addestra XGBoost. Restituisce (model, encoder, feature_cols)."""
    feature_cols = get_feature_cols(df)
    X = df[feature_cols].fillna(0).values
    le = LabelEncoder()
    y = le.fit_transform(df["result"])

    model = XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        use_label_encoder=False, eval_metric="mlogloss", random_state=42,
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
    print(f"[CV] Accuracy: {scores.mean():.3f} ± {scores.std():.3f}")
    model.fit(X, y)
    print("\n[REPORT] Training set:")
    print(classification_report(y, model.predict(X), target_names=le.classes_))
    return model, le, feature_cols


def run(cfg: PredictorConfig) -> Path:
    """Pipeline completa: carica → addestra → salva."""
    df = load_dataset(cfg)
    feature_cols = get_feature_cols(df)
    print(f"[INFO] Dataset: {len(df)} partite, {len(feature_cols)} feature")
    model, le, feature_cols = train(df)
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.models_dir / "model.joblib"
    joblib.dump({"model": model, "encoder": le, "features": feature_cols}, out)
    print(f"[OK] Modello salvato: {out}")
    return out
