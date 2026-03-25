"""
scripts/run_inference.py
Executa inferência pré-jogo a partir da linha de comando.

Uso:
    python scripts/run_inference.py \
        --competition brasileirao \
        --home "Flamengo" \
        --away "Palmeiras" \
        --date 2024-06-15

    python scripts/run_inference.py \
        --competition champions_league \
        --home "Real Madrid" \
        --away "Manchester City" \
        --date 2024-04-09 \
        --stage semi_final
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.inference.postprocess import postprocess_prediction
from app.inference.predictor import FootballPredictor, MatchContext
from app.inference.serializer import prediction_to_dict
from app.models.registry import ModelRegistry

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Football match probabilistic analysis")
    parser.add_argument("--competition", required=True, choices=settings.SUPPORTED_COMPETITIONS)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--matchday", type=int, default=None)
    args = parser.parse_args()

    competition = args.competition
    match_date = date.fromisoformat(args.date)

    # Carrega dados históricos
    processed_dir = settings.PROCESSED_DATA_DIR
    files = list(processed_dir.glob(f"{competition}_*.csv"))
    if not files:
        print(f"ERROR: No processed data for '{competition}'. Run scripts/create_sample_data.py + train_all.py first.")
        sys.exit(1)

    frames = [pd.read_csv(f, parse_dates=["date"]) for f in files]
    df = pd.concat(frames, ignore_index=True).sort_values("date")

    registry = ModelRegistry()
    predictor = FootballPredictor(historical_df=df, registry=registry)

    context = MatchContext(
        competition=competition,
        home_team=args.home.strip().title(),
        away_team=args.away.strip().title(),
        match_date=match_date,
        stage=args.stage,
        matchday=args.matchday,
    )

    print(f"\nAnalysing: {context.home_team} vs {context.away_team} [{competition}] on {match_date}")
    print("=" * 60)
    print("NOTE: These are probabilistic estimates — not guaranteed predictions.")
    print("=" * 60)

    prediction = predictor.predict(context)
    prediction = postprocess_prediction(prediction)
    result = prediction_to_dict(prediction)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    if prediction.low_confidence_warning:
        print("\n⚠ WARNING: Low confidence — limited historical data for one or both teams.")


if __name__ == "__main__":
    main()
