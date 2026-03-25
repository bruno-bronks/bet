"""
app/db/models.py
Modelos ORM SQLAlchemy para persistência de partidas e previsões.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchORM(Base):
    """Tabela de partidas históricas."""

    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    competition: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(1))

    # Estatísticas opcionais
    home_shots: Mapped[Optional[int]] = mapped_column(Integer)
    away_shots: Mapped[Optional[int]] = mapped_column(Integer)
    home_corners: Mapped[Optional[int]] = mapped_column(Integer)
    away_corners: Mapped[Optional[int]] = mapped_column(Integer)
    home_yellow_cards: Mapped[Optional[int]] = mapped_column(Integer)
    away_yellow_cards: Mapped[Optional[int]] = mapped_column(Integer)
    home_red_cards: Mapped[Optional[int]] = mapped_column(Integer)
    away_red_cards: Mapped[Optional[int]] = mapped_column(Integer)
    home_xg: Mapped[Optional[float]] = mapped_column(Float)
    away_xg: Mapped[Optional[float]] = mapped_column(Float)

    stage: Mapped[Optional[str]] = mapped_column(String(50))
    matchday: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class PredictionORM(Base):
    """Tabela de previsões geradas pelo sistema."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(50), index=True)
    competition: Mapped[str] = mapped_column(String(50))
    home_team: Mapped[str] = mapped_column(String(100))
    away_team: Mapped[str] = mapped_column(String(100))
    match_date: Mapped[date] = mapped_column(Date)

    # Probabilidades de resultado
    prob_home_win: Mapped[float] = mapped_column(Float)
    prob_draw: Mapped[float] = mapped_column(Float)
    prob_away_win: Mapped[float] = mapped_column(Float)

    # Gols
    expected_goals_home: Mapped[Optional[float]] = mapped_column(Float)
    expected_goals_away: Mapped[Optional[float]] = mapped_column(Float)
    prob_over_2_5: Mapped[Optional[float]] = mapped_column(Float)
    prob_btts: Mapped[Optional[float]] = mapped_column(Float)

    # Meta
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(20), default="1.0")
    payload_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON completo

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
