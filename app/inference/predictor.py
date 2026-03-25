"""
app/inference/predictor.py
Motor principal de inferência pré-jogo.
Recebe contexto da partida e retorna previsão completa.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.constants import Competition
from app.core.logger import get_logger
from app.core.utils import normalize_probabilities
from app.data.preprocess import MatchPreprocessor
from app.features.feature_pipeline import FeaturePipeline
from app.models.registry import ModelRegistry

logger = get_logger(__name__)


@dataclass
class MatchContext:
    """Contexto de entrada para inferência."""
    competition: str
    home_team: str
    away_team: str
    match_date: date
    stage: Optional[str] = None
    matchday: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competition": self.competition,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "date": self.match_date,
            "stage": self.stage,
            "matchday": self.matchday,
        }


@dataclass
class PredictionOutput:
    """Saída estruturada de uma previsão pré-jogo."""

    # Metadados
    competition: str
    home_team: str
    away_team: str
    match_date: str

    # Resultado (1X2)
    home_win: float
    draw: float
    away_win: float

    # Gols
    expected_goals_home: float
    expected_goals_away: float
    expected_goals_total: float
    over_0_5: float
    over_1_5: float
    over_2_5: float
    over_3_5: float
    over_4_5: float
    both_teams_score: float
    clean_sheet_home: float
    clean_sheet_away: float

    # Placares prováveis
    top_scorelines: List[Dict]

    # Escanteios
    expected_corners_total: float
    expected_corners_home: float
    expected_corners_away: float

    # Cartões
    expected_cards_total: float
    expected_cards_home: float
    expected_cards_away: float

    # Janelas temporais
    goal_first_15min: float
    goal_last_15min: float
    goal_first_half: float
    goal_second_half: float

    # Explicabilidade
    top_features: List[Dict] = field(default_factory=list)
    confidence_score: float = 0.5
    low_confidence_warning: bool = False
    model_warnings: List[str] = field(default_factory=list)


class FootballPredictor:
    """
    Motor de inferência que:
      1. Constrói features para a partida alvo usando dados históricos
      2. Chama cada modelo registrado
      3. Agrega resultados em PredictionOutput
    """

    def __init__(
        self,
        historical_df: pd.DataFrame,
        registry: Optional[ModelRegistry] = None,
        season_cutoff: Optional[str] = None,
    ) -> None:
        """
        Args:
            historical_df: DataFrame completo com histórico de partidas.
                           Usado para calibrar o pipeline de features (ELO, médias).
            registry: ModelRegistry com modelos treinados.
            season_cutoff: Data ISO (YYYY-MM-DD). Quando informada, o lookup de
                           forma/histórico dos times em _build_feature_row usa
                           apenas partidas a partir desta data (temporada atual),
                           enquanto o ELO e o pipeline são calibrados no histórico
                           completo.
        """
        self.historical_df = historical_df.copy()
        self.registry = registry or ModelRegistry()
        self._feature_pipeline = FeaturePipeline()
        self._season_cutoff: Optional[pd.Timestamp] = (
            pd.Timestamp(season_cutoff) if season_cutoff else None
        )

        # Garante colunas derivadas mínimas (sem chamar MatchPreprocessor completo
        # para não alterar nomes de times/competição)
        df = historical_df.copy()
        if "outcome" not in df.columns:
            from app.core.utils import add_outcome_column
            df = add_outcome_column(df)
        if "total_goals" not in df.columns:
            df["total_goals"] = df["home_goals"] + df["away_goals"]

        # Aplica pipeline uma vez nos dados históricos completos para calibrar ELO e
        # demais transformers com a distribuição real de toda a série histórica.
        self._df_with_features = self._feature_pipeline.fit_transform(df)
        self._feature_cols = self._feature_pipeline.feature_columns

        if self._season_cutoff is not None:
            logger.info(
                f"FootballPredictor: form lookup restricted to season >= {season_cutoff} "
                f"(pipeline calibrated on {len(df)} total matches)"
            )

    def predict(self, context: MatchContext) -> PredictionOutput:
        """
        Gera previsão completa para uma partida.

        NOTA: Esta é uma estimativa probabilística, não uma certeza.
        """
        logger.info(
            f"Predicting: {context.home_team} vs {context.away_team} "
            f"[{context.competition}] {context.match_date}"
        )

        warnings_list: List[str] = []

        # ── Constrói feature row para a partida alvo ──────────────────────────
        X_pred, confidence = self._build_feature_row(context, warnings_list)

        # ── Inferência por modelo ─────────────────────────────────────────────
        outcome_probs = self._predict_outcome(context.competition, X_pred, warnings_list)
        goals_pred = self._predict_goals(context.competition, X_pred, warnings_list)
        corners_pred = self._predict_corners(context.competition, X_pred, warnings_list)
        cards_pred = self._predict_cards(context.competition, X_pred, warnings_list)
        time_window_pred = self._predict_time_windows(context.competition, X_pred, warnings_list)

        # ── Explicabilidade ───────────────────────────────────────────────────
        top_features = self._get_top_features(context.competition, X_pred)

        return PredictionOutput(
            competition=context.competition,
            home_team=context.home_team,
            away_team=context.away_team,
            match_date=str(context.match_date),
            # Resultado
            home_win=outcome_probs.get("home_win", 0.33),
            draw=outcome_probs.get("draw", 0.33),
            away_win=outcome_probs.get("away_win", 0.34),
            # Gols
            expected_goals_home=goals_pred.get("expected_goals_home", 1.3),
            expected_goals_away=goals_pred.get("expected_goals_away", 1.1),
            expected_goals_total=goals_pred.get("expected_goals_total", 2.4),
            over_0_5=goals_pred.get("over_0_5", 0.9),
            over_1_5=goals_pred.get("over_1_5", 0.7),
            over_2_5=goals_pred.get("over_2_5", 0.5),
            over_3_5=goals_pred.get("over_3_5", 0.3),
            over_4_5=goals_pred.get("over_4_5", 0.15),
            both_teams_score=goals_pred.get("both_teams_score", 0.5),
            clean_sheet_home=goals_pred.get("clean_sheet_home", 0.3),
            clean_sheet_away=goals_pred.get("clean_sheet_away", 0.25),
            top_scorelines=goals_pred.get("top_scorelines", []),
            # Escanteios
            expected_corners_total=corners_pred.get("expected_corners_total", 9.5),
            expected_corners_home=corners_pred.get("expected_corners_home", 5.0),
            expected_corners_away=corners_pred.get("expected_corners_away", 4.5),
            # Cartões
            expected_cards_total=cards_pred.get("expected_cards_total", 4.0),
            expected_cards_home=cards_pred.get("expected_cards_home", 2.0),
            expected_cards_away=cards_pred.get("expected_cards_away", 2.0),
            # Janelas temporais
            goal_first_15min=time_window_pred.get("goal_first_15min", 0.3),
            goal_last_15min=time_window_pred.get("goal_last_15min", 0.35),
            goal_first_half=time_window_pred.get("goal_first_half", 0.7),
            goal_second_half=time_window_pred.get("goal_second_half", 0.75),
            # Meta
            top_features=top_features,
            confidence_score=confidence,
            low_confidence_warning=confidence < 0.5,
            model_warnings=warnings_list,
        )

    # ── Build feature row ─────────────────────────────────────────────────────

    def _build_feature_row(
        self, context: MatchContext, warnings_list: List[str]
    ) -> tuple[pd.DataFrame, float]:
        """
        Constrói um DataFrame de 1 linha com as features da partida.
        Usa médias dos últimos jogos dos times como proxy das features atuais.
        """
        comp = context.competition
        h, a = context.home_team, context.away_team

        comp_df = self._df_with_features[
            self._df_with_features["competition"] == comp
        ].sort_values("date")

        # Quando há corte de temporada, o lookup de forma usa apenas partidas
        # da temporada atual; o ELO/features já foram calibrados no histórico completo.
        form_df = comp_df
        if self._season_cutoff is not None:
            form_df = comp_df[comp_df["date"] >= self._season_cutoff]

        # Últimas partidas de cada time (dentro da temporada corrente)
        h_history = form_df[
            (form_df["home_team"] == h) | (form_df["away_team"] == h)
        ].tail(10)

        a_history = form_df[
            (form_df["home_team"] == a) | (form_df["away_team"] == a)
        ].tail(10)

        confidence = 1.0

        if len(h_history) < 5:
            warnings_list.append(f"Limited history for {h} ({len(h_history)} matches)")
            confidence -= 0.2

        if len(a_history) < 5:
            warnings_list.append(f"Limited history for {a} ({len(a_history)} matches)")
            confidence -= 0.2

        feat_cols = [c for c in self._feature_cols if c in comp_df.columns]

        if h_history.empty or a_history.empty:
            warnings_list.append("No historical data found — using league averages")
            confidence = 0.1
            base = form_df if not form_df.empty else comp_df
            X_row = pd.DataFrame([base[feat_cols].mean().fillna(0)])
        else:
            X_row = pd.DataFrame([
                self._build_matchup_row(h, a, h_history, a_history, feat_cols)
            ]).fillna(0)

        confidence = max(0.1, min(1.0, confidence))
        return X_row, confidence

    def _build_matchup_row(
        self,
        home_team: str,
        away_team: str,
        h_history: pd.DataFrame,
        a_history: pd.DataFrame,
        feat_cols: List[str],
    ) -> dict:
        """
        Constrói o vetor de features para a partida home_team x away_team
        extraindo corretamente as métricas de cada time segundo seu papel
        (mandante/visitante) nas partidas anteriores.

        Evita o bug de misturar ELO/forma de times diferentes nas colunas home/away.
        """
        # Última partida de cada time (qualquer papel)
        h_last = h_history.iloc[-1]
        a_last = a_history.iloc[-1]

        # Indica se o time estava como mandante/visitante na última partida
        h_was_home = h_last.get("home_team") == home_team
        a_was_away = a_last.get("away_team") == away_team

        # Últimas partidas onde cada time esteve especificamente em casa / fora
        h_home_games = h_history[h_history["home_team"] == home_team]
        a_away_games = a_history[a_history["away_team"] == away_team]

        h_last_home = h_home_games.iloc[-1] if not h_home_games.empty else h_last
        a_last_away = a_away_games.iloc[-1] if not a_away_games.empty else a_last

        row: dict = {}
        for col in feat_cols:
            if col.startswith("home_"):
                # Feature do time mandante → extrair do histórico do mandante (H)
                suffix = col[5:]          # e.g. "form", "attack_str", "home_form"
                away_col = f"away_{suffix}"

                if suffix == "home_form" or suffix == "win_rate_home":
                    # Forma especificamente em casa → usar última partida em casa de H
                    if h_was_home:
                        row[col] = h_last.get(col, 0)
                    else:
                        row[col] = h_last_home.get(col, 0)
                elif h_was_home:
                    row[col] = h_last.get(col, 0)
                elif away_col in h_last.index:
                    # H era visitante — sua métrica está na coluna "away_"
                    row[col] = h_last.get(away_col, 0)
                else:
                    row[col] = h_last.get(col, 0)

            elif col.startswith("away_"):
                # Feature do time visitante → extrair do histórico do visitante (A)
                suffix = col[5:]
                home_col = f"home_{suffix}"

                if suffix == "away_form" or suffix == "win_rate_away":
                    # Forma especificamente fora → usar última partida fora de A
                    if a_was_away:
                        row[col] = a_last.get(col, 0)
                    else:
                        row[col] = a_last_away.get(col, 0)
                elif a_was_away:
                    row[col] = a_last.get(col, 0)
                elif home_col in a_last.index:
                    # A era mandante — sua métrica está na coluna "home_"
                    row[col] = a_last.get(home_col, 0)
                else:
                    row[col] = a_last.get(col, 0)

            elif col == "elo_diff":
                # Recalcula do ELO correto de cada time
                e_home = row.get("elo_home", h_last.get("elo_away" if not h_was_home else "elo_home", 1500))
                e_away = row.get("elo_away", a_last.get("elo_home" if not a_was_away else "elo_away", 1500))
                row[col] = e_home - e_away

            elif col == "form_diff":
                row[col] = row.get("home_form", 0.5) - row.get("away_form", 0.5)

            elif col in ("attack_str_diff", "defense_str_diff"):
                # Recalcula baseado nos valores já resolvidos
                if col == "attack_str_diff":
                    row[col] = row.get("home_attack_str", 1.0) - row.get("away_attack_str", 1.0)
                else:
                    row[col] = row.get("home_defense_str", 1.0) - row.get("away_defense_str", 1.0)

            elif col == "rest_advantage":
                row[col] = row.get("home_rest_days", 4) - row.get("away_rest_days", 4)

            elif col.startswith("h2h_"):
                # H2H: média entre as últimas linhas dos dois times
                row[col] = (h_last.get(col, 0) + a_last.get(col, 0)) / 2

            else:
                # Contextuais (matchday, mês, etc.): média
                row[col] = (h_last.get(col, 0) + a_last.get(col, 0)) / 2

        # Segunda passagem: recalcula elo_diff e form_diff com valores finais
        if "elo_home" in row and "elo_away" in row and "elo_diff" in feat_cols:
            row["elo_diff"] = row["elo_home"] - row["elo_away"]
        if "home_form" in row and "away_form" in row and "form_diff" in feat_cols:
            row["form_diff"] = row["home_form"] - row["away_form"]
        if "home_attack_str" in row and "away_attack_str" in row and "attack_str_diff" in feat_cols:
            row["attack_str_diff"] = row["home_attack_str"] - row["away_attack_str"]
        if "home_defense_str" in row and "away_defense_str" in row and "defense_str_diff" in feat_cols:
            row["defense_str_diff"] = row["home_defense_str"] - row["away_defense_str"]
        if "home_rest_days" in row and "away_rest_days" in row and "rest_advantage" in feat_cols:
            row["rest_advantage"] = row["home_rest_days"] - row["away_rest_days"]

        return row

    # ── Predições por modelo ──────────────────────────────────────────────────

    def _predict_outcome(self, competition: str, X: pd.DataFrame, warnings: List[str]) -> Dict:
        try:
            model = self.registry.load("outcome", competition)
            results = model.predict_structured(X)
            return results[0]
        except Exception as e:
            warnings.append(f"Outcome model unavailable: {e}")
            return {"home_win": 0.40, "draw": 0.28, "away_win": 0.32}

    def _predict_goals(self, competition: str, X: pd.DataFrame, warnings: List[str]) -> Dict:
        try:
            model = self.registry.load("goals", competition)
            results = model.predict_full(X)
            return results[0]
        except Exception as e:
            warnings.append(f"Goals model unavailable: {e}")
            return {
                "expected_goals_home": 1.3, "expected_goals_away": 1.1,
                "expected_goals_total": 2.4, "over_0_5": 0.9, "over_1_5": 0.7,
                "over_2_5": 0.52, "over_3_5": 0.3, "over_4_5": 0.15,
                "both_teams_score": 0.5, "clean_sheet_home": 0.3,
                "clean_sheet_away": 0.25, "top_scorelines": [],
            }

    def _predict_corners(self, competition: str, X: pd.DataFrame, warnings: List[str]) -> Dict:
        try:
            model = self.registry.load("corners", competition)
            results = model.predict_full(X)
            return results[0]
        except Exception as e:
            warnings.append(f"Corners model unavailable: {e}")
            return {"expected_corners_total": 9.5, "expected_corners_home": 5.0, "expected_corners_away": 4.5}

    def _predict_cards(self, competition: str, X: pd.DataFrame, warnings: List[str]) -> Dict:
        try:
            model = self.registry.load("cards", competition)
            results = model.predict_full(X)
            return results[0]
        except Exception as e:
            warnings.append(f"Cards model unavailable: {e}")
            return {"expected_cards_total": 4.0, "expected_cards_home": 2.0, "expected_cards_away": 2.0}

    def _predict_time_windows(self, competition: str, X: pd.DataFrame, warnings: List[str]) -> Dict:
        try:
            ensemble = self.registry.load_time_window(competition)
            return ensemble.predict_all(X)
        except Exception as e:
            warnings.append(f"Time window models unavailable: {e}")
            return {
                "goal_first_15min": 0.30,
                "goal_last_15min": 0.35,
                "goal_first_half": 0.70,
                "goal_second_half": 0.75,
            }

    def _get_top_features(self, competition: str, X: pd.DataFrame) -> List[Dict]:
        """Tenta obter importância de features do modelo de resultado."""
        try:
            from app.inference.explainability import get_feature_importance
            model = self.registry.load("outcome", competition)
            return get_feature_importance(model, X, top_n=10)
        except Exception:
            return []
