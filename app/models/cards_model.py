"""
app/models/cards_model.py
Modelo de cartões (amarelos + vermelhos) por equipe e total.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import poisson

from app.core.logger import get_logger
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)

CARD_LINES = [2.5, 3.5, 4.5, 5.5]


class CardsModel(BaseFootballModel):
    """
    Modelo de cartões usando Poisson regression.
    Prediz total de cartões e por equipe (mandante/visitante).
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        super().__init__(model_type="cards", competition=competition, target="cards")
        self._total_model = None
        self._home_model = None
        self._away_model = None

    def fit(self, X: pd.DataFrame, y: pd.DataFrame) -> "CardsModel":
        """
        Args:
            y: DataFrame com 'home_total_cards', 'away_total_cards', 'total_cards'.
        """
        from sklearn.linear_model import PoissonRegressor

        self._feature_columns = list(X.columns)
        X_arr = X.fillna(0).values.astype(np.float32)

        # Garante colunas de cards
        y_home = y.get("home_total_cards", pd.Series(np.zeros(len(y)))).fillna(2.0).values
        y_away = y.get("away_total_cards", pd.Series(np.zeros(len(y)))).fillna(2.0).values
        y_total = y.get("total_cards", pd.Series(y_home + y_away)).fillna(4.0).values

        logger.info(f"Training cards model | n={len(X)} | mean_total={y_total.mean():.1f}")

        self._home_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_home)
        self._away_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_away)
        self._total_model = PoissonRegressor(alpha=0.1, max_iter=300).fit(X_arr, y_total)

        self._is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
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
                f"cards_over_{str(line).replace('.', '_')}": round(
                    float(1 - poisson.cdf(int(line), max(0.01, lam_total))), 4
                )
                for line in CARD_LINES
            }
            results.append({
                "expected_cards_total": round(float(lam_total), 2),
                "expected_cards_home": round(float(lam_home), 2),
                "expected_cards_away": round(float(lam_away), 2),
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

    def load(self, path) -> "CardsModel":
        import joblib
        a = joblib.load(path)
        self._total_model = a["total_model"]
        self._home_model = a["home_model"]
        self._away_model = a["away_model"]
        self._feature_columns = a["feature_columns"]
        self._is_fitted = True
        return self
