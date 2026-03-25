"""
app/models/calibration.py
Utilitários de calibração probabilística e diagnóstico de qualidade.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logger import get_logger

logger = get_logger(__name__)


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Brier Score para classificação binária.
    Quanto menor, melhor. Probabilidade perfeita = 0.0. Aleatório ≈ 0.25.
    """
    return float(np.mean((y_prob - y_true) ** 2))


def brier_score_multiclass(y_true_ohe: np.ndarray, y_prob: np.ndarray) -> float:
    """Brier Score para multiclasse (usa one-hot encoding de y_true)."""
    return float(np.mean(np.sum((y_prob - y_true_ohe) ** 2, axis=1)))


def log_loss_safe(y_true: np.ndarray, y_prob: np.ndarray, eps: float = 1e-7) -> float:
    """Log-loss com clipping para evitar log(0)."""
    y_prob = np.clip(y_prob, eps, 1 - eps)
    return float(-np.mean(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)))


def calibration_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Curva de calibração: frequência observada vs. probabilidade prevista.

    Returns:
        (mean_predicted, fraction_positive) para cada bin.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    mean_pred = []
    frac_pos = []

    for i in range(n_bins):
        mask = (y_prob >= bins[i]) & (y_prob < bins[i + 1])
        if mask.sum() > 0:
            mean_pred.append(y_prob[mask].mean())
            frac_pos.append(y_true[mask].mean())

    return np.array(mean_pred), np.array(frac_pos)


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Expected Calibration Error (ECE):
    Média ponderada do desvio entre probabilidade predita e frequência real.
    ECE próximo de 0 = bem calibrado.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    n = len(y_true)
    ece = 0.0

    for i in range(n_bins):
        mask = (y_prob >= bins[i]) & (y_prob < bins[i + 1])
        if mask.sum() > 0:
            acc = y_true[mask].mean()
            conf = y_prob[mask].mean()
            ece += (mask.sum() / n) * abs(acc - conf)

    return float(ece)


def calibration_report(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    label: str = "binary",
) -> dict:
    """
    Relatório completo de calibração para um modelo binário.
    """
    from sklearn.metrics import roc_auc_score, accuracy_score

    y_pred = (y_prob >= 0.5).astype(int)

    report = {
        "label": label,
        "n_samples": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
        "brier_score": round(brier_score(y_true, y_prob), 4),
        "log_loss": round(log_loss_safe(y_true, y_prob), 4),
        "ece": round(expected_calibration_error(y_true, y_prob), 4),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
    }

    try:
        report["roc_auc"] = round(roc_auc_score(y_true, y_prob), 4)
    except Exception:
        report["roc_auc"] = None

    return report


def apply_platt_scaling(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> np.ndarray:
    """
    Aplica Platt Scaling (regressão logística 1D) para recalibrar probabilidades.
    Útil quando as probabilidades brutas do modelo estão sistematicamente desviadas.
    """
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(C=1.0, max_iter=1000)
    lr.fit(y_prob.reshape(-1, 1), y_true)
    calibrated = lr.predict_proba(y_prob.reshape(-1, 1))[:, 1]
    logger.debug(
        f"Platt scaling applied | before_mean={y_prob.mean():.3f} | after_mean={calibrated.mean():.3f}"
    )
    return calibrated
