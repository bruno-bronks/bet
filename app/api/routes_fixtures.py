"""
app/api/routes_fixtures.py
Endpoints para fixtures, standings e resultados recentes via API-Football.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import (
    FixtureItem,
    FixtureWithPrediction,
    FixturesResponse,
    OutcomeProbsSlim,
    RecentResponse,
    RefereeStats,
    StandingItem,
    StandingsResponse,
    TeamCardStats,
)
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.services.football_api import football_api, _normalize_team

logger = get_logger(__name__)
router = APIRouter(tags=["fixtures"])


def _load_cards_df(competition: str) -> Optional[pd.DataFrame]:
    """
    Carrega e prepara o DataFrame de cartões da temporada mais recente
    disponível no CSV _with_stats da competição.
    """
    try:
        processed = settings.PROCESSED_DATA_DIR
        csvs = list(processed.glob(f"{competition}_*with_stats*.csv"))
        # Inclui também o CSV da temporada atual (se já tiver dados)
        current_csvs = list(processed.glob(f"{competition}_real_2*.csv"))
        all_csvs = list({f for f in csvs + current_csvs})
        if not all_csvs:
            return None

        frames = [pd.read_csv(f) for f in all_csvs]
        df = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["date", "home_team", "away_team"], keep="last"
        )

        if "home_yellow_cards" not in df.columns:
            return None

        # Filtrar pela temporada mais recente com dados de cartão reais
        if "season" in df.columns:
            seasons_with_cards = (
                df[df["home_yellow_cards"].notna()]["season"]
                .dropna()
                .unique()
            )
            if len(seasons_with_cards) > 0:
                df = df[df["season"] == int(max(seasons_with_cards))]

        # Manter apenas linhas com dados reais de cartão
        df = df[df["home_yellow_cards"].notna()].copy()
        if df.empty:
            return None

        df["home_total_cards"] = df["home_yellow_cards"].fillna(0) + df.get("home_red_cards", pd.Series(0, index=df.index)).fillna(0)
        df["away_total_cards"] = df["away_yellow_cards"].fillna(0) + df.get("away_red_cards", pd.Series(0, index=df.index)).fillna(0)
        return df
    except Exception:
        return None


def _team_card_stats(competition: str, team: str, role: str) -> Optional[float]:
    """
    Calcula a média de cartões do time para um papel específico:
      role='home' → média quando o time joga em casa
      role='away' → média quando o time joga fora
      role='all'  → média geral (casa+fora)
    Retorna None se não houver dados suficientes (mínimo 3 jogos).
    """
    df = _load_cards_df(competition)
    if df is None:
        return None
    try:
        team_norm = _normalize_team(team)
        if role == "home":
            games = df[df["home_team"] == team_norm]["home_total_cards"].dropna()
        elif role == "away":
            games = df[df["away_team"] == team_norm]["away_total_cards"].dropna()
        else:  # all
            home_g = df[df["home_team"] == team_norm]["home_total_cards"].dropna()
            away_g = df[df["away_team"] == team_norm]["away_total_cards"].dropna()
            games = pd.concat([home_g, away_g])
        if len(games) < 3:
            return None
        return round(float(games.mean()), 2)
    except Exception:
        return None


def _validate_competition(competition: str) -> str:
    comp = competition.lower()
    if comp not in settings.SUPPORTED_COMPETITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported competition: '{competition}'. Choices: {settings.SUPPORTED_COMPETITIONS}",
        )
    return comp


def _get_predictor_safe(competition: str):
    """Carrega o predictor uma única vez; loga erros em vez de suprimir."""
    try:
        from app.api.routes_predictions import get_predictor
        return get_predictor(competition)
    except Exception as e:
        logger.warning(f"Predictor indisponível para {competition}: {e}")
        return None


def _try_predict(predictor, competition: str, home_team: str, away_team: str, match_date: str) -> Optional[OutcomeProbsSlim]:
    """
    Tenta rodar a predição de resultado 1X2 para o jogo.
    Retorna None se os modelos não estiverem disponíveis ou ocorrer qualquer erro.
    """
    if predictor is None:
        return None
    try:
        from app.inference.predictor import MatchContext
        from app.inference.postprocess import postprocess_prediction

        ctx = MatchContext(
            competition=competition,
            home_team=home_team,
            away_team=away_team,
            match_date=date.fromisoformat(match_date),
        )
        pred = postprocess_prediction(predictor.predict(ctx))
        return OutcomeProbsSlim(
            home_win=round(pred.home_win, 3),
            draw=round(pred.draw, 3),
            away_win=round(pred.away_win, 3),
        )
    except Exception as e:
        logger.debug(f"Predição falhou para {home_team} vs {away_team}: {e}")
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/fixtures",
    response_model=FixturesResponse,
    summary="Próximas partidas com previsão automática",
)
async def get_fixtures(
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
    days_ahead: int = Query(14, ge=1, le=60, description="Janela de dias à frente"),
) -> FixturesResponse:
    """
    Retorna as próximas partidas não iniciadas e, para cada uma,
    tenta gerar a probabilidade 1X2 se os modelos estiverem carregados.
    """
    comp = _validate_competition(competition)
    raw = football_api.get_fixtures(comp, days_ahead=days_ahead)

    # Carrega predictor UMA VEZ para todos os fixtures (não repete por fixture)
    predictor = _get_predictor_safe(comp)

    fixtures_with_pred: List[FixtureWithPrediction] = []
    for f in raw:
        pred = _try_predict(predictor, comp, f["home_team"], f["away_team"], f["date"])
        fixtures_with_pred.append(FixtureWithPrediction(**f, prediction=pred))

    return FixturesResponse(
        competition=comp,
        count=len(fixtures_with_pred),
        fixtures=fixtures_with_pred,
    )


@router.get(
    "/standings",
    response_model=StandingsResponse,
    summary="Classificação da competição",
)
async def get_standings(
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
) -> StandingsResponse:
    """Tabela de classificação atualizada."""
    comp = _validate_competition(competition)
    data = football_api.get_standings(comp)

    return StandingsResponse(
        competition=comp,
        season=data.get("season", 0),
        standings=[StandingItem(**s) for s in data.get("standings", [])],
    )


@router.get(
    "/recent",
    response_model=RecentResponse,
    summary="Resultados recentes",
)
async def get_recent(
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
    limit: int = Query(10, ge=1, le=30, description="Número máximo de partidas"),
) -> RecentResponse:
    """Últimas partidas finalizadas da competição."""
    comp = _validate_competition(competition)
    raw = football_api.get_recent(comp, limit=limit)
    return RecentResponse(
        competition=comp,
        count=len(raw),
        fixtures=[FixtureItem(**f) for f in raw],
    )


@router.get(
    "/team-card-stats",
    response_model=TeamCardStats,
    summary="Média histórica de cartões dos times na competição",
)
async def get_team_card_stats(
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
    home_team: str = Query(..., description="Time mandante"),
    away_team: str = Query(..., description="Time visitante"),
) -> TeamCardStats:
    """
    Retorna a média histórica de cartões por jogo de cada time na competição,
    calculada a partir dos CSVs processados com estatísticas.
    """
    comp = _validate_competition(competition)
    return TeamCardStats(
        home_as_home=_team_card_stats(comp, home_team, "home"),
        away_as_away=_team_card_stats(comp, away_team, "away"),
        home_avg=_team_card_stats(comp, home_team, "all"),
        away_avg=_team_card_stats(comp, away_team, "all"),
    )


@router.get(
    "/referee-stats",
    response_model=RefereeStats,
    summary="Estatísticas de cartões de um árbitro",
)
async def get_referee_stats(
    referee: str = Query(..., description="Nome do árbitro"),
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
    home_team: str = Query(..., description="Time mandante"),
    away_team: str = Query(..., description="Time visitante"),
) -> RefereeStats:
    """
    Retorna média de cartões por jogo do árbitro na competição,
    incluindo médias específicas para os dois times quando jogam com este árbitro.
    Requer API_FOOTBALL_KEY configurada no .env (api-sports.io).
    """
    comp = _validate_competition(competition)
    stats = football_api.get_referee_stats(referee, comp, home_team, away_team)
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Estatísticas não disponíveis para o árbitro '{referee}'. "
                "Configure API_FOOTBALL_KEY no .env ou o árbitro não tem dados suficientes."
            ),
        )
    # Enriquece com média no papel do jogo (mandante em casa, visitante fora)
    stats["home_team_general_avg_cards"] = _team_card_stats(comp, home_team, "home")
    stats["away_team_general_avg_cards"] = _team_card_stats(comp, away_team, "away")
    return RefereeStats(**stats)
