"""
app/tests/test_predictor.py
Testes para o motor de inferência e postprocessamento.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from datetime import date

from app.inference.postprocess import postprocess_prediction
from app.inference.predictor import PredictionOutput
from app.inference.serializer import prediction_to_dict
from app.core.utils import normalize_probabilities, poisson_over_probability, bivariate_poisson_scoreline_probs


@pytest.fixture
def dummy_prediction() -> PredictionOutput:
    return PredictionOutput(
        competition="brasileirao",
        home_team="Flamengo",
        away_team="Palmeiras",
        match_date="2024-06-15",
        home_win=0.45,
        draw=0.28,
        away_win=0.27,
        expected_goals_home=1.5,
        expected_goals_away=1.1,
        expected_goals_total=2.6,
        over_0_5=0.92,
        over_1_5=0.72,
        over_2_5=0.52,
        over_3_5=0.30,
        over_4_5=0.14,
        both_teams_score=0.55,
        clean_sheet_home=0.33,
        clean_sheet_away=0.22,
        top_scorelines=[{"scoreline": "1-1", "home_goals": 1, "away_goals": 1, "probability": 0.12}],
        expected_corners_total=9.5,
        expected_corners_home=5.0,
        expected_corners_away=4.5,
        expected_cards_total=4.0,
        expected_cards_home=2.0,
        expected_cards_away=2.0,
        goal_first_15min=0.30,
        goal_last_15min=0.35,
        goal_first_half=0.70,
        goal_second_half=0.75,
        confidence_score=0.8,
        low_confidence_warning=False,
    )


class TestPostprocess:
    def test_outcome_sums_to_one(self, dummy_prediction):
        result = postprocess_prediction(dummy_prediction)
        total = result.home_win + result.draw + result.away_win
        assert abs(total - 1.0) < 0.001

    def test_probabilities_in_range(self, dummy_prediction):
        result = postprocess_prediction(dummy_prediction)
        for attr in ["over_2_5", "both_teams_score", "goal_first_15min", "goal_last_15min"]:
            val = getattr(result, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of range"

    def test_expected_goals_positive(self, dummy_prediction):
        dummy_prediction.expected_goals_home = -0.5  # Valor inválido
        result = postprocess_prediction(dummy_prediction)
        assert result.expected_goals_home >= 0.0

    def test_confidence_clamped(self, dummy_prediction):
        dummy_prediction.confidence_score = 1.5
        result = postprocess_prediction(dummy_prediction)
        assert result.confidence_score <= 1.0


class TestSerializer:
    def test_dict_has_required_sections(self, dummy_prediction):
        d = prediction_to_dict(dummy_prediction)
        for section in ["match", "outcome", "goals", "corners", "cards", "time_windows", "explainability"]:
            assert section in d

    def test_outcome_section_keys(self, dummy_prediction):
        d = prediction_to_dict(dummy_prediction)
        assert "home_win" in d["outcome"]
        assert "draw" in d["outcome"]
        assert "away_win" in d["outcome"]

    def test_disclaimer_present(self, dummy_prediction):
        d = prediction_to_dict(dummy_prediction)
        assert "disclaimer" in d
        assert len(d["disclaimer"]) > 10


class TestUtils:
    def test_normalize_probabilities(self):
        probs = [2.0, 1.0, 1.0]
        normalized = normalize_probabilities(probs)
        assert abs(sum(normalized) - 1.0) < 1e-6
        assert normalized[0] == pytest.approx(0.5)

    def test_normalize_zeros(self):
        probs = [0.0, 0.0, 0.0]
        normalized = normalize_probabilities(probs)
        assert abs(sum(normalized) - 1.0) < 1e-6

    def test_poisson_over(self):
        # P(X > 2.5 | lambda=3) should be > 0.5
        p = poisson_over_probability(3.0, 2.5)
        assert p > 0.5

    def test_poisson_over_low_lambda(self):
        # P(X > 2.5 | lambda=0.5) should be very low
        p = poisson_over_probability(0.5, 2.5)
        assert p < 0.1

    def test_scoreline_probs_sum(self):
        probs = bivariate_poisson_scoreline_probs(1.5, 1.1, max_goals=6)
        total = sum(probs.values())
        assert abs(total - 1.0) < 0.01  # Pequena diferença por truncamento em max_goals
