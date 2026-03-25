"""
app/models/corners_model.py
Modelo de escanteios (total e por equipe) usando regressão de Poisson/Ridge.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import poisson

from app.core.logger import get_logger
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)

CORNER_LINES = [7.5, 8.5, 9.5, 10.5, 11.5]


class CornersModel(BaseFootballModel):
    """
    Modelo de escanteios:
      - Prediz total de escanteios (lam_total)
      - Prediz escanteios por equipe (lam_home, lam_away)
      - Calcula probabilidades de over/under para linhas comuns
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        super().__init__(model_type="corners", competition=competition, target="corners")
        self._total_model = None
        self._home_model = None
        self._away_model = None

    def fit(self, X: pd.DataFrame, y: pd.DataFrame) -> "CornersModel":
        """
        Args:
            X: Features.
            y: DataFrame com 'home_corners', 'away_corners', 'total_corners'.
        """
        from sklearn.linear_model import PoissonRegressor

        self._feature_columns = list(X.columns)
        X_arr = X.fillna(0).values.astype(np.float32)

        # Usa total se disponível; caso contrário estima
        if "total_corners" in y.columns:
            y_total = y["total_corners"].fillna(y[["home_corners", "away_corners"]].sum(axis=1))
        else:
            y_total = y["home_corners"].fillna(0) + y["away_corners"].fillna(0)

        y_home = y["home_corners"].fillna(0).values.astype(float)
        y_away = y["away_corners"].fillna(0).values.astype(float)
        y_tot = y_total.fillna(9.0).values.astype(float)  # prior neutro = 9 escanteios

        logger.info(f"Training corners model | n={len(X)} | mean_total={y_tot.mean():.1f}")

        self._total_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_tot)
        self._home_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_home)
        self._away_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_away)

        self._is_fitted = True
        logger.info("Corners model fitted successfully")
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Retorna [lam_total, lam_home, lam_away] por linha."""
        self._check_fitted()
        X_prep = self._prepare_X(X).fillna(0).values.astype(np.float32)
        return np.column_stack([
            self._total_model.predict(X_prep),
            self._home_model.predict(X_prep),
            self._away_model.predict(X_prep),
        ])

    def predict_full(self, X: pd.DataFrame) -> List[Dict]:
        self._check_fitted()
        preds = self.predict(X)
        results = []
        for lam_total, lam_home, lam_away in preds:
            over_probs = {
                f"corners_over_{str(line).replace('.', '_')}": round(
                    float(1 - poisson.cdf(int(line), max(0.01, lam_total))), 4
                )
                for line in CORNER_LINES
            }
            results.append({
                "expected_corners_total": round(float(lam_total), 2),
                "expected_corners_home": round(float(lam_home), 2),
                "expected_corners_away": round(float(lam_away), 2),
                **over_probs,
            })
        return results

    def save(self, path) -> None:
        import joblib
        path = path if hasattr(path, "parent") else __import__("pathlib").Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "total_model": self._total_model,
            "home_model": self._home_model,
            "away_model": self._away_model,
            "feature_columns": self._feature_columns,
        }, path)

    def load(self, path) -> "CornersModel":
        import joblib
        a = joblib.load(path)
        self._total_model = a["total_model"]
        self._home_model = a["home_model"]
        self._away_model = a["away_model"]
        self._feature_columns = a["feature_columns"]
        self._is_fitted = True
        return self
