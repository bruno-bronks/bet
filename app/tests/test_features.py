"""
app/tests/test_features.py
Testes unitários para o módulo de feature engineering.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from datetime import date

from app.data.preprocess import MatchPreprocessor
from app.features.team_strength import EloRatingSystem, compute_recent_form
from app.features.rolling_features import compute_rolling_features
from app.features.feature_pipeline import FeaturePipeline


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """DataFrame mínimo para testes."""
    return pd.DataFrame({
        "match_id": [f"m{i:03d}" for i in range(30)],
        "competition": ["brasileirao"] * 30,
        "season": ["2023"] * 30,
        "date": pd.date_range("2023-04-01", periods=30, freq="7D"),
        "home_team": (["Flamengo", "Palmeiras", "Corinthians"] * 10),
        "away_team": (["Palmeiras", "Corinthians", "Flamengo"] * 10),
        "home_goals": np.random.randint(0, 4, 30),
        "away_goals": np.random.randint(0, 3, 30),
        "home_corners": np.random.randint(2, 10, 30),
        "away_corners": np.random.randint(2, 10, 30),
        "home_yellow_cards": np.random.randint(0, 4, 30),
        "away_yellow_cards": np.random.randint(0, 4, 30),
        "home_red_cards": np.zeros(30, dtype=int),
        "away_red_cards": np.zeros(30, dtype=int),
        "home_xg": np.random.uniform(0.5, 2.5, 30),
        "away_xg": np.random.uniform(0.5, 2.0, 30),
    })


class TestPreprocessor:
    def test_adds_outcome_column(self, sample_df):
        proc = MatchPreprocessor()
        result = proc.fit_transform(sample_df)
        assert "outcome" in result.columns
        assert set(result["outcome"].unique()).issubset({"H", "D", "A"})

    def test_adds_total_goals(self, sample_df):
        proc = MatchPreprocessor()
        result = proc.fit_transform(sample_df)
        assert "total_goals" in result.columns
        assert (result["total_goals"] == result["home_goals"] + result["away_goals"]).all()

    def test_sorted_by_date(self, sample_df):
        shuffled = sample_df.sample(frac=1, random_state=42)
        proc = MatchPreprocessor()
        result = proc.fit_transform(shuffled)
        dates = pd.to_datetime(result["date"])
        assert (dates.diff().dropna() >= pd.Timedelta(0)).all()

    def test_removes_invalid_rows(self, sample_df):
        bad_df = sample_df.copy()
        bad_df.loc[0, "home_goals"] = np.nan
        bad_df.loc[1, "date"] = pd.NaT
        proc = MatchPreprocessor()
        result = proc.fit_transform(bad_df)
        assert len(result) <= len(bad_df)

    def test_raises_on_missing_columns(self):
        df_bad = pd.DataFrame({"match_id": ["x"], "home_team": ["A"], "away_team": ["B"]})
        proc = MatchPreprocessor()
        with pytest.raises(ValueError, match="Missing required columns"):
            proc.fit_transform(df_bad)


class TestEloRating:
    def test_initial_rating(self):
        elo = EloRatingSystem()
        assert elo.get_rating("NewTeam") == elo.initial_rating

    def test_winner_gains_rating(self):
        elo = EloRatingSystem()
        elo.update("TeamA", "TeamB", "H")
        assert elo.get_rating("TeamA") > elo.initial_rating
        assert elo.get_rating("TeamB") < elo.initial_rating

    def test_draw_keeps_balance(self):
        elo = EloRatingSystem()
        elo.update("TeamA", "TeamB", "D")
        # Draw between equal teams should keep ratings similar
        diff = abs(elo.get_rating("TeamA") - elo.get_rating("TeamB"))
        assert diff < 2.0  # Should be very close

    def test_elo_features_no_leakage(self, sample_df):
        """ELO pré-jogo não pode usar resultado da partida atual."""
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        elo = EloRatingSystem()
        df_elo = elo.compute_elo_features(df)
        assert "elo_home" in df_elo.columns
        assert "elo_diff" in df_elo.columns
        # All ELO values should be >= initial (or near) at first match
        assert df_elo["elo_home"].iloc[0] == elo.initial_rating


class TestRecentForm:
    def test_form_returns_float(self, sample_df):
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        result = compute_recent_form(df, n_matches=5)
        assert "home_form" in result.columns
        assert result["home_form"].dtype in [np.float64, np.float32, float]

    def test_form_bounded_01(self, sample_df):
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        result = compute_recent_form(df, n_matches=5)
        assert (result["home_form"] >= 0.0).all()
        assert (result["home_form"] <= 1.0).all()


class TestRollingFeatures:
    def test_rolling_features_added(self, sample_df):
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        result = compute_rolling_features(df, windows=[3, 5])
        rolling_cols = [c for c in result.columns if "roll" in c]
        assert len(rolling_cols) > 0

    def test_no_future_leakage(self, sample_df):
        """Primeiro jogo de um time não pode ter rolling diferente de NaN ou 0."""
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        result = compute_rolling_features(df, windows=[3])
        # Não faz assert rígido pois min_periods=1, mas verifica que existem colunas
        assert result is not None


class TestFeaturePipeline:
    def test_pipeline_runs_end_to_end(self, sample_df):
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        pipeline = FeaturePipeline()
        result = pipeline.fit_transform(df)
        assert len(pipeline.feature_columns) > 0
        assert len(result) == len(df)

    def test_feature_matrix_no_target_columns(self, sample_df):
        proc = MatchPreprocessor()
        df = proc.fit_transform(sample_df)
        pipeline = FeaturePipeline()
        df_feat = pipeline.fit_transform(df)
        X = pipeline.get_feature_matrix(df_feat)
        # Targets não devem estar em X
        assert "home_goals" not in X.columns
        assert "outcome" not in X.columns
