"""
app/features/base_features.py
Transformer base compatível com scikit-learn para uso em Pipelines.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


class FootballFeatureTransformer(BaseEstimator, TransformerMixin):
    """
    Transformador sklearn-compatível que:
    1. Seleciona colunas de feature relevantes
    2. Preenche NaN com mediana (numéricos) ou moda (categóricos)
    3. Aplica clip em outliers extremos
    """

    def __init__(
        self,
        feature_columns: Optional[List[str]] = None,
        clip_std_factor: float = 5.0,
    ) -> None:
        self.feature_columns = feature_columns
        self.clip_std_factor = clip_std_factor
        self._medians: dict = {}
        self._clip_bounds: dict = {}
        self._fitted_columns: List[str] = []

    def fit(self, X: pd.DataFrame, y=None) -> "FootballFeatureTransformer":
        cols = self.feature_columns or list(X.select_dtypes(include=[np.number]).columns)
        self._fitted_columns = [c for c in cols if c in X.columns]

        for col in self._fitted_columns:
            col_data = X[col].dropna()
            if col_data.empty:
                self._medians[col] = 0.0
                self._clip_bounds[col] = (-np.inf, np.inf)
            else:
                median = float(col_data.median())
                std = float(col_data.std()) or 1.0
                self._medians[col] = median
                self._clip_bounds[col] = (
                    median - self.clip_std_factor * std,
                    median + self.clip_std_factor * std,
                )
        return self

    def transform(self, X: pd.DataFrame, y=None) -> np.ndarray:
        X = X.copy()
        available = [c for c in self._fitted_columns if c in X.columns]

        # Adiciona colunas ausentes com mediana
        for col in self._fitted_columns:
            if col not in X.columns:
                X[col] = self._medians.get(col, 0.0)

        X = X[self._fitted_columns]

        for col in self._fitted_columns:
            X[col] = X[col].fillna(self._medians.get(col, 0.0))
            lo, hi = self._clip_bounds.get(col, (-np.inf, np.inf))
            X[col] = X[col].clip(lo, hi)

        return X.values.astype(np.float32)

    def get_feature_names_out(self) -> np.ndarray:
        return np.array(self._fitted_columns)
