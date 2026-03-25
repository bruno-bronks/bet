"""
app/models/time_window_model.py
Modelos de classificação binária para eventos em janelas temporais:
  - Gol nos primeiros 15 minutos
  - Gol nos últimos 15 minutos
  - Gol no primeiro tempo
  - Gol no segundo tempo
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)

# Mapeamento: nome do evento → coluna alvo no DataFrame
TIME_WINDOW_TARGETS = {
    "goal_first_15min": "goal_0_15",
    "goal_last_15min": "goal_75_90",
    "goal_first_half": "goal_in_first_half",
    "goal_second_half": "goal_in_second_half",
}


class TimeWindowModel(BaseFootballModel):
    """
    Classifica probabilidade de ocorrência de evento em janela temporal.
    Um modelo separado por evento (goal_first_15min, goal_last_15min, etc.).
    Usa LightGBM binário calibrado ou LogisticRegression como fallback.
    """

    def __init__(
        self,
        event_name: str,
        competition: Optional[str] = None,
        use_calibration: bool = True,
    ) -> None:
        if event_name not in TIME_WINDOW_TARGETS:
            raise ValueError(f"Unknown event '{event_name}'. Valid: {list(TIME_WINDOW_TARGETS)}")
        super().__init__(
            model_type="time_window",
            competition=competition,
            target=TIME_WINDOW_TARGETS[event_name],
        )
        self.event_name = event_name
        self.use_calibration = use_calibration

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "TimeWindowModel":
        from sklearn.calibration import CalibratedClassifierCV

        self._feature_columns = list(X.columns)
        X_arr = X.fillna(0).values.astype(np.float32)
        y_arr = y.fillna(0).values.astype(int)

        positive_rate = y_arr.mean()
        logger.info(
            f"Training time window model [{self.event_name}] | "
            f"n={len(y)} | positive_rate={positive_rate:.2%}"
        )

        try:
            import lightgbm as lgb
            base_clf = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                num_leaves=15,
                min_child_samples=20,
                subsample=0.8,
                random_state=42,
                verbose=-1,
                scale_pos_weight=(1 - positive_rate) / max(positive_rate, 1e-6),
            )
        except ImportError:
            from sklearn.linear_model import LogisticRegression
            base_clf = LogisticRegression(max_iter=1000, C=1.0)

        if self.use_calibration and 0 < positive_rate < 1:
            self._model = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
        else:
            self._model = base_clf

        self._model.fit(X_arr, y_arr)
        self._is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self._check_fitted()
        X_prep = self._prepare_X(X).fillna(0).values.astype(np.float32)
        return self._model.predict(X_prep)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self._check_fitted()
        X_prep = self._prepare_X(X).fillna(0).values.astype(np.float32)
        return self._model.predict_proba(X_prep)

    def predict_event_probability(self, X: pd.DataFrame) -> List[float]:
        """Retorna probabilidade do evento ocorrer (classe positiva = 1)."""
        proba = self.predict_proba(X)
        # Classe 1 = evento ocorre
        classes = list(self._model.classes_) if hasattr(self._model, "classes_") else [0, 1]
        pos_idx = classes.index(1) if 1 in classes else 1
        return [round(float(p[pos_idx]), 4) for p in proba]


class TimeWindowEnsemble:
    """
    Agrupa múltiplos TimeWindowModels e expõe interface unificada.
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        self.competition = competition
        self._models: Dict[str, TimeWindowModel] = {
            name: TimeWindowModel(name, competition=competition)
            for name in TIME_WINDOW_TARGETS
        }

    def fit(self, X: pd.DataFrame, df_full: pd.DataFrame) -> "TimeWindowEnsemble":
        """Treina todos os modelos de janela temporal."""
        for event_name, target_col in TIME_WINDOW_TARGETS.items():
            if target_col not in df_full.columns:
                logger.warning(f"Target column '{target_col}' not found — skipping {event_name}")
                continue
            y = df_full[target_col].dropna()
            X_aligned = X.loc[y.index]
            self._models[event_name].fit(X_aligned, y)
        return self

    def predict_all(self, X: pd.DataFrame) -> Dict[str, float]:
        """Prediz probabilidade de todos os eventos para uma única partida."""
        result: Dict[str, float] = {}
        for event_name, model in self._models.items():
            if model._is_fitted:
                probs = model.predict_event_probability(X)
                result[event_name] = probs[0] if probs else 0.5
            else:
                result[event_name] = 0.5  # prior neutro
        return result

    def save_all(self, base_path) -> None:
        from pathlib import Path
        base = Path(base_path)
        for name, model in self._models.items():
            if model._is_fitted:
                model.save(base / f"time_window_{name}.joblib")

    def load_all(self, base_path) -> "TimeWindowEnsemble":
        from pathlib import Path
        base = Path(base_path)
        for name, model in self._models.items():
            path = base / f"time_window_{name}.joblib"
            if path.exists():
                model.load(path)
        return self
