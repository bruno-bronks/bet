"""
app/api/main.py
Ponto de entrada da API FastAPI.

Execução:
    uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_fixtures import router as fixtures_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_predictions import router as predictions_router
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Eventos de startup/shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Plataforma de análise probabilística para partidas de futebol. "
        "Brasileirão e UEFA Champions League.\n\n"
        "**AVISO**: Todas as saídas são estimativas probabilísticas baseadas em dados históricos. "
        "Não constituem previsão garantida. A incerteza é parte intrínseca de qualquer análise estatística."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — ajuste os origins em produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(predictions_router, prefix=settings.API_PREFIX)
app.include_router(fixtures_router, prefix=settings.API_PREFIX)
app.include_router(history_router, prefix=settings.API_PREFIX)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
