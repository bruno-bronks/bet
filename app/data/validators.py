"""
app/data/validators.py
Validação e schema de entrada de dados de partidas via Pydantic.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import Competition


class MatchRecord(BaseModel):
    """
    Schema de uma partida histórica.
    Colunas obrigatórias + opcionais claramente tipadas.
    """

    # ── Obrigatórios ─────────────────────────────────────────────────────────
    match_id: str = Field(..., description="Identificador único da partida")
    competition: Competition = Field(..., description="Competição: brasileirao | champions_league")
    season: str = Field(..., description="Temporada (ex: '2023' ou '2023/24')")
    date: date = Field(..., description="Data da partida (YYYY-MM-DD)")
    home_team: str = Field(..., min_length=2, description="Nome do time mandante")
    away_team: str = Field(..., min_length=2, description="Nome do time visitante")
    home_goals: int = Field(..., ge=0, le=20)
    away_goals: int = Field(..., ge=0, le=20)

    # ── Estatísticas de jogo (opcionais) ─────────────────────────────────────
    home_shots: Optional[int] = Field(None, ge=0, le=60)
    away_shots: Optional[int] = Field(None, ge=0, le=60)
    home_shots_on_target: Optional[int] = Field(None, ge=0, le=30)
    away_shots_on_target: Optional[int] = Field(None, ge=0, le=30)
    home_corners: Optional[int] = Field(None, ge=0, le=30)
    away_corners: Optional[int] = Field(None, ge=0, le=30)
    home_yellow_cards: Optional[int] = Field(None, ge=0, le=11)
    away_yellow_cards: Optional[int] = Field(None, ge=0, le=11)
    home_red_cards: Optional[int] = Field(None, ge=0, le=11)
    away_red_cards: Optional[int] = Field(None, ge=0, le=11)
    home_fouls: Optional[int] = Field(None, ge=0, le=50)
    away_fouls: Optional[int] = Field(None, ge=0, le=50)
    home_possession: Optional[float] = Field(None, ge=0.0, le=100.0)
    away_possession: Optional[float] = Field(None, ge=0.0, le=100.0)
    home_xg: Optional[float] = Field(None, ge=0.0, le=10.0, description="Expected Goals mandante")
    away_xg: Optional[float] = Field(None, ge=0.0, le=10.0, description="Expected Goals visitante")

    # ── Contexto da partida ───────────────────────────────────────────────────
    stage: Optional[str] = Field(None, description="Fase do campeonato")
    matchday: Optional[int] = Field(None, ge=1, le=40, description="Rodada (Brasileirão)")
    attendance: Optional[int] = Field(None, ge=0)
    venue: Optional[str] = None
    referee: Optional[str] = None

    # ── Eventos temporais ─────────────────────────────────────────────────────
    first_half_home_goals: Optional[int] = Field(None, ge=0, le=10)
    first_half_away_goals: Optional[int] = Field(None, ge=0, le=10)
    minute_first_goal: Optional[int] = Field(None, ge=0, le=90, description="0 se não houve gol")
    home_goals_0_15: Optional[int] = Field(None, ge=0, le=10)
    away_goals_0_15: Optional[int] = Field(None, ge=0, le=10)
    home_goals_75_90: Optional[int] = Field(None, ge=0, le=10)
    away_goals_75_90: Optional[int] = Field(None, ge=0, le=10)

    @field_validator("home_team", "away_team", mode="before")
    @classmethod
    def normalize_team_name(cls, v: str) -> str:
        return v.strip().title()

    @model_validator(mode="after")
    def check_shots_consistency(self) -> "MatchRecord":
        """Chutes no gol não podem superar total de chutes."""
        if self.home_shots is not None and self.home_shots_on_target is not None:
            if self.home_shots_on_target > self.home_shots:
                raise ValueError("home_shots_on_target cannot exceed home_shots")
        if self.away_shots is not None and self.away_shots_on_target is not None:
            if self.away_shots_on_target > self.away_shots:
                raise ValueError("away_shots_on_target cannot exceed away_shots")
        return self

    @model_validator(mode="after")
    def check_possession_sum(self) -> "MatchRecord":
        """Posse de bola deve somar ~100%."""
        if self.home_possession is not None and self.away_possession is not None:
            total = self.home_possession + self.away_possession
            if not (95.0 <= total <= 105.0):
                raise ValueError(f"Possession sums to {total}, expected ~100")
        return self

    @model_validator(mode="after")
    def check_half_time_goals(self) -> "MatchRecord":
        """Gols do 1º tempo não podem superar total."""
        if self.first_half_home_goals is not None:
            if self.first_half_home_goals > self.home_goals:
                raise ValueError("first_half_home_goals cannot exceed home_goals")
        if self.first_half_away_goals is not None:
            if self.first_half_away_goals > self.away_goals:
                raise ValueError("first_half_away_goals cannot exceed away_goals")
        return self

    model_config = {"str_strip_whitespace": True}


class PredictionRequest(BaseModel):
    """Schema de input para inferência pré-jogo."""

    competition: Competition
    home_team: str = Field(..., min_length=2)
    away_team: str = Field(..., min_length=2)
    match_date: date = Field(..., description="Data da partida (YYYY-MM-DD)")
    stage: Optional[str] = Field(None, description="Fase (grupo, oitavas, etc.)")
    matchday: Optional[int] = Field(None, ge=1, le=40)

    @field_validator("home_team", "away_team", mode="before")
    @classmethod
    def normalize_team_name(cls, v: str) -> str:
        return v.strip().title()

    model_config = {"str_strip_whitespace": True}
