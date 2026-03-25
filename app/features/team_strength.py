"""
app/features/team_strength.py
Features de força relativa dos times:
  - ELO rating simplificado
  - Força ofensiva/defensiva relativa à média da competição
  - Forma recente ponderada
  - Desempenho casa vs. fora
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.core.utils import safe_divide

logger = get_logger(__name__)


# ── ELO Rating ────────────────────────────────────────────────────────────────

class EloRatingSystem:
    """
    Sistema de ELO simplificado para futebol.

    Fórmula: novo_elo = elo_atual + K * (resultado - resultado_esperado)
    Resultado: 1 (vitória), 0.5 (empate), 0 (derrota)
    """

    def __init__(
        self,
        k_factor: float = settings.ELO_K_FACTOR,
        initial_rating: float = settings.ELO_INITIAL_RATING,
        home_advantage: float = settings.ELO_HOME_ADVANTAGE,
    ) -> None:
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.home_advantage = home_advantage
        self.ratings: Dict[str, float] = {}

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, self.initial_rating)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Probabilidade esperada de vitória de A contra B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def update(self, home_team: str, away_team: str, outcome: str) -> Tuple[float, float]:
        """
        Atualiza ELO após uma partida.

        Returns:
            (novo_elo_home, novo_elo_away)
        """
        home_elo = self.get_rating(home_team) + self.home_advantage
        away_elo = self.get_rating(away_team)

        exp_home = self.expected_score(home_elo, away_elo)
        exp_away = 1.0 - exp_home

        actual_home = {"H": 1.0, "D": 0.5, "A": 0.0}[outcome]
        actual_away = 1.0 - actual_home

        new_home = self.get_rating(home_team) + self.k_factor * (actual_home - exp_home)
        new_away = self.get_rating(away_team) + self.k_factor * (actual_away - exp_away)

        self.ratings[home_team] = new_home
        self.ratings[away_team] = new_away
        return new_home, new_away

    def compute_elo_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Percorre o DataFrame em ordem cronológica e calcula ELO pré-jogo.

        IMPORTANTE: O ELO registrado é o ANTES da partida (sem data leakage).
        """
        logger.info("Computing ELO ratings (chronological pass)")
        df = df.copy().sort_values("date").reset_index(drop=True)

        elo_home_pre: list[float] = []
        elo_away_pre: list[float] = []
        elo_diff: list[float] = []

        for _, row in df.iterrows():
            h, a = row["home_team"], row["away_team"]
            h_elo = self.get_rating(h)
            a_elo = self.get_rating(a)

            elo_home_pre.append(h_elo)
            elo_away_pre.append(a_elo)
            elo_diff.append(h_elo - a_elo)

            if "outcome" in row and pd.notna(row["outcome"]):
                self.update(h, a, row["outcome"])

        df["elo_home"] = elo_home_pre
        df["elo_away"] = elo_away_pre
        df["elo_diff"] = elo_diff

        return df


# ── Força Ofensiva e Defensiva ────────────────────────────────────────────────

def compute_attack_defense_strength(
    df: pd.DataFrame, min_matches: int = 5
) -> pd.DataFrame:
    """
    Calcula força ofensiva e defensiva relativa à média da competição/temporada.

    Força ofensiva = média de gols marcados / média da competição
    Força defensiva = média de gols sofridos / média da competição (invertido = melhor se > 1)

    NOTA: Para evitar leakage, usa a temporada ANTERIOR para calcular a média baseline.
    Em produção real, calcule com dados históricos antes da temporada corrente.
    """
    df = df.copy()
    df["season_int"] = pd.to_numeric(
        df["season"].astype(str).str[:4], errors="coerce"
    ).fillna(0).astype(int)

    # Garante que total_goals existe
    if "total_goals" not in df.columns:
        df["total_goals"] = df["home_goals"] + df["away_goals"]

    # Agrupa por time e temporada para calcular médias históricas
    records = []

    for competition in df["competition"].unique():
        comp_df = df[df["competition"] == competition].copy()

        for season in sorted(comp_df["season"].unique()):
            season_df = comp_df[comp_df["season"] == season]
            # Média de gols da competição nesta temporada
            avg_goals = season_df["total_goals"].mean() / 2  # por time

            for team in set(season_df["home_team"]) | set(season_df["away_team"]):
                home_mask = season_df["home_team"] == team
                away_mask = season_df["away_team"] == team

                h_games = season_df[home_mask]
                a_games = season_df[away_mask]

                gf = list(h_games["home_goals"]) + list(a_games["away_goals"])
                ga = list(h_games["away_goals"]) + list(a_games["home_goals"])

                if len(gf) < min_matches:
                    continue

                avg_gf = np.mean(gf)
                avg_ga = np.mean(ga)

                records.append({
                    "competition": competition,
                    "season": season,
                    "team": team,
                    "attack_strength": safe_divide(avg_gf, avg_goals, 1.0),
                    "defense_strength": safe_divide(avg_goals, avg_ga, 1.0),  # > 1 = melhor defesa
                    "avg_gf": avg_gf,
                    "avg_ga": avg_ga,
                })

    if not records:
        logger.warning("No attack/defense strength records computed")
        return df

    strength_df = pd.DataFrame(records)

    # Merge para home team
    df = df.merge(
        strength_df.rename(columns={
            "team": "home_team",
            "attack_strength": "home_attack_str",
            "defense_strength": "home_defense_str",
            "avg_gf": "home_avg_gf",
            "avg_ga": "home_avg_ga",
        }),
        on=["competition", "season", "home_team"],
        how="left",
    )

    # Merge para away team
    df = df.merge(
        strength_df.rename(columns={
            "team": "away_team",
            "attack_strength": "away_attack_str",
            "defense_strength": "away_defense_str",
            "avg_gf": "away_avg_gf",
            "avg_ga": "away_avg_ga",
        }),
        on=["competition", "season", "away_team"],
        how="left",
    )

    # Features derivadas: diferença e razão de forças
    df["attack_str_diff"] = df["home_attack_str"].fillna(1.0) - df["away_attack_str"].fillna(1.0)
    df["defense_str_diff"] = df["home_defense_str"].fillna(1.0) - df["away_defense_str"].fillna(1.0)

    return df


# ── Forma Recente Ponderada ───────────────────────────────────────────────────

def compute_recent_form(
    df: pd.DataFrame, n_matches: int = 5, weights: Optional[list] = None
) -> pd.DataFrame:
    """
    Calcula forma recente como média ponderada dos resultados.
    Vitória=3pts, Empate=1pt, Derrota=0pts — normalizado por máximo possível.
    """
    if weights is None:
        # Pesos decrescentes: jogo mais recente tem mais peso
        weights = list(range(n_matches, 0, -1))

    df = df.copy().sort_values("date")
    home_form: Dict[str, list] = {}
    away_form: Dict[str, list] = {}

    home_form_vals: list[float] = []
    away_form_vals: list[float] = []
    home_home_form: list[float] = []  # Forma apenas como mandante
    away_away_form: list[float] = []  # Forma apenas como visitante

    for _, row in df.iterrows():
        h, a = row["home_team"], row["away_team"]

        # Forma geral
        h_pts = _weighted_form(home_form.get(h, []), weights)
        a_pts = _weighted_form(away_form.get(a, []), weights)
        home_form_vals.append(h_pts)
        away_form_vals.append(a_pts)

        # Forma casa/fora
        home_home_form.append(_weighted_form(home_form.get(f"{h}_home", []), weights))
        away_away_form.append(_weighted_form(away_form.get(f"{a}_away", []), weights))

        # Atualiza listas com resultado desta partida
        outcome = row.get("outcome", None)
        if pd.notna(outcome):
            h_pts_earned = {"H": 3, "D": 1, "A": 0}[outcome]
            a_pts_earned = {"H": 0, "D": 1, "A": 3}[outcome]

            for team_key, pts in [(h, h_pts_earned), (a, a_pts_earned)]:
                for d in [home_form, away_form]:
                    if team_key not in d:
                        d[team_key] = []
                    d[team_key] = (d[team_key] + [pts])[-n_matches:]

            home_form[f"{h}_home"] = (home_form.get(f"{h}_home", []) + [h_pts_earned])[-n_matches:]
            away_form[f"{a}_away"] = (away_form.get(f"{a}_away", []) + [a_pts_earned])[-n_matches:]

    df["home_form"] = home_form_vals
    df["away_form"] = away_form_vals
    df["home_home_form"] = home_home_form
    df["away_away_form"] = away_away_form
    df["form_diff"] = df["home_form"] - df["away_form"]

    return df


def _weighted_form(history: list, weights: list) -> float:
    """Calcula forma ponderada. Retorna 0.0 se histórico vazio."""
    if not history:
        return 0.0
    # Usa os últimos len(weights) jogos
    recent = history[-len(weights):]
    w = weights[-len(recent):]
    max_pts = sum(w) * 3
    earned = sum(p * wt for p, wt in zip(recent, w))
    return safe_divide(earned, max_pts, 0.0)
