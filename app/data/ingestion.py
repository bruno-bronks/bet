"""
app/data/ingestion.py
Ingestão de dados: carrega dados brutos de diferentes fontes e valida.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.data.preprocess import MatchPreprocessor
from app.data.repository import MatchRepository

logger = get_logger(__name__)


class DataIngestionPipeline:
    """
    Pipeline completo de ingestão:
    1. Lê CSV raw
    2. Pré-processa
    3. Salva em processed/

    Para integração com APIs externas (football-data.org, Sofascore, etc.),
    implemente subclasses ou adapters que retornem pd.DataFrame compatível.
    """

    def __init__(self, competition: Optional[str] = None) -> None:
        self.competition = competition
        self.repository = MatchRepository()
        self.preprocessor = MatchPreprocessor(competition=competition)

    def ingest_csv(self, source_path: Path, save: bool = True) -> pd.DataFrame:
        """
        Ingere um CSV de partidas brutas.

        Args:
            source_path: Caminho para o CSV de entrada.
            save: Se True, salva o resultado processado em data/processed/.

        Returns:
            DataFrame processado.
        """
        logger.info(f"Ingesting CSV: {source_path}")
        raw_df = self.repository.load_from_csv(source_path)
        processed_df = self.preprocessor.fit_transform(raw_df)

        if save and not processed_df.empty:
            competition = self.competition or "all"
            season = processed_df["season"].iloc[0] if "season" in processed_df.columns else "unknown"
            self.repository.save_processed(processed_df, competition, season)

        return processed_df

    def ingest_directory(self, directory: Path, pattern: str = "*.csv") -> pd.DataFrame:
        """Ingere todos os CSVs de um diretório."""
        files = list(directory.glob(pattern))
        if not files:
            raise FileNotFoundError(f"No CSV files found in {directory}")

        frames: List[pd.DataFrame] = []
        for f in sorted(files):
            try:
                df = self.ingest_csv(f, save=False)
                frames.append(df)
            except Exception as e:
                logger.error(f"Failed to ingest {f.name}: {e}")

        if not frames:
            raise RuntimeError("No files could be ingested successfully")

        combined = pd.concat(frames, ignore_index=True)
        combined = self.preprocessor._sort_by_date(combined)
        logger.info(f"Ingested {len(combined)} total rows from {len(frames)} files")
        return combined
