"""
app/api/routes_health.py
Rotas de saúde e status da API.
"""
from fastapi import APIRouter

from app.api.schemas import HealthResponse
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    """Verifica se a API está operacional."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        supported_competitions=settings.SUPPORTED_COMPETITIONS,
    )


@router.get("/", include_in_schema=False)
async def root():
    return {"message": f"{settings.PROJECT_NAME} v{settings.VERSION} — see /docs"}
