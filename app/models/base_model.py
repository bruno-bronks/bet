"""
app/models/base_model.py
Classe base abstrata para todos os modelos da plataforma.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from app.core.logger import get_logger

logger = get_logger(__name__)


class BaseFootballModel(ABC):
    """
    Interface comum para todos os modelos preditivos.

    Subclasses devem implementar `fit` e `predict`.
    `save` / `load` podem ser sobrescritos para modelos com estrutura especial (ex: GoalsModel).
    """

    def __init__(
        self,
        model_type: str,
        competition: Optional[str] = None,
        target: Optional[str] = None,
    ) -> None:
        self.model_type = model_type
        self.competition = competition
        self.target = target

        self._model: Any = None
        self._feature_columns: List[str] = []
        self._is_fitted: bool = False

    # ── Interface obrigatória ─────────────────────────────────────────────────

    @abstractmethod
    def fit(self, X: pd.DataFrame, y) -> "BaseFootballModel":
        """Treina o modelo."""

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Retorna predições."""

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _check_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError(
                f"{self.__class__.__name__} is not fitted. Call fit() first."
            )

    def _prepare_X(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Alinha X com as colunas vistas no treino.
        Colunas ausentes são preenchidas com 0; extras são descartadas.
        """
        if not self._feature_columns:
            return X.fillna(0)

        missing = [c for c in self._feature_columns if c not in X.columns]
        if missing:
            logger.debug(f"Filling {len(missing)} missing feature columns with 0")
            for c in missing:
                X = X.copy()
                X[c] = 0.0

        return X[self._feature_columns].fillna(0)

    @property
    def feature_columns(self) -> List[str]:
        return self._feature_columns

    # ── Persistência padrão (joblib) ──────────────────────────────────────────

    def save(self, path) -> None:
        """Serializa o modelo para disco."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self._model,
            "feature_columns": self._feature_columns,
            "model_type": self.model_type,
            "competition": self.competition,
            "target": self.target,
        }, path)
        logger.info(f"Model saved: {path}")

    def load(self, path) -> "BaseFootballModel":
        """Carrega modelo do disco."""
        path = Path(path)
        artifact = joblib.load(path)
        self._model = artifact["model"]
        self._feature_columns = artifact.get("feature_columns", [])
        self._is_fitted = True
        logger.info(f"Model loaded: {path}")
        return self

    def get_feature_importances(self) -> Dict[str, float]:
        """Retorna importâncias de feature quando disponíveis."""
        if self._model is None:
            return {}
        model = self._model
        # CalibratedClassifierCV wraps the base estimator
        if hasattr(model, "estimator"):
            model = model.estimator
        if hasattr(model, "calibrated_classifiers_"):
            # Averaged across folds
            importances = []
            for cc in model.calibrated_classifiers_:
                base = cc.estimator
                if hasattr(base, "feature_importances_"):
                    importances.append(base.feature_importances_)
            if importances:
                avg = np.mean(importances, axis=0)
                return dict(zip(self._feature_columns, avg.tolist()))
        if hasattr(model, "feature_importances_"):
            return dict(zip(self._feature_columns, model.feature_importances_.tolist()))
        if hasattr(model, "coef_"):
            coefs = np.abs(model.coef_).mean(axis=0) if model.coef_.ndim > 1 else np.abs(model.coef_)
            return dict(zip(self._feature_columns, coefs.tolist()))
        return {}
