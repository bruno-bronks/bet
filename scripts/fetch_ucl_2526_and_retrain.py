"""
scripts/fetch_ucl_2526_and_retrain.py

Busca todas as partidas finalizadas da Champions League 2025/26 via football-data.org,
salva como CSV e retreina os modelos.

Uso:
    python scripts/fetch_ucl_2526_and_retrain.py
    python scripts/fetch_ucl_2526_and_retrain.py --dry-run   # só busca, não retreina
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date
from pathlib import Path

# Garante que o pacote app está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.services.football_api import _normalize_team

logger = get_logger("fetch_ucl_2526")

OUT_CSV = settings.PROCESSED_DATA_DIR / "champions_league_real_2526.csv"

# Mapeamento de nomes da football-data.org para o padrão interno
UCL_TEAM_NAME_MAP: dict[str, str] = {
    # Nomes comuns na API football-data.org para UCL
    "Real Madrid CF": "Real Madrid",
    "FC Barcelona": "Barcelona",
    "Manchester City FC": "Manchester City",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Manchester United FC": "Manchester United",
    "Tottenham Hotspur FC": "Tottenham Hotspur",
    "Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "VfB Stuttgart": "VfB Stuttgart",
    "Atlético de Madrid": "Atletico Madrid",
    "Sevilla FC": "Sevilla",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "Villarreal CF": "Villarreal",
    "Club Atlético de Madrid": "Atletico Madrid",
    "Paris Saint-Germain FC": "Paris Saint-Germain",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "LOSC Lille": "Lille",
    "Stade Rennais FC 1901": "Rennes",
    "Juventus FC": "Juventus",
    "AC Milan": "AC Milan",
    "FC Internazionale Milano": "Inter Milan",
    "SSC Napoli": "Napoli",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "Atalanta BC": "Atalanta",
    "AFC Ajax": "Ajax",
    "PSV": "PSV Eindhoven",
    "Feyenoord": "Feyenoord",
    "Club Brugge KV": "Club Brugge",
    "SL Benfica": "Benfica",
    "FC Porto": "Porto",
    "Sporting CP": "Sporting CP",
    "Celtic FC": "Celtic",
    "Rangers FC": "Rangers",
    "GNK Dinamo Zagreb": "Dinamo Zagreb",
    "FK Shakhtar Donetsk": "Shakhtar Donetsk",
    "FC Red Bull Salzburg": "RB Salzburg",
    "BSC Young Boys": "Young Boys",
    "FC Basel 1893": "Basel",
    "Galatasaray AŞ": "Galatasaray",
    "Beşiktaş JK": "Besiktas",
    "Fenerbahçe SK": "Fenerbahce",
}

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


def _normalize_ucl_team(name: str) -> str:
    """Normaliza nome de time da UCL para o padrão interno."""
    if not name:
        return name
    mapped = UCL_TEAM_NAME_MAP.get(name)
    if mapped:
        return mapped
    # Fallback: remove sufixos comuns
    for suffix in [" FC", " CF", " AC", " SC", " FK", " SK", " AŞ", " KV", " BC"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    return name


def fetch_ucl_2526() -> list[dict]:
    """Busca todos os jogos finalizados da UCL 2025/26 via football-data.org."""
    key = settings.FOOTBALL_DATA_KEY
    if not key:
        logger.error("FOOTBALL_DATA_KEY nao configurada no .env")
        return []

    base = settings.FOOTBALL_DATA_BASE_URL.rstrip("/")
    headers = {"X-Auth-Token": key, "Accept": "application/json"}

    today = date.today()
    from_date = date(2025, 8, 1)  # UCL 2025/26 começa em agosto/setembro 2025

    params = {
        "status": "FINISHED",
        "dateFrom": from_date.isoformat(),
        "dateTo": today.isoformat(),
    }

    logger.info(f"Buscando partidas UCL 2025/26: {from_date} -> {today}")
    try:
        resp = httpx.get(
            f"{base}/competitions/CL/matches",
            headers=headers,
            params=params,
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Erro ao buscar dados UCL: {e}")
        return []

    matches = data.get("matches", [])
    logger.info(f"  Encontrados: {len(matches)} jogos UCL 2025/26")
    return matches


def parse_matches(matches: list[dict]) -> pd.DataFrame:
    """Converte lista de jogos da API para DataFrame."""
    rows = []
    for m in matches:
        try:
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            home_goals = ft.get("home")
            away_goals = ft.get("away")

            if home_goals is None or away_goals is None:
                continue

            utc_date = m.get("utcDate", "")
            match_date = utc_date[:10] if utc_date else ""
            season_year = int(match_date[:4]) if match_date else 2025
            # Normaliza: UCL 2025/26 → season = 2025
            season = 2025 if season_year >= 2025 else season_year

            home_name = _normalize_ucl_team(m.get("homeTeam", {}).get("name", ""))
            away_name = _normalize_ucl_team(m.get("awayTeam", {}).get("name", ""))

            row = {
                "match_id": str(m.get("id", uuid.uuid4().hex[:12])),
                "competition": "champions_league",
                "season": season,
                "date": match_date,
                "home_team": home_name,
                "away_team": away_name,
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "matchday": m.get("matchday"),
                "stage": m.get("stage", "LEAGUE_PHASE"),
            }
            for col in STATS_COLS:
                row[col] = None

            rows.append(row)
        except Exception as e:
            logger.debug(f"Erro ao parsear jogo UCL: {e}")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    logger.info(f"Salvo: {OUT_CSV} ({len(df)} jogos)")


def retrain(competition: str = "champions_league") -> None:
    """Retreina todos os modelos UCL com dados combinados."""
    logger.info("Carregando dados UCL para retreinamento...")

    files = list(settings.PROCESSED_DATA_DIR.glob(f"{competition}_*.csv"))
    if not files:
        logger.error("Nenhum CSV UCL encontrado em data/processed/")
        return

    csv_files_sorted = sorted(files, key=lambda f: (1 if "_with_stats" in f.name else 0))
    frames = [pd.read_csv(f, parse_dates=["date"]) for f in csv_files_sorted]
    df = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["competition", "date", "home_team", "away_team"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )
    logger.info(f"  Total UCL: {len(df)} jogos ({df['date'].min().date()} -> {df['date'].max().date()})")

    from app.models.registry import ModelRegistry
    from app.training.trainer import ModelTrainer

    registry = ModelRegistry()
    trainer = ModelTrainer(competition=competition, registry=registry)
    metrics = trainer.train_all(df)

    logger.info("Retreinamento UCL concluido!")
    for model_name, m in metrics.items():
        logger.info(f"  {model_name}: {m}")


def main():
    parser = argparse.ArgumentParser(description="Busca dados UCL 2025/26 e retreina modelos")
    parser.add_argument("--dry-run", action="store_true", help="So busca dados, nao retreina")
    args = parser.parse_args()

    matches = fetch_ucl_2526()
    if not matches:
        logger.error("Nenhum jogo UCL encontrado. Verifique FOOTBALL_DATA_KEY no .env")
        sys.exit(1)

    df = parse_matches(matches)
    if df.empty:
        logger.error("Nenhum jogo UCL com placar completo")
        sys.exit(1)

    logger.info(f"\nJogos UCL por fase:")
    if "stage" in df.columns:
        for stage, grp in df.groupby("stage"):
            logger.info(f"  {stage}: {len(grp)} jogos")

    save_csv(df)

    if args.dry_run:
        logger.info("--dry-run: pulando retreinamento")
        return

    retrain("champions_league")
    logger.info("\nPronto! Reinicie o backend para carregar os novos modelos.")


if __name__ == "__main__":
    main()
