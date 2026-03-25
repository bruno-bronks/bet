"""
app/core/logger.py
Configuração de logging estruturado para todo o sistema.
"""
from __future__ import annotations

import logging
import sys
from functools import lru_cache


def _build_formatter() -> logging.Formatter:
    """Cria formatter com nível, nome do módulo e mensagem."""
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    return logging.Formatter(fmt=fmt, datefmt=datefmt)


def _configure_root_logger(level: str = "INFO") -> None:
    """Configura o logger raiz (executado apenas uma vez)."""
    root = logging.getLogger()
    if root.handlers:
        return  # Já configurado

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


@lru_cache(maxsize=None)
def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Retorna logger nomeado (cacheado por nome).

    Uso:
        logger = get_logger(__name__)
        logger.info("Mensagem")
    """
    _configure_root_logger(level)
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


# Logger padrão do sistema
logger = get_logger("football_analysis")
