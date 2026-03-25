"""
app/features/rolling_features.py
Médias móveis por múltiplas janelas temporais — sem data leakage.
"""
from __future__ import annotations

from typing import List

import pandas as pd

from app.core.logger import get_logger

logger = get_logger(__name__)


def compute_rolling_features(
    df: pd.DataFrame,
    windows: List[int] | None = None,
) -> pd.DataFrame:
    """
    Calcula médias móveis para múltiplas janelas (e.g. [3, 5, 10]).
    Usa shift(1) em cada série por time para evitar data leakage do jogo atual.

    Colunas produzidas (por janela w):
        home_goals_scored_roll{w}, home_goals_conceded_roll{w}
        away_goals_scored_roll{w}, away_goals_conceded_roll{w}
        home_corners_roll{w}, away_corners_roll{w}   (se disponível)
        home_cards_roll{w},   away_cards_roll{w}     (se disponível)
    """
    if windows is None:
        windows = [3, 5, 10]

    df = df.copy().sort_values("date").reset_index(drop=True)

    # Mapeamento: (side, stat_label) → (coluna do mandante, coluna do visitante)
    stat_map: List[tuple] = []

    if "home_goals" in df.columns and "away_goals" in df.columns:
        stat_map += [
            ("goals_scored",   "home_goals", "away_goals"),  # gols marcados pelo time
            ("goals_conceded", "away_goals", "home_goals"),  # gols sofridos pelo time
        ]
    if "home_corners" in df.columns and "away_corners" in df.columns:
        stat_map += [
            ("corners", "home_corners", "away_corners"),
        ]
    if "home_total_cards" in df.columns and "away_total_cards" in df.columns:
        stat_map += [
            ("cards", "home_total_cards", "away_total_cards"),
        ]
    elif "home_yellow_cards" in df.columns:
        # Fallback: soma de amarelos + vermelhos
        df["home_total_cards"] = df.get("home_yellow_cards", 0) + df.get("home_red_cards", 0)
        df["away_total_cards"] = df.get("away_yellow_cards", 0) + df.get("away_red_cards", 0)
        stat_map += [
            ("cards", "home_total_cards", "away_total_cards"),
        ]

    if not stat_map:
        logger.warning("compute_rolling_features: no stat columns found — skipping")
        return df

    # Para cada time, calcula rolling nas suas partidas (casa + fora)
    all_teams = pd.concat([df["home_team"], df["away_team"]]).unique()

    for stat_label, home_col, away_col in stat_map:
        # Dicionários: match_index → valor rolling para home e away
        home_rolling: dict[int, dict[int, float]] = {w: {} for w in windows}
        away_rolling: dict[int, dict[int, float]] = {w: {} for w in windows}

        for team in all_teams:
            home_mask = df["home_team"] == team
            away_mask = df["away_team"] == team

            # Série cronológica de gols marcados (home_col quando mandante, away_col quando visitante)
            home_idx = df.index[home_mask].tolist()
            away_idx = df.index[away_mask].tolist()

            all_idx = sorted(home_idx + away_idx, key=lambda i: df.loc[i, "date"])

            if not all_idx:
                continue

            # Valores por jogo (0 quando coluna não existe → já filtrado acima)
            values = []
            for i in all_idx:
                if i in home_idx:
                    values.append(df.loc[i, home_col] if pd.notna(df.loc[i, home_col]) else 0.0)
                else:
                    values.append(df.loc[i, away_col] if pd.notna(df.loc[i, away_col]) else 0.0)

            series = pd.Series(values, index=all_idx, dtype=float)

            for w in windows:
                rolled = series.shift(1).rolling(w, min_periods=1).mean()

                for i, val in rolled.items():
                    if i in home_idx:
                        home_rolling[w][i] = val
                    else:
                        away_rolling[w][i] = val

        for w in windows:
            df[f"home_{stat_label}_roll{w}"] = pd.Series(home_rolling[w]).reindex(df.index)
            df[f"away_{stat_label}_roll{w}"] = pd.Series(away_rolling[w]).reindex(df.index)

    logger.debug(
        f"Rolling features: {len(stat_map)} stats × {len(windows)} windows "
        f"= {len(stat_map) * len(windows) * 2} new columns"
    )
    return df
