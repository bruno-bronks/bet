"""
app/live/state_updater.py
Atualização de estado de partida ao vivo (estrutura para futura implementação).

NOTA: Esta é a base para inferência in-play.
Requer integração com feed de dados em tempo real (Sofascore, Opta, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LiveMatchState:
    """
    Estado atual de uma partida em andamento.
    Atualizado a cada evento significativo.
    """
    match_id: str
    competition: str
    home_team: str
    away_team: str
    minute: int = 0
    home_goals: int = 0
    away_goals: int = 0
    home_red_cards: int = 0
    away_red_cards: int = 0
    home_corners: int = 0
    away_corners: int = 0
    home_shots: int = 0
    away_shots: int = 0
    is_first_half: bool = True
    is_finished: bool = False
    last_updated: Optional[datetime] = None
    events: List[Dict] = field(default_factory=list)

    def add_goal(self, team: str, minute: int) -> None:
        if team == "home":
            self.home_goals += 1
        else:
            self.away_goals += 1
        self.events.append({"type": "goal", "team": team, "minute": minute})
        self.minute = minute
        self.last_updated = datetime.utcnow()

    def add_red_card(self, team: str, minute: int) -> None:
        if team == "home":
            self.home_red_cards += 1
        else:
            self.away_red_cards += 1
        self.events.append({"type": "red_card", "team": team, "minute": minute})

    @property
    def score_string(self) -> str:
        return f"{self.home_goals}-{self.away_goals}"

    @property
    def goals_remaining_expected(self) -> float:
        """Minutos restantes como fração do jogo (simplificado)."""
        return max(0, (90 - self.minute) / 90.0)
