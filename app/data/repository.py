"""
app/data/repository.py
Repositório de dados: abstrai acesso ao banco SQLite e CSVs processados.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class MatchRepository:
    """
    Repositório de partidas históricas.
    Suporta leitura de CSV (desenvolvimento) e banco de dados (produção).
    """

    def __init__(self, db_session: Optional[Session] = None) -> None:
        self._session = db_session

    # ── CSV / Arquivo ─────────────────────────────────────────────────────────

    def load_from_csv(self, path: Path) -> pd.DataFrame:
        """Carrega partidas de um arquivo CSV."""
        logger.info(f"Loading matches from CSV: {path}")
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        df = pd.read_csv(path, parse_dates=["date"])
        logger.info(f"Loaded {len(df)} rows from {path.name}")
        return df

    def load_processed(self, competition: Optional[str] = None) -> pd.DataFrame:
        """Carrega dados pré-processados do diretório processed/."""
        processed_dir = settings.PROCESSED_DATA_DIR
        pattern = f"{competition}_*.csv" if competition else "*.csv"
        files = list(processed_dir.glob(pattern))

        if not files:
            raise FileNotFoundError(
                f"No processed files found in {processed_dir} for pattern '{pattern}'"
            )

        frames: List[pd.DataFrame] = []
        for f in sorted(files):
            df = pd.read_csv(f, parse_dates=["date"])
            frames.append(df)
            logger.debug(f"  Loaded {len(df)} rows from {f.name}")

        combined = pd.concat(frames, ignore_index=True)
        logger.info(f"Loaded total {len(combined)} processed rows")
        return combined

    def save_processed(self, df: pd.DataFrame, competition: str, season: str) -> Path:
        """Salva DataFrame processado como CSV."""
        path = settings.PROCESSED_DATA_DIR / f"{competition}_{season}.csv"
        df.to_csv(path, index=False)
        logger.info(f"Saved {len(df)} rows to {path}")
        return path

    # ── Database ──────────────────────────────────────────────────────────────

    def load_from_db(
        self,
        competition: Optional[str] = None,
        season: Optional[str] = None,
        team: Optional[str] = None,
    ) -> pd.DataFrame:
        """Carrega partidas do banco SQLite com filtros opcionais."""
        if self._session is None:
            raise RuntimeError("Database session not initialized")

        from app.db.models import MatchORM

        query = self._session.query(MatchORM)

        if competition:
            query = query.filter(MatchORM.competition == competition)
        if season:
            query = query.filter(MatchORM.season == season)
        if team:
            query = query.filter(
                (MatchORM.home_team == team) | (MatchORM.away_team == team)
            )

        records = query.all()
        if not records:
            return pd.DataFrame()

        return pd.DataFrame([r.__dict__ for r in records]).drop(
            columns=["_sa_instance_state"], errors="ignore"
        )

    def save_to_db(self, df: pd.DataFrame) -> int:
        """Persiste DataFrame no banco de dados. Retorna número de registros inseridos."""
        if self._session is None:
            raise RuntimeError("Database session not initialized")

        from app.db.models import MatchORM

        inserted = 0
        for _, row in df.iterrows():
            record = MatchORM(**{k: v for k, v in row.items() if hasattr(MatchORM, k)})
            self._session.merge(record)  # upsert por match_id
            inserted += 1

        self._session.commit()
        logger.info(f"Saved/updated {inserted} records to database")
        return inserted

    # ── Consultas de contexto ─────────────────────────────────────────────────

    def get_team_history(
        self, df: pd.DataFrame, team: str, n_last: int = 20
    ) -> pd.DataFrame:
        """Retorna as últimas N partidas de um time (como mandante ou visitante)."""
        mask = (df["home_team"] == team) | (df["away_team"] == team)
        return df[mask].sort_values("date").tail(n_last).reset_index(drop=True)

    def get_head_to_head(
        self, df: pd.DataFrame, team_a: str, team_b: str, n_last: int = 10
    ) -> pd.DataFrame:
        """Retorna confrontos diretos entre dois times."""
        mask = (
            ((df["home_team"] == team_a) & (df["away_team"] == team_b))
            | ((df["home_team"] == team_b) & (df["away_team"] == team_a))
        )
        return df[mask].sort_values("date").tail(n_last).reset_index(drop=True)
