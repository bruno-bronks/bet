"""
scripts/train_all.py
Treina todos os modelos para todas as competições suportadas.

Uso:
    python scripts/train_all.py
    python scripts/train_all.py --competition brasileirao
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.models.registry import ModelRegistry
from app.training.trainer import ModelTrainer

logger = get_logger(__name__)


def train_competition(competition: str, registry: ModelRegistry) -> None:
    processed_dir = settings.PROCESSED_DATA_DIR
    files = list(processed_dir.glob(f"{competition}_*.csv"))

    if not files:
        logger.error(
            f"No processed data found for '{competition}'. "
            "Run scripts/create_sample_data.py first."
        )
        return

    logger.info(f"Loading data for {competition} from {len(files)} file(s)...")
    frames = [pd.read_csv(f, parse_dates=["date"]) for f in files]
    df = pd.concat(frames, ignore_index=True).sort_values("date")
    logger.info(f"Total: {len(df)} matches | date range: {df['date'].min().date()} → {df['date'].max().date()}")

    trainer = ModelTrainer(competition=competition, registry=registry)
    metrics = trainer.train_all(df)

    print(f"\n{'='*50}")
    print(f"Training complete for: {competition}")
    print(f"{'='*50}")
    for model_name, m in metrics.items():
        print(f"  {model_name}: {m}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train football prediction models")
    parser.add_argument(
        "--competition",
        default=None,
        choices=settings.SUPPORTED_COMPETITIONS + [None],
        help="Competition to train (default: all)",
    )
    args = parser.parse_args()

    registry = ModelRegistry()
    competitions = [args.competition] if args.competition else settings.SUPPORTED_COMPETITIONS

    for comp in competitions:
        train_competition(comp, registry)

    print("All training complete. Models saved to models_artifacts/")


if __name__ == "__main__":
    main()
