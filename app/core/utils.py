"""
app/core/utils.py
Utilitários gerais: helpers de data, cálculos estatísticos, formatação.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logger import get_logger

logger = get_logger(__name__)


# ── Hashing / IDs ─────────────────────────────────────────────────────────────

def generate_match_id(competition: str, date_str: str, home_team: str, away_team: str) -> str:
    """Gera ID único reproduzível para uma partida."""
    raw = f"{competition}_{date_str}_{home_team}_{away_team}".lower().replace(" ", "_")
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ── Datas ─────────────────────────────────────────────────────────────────────

def parse_date(value: Any) -> Optional[date]:
    """Tenta converter diferentes formatos para date."""
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def days_since(reference: date, target: date) -> int:
    """Retorna dias entre duas datas (positivo = target é mais recente)."""
    return (target - reference).days


def season_from_date(d: date) -> str:
    """Infere temporada a partir da data (ex: 2023/24 para Champions, 2023 para Brasileirão)."""
    year = d.year
    month = d.month
    if month >= 7:
        return f"{year}/{str(year + 1)[-2:]}"
    return f"{year - 1}/{str(year)[-2:]}"


# ── Estatísticas ──────────────────────────────────────────────────────────────

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura — retorna `default` se denominador for zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def normalize_probabilities(probs: List[float]) -> List[float]:
    """
    Normaliza lista de probabilidades para somar 1.0.
    Garante que nenhum valor seja negativo.
    """
    probs = [max(0.0, p) for p in probs]
    total = sum(probs)
    if total == 0:
        n = len(probs)
        return [1.0 / n] * n
    return [p / total for p in probs]


def poisson_probability(lam: float, k: int) -> float:
    """P(X = k) para distribuição de Poisson com parâmetro lambda."""
    from scipy.stats import poisson
    return float(poisson.pmf(k, lam))


def poisson_over_probability(lam: float, line: float) -> float:
    """P(X > line) para Poisson. Ex.: over 2.5 → P(X >= 3)."""
    from scipy.stats import poisson
    k_min = int(line) + 1
    return float(1 - poisson.cdf(k_min - 1, lam))


def bivariate_poisson_scoreline_probs(
    lam_home: float, lam_away: float, max_goals: int = 6
) -> Dict[Tuple[int, int], float]:
    """
    Calcula probabilidades de placar usando independência de Poisson bivariado.
    Retorna dict {(home_goals, away_goals): probabilidade}.

    NOTA: Assume independência entre gols do mandante e visitante.
    Modelos mais sofisticados (Dixon-Coles) podem corrigir baixos scores.
    """
    probs: Dict[Tuple[int, int], float] = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            probs[(h, a)] = poisson_probability(lam_home, h) * poisson_probability(lam_away, a)
    return probs


def top_n_scorelines(
    probs: Dict[Tuple[int, int], float], n: int = 10
) -> List[Dict[str, Any]]:
    """Retorna os N placares mais prováveis ordenados por probabilidade."""
    sorted_items = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]
    return [
        {"scoreline": f"{h}-{a}", "home_goals": h, "away_goals": a, "probability": round(p, 4)}
        for (h, a), p in sorted_items
    ]


# ── DataFrame helpers ─────────────────────────────────────────────────────────

def safe_fillna(df: pd.DataFrame, column: str, value: Any) -> pd.DataFrame:
    """Fill NA em coluna se ela existir no DataFrame."""
    if column in df.columns:
        df[column] = df[column].fillna(value)
    return df


def add_outcome_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona coluna 'outcome': 'H' (mandante vence), 'D' (empate), 'A' (visitante vence).
    Requer colunas 'home_goals' e 'away_goals'.
    """
    df = df.copy()
    conditions = [
        df["home_goals"] > df["away_goals"],
        df["home_goals"] == df["away_goals"],
        df["home_goals"] < df["away_goals"],
    ]
    choices = ["H", "D", "A"]
    df["outcome"] = np.select(conditions, choices, default="D")
    return df


# ── Serialização JSON ─────────────────────────────────────────────────────────

class JSONEncoder(json.JSONEncoder):
    """Encoder customizado para tipos numpy/pandas."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        return super().default(obj)


def to_json(obj: Any) -> str:
    """Serializa objeto para JSON usando o encoder customizado."""
    return json.dumps(obj, cls=JSONEncoder, ensure_ascii=False, indent=2)
