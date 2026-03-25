"""
app/training/trainer.py
Orquestra o treinamento completo de todos os modelos para uma competição.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.data.preprocess import MatchPreprocessor
from app.features.feature_pipeline import FeaturePipeline
from app.models.cards_model import CardsModel
from app.models.corners_model import CornersModel
from app.models.goals_model import GoalsModel
from app.models.outcome_model import OutcomeModel
from app.models.registry import ModelRegistry
from app.models.time_window_model import TimeWindowEnsemble
from app.training.evaluate import full_evaluation_report
from app.training.splitters import TemporalSplit

logger = get_logger(__name__)


class ModelTrainer:
    """
    Pipeline de treinamento completo.

    Fluxo:
      1. Carrega dados processados
      2. Aplica feature pipeline
      3. Faz split temporal
      4. Treina cada modelo
      5. Avalia no conjunto de validação
      6. Registra artefatos
    """

    def __init__(
        self,
        competition: str,
        registry: Optional[ModelRegistry] = None,
    ) -> None:
        self.competition = competition
        self.registry = registry or ModelRegistry()
        self.feature_pipeline = FeaturePipeline()
        self._metrics: Dict[str, dict] = {}

    def train_all(self, df: pd.DataFrame) -> Dict[str, dict]:
        """
        Treina todos os modelos para a competição.

        Args:
            df: DataFrame processado com partidas históricas.

        Returns:
            Dicionário de métricas por modelo.
        """
        logger.info(f"=== Starting full training for {self.competition} | {len(df)} matches ===")

        # ── Pré-processamento (adiciona total_goals, outcome, etc.) ────────────
        # Não passa competition para evitar filtro pós title-case que remove tudo
        preprocessor = MatchPreprocessor()
        df = preprocessor.fit_transform(df)

        # ── Feature engineering ───────────────────────────────────────────────
        df_feat = self.feature_pipeline.fit_transform(df)
        feature_cols = self.feature_pipeline.feature_columns

        if not feature_cols:
            raise ValueError("Feature pipeline returned 0 feature columns")

        # ── Split temporal ────────────────────────────────────────────────────
        splitter = TemporalSplit(
            test_size=settings.TEST_SIZE,
            val_size=settings.VALIDATION_SIZE,
        )
        train_df, val_df, test_df = splitter.split(df_feat)

        X_train = self.feature_pipeline.get_feature_matrix(train_df)
        X_val = self.feature_pipeline.get_feature_matrix(val_df)

        logger.info(f"X_train shape: {X_train.shape} | X_val shape: {X_val.shape}")

        # ── Modelo de resultado ───────────────────────────────────────────────
        self._train_outcome(X_train, train_df, X_val, val_df)

        # ── Modelo de gols ────────────────────────────────────────────────────
        self._train_goals(X_train, train_df, X_val, val_df)

        # ── Modelo de escanteios ──────────────────────────────────────────────
        self._train_corners(X_train, train_df, X_val, val_df)

        # ── Modelo de cartões ─────────────────────────────────────────────────
        self._train_cards(X_train, train_df, X_val, val_df)

        # ── Modelos de janela temporal ────────────────────────────────────────
        self._train_time_windows(X_train, train_df)

        logger.info(f"=== Training complete for {self.competition} ===")
        return self._metrics

    # ── Métodos privados por modelo ───────────────────────────────────────────

    def _train_outcome(self, X_train, train_df, X_val, val_df) -> None:
        target = "outcome"
        if target not in train_df.columns:
            logger.warning(f"Column '{target}' not found — skipping outcome model")
            return

        y_train = train_df[target].dropna()
        X_train_a = X_train.loc[y_train.index]

        model = OutcomeModel(competition=self.competition)
        model.fit(X_train_a, y_train)

        # Avaliação
        y_val = val_df[target].dropna()
        X_val_a = X_val.loc[y_val.index]
        y_pred = model.predict(X_val_a)
        y_prob = model.predict_proba(X_val_a)
        metrics = full_evaluation_report("outcome", y_val.values, y_pred, y_prob,
                                         label_encoder=model._label_encoder)
        self._metrics["outcome"] = metrics
        logger.info(f"Outcome model | accuracy={metrics.get('accuracy')} | log_loss={metrics.get('log_loss')}")

        self.registry.register(model, metrics)

    def _train_goals(self, X_train, train_df, X_val, val_df) -> None:
        required = {"home_goals", "away_goals"}
        if not required.issubset(train_df.columns):
            logger.warning("Goals columns not found — skipping")
            return

        y_train = train_df[["home_goals", "away_goals"]].dropna()
        X_train_a = X_train.loc[y_train.index]

        model = GoalsModel(competition=self.competition)
        model.fit(X_train_a, y_train)

        # Avaliação: MAE nas taxas esperadas vs. gols reais
        y_val = val_df[["home_goals", "away_goals"]].dropna()
        X_val_a = X_val.loc[y_val.index]
        preds = model.predict(X_val_a)

        import numpy as np
        mae_home = float(np.mean(np.abs(preds[:, 0] - y_val["home_goals"].values)))
        mae_away = float(np.mean(np.abs(preds[:, 1] - y_val["away_goals"].values)))
        metrics = {"mae_home": round(mae_home, 3), "mae_away": round(mae_away, 3)}
        self._metrics["goals"] = metrics
        logger.info(f"Goals model | mae_home={mae_home:.3f} | mae_away={mae_away:.3f}")

        self.registry.register(model, metrics)

    def _train_corners(self, X_train, train_df, X_val, val_df) -> None:
        required = {"home_corners", "away_corners"}
        if not required.issubset(train_df.columns):
            logger.warning("Corners columns not found — skipping corners model")
            return

        y_train = train_df[["home_corners", "away_corners"]].dropna()
        X_train_a = X_train.loc[y_train.index]

        # Adiciona total_corners se disponível
        if "total_corners" in train_df.columns:
            y_train = y_train.join(train_df["total_corners"])

        model = CornersModel(competition=self.competition)
        model.fit(X_train_a, y_train)
        self._metrics["corners"] = {"status": "fitted"}
        self.registry.register(model)

    def _train_cards(self, X_train, train_df, X_val, val_df) -> None:
        card_cols = {"home_total_cards", "away_total_cards"}
        if not card_cols.issubset(train_df.columns):
            logger.warning("Cards columns not found — skipping cards model")
            return

        y_train = train_df[list(card_cols)].dropna()
        X_train_a = X_train.loc[y_train.index]

        model = CardsModel(competition=self.competition)
        model.fit(X_train_a, y_train)
        self._metrics["cards"] = {"status": "fitted"}
        self.registry.register(model)

    def _train_time_windows(self, X_train, train_df) -> None:
        ensemble = TimeWindowEnsemble(competition=self.competition)
        ensemble.fit(X_train, train_df)
        self.registry.register_time_window(ensemble)
        self._metrics["time_window"] = {"status": "fitted"}
