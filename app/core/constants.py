"""
app/core/constants.py
Constantes do domínio: nomes de competições, colunas obrigatórias,
eventos estimados, fases e categorias de modelos.
"""
from __future__ import annotations

from enum import Enum
from typing import Final

# ── Competições ───────────────────────────────────────────────────────────────

class Competition(str, Enum):
    BRASILEIRAO = "brasileirao"
    CHAMPIONS_LEAGUE = "champions_league"


# ── Fases do Brasileirão ──────────────────────────────────────────────────────

class BrasileiraoDivision(str, Enum):
    SERIE_A = "serie_a"
    SERIE_B = "serie_b"


# ── Fases da Champions League ─────────────────────────────────────────────────

class UCLStage(str, Enum):
    GROUP = "group"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    FINAL = "final"


# ── Resultado da partida ──────────────────────────────────────────────────────

class MatchOutcome(str, Enum):
    HOME_WIN = "H"
    DRAW = "D"
    AWAY_WIN = "A"


# ── Colunas obrigatórias no dataset de entrada ────────────────────────────────

REQUIRED_COLUMNS: Final[list[str]] = [
    "match_id",
    "competition",
    "season",
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
]

# ── Colunas opcionais (enriquecem os modelos) ─────────────────────────────────

OPTIONAL_COLUMNS: Final[list[str]] = [
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_corners",
    "away_corners",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",
    "home_fouls",
    "away_fouls",
    "home_possession",
    "away_possession",
    "home_xg",        # Expected Goals (opcional, quando disponível)
    "away_xg",
    "stage",          # fase do campeonato
    "matchday",       # rodada (Brasileirão)
    "attendance",
    "venue",
    "referee",
    "first_half_home_goals",
    "first_half_away_goals",
    "minute_first_goal",  # minuto do primeiro gol (0 se não houve)
    "home_goals_0_15",    # gols nos primeiros 15 min
    "away_goals_0_15",
    "home_goals_75_90",   # gols nos últimos 15 min
    "away_goals_75_90",
]

# ── Eventos que o sistema estima ──────────────────────────────────────────────

ESTIMATED_EVENTS: Final[list[str]] = [
    "home_win",
    "draw",
    "away_win",
    "expected_goals_home",
    "expected_goals_away",
    "total_goals_expected",
    "over_1_5",
    "over_2_5",
    "over_3_5",
    "both_teams_score",
    "clean_sheet_home",
    "clean_sheet_away",
    "expected_corners",
    "expected_corners_home",
    "expected_corners_away",
    "expected_cards",
    "expected_cards_home",
    "expected_cards_away",
    "goal_first_15min",
    "goal_last_15min",
    "goal_first_half",
    "goal_second_half",
    "top_scorelines",
]

# ── Janelas temporais de jogo (em minutos) ────────────────────────────────────

TIME_WINDOWS: Final[dict[str, tuple[int, int]]] = {
    "0_15": (0, 15),
    "15_30": (15, 30),
    "30_45": (30, 45),
    "45_60": (45, 60),
    "60_75": (60, 75),
    "75_90": (75, 90),
    "first_half": (0, 45),
    "second_half": (45, 90),
}

# ── Tipos de modelos no registry ─────────────────────────────────────────────

class ModelType(str, Enum):
    OUTCOME = "outcome"          # 1X2
    GOALS = "goals"              # Poisson para gols
    CORNERS = "corners"          # Escanteios
    CARDS = "cards"              # Cartões
    TIME_WINDOW = "time_window"  # Evento por faixa temporal

# ── Linhas de Over/Under padrão ───────────────────────────────────────────────

GOAL_LINES: Final[list[float]] = [0.5, 1.5, 2.5, 3.5, 4.5]

# ── Scores prováveis máximos para enumerar ────────────────────────────────────

MAX_GOALS_PER_TEAM: Final[int] = 6
