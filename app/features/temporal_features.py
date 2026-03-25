"""
app/features/temporal_features.py
Features temporais: sazonalidade, cansaço, intervalo entre jogos, fase.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

from app.core.logger import get_logger
from app.core.constants import Competition

logger = get_logger(__name__)


def compute_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona features de contexto temporal:
    - dia da semana
    - mês
    - semana do ano
    - is_weekend
    - phase_weight (importância da fase)
    - season_progress (quão avançada está a temporada)
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    df["day_of_week"] = df["date"].dt.dayofweek        # 0=Mon, 6=Sun
    df["month"] = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Peso da fase — maior em fases eliminatórias
    if "stage" in df.columns:
        stage_weights = {
            "group": 1.0,
            "round_of_16": 1.5,
            "quarter_final": 2.0,
            "semi_final": 2.5,
            "final": 3.0,
        }
        df["stage_weight"] = df["stage"].map(stage_weights).fillna(1.0)
    else:
        df["stage_weight"] = 1.0

    # Progresso da temporada — rodada atual / total de rodadas
    if "matchday" in df.columns:
        max_matchday = df.groupby(["competition", "season"])["matchday"].transform("max")
        df["season_progress"] = df["matchday"].fillna(1) / max_matchday.fillna(38)
    else:
        # Estima por posição cronológica dentro da temporada
        df["season_progress"] = (
            df.groupby(["competition", "season"])
            .cumcount() / df.groupby(["competition", "season"])["date"].transform("count")
        )

    return df


def compute_rest_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula dias de descanso desde a última partida de cada time.
    Um intervalo menor indica fadiga potencial.
    """
    df = df.copy().sort_values("date")
    last_game: dict[str, pd.Timestamp] = {}

    home_rest: list[Optional[float]] = []
    away_rest: list[Optional[float]] = []

    for _, row in df.iterrows():
        h, a = row["home_team"], row["away_team"]
        d = pd.Timestamp(row["date"])

        h_rest = (d - last_game[h]).days if h in last_game else None
        a_rest = (d - last_game[a]).days if a in last_game else None

        home_rest.append(h_rest)
        away_rest.append(a_rest)

        last_game[h] = d
        last_game[a] = d

    df["home_rest_days"] = home_rest
    df["away_rest_days"] = away_rest

    # Diferença de descanso (positivo = mandante mais descansado)
    df["rest_advantage"] = (
        pd.to_numeric(df["home_rest_days"], errors="coerce")
        - pd.to_numeric(df["away_rest_days"], errors="coerce")
    )

    # Caps: mais de 30 dias = igual em descanso para efeitos práticos
    df["home_rest_days"] = df["home_rest_days"].clip(upper=30)
    df["away_rest_days"] = df["away_rest_days"].clip(upper=30)

    return df


def compute_ucl_stage_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Features específicas para Champions League:
    - is_group_stage
    - is_knockout
    - is_final
    - leg_number (jogo de ida/volta)
    """
    if "competition" not in df.columns:
        return df

    ucl_mask = df["competition"] == Competition.CHAMPIONS_LEAGUE.value

    if not ucl_mask.any():
        return df

    df = df.copy()
    df["is_group_stage"] = 0
    df["is_knockout"] = 0
    df["is_final"] = 0

    if "stage" in df.columns:
        df.loc[ucl_mask & (df["stage"] == "group"), "is_group_stage"] = 1
        df.loc[ucl_mask & df["stage"].isin(["round_of_16", "quarter_final", "semi_final"]), "is_knockout"] = 1
        df.loc[ucl_mask & (df["stage"] == "final"), "is_final"] = 1

    return df


def compute_brasileirao_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Features específicas para Brasileirão:
    - is_early_season (rodadas 1-10)
    - is_late_season (rodadas 30+)
    - matchday_normalized
    """
    brasa_mask = df.get("competition", pd.Series(dtype=str)) == Competition.BRASILEIRAO.value

    if not brasa_mask.any():
        return df

    df = df.copy()
    df["is_early_season"] = 0
    df["is_late_season"] = 0

    if "matchday" in df.columns:
        df.loc[brasa_mask & (df["matchday"] <= 10), "is_early_season"] = 1
        df.loc[brasa_mask & (df["matchday"] >= 30), "is_late_season"] = 1
        df["matchday_normalized"] = df["matchday"].fillna(19) / 38.0

    return df
