"""
app/training/datasets.py
Utilitários para montagem de datasets de treino por modelo.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

from app.core.logger import get_logger
from app.features.feature_pipeline import FeaturePipeline

logger = get_logger(__name__)


def build_training_dataset(
    df: pd.DataFrame,
    pipeline: FeaturePipeline,
    target_columns: Optional[list] = None,
    min_samples: int = 30,
) -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
    """
    Constrói o dataset de treino aplicando o feature pipeline.

    Returns:
        (X, targets_dict) onde targets_dict mapeia nome → Series.
    """
    df_feat = pipeline.fit_transform(df)
    X = pipeline.get_feature_matrix(df_feat)

    if target_columns is None:
        target_columns = [
            "outcome", "home_goals", "away_goals",
            "home_corners", "away_corners", "total_corners",
            "home_total_cards", "away_total_cards", "total_cards",
            "goal_0_15", "goal_75_90", "goal_in_first_half",
        ]

    targets: Dict[str, pd.Series] = {}
    for col in target_columns:
        if col in df_feat.columns:
            series = df_feat[col].dropna()
            if len(series) >= min_samples:
                targets[col] = series
            else:
                logger.warning(f"Target '{col}' has only {len(series)} non-null samples — skipped")

    logger.info(f"Dataset built: X={X.shape} | targets={list(targets.keys())}")
    return X, targets
