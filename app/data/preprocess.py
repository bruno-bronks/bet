"""
app/data/preprocess.py
Limpeza, padronização e enriquecimento básico do DataFrame de partidas.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional

from app.core.constants import REQUIRED_COLUMNS, OPTIONAL_COLUMNS, Competition
from app.core.logger import get_logger
from app.core.utils import add_outcome_column, safe_fillna

logger = get_logger(__name__)


class MatchPreprocessor:
    """
    Pipeline de pré-processamento de dados históricos de partidas.

    Etapas:
      1. Valida colunas obrigatórias
      2. Converte tipos
      3. Remove duplicatas
      4. Remove partidas inválidas (gols negativos, etc.)
      5. Adiciona colunas derivadas básicas
      6. Ordena por data
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        self.competition = competition
        self._n_raw: int = 0
        self._n_processed: int = 0

    # ── Public ────────────────────────────────────────────────────────────────

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica todo o pipeline de pré-processamento."""
        self._n_raw = len(df)
        logger.info(f"[Preprocessor] Starting with {self._n_raw} rows")

        df = df.copy()
        df = self._validate_required_columns(df)
        df = self._cast_types(df)
        df = self._remove_duplicates(df)
        df = self._remove_invalid_rows(df)
        df = self._fill_optional_defaults(df)
        df = self._add_derived_columns(df)
        df = self._sort_by_date(df)

        if self.competition:
            df = df[df["competition"] == self.competition].copy()

        self._n_processed = len(df)
        logger.info(
            f"[Preprocessor] Done. {self._n_processed}/{self._n_raw} rows retained "
            f"({self._n_raw - self._n_processed} removed)"
        )
        return df

    # ── Private ───────────────────────────────────────────────────────────────

    def _validate_required_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return df

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Converte colunas para tipos corretos."""
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce").astype("Int64")
        df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce").astype("Int64")

        int_cols = [
            "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
            "home_corners", "away_corners", "home_yellow_cards", "away_yellow_cards",
            "home_red_cards", "away_red_cards", "home_fouls", "away_fouls",
            "first_half_home_goals", "first_half_away_goals",
            "home_goals_0_15", "away_goals_0_15", "home_goals_75_90", "away_goals_75_90",
            "matchday", "attendance", "minute_first_goal",
        ]
        for col in int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        float_cols = ["home_possession", "away_possession", "home_xg", "away_xg"]
        for col in float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        str_cols = ["home_team", "away_team", "competition", "season"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.title()

        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["match_id"], keep="first")
        removed = before - len(df)
        if removed:
            logger.warning(f"Removed {removed} duplicate match_id rows")
        return df

    def _remove_invalid_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        # Remove linhas com data ou gols inválidos
        df = df.dropna(subset=["date", "home_goals", "away_goals"])
        df = df[df["home_goals"] >= 0]
        df = df[df["away_goals"] >= 0]
        df = df[df["home_team"] != df["away_team"]]  # time não joga contra si mesmo
        removed = before - len(df)
        if removed:
            logger.warning(f"Removed {removed} invalid rows")
        return df

    def _fill_optional_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preenche valores padrão para colunas opcionais ausentes."""
        for col in ["home_red_cards", "away_red_cards"]:
            df = safe_fillna(df, col, 0)
        return df

    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona colunas calculadas a partir dos dados brutos."""
        df = add_outcome_column(df)

        # Gols totais
        df["total_goals"] = df["home_goals"] + df["away_goals"]

        # Resultado binário para cada lado
        df["home_win"] = (df["outcome"] == "H").astype(int)
        df["draw"] = (df["outcome"] == "D").astype(int)
        df["away_win"] = (df["outcome"] == "A").astype(int)

        # Ambas as equipes marcaram
        df["both_teams_scored"] = ((df["home_goals"] > 0) & (df["away_goals"] > 0)).astype(int)

        # Clean sheets
        df["home_clean_sheet"] = (df["away_goals"] == 0).astype(int)
        df["away_clean_sheet"] = (df["home_goals"] == 0).astype(int)

        # Over lines
        for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
            col = f"over_{str(line).replace('.', '_')}"
            df[col] = (df["total_goals"] > line).astype(int)

        # Escanteios totais (se disponível)
        if "home_corners" in df.columns and "away_corners" in df.columns:
            df["total_corners"] = df["home_corners"].fillna(0) + df["away_corners"].fillna(0)

        # Cartões totais
        if "home_yellow_cards" in df.columns:
            df["home_total_cards"] = (
                df.get("home_yellow_cards", 0).fillna(0)
                + df.get("home_red_cards", 0).fillna(0)
            )
            df["away_total_cards"] = (
                df.get("away_yellow_cards", 0).fillna(0)
                + df.get("away_red_cards", 0).fillna(0)
            )
            df["total_cards"] = df["home_total_cards"] + df["away_total_cards"]

        # Gol no 1º tempo (se disponível)
        if "first_half_home_goals" in df.columns and "first_half_away_goals" in df.columns:
            df["first_half_total_goals"] = (
                df["first_half_home_goals"].fillna(0)
                + df["first_half_away_goals"].fillna(0)
            )
            df["goal_in_first_half"] = (df["first_half_total_goals"] > 0).astype(int)

        # Gol nos primeiros 15min
        if "home_goals_0_15" in df.columns and "away_goals_0_15" in df.columns:
            df["goal_0_15"] = (
                (df["home_goals_0_15"].fillna(0) + df["away_goals_0_15"].fillna(0)) > 0
            ).astype(int)

        # Gol nos últimos 15min
        if "home_goals_75_90" in df.columns and "away_goals_75_90" in df.columns:
            df["goal_75_90"] = (
                (df["home_goals_75_90"].fillna(0) + df["away_goals_75_90"].fillna(0)) > 0
            ).astype(int)

        return df

    def _sort_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.sort_values("date").reset_index(drop=True)
