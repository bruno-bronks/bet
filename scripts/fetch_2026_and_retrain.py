"""
scripts/fetch_2026_and_retrain.py

Busca todas as partidas finalizadas do Brasileirão 2026 via football-data.org,
salva como CSV e retreina os modelos.

Uso:
    python scripts/fetch_2026_and_retrain.py
    python scripts/fetch_2026_and_retrain.py --dry-run   # só busca, não retreina
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Garante que o pacote app está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.services.football_api import TEAM_NAME_MAP, _normalize_team

logger = get_logger("fetch_2026")

OUT_CSV = settings.PROCESSED_DATA_DIR / "brasileirao_real_2026.csv"

# Colunas esperadas pelo pipeline (as que não vierem da API ficam NaN → 0 no treino)
STATS_COLS = [
    "home_shots", "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "home_corners", "away_corners",
    "home_yellow_cards", "away_yellow_cards",
    "home_red_cards", "away_red_cards",
    "home_fouls", "away_fouls",
    "home_possession", "away_possession",
    "home_xg", "away_xg",
    "first_half_home_goals", "first_half_away_goals",
    "minute_first_goal",
    "home_goals_0_15", "away_goals_0_15",
    "home_goals_75_90", "away_goals_75_90",
]


def fetch_brasileirao_2026() -> list[dict]:
    """Busca todos os jogos finalizados do Brasileirão 2026 via football-data.org."""
    key = settings.FOOTBALL_DATA_KEY
    if not key:
        logger.error("FOOTBALL_DATA_KEY não configurada no .env")
        return []

    base = settings.FOOTBALL_DATA_BASE_URL.rstrip("/")
    headers = {"X-Auth-Token": key, "Accept": "application/json"}

    today = date.today()
    from_date = date(2026, 1, 1)

    params = {
        "status": "FINISHED",
        "dateFrom": from_date.isoformat(),
        "dateTo": today.isoformat(),
    }

    logger.info(f"Buscando partidas finalizadas BSA 2026: {from_date} → {today}")
    try:
        resp = httpx.get(
            f"{base}/competitions/BSA/matches",
            headers=headers,
            params=params,
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Erro ao buscar dados: {e}")
        return []

    matches = data.get("matches", [])
    logger.info(f"  Encontrados: {len(matches)} jogos")
    return matches


def parse_matches(matches: list[dict]) -> pd.DataFrame:
    """Converte lista de jogos da API para DataFrame no formato do CSV."""
    rows = []
    for m in matches:
        try:
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            home_goals = ft.get("home")
            away_goals = ft.get("away")

            if home_goals is None or away_goals is None:
                continue  # Ignora jogos sem placar

            utc_date = m.get("utcDate", "")
            match_date = utc_date[:10] if utc_date else ""

            home_name = _normalize_team(m.get("homeTeam", {}).get("name", ""))
            away_name = _normalize_team(m.get("awayTeam", {}).get("name", ""))

            row = {
                "match_id": str(m.get("id", uuid.uuid4().hex[:12])),
                "competition": "brasileirao",
                "season": 2026,
                "date": match_date,
                "home_team": home_name,
                "away_team": away_name,
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "matchday": m.get("matchday"),
                "stage": m.get("stage", "REGULAR_SEASON"),
            }
            # Stats não disponíveis na API básica — ficam vazias para o modelo preencher com 0
            for col in STATS_COLS:
                row[col] = None

            rows.append(row)
        except Exception as e:
            logger.debug(f"Erro ao parsear jogo: {e}")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    logger.info(f"Salvo: {OUT_CSV} ({len(df)} jogos)")


def retrain(competition: str = "brasileirao") -> None:
    """Retreina todos os modelos com dados combinados (histórico + 2026)."""
    logger.info("Carregando dados para retreinamento...")

    files = list(settings.PROCESSED_DATA_DIR.glob(f"{competition}_*.csv"))
    if not files:
        logger.error("Nenhum CSV encontrado em data/processed/")
        return

    frames = [pd.read_csv(f, parse_dates=["date"]) for f in files]
    df = pd.concat(frames, ignore_index=True).sort_values("date").drop_duplicates(
        subset=["competition", "date", "home_team", "away_team"]
    )
    logger.info(f"  Total: {len(df)} jogos ({df['date'].min().date()} → {df['date'].max().date()})")

    from app.models.registry import ModelRegistry
    from app.training.trainer import ModelTrainer

    registry = ModelRegistry()
    trainer = ModelTrainer(competition=competition, registry=registry)
    metrics = trainer.train_all(df)

    logger.info("Retreinamento concluído!")
    for model_name, m in metrics.items():
        logger.info(f"  {model_name}: {m}")


def main():
    parser = argparse.ArgumentParser(description="Busca dados 2026 e retreina modelos")
    parser.add_argument("--dry-run", action="store_true", help="Só busca dados, não retreina")
    args = parser.parse_args()

    # 1. Buscar dados
    matches = fetch_brasileirao_2026()
    if not matches:
        logger.error("Nenhum jogo encontrado. Verifique FOOTBALL_DATA_KEY no .env")
        sys.exit(1)

    df = parse_matches(matches)
    if df.empty:
        logger.error("Nenhum jogo com placar completo encontrado")
        sys.exit(1)

    logger.info(f"\nJogos por rodada:")
    if "matchday" in df.columns:
        for rd, grp in df.groupby("matchday"):
            logger.info(f"  Rodada {rd}: {len(grp)} jogos")

    save_csv(df)

    if args.dry_run:
        logger.info("--dry-run: pulando retreinamento")
        return

    # 2. Retreinar
    retrain("brasileirao")
    logger.info("\nPronto! Reinicie o backend para carregar os novos modelos.")


if __name__ == "__main__":
    main()
