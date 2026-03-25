"""
app/models/registry.py
Registro central de modelos: carrega, salva e lista artefatos treinados.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logger import get_logger
from app.models.base_model import BaseFootballModel
from app.models.outcome_model import OutcomeModel
from app.models.goals_model import GoalsModel
from app.models.corners_model import CornersModel
from app.models.cards_model import CardsModel
from app.models.time_window_model import TimeWindowEnsemble

logger = get_logger(__name__)

MODEL_CLASS_MAP = {
    "outcome": OutcomeModel,
    "goals": GoalsModel,
    "corners": CornersModel,
    "cards": CardsModel,
}


class ModelRegistry:
    """
    Registro centralizado que gerencia artefatos de modelo em disco.

    Estrutura de artefatos:
        models_artifacts/
          {competition}/
            outcome.joblib
            goals.joblib
            corners.joblib
            cards.joblib
            time_window_{event}.joblib
            registry.json   ← metadados
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or settings.MODELS_DIR
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    # ── Persistência do registry ───────────────────────────────────────────────

    def _registry_path(self) -> Path:
        return self.base_dir / "registry.json"

    def _load_registry(self) -> None:
        path = self._registry_path()
        if path.exists():
            with open(path) as f:
                self._registry = json.load(f)
            logger.debug(f"Registry loaded: {len(self._registry)} entries")

    def _save_registry(self) -> None:
        path = self._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._registry, f, indent=2, default=str)

    # ── Caminhos de artefatos ─────────────────────────────────────────────────

    def _model_path(self, model_type: str, competition: str) -> Path:
        return self.base_dir / competition / f"{model_type}.joblib"

    def _time_window_dir(self, competition: str) -> Path:
        return self.base_dir / competition

    # ── Registro e salvamento ─────────────────────────────────────────────────

    def register(
        self,
        model: BaseFootballModel,
        metrics: Optional[Dict[str, float]] = None,
    ) -> str:
        """Salva modelo em disco e registra metadados."""
        competition = model.competition or "all"
        model_type = model.model_type
        path = self._model_path(model_type, competition)
        path.parent.mkdir(parents=True, exist_ok=True)

        model.save(path)

        key = f"{competition}/{model_type}"
        self._registry[key] = {
            "competition": competition,
            "model_type": model_type,
            "path": str(path),
            "metrics": metrics or {},
            "feature_count": len(model.feature_columns),
        }
        self._save_registry()
        logger.info(f"Model registered: {key}")
        return key

    def register_time_window(self, ensemble: TimeWindowEnsemble) -> None:
        """Salva ensemble de janelas temporais."""
        competition = ensemble.competition or "all"
        base_path = self._time_window_dir(competition)
        ensemble.save_all(base_path)

        key = f"{competition}/time_window"
        self._registry[key] = {"competition": competition, "model_type": "time_window"}
        self._save_registry()
        logger.info(f"TimeWindowEnsemble registered: {key}")

    # ── Carregamento ──────────────────────────────────────────────────────────

    def load(self, model_type: str, competition: str) -> BaseFootballModel:
        """Carrega modelo do disco."""
        path = self._model_path(model_type, competition)
        if not path.exists():
            raise FileNotFoundError(
                f"No model artifact found for {model_type}/{competition} at {path}"
            )

        cls = MODEL_CLASS_MAP.get(model_type)
        if cls is None:
            raise ValueError(f"Unknown model_type: {model_type}")

        model = cls(competition=competition)
        model.load(path)
        return model

    def load_time_window(self, competition: str) -> TimeWindowEnsemble:
        base_path = self._time_window_dir(competition)
        ensemble = TimeWindowEnsemble(competition=competition)
        ensemble.load_all(base_path)
        return ensemble

    # ── Listagem ──────────────────────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        """Retorna lista de todos os modelos registrados."""
        return [
            {"key": k, **v}
            for k, v in self._registry.items()
        ]

    def is_available(self, model_type: str, competition: str) -> bool:
        """Verifica se um modelo está disponível em disco."""
        return self._model_path(model_type, competition).exists()
