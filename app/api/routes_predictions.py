"""
app/api/routes_predictions.py
Rotas de inferência e treinamento da API.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    ModelsResponse,
    ModelListItem,
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)
from app.core.config import settings
from app.core.logger import get_logger
from app.inference.predictor import FootballPredictor, MatchContext
from app.inference.postprocess import postprocess_prediction
from app.inference.serializer import prediction_to_dict
from app.models.registry import ModelRegistry
from app.training.trainer import ModelTrainer

logger = get_logger(__name__)
router = APIRouter(tags=["predictions"])

# Data de corte para cada competição — apenas partidas desta data em diante
# são usadas para calcular forma/contexto histórico nas previsões.
CURRENT_SEASON_CUTOFF: dict[str, str] = {
    "brasileirao": "2026-01-01",       # Brasileirão 2026
    "champions_league": "2025-08-01",  # UCL 2025/26 (começa em agosto)
}

# ── Dependências globais ──────────────────────────────────────────────────────

_registry: Optional[ModelRegistry] = None
_predictors: dict[str, FootballPredictor] = {}


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def get_predictor(competition: str) -> FootballPredictor:
    """Carrega (e cacheia) predictor para a competição."""
    global _predictors
    if competition not in _predictors:
        import pandas as pd
        processed_dir = settings.PROCESSED_DATA_DIR
        all_csvs = list(processed_dir.glob(f"{competition}_*.csv"))

        if not all_csvs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No processed data found for '{competition}'. "
                    "Run POST /train first or place CSV files in data/processed/."
                ),
            )

        # Carrega todos os CSVs; coloca _with_stats por último para que, na deduplicação,
        # os registros com stats completas prevaleçam sobre os registros base.
        csv_files_sorted = sorted(
            all_csvs,
            key=lambda f: (1 if "_with_stats" in f.name else 0),
        )
        frames = [pd.read_csv(f, parse_dates=["date"]) for f in csv_files_sorted]
        df = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates(
                subset=["competition", "date", "home_team", "away_team"],
                keep="last",  # mantém a versão with_stats (carregada por último)
            )
            .sort_values("date")
        )

        # O DataFrame completo vai para o predictor para calibrar ELO e pipeline.
        # O season_cutoff restringe apenas o lookup de forma dos times em _build_feature_row.
        season_cutoff = CURRENT_SEASON_CUTOFF.get(competition)
        _predictors[competition] = FootballPredictor(
            df,
            registry=get_registry(),
            season_cutoff=season_cutoff,
        )

    return _predictors[competition]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Generate match probability analysis",
    description=(
        "Retorna estimativas probabilísticas para múltiplos eventos de uma partida. "
        "**Não é uma previsão garantida** — são probabilidades sujeitas à incerteza estatística."
    ),
)
async def predict(req: PredictRequest) -> PredictResponse:
    logger.info(f"Predict request: {req.home_team} vs {req.away_team} [{req.competition}]")

    try:
        predictor = get_predictor(req.competition)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to load predictor: {e}",
        )

    context = MatchContext(
        competition=req.competition,
        home_team=req.home_team,
        away_team=req.away_team,
        match_date=req.match_date,
        stage=req.stage,
        matchday=req.matchday,
    )

    try:
        raw_pred = predictor.predict(context)
        pred = postprocess_prediction(raw_pred)
        result_dict = prediction_to_dict(pred)

        if req.include_explanation:
            from app.inference.explainability import generate_natural_language_explanation
            result_dict["natural_language_explanation"] = generate_natural_language_explanation(
                pred, pred.top_features, pred.confidence_score
            )

        return PredictResponse(**result_dict)

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {e}",
        )


@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train all models for a competition",
)
async def train(req: TrainRequest) -> TrainResponse:
    """
    Treina (ou re-treina) todos os modelos para a competição especificada.
    """
    competition = req.competition.lower()
    if competition not in settings.SUPPORTED_COMPETITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported competition: {competition}",
        )

    # Verifica se já existe modelo e não forçar re-treino
    registry = get_registry()
    if not req.force_retrain and registry.is_available("outcome", competition):
        return TrainResponse(
            status="skipped",
            competition=competition,
            message="Model already exists. Set force_retrain=true to retrain.",
        )

    # Carrega dados
    import pandas as pd

    if req.data_path:
        p = Path(req.data_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Data file not found: {req.data_path}")
        df = pd.read_csv(p, parse_dates=["date"])
    else:
        files = list(settings.PROCESSED_DATA_DIR.glob(f"{competition}_*.csv"))
        if not files:
            raise HTTPException(
                status_code=404,
                detail=f"No processed data for '{competition}'. Add CSVs to data/processed/.",
            )
        df = pd.concat([pd.read_csv(f, parse_dates=["date"]) for f in files], ignore_index=True)

    # Invalida cache do predictor
    _predictors.pop(competition, None)

    try:
        trainer = ModelTrainer(competition=competition, registry=registry)
        metrics = trainer.train_all(df)
        return TrainResponse(
            status="success",
            competition=competition,
            metrics=metrics,
            message=f"All models trained successfully for {competition}",
        )
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training failed: {e}",
        )


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="List all registered models",
)
async def list_models() -> ModelsResponse:
    registry = get_registry()
    items = registry.list_models()
    return ModelsResponse(
        models=[ModelListItem(**item) for item in items],
        total=len(items),
    )
