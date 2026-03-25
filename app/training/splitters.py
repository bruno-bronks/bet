"""
app/training/splitters.py
Splitters temporais para dados esportivos.
NUNCA usar split aleatório — viola a causalidade (data leakage futuro).
"""
from __future__ import annotations

from typing import Generator, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import BaseCrossValidator

from app.core.logger import get_logger

logger = get_logger(__name__)


class TemporalSplit:
    """
    Divide dados em treino/validação/teste respeitando ordem temporal.

    Garante que:
      - Treino sempre precede validação
      - Validação sempre precede teste
      - Nenhum dado futuro contamina dados passados
    """

    def __init__(
        self,
        test_size: float = 0.2,
        val_size: float = 0.1,
        date_column: str = "date",
    ) -> None:
        self.test_size = test_size
        self.val_size = val_size
        self.date_column = date_column

    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Retorna (train_df, val_df, test_df) em ordem cronológica.
        """
        df_sorted = df.sort_values(self.date_column).reset_index(drop=True)
        n = len(df_sorted)

        n_test = max(1, int(n * self.test_size))
        n_val = max(1, int(n * self.val_size))
        n_train = n - n_test - n_val

        if n_train < 10:
            logger.warning(f"Train set has only {n_train} samples — consider using more data")

        train = df_sorted.iloc[:n_train]
        val = df_sorted.iloc[n_train: n_train + n_val]
        test = df_sorted.iloc[n_train + n_val:]

        logger.info(
            f"Temporal split: train={len(train)} ({train[self.date_column].min().date()} → "
            f"{train[self.date_column].max().date()}) | "
            f"val={len(val)} | test={len(test)}"
        )
        return train, val, test


class ExpandingWindowCV(BaseCrossValidator):
    """
    Cross-validation com janela expansível (walk-forward validation).

    Para cada fold:
      - Treino = todos os dados até o ponto de corte
      - Validação = próximas N partidas

    Ideal para backtesting temporal.
    """

    def __init__(
        self,
        n_splits: int = 5,
        min_train_size: int = 50,
        date_column: str = "date",
    ) -> None:
        self.n_splits = n_splits
        self.min_train_size = min_train_size
        self.date_column = date_column

    def split(
        self, X: pd.DataFrame, y=None, groups=None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n = len(X)
        fold_size = max(1, (n - self.min_train_size) // self.n_splits)

        for i in range(self.n_splits):
            train_end = self.min_train_size + i * fold_size
            val_end = min(train_end + fold_size, n)

            if train_end >= n:
                break

            train_idx = np.arange(0, train_end)
            val_idx = np.arange(train_end, val_end)
            yield train_idx, val_idx

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits
