"""
app/live/live_predictor.py
Predictor in-play (estrutura base — requer modelos live dedicados).

A inferência live é fundamentalmente diferente da pré-jogo:
  - O estado do jogo (placar, cartões, minuto) é a feature mais importante
  - Modelos pré-jogo PODEM ser adaptados mas precisam de recalibração
  - Modelos live dedicados requerem dados de eventos minuto-a-minuto
"""
from __future__ import annotations

from typing import Dict, Optional

from app.core.logger import get_logger
from app.core.utils import poisson_over_probability
from app.live.state_updater import LiveMatchState
from scipy.stats import poisson

logger = get_logger(__name__)


class LivePredictor:
    """
    Predictor in-play simplificado baseado em ajuste dinâmico.

    Abordagem:
      1. Parte das probabilidades pré-jogo
      2. Ajusta dinamicamente com base no placar atual e minuto
      3. Usa modelo de Poisson ajustado ao tempo restante

    NOTA: Esta é uma implementação simplificada.
    Modelos live de alta qualidade requerem dados de eventos granulares.
    """

    def __init__(self, pre_game_lambda_home: float, pre_game_lambda_away: float) -> None:
        self.pre_game_lam_home = pre_game_lambda_home
        self.pre_game_lam_away = pre_game_lambda_away

    def update(self, state: LiveMatchState) -> Dict:
        """
        Recalcula probabilidades dado o estado atual do jogo.
        """
        time_fraction = max(0.01, (90 - state.minute) / 90.0)

        # Gols esperados restantes (proporcional ao tempo restante)
        lam_home_remaining = self.pre_game_lam_home * time_fraction
        lam_away_remaining = self.pre_game_lam_away * time_fraction

        # Ajuste por cartões vermelhos (reduz taxa de gol ~15% por cartão)
        lam_home_remaining *= max(0.4, 1.0 - 0.15 * state.home_red_cards)
        lam_away_remaining *= max(0.4, 1.0 - 0.15 * state.away_red_cards)

        # Calcula probabilidades de resultado final
        home_score = state.home_goals
        away_score = state.away_goals

        p_home_win, p_draw, p_away_win = self._outcome_probs(
            home_score, away_score, lam_home_remaining, lam_away_remaining
        )

        return {
            "minute": state.minute,
            "current_score": state.score_string,
            "live_home_win": round(p_home_win, 4),
            "live_draw": round(p_draw, 4),
            "live_away_win": round(p_away_win, 4),
            "expected_goals_remaining_home": round(lam_home_remaining, 3),
            "expected_goals_remaining_away": round(lam_away_remaining, 3),
            "disclaimer": "Live probabilities are simplified estimates — significant uncertainty applies.",
        }

    def _outcome_probs(
        self,
        h: int,
        a: int,
        lam_h: float,
        lam_a: float,
        max_goals: int = 8,
    ) -> tuple[float, float, float]:
        """Probabilidades de resultado final via Poisson."""
        p_hw = p_d = p_aw = 0.0
        for dh in range(max_goals + 1):
            for da in range(max_goals + 1):
                p = poisson.pmf(dh, lam_h) * poisson.pmf(da, lam_a)
                total_h = h + dh
                total_a = a + da
                if total_h > total_a:
                    p_hw += p
                elif total_h == total_a:
                    p_d += p
                else:
                    p_aw += p
        total = p_hw + p_d + p_aw
        if total > 0:
            p_hw /= total
            p_d /= total
            p_aw /= total
        return p_hw, p_d, p_aw
