"""
app/inference/serializer.py
Serializa PredictionOutput para formatos JSON-compatíveis.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from app.inference.predictor import PredictionOutput
from app.inference.explainability import generate_natural_language_explanation
from app.core.utils import JSONEncoder
import json


def prediction_to_dict(prediction: PredictionOutput) -> Dict[str, Any]:
    """Converte PredictionOutput para dicionário aninhado."""
    d = asdict(prediction)

    # Agrupa em seções lógicas para melhor legibilidade da API
    return {
        "match": {
            "competition": d["competition"],
            "home_team": d["home_team"],
            "away_team": d["away_team"],
            "match_date": d["match_date"],
        },
        "outcome": {
            "home_win": d["home_win"],
            "draw": d["draw"],
            "away_win": d["away_win"],
        },
        "goals": {
            "expected_goals_home": d["expected_goals_home"],
            "expected_goals_away": d["expected_goals_away"],
            "expected_goals_total": d["expected_goals_total"],
            "over_0_5": d["over_0_5"],
            "over_1_5": d["over_1_5"],
            "over_2_5": d["over_2_5"],
            "over_3_5": d["over_3_5"],
            "over_4_5": d["over_4_5"],
            "both_teams_score": d["both_teams_score"],
            "clean_sheet_home": d["clean_sheet_home"],
            "clean_sheet_away": d["clean_sheet_away"],
            "top_scorelines": d["top_scorelines"],
        },
        "corners": {
            "expected_corners_total": d["expected_corners_total"],
            "expected_corners_home": d["expected_corners_home"],
            "expected_corners_away": d["expected_corners_away"],
        },
        "cards": {
            "expected_cards_total": d["expected_cards_total"],
            "expected_cards_home": d["expected_cards_home"],
            "expected_cards_away": d["expected_cards_away"],
        },
        "time_windows": {
            "goal_first_15min": d["goal_first_15min"],
            "goal_last_15min": d["goal_last_15min"],
            "goal_first_half": d["goal_first_half"],
            "goal_second_half": d["goal_second_half"],
        },
        "explainability": {
            "top_features": d["top_features"],
            "confidence_score": d["confidence_score"],
            "low_confidence_warning": d["low_confidence_warning"],
        },
        "warnings": d["model_warnings"],
        "disclaimer": (
            "Estimativas probabilísticas baseadas em padrões históricos. "
            "Não constituem previsão garantida. Incerteza estatística implícita."
        ),
    }


def prediction_to_json(prediction: PredictionOutput, with_explanation: bool = False) -> str:
    """Serializa para string JSON."""
    d = prediction_to_dict(prediction)

    if with_explanation:
        explanation = generate_natural_language_explanation(
            prediction,
            prediction.top_features,
            prediction.confidence_score,
        )
        d["natural_language_explanation"] = explanation

    return json.dumps(d, cls=JSONEncoder, ensure_ascii=False, indent=2)
