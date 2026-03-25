"""
app/models/goals_model.py
Modelo de gols usando regressão de Poisson independente para cada time.
Produz expectativas de gols e probabilidades de over/under e placares.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import poisson

from app.core.logger import get_logger
from app.core.utils import bivariate_poisson_scoreline_probs, poisson_over_probability, top_n_scorelines
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)

GOAL_LINES = [0.5, 1.5, 2.5, 3.5, 4.5]


class GoalsModel(BaseFootballModel):
    """
    Modelo de gols via Regressão de Poisson (dois modelos independentes):
      - Um para gols do mandante
      - Um para gols do visitante

    Produz:
      - λ_home, λ_away (taxas esperadas de gols)
      - P(over N.5) para N em {0,1,2,3,4}
      - P(ambas marcam)
      - Distribuição de placares mais prováveis

    Alternativa avançada: Dixon-Coles para corrigir dependência em placares baixos.
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        super().__init__(model_type="goals", competition=competition, target="goals")
        self._home_model = None
        self._away_model = None
        self._home_feature_cols: List[str] = []
        self._away_feature_cols: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.DataFrame) -> "GoalsModel":
        """
        Treina dois regressores de Poisson.

        Args:
            X: Features do jogo.
            y: DataFrame com colunas 'home_goals' e 'away_goals'.
        """
        from sklearn.linear_model import PoissonRegressor

        self._feature_columns = list(X.columns)
        X_arr = X.fillna(0).values.astype(np.float32)

        y_home = y["home_goals"].fillna(0).values.astype(float)
        y_away = y["away_goals"].fillna(0).values.astype(float)

        logger.info(f"Training goals model | n={len(X)} | mean_home={y_home.mean():.2f} | mean_away={y_away.mean():.2f}")

        self._home_model = PoissonRegressor(alpha=0.1, max_iter=300)
        self._away_model = PoissonRegressor(alpha=0.1, max_iter=300)

        self._home_model.fit(X_arr, y_home)
        self._away_model.fit(X_arr, y_away)

        self._is_fitted = True
        logger.info("Goals model fitted successfully")
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Retorna array com [λ_home, λ_away] para cada linha."""
        self._check_fitted()
        X_prep = self._prepare_X(X).fillna(0).values.astype(np.float32)
        lam_home = self._home_model.predict(X_prep)
        lam_away = self._away_model.predict(X_prep)
        return np.column_stack([lam_home, lam_away])

    def predict_full(self, X: pd.DataFrame, max_goals: int = 6) -> List[Dict]:
        """
        Retorna previsão completa de gols por partida, incluindo:
          - lam_home, lam_away (taxas Poisson)
          - over_N_5 para cada linha
          - both_teams_score
          - top_scorelines (10 placares mais prováveis)
        """
        self._check_fitted()
        lambdas = self.predict(X)
        results = []

        for lam_home, lam_away in lambdas:
            lam_home = max(0.01, float(lam_home))
            lam_away = max(0.01, float(lam_away))
            lam_total = lam_home + lam_away

            over_probs = {
                f"over_{str(line).replace('.', '_')}": round(poisson_over_probability(lam_total, line), 4)
                for line in GOAL_LINES
            }

            scoreline_probs = bivariate_poisson_scoreline_probs(lam_home, lam_away, max_goals)
            # P(ambas marcam) = P(home >= 1) * P(away >= 1)
            p_bts = (1 - poisson.pmf(0, lam_home)) * (1 - poisson.pmf(0, lam_away))
            # P(clean sheet home) = P(away = 0)
            p_cs_home = float(poisson.pmf(0, lam_away))
            p_cs_away = float(poisson.pmf(0, lam_home))

            results.append({
                "expected_goals_home": round(lam_home, 3),
                "expected_goals_away": round(lam_away, 3),
                "expected_goals_total": round(lam_total, 3),
                **over_probs,
                "both_teams_score": round(p_bts, 4),
                "clean_sheet_home": round(p_cs_home, 4),
                "clean_sheet_away": round(p_cs_away, 4),
                "top_scorelines": top_n_scorelines(scoreline_probs, n=10),
            })

        return results

    def save(self, path) -> None:
        """Override para salvar ambos os modelos internos."""
        import joblib
        path = path if hasattr(path, "parent") else __import__("pathlib").Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "home_model": self._home_model,
            "away_model": self._away_model,
            "feature_columns": self._feature_columns,
            "model_type": self.model_type,
            "competition": self.competition,
        }, path)
        logger.info(f"Goals model saved to {path}")

    def load(self, path) -> "GoalsModel":
        """Override para carregar ambos os modelos internos."""
        import joblib
        artifact = joblib.load(path)
        self._home_model = artifact["home_model"]
        self._away_model = artifact["away_model"]
        self._feature_columns = artifact["feature_columns"]
        self._is_fitted = True
        logger.info(f"Goals model loaded from {path}")
        return self
