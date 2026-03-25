"""
app/inference/explainability.py
Explicabilidade das previsões via SHAP e feature importance.
"""
from __future__ import annotations

import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from app.models.base_model import BaseFootballModel

logger = get_logger(__name__)


def get_feature_importance(
    model: BaseFootballModel,
    X: pd.DataFrame,
    top_n: int = 10,
) -> List[Dict]:
    """
    Retorna as N features mais importantes para a predição.
    Tenta SHAP primeiro; cai de volta para importância do modelo.
    """
    feat_cols = model.feature_columns
    X_prep = model._prepare_X(X)

    # Tenta SHAP
    shap_values = _try_shap(model, X_prep, feat_cols)
    if shap_values is not None:
        return shap_values[:top_n]

    # Fallback: importância interna do LightGBM/sklearn
    return _get_model_importance(model, feat_cols, top_n)


def _try_shap(
    model: BaseFootballModel,
    X_prep: pd.DataFrame,
    feat_cols: List[str],
) -> Optional[List[Dict]]:
    """Tenta calcular SHAP values. Retorna None se não disponível."""
    try:
        import shap

        inner_model = model._model
        # CalibratedClassifierCV — extrai o estimador base
        if hasattr(inner_model, "calibrated_classifiers_"):
            inner_model = inner_model.calibrated_classifiers_[0].estimator

        explainer = shap.TreeExplainer(inner_model)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            shap_vals = explainer.shap_values(X_prep.values.astype(np.float32))

        # Para multiclasse, pega a magnitude média por feature
        if isinstance(shap_vals, list):
            abs_mean = np.mean([np.abs(sv) for sv in shap_vals], axis=0)
        else:
            abs_mean = np.abs(shap_vals)

        # Agrega por feature (média sobre amostras)
        importance = abs_mean.mean(axis=0) if abs_mean.ndim > 1 else abs_mean

        result = sorted(
            [
                {"feature": feat, "shap_importance": round(float(imp), 5), "method": "shap"}
                for feat, imp in zip(feat_cols, importance)
            ],
            key=lambda x: x["shap_importance"],
            reverse=True,
        )
        return result

    except Exception as e:
        logger.debug(f"SHAP not available: {e}")
        return None


def _get_model_importance(
    model: BaseFootballModel,
    feat_cols: List[str],
    top_n: int,
) -> List[Dict]:
    """Importância de features via atributos do modelo sklearn/lgbm."""
    inner = model._model
    if hasattr(inner, "calibrated_classifiers_"):
        inner = inner.calibrated_classifiers_[0].estimator

    importance = None

    if hasattr(inner, "feature_importances_"):
        importance = inner.feature_importances_
    elif hasattr(inner, "coef_"):
        importance = np.abs(inner.coef_).mean(axis=0) if inner.coef_.ndim > 1 else np.abs(inner.coef_[0])

    if importance is None or len(importance) != len(feat_cols):
        return []

    result = sorted(
        [
            {"feature": feat, "importance": round(float(imp), 5), "method": "model_importance"}
            for feat, imp in zip(feat_cols, importance)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )
    return result[:top_n]


def generate_natural_language_explanation(
    prediction,
    top_features: List[Dict],
    confidence: float,
) -> str:
    """
    Gera explicação textual da previsão em linguagem natural.

    NOTA: É uma síntese estatística, não uma análise especializada.
    """
    lines = []

    lines.append(
        f"Análise probabilística: {prediction.home_team} vs {prediction.away_team} "
        f"[{prediction.competition}] em {prediction.match_date}"
    )
    lines.append("")

    # Resultado mais provável
    outcomes = {
        "vitória do mandante": prediction.home_win,
        "empate": prediction.draw,
        "vitória do visitante": prediction.away_win,
    }
    most_likely = max(outcomes, key=outcomes.get)
    prob_most_likely = outcomes[most_likely]

    lines.append(f"O resultado mais provável segundo o modelo é {most_likely} "
                 f"(estimativa: {prob_most_likely:.1%}).")

    # Gols
    lines.append(
        f"Expectativa de gols: {prediction.expected_goals_home:.1f} (mandante) + "
        f"{prediction.expected_goals_away:.1f} (visitante) = "
        f"{prediction.expected_goals_total:.1f} total."
    )
    lines.append(
        f"Probabilidade estimada de over 2.5 gols: {prediction.over_2_5:.1%}. "
        f"Ambas as equipes marcam: {prediction.both_teams_score:.1%}."
    )

    # Features mais relevantes
    if top_features:
        feat_names = [f["feature"] for f in top_features[:3]]
        lines.append(f"Fatores mais relevantes no modelo: {', '.join(feat_names)}.")

    # Confiança
    if confidence < 0.5:
        lines.append(
            f"⚠ Alerta: confiança baixa ({confidence:.0%}). "
            "Histórico insuficiente pode comprometer a qualidade das estimativas."
        )
    else:
        lines.append(f"Grau de confiança do modelo: {confidence:.0%}.")

    lines.append("")
    lines.append(
        "IMPORTANTE: Estas são estimativas probabilísticas baseadas em padrões históricos. "
        "Resultados reais podem divergir significativamente."
    )

    return "\n".join(lines)
