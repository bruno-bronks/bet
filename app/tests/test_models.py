"""
app/tests/test_models.py
Testes unitários para os modelos probabilísticos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path
import tempfile

from app.models.outcome_model import OutcomeModel
from app.models.goals_model import GoalsModel
from app.models.corners_model import CornersModel
from app.models.cards_model import CardsModel
from app.models.calibration import brier_score, calibration_report, expected_calibration_error


@pytest.fixture
def feature_df() -> pd.DataFrame:
    """Features sintéticas para treino."""
    np.random.seed(42)
    n = 200
    return pd.DataFrame({
        "elo_diff": np.random.normal(0, 100, n),
        "home_form": np.random.uniform(0, 1, n),
        "away_form": np.random.uniform(0, 1, n),
        "h_gf_roll5": np.random.uniform(0.5, 2.5, n),
        "h_ga_roll5": np.random.uniform(0.5, 2.0, n),
        "a_gf_roll5": np.random.uniform(0.5, 2.0, n),
        "a_ga_roll5": np.random.uniform(0.5, 2.5, n),
        "competition_id": np.zeros(n, dtype=int),
    })


@pytest.fixture
def outcome_target() -> pd.Series:
    np.random.seed(42)
    return pd.Series(np.random.choice(["H", "D", "A"], 200, p=[0.45, 0.27, 0.28]))


@pytest.fixture
def goals_target() -> pd.DataFrame:
    np.random.seed(42)
    return pd.DataFrame({
        "home_goals": np.random.poisson(1.5, 200),
        "away_goals": np.random.poisson(1.1, 200),
    })


class TestOutcomeModel:
    def test_fit_predict(self, feature_df, outcome_target):
        model = OutcomeModel(use_calibration=False)
        model.fit(feature_df, outcome_target)
        preds = model.predict(feature_df)
        assert len(preds) == len(feature_df)
        assert set(preds).issubset({"H", "D", "A"})

    def test_predict_proba_shape(self, feature_df, outcome_target):
        model = OutcomeModel(use_calibration=False)
        model.fit(feature_df, outcome_target)
        proba = model.predict_proba(feature_df)
        assert proba.shape == (len(feature_df), 3)
        # Probabilidades devem somar ~1
        row_sums = proba.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5)

    def test_predict_structured(self, feature_df, outcome_target):
        model = OutcomeModel(use_calibration=False)
        model.fit(feature_df, outcome_target)
        results = model.predict_structured(feature_df[:3])
        assert len(results) == 3
        for r in results:
            assert "home_win" in r
            assert "draw" in r
            assert "away_win" in r
            total = r["home_win"] + r["draw"] + r["away_win"]
            assert abs(total - 1.0) < 0.01

    def test_save_load(self, feature_df, outcome_target, tmp_path):
        model = OutcomeModel(use_calibration=False)
        model.fit(feature_df, outcome_target)
        preds_before = model.predict(feature_df)

        path = tmp_path / "outcome.joblib"
        model.save(path)

        loaded = OutcomeModel()
        loaded.load(path)
        preds_after = loaded.predict(feature_df)
        assert list(preds_before) == list(preds_after)

    def test_raises_if_not_fitted(self, feature_df):
        model = OutcomeModel()
        with pytest.raises(RuntimeError, match="not fitted"):
            model.predict(feature_df)


class TestGoalsModel:
    def test_fit_predict(self, feature_df, goals_target):
        model = GoalsModel()
        model.fit(feature_df, goals_target)
        preds = model.predict(feature_df)
        assert preds.shape == (len(feature_df), 2)
        assert (preds >= 0).all()

    def test_predict_full_structure(self, feature_df, goals_target):
        model = GoalsModel()
        model.fit(feature_df, goals_target)
        results = model.predict_full(feature_df[:5])
        assert len(results) == 5
        for r in results:
            assert "expected_goals_home" in r
            assert "over_2_5" in r
            assert "both_teams_score" in r
            assert 0 <= r["over_2_5"] <= 1
            assert 0 <= r["both_teams_score"] <= 1
            assert len(r["top_scorelines"]) <= 10

    def test_lambda_positive(self, feature_df, goals_target):
        model = GoalsModel()
        model.fit(feature_df, goals_target)
        preds = model.predict(feature_df)
        assert (preds > 0).all(), "Lambda values should be positive"


class TestCalibration:
    def test_brier_score_perfect(self):
        y = np.array([1, 0, 1, 0])
        y_prob = np.array([1.0, 0.0, 1.0, 0.0])
        assert brier_score(y, y_prob) == 0.0

    def test_brier_score_random(self):
        y = np.array([1, 0, 1, 0])
        y_prob = np.array([0.5, 0.5, 0.5, 0.5])
        assert abs(brier_score(y, y_prob) - 0.25) < 1e-6

    def test_ece_well_calibrated(self):
        # Perfect calibration: predicted prob = empirical freq
        np.random.seed(0)
        y_prob = np.linspace(0.1, 0.9, 100)
        y_true = (np.random.rand(100) < y_prob).astype(float)
        ece = expected_calibration_error(y_true, y_prob)
        assert ece < 0.15  # Bem calibrado em amostra razoável

    def test_calibration_report_keys(self):
        y = np.array([1, 0, 1, 0, 1, 0])
        y_prob = np.array([0.8, 0.2, 0.7, 0.3, 0.9, 0.1])
        report = calibration_report(y, y_prob)
        assert "accuracy" in report
        assert "brier_score" in report
        assert "log_loss" in report
        assert "ece" in report
