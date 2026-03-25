"""
app/api/routes_history.py
Endpoint de histórico: partidas realizadas comparadas com previsões do modelo.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Query

from app.api.schemas import (
    HistoryMatch,
    HistoryResponse,
    HistorySummary,
    MatchAccuracy,
    MatchActual,
    MatchPredSummary,
)
from app.api.routes_fixtures import _validate_competition, _get_predictor_safe
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["history"])


# ── Carregamento de dados ──────────────────────────────────────────────────────

def _load_history_df(competition: str, season: Optional[int] = None) -> Optional[pd.DataFrame]:
    """
    Carrega partidas finalizadas dos CSVs with_stats + temporada atual.
    Filtra por season se fornecido. Ordena por date desc.
    """
    try:
        processed = settings.PROCESSED_DATA_DIR
        with_stats = list(processed.glob(f"{competition}_*with_stats*.csv"))
        current = list(processed.glob(f"{competition}_real_2*.csv"))
        all_csvs = list({f for f in with_stats + current})
        if not all_csvs:
            return None

        frames = [pd.read_csv(f) for f in all_csvs]
        df = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["date", "home_team", "away_team"], keep="last"
        )

        # Somente partidas finalizadas
        df = df[df["home_goals"].notna()].copy()
        if df.empty:
            return None

        if season is not None and "season" in df.columns:
            df = df[df["season"] == season]

        df = df.sort_values("date", ascending=False)
        return df
    except Exception as e:
        logger.warning(f"Erro ao carregar histórico para {competition}: {e}")
        return None


# ── Construção dos objetos ─────────────────────────────────────────────────────

def _safe_int(val) -> Optional[int]:
    try:
        v = float(val)
        return int(v) if not pd.isna(v) else None
    except (TypeError, ValueError):
        return None


def _build_actual(row: pd.Series) -> MatchActual:
    hg = int(row["home_goals"])
    ag = int(row["away_goals"])
    outcome = "H" if hg > ag else ("A" if ag > hg else "D")

    # Cartões
    hy = _safe_int(row.get("home_yellow_cards"))
    hr = _safe_int(row.get("home_red_cards"))
    ay = _safe_int(row.get("away_yellow_cards"))
    ar = _safe_int(row.get("away_red_cards"))
    home_cards = (hy or 0) + (hr or 0) if (hy is not None or hr is not None) else None
    away_cards = (ay or 0) + (ar or 0) if (ay is not None or ar is not None) else None
    total_cards = (home_cards or 0) + (away_cards or 0) if (home_cards is not None or away_cards is not None) else None

    # Cantos
    hc = _safe_int(row.get("home_corners"))
    ac = _safe_int(row.get("away_corners"))
    total_corners = (hc or 0) + (ac or 0) if (hc is not None or ac is not None) else None

    # Gols 1° tempo
    fhh = _safe_int(row.get("first_half_home_goals"))
    fha = _safe_int(row.get("first_half_away_goals"))
    first_half_goals: Optional[int] = None
    goal_first_half: Optional[bool] = None
    if fhh is not None and fha is not None:
        first_half_goals = fhh + fha
        goal_first_half = first_half_goals > 0

    return MatchActual(
        home_goals=hg,
        away_goals=ag,
        outcome=outcome,
        total_goals=hg + ag,
        btts=(hg > 0 and ag > 0),
        home_cards=home_cards,
        away_cards=away_cards,
        total_cards=total_cards,
        home_corners=hc,
        away_corners=ac,
        total_corners=total_corners,
        first_half_goals=first_half_goals,
        goal_first_half=goal_first_half,
    )


def _run_prediction(predictor, comp: str, row: pd.Series) -> Optional[MatchPredSummary]:
    if predictor is None:
        return None
    try:
        from app.inference.predictor import MatchContext
        from app.inference.postprocess import postprocess_prediction

        match_date = date.fromisoformat(str(row["date"])[:10])
        ctx = MatchContext(
            competition=comp,
            home_team=str(row["home_team"]),
            away_team=str(row["away_team"]),
            match_date=match_date,
        )
        pred = postprocess_prediction(predictor.predict(ctx))

        probs = {"H": pred.home_win, "D": pred.draw, "A": pred.away_win}
        predicted_outcome = max(probs, key=probs.__getitem__)

        return MatchPredSummary(
            home_win=round(pred.home_win, 3),
            draw=round(pred.draw, 3),
            away_win=round(pred.away_win, 3),
            predicted_outcome=predicted_outcome,
            over_2_5=round(pred.over_2_5, 3),
            btts=round(pred.both_teams_score, 3),
            expected_home_goals=round(pred.expected_goals_home, 2),
            expected_away_goals=round(pred.expected_goals_away, 2),
            expected_total_cards=round(pred.expected_cards_total, 2),
            expected_total_corners=round(pred.expected_corners_total, 2),
            goal_first_half=round(pred.goal_first_half, 3),
        )
    except Exception as e:
        logger.debug(f"Predição falhou para {row.get('home_team')} vs {row.get('away_team')}: {e}")
        return None


def _compute_accuracy(actual: MatchActual, pred: MatchPredSummary) -> MatchAccuracy:
    outcome_correct = actual.outcome == pred.predicted_outcome
    over_2_5_correct = (pred.over_2_5 > 0.5) == (actual.total_goals > 2)
    btts_correct = (pred.btts > 0.5) == actual.btts

    cards_diff: Optional[float] = None
    if actual.total_cards is not None:
        cards_diff = round(abs(pred.expected_total_cards - actual.total_cards), 2)

    corners_diff: Optional[float] = None
    if actual.total_corners is not None:
        corners_diff = round(abs(pred.expected_total_corners - actual.total_corners), 2)

    first_half_correct: Optional[bool] = None
    if actual.goal_first_half is not None:
        first_half_correct = (pred.goal_first_half > 0.5) == actual.goal_first_half

    return MatchAccuracy(
        outcome_correct=outcome_correct,
        over_2_5_correct=over_2_5_correct,
        btts_correct=btts_correct,
        cards_diff=cards_diff,
        corners_diff=corners_diff,
        first_half_correct=first_half_correct,
    )


def _compute_summary(matches: List[HistoryMatch]) -> HistorySummary:
    with_pred = [m for m in matches if m.accuracy is not None]
    total = len(with_pred)
    if total == 0:
        return HistorySummary(total_matches=len(matches))

    outcome_correct = sum(1 for m in with_pred if m.accuracy.outcome_correct)  # type: ignore[union-attr]
    over_correct = [m for m in with_pred if m.accuracy.over_2_5_correct is not None]  # type: ignore[union-attr]
    btts_correct = [m for m in with_pred if m.accuracy.btts_correct is not None]  # type: ignore[union-attr]
    cards_diffs = [m.accuracy.cards_diff for m in with_pred if m.accuracy.cards_diff is not None]  # type: ignore[union-attr]
    corners_diffs = [m.accuracy.corners_diff for m in with_pred if m.accuracy.corners_diff is not None]  # type: ignore[union-attr]

    return HistorySummary(
        total_matches=total,
        outcome_accuracy=round(outcome_correct / total, 3),
        over_2_5_accuracy=round(sum(1 for m in over_correct if m.accuracy.over_2_5_correct) / len(over_correct), 3) if over_correct else None,  # type: ignore[union-attr]
        btts_accuracy=round(sum(1 for m in btts_correct if m.accuracy.btts_correct) / len(btts_correct), 3) if btts_correct else None,  # type: ignore[union-attr]
        avg_cards_diff=round(sum(cards_diffs) / len(cards_diffs), 2) if cards_diffs else None,
        avg_corners_diff=round(sum(corners_diffs) / len(corners_diffs), 2) if corners_diffs else None,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Histórico de partidas com comparação previsão vs real",
)
async def get_history(
    competition: str = Query(..., description="'brasileirao' ou 'champions_league'"),
    limit: int = Query(20, ge=1, le=50, description="Número de partidas a retornar"),
    season: Optional[int] = Query(None, description="Filtrar por temporada (ex: 2025)"),
) -> HistoryResponse:
    """
    Retorna partidas já realizadas com o resultado real e a previsão do modelo,
    calculando acerto por mercado: resultado 1X2, Over 2.5, BTTS, cartões, cantos, gol no 1° tempo.
    """
    comp = _validate_competition(competition)

    df = _load_history_df(comp, season)
    if df is None or df.empty:
        return HistoryResponse(
            competition=comp,
            season=season,
            count=0,
            matches=[],
            summary=HistorySummary(total_matches=0),
        )

    rows = df.head(limit)
    predictor = _get_predictor_safe(comp)

    matches: List[HistoryMatch] = []
    for _, row in rows.iterrows():
        try:
            actual = _build_actual(row)
        except Exception as e:
            logger.debug(f"Erro ao montar actual para {row.get('home_team')} vs {row.get('away_team')}: {e}")
            continue

        pred = _run_prediction(predictor, comp, row)
        accuracy = _compute_accuracy(actual, pred) if pred else None

        matchday_val = _safe_int(row.get("matchday"))
        stage_val = str(row["stage"]) if "stage" in row.index and pd.notna(row.get("stage")) else None

        matches.append(HistoryMatch(
            date=str(row["date"])[:10],
            matchday=matchday_val,
            stage=stage_val,
            home_team=str(row["home_team"]),
            away_team=str(row["away_team"]),
            actual=actual,
            prediction=pred,
            accuracy=accuracy,
        ))

    return HistoryResponse(
        competition=comp,
        season=season,
        count=len(matches),
        matches=matches,
        summary=_compute_summary(matches),
    )
