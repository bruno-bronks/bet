"""
scripts/fetch_and_train.py
Baixa dados históricos reais do football-data.org e treina os modelos.

Usa os resultados reais (placar) e gera estatísticas complementares
(chutes, escanteios, cartões) de forma sintética baseada nos gols reais.

Uso:
    python scripts/fetch_and_train.py
    python scripts/fetch_and_train.py --competition brasileirao
    python scripts/fetch_and_train.py --dry-run   (só baixa, não treina)
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Configuração ──────────────────────────────────────────────────────────────

_BASE_URL = settings.FOOTBALL_DATA_BASE_URL.rstrip("/")
_KEY = settings.FOOTBALL_DATA_KEY

# Códigos das competições em football-data.org
_COMP_CODE = {
    "brasileirao": "BSA",
    "champions_league": "CL",
}

# Seasons para cada competição (BSA: ano do início; CL: ano do início, e.g. 2022 = 2022/23)
_SEASONS = {
    "brasileirao": ["2022", "2023", "2024", "2025", "2026"],
    "champions_league": ["2022", "2023", "2024"],  # 2024 = 2024/25
}

# Rate limit: plano gratuito = 10 req/min → esperar 7s entre chamadas
_RATE_LIMIT_SLEEP = 7


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | None:
    url = f"{_BASE_URL}/{path.lstrip('/')}"
    headers = {"X-Auth-Token": _KEY, "Accept": "application/json"}
    try:
        resp = httpx.get(url, headers=headers, params=params or {}, timeout=20.0)
        if resp.status_code == 429:
            logger.warning("Rate limit atingido — aguardando 60s...")
            time.sleep(60)
            resp = httpx.get(url, headers=headers, params=params or {}, timeout=20.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code} → {url}: {e.response.text[:300]}")
    except Exception as e:
        logger.error(f"Request error: {e}")
    return None


# ── Geração de estatísticas sintéticas baseadas nos gols reais ────────────────

def _synthetic_stats(hg: int, ag: int, rng: random.Random, npr: np.random.Generator) -> dict:
    """Gera estatísticas de jogo realistas com base no placar real."""
    hs = max(2, int(npr.normal(12 + hg * 0.8, 3)))
    as_ = max(2, int(npr.normal(10 + ag * 0.8, 3)))
    hp = round(rng.uniform(38, 62), 1)

    def _goal_minutes(n_goals: int) -> tuple[int, int, int]:
        g015 = g7590 = ght = 0
        for _ in range(n_goals):
            m = rng.randint(1, 90)
            if m <= 15:
                g015 += 1
            if m > 75:
                g7590 += 1
            if m <= 45:
                ght += 1
        return g015, g7590, ght

    hg015, hg7590, htg = _goal_minutes(hg)
    ag015, ag7590, atg = _goal_minutes(ag)

    return {
        "home_shots": hs,
        "away_shots": as_,
        "home_shots_on_target": min(hs, max(0, int(hs * rng.uniform(0.3, 0.55)))),
        "away_shots_on_target": min(as_, max(0, int(as_ * rng.uniform(0.3, 0.55)))),
        "home_corners": max(0, int(npr.poisson(5.0))),
        "away_corners": max(0, int(npr.poisson(4.5))),
        "home_yellow_cards": max(0, int(npr.poisson(1.8))),
        "away_yellow_cards": max(0, int(npr.poisson(1.8))),
        "home_red_cards": 1 if rng.random() < 0.05 else 0,
        "away_red_cards": 1 if rng.random() < 0.05 else 0,
        "home_fouls": max(5, int(npr.normal(12, 3))),
        "away_fouls": max(5, int(npr.normal(12, 3))),
        "home_possession": hp,
        "away_possession": round(100 - hp, 1),
        "home_xg": round(max(0.1, npr.normal(hg * 0.9 + 0.3, 0.5)), 2),
        "away_xg": round(max(0.1, npr.normal(ag * 0.9 + 0.3, 0.5)), 2),
        "first_half_home_goals": htg,
        "first_half_away_goals": atg,
        "minute_first_goal": rng.randint(1, 90) if (hg + ag) > 0 else 0,
        "home_goals_0_15": hg015,
        "away_goals_0_15": ag015,
        "home_goals_75_90": hg7590,
        "away_goals_75_90": ag7590,
    }


# ── Download de partidas ───────────────────────────────────────────────────────

def fetch_season(competition: str, season: str) -> list[dict]:
    """Baixa todas as partidas FINISHED de uma temporada."""
    code = _COMP_CODE.get(competition)
    if not code:
        return []

    logger.info(f"  Baixando {competition} {season}...")
    data = _get(f"competitions/{code}/matches", {
        "season": season,
        "status": "FINISHED",
    })
    time.sleep(_RATE_LIMIT_SLEEP)  # respeitar rate limit

    if not data:
        logger.warning(f"  Sem dados para {competition} {season}")
        return []

    matches = data.get("matches", [])
    logger.info(f"  {len(matches)} partidas encontradas em {competition} {season}")
    return matches


def matches_to_df(matches: list[dict], competition: str, season: str,
                  rng: random.Random, npr: np.random.Generator) -> pd.DataFrame:
    """Converte lista de partidas da API em DataFrame no formato de treinamento."""
    rows = []
    for m in matches:
        try:
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            hg = ft.get("home")
            ag = ft.get("away")
            if hg is None or ag is None:
                continue  # ignora partidas sem placar

            hg, ag = int(hg), int(ag)

            utc_date = m.get("utcDate", "")
            date_str = utc_date[:10] if utc_date else ""
            if not date_str:
                continue

            home_name = m.get("homeTeam", {}).get("name", "")
            away_name = m.get("awayTeam", {}).get("name", "")

            match_id = hashlib.md5(
                f"{competition}_{date_str}_{home_name}_{away_name}".lower().encode()
            ).hexdigest()[:12]

            matchday = m.get("matchday")
            stage = m.get("stage", "")

            # Gols do 1º tempo: dados REAIS da API
            ht = score.get("halfTime", {})
            ht_home = ht.get("home")
            ht_away = ht.get("away")

            synthetic = _synthetic_stats(hg, ag, rng, npr)

            # Sobrescreve os gols de 1º tempo sintéticos com os reais (quando disponíveis)
            if ht_home is not None and ht_away is not None:
                synthetic["first_half_home_goals"] = int(ht_home)
                synthetic["first_half_away_goals"] = int(ht_away)

            row = {
                "match_id": match_id,
                "competition": competition,
                "season": season,
                "date": date_str,
                "home_team": home_name,
                "away_team": away_name,
                "home_goals": hg,
                "away_goals": ag,
                "matchday": matchday,
                "stage": stage,
                **synthetic,
            }
            rows.append(row)
        except Exception as e:
            logger.debug(f"Erro ao processar partida: {e}")

    return pd.DataFrame(rows)


# ── Processamento por competição ──────────────────────────────────────────────

def process_competition(competition: str) -> pd.DataFrame | None:
    seasons = _SEASONS.get(competition, [])
    if not seasons:
        return None

    rng = random.Random(42)
    npr = np.random.default_rng(42)

    all_frames = []
    for season in seasons:
        matches = fetch_season(competition, season)
        if not matches:
            continue
        df = matches_to_df(matches, competition, season, rng, npr)
        if not df.empty:
            all_frames.append(df)
            logger.info(f"  Convertidas {len(df)} partidas de {competition} {season}")

    if not all_frames:
        logger.warning(f"Nenhum dado obtido para {competition}")
        return None

    combined = pd.concat(all_frames, ignore_index=True).sort_values("date")
    combined["date"] = pd.to_datetime(combined["date"])
    return combined


# ── Treino ────────────────────────────────────────────────────────────────────

def train(competition: str, df: pd.DataFrame) -> None:
    from app.models.registry import ModelRegistry
    from app.training.trainer import ModelTrainer

    registry = ModelRegistry()
    trainer = ModelTrainer(competition=competition, registry=registry)
    metrics = trainer.train_all(df)
    print(f"\n{'='*50}")
    print(f"Treinamento concluído: {competition}")
    print(f"{'='*50}")
    for model_name, m in metrics.items():
        print(f"  {model_name}: {m}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa dados reais e treina modelos")
    parser.add_argument("--competition", choices=list(_COMP_CODE.keys()),
                        default=None, help="Competição (padrão: todas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Só baixa e salva CSV, não treina")
    args = parser.parse_args()

    if not _KEY:
        print("ERRO: FOOTBALL_DATA_KEY não configurada no .env")
        sys.exit(1)

    competitions = [args.competition] if args.competition else list(_COMP_CODE.keys())
    processed_dir = settings.PROCESSED_DATA_DIR
    processed_dir.mkdir(parents=True, exist_ok=True)

    for comp in competitions:
        print(f"\n{'─'*50}")
        print(f"Processando: {comp}")
        print(f"{'─'*50}")

        df = process_competition(comp)
        if df is None or df.empty:
            print(f"  Sem dados para {comp}. Pulando.")
            continue

        out_path = processed_dir / f"{comp}_real_2022-2025.csv"
        df.to_csv(out_path, index=False)
        print(f"  Salvo: {out_path} ({len(df)} partidas, {df['date'].min().date()} → {df['date'].max().date()})")

        if not args.dry_run:
            train(comp, df)
        else:
            print("  (dry-run: treinamento pulado)")

    print("\nConcluído! Modelos salvos em models_artifacts/")


if __name__ == "__main__":
    main()
