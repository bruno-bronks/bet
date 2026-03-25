"""
app/core/config.py
Configuração centralizada do sistema via Pydantic Settings.
Todas as variáveis de ambiente e parâmetros globais vivem aqui.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Projeto ──────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "Football Probabilistic Analysis Platform"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Competições suportadas ────────────────────────────────────────────────
    SUPPORTED_COMPETITIONS: List[str] = ["brasileirao", "champions_league"]
    BRASILEIRAO_NAME: str = "brasileirao"
    UCL_NAME: str = "champions_league"

    # ── Diretórios (resolvidos em model_post_init) ────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Optional[Path] = None
    RAW_DATA_DIR: Optional[Path] = None
    PROCESSED_DATA_DIR: Optional[Path] = None
    SAMPLES_DATA_DIR: Optional[Path] = None
    MODELS_DIR: Optional[Path] = None

    # ── Banco de dados ────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./football_analysis.db"

    # ── API ───────────────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    # ── Parâmetros de treinamento ─────────────────────────────────────────────
    RANDOM_STATE: int = 42
    TEST_SIZE: float = 0.2
    VALIDATION_SIZE: float = 0.1
    N_JOBS: int = -1
    CV_FOLDS: int = 5

    # ── LightGBM padrão ───────────────────────────────────────────────────────
    LGBM_N_ESTIMATORS: int = 300
    LGBM_LEARNING_RATE: float = 0.05
    LGBM_MAX_DEPTH: int = 6
    LGBM_NUM_LEAVES: int = 31
    LGBM_MIN_CHILD_SAMPLES: int = 20
    LGBM_SUBSAMPLE: float = 0.8
    LGBM_COLSAMPLE_BYTREE: float = 0.8

    # ── Features de janela temporal ───────────────────────────────────────────
    ROLLING_WINDOWS: List[int] = [3, 5, 10]
    RECENT_FORM_MATCHES: int = 5

    # ── ELO ───────────────────────────────────────────────────────────────────
    ELO_K_FACTOR: float = 32.0
    ELO_INITIAL_RATING: float = 1500.0
    ELO_HOME_ADVANTAGE: float = 100.0

    # ── API-Football (api-sports.io) — plano gratuito: 2022-2024 ─────────────
    API_FOOTBALL_KEY: str = ""
    API_FOOTBALL_BASE_URL: str = "https://v3.football.api-sports.io"

    # ── football-data.org — plano gratuito: temporada atual ───────────────────
    FOOTBALL_DATA_KEY: str = ""
    FOOTBALL_DATA_BASE_URL: str = "https://api.football-data.org/v4"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        """Inicializa paths derivados após a criação do objeto."""
        object.__setattr__(self, "DATA_DIR", self.BASE_DIR / "data")
        object.__setattr__(self, "RAW_DATA_DIR", self.BASE_DIR / "data" / "raw")
        object.__setattr__(self, "PROCESSED_DATA_DIR", self.BASE_DIR / "data" / "processed")
        object.__setattr__(self, "SAMPLES_DATA_DIR", self.BASE_DIR / "data" / "samples")
        object.__setattr__(self, "MODELS_DIR", self.BASE_DIR / "models_artifacts")
        for d in [self.RAW_DATA_DIR, self.PROCESSED_DATA_DIR, self.SAMPLES_DATA_DIR, self.MODELS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    @field_validator("TEST_SIZE", "VALIDATION_SIZE")
    @classmethod
    def validate_split_sizes(cls, v: float) -> float:
        if not 0 < v < 1:
            raise ValueError("Split sizes must be between 0 and 1")
        return v


# Singleton — importar como `from app.core.config import settings`
settings = Settings()
