from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class MatchHistorical(BaseModel):
    match_id: str
    date: datetime
    competition: str = Field(..., description="Brasileirao or UEFA Champions League")
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
    home_corners: int
    away_corners: int
    home_cards: int
    away_cards: int
    home_possession: Optional[float] = None
    away_possession: Optional[float] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None

class ContextFeatures(BaseModel):
    is_derby: bool = False
    days_since_last_match_home: Optional[int] = None
    days_since_last_match_away: Optional[int] = None
    weather_condition: Optional[str] = None
    round_number: Optional[int] = None

class ProbabilisticPrediction(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    competition: str
    
    # Probabilidades Principais
    prob_home_win: float = Field(..., ge=0.0, le=1.0)
    prob_draw: float = Field(..., ge=0.0, le=1.0)
    prob_away_win: float = Field(..., ge=0.0, le=1.0)
    
    # Gols
    exp_total_goals: float
    prob_over_2_5: float = Field(..., ge=0.0, le=1.0)
    prob_btts: float = Field(..., ge=0.0, le=1.0)
    most_likely_scores: dict[str, float]
    
    # Eventos temporais
    prob_goal_first_15: float
    prob_goal_last_15: float
    
    # Eventos Secundários
    exp_home_corners: float
    exp_away_corners: float
    exp_total_cards: float

    # Metadados de predição
    confidence_score: float = Field(..., description="1.0 to 10.0 based on available data history")
    top_features_home: list[str] = []
    top_features_away: list[str] = []
    warning_low_data: bool = False
    disclaimer: str = "Estimativas estatísticas. Não representa certeza ou recomendação de aposta."
