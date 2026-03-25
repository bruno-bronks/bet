"""
app/features/feature_pipeline.py
Pipeline completo de feature engineering — orquestra todos os módulos
e retorna o DataFrame enriquecido pronto para treino/inferência.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.features.rolling_features import compute_rolling_features
from app.features.team_strength import EloRatingSystem, compute_attack_defense_strength, compute_recent_form
from app.features.temporal_features import (
    compute_temporal_features,
    compute_rest_days,
    compute_ucl_stage_features,
    compute_brasileirao_features,
)
from app.features.match_context import (
    compute_head_to_head_features,
    encode_competition,
    compute_home_away_record,
    compute_goal_timing_features,
)

logger = get_logger(__name__)


class FeaturePipeline:
    """
    Orquestra todas as etapas de feature engineering.

    Uso:
        pipeline = FeaturePipeline()
        df_features = pipeline.fit_transform(df_processed)

    Para inferência (sem dados de treino disponíveis):
        features = pipeline.transform_single(match_context_dict)
    """

    # Colunas que identificam uma partida mas NÃO são features
    META_COLUMNS: List[str] = [
        "match_id", "competition", "season", "date",
        "home_team", "away_team", "outcome", "venue", "referee",
        "stage", "attendance",
    ]

    # Targets que não devem vazar para as features
    TARGET_COLUMNS: List[str] = [
        "home_goals", "away_goals", "total_goals",
        "home_win", "draw", "away_win",
        "both_teams_scored", "home_clean_sheet", "away_clean_sheet",
        "over_0_5", "over_1_5", "over_2_5", "over_3_5", "over_4_5",
        "first_half_home_goals", "first_half_away_goals", "first_half_total_goals",
        "goal_in_first_half", "goal_0_15", "goal_75_90",
        "home_total_cards", "away_total_cards", "total_cards",
        "total_corners",
        "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
        "home_corners", "away_corners",
        "home_yellow_cards", "away_yellow_cards",
        "home_red_cards", "away_red_cards",
        "home_fouls", "away_fouls",
        "home_xg", "away_xg",
        # Colunas 0/1 que são targets
        "home_goals_0_15", "away_goals_0_15",
        "home_goals_75_90", "away_goals_75_90",
        "minute_first_goal",
    ]

    def __init__(self, rolling_windows: Optional[List[int]] = None) -> None:
        self.rolling_windows = rolling_windows or settings.ROLLING_WINDOWS
        self.elo_system = EloRatingSystem()
        self._feature_columns: List[str] = []

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica todo o pipeline de features em dados históricos.
        Deve ser chamado UMA VEZ com todos os dados de treino + validação.
        """
        logger.info(f"Feature pipeline: starting with {len(df)} rows")

        df = encode_competition(df)
        df = compute_temporal_features(df)
        df = compute_rest_days(df)
        df = compute_ucl_stage_features(df)
        df = compute_brasileirao_features(df)
        df = self.elo_system.compute_elo_features(df)
        df = compute_attack_defense_strength(df)
        df = compute_recent_form(df, n_matches=settings.RECENT_FORM_MATCHES)
        df = compute_rolling_features(df, windows=self.rolling_windows)
        df = compute_head_to_head_features(df)
        df = compute_home_away_record(df)
        df = compute_goal_timing_features(df)

        # Registra as colunas de feature (exclui meta e targets)
        all_cols = set(df.columns)
        non_feature_cols = set(self.META_COLUMNS) | set(self.TARGET_COLUMNS)
        self._feature_columns = [c for c in df.columns if c not in non_feature_cols]

        logger.info(f"Feature pipeline: {len(self._feature_columns)} feature columns generated")
        return df

    @property
    def feature_columns(self) -> List[str]:
        """Lista de colunas de feature geradas pelo pipeline."""
        return self._feature_columns

    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Retorna apenas as colunas de features numéricas (sem meta e targets)."""
        available = [c for c in self._feature_columns if c in df.columns]
        result = df[available].copy()
        # Remove colunas não-numéricas que possam ter escapado
        non_numeric = result.select_dtypes(exclude=["number"]).columns.tolist()
        if non_numeric:
            logger.warning(f"Dropping non-numeric feature columns: {non_numeric}")
            result = result.drop(columns=non_numeric)
        return result

    def get_target(self, df: pd.DataFrame, target: str) -> pd.Series:
        """Retorna série de target com tratamento de NaN."""
        if target not in df.columns:
            raise KeyError(f"Target column '{target}' not found in DataFrame")
        return df[target].dropna()
