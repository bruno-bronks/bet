"""
app/models/outcome_model.py
Modelo para resultado final da partida (1X2): H, D, A.
Usa LightGBM com classificação multiclasse + fallback logístico.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from app.core.utils import normalize_probabilities
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)

OUTCOME_CLASSES = ["H", "D", "A"]
OUTCOME_LABELS = {"H": "home_win", "D": "draw", "A": "away_win"}


class OutcomeModel(BaseFootballModel):
    """
    Modelo de resultado 1X2 (mandante vence / empate / visitante vence).

    - LightGBM multiclasse como modelo principal
    - Saída calibrada via CalibratedClassifierCV (isotônico)
    - Fallback para Logistic Regression se lgbm não disponível

    NOTA: Probabilidades são estimativas — não certezas.
    """

    def __init__(
        self,
        competition: Optional[str] = None,
        use_calibration: bool = True,
        n_estimators: int = 300,
        learning_rate: float = 0.05,
    ) -> None:
        super().__init__(model_type="outcome", competition=competition, target="outcome")
        self.use_calibration = use_calibration
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self._label_encoder = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "OutcomeModel":
        """
        Treina o modelo de resultado.

        Args:
            X: DataFrame com features.
            y: Série com outcomes ('H', 'D', 'A').
        """
        from sklearn.preprocessing import LabelEncoder
        from sklearn.calibration import CalibratedClassifierCV

        self._feature_columns = list(X.columns)
        X_arr = X.fillna(0).values.astype(np.float32)

        # Codifica labels
        self._label_encoder = LabelEncoder()
        y_enc = self._label_encoder.fit_transform(y)
        classes = list(self._label_encoder.classes_)
        logger.info(f"Training outcome model | classes={classes} | n={len(y)}")

        try:
            import lightgbm as lgb
            base_clf = lgb.LGBMClassifier(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                max_depth=6,
                num_leaves=31,
                min_child_samples=15,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1,
                objective="multiclass",
                num_class=len(classes),
            )
        except ImportError:
            logger.warning("LightGBM not available — falling back to LogisticRegression")
            from sklearn.linear_model import LogisticRegression
            base_clf = LogisticRegression(max_iter=1000, C=1.0)

        if self.use_calibration and len(np.unique(y_enc)) > 1:
            self._model = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
        else:
            self._model = base_clf

        self._model.fit(X_arr, y_enc)
        self._is_fitted = True
        logger.info("Outcome model fitted successfully")
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Retorna classe predita ('H', 'D', 'A') para cada linha."""
        self._check_fitted()
        X_prep = self._prepare_X(X)
        y_enc = self._model.predict(X_prep.values.astype(np.float32))
        return self._label_encoder.inverse_transform(y_enc)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Retorna probabilidades [P(H), P(D), P(A)] para cada partida.
        Shape: (n_samples, 3)
        """
        self._check_fitted()
        X_prep = self._prepare_X(X)
        return self._model.predict_proba(X_prep.values.astype(np.float32))

    def save(self, path) -> None:
        """Override para incluir _label_encoder na serialização."""
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        import joblib
        joblib.dump({
            "model": self._model,
            "feature_columns": self._feature_columns,
            "model_type": self.model_type,
            "competition": self.competition,
            "target": self.target,
            "label_encoder": self._label_encoder,
        }, path)

    def load(self, path) -> "OutcomeModel":
        """Override para restaurar _label_encoder."""
        from pathlib import Path
        import joblib
        path = Path(path)
        artifact = joblib.load(path)
        self._model = artifact["model"]
        self._feature_columns = artifact.get("feature_columns", [])
        self._label_encoder = artifact.get("label_encoder")
        self._is_fitted = True
        return self

    def predict_structured(self, X: pd.DataFrame) -> List[Dict[str, float]]:
        """
        Retorna lista de dicts com probabilidades nomeadas e normalizadas.
        """
        self._check_fitted()
        raw = self.predict_proba(X)
        # Usa classes do label encoder se disponível, senão fallback para ordem padrão
        if self._label_encoder is not None:
            classes = list(self._label_encoder.classes_)
        else:
            classes = OUTCOME_CLASSES

        results = []
        for proba_row in raw:
            class_proba = dict(zip(classes, proba_row.tolist()))
            normalized = normalize_probabilities([
                class_proba.get("H", 0.33),
                class_proba.get("D", 0.33),
                class_proba.get("A", 0.33),
            ])
            results.append({
                "home_win": round(normalized[0], 4),
                "draw": round(normalized[1], 4),
                "away_win": round(normalized[2], 4),
            })
        return results
