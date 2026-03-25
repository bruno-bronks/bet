"""
scripts/fetch_season_stats.py

Busca estatísticas (cartões, cantos, chutes, posse) dos jogos finalizados
da temporada atual via api-sports.io e preenche os CSVs de dados.

Uso:
    python scripts/fetch_season_stats.py                       # ambas as competições
    python scripts/fetch_season_stats.py --competition brasileirao
    python scripts/fetch_season_stats.py --competition champions_league
    python scripts/fetch_season_stats.py --max-per-run 50     # limita chamadas por execução

Limites api-sports.io (plano gratuito):
    - 100 requisições/dia
    - Cada jogo requer 1 chamada → execute diariamente até cobrir todos os jogos
    - O script é incremental: pula jogos que já têm dados

Saída:
    - Atualiza brasileirao_real_2026.csv
    - Atualiza champions_league_real_2526.csv
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger
from app.services.football_api import TEAM_NAME_MAP, _normalize_team

logger = get_logger("fetch_season_stats")

# ── Configuração ───────────────────────────────────────────────────────────────

_AS_LEAGUE_IDS = {"brasileirao": 71, "champions_league": 2}

_SEASON_CSV: dict[str, Path] = {
    "brasileirao":      settings.PROCESSED_DATA_DIR / "brasileirao_real_2026.csv",
    "champions_league": settings.PROCESSED_DATA_DIR / "champions_league_real_2526.csv",
}

# Colunas que tentamos preencher com as stats do api-sports.io
_STATS_COLS = [
    "home_yellow_cards", "away_yellow_cards",
    "home_red_cards",    "away_red_cards",
    "home_corners",      "away_corners",
    "home_shots",        "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "home_fouls",        "away_fouls",
    "home_possession",   "away_possession",
]

RATE_LIMIT_SLEEP = 1.3   # segundos entre chamadas à API
DEFAULT_MAX_PER_RUN = 80  # preserva cota diária de 100 req/dia


# ── Helpers de API ─────────────────────────────────────────────────────────────

def _current_season(competition: str) -> int:
    today = date.today()
    if competition == "brasileirao":
        return today.year
    return today.year if today.month >= 7 else today.year - 1


def _api_get(path: str, params: dict) -> dict | None:
    key = settings.API_FOOTBALL_KEY
    if not key:
        return None
    base = settings.API_FOOTBALL_BASE_URL.rstrip("/")
    headers = {"x-apisports-key": key, "Accept": "application/json"}
    try:
        r = httpx.get(f"{base}/{path}", headers=headers, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            logger.warning(f"API error: {data['errors']}")
            return None
        remaining = r.headers.get("x-ratelimit-requests-remaining", "?")
        logger.debug(f"  API req ok — cota restante: {remaining}")
        return data
    except Exception as e:
        logger.error(f"Falha na requisição {path}: {e}")
        return None


# ── Busca fixtures e stats ─────────────────────────────────────────────────────

def _fetch_finished_fixtures(competition: str, season: int) -> list[dict]:
    """Retorna todos os jogos finalizados da temporada no api-sports.io."""
    lid = _AS_LEAGUE_IDS.get(competition)
    if not lid:
        return []
    data = _api_get("fixtures", {
        "league": lid, "season": season, "status": "FT-AET-PEN",
    })
    fixtures = (data or {}).get("response", [])
    logger.info(f"  api-sports.io → {len(fixtures)} jogos finalizados para {competition}/{season}")
    return fixtures


def _fetch_fixture_stats(fixture_id: int) -> list[dict]:
    """Retorna a lista de estatísticas por time para um jogo."""
    data = _api_get("fixtures/statistics", {"fixture": fixture_id})
    return (data or {}).get("response", [])


def _parse_team_stats(stats_list: list[dict]) -> dict:
    """Converte lista de stats de um time para dict de colunas."""
    def _val(type_name: str):
        v = next((s.get("value") for s in stats_list if s.get("type") == type_name), None)
        if isinstance(v, str) and "%" in v:
            try:
                return float(v.replace("%", "").strip())
            except ValueError:
                return None
        return v

    return {
        "yellow_cards":     int(_val("Yellow Cards") or 0),
        "red_cards":        int(_val("Red Cards") or 0),
        "corners":          _val("Corner Kicks"),
        "shots":            _val("Total Shots"),
        "shots_on_target":  _val("Shots on Goal"),
        "fouls":            _val("Fouls"),
        "possession":       _val("Ball Possession"),
    }


def _extract_game_stats(stats_response: list[dict]) -> dict | None:
    """
    stats_response[0] = time da casa, stats_response[1] = visitante.
    Retorna dict com colunas home_* e away_*.
    """
    if len(stats_response) < 2:
        return None
    home = _parse_team_stats(stats_response[0].get("statistics", []))
    away = _parse_team_stats(stats_response[1].get("statistics", []))
    return {
        "home_yellow_cards":     home["yellow_cards"],
        "away_yellow_cards":     away["yellow_cards"],
        "home_red_cards":        home["red_cards"],
        "away_red_cards":        away["red_cards"],
        "home_corners":          home["corners"],
        "away_corners":          away["corners"],
        "home_shots":            home["shots"],
        "away_shots":            away["shots"],
        "home_shots_on_target":  home["shots_on_target"],
        "away_shots_on_target":  away["shots_on_target"],
        "home_fouls":            home["fouls"],
        "away_fouls":            away["fouls"],
        "home_possession":       home["possession"],
        "away_possession":       away["possession"],
    }


# ── Matching CSV ↔ api-sports.io ──────────────────────────────────────────────

def _build_api_index(fixtures_api: list[dict]) -> dict[tuple, int]:
    """
    Indexa os fixtures do api-sports.io por (date_str, home_norm, away_norm).
    Usa datas ±1 dia para absorver diferença de fuso UTC.
    """
    idx: dict[tuple, int] = {}
    for item in fixtures_api:
        fix = item.get("fixture", {})
        teams = item.get("teams", {})
        fid = fix.get("id")
        if not fid:
            continue
        dt_raw = fix.get("date", "")[:10]
        home = _normalize_team(teams.get("home", {}).get("name", ""))
        away = _normalize_team(teams.get("away", {}).get("name", ""))
        if not (home and away and dt_raw):
            continue
        idx[(dt_raw, home, away)] = fid
        # Adiciona ±1 dia para absorver diferença de fuso
        try:
            d = date.fromisoformat(dt_raw)
            idx[((d - timedelta(days=1)).isoformat(), home, away)] = fid
            idx[((d + timedelta(days=1)).isoformat(), home, away)] = fid
        except ValueError:
            pass
    return idx


def _find_fixture_id(
    row_date: str, home_team: str, away_team: str,
    api_index: dict[tuple, int],
) -> int | None:
    """Tenta encontrar o fixture_id pelo par de times e data."""
    date_str = str(row_date)[:10]
    home_norm = _normalize_team(home_team)
    away_norm  = _normalize_team(away_team)
    return api_index.get((date_str, home_norm, away_norm))


# ── Processamento principal ────────────────────────────────────────────────────

def process_competition(competition: str, max_per_run: int) -> int:
    """
    Atualiza o CSV da competição com stats da temporada atual.
    Retorna o número de jogos atualizados nesta execução.
    """
    csv_path = _SEASON_CSV.get(competition)
    if not csv_path or not csv_path.exists():
        logger.error(f"CSV não encontrado: {csv_path}")
        return 0

    season = _current_season(competition)
    logger.info(f"\n{'='*56}")
    logger.info(f"Competição : {competition}")
    logger.info(f"Temporada  : {season}")
    logger.info(f"CSV        : {csv_path.name}")

    df = pd.read_csv(csv_path)

    # Garante que as colunas de stats existam
    for col in _STATS_COLS:
        if col not in df.columns:
            df[col] = None

    # Jogos que ainda não têm cartões
    missing_mask = df["home_yellow_cards"].isna()
    n_missing = missing_mask.sum()
    logger.info(f"Jogos sem stats: {n_missing} / {len(df)}")

    if n_missing == 0:
        logger.info("  Tudo já preenchido — nada a fazer.")
        return 0

    # Busca fixtures no api-sports.io (1 req)
    fixtures_api = _fetch_finished_fixtures(competition, season)
    if not fixtures_api:
        logger.warning("  Nenhum fixture retornado pelo api-sports.io.")
        return 0

    api_index = _build_api_index(fixtures_api)
    logger.info(f"  Index api-sports.io: {len(api_index)} entradas (inclui ±1 dia)")

    # Itera pelos jogos sem stats
    updated = 0
    skipped_no_match = 0
    api_calls_used = 1  # contabiliza a chamada de fixtures acima

    for idx in df[missing_mask].index:
        if updated >= max_per_run:
            logger.info(f"  Limite de {max_per_run} atualizações por execução atingido.")
            break

        row = df.loc[idx]
        fid = _find_fixture_id(
            str(row.get("date", ""))[:10],
            str(row.get("home_team", "")),
            str(row.get("away_team", "")),
            api_index,
        )

        if fid is None:
            skipped_no_match += 1
            logger.debug(
                f"  Sem match: {row.get('home_team')} vs {row.get('away_team')} "
                f"({str(row.get('date',''))[:10]})"
            )
            continue

        time.sleep(RATE_LIMIT_SLEEP)
        api_calls_used += 1

        stats_raw = _fetch_fixture_stats(fid)
        game_stats = _extract_game_stats(stats_raw)
        if game_stats is None:
            logger.warning(f"  Stats vazias para fixture {fid}")
            continue

        for col, val in game_stats.items():
            if col in df.columns and val is not None:
                df.at[idx, col] = val

        updated += 1
        logger.info(
            f"  [{updated:>3}] {row.get('home_team')} vs {row.get('away_team')} "
            f"({str(row.get('date',''))[:10]}) "
            f"— amarelos: {game_stats['home_yellow_cards']}/{game_stats['away_yellow_cards']}"
        )

    # Salva
    if updated > 0:
        df.to_csv(csv_path, index=False)
        logger.info(f"\n  Salvo: {csv_path.name}")

    logger.info(
        f"\n  Resumo {competition}: {updated} atualizados, "
        f"{skipped_no_match} sem match, {api_calls_used} req usadas"
    )
    return updated


# ── Entrada ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preenche stats de cartões/cantos da temporada atual via api-sports.io"
    )
    parser.add_argument(
        "--competition",
        choices=list(_AS_LEAGUE_IDS.keys()),
        help="Competição a processar (padrão: ambas)",
    )
    parser.add_argument(
        "--max-per-run", type=int, default=DEFAULT_MAX_PER_RUN,
        help=f"Máx. jogos a atualizar por execução (padrão: {DEFAULT_MAX_PER_RUN})",
    )
    args = parser.parse_args()

    if not settings.API_FOOTBALL_KEY:
        logger.error("API_FOOTBALL_KEY não configurada no .env")
        sys.exit(1)

    competitions = [args.competition] if args.competition else list(_AS_LEAGUE_IDS.keys())

    total = 0
    for comp in competitions:
        total += process_competition(comp, args.max_per_run)

    if total > 0:
        logger.info(
            f"\nTotal atualizado: {total} jogos.\n"
            "Reinicie o backend para recarregar os dados:\n"
            "  uvicorn app.api.main:app --reload --port 8000"
        )
    else:
        logger.info("\nNenhum jogo atualizado nesta execução.")


if __name__ == "__main__":
    main()
