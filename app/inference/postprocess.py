"""
app/inference/postprocess.py
Pós-processamento de previsões: arredondamento, normalização, sanity checks.
"""
from __future__ import annotations

from app.core.utils import normalize_probabilities
from app.inference.predictor import PredictionOutput
from app.core.logger import get_logger

logger = get_logger(__name__)


def postprocess_prediction(pred: PredictionOutput) -> PredictionOutput:
    """
    Aplica sanity checks e normalizações na saída do predictor:
      1. Normaliza probabilidades de resultado para somar 1.0
      2. Clippa valores fora do range [0,1]
      3. Garante que expected_goals >= 0
    """
    # Normaliza 1X2
    probs = normalize_probabilities([pred.home_win, pred.draw, pred.away_win])
    pred.home_win = round(probs[0], 4)
    pred.draw = round(probs[1], 4)
    pred.away_win = round(probs[2], 4)

    # Clipa probabilidades binárias
    for attr in [
        "over_0_5", "over_1_5", "over_2_5", "over_3_5", "over_4_5",
        "both_teams_score", "clean_sheet_home", "clean_sheet_away",
        "goal_first_15min", "goal_last_15min", "goal_first_half", "goal_second_half",
    ]:
        val = getattr(pred, attr, 0.5)
        setattr(pred, attr, round(max(0.0, min(1.0, val)), 4))

    # Garante values positivos
    for attr in [
        "expected_goals_home", "expected_goals_away", "expected_goals_total",
        "expected_corners_total", "expected_corners_home", "expected_corners_away",
        "expected_cards_total", "expected_cards_home", "expected_cards_away",
    ]:
        val = getattr(pred, attr, 0.0)
        setattr(pred, attr, round(max(0.0, val), 3))

    # Clipa confidence
    pred.confidence_score = round(max(0.0, min(1.0, pred.confidence_score)), 3)

    return pred
