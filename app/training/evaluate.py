"""
app/training/evaluate.py
Métricas de avaliação para modelos de classificação e regressão.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from app.models.calibration import (
    brier_score,
    log_loss_safe,
    calibration_report,
    expected_calibration_error,
)

logger = get_logger(__name__)


def evaluate_outcome_model(
    y_true: np.ndarray,
    y_pred_classes: np.ndarray,
    y_prob: np.ndarray,
    label_encoder=None,
) -> Dict:
    """Avalia modelo de resultado 1X2."""
    from sklearn.metrics import accuracy_score, classification_report, log_loss

    acc = accuracy_score(y_true, y_pred_classes)

    # Log-loss multiclasse (sklearn)
    try:
        ll = log_loss(y_true, y_prob)
    except Exception:
        ll = None

    # Brier Score multiclasse
    classes = label_encoder.classes_ if label_encoder else np.unique(y_true)
    ohe = pd.get_dummies(y_true).reindex(columns=classes, fill_value=0).values
    bs = float(np.mean(np.sum((y_prob - ohe) ** 2, axis=1)))

    report = {
        "accuracy": round(acc, 4),
        "log_loss": round(ll, 4) if ll else None,
        "brier_score_multiclass": round(bs, 4),
    }

    try:
        cr = classification_report(y_true, y_pred_classes, output_dict=True)
        report["per_class"] = {
            k: {m: round(v, 3) for m, v in v_dict.items()}
            for k, v_dict in cr.items()
            if isinstance(v_dict, dict)
        }
    except Exception:
        pass

    return report


def evaluate_regression_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label: str = "regression",
) -> Dict:
    """Avalia modelo de regressão (gols, escanteios, cartões)."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    bias = float(np.mean(y_pred - y_true))

    return {
        "label": label,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "bias": round(bias, 4),
        "mean_true": round(float(y_true.mean()), 4),
        "mean_pred": round(float(y_pred.mean()), 4),
    }


def evaluate_binary_model(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    label: str = "binary",
) -> Dict:
    """Avalia modelo de classificação binária."""
    return calibration_report(y_true, y_prob, label=label)


def full_evaluation_report(
    model_type: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
    **kwargs,
) -> Dict:
    """
    Relatório de avaliação completo baseado no tipo de modelo.
    """
    logger.info(f"Evaluating model: {model_type}")

    if model_type == "outcome":
        return evaluate_outcome_model(y_true, y_pred, y_prob, **kwargs)
    elif model_type in ("goals", "corners", "cards"):
        return evaluate_regression_model(y_true, y_pred, label=model_type)
    elif model_type == "time_window":
        return evaluate_binary_model(y_true, y_prob[:, 1] if y_prob.ndim > 1 else y_prob)
    else:
        return {"warning": f"Unknown model_type: {model_type}"}
