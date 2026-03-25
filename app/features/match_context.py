"""
app/features/match_context.py
Features de contexto da partida: H2H, localização, competição codificada.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional

from app.core.logger import get_logger
from app.core.utils import safe_divide

logger = get_logger(__name__)


def compute_head_to_head_features(df: pd.DataFrame, n_last: int = 5) -> pd.DataFrame:
    """
    Features de confronto direto (H2H) entre os dois times.
    Calcula vitórias/empates/derrotas do mandante nos últimos N encontros.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    h2h_home_wins: list[float] = []
    h2h_draws: list[float] = []
    h2h_away_wins: list[float] = []
    h2h_avg_goals: list[float] = []

    for idx, row in df.iterrows():
        h, a = row["home_team"], row["away_team"]
        match_date = row["date"]

        # Confrontos anteriores entre esses times (em qualquer ordem)
        past = df[
            (df["date"] < match_date)
            & (
                ((df["home_team"] == h) & (df["away_team"] == a))
                | ((df["home_team"] == a) & (df["away_team"] == h))
            )
        ].tail(n_last)

        if past.empty or "total_goals" not in past.columns:
            h2h_home_wins.append(0.0)
            h2h_draws.append(0.0)
            h2h_away_wins.append(0.0)
            h2h_avg_goals.append(2.5)  # prior neutro
            continue

        wins = draws = losses = 0
        for _, p in past.iterrows():
            if p["home_team"] == h:
                outcome = p["outcome"]
            else:
                # Time estava como visitante nessa partida — inverte
                outcome = {"H": "A", "D": "D", "A": "H"}[p["outcome"]]

            if outcome == "H":
                wins += 1
            elif outcome == "D":
                draws += 1
            else:
                losses += 1

        n = len(past)
        h2h_home_wins.append(wins / n)
        h2h_draws.append(draws / n)
        h2h_away_wins.append(losses / n)
        tg = past["total_goals"] if "total_goals" in past.columns else (past["home_goals"] + past["away_goals"])
        h2h_avg_goals.append(tg.mean())

    df["h2h_home_win_rate"] = h2h_home_wins
    df["h2h_draw_rate"] = h2h_draws
    df["h2h_away_win_rate"] = h2h_away_wins
    df["h2h_avg_goals"] = h2h_avg_goals

    return df


def encode_competition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Codifica competição como variável numérica (label encoding simples).
    Adiciona flag binária para cada competição.
    """
    df = df.copy()
    comp_map = {"brasileirao": 0, "champions_league": 1}
    df["competition_id"] = df["competition"].map(comp_map).fillna(0).astype(int)
    df["is_ucl"] = (df["competition"] == "champions_league").astype(int)
    df["is_brasileirao"] = (df["competition"] == "brasileirao").astype(int)
    return df


def compute_home_away_record(df: pd.DataFrame, n_last: int = 10) -> pd.DataFrame:
    """
    Taxa de vitória em casa (mandante) e fora (visitante) nos últimos N jogos.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    home_win_rate: list[float] = []
    away_win_rate: list[float] = []

    # Histórico acumulado
    home_history: dict[str, list[int]] = {}
    away_history: dict[str, list[int]] = {}

    for _, row in df.iterrows():
        h, a = row["home_team"], row["away_team"]

        h_hist = home_history.get(h, [])
        a_hist = away_history.get(a, [])

        home_win_rate.append(safe_divide(sum(h_hist[-n_last:]), min(len(h_hist), n_last), 0.5))
        away_win_rate.append(safe_divide(sum(a_hist[-n_last:]), min(len(a_hist), n_last), 0.5))

        if "outcome" in row and pd.notna(row["outcome"]):
            home_history.setdefault(h, []).append(1 if row["outcome"] == "H" else 0)
            away_history.setdefault(a, []).append(1 if row["outcome"] == "A" else 0)

    df["home_win_rate_home"] = home_win_rate
    df["away_win_rate_away"] = away_win_rate

    return df


def compute_goal_timing_features(df: pd.DataFrame, n_last: int = 10) -> pd.DataFrame:
    """
    Taxas históricas de gol em faixas temporais específicas.
    """
    df = df.copy().sort_values("date")

    if "goal_0_15" not in df.columns and "goal_75_90" not in df.columns:
        logger.debug("Time-window goal columns not found — skipping goal timing features")
        return df

    for col in ["goal_0_15", "goal_75_90", "goal_in_first_half"]:
        if col not in df.columns:
            continue

        # Médias globais por competição como prior
        global_rate = df.groupby("competition")[col].transform("mean")
        df[f"competition_avg_{col}"] = global_rate

    return df
