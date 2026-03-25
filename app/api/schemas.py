"""
app/api/schemas.py
Schemas Pydantic para request/response da API FastAPI.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ───────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    """Payload de entrada para /predict."""
    competition: str = Field(
        ...,
        description="Competição: 'brasileirao' ou 'champions_league'",
        examples=["brasileirao"],
    )
    home_team: str = Field(..., min_length=2, description="Nome do time mandante")
    away_team: str = Field(..., min_length=2, description="Nome do time visitante")
    match_date: date = Field(..., description="Data da partida (YYYY-MM-DD)")
    stage: Optional[str] = Field(None, description="Fase (group, round_of_16, etc.)")
    matchday: Optional[int] = Field(None, ge=1, le=40)
    include_explanation: bool = Field(False, description="Inclui explicação em linguagem natural")

    @field_validator("competition")
    @classmethod
    def validate_competition(cls, v: str) -> str:
        allowed = {"brasileirao", "champions_league"}
        if v.lower() not in allowed:
            raise ValueError(f"competition must be one of {allowed}")
        return v.lower()

    @field_validator("home_team", "away_team", mode="before")
    @classmethod
    def normalize_team(cls, v: str) -> str:
        return v.strip()  # .title() removido — quebrava siglas como RB, SE, CR, CA, EC


class TrainRequest(BaseModel):
    """Payload para /train."""
    competition: str = Field(..., description="Competição a treinar")
    data_path: Optional[str] = Field(None, description="Caminho para CSV de dados (usa processed/ se omitido)")
    force_retrain: bool = Field(False, description="Força re-treino mesmo se modelo existir")


# ── Response Schemas ──────────────────────────────────────────────────────────

class OutcomeProbs(BaseModel):
    home_win: float
    draw: float
    away_win: float


class GoalsInfo(BaseModel):
    expected_goals_home: float
    expected_goals_away: float
    expected_goals_total: float
    over_0_5: float
    over_1_5: float
    over_2_5: float
    over_3_5: float
    over_4_5: float
    both_teams_score: float
    clean_sheet_home: float
    clean_sheet_away: float
    top_scorelines: List[Dict[str, Any]] = []


class CornersInfo(BaseModel):
    expected_corners_total: float
    expected_corners_home: float
    expected_corners_away: float


class CardsInfo(BaseModel):
    expected_cards_total: float
    expected_cards_home: float
    expected_cards_away: float


class TimeWindowsInfo(BaseModel):
    goal_first_15min: float
    goal_last_15min: float
    goal_first_half: float
    goal_second_half: float


class ExplainabilityInfo(BaseModel):
    top_features: List[Dict[str, Any]] = []
    confidence_score: float
    low_confidence_warning: bool


class PredictResponse(BaseModel):
    """Resposta completa de /predict."""
    match: Dict[str, Any]
    outcome: OutcomeProbs
    goals: GoalsInfo
    corners: CornersInfo
    cards: CardsInfo
    time_windows: TimeWindowsInfo
    explainability: ExplainabilityInfo
    warnings: List[str] = []
    natural_language_explanation: Optional[str] = None
    disclaimer: str = (
        "Estimativas probabilísticas baseadas em padrões históricos. "
        "Não constituem previsão garantida."
    )


class TrainResponse(BaseModel):
    status: str
    competition: str
    metrics: Dict[str, Any] = {}
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    supported_competitions: List[str]


class ModelListItem(BaseModel):
    model_config = {'protected_namespaces': ()}
    key: str
    competition: str
    model_type: str
    path: Optional[str] = None
    metrics: Dict[str, Any] = {}


class ModelsResponse(BaseModel):
    models: List[ModelListItem]
    total: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ── Fixtures / Standings Schemas ──────────────────────────────────────────────

class OutcomeProbsSlim(BaseModel):
    """Probabilidades 1X2 resumidas para exibição inline."""
    home_win: float
    draw: float
    away_win: float


class RefereeStats(BaseModel):
    """Estatísticas de cartões de um árbitro na competição."""
    name: str
    matches_analyzed: int
    avg_yellow_per_game: float
    avg_red_per_game: float
    avg_cards_per_game: float
    # Média com este árbitro por time
    avg_cards_home_team: Optional[float] = None
    avg_cards_away_team: Optional[float] = None
    home_team_matches: int = 0
    away_team_matches: int = 0
    # Média geral do time na temporada (para comparação)
    home_team_general_avg_cards: Optional[float] = None
    away_team_general_avg_cards: Optional[float] = None


class FixtureItem(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    home_team_logo: str = ""
    away_team_logo: str = ""
    date: str          # YYYY-MM-DD
    time: str          # HH:MM (horário local Brasília)
    matchday: Optional[int] = None
    stage: str = ""
    venue: str = ""
    status: str = "NS"
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    referee: Optional[str] = None


class FixtureWithPrediction(FixtureItem):
    prediction: Optional[OutcomeProbsSlim] = None


class StandingItem(BaseModel):
    position: int
    team: str
    team_logo: str = ""
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int
    form: str = ""
    description: str = ""


class StandingsResponse(BaseModel):
    competition: str
    season: int
    standings: List[StandingItem]


class FixturesResponse(BaseModel):
    competition: str
    season_label: str = ""
    count: int
    fixtures: List[FixtureWithPrediction]


class RecentResponse(BaseModel):
    competition: str
    count: int
    fixtures: List[FixtureItem]


class TeamCardStats(BaseModel):
    """Média de cartões dos times na temporada, por papel no jogo."""
    # Mandante: média quando joga em casa
    home_as_home: Optional[float] = None
    # Visitante: média quando joga fora
    away_as_away: Optional[float] = None
    # Média geral (casa+fora) — fallback
    home_avg: Optional[float] = None
    away_avg: Optional[float] = None


# ── History / Backtesting Schemas ─────────────────────────────────────────────

class MatchActual(BaseModel):
    """Resultado real de uma partida finalizada."""
    home_goals: int
    away_goals: int
    outcome: str               # "H", "D", "A"
    total_goals: int
    btts: bool                 # ambas marcaram
    home_cards: Optional[int] = None
    away_cards: Optional[int] = None
    total_cards: Optional[int] = None
    home_corners: Optional[int] = None
    away_corners: Optional[int] = None
    total_corners: Optional[int] = None
    first_half_goals: Optional[int] = None
    goal_first_half: Optional[bool] = None


class MatchPredSummary(BaseModel):
    """Resumo das previsões do modelo para um jogo passado."""
    home_win: float
    draw: float
    away_win: float
    predicted_outcome: str     # "H", "D", "A" (maior probabilidade)
    over_2_5: float
    btts: float
    expected_home_goals: float
    expected_away_goals: float
    expected_total_cards: float
    expected_total_corners: float
    goal_first_half: float


class MatchAccuracy(BaseModel):
    """Comparação previsão vs real."""
    outcome_correct: bool
    over_2_5_correct: Optional[bool] = None
    btts_correct: Optional[bool] = None
    cards_diff: Optional[float] = None    # |previsto – real|
    corners_diff: Optional[float] = None
    first_half_correct: Optional[bool] = None


class HistoryMatch(BaseModel):
    date: str
    matchday: Optional[int] = None
    stage: Optional[str] = None
    home_team: str
    away_team: str
    actual: MatchActual
    prediction: Optional[MatchPredSummary] = None
    accuracy: Optional[MatchAccuracy] = None


class HistorySummary(BaseModel):
    total_matches: int
    outcome_accuracy: Optional[float] = None   # 0.0–1.0
    over_2_5_accuracy: Optional[float] = None
    btts_accuracy: Optional[float] = None
    avg_cards_diff: Optional[float] = None
    avg_corners_diff: Optional[float] = None


class HistoryResponse(BaseModel):
    competition: str
    season: Optional[int] = None
    count: int
    matches: List[HistoryMatch]
    summary: HistorySummary
