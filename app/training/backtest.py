"""
app/training/backtest.py
Backtesting temporal: simula previsões em janelas históricas
para validar a qualidade preditiva do sistema ao longo do tempo.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from app.features.feature_pipeline import FeaturePipeline
from app.models.outcome_model import OutcomeModel
from app.models.calibration import brier_score, log_loss_safe
from app.training.splitters import ExpandingWindowCV

logger = get_logger(__name__)


class Backtester:
    """
    Backtesting com janela expansível (walk-forward).

    Para cada fold:
      1. Treina modelo nos dados passados
      2. Prediz nos dados futuros imediatos
      3. Computa métricas

    Retorna DataFrame de resultados com métricas por fold.
    """

    def __init__(
        self,
        competition: str,
        n_splits: int = 5,
        min_train_size: int = 100,
    ) -> None:
        self.competition = competition
        self.n_splits = n_splits
        self.min_train_size = min_train_size

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Executa backtesting completo.

        Returns:
            DataFrame com métricas por fold: accuracy, brier_score, log_loss.
        """
        logger.info(
            f"Starting backtest for {self.competition} | {len(df)} matches | {self.n_splits} folds"
        )

        df = df.sort_values("date").reset_index(drop=True)

        cv = ExpandingWindowCV(
            n_splits=self.n_splits,
            min_train_size=self.min_train_size,
        )

        results: List[Dict] = []

        for fold_idx, (train_idx, val_idx) in enumerate(cv.split(df)):
            train_df = df.iloc[train_idx].copy()
            val_df = df.iloc[val_idx].copy()

            fold_date_min = val_df["date"].min()
            fold_date_max = val_df["date"].max()

            try:
                # Feature engineering independente por fold
                pipeline = FeaturePipeline()
                train_feat = pipeline.fit_transform(train_df)
                val_feat = pipeline.fit_transform(pd.concat([train_df, val_df]))
                val_feat = val_feat.iloc[len(train_df):]

                X_train = pipeline.get_feature_matrix(train_feat)
                X_val = pipeline.get_feature_matrix(val_feat)

                y_train = train_feat["outcome"].dropna()
                y_val = val_feat["outcome"].dropna()
                X_train = X_train.loc[y_train.index]
                X_val_aligned = X_val.loc[y_val.index]

                if len(y_train) < 10 or len(y_val) < 3:
                    logger.warning(f"Fold {fold_idx}: insufficient data — skipping")
                    continue

                model = OutcomeModel(competition=self.competition)
                model.fit(X_train, y_train)

                y_pred = model.predict(X_val_aligned)
                y_prob = model.predict_proba(X_val_aligned)

                acc = float((y_pred == y_val.values).mean())

                # Brier Score multiclasse
                classes = list(model._label_encoder.classes_)
                ohe = pd.get_dummies(y_val).reindex(columns=classes, fill_value=0).values
                bs = float(np.mean(np.sum((y_prob - ohe) ** 2, axis=1)))

                results.append({
                    "fold": fold_idx,
                    "train_n": len(y_train),
                    "val_n": len(y_val),
                    "val_date_min": fold_date_min.date() if hasattr(fold_date_min, "date") else fold_date_min,
                    "val_date_max": fold_date_max.date() if hasattr(fold_date_max, "date") else fold_date_max,
                    "accuracy": round(acc, 4),
                    "brier_score": round(bs, 4),
                })
                logger.info(
                    f"  Fold {fold_idx}: n_val={len(y_val)} | "
                    f"acc={acc:.3f} | brier={bs:.4f} | "
                    f"period={fold_date_min.date()} → {fold_date_max.date()}"
                )

            except Exception as e:
                logger.error(f"Fold {fold_idx} failed: {e}", exc_info=True)

        results_df = pd.DataFrame(results)

        if not results_df.empty:
            logger.info(
                f"Backtest summary | mean_accuracy={results_df['accuracy'].mean():.3f} | "
                f"mean_brier={results_df['brier_score'].mean():.4f}"
            )

        return results_df
